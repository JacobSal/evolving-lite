"""ARS tests: classification, dispatch targets, idempotency, schema safety.

All tests run against a throwaway plugin tree (CLAUDE_PLUGIN_ROOT override),
never the real repo.
"""

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))


@pytest.fixture()
def plugin_tree(tmp_path, monkeypatch):
    """Minimal plugin tree + freshly-bound artifact_registration module."""
    (tmp_path / "_graph" / "cache").mkdir(parents=True)
    (tmp_path / "commands").mkdir()
    (tmp_path / "_graph" / "knowledge-nodes.json").write_text(
        json.dumps({"version": "1.0", "nodes": []}))
    (tmp_path / "_graph" / "cache" / "context-router.json").write_text(
        json.dumps({"version": "1.0", "routes": {
            "debugging": {"keywords": ["debug"],
                          "primary_nodes": ["knowledge/rules/quick-dsv.md"]},
        }}))
    (tmp_path / "_graph" / "cache" / "detection-index.json").write_text(
        json.dumps({"version": "1.0", "entries": {
            "debug": {"keywords": ["debug"], "command": "/debug",
                      "confidence_boost": 15},
        }}))
    (tmp_path / "commands" / "test-cmd.md").write_text(
        "# Test Command\n\nA synthetic command for testing.\n")

    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))
    monkeypatch.delenv("CLAUDE_ARTIFACT_BACKFILL_RUNNING", raising=False)
    import lib.plugin_paths
    import lib.artifact_registration
    importlib.reload(lib.plugin_paths)
    ar = importlib.reload(lib.artifact_registration)
    yield tmp_path, ar
    # Re-bind to the real repo for subsequent test modules.
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT")
    importlib.reload(lib.plugin_paths)
    importlib.reload(lib.artifact_registration)


def test_classify_lite_layout(plugin_tree):
    _, ar = plugin_tree
    assert ar.classify("hooks/scripts/security-tier-check.py") == "hook"
    assert ar.classify("commands/test-cmd.md") == "command"
    assert ar.classify("skills/foo/SKILL.md") == "skill"
    assert ar.classify("agents/planner.md") == "agent"
    assert ar.classify("knowledge/rules/delegation.md") == "rule"
    assert ar.classify("scripts/graph/auto-edges.py") == "script"
    assert ar.classify("docs/PORT-MANIFEST.md") == "reference"
    assert ar.classify("README.md") is None
    assert ar.classify("_archive/old.md") is None  # deny list


def test_dispatch_command_hits_all_four_targets(plugin_tree):
    root, ar = plugin_tree
    result = ar.dispatch("commands/test-cmd.md", mode="apply")

    assert result.artifact_type == "command"
    assert set(result.targets_ok) == {"kairn", "router", "detection", "knowledge_nodes"}
    assert result.targets_failed == []

    nodes = json.loads((root / "_graph" / "knowledge-nodes.json").read_text())["nodes"]
    assert any(n["id"] == "command-test-cmd" for n in nodes)

    router = json.loads((root / "_graph" / "cache" / "context-router.json").read_text())
    route = router["routes"]["auto-command-commands-test-cmd"]
    assert "command-test-cmd" in route["primary"]
    # Curated route untouched (primary_nodes schema coexists).
    assert router["routes"]["debugging"]["primary_nodes"] == ["knowledge/rules/quick-dsv.md"]

    det = json.loads((root / "_graph" / "cache" / "detection-index.json").read_text())
    assert det["entries"]["test-cmd"]["command"] == "/test-cmd"
    # Curated entry untouched.
    assert det["entries"]["debug"]["confidence_boost"] == 15

    queue = (root / "_inbox" / "artifact-registration-queue.jsonl").read_text().splitlines()
    assert json.loads(queue[0])["kind"] == "kairn_add"

    ledger = (root / "_ledgers" / "artifact-registration-latency.jsonl").read_text().splitlines()
    assert json.loads(ledger[-1])["type"] == "command"


def test_dispatch_idempotent_on_second_run(plugin_tree):
    root, ar = plugin_tree
    ar.dispatch("commands/test-cmd.md", mode="apply")
    second = ar.dispatch("commands/test-cmd.md", mode="apply")
    assert "knowledge_nodes:idempotent" in second.targets_ok
    assert "detection:idempotent" in second.targets_ok
    nodes = json.loads((root / "_graph" / "knowledge-nodes.json").read_text())["nodes"]
    assert sum(1 for n in nodes if n["id"] == "command-test-cmd") == 1


def test_preserve_existing_protects_curated_detection_entry(plugin_tree):
    root, ar = plugin_tree
    changed = ar.upsert_detection_entry("/debug", ["totally", "new"], artifact_type="command")
    assert changed is False
    det = json.loads((root / "_graph" / "cache" / "detection-index.json").read_text())
    assert det["entries"]["debug"]["keywords"] == ["debug"]  # untouched


def test_observe_mode_writes_nothing(plugin_tree):
    root, ar = plugin_tree
    result = ar.dispatch("commands/test-cmd.md", mode="observe")
    assert result.targets_ok == []
    nodes = json.loads((root / "_graph" / "knowledge-nodes.json").read_text())["nodes"]
    assert nodes == []
    assert not (root / "_inbox" / "artifact-registration-queue.jsonl").exists()


def test_recursion_guard_skips(plugin_tree, monkeypatch):
    _, ar = plugin_tree
    monkeypatch.setenv("CLAUDE_ARTIFACT_BACKFILL_RUNNING", "1")
    result = ar.dispatch("commands/test-cmd.md", mode="apply")
    assert result.skipped_reason == "recursion_guard"


def test_config_loaded_classify_rules_override(plugin_tree, monkeypatch):
    root, _ = plugin_tree
    (root / "_graph" / "cache" / "ars-classify-rules.json").write_text(json.dumps({
        "rules": [{"pattern": r"^custom/.+\.md$", "type": "reference"}]
    }))
    import lib.artifact_registration
    ar = importlib.reload(lib.artifact_registration)
    assert ar.classify("custom/thing.md") == "reference"
    assert ar.classify("commands/test-cmd.md") is None  # defaults replaced


def test_path_traversal_returns_none(plugin_tree):
    _, ar = plugin_tree
    assert ar.extract_title("../../etc/passwd.md") is None
