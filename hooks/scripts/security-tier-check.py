#!/usr/bin/env python3
"""
Security Tier Check - PreToolUse hook for Bash commands.
Adapted from Evolving. Simplified for Evolving Lite.

10-tier security system:
  Tier 10-7: BLOCK (catastrophic, reverse shell, code exec, prompt injection)
  Tier 6-5: WARN_CONFIRM (data exfil, credential access)
  Tier 4-3: WARN (destructive, sudo)
  Tier 2-1: LOG (elevated, monitoring)

Exit Codes: 0 = Allow, 1 = Warn/Confirm, 2 = Block
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from common import PLUGIN_ROOT, write_sentinel, safe_read_json


def load_tiers() -> dict:
    tiers_file = PLUGIN_ROOT / "hooks" / "security-tiers.json"
    data = safe_read_json(tiers_file)
    return data.get("tiers", {})


def load_allowlist() -> list:
    """User-merge allowlist: patterns the user trusts override tier classification.

    Ships as _memory/security/allowlist.json (empty patterns array); the user adds
    regexes to permit commands the tiers would otherwise block.
    """
    allowlist_file = PLUGIN_ROOT / "_memory" / "security" / "allowlist.json"
    data = safe_read_json(allowlist_file)
    return data.get("patterns", [])


def log_injection_attempt(command: str, tier: int, name: str) -> None:
    """Record a blocked prompt-injection command to the shared injection ledger.

    Same sink the sanitizer writes to, so all injection events live in one place.
    """
    log_dir = PLUGIN_ROOT / "_memory" / "security"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source": "security-tier-check",
            "tier": tier,
            "name": name,
            "action": "block",
            "command": command[:200],
        }
        with open(log_dir / "injection-attempts.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # logging failure must never break the gate


def is_allowlisted(command: str, allowlist: list) -> bool:
    for pattern in allowlist:
        try:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def check_command(command: str, tiers: dict, allowlist: list) -> dict:
    if is_allowlisted(command, allowlist):
        return {"action": "ALLOW", "tier": 0}

    for tier_num in sorted(tiers.keys(), key=int, reverse=True):
        tier = tiers[tier_num]
        for pattern in tier.get("patterns", []):
            try:
                if re.search(pattern, command, re.IGNORECASE):
                    return {
                        "action": tier.get("action", "LOG"),
                        "tier": int(tier_num),
                        "name": tier.get("name", "UNKNOWN"),
                        "exit_code": tier.get("exit_code", 0)
                    }
            except re.error:
                continue

    return {"action": "ALLOW", "tier": 0}


def main():
    try:
        hook_input = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except (json.JSONDecodeError, OSError):
        hook_input = {}

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        write_sentinel("security-tier-check", "skip")
        sys.exit(0)

    result = check_command(command, load_tiers(), load_allowlist())
    action = result.get("action", "ALLOW")
    tier = result.get("tier", 0)
    name = result.get("name", "")

    if action == "BLOCK":
        if name == "PROMPT_INJECTION":
            log_injection_attempt(command, tier, name)
        print(json.dumps({"error": f"BLOCKED [Tier {tier} {name}]: Command not allowed. {command[:80]}"}))
        write_sentinel("security-tier-check", "block")
        sys.exit(2)
    elif action == "WARN_CONFIRM":
        # Note: exit(2) blocks the command. Claude Code hooks have no "soft confirm" mechanism.
        # Tiers 5-6 (credential access, data exfil) are treated as blocks with explanation.
        print(json.dumps({"error": f"BLOCKED [Tier {tier} {name}]: {command[:80]}. Add pattern to _memory/security/allowlist.json to permit."}))
        write_sentinel("security-tier-check", "block-warn")
        sys.exit(2)
    elif action == "WARN":
        print(json.dumps({"systemMessage": f"CAUTION [Tier {tier} {name}]: {command[:80]}", "continue": True}))
        write_sentinel("security-tier-check", "ok")
        sys.exit(0)
    elif action == "LOG":
        # Tiers 1-2: log for audit trail (package installs, permission changes).
        # Logging must never block the command - hence the defensive guard.
        try:
            from common import log_evolution_event
            log_evolution_event("security_log", f"Tier {tier} {name}: {command[:100]}", source="security-tier-check")
        except Exception:
            pass
        write_sentinel("security-tier-check", "ok")
        sys.exit(0)
    else:
        write_sentinel("security-tier-check", "ok")
        sys.exit(0)


if __name__ == "__main__":
    # Fail-open: a crash in the gate must never block a tool call (exit 0).
    # SystemExit (the intended exit codes 0/2) propagates normally.
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
