#!/usr/bin/env python3
"""
AutoEvolve Runner Helpers - CLI hooks the autoevolve-optimizer agent calls via
Bash to (a) record rejected mutations and (b) increment/decay habituation counts.

Why a separate script: the optimizer agent's tool set is {Read, Edit, Write,
Bash, Grep, Glob} - no Python import. These helpers expose the Python-side
functions (record_rejected_mutation in autoevolve-scorer.py) + habituation file
CRUD to the agent via Bash subprocess calls.

Subcommands:
  reject            Append a rejected-mutation record to _autoevolve/rejected/.
                    Always exits 0. Stderr on IO failure (consumer can ignore).
  habituate         Increment the habituation counter for a task_type in
                    _autoevolve/.mutation-habituation.json (updates last_seen).
  read-habituation  Print the habituation JSON to stdout. Never errors.
  decay             Halve any count whose last_seen is older than DECAY_DAYS
                    (default 14). Idempotent; never goes negative; drops zeros.

The habituation bias steers mutation selection AWAY from over-mutated task types
(mutation_weight = 1 / (1 + count)). Gated subcommands honor the v2_canary_mode
switch in delegation-config.json: when canary is false a --gated call no-ops,
keeping the inert/active boundary sharp.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from scripts.lib.plugin_paths import plugin_root  # noqa: E402

ROOT = plugin_root()
HABITUATION_FILE = ROOT / "_autoevolve" / ".mutation-habituation.json"
DELEGATION_CONFIG = ROOT / "_graph" / "cache" / "delegation-config.json"
SCORER_PATH = ROOT / "scripts" / "autoevolve-scorer.py"
DECAY_DAYS_DEFAULT = 14


# ---------------------------------------------------------------------------
# Habituation file CRUD
# ---------------------------------------------------------------------------

def _read_habituation() -> dict:
    """Read habituation state. Returns empty schema if file missing/malformed."""
    if not HABITUATION_FILE.exists():
        return {"counts": {}, "last_seen": {}, "version": "1.0"}
    try:
        with open(HABITUATION_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"counts": {}, "last_seen": {}, "version": "1.0"}
        data.setdefault("counts", {})
        data.setdefault("last_seen", {})
        data.setdefault("version", "1.0")
        return data
    except (OSError, json.JSONDecodeError):
        return {"counts": {}, "last_seen": {}, "version": "1.0"}


def _write_habituation(data: dict) -> None:
    """Atomic write via tmp+rename."""
    HABITUATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = HABITUATION_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, HABITUATION_FILE)


def _v2_canary_enabled() -> bool:
    """Read v2_canary_mode switch. False on any read error (fail-closed)."""
    try:
        with open(DELEGATION_CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
        return bool(cfg.get("mutation_rules", {}).get("v2_canary_mode", False))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_reject(args) -> int:
    """Append a rejected-mutation entry via autoevolve-scorer.record_rejected_mutation.

    Imports the scorer module dynamically so it always reflects the current
    on-disk implementation. Never raises - stderr on IO failure.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("autoevolve_scorer", SCORER_PATH)
    if spec is None or spec.loader is None:
        print(f"ERROR: cannot load autoevolve-scorer: spec None at {SCORER_PATH}",
              file=sys.stderr)
        return 0
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f"ERROR: cannot load autoevolve-scorer: {e}", file=sys.stderr)
        return 0  # best-effort
    out_path = mod.record_rejected_mutation(
        root=str(ROOT),
        target=args.target,
        run_id=args.run_id,
        mutation_description=args.description,
        score_before=args.score_before,
        score_after=args.score_after,
        reject_reason=args.reason,
        source_config_hash=args.source_hash,
    )
    if out_path:
        print(json.dumps({"wrote": str(out_path)}))
    return 0


def cmd_habituate(args) -> int:
    """Increment habituation counter for a task_type. Updates last_seen.

    Gated on v2_canary_mode if --gated is passed. Without --gated the call
    always proceeds (useful for dry-run cycles + ECP).
    """
    if args.gated and not _v2_canary_enabled():
        print(json.dumps({"skipped": "v2_canary_mode=false"}))
        return 0
    task_type = args.task_type
    if not task_type:
        print("ERROR: --task-type required", file=sys.stderr)
        return 1
    data = _read_habituation()
    data["counts"][task_type] = data["counts"].get(task_type, 0) + 1
    data["last_seen"][task_type] = datetime.now(timezone.utc).isoformat()
    _write_habituation(data)
    print(json.dumps({
        "task_type": task_type,
        "count": data["counts"][task_type],
        "last_seen": data["last_seen"][task_type],
    }))
    return 0


def cmd_read_habituation(args) -> int:
    """Print the habituation JSON to stdout. Always exits 0."""
    print(json.dumps(_read_habituation(), indent=2, ensure_ascii=False))
    return 0


def cmd_decay(args) -> int:
    """Apply time-decay: counts halve when last_seen > decay_days ago.

    Idempotent: re-runs converge. Never goes below 0. Removes entries that
    decay to 0.
    """
    days = max(1, int(args.days or DECAY_DAYS_DEFAULT))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    data = _read_habituation()
    decayed = removed = 0
    for task_type in list(data["counts"].keys()):
        last_seen_raw = data["last_seen"].get(task_type)
        if not last_seen_raw:
            continue
        try:
            last_dt = datetime.fromisoformat(last_seen_raw.replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if last_dt < cutoff:
            new_count = data["counts"][task_type] // 2
            if new_count <= 0:
                del data["counts"][task_type]
                del data["last_seen"][task_type]
                removed += 1
            else:
                data["counts"][task_type] = new_count
                decayed += 1
    _write_habituation(data)
    print(json.dumps({"decayed": decayed, "removed": removed, "days_threshold": days}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    p_reject = subparsers.add_parser("reject", help="Record a rejected mutation")
    p_reject.add_argument("--target", required=True)
    p_reject.add_argument("--run-id", required=True)
    p_reject.add_argument("--description", required=True)
    p_reject.add_argument("--score-before", required=True, type=float)
    p_reject.add_argument("--score-after", required=True, type=float)
    p_reject.add_argument("--reason", required=True,
                          help="Short tag: regression, plateau, north_star_lock")
    p_reject.add_argument("--source-hash", default=None)
    p_reject.set_defaults(func=cmd_reject)

    p_hab = subparsers.add_parser("habituate", help="Increment habituation count")
    p_hab.add_argument("--task-type", required=True)
    p_hab.add_argument("--gated", action="store_true",
                       help="Skip when v2_canary_mode is false")
    p_hab.set_defaults(func=cmd_habituate)

    p_read = subparsers.add_parser("read-habituation", help="Print habituation JSON")
    p_read.set_defaults(func=cmd_read_habituation)

    p_decay = subparsers.add_parser("decay", help="Apply time-decay to counts")
    p_decay.add_argument("--days", type=int, default=DECAY_DAYS_DEFAULT)
    p_decay.set_defaults(func=cmd_decay)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
