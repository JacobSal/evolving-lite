# The 7 Junctions

Evolving Lite ships the complete self-improving loop as a set of wired Claude Code
hooks and scripts. The **Self-Star Doctor** (`/health`) verifies each junction with
a synthetic pulse and reports a green/yellow/red board.

This is a **file-level inventory** so you can find each junction in the tree. It is
not an architecture deep-dive - run `/health` to see the live status, and read the
code (every junction is plain Python, stdlib only).

| Junction | What it proves | Key files |
|----------|----------------|-----------|
| **delegation** | A prompt produces a valid delegation-enforcer decision row | `hooks/scripts/delegation-enforcer.py`, `hooks/scripts/delegation-outcome-tracker.py`, `_graph/cache/delegation-config.json` |
| **fitness** | A delegation event flows to a bounded cognitive-fitness score that the enforcer reads back | `scripts/recalc-fitness.py`, `scripts/lib/delegation_outcomes.py`, `_graph/cache/{delegation,trait,lens}-fitness.json`, `_graph/cache/fitness-config.json` |
| **autoevolve** | The optimizer mutates config only on real signal, kill-switches read correctly, and a below-baseline mutation auto-reverts | `scripts/autoevolve-scorer.py`, `_autoevolve/baselines.json`, `_autoevolve/rejected/` |
| **steward** | Maintenance checks emit zero false findings on a clean repo; a planted overdue item is surfaced | `hooks/scripts/steward-checker.py`, `scripts/steward_actuator.py`, `scripts/steward_checks/` |
| **verifier-spine** | The EPT spine resolves and (under autonomy) a markerless completion claim is blocked | `scripts/lib/verifier/spine.py`, `scripts/lib/verifier/stop_gate.py`, `hooks/scripts/forced-verify-stop-gate.py`, `scripts/autonom/lease.py` |
| **security** | The 10-tier bash classifier blocks a known sample and the content-scanner flags a planted secret + injection | `hooks/scripts/security-tier-check.py`, `hooks/security-tiers.json`, `hooks/scripts/content-scanner.py`, `hooks/scripts/sanitizer.py`, `_memory/security/allowlist.json` |
| **kairn-link** | Your Kairn prerequisite (`pip install kairn-ai`) is installed and reachable | external - the user's Kairn install + its MCP server |

## The substrate underneath

The loop eats data produced by a substrate layer that runs on Claude Code events:

- **Graph compute** (`scripts/graph/`): coactivation, hot-pairs, auto-edges, auto-routes, centrality, core-view.
- **Artifact registration** (`scripts/lib/artifact_registration.py` + `hooks/scripts/artifact-registration-enforcer.py`): every Write registers into the graph/router/detection caches.
- **Telemetry** (`scripts/lib/hook_telemetry.py`, `scripts/lib/cache_writer.py`, `scripts/lib/locked_json_rmw.py`): concurrency-safe writes + hook-invocation ledgers.

## How it all runs

Hooks are registered in `hooks/hooks.json` (no `settings.json` modification). Tiered
activation gates each junction by session count (see the main README). The Doctor
(`scripts/doctor.py`) reuses `scripts/dev/smoke-substrate.sh` to drive a synthetic
pulse through junctions in an isolated scratch copy - it never writes your real data.

## Verify it yourself

```bash
python3 scripts/doctor.py            # the 7-junction board
python3 scripts/doctor.py --json     # machine-readable
bash scripts/dev/smoke-substrate.sh  # the raw substrate smoke (S1-S8)
python3 -m pytest -q                 # the full test suite
```
