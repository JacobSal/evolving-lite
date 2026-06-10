"""Shared plugin-root resolution for substrate scripts and hooks.

Data (graph caches, ledgers, memory) lives in the PLUGIN root, not the
user's project: resolution order is CLAUDE_PLUGIN_ROOT env (set by Claude
Code when invoking plugin hooks) > walk-up to .claude-plugin/plugin.json
(manual runs inside the repo) > CLAUDE_PROJECT_DIR env (vendored installs
without a plugin manifest) > file-relative fallback.
"""
from __future__ import annotations

import os
from pathlib import Path


def plugin_root() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".claude-plugin" / "plugin.json").exists():
            return parent
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    return here.parents[2]  # scripts/lib/plugin_paths.py -> repo root


__all__ = ["plugin_root"]
