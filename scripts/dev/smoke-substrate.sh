#!/usr/bin/env bash
# Substrate smoke test (Phase 1 gate; later promoted into the Self-Star
# Doctor's "substrate" junction checks).
#
# Proves on the COMMITTED tree, from cold data:
#   S1: graph pipeline builds caches from empty (coactivation, hot-pairs)
#   S2: ARS registers a synthetic Write (knowledge-node + router + detection
#       + kairn queue + latency ledger)
#   S3: auto-edges/auto-routes pick up the ARS-created node without data loss
#   S4: telemetry chain produces a delegation-gaps row + hook-invocations rows
#
# Run inside the clean-room for the gate: scripts/dev/clean-room.sh bash scripts/dev/smoke-substrate.sh
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export CLAUDE_PLUGIN_ROOT="$(pwd)"
export CLAUDE_SESSION_ID="smoke-substrate-$$"
FAIL=0

check() { # desc, condition-exit-code
  if [ "$2" -eq 0 ]; then echo "PASS: $1"; else echo "FAIL: $1"; FAIL=1; fi
}

# --- S1: cold-start graph pipeline ---------------------------------------
for s in coactivation-aggregator compute-hot-pairs synthesis-detector; do
  python3 "scripts/graph/$s.py" >/dev/null 2>&1
  check "S1 $s exits 0 on cold data" $?
done
python3 - << 'PY'
import json, sys
d = json.load(open("_graph/cache/coactivation.json"))
sys.exit(0 if "node_pairs" in d else 1)
PY
check "S1 coactivation.json valid schema from empty" $?

# --- S2: ARS synthetic registration --------------------------------------
mkdir -p commands
printf '# Smoke Test Command\n\nSynthetic artifact for the substrate smoke.\n' > commands/smoke-test-cmd.md
printf '{"tool_name":"Write","tool_input":{"file_path":"%s/commands/smoke-test-cmd.md"},"session_id":"%s"}' \
  "$(pwd)" "$CLAUDE_SESSION_ID" | python3 hooks/scripts/artifact-registration-enforcer.py
check "S2 ARS enforcer exits 0" $?
python3 - << 'PY'
import json, sys
nodes = json.load(open("_graph/knowledge-nodes.json"))["nodes"]
ok = any(n["id"] == "command-smoke-test-cmd" for n in nodes)
det = json.load(open("_graph/cache/detection-index.json"))["entries"]
ok = ok and "smoke-test-cmd" in det
router = json.load(open("_graph/cache/context-router.json"))["routes"]
ok = ok and "auto-command-commands-smoke-test-cmd" in router
queue = open("_inbox/artifact-registration-queue.jsonl").read().splitlines()
ok = ok and any(json.loads(l)["path"] == "commands/smoke-test-cmd.md" for l in queue)
ledger = open("_ledgers/artifact-registration-latency.jsonl").read().splitlines()
ok = ok and json.loads(ledger[-1])["type"] == "command"
sys.exit(0 if ok else 1)
PY
check "S2 node + detection + router + queue + ledger all registered" $?

# --- S3: graph compute over the registered node ---------------------------
python3 scripts/graph/auto-edges.py >/dev/null 2>&1
check "S3 auto-edges exits 0 with 1 node" $?
python3 scripts/graph/auto-routes.py >/dev/null 2>&1
check "S3 auto-routes exits 0" $?
python3 scripts/graph/generate-core-view.py >/dev/null 2>&1
check "S3 generate-core-view exits 0" $?
python3 - << 'PY'
import json, sys
# Curated routes survived all writers (lost-update guard).
router = json.load(open("_graph/cache/context-router.json"))["routes"]
sys.exit(0 if router["debugging"]["primary_nodes"] == ["knowledge/rules/quick-dsv.md"] else 1)
PY
check "S3 curated router content survived concurrent-writer discipline" $?

# --- S4: telemetry chain ---------------------------------------------------
# The delegation enforcer is tier-gated (active from session 3+ by design,
# dormant on install day). Seed the session counter to simulate steady state -
# the Doctor's synthetic pulse uses the same seeding.
mkdir -p _memory
printf '5' > _memory/.session-count
printf '{"session_id":"%s","hook_event_name":"UserPromptSubmit","prompt":"find all usages of the config loader across the whole codebase"}' \
  "$CLAUDE_SESSION_ID" | python3 hooks/scripts/delegation-enforcer.py >/dev/null
test -f "/tmp/delegation-pending-$CLAUDE_SESSION_ID.json"
check "S4 enforcer wrote pending marker" $?
printf '{"session_id":"%s","hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"subagent_type":"Explore"}}' \
  "$CLAUDE_SESSION_ID" | python3 hooks/scripts/delegation-outcome-tracker.py
check "S4 tracker PreToolUse exits 0" $?
printf '{"session_id":"%s","hook_event_name":"Stop"}' \
  "$CLAUDE_SESSION_ID" | python3 hooks/scripts/delegation-outcome-tracker.py
check "S4 tracker Stop exits 0" $?
python3 - << PY
import json, sys
rows = [json.loads(l) for l in open("_memory/analytics/delegation-gaps.jsonl")]
row = rows[-1]
ok = row["was_delegated"] is True and row["session"] == "$CLAUDE_SESSION_ID"
inv = [json.loads(l)["hook"] for l in open("_ledgers/hook-invocations.jsonl")]
ok = ok and "delegation-outcome-tracker" in inv
sys.exit(0 if ok else 1)
PY
check "S4 gaps row (was_delegated=true) + hook-invocations telemetry" $?
test ! -f "/tmp/delegation-pending-$CLAUDE_SESSION_ID.json"
check "S4 marker unlinked after Stop" $?

if [ "$FAIL" -eq 0 ]; then
  echo "SUBSTRATE SMOKE: ALL GREEN"
else
  echo "SUBSTRATE SMOKE: FAILURES PRESENT"
  exit 1
fi
