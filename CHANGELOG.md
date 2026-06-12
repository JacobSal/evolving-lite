# Changelog

## Unreleased - Self-* organism

The complete self-improving loop, ported and genericized from the production Evolving
system. Cold data: every ledger starts empty and builds from your own sessions.

### Added
- **Self-Star Doctor** (`scripts/doctor.py`, `/health`): install-time health assistant
  with a green/yellow/red board across 7 junctions (delegation, fitness, autoevolve,
  steward, verifier-spine, security, kairn-link). Conservative create-only heal
  (consent-gated on `settings.json`, never overwrites/deletes). Runs its synthetic pulse
  in an isolated scratch copy - never touches your real data. Dual trigger: a guarded
  once-per-install SessionStart check + the re-runnable `/health`.
- **Self-* loop**: cognitive-fitness scoring, AutoEvolve config self-tuning (on by
  default with sparse-data guards + a no-regression auto-revert; one-step off-switch
  documented in the README), a steward maintenance engine, and an EPT verifier-spine
  with an opt-in autonomy layer (off by default).
- **Security apparatus**: a content-scanner (prompt-injection + planted-secret detection
  on fetched content), an agent-output sanitizer, and an injection-attempt ledger + a
  user-merge allowlist on the existing 10-tier bash classifier.
- **Substrate**: graph-compute pipeline, artifact registration, concurrency-safe
  telemetry writers.
- `docs/JUNCTIONS.md`: file-level inventory of all 7 junctions.

### Requires
- [Kairn](https://github.com/primeline-ai/kairn) (`pip install kairn-ai`) as a prerequisite
  for the memory layer. The Doctor detects and guides if it is absent.

## v1.0.0 (2026-03-17)

Initial release.

### Features
- 4 feedback loops: LEARN, HEAL, EVOLVE, CONTEXT
- 3-tier progressive activation (Safety -> Learning -> Deep)
- 15 slash commands
- 5 specialized agents
- 2 auto-activating skills (system-boot, evolution-guide)
- 10 hook scripts (4 Tier 1, 3 Tier 2, 3 Tier 3)
- 10-tier bash security system
- Hook health sentinel with per-hook verification
- 20 pre-warmed experiences
- 25 context routes
- 12 curated patterns
- 5 behavioral rules
- Session counter with double-increment guard
- Evolution changelog (/evolution command)
- Version check (/evolving-update command)

### Architecture
- Claude Code plugin (hooks/hooks.json, no settings.json modification)
- Portable paths via setup.sh (replaces ${CLAUDE_PLUGIN_ROOT} placeholders with absolute paths)
- common.py shared utilities (sentinel, session counter, safe JSON, experience creation)
- Fail-open hooks (never block tool execution)
- Bash 3.2 compatible shell scripts
- Python 3.10+ stdlib only (no pip dependencies)
