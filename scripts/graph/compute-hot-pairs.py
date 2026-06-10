#!/usr/bin/env python3
"""Pre-compute top N coactivation pairs for fast delegation lookup.

Reads: _graph/cache/coactivation.json
Writes: _graph/cache/hot-pairs.json

Run: python3 scripts/compute-hot-pairs.py
Hook into: SessionStart or post-coactivation-aggregator
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR.parent))
from lib.plugin_paths import plugin_root  # noqa: E402

PLUGIN_ROOT = plugin_root()
COACTIVATION_FILE = PLUGIN_ROOT / "_graph" / "cache" / "coactivation.json"
OUTPUT_FILE = PLUGIN_ROOT / "_graph" / "cache" / "hot-pairs.json"
TOP_N = 50


def main():
    if not COACTIVATION_FILE.exists():
        print("No coactivation.json found, skipping hot-pairs computation.")
        return

    with open(COACTIVATION_FILE) as f:
        data = json.load(f)

    node_pairs = data.get("node_pairs", {})

    sorted_pairs = sorted(
        node_pairs.items(),
        key=lambda x: x[1].get("weighted_count", 0),
        reverse=True
    )[:TOP_N]

    hot_pairs = {
        "updated": data.get("updated", ""),
        "source_total_pairs": data.get("total_pairs", 0),
        "top_n": TOP_N,
        "pairs": []
    }

    for pair_key, pair_data in sorted_pairs:
        nodes = pair_key.split("::")
        hot_pairs["pairs"].append({
            "pair": pair_key,
            "nodes": nodes,
            "weight": round(pair_data["weighted_count"], 2),
            "raw_count": pair_data["count"],
            "last_seen": pair_data["last_seen"]
        })

    from lib.cache_writer import atomic_write_json
    atomic_write_json(OUTPUT_FILE, hot_pairs, indent=2)

    print(f"Wrote {len(hot_pairs['pairs'])} hot pairs to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
