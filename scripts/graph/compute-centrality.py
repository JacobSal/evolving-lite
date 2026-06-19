#!/usr/bin/env python3
"""
Compute Centrality Scores — Katz Centrality on weighted, filtered Knowledge Graph.

Loads edges.json + coactivation.json, applies edge-type and provenance weighting,
computes Katz Centrality via networkx, outputs centrality-scores.json.

Edge-Type Weights:
  implements/triggers/depends_on -> 1.0
  uses/extends                   -> 0.8
  documents/references           -> 0.5
  related_to                     -> EXCLUDED unless co-activated (then 0.4)
  all others                     -> 0.3

Provenance Weights:
  human      -> 1.0
  behavioral -> 0.8
  auto       -> 0.3
  unknown    -> 0.2

Usage:
  python3 scripts/compute-centrality.py              # Full computation
  python3 scripts/compute-centrality.py --validate   # Validate output JSON schema
  python3 scripts/compute-centrality.py --dry-run    # Compute and print, don't write
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import networkx as nx
except ImportError:
    # Fail-open: centrality is an enhancer, never a SessionStart blocker.
    print("compute-centrality: skipped (networkx not installed - pip install networkx)",
          file=sys.stderr)
    sys.exit(0)

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR.parent))
from lib.plugin_paths import plugin_root  # noqa: E402

PLUGIN_ROOT = plugin_root()
EDGES_PATH = PLUGIN_ROOT / "_graph" / "edges.json"
NODES_PATH = PLUGIN_ROOT / "_graph" / "knowledge-nodes.json"
COACTIVATION_PATH = PLUGIN_ROOT / "_graph" / "cache" / "coactivation.json"
OUTPUT_PATH = PLUGIN_ROOT / "_graph" / "cache" / "centrality-scores.json"

# Edge-type weight mapping
EDGE_TYPE_WEIGHTS = {
    "implements": 1.0,
    "triggers": 1.0,
    "depends_on": 1.0,
    "uses": 0.8,
    "extends": 0.8,
    "delegates_to": 0.8,
    "called_by": 0.8,
    "produces": 0.9,
    "documents": 0.5,
    "references": 0.5,
    "documented_by": 0.5,
    "contains": 0.5,
    "has_command": 0.5,
    "has_agent": 0.5,
    "has_knowledge": 0.5,
    "uses_agent": 0.5,
    "uses_knowledge": 0.5,
    "related_to": 0.05,  # Boosted to 0.4 if co-activated (weighted_count >= 2.0)
    "sibling": 0.3,
    "complements": 0.3,
    "integrates_with": 0.3,
    "inspired_by": 0.2,
}

PROVENANCE_WEIGHTS = {
    "human": 1.0,
    "behavioral": 0.8,
    "auto": 0.3,
    "unknown": 0.2,
}

# Katz centrality alpha parameter (small for sparse graphs)
KATZ_ALPHA = 0.005


def load_edges():
    """Load and return edges from edges.json."""
    with open(EDGES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("edges", [])


def load_nodes():
    """Load all node IDs from knowledge-nodes.json."""
    with open(NODES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {n["id"] for n in data.get("nodes", [])}


def load_coactivation():
    """Load co-activation data. Returns dict of pair_key -> weighted_count."""
    if not COACTIVATION_PATH.exists():
        return {}
    try:
        with open(COACTIVATION_PATH, encoding="utf-8") as f:
            data = json.load(f)
        pairs = data.get("node_pairs", {})
        return {k: v.get("weighted_count", 0) for k, v in pairs.items()}
    except Exception:
        return {}


def is_coactivated(source, target, coactivation, min_weight=2.0):
    """Check if two nodes have been meaningfully co-activated (not just once)."""
    pair_key = "::".join(sorted([source, target]))
    return coactivation.get(pair_key, 0) >= min_weight


def build_graph(edges, all_node_ids, coactivation):
    """Build weighted directed graph from edges."""
    G = nx.DiGraph()

    # Add all nodes (even isolated ones)
    for node_id in all_node_ids:
        G.add_node(node_id)

    for edge in edges:
        source = edge.get("source", "")
        target = edge.get("target", "")
        edge_type = edge.get("type", "related_to")
        provenance = edge.get("provenance", "unknown")

        if not source or not target:
            continue
        if source not in all_node_ids or target not in all_node_ids:
            continue  # Skip edges referencing unknown/phantom nodes

        # Compute edge weight
        type_weight = EDGE_TYPE_WEIGHTS.get(edge_type, 0.3)

        # related_to edges are excluded unless co-activated (QL finding: noise dominates)
        if edge_type == "related_to":
            if is_coactivated(source, target, coactivation):
                type_weight = 0.4
            else:
                continue  # Skip: unconfirmed related_to is noise

        prov_weight = PROVENANCE_WEIGHTS.get(provenance, 0.2)

        final_weight = type_weight * prov_weight

        # Add edge (if duplicate, keep higher weight)
        if G.has_edge(source, target):
            existing = G[source][target].get("weight", 0)
            if final_weight > existing:
                G[source][target]["weight"] = final_weight
        else:
            G.add_edge(source, target, weight=final_weight)

    return G


def compute_katz(G):
    """Compute Katz centrality. Falls back to lower alpha if convergence fails."""
    alpha = KATZ_ALPHA
    for attempt in range(3):
        try:
            scores = nx.katz_centrality(
                G, alpha=alpha, beta=1.0, max_iter=1000, tol=1e-6, weight="weight"
            )
            return scores
        except nx.PowerIterationFailedConvergence:
            old_alpha = alpha
            alpha *= 0.5  # Reduce alpha and retry
            print(f"  Convergence failed at alpha={old_alpha}, retrying with alpha={alpha}", file=sys.stderr)

    # Last resort: use degree centrality
    print("  WARNING: Katz failed, falling back to degree centrality", file=sys.stderr)
    return nx.degree_centrality(G)


def normalize_scores(scores):
    """Normalize scores to 0-1 range."""
    if not scores:
        return {}
    max_score = max(scores.values())
    if max_score == 0:
        return {k: 0.0 for k in scores}
    return {k: round(v / max_score, 6) for k, v in scores.items()}


def build_output(scores, all_node_ids, G):
    """Build output JSON structure."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    nodes_output = {}
    for node_id in all_node_ids:
        centrality = scores.get(node_id, 0.0)
        in_degree = G.in_degree(node_id, weight="weight") if node_id in G else 0
        out_degree = G.out_degree(node_id, weight="weight") if node_id in G else 0

        nodes_output[node_id] = {
            "centrality": centrality,
            "in_degree_weighted": round(in_degree, 4),
            "out_degree_weighted": round(out_degree, 4),
            "keystone": None,  # Phase 2: simulated removal (optional)
            "last_computed": now,
        }

    # Sort by centrality descending
    sorted_nodes = dict(
        sorted(nodes_output.items(), key=lambda x: x[1]["centrality"], reverse=True)
    )

    return {
        "schema_version": "1.0",
        "algorithm": "katz_centrality",
        "alpha": KATZ_ALPHA,
        "updated": now,
        "total_nodes": len(sorted_nodes),
        "graph_stats": {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "density": round(nx.density(G), 6),
            "avg_in_degree": round(sum(d for _, d in G.in_degree()) / max(G.number_of_nodes(), 1), 2),
        },
        "scores": sorted_nodes,
    }


def validate_output(output_path):
    """Validate the output JSON schema."""
    try:
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        required_keys = ["schema_version", "algorithm", "updated", "total_nodes", "scores"]
        for key in required_keys:
            if key not in data:
                print(f"FAIL: Missing key '{key}'", file=sys.stderr)
                return False

        scores = data.get("scores", {})
        if not scores:
            print("FAIL: Empty scores", file=sys.stderr)
            return False

        # Check a sample node
        sample = next(iter(scores.values()))
        for field in ["centrality", "last_computed"]:
            if field not in sample:
                print(f"FAIL: Node missing field '{field}'", file=sys.stderr)
                return False

        print(f"PASS: {len(scores)} nodes scored, schema valid")
        return True
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return False


def main():
    dry_run = "--dry-run" in sys.argv
    validate_only = "--validate" in sys.argv

    if validate_only:
        if not OUTPUT_PATH.exists():
            print("FAIL: centrality-scores.json not found", file=sys.stderr)
            sys.exit(1)
        ok = validate_output(OUTPUT_PATH)
        sys.exit(0 if ok else 1)

    if not EDGES_PATH.exists() or not NODES_PATH.exists():
        print("compute-centrality: skipped (graph files not present yet)")
        return

    print("Loading edges...")
    edges = load_edges()
    print(f"  {len(edges)} edges loaded")

    print("Loading nodes...")
    all_node_ids = load_nodes()
    print(f"  {len(all_node_ids)} nodes loaded")

    if not all_node_ids:
        print("compute-centrality: skipped (empty graph - cold start)")
        return

    print("Loading co-activation data...")
    coactivation = load_coactivation()
    print(f"  {len(coactivation)} co-activation pairs loaded")

    print("Building weighted graph...")
    G = build_graph(edges, all_node_ids, coactivation)
    print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"  Density: {nx.density(G):.6f}")

    print("Computing Katz centrality...")
    raw_scores = compute_katz(G)
    scores = normalize_scores(raw_scores)
    print(f"  Scored {len(scores)} nodes")

    # Print top 10
    top10 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
    print("\nTop 10 by centrality:")
    for i, (node, score) in enumerate(top10, 1):
        print(f"  {i:2d}. {node}: {score:.6f}")

    output = build_output(scores, all_node_ids, G)

    if dry_run:
        print(f"\nDRY RUN: Would write {output['total_nodes']} nodes to {OUTPUT_PATH}")
        return

    # Atomic write (shared discipline)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    from lib.cache_writer import atomic_write_json
    atomic_write_json(OUTPUT_PATH, output, indent=2, ensure_ascii=False)

    print(f"\nWrote {output['total_nodes']} nodes to {OUTPUT_PATH}")

    # Run validation
    ok = validate_output(OUTPUT_PATH)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
