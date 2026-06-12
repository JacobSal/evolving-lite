"""Self-Star Doctor tests: heal whitelist (R5), board classification, pulses."""
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("doctor_mod", REPO / "scripts" / "doctor.py")
doc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doc)


# --- R5: heal is create-only, consent-gated, never destructive ---------------

def test_heal_creates_missing_scaffold(tmp_path):
    actions = doc.heal(tmp_path)
    assert (tmp_path / "_graph" / "cache").is_dir()
    assert (tmp_path / "_memory" / "security").is_dir()
    assert any(a[0] == "created_dir" for a in actions)


def test_heal_planted_missing_cache_is_healed(tmp_path):
    # Planted: the dir does not exist -> heal must create it (R5 binary leg A).
    target = tmp_path / "_graph" / "cache"
    assert not target.exists()
    doc.heal(tmp_path)
    assert target.is_dir()


def test_heal_settings_change_requires_consent_not_silent_write(tmp_path):
    # R5 binary leg B: a settings.json lacking the plugin must trigger a CONSENT
    # prompt, never a silent write.
    settings = tmp_path / "settings.json"
    original = {"pluginDirectories": ["/some/other/plugin"]}
    settings.write_text(json.dumps(original))
    actions = doc.heal(tmp_path, settings_path=settings, consent=lambda a: False)
    assert any(a[0] == "needs_consent:register_plugin" for a in actions)
    # File MUST be byte-unchanged (no silent write).
    assert json.loads(settings.read_text()) == original


def test_heal_settings_change_writes_only_with_consent(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"pluginDirectories": []}))
    actions = doc.heal(tmp_path, settings_path=settings, consent=lambda a: True)
    assert any(a[0] == "registered_plugin" for a in actions)
    assert str(tmp_path) in json.loads(settings.read_text())["pluginDirectories"]


def test_heal_never_overwrites_nonempty_file(tmp_path):
    # A non-empty .gitkeep-target must not be clobbered.
    (tmp_path / "_memory" / "sessions").mkdir(parents=True)
    gk = tmp_path / "_memory" / "sessions" / ".gitkeep"
    gk.write_text("PRECIOUS")
    doc.heal(tmp_path)
    assert gk.read_text() == "PRECIOUS"


def test_heal_never_deletes(tmp_path):
    marker = tmp_path / "_graph" / "cache"
    marker.mkdir(parents=True)
    sentinel = marker / "keep.json"
    sentinel.write_text("{}")
    doc.heal(tmp_path)
    assert sentinel.exists()


def test_heal_recognizes_already_registered_plugin(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"pluginDirectories": [str(tmp_path)]}))
    actions = doc.heal(tmp_path, settings_path=settings, consent=lambda a: False)
    assert not any("register_plugin" in a[0] for a in actions)


def test_plugin_registered_no_substring_false_positive(tmp_path):
    # RC#1: a sibling plugin whose path merely contains the basename must NOT
    # count as registered (else the real plugin is never registered).
    settings = tmp_path / "settings.json"
    sibling = str(tmp_path) + "-fork"
    settings.write_text(json.dumps({"pluginDirectories": [sibling]}))
    assert doc._plugin_registered(settings, tmp_path) is False
    actions = doc.heal(tmp_path, settings_path=settings, consent=lambda a: False)
    assert any(a[0] == "needs_consent:register_plugin" for a in actions)


# --- Board classification ----------------------------------------------------

def test_smoke_junction_all_pass_green():
    st, _ = doc._smoke_junction_status(("S4",), {"S4": [True, True, True]})
    assert st == doc.GREEN


def test_smoke_junction_any_fail_red():
    st, _ = doc._smoke_junction_status(("S4",), {"S4": [True, False]})
    assert st == doc.RED


def test_smoke_junction_absent_red():
    st, _ = doc._smoke_junction_status(("S4",), {})
    assert st == doc.RED


def test_parse_smoke_extracts_results():
    out = "PASS: S4 enforcer ok\nFAIL: S5 recalc\nPASS: S5 row\nirrelevant line"
    r = doc._parse_smoke(out)
    assert r["S4"] == [True]
    assert r["S5"] == [False, True]


def test_parse_smoke_multidigit_not_misbucketed():
    # RC#2: S10 must NOT collapse into S1's bucket; S1abc must be ignored.
    r = doc._parse_smoke("PASS: S1 a\nPASS: S10 b\nFAIL: S1abc c")
    assert r["S1"] == [True]
    assert r["S10"] == [True]
    assert "S1abc" not in r


def test_session_start_emits_valid_json_contract(tmp_path, monkeypatch, capsys):
    # RC#2: the SessionStart hook output must be a valid JSON line carrying the
    # CC hook keys. Run against a scratch root so no real marker/ledger is touched.
    monkeypatch.setattr(doc, "_plugin_root", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["doctor.py", "--session-start"])
    rc = doc.main()
    assert rc == 0
    line = capsys.readouterr().out.strip()
    payload = json.loads(line)
    assert "systemMessage" in payload and payload["continue"] is True
    assert (tmp_path / doc._MARKER).exists()  # marker written -> guards next run


def test_overall_all_green():
    board = {j: {"status": doc.GREEN, "detail": ""} for j in doc.JUNCTIONS}
    assert doc.overall(board) == doc.GREEN


def test_overall_red_dominates():
    board = {j: {"status": doc.GREEN, "detail": ""} for j in doc.JUNCTIONS}
    board["security"]["status"] = doc.RED
    assert doc.overall(board) == doc.RED


# --- Pulses ------------------------------------------------------------------

def test_security_pulse_ok_on_real_repo():
    res = doc.security_pulse(REPO)
    assert res["ok"] is True
    assert res["secret_flagged"] and res["injection_flagged"] and res["tier_ok"]


def test_kairn_pulse_red_when_cli_absent():
    res = doc.kairn_pulse({"kairn_cli": False})
    assert res["status"] == doc.RED


def test_kairn_pulse_green_when_mcp_registered():
    res = doc.kairn_pulse({"kairn_cli": True, "kairn_mcp_registered": True, "kairn_doctor_ok": False})
    assert res["status"] == doc.GREEN


def test_kairn_pulse_yellow_when_unconfirmed():
    res = doc.kairn_pulse({"kairn_cli": True, "kairn_mcp_registered": False, "kairn_doctor_ok": False})
    assert res["status"] == doc.YELLOW


def test_wiring_verify_ok_on_real_repo():
    res = doc.wiring_verify(REPO)
    assert res["ok"] is True, f"missing={res['missing_files']} hooks_ok={res['hooks_ok']}"


def test_no_pulse_board_is_yellow_not_red():
    pf = {"python": "3.12", "python_ok": True, "kairn_cli": True, "kairn_mcp_registered": True, "kairn_doctor_ok": True}
    wiring = doc.wiring_verify(REPO)
    board = doc.build_board(REPO, pf, wiring, None, None, doc.kairn_pulse(pf))
    # Loop junctions are present+wired but pulse skipped -> YELLOW, never RED.
    assert board["delegation"]["status"] == doc.YELLOW
