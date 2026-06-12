#!/usr/bin/env python3
"""
AutoEvolve Scorer - Deterministic evaluation of optimization targets.

Scores a config artifact against fixed test cases with ZERO LLM cost, so the
mutate-score-revert loop (the autoevolve-optimizer agent) has an objective,
reproducible signal. Two safety layers ship as CODE here, not agent discipline:

  1. mutation-eligibility gate (evaluate_mutation_gate): a target may be mutated
     only when (a) the global off-switch is ON, (b) the per-target switch is ON,
     and (c) at least MVP-many real outcomes have accumulated. On a fresh
     cold-data install no target is eligible until usage data arrives, so the
     loop is provably quiet out of the box.
  2. deterministic baseline-persist gate (enforce_persist_gate): after a
     mutation is scored, a below-baseline result is reverted by code (atomic
     snapshot restore + rejected-mutation log), independent of whether the
     optimizer agent remembers to revert.

Supported targets (deterministic scorers):
  detection-index  : keyword-match precision/recall against test cases
  context-router   : route keyword accuracy against test cases

Usage:
  python3 scripts/autoevolve-scorer.py score detection-index
  python3 scripts/autoevolve-scorer.py baseline context-router
  python3 scripts/autoevolve-scorer.py plateau detection-index [window]
  python3 scripts/autoevolve-scorer.py compare context-router
  python3 scripts/autoevolve-scorer.py mutation-gate context-router
  python3 scripts/autoevolve-scorer.py persist-gate context-router --snapshot PATH

Dependencies: stdlib only. Data lives in the plugin root (resolved via
scripts/lib/plugin_paths.plugin_root).
"""

import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from scripts.lib.plugin_paths import plugin_root  # noqa: E402


def load_json(path):
    """Load JSON file, return None on failure."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: Cannot load {path}: {e}", file=sys.stderr)
        return None


def save_json(path, data):
    """Save JSON file with pretty printing."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Detection-Index Scorer (lite {entries} schema)
# ---------------------------------------------------------------------------

def score_detection_index(target_path, test_cases_path):
    """
    Score detection-index.json against test cases.

    Lite schema: {"entries": {name: {"keywords": [...], "command": "/name",
    "confidence_boost": int}}}. (No base-confidence or patterns field - those
    are upstream-only; the scorer reads only what lite ships.)

    Matching mirrors how the keyword detector ranks commands:
      score = keyword_hits * 10 + (confidence_boost if any keyword hit)
      top-scoring entry = predicted command; compared to expected.

    Returns dict with precision, recall, f1, confidence_accuracy, composite.
    """
    index = load_json(target_path)
    cases = load_json(test_cases_path)
    if not index or not cases:
        return {"error": "Failed to load files"}

    entries = index.get("entries", {})
    if not isinstance(entries, dict):
        return {"error": "detection-index has no 'entries' object"}
    test_items = cases.get("test_cases", [])
    if not test_items:
        return {"error": "No test cases found"}

    results = []
    correct = 0
    total = len(test_items)
    expected_commands = {}
    found_commands = {}

    for case in test_items:
        input_text = case["input"].lower()
        expected = case["expected_command"]
        expected_confidence = case.get("expected_confidence", "high")

        if expected != "no_match":
            expected_commands[expected] = expected_commands.get(expected, 0) + 1

        input_words = set(re.findall(r"\w+", input_text))
        best_command = None
        best_score = 0

        for name, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            keywords = [str(k).lower() for k in entry.get("keywords", [])]
            boost = entry.get("confidence_boost", 0) or 0
            command = entry.get("command") or f"/{name}"

            keyword_hits = 0
            for kw in keywords:
                kw_words = set(re.findall(r"\w+", kw))
                if kw_words and kw_words.issubset(input_words):
                    keyword_hits += 1
                elif kw in input_text:
                    keyword_hits += 1

            score = (keyword_hits * 10) + (boost if keyword_hits > 0 else 0)
            if keyword_hits > 0 and score > best_score:
                best_score = score
                best_command = command

        if best_score >= 20:
            pred_confidence = "high"
        elif best_score >= 10:
            pred_confidence = "medium"
        else:
            pred_confidence = "low"

        if best_command is None:
            best_command = "no_match"
            pred_confidence = "none"

        is_correct = best_command.lstrip("/") == expected.lstrip("/")
        confidence_correct = pred_confidence == expected_confidence

        if is_correct:
            correct += 1
            if expected != "no_match":
                found_commands[expected] = found_commands.get(expected, 0) + 1

        results.append({
            "input": case["input"],
            "expected": expected,
            "predicted": best_command,
            "correct": is_correct,
            "score": best_score,
            "expected_confidence": expected_confidence,
            "predicted_confidence": pred_confidence,
            "confidence_correct": confidence_correct,
        })

    precision = correct / total if total > 0 else 0
    recall_hits = sum(found_commands.values())
    recall_total = sum(expected_commands.values())
    recall = recall_hits / recall_total if recall_total > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    conf_correct = sum(1 for r in results if r["confidence_correct"])
    confidence_accuracy = conf_correct / total if total > 0 else 0
    composite = (f1 * 0.6) + (confidence_accuracy * 0.2) + (precision * 0.2)

    return {
        "target": "detection-index",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "confidence_accuracy": round(confidence_accuracy, 4),
            "composite": round(composite, 4),
        },
        "summary": {
            "total_cases": total,
            "correct": correct,
            "incorrect": total - correct,
        },
        "failures": [r for r in results if not r["correct"]],
        "details": results,
    }


# ---------------------------------------------------------------------------
# Context-Router Scorer
# ---------------------------------------------------------------------------

def score_context_router(target_path, test_cases_path):
    """
    Score context-router.json against test cases.

    Schema: {"routes": {name: {"keywords": [...], ...}}}. Only `keywords` is
    read (curated `primary_nodes` / auto `primary`/`secondary` are ignored by
    the scorer - additive keys, never required).

    Matching: keyword-overlap; longer (multi-word) keyword matches weigh more.
    Tie-break by lexicographically-smaller route name (key-order independent).

    Returns dict with precision, recall, f1, composite.
    """
    router = load_json(target_path)
    cases = load_json(test_cases_path)
    if not router or not cases:
        return {"error": "Failed to load files"}

    routes = router.get("routes", {})
    test_items = cases.get("test_cases", [])
    if not test_items:
        return {"error": "No test cases found"}

    results = []
    correct = 0
    total = len(test_items)
    expected_routes = {}
    found_routes = {}

    for case in test_items:
        input_text = case["input"].lower()
        expected = case["expected_route"]

        if expected != "no_match":
            expected_routes[expected] = expected_routes.get(expected, 0) + 1

        best_route = None
        best_score = 0

        for route_name, route_config in routes.items():
            keywords = [str(k).lower() for k in route_config.get("keywords", [])]
            score = 0
            for kw in keywords:
                if kw in input_text:
                    score += len(kw.split())
            if score > best_score or (
                score == best_score and score > 0
                and (best_route is None or route_name < best_route)
            ):
                best_score = score
                best_route = route_name

        if best_route is None:
            best_route = "no_match"

        is_correct = best_route == expected
        if is_correct:
            correct += 1
            if expected != "no_match":
                found_routes[expected] = found_routes.get(expected, 0) + 1

        results.append({
            "input": case["input"],
            "expected": expected,
            "predicted": best_route,
            "correct": is_correct,
            "score": best_score,
        })

    precision = correct / total if total > 0 else 0
    recall_hits = sum(found_routes.values())
    recall_total = sum(expected_routes.values())
    recall = recall_hits / recall_total if recall_total > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    composite = (f1 * 0.7) + (precision * 0.3)

    return {
        "target": "context-router",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "composite": round(composite, 4),
        },
        "summary": {
            "total_cases": total,
            "correct": correct,
            "incorrect": total - correct,
        },
        "failures": [r for r in results if not r["correct"]],
        "details": results,
    }


# ---------------------------------------------------------------------------
# Baseline Management
# ---------------------------------------------------------------------------

def update_baseline(root, target, score_result):
    """Update baselines.json: ratchet the recorded composite up on improvement,
    always append a history row. Ratchet is monotonic (only improvements move
    the baseline) - it is the score reference the persist-gate restores toward."""
    baselines_path = Path(root) / "_autoevolve" / "baselines.json"
    baselines = load_json(baselines_path) or {"targets": {}, "history": []}
    baselines.setdefault("targets", {})
    baselines.setdefault("history", [])

    new_composite = score_result["metrics"]["composite"]
    current = baselines["targets"].get(target, {})
    current_composite = current.get("composite", 0)
    improved = new_composite > current_composite

    if improved:
        baselines["targets"][target] = {
            "composite": new_composite,
            "metrics": score_result["metrics"],
            "updated": score_result["timestamp"],
        }

    baselines["history"].append({
        "target": target,
        "timestamp": score_result["timestamp"],
        "composite": new_composite,
        "improved": improved,
        "delta": round(new_composite - current_composite, 4),
    })
    baselines["history"] = baselines["history"][-200:]
    save_json(baselines_path, baselines)

    return {
        "improved": improved,
        "previous": current_composite,
        "current": new_composite,
        "delta": round(new_composite - current_composite, 4),
    }


def get_baseline(root, target):
    """Get current baseline for a target."""
    baselines_path = Path(root) / "_autoevolve" / "baselines.json"
    baselines = load_json(baselines_path) or {"targets": {}}
    return baselines.get("targets", {}).get(target, {"composite": 0})


# ---------------------------------------------------------------------------
# Plateau Detection (The Stopping Problem)
# ---------------------------------------------------------------------------

def detect_plateau(root, target, window=10):
    """
    Detect if optimization has plateaued: no improvement in the last `window`
    iterations. The convergence ceiling IS the discovery - a plateau marks the
    quality limit of this artifact, not a loop failure.
    """
    baselines_path = Path(root) / "_autoevolve" / "baselines.json"
    baselines = load_json(baselines_path) or {"history": []}
    history = [h for h in baselines.get("history", []) if h["target"] == target]

    if len(history) < window:
        return {"plateau": False, "reason": f"Only {len(history)} iterations, need {window}"}

    recent = history[-window:]
    improvements = sum(1 for h in recent if h["improved"])
    if improvements == 0:
        return {
            "plateau": True,
            "reason": f"No improvement in last {window} iterations",
            "ceiling": recent[-1]["composite"],
            "suggestion": "Consider: (1) expand test cases, (2) try a different target, (3) accept ceiling",
        }
    return {
        "plateau": False,
        "improvements_in_window": improvements,
        "trend": "improving" if improvements >= window // 3 else "slowing",
    }


# ---------------------------------------------------------------------------
# Rejected Mutations Log
# ---------------------------------------------------------------------------

def record_rejected_mutation(root, target, run_id, mutation_description,
                             score_before, score_after, reject_reason,
                             source_config_hash=None):
    """
    Append a structured failure entry to _autoevolve/rejected/{ts}-{target}.json.

    Failed iterations carry the gradient information that turns a random walk
    into gradient descent. Called whenever a mutation scores below baseline.
    Best-effort: never raises on IO error (emits a stderr line so disk/permission
    failures stay observable).
    """
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = Path(root) / "_autoevolve" / "rejected"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{ts}-{target}.json"
        try:
            score_before_f = float(score_before)
            score_after_f = float(score_after)
            delta = round(score_after_f - score_before_f, 4)
        except (TypeError, ValueError):
            score_before_f = score_before
            score_after_f = score_after
            delta = None
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "target": target,
            "run_id": run_id,
            "source_config_hash": source_config_hash,
            "mutation_description": mutation_description,
            "score_before": score_before_f,
            "score_after": score_after_f,
            "delta": delta,
            "reject_reason": reject_reason,
        }
        save_json(out_path, entry)
        return out_path
    except Exception as e:
        print(f"WARNING record_rejected_mutation failed: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Mutation-Eligibility Gate (cold-data quiet: off-switch + per-target + MVP-N)
# ---------------------------------------------------------------------------
#
# Deterministic answer to "may AutoEvolve mutate this target right now?". This
# is the code that makes self-tuning ship ON yet stay provably quiet on a fresh
# install: it requires the global off-switch ON, the per-target switch ON, and
# at least MVP-many accumulated real outcomes. The static test-case fixtures are
# the SCORING oracle (always present); this gate is a separate ELIGIBILITY
# signal sourced from a per-target outcomes ledger that ships EMPTY.

MVP_SAMPLE_THRESHOLD_DEFAULT = 8


def _autoevolve_config(root):
    return load_json(Path(root) / "_autoevolve" / "config.json") or {}


def _global_tuning_enabled(root):
    """Read the one-step global off-switch from delegation-config mutation_rules.
    Missing/malformed -> False (fail-closed: no tuning on a broken config)."""
    cfg = load_json(Path(root) / "_graph" / "cache" / "delegation-config.json") or {}
    return bool(cfg.get("mutation_rules", {}).get("v2_tuning_enabled", False))


def count_outcomes(root, target, target_cfg=None):
    """
    Count accumulated real outcomes for a target (the MVP-gate input).

    Reads the per-target outcomes ledger (JSONL, one outcome per non-blank line).
    Ships absent/empty on a cold install -> 0 -> below threshold -> no mutation.
    A real producer (e.g. usage telemetry) appends to this ledger over time.
    """
    target_cfg = target_cfg or {}
    ledger = target_cfg.get("outcomes_ledger") or f"_autoevolve/outcomes/{target}.jsonl"
    path = Path(root) / ledger
    if not path.exists():
        return 0
    try:
        with open(path) as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


def evaluate_mutation_gate(root, target, config=None):
    """
    Deterministic eligibility decision, checked in order:
      1. global off-switch (v2_tuning_enabled) - one-step kill for ALL tuning
      2. per-target `enabled` switch (the per-target default map)
      3. MVP sample threshold - N real outcomes before any mutation

    Returns a dict; `eligible` is True only when all three pass. Never raises.
    """
    root = Path(root)
    config = config if config is not None else _autoevolve_config(root)
    targets = config.get("targets", {}) or {}
    tcfg = targets.get(target)

    result = {
        "target": target,
        "eligible": False,
        "reason": None,
        "outcomes": None,
        "threshold": None,
    }
    if tcfg is None:
        result["reason"] = "unknown-target"
        return result
    if not _global_tuning_enabled(root):
        result["reason"] = "global-off (v2_tuning_enabled=false)"
        return result
    if not tcfg.get("enabled", False):
        result["reason"] = "target-disabled (per-target default OFF)"
        return result

    threshold = int(tcfg.get("mvp_sample_threshold", MVP_SAMPLE_THRESHOLD_DEFAULT))
    n = count_outcomes(root, target, tcfg)
    result["outcomes"] = n
    result["threshold"] = threshold
    if n < threshold:
        result["reason"] = f"insufficient-samples ({n}/{threshold})"
        return result

    result["eligible"] = True
    result["reason"] = "eligible"
    return result


# ---------------------------------------------------------------------------
# Deterministic Baseline-Persist Gate
# ---------------------------------------------------------------------------
#
# Backstops the agent-prompt-enforced revert in the optimizer agent. That revert
# depends on the agent re-reading and restoring the file by judgment. This gate
# moves the revert DECISION from agent judgment to code: re-score the live
# (mutated) config against the pre-mutation snapshot and, on regression,
# deterministically restore the snapshot. A regression cannot persist even if
# the agent forgets to revert.

# Targets whose scorer is a pure function of (config + fixed test cases). A
# score-based gate is only sound for deterministic scorers.
DETERMINISTIC_GATE_TARGETS = {"detection-index", "context-router"}


def _target_live_path(root, target):
    """Map a target name to its live config path (lite layout)."""
    root = Path(root)
    if target == "detection-index":
        return root / "_graph" / "cache" / "detection-index.json"
    if target == "context-router":
        return root / "_graph" / "cache" / "context-router.json"
    return None


def _score_config(target, config_path, root=None):
    """
    Score an arbitrary config file for a deterministic target.

    Returns the composite float, or None if the target is unsupported or the
    scorer could not produce a metric. `root` locates the test-cases; pass it
    explicitly so the gate never depends on CWD.
    """
    config_path = Path(config_path)
    root = Path(root) if root is not None else plugin_root()
    tc_path = root / "_autoevolve" / "test-cases" / f"{target}.json"
    if target == "detection-index":
        result = score_detection_index(config_path, tc_path)
    elif target == "context-router":
        result = score_context_router(config_path, tc_path)
    else:
        return None
    if not result or "error" in result:
        return None
    return result.get("metrics", {}).get("composite")


def evaluate_persist(baseline_composite, mutated_composite, eps=1e-6):
    """
    Pure decision: KEEP or REVERT a mutated config?

    Reverts only on a real regression (mutated below baseline by more than eps).
    Inputs are rounded to 4 places first (the scorers emit 4-place composites);
    eps then only guards injected higher-precision score_fn outputs from
    float-representation noise.
    """
    b = round(baseline_composite, 4)
    m = round(mutated_composite, 4)
    delta = round(m - b, 6)
    regression = m < (b - eps)
    return {
        "action": "revert" if regression else "keep",
        "regression": regression,
        "baseline": baseline_composite,
        "mutated": mutated_composite,
        "delta": delta,
    }


def enforce_persist_gate(root, target, live_config_path, snapshot_path,
                         run_id=None, mutation_description="", score_fn=None):
    """
    Deterministic baseline-persist gate.

    Re-scores the live (mutated) config against the pre-mutation snapshot. On a
    regression it restores the snapshot over the live config (code-enforced
    revert) and records a rejected-mutation entry.

    Returns dict: action ("keep"|"revert"|"skip"|"error"), regression, baseline,
      mutated, delta, reverted_to_snapshot, rejected_log, target [, reason].
    """
    live_config_path = Path(live_config_path)
    snapshot_path = Path(snapshot_path)

    result = {
        "target": target,
        "action": "skip",
        "regression": False,
        "baseline": None,
        "mutated": None,
        "delta": None,
        "reverted_to_snapshot": False,
        "rejected_log": None,
    }

    if target not in DETERMINISTIC_GATE_TARGETS:
        result["reason"] = "non-deterministic scorer; persist-gate requires a deterministic target"
        return result

    # Loud, distinct error if the snapshot is missing: the agent writes it before
    # mutating (Rule 7), so a missing snapshot is a workflow bug that would
    # otherwise let a regression persist silently. Do not revert against nothing.
    if not snapshot_path.exists():
        result["action"] = "error"
        result["reason"] = f"snapshot not found: {snapshot_path}"
        return result

    # Default scorer bound to the caller's root (CWD-independent).
    scorer = score_fn or (lambda tgt, path: _score_config(tgt, path, root=root))
    try:
        baseline_composite = scorer(target, snapshot_path)
        mutated_composite = scorer(target, live_config_path)
    except Exception as e:
        result["action"] = "error"
        result["reason"] = f"scoring failed: {e}"
        return result

    if baseline_composite is None or mutated_composite is None:
        result["action"] = "error"
        result["reason"] = "scorer returned no composite (missing config or test cases)"
        return result

    decision = evaluate_persist(baseline_composite, mutated_composite)
    result.update({
        "action": decision["action"],
        "regression": decision["regression"],
        "baseline": decision["baseline"],
        "mutated": decision["mutated"],
        "delta": decision["delta"],
    })

    if decision["action"] == "revert":
        # Atomic restore: copy into a temp file in the live dir, then os.replace
        # (atomic rename on the same filesystem). A kill mid-copy cannot leave a
        # truncated live config - the original stays until the rename succeeds.
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(live_config_path.parent), prefix=".persist-gate-", suffix=".tmp")
        os.close(tmp_fd)
        try:
            shutil.copyfile(snapshot_path, tmp_path)
            os.replace(tmp_path, live_config_path)
        finally:
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()
        result["reverted_to_snapshot"] = True
        log_path = record_rejected_mutation(
            root=root,
            target=target,
            run_id=run_id or "persist-gate",
            mutation_description=mutation_description or "(persist-gate auto-revert)",
            score_before=baseline_composite,
            score_after=mutated_composite,
            reject_reason="persist-gate-regression",
        )
        result["rejected_log"] = str(log_path) if log_path is not None else None

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_SCORERS = {
    "detection-index": score_detection_index,
    "context-router": score_context_router,
}


def _score_target(root, target):
    """Run the configured scorer for a target via its config entry."""
    config = _autoevolve_config(root)
    tcfg = (config.get("targets", {}) or {}).get(target, {})
    target_file = tcfg.get("target_file")
    test_cases = tcfg.get("test_cases")
    if target_file and test_cases:
        target_path = Path(root) / target_file
        tc_path = Path(root) / test_cases
    else:
        target_path = _target_live_path(root, target)
        tc_path = Path(root) / "_autoevolve" / "test-cases" / f"{target}.json"
    scorer = _SCORERS.get(target)
    if scorer is None or target_path is None:
        return {"error": f"Unknown or unscorable target '{target}'"}
    return scorer(target_path, tc_path)


def main():
    if len(sys.argv) < 2:
        print("Usage: autoevolve-scorer.py <command> [target] [options]")
        print("Commands: score, baseline, plateau, compare, mutation-gate, persist-gate")
        print("Targets: detection-index, context-router")
        sys.exit(1)

    command = sys.argv[1]
    root = plugin_root()

    if command == "score":
        target = sys.argv[2] if len(sys.argv) > 2 else "detection-index"
        result = _score_target(root, target)
        if "error" not in result:
            result["baseline_comparison"] = update_baseline(root, target, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if "error" not in result else 1)

    elif command == "baseline":
        target = sys.argv[2] if len(sys.argv) > 2 else "detection-index"
        print(json.dumps(get_baseline(root, target), indent=2))

    elif command == "plateau":
        target = sys.argv[2] if len(sys.argv) > 2 else "detection-index"
        window = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        result = detect_plateau(root, target, window)
        print(json.dumps(result, indent=2))
        sys.exit(1 if result.get("plateau") else 0)

    elif command == "compare":
        target = sys.argv[2] if len(sys.argv) > 2 else "detection-index"
        baselines_path = Path(root) / "_autoevolve" / "baselines.json"
        baselines = load_json(baselines_path) or {"history": []}
        history = [h for h in baselines.get("history", []) if h["target"] == target]
        if history:
            first, last = history[0], history[-1]
            print(json.dumps({
                "target": target,
                "iterations": len(history),
                "start_score": first["composite"],
                "end_score": last["composite"],
                "total_improvement": round(last["composite"] - first["composite"], 4),
                "improvements": sum(1 for h in history if h["improved"]),
                "improvement_rate": round(sum(1 for h in history if h["improved"]) / len(history), 4),
            }, indent=2))
        else:
            print('{"error": "No history found"}')

    elif command == "mutation-gate":
        # Deterministic eligibility: may AutoEvolve mutate this target now?
        target = sys.argv[2] if len(sys.argv) > 2 else None
        if not target:
            print("Usage: autoevolve-scorer.py mutation-gate <target>", file=sys.stderr)
            sys.exit(1)
        result = evaluate_mutation_gate(root, target)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        # exit 0 = eligible (proceed), 1 = blocked (skip the cycle)
        sys.exit(0 if result.get("eligible") else 1)

    elif command == "persist-gate":
        # Re-score a mutated config against its pre-mutation snapshot and
        # auto-revert on regression.
        target = sys.argv[2] if len(sys.argv) > 2 else None
        snapshot = live = run_id = None
        desc = ""
        for i, arg in enumerate(sys.argv):
            if arg == "--snapshot" and i + 1 < len(sys.argv):
                snapshot = sys.argv[i + 1]
            if arg == "--live" and i + 1 < len(sys.argv):
                live = sys.argv[i + 1]
            if arg == "--run-id" and i + 1 < len(sys.argv):
                run_id = sys.argv[i + 1]
            if arg == "--desc" and i + 1 < len(sys.argv):
                desc = sys.argv[i + 1]
        if not target or not snapshot:
            print("Usage: autoevolve-scorer.py persist-gate <target> --snapshot PATH "
                  "[--live PATH] [--run-id ID] [--desc TEXT]", file=sys.stderr)
            sys.exit(1)
        if live is None:
            live = _target_live_path(root, target)
        result = enforce_persist_gate(root, target, live, snapshot,
                                      run_id=run_id, mutation_description=desc)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        # exit 0 = kept, 2 = reverted (regression caught), 3 = skip/error
        sys.exit({"keep": 0, "revert": 2}.get(result.get("action"), 3))

    else:
        print(f"ERROR: Unknown command '{command}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
