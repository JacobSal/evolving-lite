#!/usr/bin/env python3
"""
Usage Tracker - PostToolUse hook.
Adapted from Evolving. Simplified: no buffer, no analyzer trigger, no hash session ID.

Tracks tool usage counts (aggregated in usage.json).
Session counter is managed by health-sentinel.sh (SessionStart) only.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from common import (
    PLUGIN_ROOT, ANALYTICS_DIR, write_sentinel,
    safe_read_json, safe_write_json
)


def _append_history_event(hook_input: dict, tool_name: str) -> None:
    """Append one event row to usage-history.jsonl (the raw event stream
    graph/telemetry consumers read). flock-serialized append; fail-open."""
    try:
        history_file = ANALYTICS_DIR / "usage-history.jsonl"
        session = (hook_input.get("session_id") or hook_input.get("session")
                   or os.environ.get("CLAUDE_SESSION_ID") or f"pid-{os.getppid()}")
        row = {
            "ts": datetime.now().astimezone().isoformat(),
            "tool": tool_name,
            "session": session,
        }
        tool_input = hook_input.get("tool_input")
        if isinstance(tool_input, dict):
            sub = tool_input.get("subagent_type")
            if sub:
                row["subagent_type"] = str(sub)[:60]
        line = json.dumps(row) + "\n"
        try:
            import fcntl
            with open(history_file, "a", encoding="utf-8") as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    f.write(line)
                finally:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
        except ImportError:
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception:
        pass


def main():
    # Read hook input
    try:
        hook_input = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except (json.JSONDecodeError, OSError):
        hook_input = {}

    tool_name = hook_input.get("tool_name", "unknown")

    # Ensure analytics dir exists
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

    # Raw event stream (consumed by graph/telemetry pipelines)
    _append_history_event(hook_input, tool_name)

    # Update aggregated usage counts. The lock wraps the WHOLE read-modify-
    # write so two concurrent PostToolUse fires cannot lose a count.
    usage_file = ANALYTICS_DIR / "usage.json"
    try:
        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        from lib.cache_writer import exclusive_lock
    except ImportError:
        from contextlib import nullcontext
        exclusive_lock = lambda _p: nullcontext()  # noqa: E731

    with exclusive_lock(usage_file):
        usage = safe_read_json(usage_file, {
            "total_calls": 0,
            "tools": {},
            "sessions": 0,
            "first_seen": datetime.now().isoformat(),
            "last_updated": None
        })

        usage["total_calls"] = usage.get("total_calls", 0) + 1
        usage["last_updated"] = datetime.now().isoformat()

        tools = usage.get("tools", {})
        tools[tool_name] = tools.get(tool_name, 0) + 1
        usage["tools"] = tools

        safe_write_json(usage_file, usage)

    write_sentinel("usage-tracker", "ok")
    sys.exit(0)


if __name__ == "__main__":
    main()
