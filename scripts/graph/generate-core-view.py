#!/usr/bin/env python3
"""Generate core-nodes.json as a filtered view of knowledge-nodes.json.

core-nodes.json is referenced by 20+ files across the codebase.
This script keeps it in sync as a generated artifact.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR.parent))
from lib.plugin_paths import plugin_root  # noqa: E402

PLUGIN_ROOT = plugin_root()
KB_PATH = PLUGIN_ROOT / "_graph" / "knowledge-nodes.json"
CORE_PATH = PLUGIN_ROOT / "_graph" / "core-nodes.json"

# core-nodes.json is a SHARED graph file; route the write through the locked
# in-place helper (lock + truncate + fsync), the same discipline as every
# other graph writer.
from lib.locked_json_rmw import _locked_overwrite_raw  # noqa: E402


def main():
    if not KB_PATH.exists():
        print(f"ERROR: {KB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    with open(KB_PATH, encoding="utf-8") as f:
        kb = json.load(f)

    core_nodes = [n for n in kb["nodes"] if n.get("partition") == "core"]

    core_data = {
        "metadata": {
            "generated_from": "knowledge-nodes.json",
            "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "total_count": len(core_nodes),
            "note": "AUTO-GENERATED. Edit knowledge-nodes.json instead."
        },
        "nodes": core_nodes
    }

    payload = json.dumps(core_data, indent=2, ensure_ascii=False)
    _locked_overwrite_raw(CORE_PATH, payload)

    print(f"Generated {CORE_PATH.name}: {len(core_nodes)} nodes (from {len(kb['nodes'])} total)")


if __name__ == "__main__":
    main()
