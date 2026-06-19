#!/usr/bin/env bash
# Evolving Lite - post-clone setup (cross-platform: Linux/macOS + Windows Git Bash).
#
# IMPORTANT: hooks/hooks.json ships with ${CLAUDE_PLUGIN_ROOT} placeholders.
# Claude Code substitutes that token itself for marketplace/plugin installs, so
# this script DOES NOT rewrite the file (an earlier version sed-baked an absolute
# path, which broke portability and fought the plugin loader). We only validate.
#
# Run once after cloning, or any time to re-check health.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_FILE="${PLUGIN_ROOT}/hooks/hooks.json"

echo "Evolving Lite setup"
echo "Plugin root: ${PLUGIN_ROOT}"

if [[ ! -f "$HOOKS_FILE" ]]; then
  echo "ERROR: hooks.json not found at ${HOOKS_FILE}" >&2
  exit 1
fi

# Pick a Python: prefer python3, fall back to python (Windows often ships only
# `python`). -X utf8 forces UTF-8 so cp1252 on Windows never breaks file reads.
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [[ -z "$PY" ]]; then
  echo "ERROR: no python interpreter on PATH (need 3.10+)." >&2
  exit 1
fi

# Validate hooks.json is parseable JSON and still uses the placeholder (i.e. not
# accidentally hardcoded or left with merge-conflict markers).
if ! "$PY" -X utf8 - "$HOOKS_FILE" <<'PY'
import json, sys
p = sys.argv[1]
txt = open(p, encoding="utf-8").read()
if "<<<<<<<" in txt or ">>>>>>>" in txt:
    print("ERROR: hooks.json contains unresolved merge-conflict markers.", file=sys.stderr)
    sys.exit(1)
json.loads(txt)  # raises if invalid
if "${CLAUDE_PLUGIN_ROOT}" not in txt:
    print("WARNING: hooks.json has no ${CLAUDE_PLUGIN_ROOT} placeholder; paths may "
          "be hardcoded and non-portable.", file=sys.stderr)
print("hooks.json: valid JSON, portable placeholders present.")
PY
then
  echo "hooks.json validation FAILED - see message above." >&2
  exit 1
fi

cat <<EOF

Next steps
----------
1. Ensure the plugin is enabled in ~/.claude/settings.json (marketplace install:
   "enabledPlugins": { "evolving-lite@<marketplace>": true }).

2. Kairn is the prerequisite for the memory layer. On Windows, install it into a
   venv (the kairn MCP server is configured to use ./venv/Scripts/kairn.exe):
     python -m venv venv
     ./venv/Scripts/python -m pip install kairn-ai      # Windows
     # or:  ./venv/bin/pip install kairn-ai             # Linux/macOS
   The kairn-link Doctor junction is GREEN once the kairn CLI is reachable
   (MCP server registered, or the venv's Scripts/ on PATH).

EOF

# Run the Self-Star Doctor once (re-runnable any time via /health).
echo "Running the Self-Star Doctor..."
CLAUDE_PLUGIN_ROOT="${PLUGIN_ROOT}" "$PY" -X utf8 "${PLUGIN_ROOT}/scripts/doctor.py" || true
