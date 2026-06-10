"""lock_telemetry - cross-hook lock contention ledger.

Records how long hooks block on shared-file locks. Latency/crash/invocation
telemetry is covered by ``hook_telemetry.py``; this module covers the
cross-hook lock-contention signal.

Mechanism
---------
``scripts/cache_writer.py:_exclusive_lock`` is instrumented to capture
``time.monotonic()`` before and after ``fcntl.flock(LOCK_EX)``. The
difference (``wait_ms``) measures how long a hook was blocked waiting
for the lock; the post-yield interval measures ``hold_ms``. Any wait
above the threshold (default 5ms, env-tunable) is appended to
``_ledgers/lock-contention.jsonl`` as a one-line JSON row:

    {"ts": "...", "hook": "...", "target_file": "...",
     "wait_ms": ..., "hold_ms": ...}

5ms is conservative: an uncontended ``fcntl.flock(LOCK_EX)`` against an
existing lockfile completes in <100us on macOS APFS / Linux ext4.
Anything above 5ms is real contention worth recording.

Design constraints
------------------
* **Fail-open**: any exception in this module is swallowed and the
  caller proceeds normally; telemetry must never break the lock
  release path of the instrumented context manager.
* **Single shared sink** ``_ledgers/lock-contention.jsonl`` so a
  consumer can answer "which hook serialized against which file?"
  with one grep, not a fan-out across N per-hook files.
* **Append-only with fcntl.LOCK_EX** when available; the JSONL row is
  well under PIPE_BUF (4096) so O_APPEND atomicity is the fallback.
  The lock used here is on the LEDGER file, not the instrumented
  cache file - no recursion / deadlock with cache_writer's own lock.
* **No external imports** beyond stdlib so cache_writer.py keeps its
  dependency-free profile.
* **Threshold gating**: rows below threshold are dropped on the
  caller's hot path; the ledger captures contention events, not
  every lock acquisition. Use ``LOCK_CONTENTION_THRESHOLD_MS=0``
  during baseline-measurement sessions to record everything.

Usage from cache_writer (called by the instrumented context manager)
--------------------------------------------------------------------

    from lock_telemetry import record_lock_event
    # inside _exclusive_lock, after fcntl.LOCK_EX release:
    record_lock_event(target_path, wait_ms=..., hold_ms=...)

``hook`` is derived from ``sys.argv[0]`` if not passed explicitly;
each instrumented caller can override.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional


# Threshold below which lock acquisition is treated as uncontended and
# the row is dropped. Override via env var; "0" records everything.
_DEFAULT_THRESHOLD_MS = 5.0
_LEDGER_FILENAME = "lock-contention.jsonl"


def _project_dir() -> Path:
    """Data root: plugin root (env) > project dir (env) > walk-up > cwd."""
    for var in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR"):
        v = os.environ.get(var)
        if v:
            return Path(v)
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude-plugin" / "plugin.json").exists():
            return parent
    return Path(os.getcwd())


def _ledger_path() -> Path:
    """Default ledger location; override via ``LOCK_CONTENTION_LEDGER``."""
    override = os.environ.get("LOCK_CONTENTION_LEDGER")
    if override:
        return Path(override)
    return _project_dir() / "_ledgers" / _LEDGER_FILENAME


def _threshold_ms() -> float:
    """Threshold above which a wait is recorded. Env-tunable; fail-safe."""
    raw = os.environ.get("LOCK_CONTENTION_THRESHOLD_MS")
    if raw is None:
        return _DEFAULT_THRESHOLD_MS
    try:
        return float(raw)
    except (TypeError, ValueError):
        return _DEFAULT_THRESHOLD_MS


def _now_iso() -> str:
    """ISO-8601 with UTC offset. Caveat: consumers on Python <3.11 must
    use a portable parser; ``datetime.fromisoformat`` accepts +00:00
    only from 3.11 onwards. See ``hook-timeout-scanner._parse_iso_timestamp``
    for the portable consumer-side helper."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _infer_hook() -> str:
    """Derive caller identification from sys.argv[0]. Strip extension."""
    if sys.argv and sys.argv[0]:
        return Path(sys.argv[0]).stem or "unknown"
    return "unknown"


def _sanitize_hook(s: str) -> str:
    """Same sanitization rule as hook_telemetry._sanitize_marker_component:
    keep ledger rows JSON-safe and bound length, mirror cross-module shape."""
    return re.sub(r"[^A-Za-z0-9_\-./]", "_", s)[:128]


def _relativize_target(target: Path) -> str:
    """Render target as a project-relative path when possible; absolute otherwise.
    Truncate aggressively long paths to keep rows compact."""
    try:
        rel = target.resolve().relative_to(_project_dir().resolve())
        return str(rel)[:256]
    except (ValueError, OSError):
        return str(target)[:256]


def _append_row(row: Dict[str, Any]) -> None:
    """Append one JSON row to the contention ledger. Fail-open on any IO error.

    Mirrors ``hook_telemetry._append_row`` shape so reviewers see the same
    pattern: fcntl.LOCK_EX where available, plain O_APPEND otherwise.
    """
    try:
        path = _ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, separators=(",", ":")) + "\n"
        try:
            import fcntl  # POSIX-only; Windows takes the ImportError fallback.
            with open(path, "a") as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    f.write(line)
                finally:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except (OSError, IOError):
                        pass
        except ImportError:
            # Sub-PIPE_BUF (4096) O_APPEND writes are atomic without fcntl.
            with open(path, "a") as f:
                f.write(line)
    except Exception:  # noqa: BLE001 - fail-open contract
        return


def record_lock_event(
    target: Path,
    wait_ms: float,
    hold_ms: float,
    *,
    hook: Optional[str] = None,
) -> None:
    """Record one lock acquisition event if ``wait_ms`` exceeds threshold.

    Arguments
    ---------
    target : the Path whose lock was contended (the cache file, not the
        ``.lock`` sidecar).
    wait_ms : time spent blocked on ``fcntl.flock(LOCK_EX)``, in milliseconds.
    hold_ms : time the lock was held by the caller, in milliseconds.
    hook : optional caller identification; defaults to ``sys.argv[0]`` stem.

    No-op when ``wait_ms < threshold``. Fail-open on any internal error;
    callers are NOT responsible for catching exceptions from this function.
    """
    try:
        threshold = _threshold_ms()
        # Float compare is safe here: wait_ms originates from
        # time.monotonic() subtraction; NaN cannot occur.
        if wait_ms < threshold:
            return
        row = {
            "ts": _now_iso(),
            "hook": _sanitize_hook(hook or _infer_hook()),
            "target_file": _relativize_target(target),
            "wait_ms": round(float(wait_ms), 3),
            "hold_ms": round(float(hold_ms), 3),
        }
        _append_row(row)
    except Exception:  # noqa: BLE001 - fail-open contract
        return


__all__ = ["record_lock_event"]
