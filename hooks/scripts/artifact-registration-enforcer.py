#!/usr/bin/env python3
"""Artifact Registration Enforcer (PostToolUse[Write|Edit]).

Real-time GAP-CLOSER: intercepts Write/Edit tool calls and dispatches to the
artifact registration framework (scripts/lib/artifact_registration.py), which
upserts the knowledge-graph node, context-router route, detection-index entry,
and queues the Kairn add.

Mode (env var ARTIFACT_REG_MODE):
  - "apply" (default): register the artifact synchronously
  - "observe": log only, no writes (rollback target)

Safety: fail-open. Any exception -> exit 0 silently. SIGALRM hard timeout.
Never blocks the Write tool. Recursion guard via CLAUDE_ARTIFACT_BACKFILL_RUNNING.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()


def _plugin_root() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return SCRIPT_DIR.parent.parent  # hooks/scripts/ -> hooks/ -> plugin root


PLUGIN_ROOT = _plugin_root()

HARD_TIMEOUT_S = 2
MODE_ENV = "ARTIFACT_REG_MODE"
DEFAULT_MODE = "apply"


def _install_hard_timeout(seconds: int) -> None:
    """Install SIGALRM handler. POSIX only; elsewhere this is a no-op."""
    try:
        import signal

        def _handler(signum, frame):
            sys.exit(0)

        signal.signal(signal.SIGALRM, _handler)
        signal.alarm(seconds)
    except (ImportError, AttributeError, ValueError):
        pass


def _read_payload(raw: str) -> dict:
    try:
        if not raw.strip():
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return {}


def _extract_file_path(payload: dict) -> str:
    """Get tool_input.file_path; tolerate missing / non-Write tool calls."""
    tool_name = payload.get("tool_name") or payload.get("tool", "")
    if tool_name not in ("Write", "Edit"):
        return ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return ""
    path = tool_input.get("file_path", "")
    if not isinstance(path, str):
        return ""
    return path.strip()


def main(payload: dict) -> None:
    _install_hard_timeout(HARD_TIMEOUT_S)
    try:
        # Recursion guard: backfill sets this env. Skip immediately.
        if os.environ.get("CLAUDE_ARTIFACT_BACKFILL_RUNNING") == "1":
            sys.exit(0)

        file_path = _extract_file_path(payload)
        if not file_path:
            sys.exit(0)

        # Only register files INSIDE the plugin root; user-project writes are
        # not this plugin's artifacts.
        try:
            if not Path(file_path).resolve().is_relative_to(PLUGIN_ROOT.resolve()):
                sys.exit(0)
        except (OSError, ValueError):
            sys.exit(0)

        # Lazy import: keeps hook startup cheap when path doesn't qualify.
        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        from lib import artifact_registration as ar  # noqa: WPS433

        mode = os.environ.get(MODE_ENV, DEFAULT_MODE)
        if mode not in ("apply", "observe"):
            mode = DEFAULT_MODE

        session_id = payload.get("session_id") or payload.get("session")
        ar.dispatch(file_path, mode=mode, backfill=False, write_ledger=True,
                    session_id=session_id)
    except Exception:
        # Fail-open: never crash the Write tool.
        pass
    sys.exit(0)


if __name__ == "__main__":
    raw_stdin = ""
    try:
        raw_stdin = sys.stdin.read()
    except Exception:
        pass
    payload = _read_payload(raw_stdin)

    try:
        scripts_dir = str(PLUGIN_ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from lib.hook_telemetry import track_hook
        try:
            with track_hook("artifact-registration-enforcer", event="PostToolUse",
                            session_id=payload.get("session_id"),
                            input_data=payload or None):
                main(payload)
        except SystemExit:
            raise
        except Exception:
            sys.exit(0)
    except ImportError:
        try:
            main(payload)
        except Exception:
            sys.exit(0)
