"""Tests for scripts/autoevolve-scorer.py.

Covers: the two deterministic scorers (lite schema), the baseline ratchet, the
mutation-eligibility gate (off-switch + per-target + MVP-N), and the
deterministic baseline-persist gate (keep / revert / skip / error).

Module loaded via importlib because the file name is hyphenated.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "autoevolve-scorer.py"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load():
    spec = importlib.util.spec_from_file_location("autoevolve_scorer", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ae = _load()


# ---------------------------------------------------------------------------
# Fixtures: a minimal lite tree under tmp_path
# ---------------------------------------------------------------------------

DETECTION = {
    "entries": {
        "remember": {"keywords": ["remember", "merke dir"], "command": "/remember", "confidence_boost": 10},
        "debug": {"keywords": ["debug", "fehler suchen"], "command": "/debug", "confidence_boost": 15},
        "review": {"keywords": ["code review", "review"], "command": "/review", "confidence_boost": 10},
    }
}
DETECTION_CASES = {
    "test_cases": [
        {"input": "remember this please", "expected_command": "/remember", "expected_confidence": "high"},
        {"input": "debug this error", "expected_command": "/debug", "expected_confidence": "high"},
        {"input": "code review this", "expected_command": "/review", "expected_confidence": "high"},
        {"input": "the weather is nice", "expected_command": "no_match", "expected_confidence": "none"},
    ]
}

ROUTER = {
    "routes": {
        "debugging": {"keywords": ["debug", "crash", "exception"]},
        "memory": {"keywords": ["remember", "recall", "memory"]},
        "git": {"keywords": ["commit", "branch", "merge"]},
    }
}
ROUTER_CASES = {
    "test_cases": [
        {"input": "debug this crash exception", "expected_route": "debugging"},
        {"input": "recall this from memory", "expected_route": "memory"},
        {"input": "commit and merge the branch", "expected_route": "git"},
        {"input": "the weather is nice", "expected_route": "no_match"},
    ]
}


def _write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


@pytest.fixture
def lite_root(tmp_path):
    """A throwaway lite tree with detection/router caches + test-cases + configs."""
    _write(tmp_path / "_graph" / "cache" / "detection-index.json", DETECTION)
    _write(tmp_path / "_graph" / "cache" / "context-router.json", ROUTER)
    _write(tmp_path / "_autoevolve" / "test-cases" / "detection-index.json", DETECTION_CASES)
    _write(tmp_path / "_autoevolve" / "test-cases" / "context-router.json", ROUTER_CASES)
    _write(tmp_path / "_graph" / "cache" / "delegation-config.json",
           {"mutation_rules": {"v2_tuning_enabled": True}})
    _write(tmp_path / "_autoevolve" / "config.json", {
        "targets": {
            "detection-index": {
                "enabled": True, "mvp_sample_threshold": 8,
                "target_file": "_graph/cache/detection-index.json",
                "test_cases": "_autoevolve/test-cases/detection-index.json",
                "outcomes_ledger": "_autoevolve/outcomes/detection-index.jsonl",
            },
            "context-router": {
                "enabled": True, "mvp_sample_threshold": 8,
                "target_file": "_graph/cache/context-router.json",
                "test_cases": "_autoevolve/test-cases/context-router.json",
                "outcomes_ledger": "_autoevolve/outcomes/context-router.jsonl",
            },
            "delegation-config": {"enabled": False, "scorer": "none"},
        }
    })
    return tmp_path


# ---------------------------------------------------------------------------
# Scorers
# ---------------------------------------------------------------------------

def test_detection_scorer_composite_perfect_on_seed(lite_root):
    res = ae.score_detection_index(
        lite_root / "_graph/cache/detection-index.json",
        lite_root / "_autoevolve/test-cases/detection-index.json")
    assert "error" not in res
    assert 0.0 <= res["metrics"]["composite"] <= 1.0
    assert res["summary"]["correct"] == res["summary"]["total_cases"]


def test_detection_scorer_drops_when_keyword_removed(lite_root):
    """Removing a route's keyword must measurably lower the composite -
    this sensitivity is what the persist-gate relies on."""
    p = lite_root / "_graph/cache/detection-index.json"
    before = ae.score_detection_index(p, lite_root / "_autoevolve/test-cases/detection-index.json")["metrics"]["composite"]
    degraded = json.loads(p.read_text())
    degraded["entries"]["debug"]["keywords"] = ["zzz_no_match"]
    p.write_text(json.dumps(degraded))
    after = ae.score_detection_index(p, lite_root / "_autoevolve/test-cases/detection-index.json")["metrics"]["composite"]
    assert after < before


def test_detection_scorer_handles_malformed_entries(tmp_path):
    # entries present but not a dict -> error dict, never raises
    idx = tmp_path / "i.json"
    tc = tmp_path / "tc.json"
    idx.write_text(json.dumps({"entries": ["bad", "shape"]}))
    tc.write_text(json.dumps(DETECTION_CASES))
    out = ae.score_detection_index(idx, tc)
    assert "error" in out


def test_router_scorer_composite_bounds(lite_root):
    res = ae.score_context_router(
        lite_root / "_graph/cache/context-router.json",
        lite_root / "_autoevolve/test-cases/context-router.json")
    assert "error" not in res
    assert 0.0 <= res["metrics"]["composite"] <= 1.0
    assert res["summary"]["correct"] == res["summary"]["total_cases"]


def test_router_scorer_drops_when_route_keywords_removed(lite_root):
    p = lite_root / "_graph/cache/context-router.json"
    tc = lite_root / "_autoevolve/test-cases/context-router.json"
    before = ae.score_context_router(p, tc)["metrics"]["composite"]
    degraded = json.loads(p.read_text())
    degraded["routes"]["debugging"]["keywords"] = []
    p.write_text(json.dumps(degraded))
    after = ae.score_context_router(p, tc)["metrics"]["composite"]
    assert after < before


# ---------------------------------------------------------------------------
# Baseline ratchet
# ---------------------------------------------------------------------------

def test_update_baseline_ratchets_up_only(lite_root):
    res_hi = {"metrics": {"composite": 0.80}, "timestamp": "t1"}
    res_lo = {"metrics": {"composite": 0.50}, "timestamp": "t2"}
    ae.update_baseline(lite_root, "detection-index", res_hi)
    assert ae.get_baseline(lite_root, "detection-index")["composite"] == 0.80
    out = ae.update_baseline(lite_root, "detection-index", res_lo)
    assert out["improved"] is False
    # baseline stayed at the high-water mark; history recorded the regression
    assert ae.get_baseline(lite_root, "detection-index")["composite"] == 0.80
    baselines = json.loads((lite_root / "_autoevolve" / "baselines.json").read_text())
    assert len(baselines["history"]) == 2


# ---------------------------------------------------------------------------
# evaluate_persist (pure decision)
# ---------------------------------------------------------------------------

def test_evaluate_persist_keeps_equal_or_better():
    assert ae.evaluate_persist(0.70, 0.70)["action"] == "keep"
    assert ae.evaluate_persist(0.70, 0.85)["action"] == "keep"


def test_evaluate_persist_reverts_regression():
    d = ae.evaluate_persist(0.7569, 0.7101)
    assert d["action"] == "revert"
    assert d["regression"] is True


def test_evaluate_persist_eps_boundary():
    # a sub-eps drop is noise, not a regression
    assert ae.evaluate_persist(0.7000, 0.69999999)["action"] == "keep"


# ---------------------------------------------------------------------------
# count_outcomes + mutation gate
# ---------------------------------------------------------------------------

def test_count_outcomes_zero_when_absent(lite_root):
    assert ae.count_outcomes(lite_root, "context-router",
                             {"outcomes_ledger": "_autoevolve/outcomes/context-router.jsonl"}) == 0


def test_count_outcomes_counts_nonblank_lines(lite_root):
    led = lite_root / "_autoevolve" / "outcomes" / "context-router.jsonl"
    led.parent.mkdir(parents=True, exist_ok=True)
    led.write_text('{"a":1}\n\n{"b":2}\n   \n{"c":3}\n')
    assert ae.count_outcomes(lite_root, "context-router",
                             {"outcomes_ledger": "_autoevolve/outcomes/context-router.jsonl"}) == 3


def test_gate_blocked_when_global_off(lite_root):
    cfg = lite_root / "_graph" / "cache" / "delegation-config.json"
    cfg.write_text(json.dumps({"mutation_rules": {"v2_tuning_enabled": False}}))
    g = ae.evaluate_mutation_gate(lite_root, "context-router")
    assert g["eligible"] is False
    assert "global-off" in g["reason"]


def test_gate_blocked_when_target_disabled(lite_root):
    g = ae.evaluate_mutation_gate(lite_root, "delegation-config")
    assert g["eligible"] is False
    assert "target-disabled" in g["reason"]


def test_gate_blocked_when_insufficient_samples(lite_root):
    g = ae.evaluate_mutation_gate(lite_root, "context-router")
    assert g["eligible"] is False
    assert g["outcomes"] == 0 and g["threshold"] == 8
    assert "insufficient-samples" in g["reason"]


def test_gate_eligible_when_all_pass(lite_root):
    led = lite_root / "_autoevolve" / "outcomes" / "context-router.jsonl"
    led.parent.mkdir(parents=True, exist_ok=True)
    led.write_text("\n".join('{"o":%d}' % i for i in range(8)) + "\n")
    g = ae.evaluate_mutation_gate(lite_root, "context-router")
    assert g["eligible"] is True
    assert g["outcomes"] == 8


def test_gate_unknown_target(lite_root):
    g = ae.evaluate_mutation_gate(lite_root, "no-such-target")
    assert g["eligible"] is False
    assert g["reason"] == "unknown-target"


# ---------------------------------------------------------------------------
# enforce_persist_gate (IO; injected score_fn so no real config needed)
# ---------------------------------------------------------------------------

def test_persist_gate_keeps_improvement(tmp_path):
    live = tmp_path / "live.json"
    snap = tmp_path / "snap.json"
    live.write_text('{"v": "mutated"}')
    snap.write_text('{"v": "original"}')
    scores = {str(snap): 0.70, str(live): 0.85}
    res = ae.enforce_persist_gate(
        tmp_path, "context-router", live, snap,
        score_fn=lambda t, p: scores[str(p)])
    assert res["action"] == "keep"
    assert res["reverted_to_snapshot"] is False
    assert json.loads(live.read_text())["v"] == "mutated"  # not restored


def test_persist_gate_reverts_regression_atomically(tmp_path):
    live = tmp_path / "live.json"
    snap = tmp_path / "snap.json"
    live.write_text('{"v": "mutated-bad"}')
    snap.write_text('{"v": "original-good"}')
    scores = {str(snap): 0.7569, str(live): 0.7101}
    res = ae.enforce_persist_gate(
        tmp_path, "context-router", live, snap,
        run_id="t", mutation_description="planted regression",
        score_fn=lambda t, p: scores[str(p)])
    assert res["action"] == "revert"
    assert res["reverted_to_snapshot"] is True
    # live restored to the snapshot content
    assert json.loads(live.read_text())["v"] == "original-good"
    # a rejected-mutation record was written
    assert res["rejected_log"] is not None
    assert Path(res["rejected_log"]).exists()


def test_persist_gate_skips_non_deterministic_target(tmp_path):
    snap = tmp_path / "snap.json"
    snap.write_text("{}")
    res = ae.enforce_persist_gate(tmp_path, "delegation-config",
                                  tmp_path / "live.json", snap)
    assert res["action"] == "skip"


def test_persist_gate_errors_on_missing_snapshot(tmp_path):
    res = ae.enforce_persist_gate(
        tmp_path, "context-router",
        tmp_path / "live.json", tmp_path / "does-not-exist.json")
    assert res["action"] == "error"
    assert "snapshot not found" in res["reason"]


# ---------------------------------------------------------------------------
# record_rejected_mutation
# ---------------------------------------------------------------------------

def test_record_rejected_mutation_writes_file(tmp_path):
    out = ae.record_rejected_mutation(
        tmp_path, "context-router", "run-1", "desc", 0.75, 0.71, "regression")
    assert out is not None and Path(out).exists()
    rec = json.loads(Path(out).read_text())
    assert rec["target"] == "context-router"
    assert rec["delta"] == -0.04
