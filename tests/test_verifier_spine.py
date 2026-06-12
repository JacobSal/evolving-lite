"""Tests for the Phase-5 verifier-spine (loop closure).

Covers:
  - spine.is_spine_path / first_spine_match (Invariant B registry)
  - stop_gate.check_stop_gate + EPTEvidence (the EPT gate)
  - steward_actuator ACTIVATION with the spine PRESENT (the Phase-5 flip):
    a spine path is REFUSED (INTERACTIVE / never archived), a genuinely-dead
    NON-spine file IS archived.
  - forced-verify-stop-gate hook lease-scoping + subprocess SC-F (markerless
    claim blocked under an autonomy lease; observe-only without one).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.lib.verifier.spine import first_spine_match, is_spine_path  # noqa: E402
from scripts.lib.verifier.stop_gate import EPTEvidence, check_stop_gate  # noqa: E402


def _load_module(path: Path, root: Path, mod_name: str):
    os.environ["CLAUDE_PLUGIN_ROOT"] = str(root)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# spine
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "scripts/lib/verifier/spine.py",
    "scripts/lib/verifier/stop_gate.py",
    "hooks/scripts/forced-verify-stop-gate.py",
    "scripts/autonom/lease.py",
    "scripts/steward_actuator.py",
    "tests/test_verifier_spine.py",
    "/abs/prefix/scripts/lib/verifier/__init__.py",
])
def test_spine_paths_detected(path):
    assert is_spine_path(path) is True
    assert first_spine_match(path) is not None


@pytest.mark.parametrize("path", [
    "hooks/scripts/delegation-enforcer.py",
    "scripts/recalc-fitness.py",
    "scripts/graph/auto-edges.py",
    "_graph/cache/delegation-config.json",
    "README.md",
])
def test_non_spine_paths_pass(path):
    assert is_spine_path(path) is False
    assert first_spine_match(path) is None


def test_spine_empty_input_is_false():
    assert is_spine_path("") is False
    assert is_spine_path(None) is False  # type: ignore[arg-type]


def test_spine_caller_supplied_patterns():
    # Default set does not protect this; a caller-supplied list does.
    assert is_spine_path("config/secret.py") is False
    assert is_spine_path("config/secret.py", patterns=[r"config/secret"]) is True


# ---------------------------------------------------------------------------
# stop_gate
# ---------------------------------------------------------------------------

def test_stop_gate_no_trigger_word_passes():
    res = check_stop_gate("I am still editing the port modules.")
    assert res.passed is True
    assert res.claim_triggered is False


def test_stop_gate_trigger_without_evidence_blocks():
    res = check_stop_gate("The verifier spine is done and shipped.")
    assert res.passed is False
    assert set(res.missing_legs) == {"trigger", "effect", "consumer"}
    assert "DEFERRED-AND-UNTESTED" in res.block_reason


def test_stop_gate_trigger_with_full_markers_passes():
    ev = EPTEvidence(
        trigger="pytest run at 12:00Z returned exit 0 over 17 tests",
        effect="test_verifier_spine.py::test_spine_paths_detected PASSED",
        consumer="steward_actuator imports is_spine_path; Invariant B active",
    )
    res = check_stop_gate("The verifier spine is done.", evidence=ev)
    assert res.passed is True


def test_stop_gate_partial_markers_block():
    ev = EPTEvidence(trigger="pytest exit 0 at 12:00Z", effect="", consumer="")
    res = check_stop_gate("shipped and verified", evidence=ev)
    assert res.passed is False
    assert "trigger" not in res.missing_legs
    assert set(res.missing_legs) == {"effect", "consumer"}


def test_stop_gate_custom_trigger_words():
    # English default does not flag "fertig"; a custom set does.
    assert check_stop_gate("das ist fertig").passed is True
    res = check_stop_gate("das ist fertig", trigger_words=["fertig"])
    assert res.passed is False


# ---------------------------------------------------------------------------
# steward_actuator ACTIVATION with the spine PRESENT (the Phase-5 flip)
# ---------------------------------------------------------------------------

def _load_actuator_spine_present(tmp_path, mod_name):
    """Load the actuator and force the spine-PRESENT state (the post-Phase-5
    world), wiring in the REAL is_spine_path. _load_module sets
    CLAUDE_PLUGIN_ROOT=tmp_path so REPO_ROOT binds to the tmp repo, but the spine
    import resolves against the empty tmp dir -> we set the globals explicitly so
    the test does not depend on ambient import resolution."""
    act = _load_module(REPO / "scripts" / "steward_actuator.py", tmp_path, mod_name)
    act._SPINE_AVAILABLE = True
    act._is_spine_path = is_spine_path
    return act


def test_actuator_spine_present_refuses_spine_path(tmp_path):
    act = _load_actuator_spine_present(tmp_path, "act_spine_refuse")
    # classify_action: a finding whose source is a spine file -> INTERACTIVE.
    cls = act.classify_action({
        "module": "retirement",
        "detail": act.HIGH_CONFIDENCE_MARKER,
        "source": "scripts/steward_actuator.py",
    })
    assert cls == act.AutonomyClass.INTERACTIVE
    # is_safe_to_autonomously_archive refuses a spine path with a spine reason.
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "scripts" / "steward_actuator.py").write_text("# self")
    safe, reason = act.is_safe_to_autonomously_archive(
        {"source": "scripts/steward_actuator.py"}, repo_root=tmp_path
    )
    assert safe is False
    assert "spine" in reason.lower()


def test_actuator_spine_present_archives_genuinely_dead(tmp_path):
    act = _load_actuator_spine_present(tmp_path, "act_spine_archive")
    sd = tmp_path / "hooks" / "scripts"
    sd.mkdir(parents=True)
    (sd / "ghost.py").write_text("# nobody references me")
    findings = tmp_path / "_inbox" / "steward-findings.jsonl"
    findings.parent.mkdir(parents=True)
    findings.write_text(json.dumps({
        "module": "retirement", "severity": "P2",
        "title": "Retirement candidate: ghost.py",
        "detail": act.HIGH_CONFIDENCE_MARKER,
        "source": "hooks/scripts/ghost.py",
        "item_id": "ghost.py", "maintainer_decision": "silent",
    }) + "\n")
    summary = act.run_actuator(findings_path=findings, dry_run=False)
    assert summary["autonomous_archived"] == 1  # spine present + genuinely dead -> archived
    assert not (sd / "ghost.py").exists()       # moved
    archived = list((tmp_path / "_archive" / "retired").glob("ghost.py-*"))
    assert len(archived) == 1


# ---------------------------------------------------------------------------
# forced-verify-stop-gate hook
# ---------------------------------------------------------------------------

HOOK = REPO / "hooks" / "scripts" / "forced-verify-stop-gate.py"


def _load_hook(tmp_path):
    return _load_module(HOOK, tmp_path, "fv_hook")


def test_hook_lease_scoping_owned_vs_foreign(tmp_path):
    hook = _load_hook(tmp_path)
    lease = tmp_path / "_graph" / "cache" / "autonom-lease.json"
    lease.parent.mkdir(parents=True)
    import time as _t
    lease.write_text(json.dumps({"session_id": "sess-A", "claimed_at": _t.time(), "released": False}))
    hook._LEASE_PATH = lease
    # Owned by this session -> autonomous.
    assert hook._is_autonomous_session({"session_id": "sess-A"}) is True
    # Foreign owner -> NOT autonomous (observe-only).
    assert hook._is_autonomous_session({"session_id": "sess-B"}) is False
    # Released lease -> NOT autonomous.
    lease.write_text(json.dumps({"session_id": "sess-A", "claimed_at": _t.time(), "released": True}))
    assert hook._is_autonomous_session({"session_id": "sess-A"}) is False
    # Missing lease -> NOT autonomous.
    lease.unlink()
    assert hook._is_autonomous_session({"session_id": "sess-A"}) is False


def _run_hook_subprocess(tmp_path, payload, mode=None):
    """Run the hook as a real subprocess with paths rooted at tmp_path but the
    verifier lib resolved from the real repo (PYTHONPATH). Returns (rc, stdout)."""
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    if mode is not None:
        env["STOP_GATE_MODE"] = mode
    else:
        env.pop("STOP_GATE_MODE", None)
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
    )
    return proc.returncode, proc.stdout


def test_hook_subprocess_autonomy_off_never_blocks(tmp_path):
    # No lease -> interactive -> observe-only -> markerless claim allowed.
    rc, out = _run_hook_subprocess(
        tmp_path, {"session_id": "s1", "stop_reason": "the port is done and shipped"}
    )
    assert rc == 0
    # An observation row was logged (observe-only).
    ledger = tmp_path / "_ledgers" / "stop-gate-observations.jsonl"
    assert ledger.exists()


def test_hook_subprocess_autonomy_on_blocks_markerless(tmp_path):
    # Plant a lease owned by THIS session -> autonomous -> markerless claim blocks.
    lease = tmp_path / "_graph" / "cache" / "autonom-lease.json"
    lease.parent.mkdir(parents=True)
    import time as _t
    lease.write_text(json.dumps({"session_id": "s-own", "claimed_at": _t.time(), "released": False}))
    rc, out = _run_hook_subprocess(
        tmp_path, {"session_id": "s-own", "stop_reason": "the port is done and shipped"}
    )
    assert rc == 1
    assert json.loads(out).get("decision") == "block"


def test_hook_subprocess_autonomy_on_passes_with_markers(tmp_path):
    lease = tmp_path / "_graph" / "cache" / "autonom-lease.json"
    lease.parent.mkdir(parents=True)
    import time as _t
    lease.write_text(json.dumps({"session_id": "s-own", "claimed_at": _t.time(), "released": False}))
    claim = (
        "The port is done. "
        "[EPT-TRIGGER: pytest run at 12:00Z exit 0] "
        "[EPT-EFFECT: test_verifier_spine.py all PASSED] "
        "[EPT-CONSUMER: steward_actuator imports is_spine_path; loop closed]"
    )
    rc, out = _run_hook_subprocess(tmp_path, {"session_id": "s-own", "stop_reason": claim})
    assert rc == 0
