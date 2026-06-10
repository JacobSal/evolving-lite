#!/usr/bin/env python3
"""
Synthesis Detector — Finds coactivation clusters and writes synthesis candidates.

Reads coactivation.json, finds cliques of 3+ nodes that consistently fire together,
checks against already-synthesized clusters, writes new candidates to
_graph/cache/synthesis-candidates.json.

Runs as SessionStart hook AFTER coactivation-aggregator.py.
Idempotent: safe to run multiple times. Only adds NEW candidates.

Usage:
  python3 scripts/synthesis-detector.py           # Normal run
  python3 scripts/synthesis-detector.py --dry-run  # Show candidates without writing
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR.parent))
from lib.plugin_paths import plugin_root  # noqa: E402

PLUGIN_ROOT = plugin_root()
COACTIVATION_FILE = PLUGIN_ROOT / "_graph" / "cache" / "coactivation.json"
NODES_FILE = PLUGIN_ROOT / "_graph" / "knowledge-nodes.json"
OUTPUT_FILE = PLUGIN_ROOT / "_graph" / "cache" / "synthesis-candidates.json"
# Input-fingerprint cache for skip-if-unchanged optimization. Synthesis is
# deterministic: same inputs -> same outputs. Skip the full O(n^2) clique
# computation when coactivation.json + knowledge-nodes.json are unchanged.
INPUT_FINGERPRINT_FILE = PLUGIN_ROOT / "_graph" / "cache" / ".synthesis-detector-input-fingerprint.json"

# Only consider pairs with weighted_count above this threshold
MIN_WEIGHTED_COUNT = 45.0  # High bar: only the strongest coactivation clusters
MIN_CLIQUE_SIZE = 3
MAX_CLIQUE_SIZE = 7  # Larger clusters are too broad for meaningful synthesis
MAX_CANDIDATES_PER_RUN = 3  # Conservative: quality over quantity
MIN_OVERLAP_RATIO = 0.7  # Merge clusters sharing 70%+ members


def load_coactivation():
    """Load coactivation data and return filtered pairs."""
    if not COACTIVATION_FILE.exists():
        return {}

    with open(COACTIVATION_FILE) as f:
        data = json.load(f)

    pairs = {}
    for pair_key, info in data.get("node_pairs", {}).items():
        if info.get("weighted_count", 0) >= MIN_WEIGHTED_COUNT:
            a, b = pair_key.split("::")
            pairs[(a, b)] = info["weighted_count"]

    return pairs


def load_node_names():
    """Load node id -> name mapping from knowledge-nodes.json."""
    if not NODES_FILE.exists():
        return {}

    with open(NODES_FILE) as f:
        data = json.load(f)

    names = {}
    for node in data.get("nodes", []):
        node_id = node.get("id", "")
        names[node_id] = {
            "name": node.get("name", node_id),
            "type": node.get("type", "unknown"),
            "description": node.get("description", "")[:120],
        }

    return names


def build_adjacency(pairs):
    """Build adjacency list from coactivation pairs."""
    adj = defaultdict(set)
    for (a, b) in pairs:
        adj[a].add(b)
        adj[b].add(a)
    return dict(adj)


def find_cliques(pairs, adj, min_size=3):
    """Find cliques (fully connected subgraphs) using greedy triangle expansion.

    Conservative: only finds cliques where ALL pairs are above threshold.
    """
    pair_set = set()
    for (a, b) in pairs:
        pair_set.add((min(a, b), max(a, b)))

    def are_connected(n1, n2):
        key = (min(n1, n2), max(n1, n2))
        return key in pair_set

    # Step 1: Find all triangles (3-cliques)
    triangles = set()
    seen_nodes = set(adj.keys())

    for node in seen_nodes:
        neighbors = adj.get(node, set())
        for n1, n2 in combinations(neighbors, 2):
            if are_connected(n1, n2):
                triangle = tuple(sorted([node, n1, n2]))
                triangles.add(triangle)

    if not triangles:
        return []

    # Step 2: Try to expand triangles into larger cliques (capped)
    cliques = []
    for triangle in triangles:
        clique = set(triangle)
        # Try adding nodes connected to ALL clique members, up to max size
        candidates = set.intersection(*(adj.get(n, set()) for n in clique))
        for candidate in sorted(candidates):
            if len(clique) >= MAX_CLIQUE_SIZE:
                break
            if all(are_connected(candidate, member) for member in clique):
                clique.add(candidate)
        cliques.append(tuple(sorted(clique)))

    # Deduplicate exact matches
    cliques = list(set(cliques))
    cliques.sort(key=lambda c: (-len(c), c))

    # Remove cliques that are subsets of larger ones
    final = []
    for clique in cliques:
        clique_set = set(clique)
        if not any(clique_set <= set(other) for other in final):
            final.append(clique)

    # Merge near-duplicates (70%+ overlap): keep the larger one
    merged = []
    for clique in final:
        clique_set = set(clique)
        is_near_dup = False
        for existing in merged:
            existing_set = set(existing)
            overlap = len(clique_set & existing_set) / min(len(clique_set), len(existing_set))
            if overlap >= MIN_OVERLAP_RATIO:
                is_near_dup = True
                break
        if not is_near_dup:
            merged.append(clique)

    return merged[:MAX_CANDIDATES_PER_RUN * 3]


def load_existing_candidates():
    """Load already-synthesized cluster IDs to avoid duplicates."""
    if not OUTPUT_FILE.exists():
        return set()

    with open(OUTPUT_FILE) as f:
        data = json.load(f)

    existing = set()
    for candidate in data.get("candidates", []):
        existing.add(candidate.get("cluster_id", ""))
    for processed in data.get("processed", []):
        existing.add(processed)

    return existing


def make_cluster_id(clique):
    """Deterministic cluster ID from sorted node IDs."""
    return "+".join(sorted(clique))


def avg_coactivation(clique, pairs):
    """Average weighted coactivation score across all pairs in clique."""
    scores = []
    for a, b in combinations(clique, 2):
        score = pairs.get((a, b), pairs.get((b, a), 0))
        scores.append(score)
    return sum(scores) / len(scores) if scores else 0


def _compute_input_fingerprint():
    """Cheap fingerprint of input files for skip-if-unchanged check.

    Uses mtime_ns + size of both input files. No content hash (file sizes
    here are MB-scale, hashing would defeat the optimization purpose).
    Returns a stable string suitable for equality comparison.
    """
    parts = []
    for f in (COACTIVATION_FILE, NODES_FILE):
        try:
            if f.exists():
                st = f.stat()
                parts.append(f"{f.name}:{st.st_mtime_ns}:{st.st_size}")
            else:
                parts.append(f"{f.name}:absent")
        except OSError:
            parts.append(f"{f.name}:stat-error")
    return "|".join(parts)


def _read_cached_fingerprint():
    """Returns cached fingerprint string or None on miss/error. Fail-open."""
    try:
        if INPUT_FINGERPRINT_FILE.exists():
            return json.loads(INPUT_FINGERPRINT_FILE.read_text()).get("fingerprint")
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _write_cached_fingerprint(fp):
    """Persist fingerprint after successful run. Fail-open."""
    try:
        INPUT_FINGERPRINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        INPUT_FINGERPRINT_FILE.write_text(json.dumps({
            "fingerprint": fp,
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }))
    except OSError:
        pass


def main():
    dry_run = "--dry-run" in sys.argv

    # Skip-if-unchanged: synthesis is deterministic per input. Compare fingerprint
    # of input files to last-successful-run fingerprint. Skip on match.
    current_fp = _compute_input_fingerprint()
    if not dry_run:
        cached_fp = _read_cached_fingerprint()
        if cached_fp == current_fp:
            print("synthesis-detector: skip (inputs unchanged since last run)")
            return

    pairs = load_coactivation()
    if not pairs:
        print("synthesis-detector: no coactivation data, skipping")
        if not dry_run:
            _write_cached_fingerprint(current_fp)
        return

    adj = build_adjacency(pairs)
    cliques = find_cliques(pairs, adj, MIN_CLIQUE_SIZE)

    if not cliques:
        print("synthesis-detector: no clusters found above threshold")
        if not dry_run:
            _write_cached_fingerprint(current_fp)
        return

    node_names = load_node_names()
    existing = load_existing_candidates()

    # Build candidates
    new_candidates = []
    for clique in cliques:
        cluster_id = make_cluster_id(clique)
        if cluster_id in existing:
            continue

        avg_score = avg_coactivation(clique, pairs)
        members = []
        for node_id in clique:
            info = node_names.get(node_id, {"name": node_id, "type": "unknown", "description": ""})
            members.append({
                "id": node_id,
                "name": info["name"],
                "type": info["type"],
            })

        new_candidates.append({
            "cluster_id": cluster_id,
            "size": len(clique),
            "avg_coactivation": round(avg_score, 2),
            "members": members,
            "detected": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "pending",
        })

    # Sort by score descending, limit
    new_candidates.sort(key=lambda c: -c["avg_coactivation"])
    new_candidates = new_candidates[:MAX_CANDIDATES_PER_RUN]

    if not new_candidates:
        print("synthesis-detector: no new clusters (all already known)")
        if not dry_run:
            _write_cached_fingerprint(current_fp)
        return

    if dry_run:
        print(f"DRY RUN: {len(new_candidates)} new synthesis candidates:")
        for c in new_candidates:
            names = [m["name"] for m in c["members"]]
            print(f"  [{c['size']} nodes, score={c['avg_coactivation']}] {', '.join(names)}")
        return

    # Load existing file or create new
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            output = json.load(f)
    else:
        output = {
            "schema_version": "1.0",
            "candidates": [],
            "processed": [],
        }

    output["candidates"].extend(new_candidates)
    output["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    from lib.cache_writer import atomic_write_json
    atomic_write_json(OUTPUT_FILE, output, indent=2, ensure_ascii=False)

    print(f"synthesis-detector: {len(new_candidates)} new candidates written")
    for c in new_candidates:
        names = [m["name"] for m in c["members"]]
        print(f"  [{c['size']} nodes, score={c['avg_coactivation']}] {', '.join(names)}")

    # Cache fingerprint after successful run so next call with same inputs skips.
    _write_cached_fingerprint(current_fp)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Fail-open: never block session start
        print(f"synthesis-detector error: {e}", file=sys.stderr)
        sys.exit(0)
