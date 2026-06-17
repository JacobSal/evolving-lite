#!/usr/bin/env python3
"""
Auto-Edge Generator v2 for Knowledge Graph

Run at SessionStart (or manually) to keep the graph self-wiring.

Two edge generation strategies:
1. **Typed edges** (content-based inference):
   - Commands referencing agents → "uses" edge
   - Hooks in same event group → "triggers" edge
   - Scenarios containing agents/commands → "contains" edge
   - Agents referencing other agents → "delegates_to" edge

2. **related_to edges** (domain tag overlap, fallback):
   - Nodes with >= 2 shared domain tags → "related_to" edge
   - Applied to all system component types

All auto-generated edges are marked with auto_generated: true and provenance: "auto".
Existing edges (manual or auto) are never modified or duplicated.

Usage:
    python3 auto-edges.py [--dry-run]
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Set

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR.parent))
from lib.plugin_paths import plugin_root  # noqa: E402

PLUGIN_ROOT = plugin_root()
EDGES_FILE = PLUGIN_ROOT / "_graph" / "edges.json"
NODES_FILE = PLUGIN_ROOT / "_graph" / "knowledge-nodes.json"

# Shared locked-write discipline (flock + in-place RMW): edges.json is a
# multi-writer target (ARS upsert + graph maintenance across concurrent
# sessions); a tmp.replace inode swap could clobber a concurrent locked append.
from lib.locked_json_rmw import locked_write_remerge  # noqa: E402

# All system component types participate in edge generation
SYSTEM_TYPES = {
    "command", "agent", "skill", "hook", "rule", "script",
    "template", "blueprint", "scenario", "reference", "tool",
}

MAX_RELATED_EDGES_PER_NODE = 3
MAX_RELATED_EDGES_PER_RUN = 30

# Generic words excluded from domain overlap matching
GENERIC_WORDS = {
    "pattern", "system", "config", "configuration", "tool", "tools",
    "automation", "quality", "management", "component", "general",
    "agent", "command", "hook", "rule", "template", "learning",
    "knowledge", "workflow", "process", "data", "file", "script",
}


def load_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error loading {path}: {e}", file=sys.stderr)
        return {}


def build_edge_set(edges: list) -> set:
    """Build set of (source, target) tuples for fast dedup."""
    return {(e.get("source", ""), e.get("target", "")) for e in edges}


def make_edge(source: str, target: str, edge_type: str, weight: float = 0.7) -> dict:
    return {
        "source": source,
        "target": target,
        "type": edge_type,
        "weight": weight,
        "auto_generated": True,
        "provenance": "auto",
    }


# =============================================================================
# Strategy 1: Typed edges from content analysis
# =============================================================================

def infer_typed_edges(node_map: dict, existing_pairs: set) -> list:
    """Infer typed edges by analyzing file contents and structure."""
    new_edges = []

    # Pre-read file contents for commands and agents (only .md files < 50KB)
    file_contents = {}
    for nid, node in node_map.items():
        if node.get("type") not in ("command", "agent"):
            continue
        path = node.get("path", "")
        if not path:
            continue
        full_path = PLUGIN_ROOT / path
        if full_path.exists() and full_path.stat().st_size < 50000:
            try:
                file_contents[nid] = full_path.read_text(encoding="utf-8").lower()
            except OSError:
                pass

    # Build quick lookups — use list to handle duplicate stems (agent-debugger + agent-debugger-agent)
    agent_name_to_ids: Dict[str, List[str]] = {}
    for nid, n in node_map.items():
        if n.get("type") == "agent":
            stems = set()
            # Stem from ID (e.g., "debugger" from "agent-debugger")
            stem = nid.replace("agent-", "")
            stems.add(stem)
            if stem.endswith("-agent"):
                stems.add(stem[:-6])
            for s in stems:
                if len(s) >= 6:  # Filter short stems early
                    agent_name_to_ids.setdefault(s, []).append(nid)

    def _match_agents(content: str, source_nid: str, edge_type: str, weight: float):
        """Find agent references in content using word-boundary matching."""
        for agent_name, agent_ids in agent_name_to_ids.items():
            # Use word-boundary check to reduce prose false positives
            # Match: "agent-debugger", "debugger-agent", "debugger agent"
            # Reject: "debugging" containing "debugg" but not "debugger"
            if agent_name not in content:
                continue
            # Verify word boundary: char before/after must be non-alphanumeric
            idx = content.find(agent_name)
            if idx > 0 and content[idx - 1].isalnum():
                continue  # Part of a larger word
            end = idx + len(agent_name)
            if end < len(content) and content[end].isalnum():
                continue  # Part of a larger word
            for agent_id in agent_ids:
                if agent_id == source_nid:
                    continue
                pair = (source_nid, agent_id)
                if pair not in existing_pairs:
                    new_edges.append(make_edge(source_nid, agent_id, edge_type, weight))
                    existing_pairs.add(pair)

    # --- Commands → Agents (uses) ---
    for nid, content in file_contents.items():
        if node_map[nid].get("type") == "command":
            _match_agents(content, nid, "uses", 0.8)

    # --- Agents → Agents (delegates_to) ---
    for nid, content in file_contents.items():
        if node_map[nid].get("type") == "agent":
            _match_agents(content, nid, "delegates_to", 0.7)

    # --- Scenarios → contained components (contains) ---
    # Build reverse path → node_id index for O(1) lookups
    path_to_id = {n.get("path", ""): nid for nid, n in node_map.items() if n.get("path")}

    scenarios_dir = PLUGIN_ROOT / "scenarios"
    if scenarios_dir.exists():
        for scenario_dir in scenarios_dir.iterdir():
            if not scenario_dir.is_dir():
                continue
            scenario_id = f"scenario-{scenario_dir.name}"
            if scenario_id not in node_map:
                continue
            for sub in ("agents", "commands", "skills"):
                sub_dir = scenario_dir / sub
                if not sub_dir.exists():
                    continue
                for f in sub_dir.glob("*.md"):
                    rel_path = str(f.relative_to(PLUGIN_ROOT))
                    cid = path_to_id.get(rel_path)
                    if cid:
                        pair = (scenario_id, cid)
                        if pair not in existing_pairs:
                            new_edges.append(make_edge(scenario_id, cid, "contains", 0.9))
                            existing_pairs.add(pair)

    # --- Rules referenced by hooks (triggers) ---
    # Check if hook file content mentions rule names
    hook_nodes = {nid: n for nid, n in node_map.items() if n.get("type") == "hook"}
    rule_nodes = {nid: n for nid, n in node_map.items() if n.get("type") == "rule"}
    for hook_id, hook_node in hook_nodes.items():
        path = hook_node.get("path", "")
        if not path:
            continue
        full_path = PLUGIN_ROOT / path
        if not full_path.exists() or full_path.stat().st_size > 50000:
            continue
        try:
            content = full_path.read_text(encoding="utf-8").lower()
        except OSError:
            continue
        for rule_id, rule_node in rule_nodes.items():
            rule_stem = rule_id.replace("rule-", "")
            if len(rule_stem) < 6:
                continue
            if rule_stem in content:
                pair = (hook_id, rule_id)
                if pair not in existing_pairs:
                    new_edges.append(make_edge(hook_id, rule_id, "triggers", 0.7))
                    existing_pairs.add(pair)

    return new_edges


# =============================================================================
# Strategy 2: related_to edges from domain tag overlap
# =============================================================================

def infer_related_edges(node_map: dict, existing_pairs: set) -> list:
    """Generate related_to edges for system nodes without any edges."""
    new_edges = []

    # Find system nodes that have no edges at all
    nodes_with_edges = set()
    for s, t in existing_pairs:
        nodes_with_edges.add(s)
        nodes_with_edges.add(t)

    orphan_nodes = [
        n for n in node_map.values()
        if n.get("type") in SYSTEM_TYPES
        and n.get("id") not in nodes_with_edges
        and n.get("domain")
        and len(n["domain"]) > 0
    ]

    total_added = 0
    for node in orphan_nodes:
        if total_added >= MAX_RELATED_EDGES_PER_RUN:
            break

        node_tags = {t.lower() for t in node.get("domain", [])
                     if t.lower() not in GENERIC_WORDS and len(t) > 2}
        if len(node_tags) < 1:
            continue

        candidates = []
        for other in node_map.values():
            if other["id"] == node["id"]:
                continue
            pair = (node["id"], other["id"])
            rev_pair = (other["id"], node["id"])
            if pair in existing_pairs or rev_pair in existing_pairs:
                continue
            other_tags = {t.lower() for t in other.get("domain", [])
                         if t.lower() not in GENERIC_WORDS and len(t) > 2}
            overlap = node_tags & other_tags
            if len(overlap) >= 2:
                weight = round(len(overlap) / max(len(node_tags), len(other_tags)) * 0.5, 2)
                candidates.append((other["id"], weight))

        candidates.sort(key=lambda c: c[1], reverse=True)
        node_added = 0
        for target_id, weight in candidates[:MAX_RELATED_EDGES_PER_NODE]:
            if total_added >= MAX_RELATED_EDGES_PER_RUN:
                break
            pair = (node["id"], target_id)
            new_edges.append(make_edge(node["id"], target_id, "related_to", weight))
            existing_pairs.add(pair)
            node_added += 1
            total_added += 1

    return new_edges


# =============================================================================
# Main
# =============================================================================

def generate_edges(dry_run: bool = False) -> dict:
    """Run both edge generation strategies."""
    nodes_data = load_json(NODES_FILE)
    edges_data = load_json(EDGES_FILE)

    if not nodes_data or not edges_data:
        print("Error: Could not load nodes or edges", file=sys.stderr)
        return {"new_edges": 0, "nodes_processed": 0}

    # Guard: abort only on a MALFORMED edges.json (missing/non-list "edges").
    # An empty list is the legitimate cold-start state on a fresh install.
    existing_edges_list = edges_data.get("edges")
    if not isinstance(existing_edges_list, list):
        print("Error: edges.json malformed - aborting to prevent data loss", file=sys.stderr)
        return {"new_edges": 0, "nodes_processed": 0}

    node_map = {n["id"]: n for n in nodes_data.get("nodes", [])}
    existing_edges = edges_data.get("edges", [])
    existing_pairs = build_edge_set(existing_edges)

    if dry_run:
        # Preview against the start-of-run snapshot; no write.
        typed = infer_typed_edges(node_map, existing_pairs)
        related = infer_related_edges(node_map, existing_pairs)
        total = len(typed) + len(related)
        print(f"Auto-edges: {total} new edges ({len(typed)} typed, "
              f"{len(related)} related_to) for {len(node_map)} nodes (dry-run)")
        return {"new_edges": total, "nodes_processed": len(node_map)}

    # Apply path: re-read edges.json FRESH under an exclusive lock and re-infer
    # against the fresh edge set (infer_* dedups against existing pairs, so this
    # is idempotent), then write IN PLACE (shared locked_json_rmw discipline).
    counts = {"typed": 0, "related": 0}

    def _apply(fresh):
        fresh_edges = fresh.get("edges")
        if not isinstance(fresh_edges, list):
            return False  # malformed fresh read -> protect existing edges
        pairs = build_edge_set(fresh_edges)
        typed = infer_typed_edges(node_map, pairs)
        related = infer_related_edges(node_map, pairs)
        new = typed + related
        if not new:
            return False
        counts["typed"], counts["related"] = len(typed), len(related)
        fresh_edges.extend(new)
        fresh["edges"] = fresh_edges
        fresh["total_count"] = len(fresh_edges)
        fresh["auto_count"] = sum(1 for e in fresh_edges if e.get("auto_generated"))
        fresh["explicit_count"] = sum(
            1 for e in fresh_edges if not e.get("auto_generated"))
        type_counts = {}
        for e in fresh_edges:
            t = e.get("type", "related_to")
            type_counts[t] = type_counts.get(t, 0) + 1
        fresh["edge_type_breakdown"] = type_counts
        return True

    changed = locked_write_remerge(EDGES_FILE, _apply)
    total = counts["typed"] + counts["related"]
    status = "written" if changed else "no-op (lock-timeout or nothing new)"
    print(f"Auto-edges: {total} new edges ({counts['typed']} typed, "
          f"{counts['related']} related_to) for {len(node_map)} nodes ({status})")

    return {"new_edges": total, "nodes_processed": len(node_map)}


def main():
    dry_run = "--dry-run" in sys.argv
    generate_edges(dry_run=dry_run)


if __name__ == "__main__":
    main()
