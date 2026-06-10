#!/usr/bin/env python3
"""
Auto Context-Router Route Generator v2

Run at SessionStart (or manually). For each unrouted system component, either:
1. Adds it to an existing route (if domain tags overlap with route keywords)
2. Creates a new auto-route (if no existing route matches)

All system component types are routable (not just patterns/learnings).
Manual (primary) route entries are never touched - only secondary. Curated
routes that use the human-edited `primary_nodes` (file-path) key coexist
untouched; this script only manages the node-id `primary`/`secondary` keys.

Usage:
    python3 auto-routes.py [--dry-run]
"""

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR.parent))
from lib.plugin_paths import plugin_root  # noqa: E402

PLUGIN_ROOT = plugin_root()
ROUTER_FILE = PLUGIN_ROOT / "_graph" / "cache" / "context-router.json"
NODES_FILE = PLUGIN_ROOT / "_graph" / "knowledge-nodes.json"

# Shared locked-write discipline (flock + in-place RMW): context-router.json
# is a multi-writer target across concurrent sessions.
from lib.locked_json_rmw import locked_write_remerge  # noqa: E402

# All system component types are routable
ROUTABLE_TYPES = {
    "command", "agent", "skill", "hook", "rule", "script",
    "template", "blueprint", "scenario", "reference", "tool",
    "config", "module", "package",
}

# Types that don't benefit from individual routes (if no existing route matches, skip)
SKIP_NEW_ROUTE_TYPES = {"config", "module", "package", "tool"}

# Generic stopwords to exclude from route keywords
STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "are", "was",
    "been", "have", "has", "will", "can", "not", "but", "all", "any",
    "each", "every", "more", "most", "other", "some", "such", "than",
    "too", "very", "just", "about", "into", "over", "after", "before",
    "between", "through", "during", "without", "pattern", "system",
    "how", "what", "when", "why", "where", "which", "who",
}

# Minimum keyword overlap to match a node to an existing route
MIN_OVERLAP = 2


def load_json(path: Path) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error loading {path}: {e}", file=sys.stderr)
        sys.exit(1)


def extract_keywords(node: dict) -> list:
    """Extract meaningful keywords from a node's domain tags and name."""
    keywords = set()

    # Domain tags (best source)
    for tag in node.get("domain", []):
        tag_lower = tag.lower().strip()
        if tag_lower and tag_lower not in STOPWORDS and len(tag_lower) > 2:
            keywords.add(tag_lower)

    # Name words (fallback)
    name = node.get("name", "")
    name_words = re.findall(r'[a-zA-Z]{3,}', name.lower())
    for word in name_words:
        if word not in STOPWORDS and len(word) > 2:
            keywords.add(word)

    # ID words (additional signal)
    node_id = node.get("id", "")
    id_parts = node_id.split("-")[1:]  # skip type prefix
    for part in id_parts:
        if part not in STOPWORDS and len(part) > 2:
            keywords.add(part.lower())

    # Prioritize domain tags over name/ID words
    domain_set = {t.lower().strip() for t in node.get("domain", [])}
    domain_kws = sorted(k for k in keywords if k in domain_set)
    other_kws = sorted(k for k in keywords if k not in domain_set)
    return (domain_kws + other_kws)[:10]


def build_route_keyword_index(routes: dict) -> dict:
    """Build route_name → set(keywords) index for fast matching."""
    index = {}
    for route_name, route in routes.items():
        kws = set()
        for kw in route.get("keywords", []):
            # Split multi-word keywords: "create agent" → {"create", "agent"}
            for word in kw.lower().split():
                if len(word) > 2 and word not in STOPWORDS:
                    kws.add(word)
        index[route_name] = kws
    return index


def find_best_route(node_keywords: list, route_kw_index: dict) -> str:
    """Find the existing route with the highest keyword overlap (Jaccard-normalized)."""
    best_route = None
    best_score = 0.0
    node_kw_set = set(node_keywords)

    for route_name, route_kws in route_kw_index.items():
        if not route_kws:
            continue
        overlap = len(node_kw_set & route_kws)
        if overlap < MIN_OVERLAP:
            continue
        # Jaccard similarity favors smaller, more specific routes
        jaccard = overlap / len(node_kw_set | route_kws)
        if jaccard > best_score:
            best_score = jaccard
            best_route = route_name

    return best_route


def generate_routes(dry_run: bool = False) -> dict:
    """Generate context-router routes for unrouted system components."""
    nodes_data = load_json(NODES_FILE)
    all_nodes = nodes_data.get("nodes", [])

    def _assign(routes, mutate):
        """Assign unrouted nodes to existing/new routes. Mutates ``routes`` in
        place only when ``mutate``. Returns (added_to_existing, new_routes).
        Idempotent: already-routed nodes + existing auto-<id> routes are skipped,
        so re-running on a fresh read adds nothing already present."""
        routed_nodes = set()
        for route in routes.values():
            for node_id in route.get("primary", []) + route.get("secondary", []):
                routed_nodes.add(node_id)
        route_kw_index = build_route_keyword_index(routes)
        added_to_existing = 0
        new_routes = 0
        for node in all_nodes:
            if node.get("type") not in ROUTABLE_TYPES:
                continue
            if node.get("id") in routed_nodes:
                continue
            keywords = extract_keywords(node)
            if not keywords:
                continue
            best_route = find_best_route(keywords, route_kw_index)
            if best_route:
                if mutate:
                    routes[best_route].setdefault("secondary", []).append(node["id"])
                routed_nodes.add(node["id"])
                added_to_existing += 1
            elif node.get("type") not in SKIP_NEW_ROUTE_TYPES and len(keywords) >= 2:
                route_name = f"auto-{node['id']}"
                if route_name in routes:
                    continue
                if mutate:
                    routes[route_name] = {
                        "keywords": keywords,
                        "primary": [node["id"]],
                        "secondary": [],
                        "auto_generated": True,
                    }
                # Update the in-memory match index in BOTH modes so a later node
                # can match this just-created route - keeps the dry-run count
                # consistent with the live (mutate=True) outcome (RC finding 1).
                route_kw_index[route_name] = set(keywords)
                routed_nodes.add(node["id"])
                new_routes += 1
        return added_to_existing, new_routes

    if dry_run:
        routes = load_json(ROUTER_FILE).get("routes", {})
        added_to_existing, new_routes = _assign(routes, mutate=False)
        total_added = added_to_existing + new_routes
        print(f"Auto-routes: {total_added} new routes "
              f"({added_to_existing} to existing, {new_routes} new) "
              f"(total: {len(routes)}) (dry-run)")
        return {"new_routes": total_added, "total_routes": len(routes)}

    # Apply path: re-read context-router.json FRESH under an exclusive lock and
    # re-assign against the fresh route set, then write IN PLACE (shared
    # locked_json_rmw discipline). Re-applying the idempotent pass loses nothing.
    counts = {"added": 0, "new": 0, "total": 0}

    def _apply(fresh):
        routes = fresh.setdefault("routes", {})
        added_to_existing, new_routes = _assign(routes, mutate=True)
        counts["added"], counts["new"] = added_to_existing, new_routes
        counts["total"] = len(routes)
        return (added_to_existing + new_routes) > 0

    changed = locked_write_remerge(ROUTER_FILE, _apply)
    total_added = counts["added"] + counts["new"]
    status = "written" if changed else "no-op (lock-timeout or nothing new)"
    print(f"Auto-routes: {total_added} new routes "
          f"({counts['added']} to existing, {counts['new']} new) "
          f"(total: {counts['total']}) ({status})")

    return {"new_routes": total_added, "total_routes": counts["total"]}


def main():
    dry_run = "--dry-run" in sys.argv
    generate_routes(dry_run=dry_run)


if __name__ == "__main__":
    main()
