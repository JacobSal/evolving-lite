# PORT-MANIFEST - Self-* Organism Port (Phase 0 Audit)

**Date**: 2026-06-10
**Status**: Phase 0 complete - awaiting maintainer review before Phase 1
**Scope**: per-component coupling verdicts for porting the complete self-* machinery
(delegation, cognitive-fitness, AutoEvolve v2, steward, verifier-spine, security,
autonomy layer + substrate) from the upstream private system into evolving-lite.

Coupling classes: `path-only` (trivial path/env genericization) | `taxonomy`
(upstream naming substitutable by a generic set) | `data-semantic` (meaningless
without upstream private data - drop or redesign) | `Kairn-API` (calls the Kairn
engine; mechanism noted).

Verdicts: `genericize` (port with path/taxonomy cleanup) | `adapter` (port behind a
config/injection seam) | `extend-lite` (lite already ships a counterpart; extend it)
| `drop` (do not ship) | `cold-data-schema` (ship empty file with schema only).

Effort: S < 1h | M 1-4h | L > 4h per component (genericize + test + review).

---

## 1. Delegation apparatus

| component | coupling | verdict | effort | kairn | lite counterpart | notes |
|---|---|---|---|---|---|---|
| delegation-enforcer (2363 LOC) | taxonomy | extend-lite | L | file-queue (experience writes only) | YES (240-LOC stripped version) | Core scoring engine is generic. Strip: plugin-agent routing, SITUATION coordination block, upstream fitness V2 pipeline -> re-add fitness lookup as Phase 2 consumer. Lite's existing version proves the reduction works. |
| delegation-config.json (937 lines) | taxonomy | extend-lite | M | none | YES (flat generic schema) | Generic mechanism keys (effort_routing, thresholds, keyword_to_type, mutation_rules incl. v2_tuning_enabled + locks) port; 7 third-party-plugin agent entries and personal task taxonomy get replaced by lite's generic task set. |
| subagent-router (1427 LOC) | taxonomy | genericize | M | none | NO | SubagentStop fitness writer = the loop's telemetry leg. Category folder names remappable; imports sanitizer (ports together). |
| delegation-outcome-tracker (651 LOC) | path-only | genericize | S | none | NO | Generic schema (was_delegated, task_type, score). Remove upstream cutoff-date filter constant. |
| effort-inheritance-injector (366 LOC) | path-only | genericize | S | none | NO | Reads /tmp context file written by enforcer; pure convention. |
| trait-combo-lookup lib (99 LOC) | taxonomy | adapter | S | none | NO | Mechanism generic; trait taxonomy file becomes a lite-shipped generic taxonomy. |
| detection-index + regenerator | path-only | extend-lite | S | none | YES | Auto-generated from lite's own commands/skills; regenerator script ports as-is. |
| feature-flags.json | path-only | cold-data-schema | S | none | NO | Ship flag mechanism with empty/default flags; strip upstream audit-trail notes. |
| hook_telemetry lib (315 LOC) | path-only | genericize | S | none | NO | Root-finder already supports plugin layout. Verbatim copy candidate. |
| personality files (6 md) | taxonomy | genericize | S | none | NO | Generic behavioral prose; ship as-is. |

## 2. Cognitive-fitness + AutoEvolve v2

| component | coupling | verdict | effort | kairn | lite counterpart | notes |
|---|---|---|---|---|---|---|
| recalc-fitness (731 LOC) | taxonomy | genericize | M | none | NO | EMA core (asymmetric alpha_down>alpha_up, Muller-ratchet floor, MVP N=8 at a code constant, cold-start N=5) is 100% generic. Extract lens/trait/task-type default tables into injectable config; expose N thresholds as config keys. |
| autoevolve config.json | taxonomy (+1 data-semantic target) | adapter | S | none | NO | Drop the upstream domain-specific diagnostic target entirely. 4-key target schema (target_file, test_cases, scorer, safety) is the lite schema. |
| autoevolve-scorer (1232 LOC) | taxonomy (one function data-semantic) | genericize | M | none | NO | Drop the domain-specific scorer function (~115 LOC). update_baseline ratchet + record_rejected_mutation + 3 infra scorers port. **SC-G(ii) deterministic no-regression gate hooks here**: update_baseline already computes `improved`; lite adds a non-bypassable wrapper that refuses to persist/commit when improved=false (upstream relies on agent-prompt discipline only - lite ships the code gate as reference impl). |
| v2_runner_helpers (264 LOC) | taxonomy | genericize | S | none | NO | Habituation CRUD + decay generic; paths via config. |
| autoevolve-optimizer agent (208 lines) | taxonomy | genericize | M | none | NO | Mutate-score-revert loop generic; wire the deterministic persist gate into its commit step. |
| baselines.json | cold-data | cold-data-schema | S | none | NO | Ship empty with schema; keys injected per target. |
| test-cases/*.json | taxonomy | genericize | S | none | NO | Rebuild fixtures against lite's own command/route/task sets; drop domain-specific + disabled fixtures. |
| metacognitive-synthesizer (324 LOC) + health cache + orchestrator rule | taxonomy | genericize | M | none | partial (health-monitor agent stub) | Hint-type schema is the value; stale skip-list + paths become config. |
| lens-fitness-drainer (344 LOC) | taxonomy | genericize | S | none | NO | Drain pattern (marker -> JSONL -> unlink) generic; lens names flow as strings from the producer. |
| habituation cache | taxonomy keys | cold-data-schema | S | none | NO | Ship empty. |
| run-recurring-tasks (434 LOC) + checker hook | path-only | genericize | S | none | NO | Generic subprocess scheduler; the recalc schedule is data-level. Replaces launchd for periodic work (SessionStart-triggered). |

### AutoEvolve per-target default map (v2_tuning_enabled)

Evidence basis: upstream baselines history (153 entries) + recorded decisions.

| target | upstream evidence | lite default | rationale |
|---|---|---|---|
| detection-index | +0.28 cumulative improvement; one -0.12 dip recovered; later saturated | **ON** | Real headroom on a fresh install (cold start far from saturation); guards hold fire below N=8 |
| context-router | +0.55 improvement, zero regressions ever | **ON** | Cleanest improvement record |
| delegation-config | one -0.0468 regression that persisted across 2 measurement points before recovery | **OFF** | Demonstrated regression risk + the revert was agent-discipline-dependent; user may opt in after the deterministic gate proves itself |
| (upstream domain scorer) | n/a | **DROPPED** | data-semantic, no generic analogue |

ALL targets get: (i) MVP sample threshold N=8 before any mutation, (ii) the
deterministic no-regression persist gate (auto-revert below baseline), (iii) the
rejected-mutation log, (iv) one-step global off-switch `v2_tuning_enabled: false`.
The autonomy layer (`/autonom` loop) is separate and ships DEFAULT-OFF.

## 3. Steward apparatus

| component | coupling | verdict | effort | kairn | lite counterpart | notes |
|---|---|---|---|---|---|---|
| steward-checker hook (709 LOC) | data-semantic -> adapter | genericize | M | none | NO | Parallel-session + false-completion branches generic once the completion-evidence vocabulary is a configurable keyword list; plan-rot branch needs lite's memory-index contract. |
| checks/wiedervorlage (715 LOC) | data-semantic -> adapter | adapter | L | none | NO | Rename concept to "scheduled follow-up"; date-marker keyword configurable. CC-project-dir derivation is actually generic (computed from repo root) - works on any machine. Fail-open: empty sources -> zero findings. |
| checks/audit (295 LOC) | path-only | adapter | S | none | NO | COLD-BASELINE FIX REQUIRED: "no audit reports found" fires on every fresh install -> add never-audited-is-ok default. Audit command name becomes config. |
| checks/retirement (975 LOC) | data-semantic | adapter | M | none | NO | Externalize CRITICAL_ALLOWLIST to config; inspector-DB session-count source becomes optional (absent -> threshold unmet -> suppressed, safe); uninstalled->90d check needs an age-grace default for fresh repos. |
| checks/common (270 LOC) | path-only | genericize | S | none | NO | Rename the maintainer-decision field name. |
| steward_actuator (893 LOC) | path-only (spine import is internal) | genericize | L | none | NO | Imports spine.is_spine_path (ships in Phase 5 - ordering dependency, fail-closed if missing is correct behavior). False-positive guard ports. Autonomy classification module-name strings -> config. |
| steward-self-heal (153 LOC) | path-only | adapter | S | none | NO | launchd -> SessionStart-triggered + documented cron snippet (no plist ships). |
| steward-trend (232 LOC) / steward-reaper (444 LOC) | path-only | genericize | S | none | NO | Fully portable. |
| recurring-task-completer (420 LOC) | data-semantic -> adapter | adapter | M | none | NO | Depends on memory-projects schema; lite defines a minimal recurring-tasks schema. |
| /steward command | path-only | genericize | S | none | NO | Relative paths already. |
| desk-aggregator (767 LOC) + /desk + badge | data-semantic (2 of 4 sources) | adapter | M | none (reads ledgers as files) | NO | Ship with steward-findings + steward-actions sources; Kairn-pipeline sources optional (missing file -> skip). |
| steward ledgers (6 files) | cold-data | cold-data-schema | S | none | partial (_inbox exists) | Absent -> all readers fail-open. |
| integration-matrix-checker (473 LOC) | data-semantic | adapter | M | none | NO | Mechanism (mtime cross-check) generic; check groups rewritten against lite's own registration points. |

Cold-baseline verdict: with the audit.py fix + retirement age-grace + configurable
completion-vocabulary, a fresh repo emits ZERO false findings (Phase 4 gate test).

## 4. Verifier-spine + autonomy + security

| component | coupling | verdict | effort | kairn | lite counterpart | notes |
|---|---|---|---|---|---|---|
| verifier/spine.py (87 LOC) | taxonomy | genericize | S | none | NO | Pure regex; SPINE_PATH_PATTERNS becomes DEFAULT + caller-supplied list with lite's own spine set. |
| verifier/stop_gate.py (320 LOC) | taxonomy | genericize | S | none | NO | EPTEvidence + check_stop_gate generic. Trigger-word list injectable (ships English defaults + documented extension for other languages); template comment de-personalized. |
| verifier/calibration.py (335 LOC) | data-semantic (corpus runner) | adapter | M | none | NO | Metric functions (brier, over-refusal) port; corpus runner = bring-your-own-corpus interface; ledger path passed explicitly. |
| verifier/llm_judge.py (340 LOC) | data-semantic (judge assets) | adapter | M | none | NO | Ollama path ships as default judge; personal CLI-tool adapters dropped; register_asset() plugin seam for user models. |
| verifier/deterministic.py (267) + risk_classifier.py (180) + __init__ | path-only / taxonomy | genericize | S | none | NO | deterministic.py copies verbatim; risk patterns split base-set + extras; import prefix flattened. |
| forced-verify-stop-gate hook (224 LOC) | path-only | genericize | M | none | NO | Lease-absent -> observe-only is the correct lite default (= autonomy OFF). Blocking activates only with a lease (documented). |
| autonom/lease.py (351 LOC) | path-only | genericize | S | none | NO | Functions take lease_path param already; POSIX flock with graceful degrade. |
| /autonom skill (414 lines) | data-semantic -> adapter | adapter | L | MCP (one action type) | NO | Ships DEFAULT-OFF (present, not trigger-registered; explicit documented opt-in flag). Generic loop contract (claim-lease -> governor -> drain -> stop-gate -> release) ports; action-type patterns rebuilt for lite's queues; Kairn-MCP action degrades to DEFER without Kairn. |
| autonomy-classifier doc (234 lines) | cold-data-schema | genericize | S | none | NO | 3-class taxonomy (AUTONOMOUS/SUPERVISED/INTERACTIVE) fully portable; translate prose to English; user-profile ref becomes generic placeholder. |
| security-tier-check (281 LOC upstream) | path-only | extend-lite | M | none | YES (89-LOC version) | Merge back: allowlist mechanism + injection-attempt ledger + richer logging. |
| sanitizer.py (349 LOC) | path-only | genericize | S | none | NO | 14 generic injection regexes; zero internal coupling. Patterns reviewed pre-publish (a redaction list can itself leak - none of these do). |
| security-tiers.json | none | already-in-lite | - | none | YES (identical) | Confirmed byte-identical. |
| content-scanner hook | path-only | genericize | S | none | NO | Generic sensitive-data Read scanner. |

## 5. Kairn-coupled set + call mechanism (F2 RESOLVED)

**Mechanism census** (code components): file-queue 4 | CLI subprocess 4 | MCP-instruction
injection 2 | direct sqlite read 1 | indirect file-queue 2 | none-after-all 7.

**Install story (single, documented in README + checked by the Doctor):**
`pip install kairn-ai` provides BOTH surfaces the port needs:
1. **CLI** (`kairn` on PATH: learn/add/context/recall/query/doctor/init/...) - used by
   drain scripts + thinking-recall subprocess calls.
2. **MCP server** (`python -m kairn.server`, 21 kn_* tools) - registered in the user's
   Claude Code MCP config; used by LLM-facing rules/skills.
Workspace: `kairn init` -> repo-local `_brain/` (gitignored). Doctor Kairn-link check =
(a) `which kairn` + `kairn doctor` round-trip, (b) synthetic learn->recall round-trip,
(c) MCP registration detected (yellow if CLI-only).

| component | mechanism | verdict | effort | notes |
|---|---|---|---|---|
| kairn_drain (~950 LOC) | CLI (`kairn learn`, `kairn promote-pending`) | adapter | S | CLI bin already configurable; binary-absent -> clean no-op exit. |
| kairn-sync-staging (~973 LOC) | file-queue | genericize | S | NAMESPACE_MAP -> config; queue works Kairn-less (drain just never fires). |
| kairn-sync-enforcer (~658 LOC) | drain-trigger + MCP injection | adapter | M | Keep drain trigger; flag-guard the MCP instruction block. |
| thinking-recall (~1400 LOC upstream) | CLI subprocess (cached) | extend-lite | M | Lite has a file-based version; upstream adds Kairn CLI context with 500ms timeout + automatic fallback to file path when binary absent. Merge. |
| correction-detector (~701 LOC upstream) | file-queue | extend-lite | S | Experience-creation core already in lite; add conditional queue write. |
| archival/{experiences,consolidation,distillation,reflect} | none / file-queue | genericize | M | experiences+access-tracker have zero Kairn coupling; consolidation queue write conditional; distillation+reflect are the kn_learn feeders (queue-based). |
| experience-access-tracker (141 LOC) | none | genericize | S | Pure file ops. |
| kairn-first-enforcer (255 LOC) | MCP injection | genericize | S | Ships WITH lite (Kairn is required): enforces query-before-edit; degrades to no-op if MCP absent (Doctor flags yellow). |
| kairn-call-tracker (102 LOC) | none (watches MCP call names) | genericize | S | Ships: feeds kairn-first suppression. No-op without MCP. |
| kairn-drain-freshness-scanner | none (reads drain stats) | genericize | S | Ship with binary-absent guard (silent no-op). |
| kairn_promotion_observer (~250 LOC) | direct sqlite (schema-coupled) | adapter | M | Guard: only runs when _brain/kairn.db exists; pin to engine schema version; degrade silently. |
| drain-artifact-registration-queue | CLI (`kairn add`) - HARDCODED ABSOLUTE BIN PATH upstream | genericize | S | **Highest-priority single fix**: resolve binary via `which`/env, never an absolute personal path. |
| artifact_registration lib (~1023 LOC) + enforcer hook | file-queue | adapter | L | ARS core (locked upsert, dedup, latency ledger) portable; _CLASSIFY_RULES rewritten for lite's dir layout (config-loaded, not hardcoded). |
| rebuild-experience-index | none | genericize | S | Utility. |
| graph-orphan-surface (99 LOC) | none | genericize | S | SessionStart graph hygiene. |

## 6. Substrate (graph-compute + telemetry + libs)

| component | coupling | verdict | effort | kairn | lite counterpart | notes |
|---|---|---|---|---|---|---|
| auto-edges.py (362) / auto-routes.py (235) | path-only + schema | genericize | M | none | NO | **Schema fix required**: lite's context-router uses `primary_nodes`; upstream writer uses `primary`/`secondary` - normalize before port (silent-corruption risk otherwise). |
| compute-centrality.py (327) | path-only | genericize | M | none | NO | Needs `networkx` (the port's only third-party pip dep). |
| compute-hot-pairs (64) / coactivation-aggregator (180) / synthesis-detector (340) / generate-core-view | path-only | genericize | S-M | none | NO | Pure graph pipeline; builds from empty caches on first run. |
| locked_json_rmw.py (486) | none | genericize | S | none | NO - critical gap | Verbatim copy. Required by auto-edges/routes (lost-update protection). POSIX-only (documented). |
| cache_writer.py (241) / lock_telemetry.py (193) | none | genericize | S | none | NO | Verbatim; lock_telemetry optional (fail-open lazy import). |
| post-tool-tracker (875 LOC, 5 modules) | mixed | adapter | L | none | YES (usage-tracker = module 1) | Port modules 1 (usage) + 3 (findings-exchange); drop journal/system-mapper/deferral-tic (personal-phrase list). |
| usage-tracker (342 upstream) | path-only | extend-lite | S | none | YES | Add buffer + builtin-name guard + lock to lite's version. |
| session_attribution.py (229) | none | genericize | S | none | NO | Verbatim. |
| hook wiring | n/a | adapter | M | none | YES (hooks.json, 6 events) | Lite's `hooks.json` + `${CLAUDE_PLUGIN_ROOT}` is the portable form (never assume a single settings.json - two-settings quirk honored). Full organism adds registrations within existing events + SubagentStop + Stop legs; no exotic events needed. |
| full-sync.sh (16 phases) | taxonomy | adapter | L | none | NO | Slim port: phases 7-8 (auto-edges/routes) + 16 (centrality) + detection-index regen as a `lite-sync.sh`; the other phases are upstream-specific. |
| code-index-startup + build-code-index (497) | path-only | genericize | S | none | NO | Generic. |
| qr-scan.py (1922) | taxonomy | adapter | L | none | NO | Core compliance engine ports with REQUIRED_POINTS configurable to lite's registration matrix; manifest generator dropped. |
| graph schemas (knowledge-nodes/edges/index/core) | cold-data | cold-data-schema | S | none | partial | Ship empty skeletons (required by auto-edges first run). |
| task-types / context-router / detection-index / orchestration+delegation config caches | cold-data | extend-lite | S-M | none | YES | Lite's exist; flag that upstream numeric thresholds were behaviorally tuned - lite ships neutral defaults, AutoEvolve re-tunes per user. |

---

## KILL-1 evaluation: **NOT TRIGGERED**

No critical-path component is semantically inseparable from upstream private
taxonomy/data. The only true data-semantic dead-ends are: the domain-specific
AutoEvolve scorer/target/fixtures (dropped - off the loop's critical path), the
inspector-DB retirement source (optional source, degrades safely), personal judge-CLI
adapters in llm_judge (dropped behind a plugin seam), and personal deferral phrases
(dropped). Everything on the loop's critical path (enforcer -> fitness -> autoevolve ->
steward -> spine -> back) is path-only or taxonomy coupling with a generic substitute.

## Effort totals (F7 honest sizing)

~38 genericize-S, ~16 M, ~7 L across ~61 deduplicated in-scope components
(integration components counted once; data files as schema stubs). Confirms a
multi-session program. Phase ordering per the plan DAG: substrate -> fitness ->
autoevolve -> steward -> spine -> Doctor.

## Snapshot-fork decision (R3) - RECORDED

evolving-lite is a **snapshot fork**: frozen at port time, diverges thereafter.
Re-sync from upstream is manual and opportunistic, never automated, never a
maintained parallel. A snapshot tag is set at ship. Upstream improvements flow
back by the same audited-port discipline used here (notably: the deterministic
AutoEvolve no-regression gate is built HERE first as reference implementation).

## Reconciliation summary vs current lite

- **Already present, keep**: security-tiers.json (identical), precompact-extract,
  context-warning, auto-archival, session-summary, health-sentinel, lib/common.py,
  _memory prewarmed experiences, _graph cache configs (schema-reconcile).
- **Extend**: delegation-enforcer, delegation-config, thinking-recall,
  correction-detector, usage-tracker, security-tier-check, detection-index.
- **Port new**: everything in sections 2-6 marked genericize/adapter (the loop
  machinery: fitness, autoevolve, steward, spine, autonomy, substrate scripts).
- **Drop**: domain-specific scorer+target+fixtures, inspector-DB dependency,
  personal judge adapters, launchd plists (-> SessionStart/cron docs),
  deferral-phrase module, upstream observability stack hooks.
