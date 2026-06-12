#!/usr/bin/env python3
"""forced-verify-stop-gate.py - LIVE Stop hook for the EPT Stop-gate.

SCOPE (the key behavioural contract):
  - AUTONOMOUS session (an autonomy lease is held for THIS session): the gate is
    ACTIVE. A completion claim ("done/works/shipped/...") that lacks the 3-leg
    EPT evidence markers BLOCKS the Stop. This is where self-preferential bias
    bites - no human is watching the claim.
  - INTERACTIVE session (the default - no autonomy lease for this session): the
    gate is OBSERVE-ONLY. It logs an evidence-less completion claim to a ledger
    but NEVER blocks. Autonomy is OFF by default, so a fresh install never nags.

Kill-switch: set STOP_GATE_MODE=off to disable entirely (exit 0, no logging).
Force modes (testing/override): STOP_GATE_MODE=enforce | observe.

Fail-open everywhere: any import error, parse error, or unexpected exception
results in exit 0 (allow). A verification gate must never brick a session.

SAFETY SPINE INVARIANT: this hook + the verifier lib it calls live OUTSIDE the
autonomous session's self-modification scope (enforced in code via
scripts/lib/verifier/spine.py consumed by steward_actuator.classify_action).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# CODE root = the plugin root. Prefer CLAUDE_PLUGIN_ROOT (set by CC for plugin
# hooks); fall back to __file__-relative (hooks/scripts/ -> hooks/ -> root) so a
# standalone invocation also resolves. The verifier package uses absolute
# `scripts.lib.verifier.*` imports, so the plugin root (not scripts/) is on path.
_CODE_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(_CODE_ROOT))

_LEASE_PATH = _CODE_ROOT / "_graph" / "cache" / "autonom-lease.json"
_LEASE_TTL_S = 4 * 3600  # mirrors scripts/autonom/lease.py LEASE_TTL_SECONDS
_OBSERVE_LEDGER = _CODE_ROOT / "_ledgers" / "stop-gate-observations.jsonl"


def _allow() -> None:
    """Allow the Stop (empty stdout + exit 0)."""
    sys.exit(0)


def _candidate_session_ids(hook_input: dict) -> set[str]:
    """All identifiers that could legitimately own this session's lease.

    CC does not reliably export CLAUDE_SESSION_ID into a Stop hook subprocess, so
    the canonical id is in the hook payload (`session_id`); prefer it, also accept
    the env var and a pid fallback. Matching the lease holder against this SET
    keeps autonomous detection robust to whichever source is populated.
    """
    ids: set[str] = set()
    hid = hook_input.get("session_id")
    if hid:
        ids.add(str(hid))
    env = os.environ.get("CLAUDE_SESSION_ID")
    if env:
        ids.add(str(env))
    ids.add(f"pid-{os.getpid()}")
    return ids


def _is_autonomous_session(hook_input: dict) -> bool:
    """True iff an active, non-expired lease is owned by one of THIS session's
    candidate ids.

    Fail-closed to INTERACTIVE (returns False) on any uncertainty: a missing,
    unreadable, expired, or foreign-owned lease means this is NOT the autonomous
    session, so the gate stays observe-only - the safe default.
    """
    try:
        if not _LEASE_PATH.exists():
            return False
        if (time.time() - _LEASE_PATH.stat().st_mtime) > _LEASE_TTL_S:
            return False
        data = json.loads(_LEASE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False
        if data.get("released") is True:
            return False
        holder = str(data.get("session_id", ""))
        return bool(holder) and holder in _candidate_session_ids(hook_input)
    except Exception:
        return False


def _read_hook_input() -> dict:
    raw = os.environ.get("CLAUDE_HOOK_INPUT", "")
    if not raw:
        try:
            raw = sys.stdin.read()
        except Exception:
            raw = ""
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {"stop_reason": raw[:500]}


def _extract_last_text(hook_input: dict) -> str:
    last_text = ""
    msg = hook_input.get("message", {})
    if isinstance(msg, dict):
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in reversed(content):
                if isinstance(block, dict) and block.get("type") == "text":
                    last_text = block.get("text", "")
                    break
        elif isinstance(content, str):
            last_text = content
    if not last_text:
        last_text = hook_input.get("stop_reason", "")
    return last_text or ""


def _extract_markers(last_text: str):
    """Parse [EPT-TRIGGER:] [EPT-EFFECT:] [EPT-CONSUMER:] markers from text."""
    import re as _re
    from scripts.lib.verifier.stop_gate import EPTEvidence

    def _extract(marker: str) -> str:
        # Evidence legitimately contains ']' (pytest ids like test_foo[case1],
        # arr[0]). Run the content lazily up to the closing ']' that is followed
        # by the NEXT [EPT- marker or end-of-text - tolerates internal brackets
        # while still delimiting consecutive markers.
        pat = r"\[EPT-" + marker + r":\s*(.*?)\s*\](?=\s*(?:\[EPT-|$))"
        m = _re.search(pat, last_text, _re.IGNORECASE | _re.DOTALL)
        if m:
            return m.group(1).strip()
        # Fallback (additive; the strict path above is unchanged): the strict
        # anchor misses when prose follows the FINAL marker (e.g. a session
        # appends a summary sentence after [EPT-CONSUMER: ...]). Take content up
        # to the first ']'. Only fires on a strict miss, so it never weakens the
        # inner-']' tolerance for consecutive markers.
        m2 = _re.search(r"\[EPT-" + marker + r":\s*(.*?)\s*\]", last_text,
                        _re.IGNORECASE | _re.DOTALL)
        return m2.group(1).strip() if m2 else ""

    return EPTEvidence(
        trigger=_extract("TRIGGER"),
        effect=_extract("EFFECT"),
        consumer=_extract("CONSUMER"),
    )


def _log_observation(session_id: str, claim: str, missing: list[str]) -> None:
    """Append an interactive-mode observation. Fail-open (never raises)."""
    try:
        _OBSERVE_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "mode": "observe",
            "missing_legs": missing,
            "claim_excerpt": claim[:200],
        }
        with open(_OBSERVE_LEDGER, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main() -> None:
    mode_env = os.environ.get("STOP_GATE_MODE", "").strip().lower()
    if mode_env == "off":
        _allow()

    try:
        from scripts.lib.verifier.stop_gate import check_stop_gate
    except Exception as exc:  # fail-open: lib missing/broken -> never block
        sys.stderr.write(f"[stop-gate] WARN: verifier lib import failed ({exc}); gate skipped.\n")
        _allow()

    try:
        hook_input = _read_hook_input()
        last_text = _extract_last_text(hook_input)
        evidence = _extract_markers(last_text)
        result = check_stop_gate(last_text, evidence=evidence)
    except Exception as exc:  # fail-open on any parse/check error
        sys.stderr.write(f"[stop-gate] WARN: gate check errored ({exc}); allowing.\n")
        _allow()
        return

    session_id = (
        str(hook_input.get("session_id", ""))
        or os.environ.get("CLAUDE_SESSION_ID", "")
        or f"pid-{os.getpid()}"
    )

    # Resolve mode: explicit override wins, else lease-based auto-scoping.
    if mode_env == "enforce":
        autonomous = True
    elif mode_env == "observe":
        autonomous = False
    else:
        autonomous = _is_autonomous_session(hook_input)

    if result.passed:
        _allow()
        return

    if autonomous:
        sys.stderr.write(result.block_reason + "\n")
        print(json.dumps({"decision": "block"}))
        sys.exit(1)
    else:
        _log_observation(session_id, last_text, result.missing_legs)
        _allow()


if __name__ == "__main__":
    main()
