# Project Context

**Language**: markdown
**Project Path**: .

## Project Structure

- **Total Files**: 48
- **Total Functions**: 350
- **Median Cyclomatic**: 78.00
- **Median Cognitive**: 78.00

## Quality Scorecard

- **Overall Health**: 68.3%
- **Maintainability Index**: 70.0
- **Complexity Score**: 50.0
- **Test Coverage**: 65.0%

## Files

### ./_autoevolve/baselines.json


### ./_autoevolve/config.json


### ./_autoevolve/test-cases/context-router.json


### ./_autoevolve/test-cases/detection-index.json


### ./_graph/cache/context-router.json


### ./_graph/cache/delegation-config.json


### ./_graph/cache/detection-index.json


### ./_graph/cache/fitness-config.json


### ./_graph/cache/orchestration-config.json


### ./_graph/cache/steward-config.json


### ./_graph/cache/task-types.json


### ./_graph/edges.json


### ./_graph/knowledge-nodes.json


### ./_memory/experiences/_prewarmed/exp-pw-001.json


### ./_memory/experiences/_prewarmed/exp-pw-002.json


### ./_memory/experiences/_prewarmed/exp-pw-003.json


### ./_memory/experiences/_prewarmed/exp-pw-004.json


### ./_memory/experiences/_prewarmed/exp-pw-005.json


### ./_memory/experiences/_prewarmed/exp-pw-006.json


### ./_memory/experiences/_prewarmed/exp-pw-007.json


### ./_memory/experiences/_prewarmed/exp-pw-008.json


### ./_memory/experiences/_prewarmed/exp-pw-009.json


### ./_memory/experiences/_prewarmed/exp-pw-010.json


### ./_memory/experiences/_prewarmed/exp-pw-011.json


### ./_memory/experiences/_prewarmed/exp-pw-012.json


### ./_memory/experiences/_prewarmed/exp-pw-013.json


### ./_memory/experiences/_prewarmed/exp-pw-014.json


### ./_memory/experiences/_prewarmed/exp-pw-015.json


### ./_memory/experiences/_prewarmed/exp-pw-016.json


### ./_memory/experiences/_prewarmed/exp-pw-017.json


### ./_memory/experiences/_prewarmed/exp-pw-018.json


### ./_memory/experiences/_prewarmed/exp-pw-019.json


### ./_memory/experiences/_prewarmed/exp-pw-020.json


### ./_memory/security/allowlist.json


### ./hooks/hooks.json


### ./hooks/scripts/artifact-registration-enforcer.py

**File Complexity**: 36 | **Functions**: 5

- **Function**: `_plugin_root` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `_install_hard_timeout` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `_handler` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `_read_payload` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `_extract_file_path` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `main` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]

### ./hooks/scripts/auto-archival.py

**File Complexity**: 41 | **Functions**: 4

- **Function**: `should_run` [complexity: 41] [cognitive: 41] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `archive_old_experiences` [complexity: 41] [cognitive: 41] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `archive_old_sessions` [complexity: 41] [cognitive: 41] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 41] [cognitive: 41] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./hooks/scripts/content-scanner.py

**File Complexity**: 104 | **Functions**: 11

- **Function**: `_compile` [complexity: 104] [cognitive: 104] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `detect_code_fences` [complexity: 104] [cognitive: 104] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_in_fence` [complexity: 104] [cognitive: 104] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_in_quote` [complexity: 104] [cognitive: 104] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `scan_text` [complexity: 104] [cognitive: 104] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `actionable` [complexity: 104] [cognitive: 104] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `extract_text` [complexity: 104] [cognitive: 104] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_log` [complexity: 104] [cognitive: 104] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `build_warning` [complexity: 104] [cognitive: 104] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `run_self_tests` [complexity: 104] [cognitive: 104] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 104] [cognitive: 104] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./hooks/scripts/context-warning.sh


### ./hooks/scripts/correction-detector.py

**File Complexity**: 49 | **Functions**: 4

- **Function**: `detect_patterns` [complexity: 49] [cognitive: 49] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `calculate_confidence` [complexity: 49] [cognitive: 49] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `should_create_experience` [complexity: 49] [cognitive: 49] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `main` [complexity: 49] [cognitive: 49] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]

### ./hooks/scripts/delegation-enforcer.py

**File Complexity**: 81 | **Functions**: 9

- **Function**: `extract_keywords` [complexity: 81] [cognitive: 81] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(4)] [tdg: 2.5]
- **Function**: `extract_inline_hint` [complexity: 81] [cognitive: 81] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(4)] [tdg: 2.5]
- **Function**: `is_destructive` [complexity: 81] [cognitive: 81] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(4)] [tdg: 2.5]
- **Function**: `calculate_score` [complexity: 81] [cognitive: 81] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(4)] [tdg: 2.5]
- **Function**: `determine_routing` [complexity: 81] [cognitive: 81] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(4)] [tdg: 2.5]
- **Function**: `lookup_fitness` [complexity: 81] [cognitive: 81] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(4)] [tdg: 2.5]
- **Function**: `format_delegation_message` [complexity: 81] [cognitive: 81] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(4)] [tdg: 2.5]
- **Function**: `write_pending_marker` [complexity: 81] [cognitive: 81] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(4)] [tdg: 2.5]
- **Function**: `main` [complexity: 81] [cognitive: 81] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(4)] [tdg: 2.5]

### ./hooks/scripts/delegation-outcome-tracker.py

**File Complexity**: 123 | **Functions**: 22

- **Struct**: `_NoFcntl` [fields: 0]
- **Function**: `_NoFcntl::flock` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_plugin_root` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_pending_marker_path` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_resolve_session_id` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_read_marker` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_write_marker` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_unlink_marker` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_quality_signal_path` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_quality_signal_mode` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_read_quality_verdict` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_unlink_quality_verdict` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_apply_quality_signal` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_log_invocation` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_append_gap_entry` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_v2_tuning_enabled` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_parse_ts_utc` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_derive_outcome` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_write_fitness_from_gap` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `handle_pre_tool_use` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_marker_age_seconds` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `handle_stop` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_install_timeout` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_bail` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 123] [cognitive: 123] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./hooks/scripts/forced-verify-stop-gate.py

**File Complexity**: 61 | **Functions**: 8

- **Function**: `_allow` [complexity: 61] [cognitive: 61] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_candidate_session_ids` [complexity: 61] [cognitive: 61] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_is_autonomous_session` [complexity: 61] [cognitive: 61] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_read_hook_input` [complexity: 61] [cognitive: 61] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_extract_last_text` [complexity: 61] [cognitive: 61] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_extract_markers` [complexity: 61] [cognitive: 61] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_extract` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_log_observation` [complexity: 61] [cognitive: 61] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 61] [cognitive: 61] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./hooks/scripts/health-sentinel.sh


### ./hooks/scripts/lib/__init__.py

**File Complexity**: 1 | **Functions**: 0


### ./hooks/scripts/lib/common.py

**File Complexity**: 36 | **Functions**: 13

- **Function**: `_resolve_plugin_root` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `write_sentinel` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `get_session_count` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `increment_session_count` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `is_tier_active` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `get_current_tier` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `safe_write_json` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `safe_read_json` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `safe_write_text` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `create_experience` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `log_evolution_event` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `ensure_memory_initialized` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `read_hook_input` [complexity: 36] [cognitive: 36] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]

### ./hooks/scripts/lib/steward_routing.py

**File Complexity**: 25 | **Functions**: 5

- **Function**: `should_run_today` [complexity: 25] [cognitive: 25] [big-o: O(n²)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `read_input_fingerprint` [complexity: 25] [cognitive: 25] [big-o: O(n²)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `cache_is_fresh` [complexity: 25] [cognitive: 25] [big-o: O(n²)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `write_throttle_marker` [complexity: 25] [cognitive: 25] [big-o: O(n²)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `marker_is_old` [complexity: 25] [cognitive: 25] [big-o: O(n²)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]

### ./hooks/scripts/precompact-extract.py

**File Complexity**: 28 | **Functions**: 2

- **Function**: `extract_knowledge` [complexity: 28] [cognitive: 28] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `main` [complexity: 28] [cognitive: 28] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]

### ./hooks/scripts/sanitizer.py

**File Complexity**: 65 | **Functions**: 8

- **Struct**: `PatternMatch` [fields: 0]
- **Struct**: `SanitizationResult` [fields: 0]
- **Function**: `detect_code_fences` [complexity: 65] [cognitive: 65] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_in_code_fence` [complexity: 65] [cognitive: 65] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_in_markdown_quote` [complexity: 65] [cognitive: 65] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `scan_content` [complexity: 65] [cognitive: 65] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `redact_matches` [complexity: 65] [cognitive: 65] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_get_log_path` [complexity: 65] [cognitive: 65] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `log_detection` [complexity: 65] [cognitive: 65] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_rotate_log_if_needed` [complexity: 65] [cognitive: 65] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./hooks/scripts/security-tier-check.py

**File Complexity**: 44 | **Functions**: 6

- **Function**: `load_tiers` [complexity: 44] [cognitive: 44] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `load_allowlist` [complexity: 44] [cognitive: 44] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `log_injection_attempt` [complexity: 44] [cognitive: 44] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `is_allowlisted` [complexity: 44] [cognitive: 44] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `check_command` [complexity: 44] [cognitive: 44] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 44] [cognitive: 44] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./hooks/scripts/session-summary.sh


### ./hooks/scripts/steward-checker.py

**File Complexity**: 150 | **Functions**: 12

- **Struct**: `_NoFcntl` [fields: 0]
- **Function**: `_NoFcntl::flock` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_plugin_root` [complexity: 150] [cognitive: 150] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `run_followup` [complexity: 150] [cognitive: 150] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `run_audit_if_due` [complexity: 150] [cognitive: 150] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `run_retirement_if_due` [complexity: 150] [cognitive: 150] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `run_plan_rot` [complexity: 150] [cognitive: 150] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `scan_false_completions` [complexity: 150] [cognitive: 150] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `scan_parallel_sessions` [complexity: 150] [cognitive: 150] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `write_findings_jsonl` [complexity: 150] [cognitive: 150] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `select_top_n` [complexity: 150] [cognitive: 150] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `build_system_message` [complexity: 150] [cognitive: 150] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `emit_hook_output` [complexity: 150] [cognitive: 150] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 150] [cognitive: 150] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./hooks/scripts/thinking-recall.py

**File Complexity**: 39 | **Functions**: 5

- **Function**: `extract_keywords` [complexity: 39] [cognitive: 39] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `load_experiences` [complexity: 39] [cognitive: 39] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `match_experiences` [complexity: 39] [cognitive: 39] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `format_injection` [complexity: 39] [cognitive: 39] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `main` [complexity: 39] [cognitive: 39] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]

### ./hooks/scripts/usage-tracker.py

**File Complexity**: 19 | **Functions**: 2

- **Function**: `_append_history_event` [complexity: 19] [cognitive: 19] [big-o: O(n²)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 19] [cognitive: 19] [big-o: O(n²)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./hooks/security-tiers.json


### ./scripts/autoevolve-scorer.py

**File Complexity**: 227 | **Functions**: 18

- **Function**: `load_json` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `save_json` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `score_detection_index` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `score_context_router` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `update_baseline` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `get_baseline` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `detect_plateau` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `record_rejected_mutation` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_autoevolve_config` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_global_tuning_enabled` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `count_outcomes` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `evaluate_mutation_gate` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_target_live_path` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_score_config` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `evaluate_persist` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `enforce_persist_gate` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_score_target` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `main` [complexity: 227] [cognitive: 227] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]

### ./scripts/autonom/__init__.py

**File Complexity**: 1 | **Functions**: 0


### ./scripts/autonom/lease.py

**File Complexity**: 64 | **Functions**: 8

- **Struct**: `_NoFcntl` [fields: 0]
- **Function**: `_NoFcntl::flock` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Struct**: `LeaseRefused` [fields: 0]
- **Function**: `LeaseRefused::__init__` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Struct**: `LeaseNotHeld` [fields: 0]
- **Function**: `_acquire_flock` [complexity: 64] [cognitive: 64] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Struct**: `LeaseState` [fields: 0]
- **Function**: `LeaseState::is_stale` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `LeaseState::age_s` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `LeaseState::to_dict` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `LeaseState::from_dict` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `LeaseState::empty` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_read_lease` [complexity: 64] [cognitive: 64] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_write_lease` [complexity: 64] [cognitive: 64] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `claim_lease` [complexity: 64] [cognitive: 64] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `release_lease` [complexity: 64] [cognitive: 64] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `read_lease_state` [complexity: 64] [cognitive: 64] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_default_lease_path` [complexity: 64] [cognitive: 64] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 64] [cognitive: 64] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/dev/clean-room.sh


### ./scripts/dev/leak-scan.py

**File Complexity**: 37 | **Functions**: 7

- **Function**: `_git` [complexity: 37] [cognitive: 37] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `staged_paths` [complexity: 37] [cognitive: 37] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `tracked_paths` [complexity: 37] [cognitive: 37] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `read_index_blob` [complexity: 37] [cognitive: 37] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `scan_text` [complexity: 37] [cognitive: 37] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_scannable` [complexity: 37] [cognitive: 37] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `main` [complexity: 37] [cognitive: 37] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]

### ./scripts/dev/smoke-known-good.sh


### ./scripts/dev/smoke-substrate.sh


### ./scripts/doctor.py

**File Complexity**: 191 | **Functions**: 19

- **Function**: `_plugin_root` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_find_bash` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_run` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `preflight` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_kairn_mcp_registered` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `wiring_verify` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `heal` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_plugin_registered` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_register_plugin` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_make_scratch` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_parse_smoke` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `run_substrate_pulse` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `security_pulse` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_load` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `kairn_pulse` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_smoke_junction_status` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `build_board` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `overall` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `render` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `run` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `main` [complexity: 191] [cognitive: 191] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(3)] [tdg: 2.5]

### ./scripts/graph/auto-edges.py

**File Complexity**: 143 | **Functions**: 7

- **Function**: `load_json` [complexity: 143] [cognitive: 143] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `build_edge_set` [complexity: 143] [cognitive: 143] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `make_edge` [complexity: 143] [cognitive: 143] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `infer_typed_edges` [complexity: 143] [cognitive: 143] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_match_agents` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `infer_related_edges` [complexity: 143] [cognitive: 143] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `generate_edges` [complexity: 143] [cognitive: 143] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_apply` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 143] [cognitive: 143] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/graph/auto-routes.py

**File Complexity**: 69 | **Functions**: 6

- **Function**: `load_json` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `extract_keywords` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `build_route_keyword_index` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `find_best_route` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `generate_routes` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_assign` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_apply` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/graph/coactivation-aggregator.py

**File Complexity**: 45 | **Functions**: 4

- **Function**: `parse_events` [complexity: 45] [cognitive: 45] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `compute_coactivation` [complexity: 45] [cognitive: 45] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `build_output` [complexity: 45] [cognitive: 45] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 45] [cognitive: 45] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/graph/compute-centrality.py

**File Complexity**: 68 | **Functions**: 10

- **Function**: `load_edges` [complexity: 68] [cognitive: 68] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `load_nodes` [complexity: 68] [cognitive: 68] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `load_coactivation` [complexity: 68] [cognitive: 68] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `is_coactivated` [complexity: 68] [cognitive: 68] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `build_graph` [complexity: 68] [cognitive: 68] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `compute_katz` [complexity: 68] [cognitive: 68] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `normalize_scores` [complexity: 68] [cognitive: 68] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `build_output` [complexity: 68] [cognitive: 68] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `validate_output` [complexity: 68] [cognitive: 68] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 68] [cognitive: 68] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/graph/compute-hot-pairs.py

**File Complexity**: 8 | **Functions**: 1

- **Function**: `main` [complexity: 8] [cognitive: 8] [big-o: O(n log n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/graph/generate-core-view.py

**File Complexity**: 6 | **Functions**: 1

- **Function**: `main` [complexity: 6] [cognitive: 6] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/graph/synthesis-detector.py

**File Complexity**: 98 | **Functions**: 11

- **Function**: `load_coactivation` [complexity: 98] [cognitive: 98] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `load_node_names` [complexity: 98] [cognitive: 98] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `build_adjacency` [complexity: 98] [cognitive: 98] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `find_cliques` [complexity: 98] [cognitive: 98] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `are_connected` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `load_existing_candidates` [complexity: 98] [cognitive: 98] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `make_cluster_id` [complexity: 98] [cognitive: 98] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `avg_coactivation` [complexity: 98] [cognitive: 98] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_compute_input_fingerprint` [complexity: 98] [cognitive: 98] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_read_cached_fingerprint` [complexity: 98] [cognitive: 98] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_write_cached_fingerprint` [complexity: 98] [cognitive: 98] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 98] [cognitive: 98] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/lib/__init__.py

**File Complexity**: 1 | **Functions**: 0


### ./scripts/lib/artifact_registration.py

**File Complexity**: 166 | **Functions**: 21

- **Struct**: `RegistrationResult` [fields: 0]
- **Function**: `RegistrationResult::to_dict` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_load_classify_rules` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_normalize_path` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `is_in_scope` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `classify` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `compute_node_id` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `compute_semantic_node_id` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `compute_kairn_name` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `extract_title` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_append_jsonl` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_sanitize_for_fts5` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `enqueue_kairn_add` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `upsert_router_route` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_apply` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `upsert_detection_entry` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_apply` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `upsert_knowledge_node` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_mutate` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `dispatch` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `handle` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_derive_keywords` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_derive_detection_key` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_derive_route_name` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_safe_str` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_append_jsonl_safe` [complexity: 166] [cognitive: 166] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]

### ./scripts/lib/cache_writer.py

**File Complexity**: 77 | **Functions**: 6

- **Struct**: `CacheWriteError` [fields: 0]
- **Function**: `atomic_write_json` [complexity: 77] [cognitive: 77] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `atomic_consume_json` [complexity: 77] [cognitive: 77] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `safe_read_json` [complexity: 77] [cognitive: 77] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `_exclusive_lock` [complexity: 77] [cognitive: 77] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `_record_lock_event_safe` [complexity: 77] [cognitive: 77] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `_remove_silently` [complexity: 77] [cognitive: 77] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]

### ./scripts/lib/delegation_outcomes.py

**File Complexity**: 73 | **Functions**: 5

- **Function**: `_parse_ts` [complexity: 73] [cognitive: 73] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `_is_valid_was_delegated` [complexity: 73] [cognitive: 73] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `is_quarantined` [complexity: 73] [cognitive: 73] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `iter_delegation_events` [complexity: 73] [cognitive: 73] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Struct**: `DriftCounter` [fields: 0]
- **Function**: `DriftCounter::__init__` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `DriftCounter::observe` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `DriftCounter::total` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `DriftCounter::true_rate` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `DriftCounter::as_dict` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `collect_session_outcomes` [complexity: 73] [cognitive: 73] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]

### ./scripts/lib/hook_telemetry.py

**File Complexity**: 78 | **Functions**: 12

- **Function**: `_project_dir` [complexity: 78] [cognitive: 78] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_marker_dir` [complexity: 78] [cognitive: 78] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_sanitize_marker_component` [complexity: 78] [cognitive: 78] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_marker_path` [complexity: 78] [cognitive: 78] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_write_marker` [complexity: 78] [cognitive: 78] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_delete_marker` [complexity: 78] [cognitive: 78] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_ledger_path` [complexity: 78] [cognitive: 78] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_resolve_session_id` [complexity: 78] [cognitive: 78] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_now_iso` [complexity: 78] [cognitive: 78] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_append_row` [complexity: 78] [cognitive: 78] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Struct**: `_Tracker` [fields: 0]
- **Function**: `_Tracker::__init__` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_Tracker::set_error` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_Tracker::add_meta` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `track_hook` [complexity: 78] [cognitive: 78] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `record_invocation` [complexity: 78] [cognitive: 78] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/lib/lock_telemetry.py

**File Complexity**: 42 | **Functions**: 9

- **Function**: `_project_dir` [complexity: 42] [cognitive: 42] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_ledger_path` [complexity: 42] [cognitive: 42] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_threshold_ms` [complexity: 42] [cognitive: 42] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_now_iso` [complexity: 42] [cognitive: 42] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_infer_hook` [complexity: 42] [cognitive: 42] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_sanitize_hook` [complexity: 42] [cognitive: 42] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_relativize_target` [complexity: 42] [cognitive: 42] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_append_row` [complexity: 42] [cognitive: 42] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `record_lock_event` [complexity: 42] [cognitive: 42] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/lib/locked_json_rmw.py

**File Complexity**: 122 | **Functions**: 5

- **Struct**: `_NoFcntl` [fields: 0]
- **Function**: `_NoFcntl::flock` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Struct**: `LockTimeout` [fields: 0]
- **Function**: `locked_rmw_json` [complexity: 122] [cognitive: 122] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `_acquire_locked` [complexity: 122] [cognitive: 122] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `locked_write_remerge` [complexity: 122] [cognitive: 122] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `_mutate` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `_locked_overwrite_raw` [complexity: 122] [cognitive: 122] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `_cli` [complexity: 122] [cognitive: 122] [big-o: O(?)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]
- **Function**: `_jq_mutate` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 1 items] [churn: low(2)] [tdg: 2.5]

### ./scripts/lib/plugin_paths.py

**File Complexity**: 9 | **Functions**: 1

- **Function**: `plugin_root` [complexity: 9] [cognitive: 9] [big-o: O(n log n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]

### ./scripts/lib/session_attribution.py

**File Complexity**: 59 | **Functions**: 5

- **Function**: `resolve_session_id` [complexity: 59] [cognitive: 59] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `normalize_session_key` [complexity: 59] [cognitive: 59] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `attribute_row` [complexity: 59] [cognitive: 59] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `attribute_decision_md` [complexity: 59] [cognitive: 59] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `get_unknown_session_id` [complexity: 59] [cognitive: 59] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]

### ./scripts/lib/verifier/__init__.py

**File Complexity**: 1 | **Functions**: 0


### ./scripts/lib/verifier/spine.py

**File Complexity**: 33 | **Functions**: 3

- **Function**: `_compile` [complexity: 33] [cognitive: 33] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `is_spine_path` [complexity: 33] [cognitive: 33] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `first_spine_match` [complexity: 33] [cognitive: 33] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]

### ./scripts/lib/verifier/stop_gate.py

**File Complexity**: 27 | **Functions**: 2

- **Struct**: `EPTEvidence` [fields: 0]
- **Function**: `EPTEvidence::legs_present` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `EPTEvidence::all_present` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Struct**: `StopGateResult` [fields: 0]
- **Function**: `check_stop_gate` [complexity: 27] [cognitive: 27] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `_has_trigger_word` [complexity: 27] [cognitive: 27] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]

### ./scripts/recalc-fitness.py

**File Complexity**: 212 | **Functions**: 21

- **Struct**: `_NoFcntl` [fields: 0]
- **Function**: `_NoFcntl::flock` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `load_config` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_ema_honesty_enabled` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_niche_selection_enabled` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `read_ledger` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `outcome_to_score` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_clamp01` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_symmetric_ema` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `compute_ema` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `apply_ratchet_floor` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_ema_meta` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `cold_start_blend` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_niche_distance` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_select_quick_picks` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `recalc_lens` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_warn_if_stale_skiplist_collides_with_live_config` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `recalc_trait` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `recalc_delegation` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `write_cache` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `log_invocation` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `_arg_value` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]
- **Function**: `main` [complexity: 212] [cognitive: 212] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(3)] [tdg: 2.5]

### ./scripts/steward_actuator.py

**File Complexity**: 162 | **Functions**: 17

- **Struct**: `_NoFcntl` [fields: 0]
- **Function**: `_NoFcntl::flock` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_plugin_root` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_is_spine_path` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Struct**: `AutonomyClass` [fields: 0]
- **Function**: `classify_action` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_utc_now_iso` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_utc_now_stamp` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_append_jsonl` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_write_failure` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_resolve_hook_path` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_is_test_file` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_scan_referenced_basenames` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `load_reviewed_keep_ids` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `is_safe_to_autonomously_archive` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `archive_dead_hook` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `emit_pending_action` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `emit_manual_retirement_pending` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `run_actuator` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_build_parser` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `main` [complexity: 162] [cognitive: 162] [big-o: O(?)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]
- **Function**: `_timeout` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 2 items] [churn: low(3)] [tdg: 2.5]

### ./scripts/steward_checks/__init__.py

**File Complexity**: 1 | **Functions**: 0


### ./scripts/steward_checks/audit.py

**File Complexity**: 51 | **Functions**: 5

- **Function**: `find_latest_audit_report` [complexity: 51] [cognitive: 51] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `check_audit_freshness` [complexity: 51] [cognitive: 51] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `run_check` [complexity: 51] [cognitive: 51] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_install_timeout` [complexity: 51] [cognitive: 51] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_handler` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 51] [cognitive: 51] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/steward_checks/common.py

**File Complexity**: 36 | **Functions**: 13

- **Function**: `load_steward_config` [complexity: 63] [cognitive: 63] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Struct**: `Severity` [fields: 0]
- **Struct**: `StewardFinding` [fields: 0]
- **Function**: `StewardFinding::to_dict` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Struct**: `CheckResult` [fields: 0]
- **Function**: `CheckResult::findings_count` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `CheckResult::findings_by_severity` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `CheckResult::to_dict` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `write_failure_ledger` [complexity: 63] [cognitive: 63] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `render_output` [complexity: 63] [cognitive: 63] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `add_argparse_output_flags` [complexity: 63] [cognitive: 63] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]
- **Function**: `utc_now_iso` [complexity: 63] [cognitive: 63] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(1)] [tdg: 2.5]

### ./scripts/steward_checks/followup.py

**File Complexity**: 69 | **Functions**: 8

- **Function**: `build_marker_re` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `parse_target_date` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `severity_from_days` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_format_title` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `scan_followup_dir` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `run_check` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_install_timeout` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_handler` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 69] [cognitive: 69] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/steward_checks/retirement.py

**File Complexity**: 71 | **Functions**: 9

- **Function**: `load_registered_basenames` [complexity: 71] [cognitive: 71] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `load_hook_files_on_disk` [complexity: 71] [cognitive: 71] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_is_test_file` [complexity: 71] [cognitive: 71] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_has_shared_library_marker` [complexity: 71] [cognitive: 71] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_file_age_days` [complexity: 71] [cognitive: 71] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `check_retirement` [complexity: 71] [cognitive: 71] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `run_check` [complexity: 71] [cognitive: 71] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_install_timeout` [complexity: 71] [cognitive: 71] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_handler` [complexity: 3] [cognitive: 2] [big-o: O(n)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 71] [cognitive: 71] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./scripts/v2_runner_helpers.py

**File Complexity**: 38 | **Functions**: 8

- **Function**: `_read_habituation` [complexity: 38] [cognitive: 38] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_write_habituation` [complexity: 38] [cognitive: 38] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `_v2_canary_enabled` [complexity: 38] [cognitive: 38] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `cmd_reject` [complexity: 38] [cognitive: 38] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `cmd_habituate` [complexity: 38] [cognitive: 38] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `cmd_read_habituation` [complexity: 38] [cognitive: 38] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `cmd_decay` [complexity: 38] [cognitive: 38] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]
- **Function**: `main` [complexity: 38] [cognitive: 38] [big-o: O(?)] [provability: 66%] [satd: 0] [churn: low(2)] [tdg: 2.5]

### ./setup.ps1


### ./setup.sh


