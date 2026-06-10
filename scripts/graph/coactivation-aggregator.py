#!/usr/bin/env python3
"""
Co-Activation Aggregator — Computes pairwise node co-activation from thinking-recall.jsonl.

Reads all entries with `nodes_loaded` field, computes pairwise co-activation counts,
applies exponential decay (half-life 60 days), writes to _graph/cache/coactivation.json.

Idempotent: processes all data each run. Safe to run at any time.

Usage:
  python3 scripts/coactivation-aggregator.py           # Full run
  python3 scripts/coactivation-aggregator.py --dry-run  # Validate without writing

Can be registered as SessionStart hook or run as recurring task.
"""
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR.parent))
from lib.plugin_paths import plugin_root  # noqa: E402

PLUGIN_ROOT = plugin_root()
ANALYTICS_FILE = PLUGIN_ROOT / "_memory" / "analytics" / "thinking-recall.jsonl"
OUTPUT_FILE = PLUGIN_ROOT / "_graph" / "cache" / "coactivation.json"

HALF_LIFE_DAYS = 60
DECAY_LAMBDA = math.log(2) / HALF_LIFE_DAYS


def parse_events():
    """Parse thinking-recall.jsonl for events with nodes_loaded."""
    if not ANALYTICS_FILE.exists():
        return []

    events = []
    with open(ANALYTICS_FILE) as f:  # Let open() exceptions propagate to caller
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            nodes = entry.get("nodes_loaded")
            if not nodes or not isinstance(nodes, list) or len(nodes) < 2:
                continue

            timestamp = entry.get("timestamp", "")
            events.append({
                "nodes": nodes,
                "timestamp": timestamp,
            })

    return events


def compute_coactivation(events):
    """Compute pairwise co-activation counts with decay weighting."""
    now = datetime.now(timezone.utc)
    pair_data = defaultdict(lambda: {"count": 0, "weighted_count": 0.0, "last_seen": ""})

    for event in events:
        nodes = event["nodes"]
        ts_str = event["timestamp"]

        # Parse timestamp for decay calculation
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            ts = now  # If unparseable, treat as current (no decay)

        days_ago = max(0, (now - ts).total_seconds() / 86400)
        decay_weight = math.exp(-DECAY_LAMBDA * days_ago)

        # Generate all unique pairs (order-independent)
        unique_nodes = list(dict.fromkeys(nodes))  # deduplicate, preserve order
        for a, b in combinations(unique_nodes, 2):
            # Canonical ordering: alphabetical
            pair_key = "::".join(sorted([a, b]))
            pair_data[pair_key]["count"] += 1
            pair_data[pair_key]["weighted_count"] += decay_weight
            if ts_str > pair_data[pair_key]["last_seen"]:
                pair_data[pair_key]["last_seen"] = ts_str

    return dict(pair_data)


def build_output(pair_data):
    """Build the output JSON structure."""
    # Filter out pairs with negligible weighted count
    filtered = {}
    for pair_key, data in pair_data.items():
        if data["weighted_count"] >= 0.01:  # Threshold: ~7 half-lives
            filtered[pair_key] = {
                "count": data["count"],
                "weighted_count": round(data["weighted_count"], 4),
                "last_seen": data["last_seen"],
            }

    # Sort by weighted_count descending
    sorted_pairs = dict(
        sorted(filtered.items(), key=lambda x: x[1]["weighted_count"], reverse=True)
    )

    return {
        "schema_version": "1.0",
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "half_life_days": HALF_LIFE_DAYS,
        "total_pairs": len(sorted_pairs),
        "total_events_processed": 0,  # Set by caller
        "node_pairs": sorted_pairs,
    }


def main():
    dry_run = "--dry-run" in sys.argv

    events = parse_events()
    print(f"Events with nodes_loaded: {len(events)}")

    if not events:
        if dry_run:
            print("DRY RUN: No events to process. Would write empty coactivation.json.")
            # Still produce valid output for gate check
            output = build_output({})
            output["total_events_processed"] = 0
            print(json.dumps(output, indent=2))
            return
        else:
            # Write empty but valid file (cold-start state on a fresh install)
            output = build_output({})
            output["total_events_processed"] = 0
            OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
            from lib.cache_writer import atomic_write_json
            atomic_write_json(OUTPUT_FILE, output, indent=2)
            print(f"Wrote empty coactivation to {OUTPUT_FILE}")
            return

    pair_data = compute_coactivation(events)
    output = build_output(pair_data)
    output["total_events_processed"] = len(events)

    if dry_run:
        print(f"\nDRY RUN: Would write {output['total_pairs']} pairs")
        print(f"Top 5 pairs:")
        for i, (k, v) in enumerate(output["node_pairs"].items()):
            if i >= 5:
                break
            print(f"  {k}: count={v['count']}, weighted={v['weighted_count']}")
        # Output full JSON for validation
        print(f"\nValid JSON output ({len(json.dumps(output))} bytes)")
        return

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    from lib.cache_writer import atomic_write_json
    atomic_write_json(OUTPUT_FILE, output, indent=2, ensure_ascii=False)

    print(f"Wrote {output['total_pairs']} pairs to {OUTPUT_FILE}")
    print(f"Events processed: {len(events)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Fail-open when running as hook: never block session start
        # Print error for debugging but exit cleanly
        print(f"coactivation-aggregator error: {e}", file=sys.stderr)
        sys.exit(0)
