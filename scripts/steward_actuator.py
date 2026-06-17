#!/usr/bin/env python3
"""Steward Actuator - reversible, autonomy-gated steward actions.

Consumes `_inbox/steward-findings.jsonl` and takes reversible, autonomy-gated
actions based on finding type and severity. Never hard-deletes anything.

TWO action paths:

1. DEAD-HOOK ARCHIVER (AUTONOMOUS-class)
   For retirement findings carrying the HIGH-confidence "not registered = never
   fires" marker, MOVE the hook file to `_archive/retired/<basename>-<stamp>` and
   write a restore record to `_ledgers/steward-auto-archive.jsonl`.

2. OVERDUE EMITTER (SUPERVISED-class)
   For P0+P1 overdue follow-up findings, write a structured actionable record to
   `_inbox/steward-actions-pending.jsonl` for a human / SessionStart surface to
   action. Does NOT create tasks directly.

Safety guards (do NOT weaken):
  - Invariant B (verifier/safety spine): any finding whose source/detail touches
    a spine path is forced INTERACTIVE (never auto-acted). The spine registry is
    imported from scripts.lib.verifier.spine; if that import fails the guard
    FAILS CLOSED (treats everything as spine -> nothing auto-archived). In a
    pre-spine install (the spine ships later) this means the archiver is fully
    dormant until the spine exists - the intended conservative default.
  - Library/test/reference guard: a HIGH-confidence candidate is only archived if
    it is genuinely a dead event handler - not a test file, not a shared library,
    not referenced/sourced/imported anywhere. Failing candidates DOWNGRADE to a
    SUPERVISED manual-review record, never silent-dropped.
"""

from __future__ import annotations

import argparse
try:
    import fcntl  # POSIX file locking
except ImportError:  # Windows: degrade to best-effort lock-free (no fcntl)
    class _NoFcntl:
        LOCK_EX = LOCK_UN = LOCK_NB = LOCK_SH = 0
        @staticmethod
        def flock(*_a, **_k):
            return None
    fcntl = _NoFcntl()
import json
import os
import re
import shlex
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent  # scripts/


def _plugin_root() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return _HERE.parent  # scripts/ -> plugin root


REPO_ROOT = _plugin_root()

# Make the steward_checks package + the verifier spine importable.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from steward_checks.common import HIGH_CONFIDENCE_MARKER  # noqa: E402

# Verification/safety-spine registry (Invariant B). FAIL-CLOSED: if the spine lib
# is unavailable (e.g. it ships in a later phase) we cannot prove a file is NOT
# spine, so treat EVERYTHING as spine -> all findings INTERACTIVE -> the
# autonomous archiver halts until the spine exists. Loud on stderr; never silent.
try:
    from scripts.lib.verifier.spine import is_spine_path as _is_spine_path
    _SPINE_AVAILABLE = True
except Exception as _spine_err:  # pragma: no cover - exercised pre-spine + in tests
    # Pre-spine (the spine ships in a later phase) OR a genuinely broken registry.
    # FAIL-CLOSED at the archive guard: _is_spine_path returns True so nothing is
    # ever auto-archived. But we DON'T force every finding to INTERACTIVE in
    # classify_action (that would silence the reversible SUPERVISED emitter too);
    # instead retirement findings flow to AUTONOMOUS, hit the fail-closed archive
    # guard, and DOWNGRADE to a SUPERVISED manual-review record. So pre-spine the
    # actuator surfaces candidates for humans but never acts on them itself.
    sys.stderr.write(
        f"[steward] spine registry unavailable ({_spine_err}); Invariant-B guard "
        "FAIL-CLOSED (nothing auto-archived; findings downgrade to SUPERVISED).\n"
    )
    _SPINE_AVAILABLE = False

    def _is_spine_path(_path: str) -> bool:  # type: ignore[misc]
        return True


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FINDINGS_PATH = REPO_ROOT / "_inbox" / "steward-findings.jsonl"
ARCHIVE_DIR = REPO_ROOT / "_archive" / "retired"
ARCHIVE_LEDGER = REPO_ROOT / "_ledgers" / "steward-auto-archive.jsonl"
PENDING_ACTIONS_PATH = REPO_ROOT / "_inbox" / "steward-actions-pending.jsonl"
FAILURES_LEDGER = REPO_ROOT / "_ledgers" / "steward-failures.jsonl"
REVIEWED_KEEP_PATH = REPO_ROOT / "_autonomous" / "steward-reviewed-keep.json"

HARD_TIMEOUT_S = 60

SUPERVISED_SEVERITIES = frozenset({"P0", "P1"})
RETIREMENT_MODULE = "retirement"
FOLLOWUP_MODULE = "followup"


class AutonomyClass:
    AUTONOMOUS = "AUTONOMOUS"
    SUPERVISED = "SUPERVISED"
    INTERACTIVE = "INTERACTIVE"


def classify_action(finding: dict[str, Any]) -> str:
    """Map a finding to an autonomy class (first matching rule wins)."""
    module = finding.get("module", "")
    severity = finding.get("severity", "")
    detail = finding.get("detail", "")
    title = finding.get("title", "").lower()
    source = finding.get("source", "")

    # INTERACTIVE override: production/security content.
    if any(kw in title for kw in ("production", "security", "credential", "auth", "secret")):
        return AutonomyClass.INTERACTIVE
    if any(kw in detail.lower() for kw in ("production", "security", "credential")):
        return AutonomyClass.INTERACTIVE

    # INTERACTIVE override (Invariant B): never auto-act on a safety-spine file.
    # Only when the spine registry is genuinely available - otherwise every
    # finding would be forced INTERACTIVE (the fail-closed _is_spine_path returns
    # True for everything), silencing the reversible SUPERVISED emitter too. When
    # the registry is absent, retirement findings instead reach the fail-closed
    # archive guard and downgrade to SUPERVISED (never auto-archived).
    if _SPINE_AVAILABLE and (_is_spine_path(source) or _is_spine_path(detail)):
        return AutonomyClass.INTERACTIVE

    # AUTONOMOUS: HIGH-confidence dead retirement candidate.
    if module == RETIREMENT_MODULE and HIGH_CONFIDENCE_MARKER in detail:
        return AutonomyClass.AUTONOMOUS

    # SUPERVISED: P0/P1 follow-up -> needs a human task decision.
    if module == FOLLOWUP_MODULE and severity in SUPERVISED_SEVERITIES:
        return AutonomyClass.SUPERVISED

    # SUPERVISED: LOW-confidence retirement (cannot confirm dead).
    if module == RETIREMENT_MODULE:
        return AutonomyClass.SUPERVISED

    return AutonomyClass.SUPERVISED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _utc_now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with open(path, "a", encoding="utf-8") as fh:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            except OSError:
                pass
            fh.write(line)
    except Exception:
        pass


def _write_failure(error: BaseException, context: str = "") -> None:
    try:
        entry = {
            "ts": time.time(),
            "ts_iso": _utc_now_iso(),
            "module": "steward_actuator",
            "error_type": type(error).__name__,
            "error_msg": str(error)[:500],
            "context": context[:300],
        }
        _append_jsonl(FAILURES_LEDGER, entry)
    except Exception:
        pass


def _resolve_hook_path(finding: dict[str, Any]) -> Optional[Path]:
    source = finding.get("source", "")
    if not source:
        return None
    # Containment guard (RC#1): a finding row's `source` is untrusted input. A
    # `..` traversal must never let archive_dead_hook move a file outside the
    # plugin root. Resolve and require the result to live under REPO_ROOT.
    candidate = (REPO_ROOT / source).resolve()
    root = REPO_ROOT.resolve()
    if root not in candidate.parents:
        return None
    if candidate.exists():
        return candidate
    return None


# ---------------------------------------------------------------------------
# Library/test/reference safety guard
# ---------------------------------------------------------------------------

_TEST_FILE_PATTERNS = (
    re.compile(r"^test[-_].*\.(sh|py)$"),
    re.compile(r".*[-_]test\.(sh|py)$"),
)
# Lite component dirs scanned for inbound references.
_REFERENCE_SCAN_DIRS = ("hooks", "scripts", "agents", "commands", "skills")
_SCAN_SKIP_SUFFIXES = (".jsonl", ".log", ".pyc", ".png", ".jpg", ".gif", ".zip", ".gz")
_SCAN_SKIP_DIR_PARTS = frozenset({
    "__pycache__", "node_modules", ".git", "_archive", "tests", ".venv",
})
_SCAN_MAX_FILE_BYTES = 524_288


def _is_test_file(path_str: str) -> bool:
    p = Path(path_str)
    if any(part in ("tests", "test") for part in p.parts):
        return True
    return any(pat.match(p.name) for pat in _TEST_FILE_PATTERNS)


def _scan_referenced_basenames(
    basenames: set[str],
    repo_root: Path = REPO_ROOT,
) -> set[str]:
    """Return the subset of `basenames` referenced (as a whole token) by any file
    under the reference-scan dirs, excluding the file's own definition.

    Fail-CLOSED: any unexpected error -> treat ALL candidates as referenced
    (never auto-archive on error).
    """
    if not basenames:
        return set()
    found: set[str] = set()
    patterns = {
        b: re.compile(r"(?<![\w.-])" + re.escape(b) + r"(?![\w-])")
        for b in basenames
    }
    try:
        for scan_dir in _REFERENCE_SCAN_DIRS:
            base = repo_root / scan_dir
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if len(found) == len(basenames):
                    return found
                try:
                    if not path.is_file():
                        continue
                    if any(part in _SCAN_SKIP_DIR_PARTS for part in path.parts):
                        continue
                    if path.suffix in _SCAN_SKIP_SUFFIXES:
                        continue
                    if path.name in basenames:
                        continue
                    if path.stat().st_size > _SCAN_MAX_FILE_BYTES:
                        continue
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except (OSError, ValueError):
                    continue
                for b, pat in patterns.items():
                    if b in found:
                        continue
                    if pat.search(text):
                        found.add(b)
    except Exception:
        return set(basenames)
    return found


def load_reviewed_keep_ids(path: Path = REVIEWED_KEEP_PATH) -> set[str]:
    """Return finding item_ids a human explicitly reviewed as KEEP. Fail-open:
    missing/malformed -> empty set."""
    try:
        if not path.exists():
            return set()
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("reviewed", []) if isinstance(data, dict) else []
        return {
            str(e["item_id"])
            for e in entries
            if isinstance(e, dict) and e.get("item_id") and e.get("verdict") == "keep"
        }
    except Exception:
        return set()


def is_safe_to_autonomously_archive(
    finding: dict[str, Any],
    repo_root: Path = REPO_ROOT,
    _referenced: Optional[set[str]] = None,
) -> tuple[bool, str]:
    """Decide whether a HIGH-confidence retirement finding is genuinely a dead
    event handler (safe to AUTONOMOUS-archive) vs a library/test/reference false
    positive. Returns (safe, reason)."""
    source = finding.get("source", "")
    if not source:
        return False, "file not found on disk"
    if _is_spine_path(source):
        return False, f"verification/safety-spine file (never auto-archive): {source}"
    # Containment guard (RC#1): reject a `source` that escapes the repo root.
    hook_path = (repo_root / source).resolve()
    if repo_root.resolve() not in hook_path.parents:
        return False, f"path escapes repo root (rejected): {source}"
    if not hook_path.exists():
        return False, "file not found on disk"
    if _is_test_file(source):
        return False, f"test file (archiving loses coverage): {source}"
    basename = hook_path.name
    if _referenced is None:
        _referenced = _scan_referenced_basenames({basename}, repo_root=repo_root)
    if basename in _referenced:
        return False, f"referenced/sourced elsewhere (dependency, not dead): {basename}"
    return True, "genuinely dead event handler (no refs, not a test)"


# ---------------------------------------------------------------------------
# AUTONOMOUS path: dead-hook archiver
# ---------------------------------------------------------------------------

def archive_dead_hook(finding: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Move a dead hook file to _archive/retired/ and log the restore record.
    Never raises. Never hard-deletes."""
    item_id = finding.get("item_id", "unknown")
    result: dict[str, Any] = {"ok": False, "archive_path": None, "error": None}

    hook_path = _resolve_hook_path(finding)
    if hook_path is None:
        result["error"] = f"hook file not found on disk for item_id={item_id!r}"
        return result

    stamp = _utc_now_stamp()
    archive_name = f"{hook_path.name}-{stamp}"
    archive_path = ARCHIVE_DIR / archive_name
    while archive_path.exists():
        archive_name = f"{hook_path.name}-{stamp}-{os.urandom(4).hex()}"
        archive_path = ARCHIVE_DIR / archive_name

    abs_original = str(hook_path.resolve() if hook_path.is_absolute() else (REPO_ROOT / hook_path).resolve())
    abs_archive = str(archive_path if archive_path.is_absolute() else (REPO_ROOT / archive_path).resolve())
    try:
        rel_original = str(hook_path.relative_to(REPO_ROOT))
    except ValueError:
        rel_original = str(hook_path)
    try:
        rel_archive = str(archive_path.relative_to(REPO_ROOT))
    except ValueError:
        rel_archive = str(archive_path)
    revert_cmd = f"cp {shlex.quote(abs_archive)} {shlex.quote(abs_original)}"

    ledger_record: dict[str, Any] = {
        "ts": time.time(),
        "ts_iso": _utc_now_iso(),
        "action": "archive",
        "original_path": rel_original,
        "original_path_abs": abs_original,
        "archive_path": rel_archive,
        "archive_path_abs": abs_archive,
        "revert_cmd": revert_cmd,
        "finding_item_id": item_id,
        "finding_severity": finding.get("severity", ""),
        "finding_detail": finding.get("detail", ""),
        "autonomy_class": AutonomyClass.AUTONOMOUS,
        "dry_run": dry_run,
    }

    if dry_run:
        result["ok"] = True
        result["archive_path"] = rel_archive
        _append_jsonl(ARCHIVE_LEDGER, ledger_record)
        return result

    try:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        # Write the restore-ledger record BEFORE moving the file (crash-safety:
        # worst case is an over-reported archive, never an unrecoverable move).
        _append_jsonl(ARCHIVE_LEDGER, ledger_record)
        shutil.move(str(hook_path), str(archive_path))
        result["ok"] = True
        result["archive_path"] = rel_archive
    except Exception as exc:
        result["error"] = str(exc)
        _write_failure(exc, f"archive_dead_hook: {item_id}")
    return result


# ---------------------------------------------------------------------------
# SUPERVISED path: overdue emitter + manual-review downgrade
# ---------------------------------------------------------------------------

def emit_pending_action(finding: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Write a pending-action record for P0/P1 overdue follow-up findings. Does
    NOT create tasks. Never raises."""
    title = finding.get("title", "")
    days_overdue = finding.get("days_overdue")
    item_id = finding.get("item_id", "")
    source = finding.get("source", "")
    severity = finding.get("severity", "P1")

    overdue_str = f" ({days_overdue}d overdue)" if days_overdue else ""
    record: dict[str, Any] = {
        "ts": time.time(),
        "ts_iso": _utc_now_iso(),
        "action_type": "create_task",
        "autonomy_class": AutonomyClass.SUPERVISED,
        "finding_module": finding.get("module", ""),
        "finding_severity": severity,
        "finding_title": title,
        "finding_source": source,
        "finding_item_id": item_id,
        "days_overdue": days_overdue,
        "suggested_task_title": f"[steward-auto] {title}{overdue_str}",
        "suggested_task_body": (
            f"Auto-emitted by steward_actuator (SUPERVISED path).\n"
            f"Source: {source}\nItem ID: {item_id}\nSeverity: {severity}\n"
            f"Detail: {finding.get('detail', '')}\n\n"
            f"Action: review this overdue item and complete, defer with a new "
            f"date, or close as no-longer-relevant."
        ),
        "dry_run": dry_run,
    }
    if not dry_run:
        _append_jsonl(PENDING_ACTIONS_PATH, record)
    return {"ok": True, "record": record}


def emit_manual_retirement_pending(
    finding: dict[str, Any], reason: str, dry_run: bool = False
) -> dict[str, Any]:
    """Write a SUPERVISED pending record for a retirement finding that FAILED the
    AUTONOMOUS-archive safety guard. Nothing is moved. Never raises."""
    title = finding.get("title", "")
    item_id = finding.get("item_id", "")
    source = finding.get("source", "")
    severity = finding.get("severity", "P2")
    record: dict[str, Any] = {
        "ts": time.time(),
        "ts_iso": _utc_now_iso(),
        "action_type": "manual_retirement_review",
        "autonomy_class": AutonomyClass.SUPERVISED,
        "finding_module": finding.get("module", ""),
        "finding_severity": severity,
        "finding_title": title,
        "finding_source": source,
        "finding_item_id": item_id,
        "guard_reason": reason,
        "days_overdue": finding.get("days_overdue"),
        "suggested_task_title": f"[steward-auto] manual retirement review: {title}",
        "suggested_task_body": (
            f"Auto-emitted by steward_actuator (AUTONOMOUS->SUPERVISED downgrade).\n"
            f"The dead-hook archiver did NOT auto-archive this file: {reason}\n"
            f"Source: {source}\nItem ID: {item_id}\nSeverity: {severity}\n"
            f"Detail: {finding.get('detail', '')}\n\n"
            f"Action: a human must decide whether to retire this file - it is a "
            f"shared library, a test harness, or referenced elsewhere, so "
            f"archiving it autonomously could break a dependency."
        ),
        "dry_run": dry_run,
    }
    if not dry_run:
        _append_jsonl(PENDING_ACTIONS_PATH, record)
    return {"ok": True, "record": record}


# ---------------------------------------------------------------------------
# Main actuator loop
# ---------------------------------------------------------------------------

def run_actuator(findings_path: Path = FINDINGS_PATH, dry_run: bool = False) -> dict[str, Any]:
    """Read findings and dispatch each to the appropriate autonomy path."""
    summary: dict[str, Any] = {
        "run_at": _utc_now_iso(),
        "dry_run": dry_run,
        "rows_read": 0,
        "autonomous_archived": 0,
        "autonomous_errors": 0,
        "supervised_emitted": 0,
        "downgraded_to_supervised": 0,
        "reviewed_keep_suppressed": 0,
        "skipped": 0,
        "error": None,
    }

    if not findings_path.exists():
        return summary

    try:
        rows: list[dict[str, Any]] = []
        with open(findings_path, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    rows.append(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
        summary["rows_read"] = len(rows)

        # Most-recent finding per (module, item_id).
        seen_keys: set[tuple[str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for row in reversed(rows):
            key = (row.get("module", ""), row.get("item_id", ""))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(row)

        # Only act on still-"silent" findings.
        eligible = [r for r in deduped if r.get("maintainer_decision") == "silent"]

        # One filesystem walk for ALL archive candidates.
        archive_candidates = {
            _resolve_hook_path(f).name
            for f in eligible
            if classify_action(f) == AutonomyClass.AUTONOMOUS
            and _resolve_hook_path(f) is not None
        }
        referenced = _scan_referenced_basenames(archive_candidates, repo_root=REPO_ROOT)
        reviewed_keep = load_reviewed_keep_ids(REVIEWED_KEEP_PATH)

        for finding in eligible:
            autonomy_class = classify_action(finding)
            if autonomy_class == AutonomyClass.AUTONOMOUS:
                safe, reason = is_safe_to_autonomously_archive(
                    finding, repo_root=REPO_ROOT, _referenced=referenced
                )
                if not safe:
                    if finding.get("item_id", "") in reviewed_keep:
                        summary["reviewed_keep_suppressed"] += 1
                        continue
                    emit_manual_retirement_pending(finding, reason, dry_run=dry_run)
                    summary["downgraded_to_supervised"] += 1
                    continue
                # RC#2: a human who reviewed this file as KEEP must never have it
                # autonomously archived, even if it now passes the dead-hook guard.
                if finding.get("item_id", "") in reviewed_keep:
                    summary["reviewed_keep_suppressed"] += 1
                    continue
                result = archive_dead_hook(finding, dry_run=dry_run)
                if result["ok"]:
                    summary["autonomous_archived"] += 1
                else:
                    summary["autonomous_errors"] += 1
            elif autonomy_class == AutonomyClass.SUPERVISED:
                module = finding.get("module", "")
                severity = finding.get("severity", "")
                if module == FOLLOWUP_MODULE and severity in SUPERVISED_SEVERITIES:
                    emit_pending_action(finding, dry_run=dry_run)
                    summary["supervised_emitted"] += 1
                else:
                    summary["skipped"] += 1
            else:
                summary["skipped"] += 1
    except Exception as exc:
        summary["error"] = str(exc)
        _write_failure(exc, "run_actuator")

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reversible, autonomy-gated steward actuator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Print actions without moving files or writing pending records")
    parser.add_argument("--findings-path", type=Path, default=FINDINGS_PATH,
                        metavar="PATH", help="Path to steward-findings.jsonl")
    return parser


def main() -> int:
    import signal

    def _timeout(signum: int, frame: object) -> None:  # noqa: ARG001
        sys.stderr.write("steward_actuator: HARD TIMEOUT\n")
        sys.exit(0)

    try:
        signal.signal(signal.SIGALRM, _timeout)
        signal.alarm(HARD_TIMEOUT_S)
    except (AttributeError, ValueError):
        pass

    args = _build_parser().parse_args()
    summary = run_actuator(findings_path=args.findings_path, dry_run=args.dry_run)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    try:
        signal.alarm(0)
    except (AttributeError, ValueError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
