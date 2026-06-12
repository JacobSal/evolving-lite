---
description: Run the Self-Star Doctor - a green/yellow/red health board across all 7 junctions of the self-* loop
---

Run the native Self-Star Doctor and show the user the junction board.

## Process

1. Run the Doctor:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"
```

2. Show the user the board it prints. It covers 7 junctions:
   - **delegation** - synthetic prompt produces a valid delegation decision row
   - **fitness** - a synthetic event flows to a bounded cognitive-fitness score
   - **autoevolve** - the optimizer is present, kill-switches read correctly, one scored mutation cycle runs
   - **steward** - the maintenance checks emit zero false findings on a clean repo
   - **verifier-spine** - the EPT spine resolves and a markerless completion claim is blocked under autonomy
   - **security** - the tier-check classifies a known command and the content-scanner flags a planted secret + injection
   - **kairn-link** - the user's Kairn prerequisite is installed and reachable

3. **Interpret for the user:**
   - **GREEN** = healthy and proven by a synthetic pulse.
   - **YELLOW** = present but degraded (e.g. Kairn installed but its MCP server not yet registered). Tell them the one concrete step the `detail` field names.
   - **RED** = absent or throwing. The most common RED is **kairn-link** on a fresh machine: tell them to run `pip install kairn-ai` (Kairn is a required prerequisite) and register its MCP server in their Claude Code config.

## Notes

- The Doctor runs its synthetic loop pulse in an **isolated scratch copy** of the plugin. It never writes your real ledgers, so running `/health` as often as you like is safe.
- The Doctor heals conservatively: it creates only missing empty scaffolding (cache dirs, ledgers, `.gitkeep`). It will **ask before** touching your `settings.json` and never overwrites or deletes anything.
- For machine-readable output: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --json`.
- The same Doctor runs once automatically on your first session (a quick wiring + preflight check); `/health` is the full, re-runnable version.
