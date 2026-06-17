"""hook_telemetry - shared invocation/latency/crash ledger for hooks.

Covers three telemetry signals:

  * **hook execution latency p50/p95**: each invocation records
    ``duration_ms``.
  * **hook crash count**: each invocation records ``exit_code``;
    non-fatal crashes surface as ``exit_code != 0`` rows.
  * **per-event invocation count**: each invocation appends a row with
    ``hook`` + ``event``; ``grep hook=foo | wc -l`` answers "did hook X
    fire on event Y?".

Cross-hook lock contention is covered by ``lock_telemetry.py``; SIGKILL/
timeout detection by the marker files below (a SessionStart scanner can
synthesize timeout rows from orphaned markers).

Design constraints
------------------
* **Fail-open**: any exception in this module is swallowed and the
  caller proceeds normally; telemetry must never break a hook.
* **Single shared sink** ``_ledgers/hook-invocations.jsonl`` so a
  consumer can answer "did hook X fire?" with one grep, not a fan-out
  across 35 per-hook files.
* **Append-only with fcntl locking** when available, atomic
  ``open(..., 'a')`` write otherwise. The single-line JSON-per-row
  shape tolerates partial-write interleaving better than read-modify-
  write JSON blobs.
* **No external imports** beyond stdlib so it can be imported by any
  hook without dependency risk.

Usage from a hook
-----------------

    from hook_telemetry import track_hook
    # at top of main():
    with track_hook("post-tool-tracker", event="PostToolUse",
                    session_id=session_id) as t:
        ...hook body...
        # t.set_error("custom failure reason")   # optional
        # t.add_meta(key=value)                  # optional

The context manager records ``duration_ms`` from enter to exit and
captures the exit_code via ``sys.exit`` interception. Exceptions are
caught, recorded as ``exit_code=1`` with ``error`` set, then
re-raised so the hook's own fail-open path runs.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional


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


# --- Marker-file helpers (Signal 2: timeout/SIGKILL detection) ----------------
#
# On track_hook.__enter__, a small JSON file is written to the marker dir.
# On __exit__ (normal OR exception), the file is deleted.  If the hook
# subprocess is SIGKILLed mid-execution, __exit__ never runs and the marker
# persists.  hook-timeout-scanner.py picks it up at the next SessionStart,
# synthesises a "timeout-detected" row in hook-invocations.jsonl, and cleans up.
#
# Design constraints: same fail-open invariant as the rest of this module.
# O_NOFOLLOW guards against symlink TOCTOU attacks.

_MARKER_DIR_DEFAULT = os.path.join(tempfile.gettempdir(), "hook-active")
_MARKER_DIR_MODE = 0o700


def _marker_dir() -> Path:
    """Return the directory used for active-hook markers.

    Reads ``HOOK_ACTIVE_MARKER_DIR`` env var first so tests can redirect to a
    temp directory without touching /tmp.
    """
    return Path(os.environ.get("HOOK_ACTIVE_MARKER_DIR", _MARKER_DIR_DEFAULT))


def _sanitize_marker_component(s: str) -> str:
    """Replace unsafe characters in marker filename components.

    Prevents path traversal via untrusted session_id or hook values (which can
    originate from CC's stdin payload or env vars).  Keeps the component
    recognisable while ensuring it stays within the marker directory.
    """
    import re as _re
    return _re.sub(r"[^A-Za-z0-9_\-]", "_", s)[:128]


def _marker_path(session_id: str, pid: int, hook: str) -> Path:
    """Return the Path for a specific hook's active marker."""
    safe_sid = _sanitize_marker_component(session_id)
    safe_hook = _sanitize_marker_component(hook)
    return _marker_dir() / f"{safe_sid}-{pid}-{safe_hook}.json"


def _write_marker(session_id: str, pid: int, hook: str) -> None:
    """Write a marker file signalling this hook is actively running.

    Fail-open: any OS error (including O_NOFOLLOW symlink rejection) is
    swallowed silently so the hook is never blocked.
    """
    try:
        d = _marker_dir()
        d.mkdir(mode=_MARKER_DIR_MODE, parents=True, exist_ok=True)
        p = _marker_path(session_id, pid, hook)
        fd = os.open(
            str(p),
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            data = json.dumps(
                {"started_at": _now_iso(), "hook": hook, "pid": pid, "session": session_id},
                separators=(",", ":"),
            ).encode()
            os.write(fd, data)
        finally:
            os.close(fd)
    except Exception:  # noqa: BLE001 - fail-open contract
        return


def _delete_marker(session_id: str, pid: int, hook: str) -> None:
    """Remove the active-hook marker.  Fail-open: missing file is not an error."""
    try:
        _marker_path(session_id, pid, hook).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001 - fail-open contract
        return


def _ledger_path() -> Path:
    return _project_dir() / "_ledgers" / "hook-invocations.jsonl"


def _resolve_session_id(input_data: Optional[Dict] = None) -> str:
    """Same fallback chain as session_attribution.resolve_session_id so
    cross-hook rows agree on session attribution."""
    sid: Optional[str] = None
    if isinstance(input_data, dict):
        sid = input_data.get("session_id") or input_data.get("session")
    if not sid:
        sid = os.environ.get("CLAUDE_SESSION_ID")
    if not sid:
        sid = f"pid-{os.getppid()}"
    return sid or "unknown"


def _now_iso() -> str:
    # Local import to keep top-level imports minimal.
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _append_row(row: Dict[str, Any]) -> None:
    """Append one JSON row. Fail-open: swallow any IO error."""
    try:
        path = _ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, separators=(",", ":")) + "\n"
        # Best-effort fcntl lock; cross-process atomic append is the
        # POSIX-guaranteed property of O_APPEND for writes under
        # PIPE_BUF (4096 on macOS/Linux). Our rows are well under that.
        try:
            import fcntl
            with open(path, "a", encoding="utf-8") as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    f.write(line)
                finally:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except (OSError, IOError):
                        pass
        except ImportError:
            # No fcntl (eg. Windows): plain append. O_APPEND atomicity
            # alone is sufficient for sub-PIPE_BUF writes.
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception:  # noqa: BLE001 - fail-open contract
        return


class _Tracker:
    """Mutable handle returned by ``track_hook``; lets callers attach
    error reasons or arbitrary metadata before the row is flushed."""

    def __init__(self) -> None:
        self.error: Optional[str] = None
        self.meta: Dict[str, Any] = {}

    def set_error(self, msg: str) -> None:
        # Keep error short to bound ledger row size.
        self.error = (msg or "")[:200]

    def add_meta(self, **kwargs: Any) -> None:
        # meta is for caller-supplied bookkeeping (eg. action, reason).
        # Keep keys flat and JSON-serializable.
        for k, v in kwargs.items():
            self.meta[str(k)[:64]] = v


@contextmanager
def track_hook(
    hook: str,
    *,
    event: Optional[str] = None,
    session_id: Optional[str] = None,
    input_data: Optional[Dict] = None,
) -> Iterator[_Tracker]:
    """Context manager wrapping a hook's body.

    Records one row to ``_ledgers/hook-invocations.jsonl`` on exit.
    Re-raises exceptions after recording so the caller's existing
    fail-open path (or top-level ``except``) still runs.

    Arguments
    ---------
    hook : short stable identifier, eg. "post-tool-tracker".
    event : the CC hook event name (PostToolUse, SessionStart, ...).
        If None and ``input_data`` is given, derived from
        ``input_data["hook_event_name"]``.
    session_id : explicit session id; if None, resolved from
        ``input_data`` / env / ppid.
    input_data : the raw stdin payload (used only to derive event +
        session_id when they are not passed explicitly).
    """
    t = _Tracker()
    started = time.monotonic()
    exit_code = 0
    # Resolve session_id once so both marker and ledger row use the same value.
    sid = session_id or _resolve_session_id(input_data)
    _write_marker(sid, os.getpid(), hook)
    try:
        yield t
    except SystemExit as exc:  # noqa: TRY302
        # Hook called sys.exit(code). Capture and re-raise so the
        # shell still gets the intended exit status.
        try:
            exit_code = int(exc.code) if exc.code is not None else 0
        except (TypeError, ValueError):
            exit_code = 1
        raise
    except BaseException as exc:  # noqa: BLE001 - record + re-raise
        exit_code = 1
        if not t.error:
            # Truncate traceback to single short line for ledger.
            t.set_error(f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _delete_marker(sid, os.getpid(), hook)
        duration_ms = (time.monotonic() - started) * 1000.0
        derived_event = event
        if derived_event is None and isinstance(input_data, dict):
            derived_event = input_data.get("hook_event_name") or input_data.get("event")
        row: Dict[str, Any] = {
            "ts": _now_iso(),
            "hook": hook,
            "event": derived_event,
            "session": sid,
            "duration_ms": round(duration_ms, 4),
            "exit_code": exit_code,
            "error": t.error,
        }
        if t.meta:
            row["meta"] = t.meta
        _append_row(row)


def record_invocation(
    hook: str,
    *,
    event: Optional[str] = None,
    duration_ms: float = 0.0,
    exit_code: int = 0,
    session_id: Optional[str] = None,
    error: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Direct API for hooks that cannot use the context manager
    (e.g. module-level scripts that exit before reaching a wrap)."""
    sid = session_id or _resolve_session_id()
    row: Dict[str, Any] = {
        "ts": _now_iso(),
        "hook": hook,
        "event": event,
        "session": sid,
        "duration_ms": round(duration_ms, 4),
        "exit_code": int(exit_code),
        "error": error,
    }
    if meta:
        row["meta"] = meta
    _append_row(row)


__all__ = [
    "track_hook",
    "record_invocation",
    "_resolve_session_id",
    "_marker_dir",
    "_marker_path",
    "_write_marker",
    "_delete_marker",
]
