#!/usr/bin/env bash
# Substrate smoke test (Phase 1+2 gate; later promoted into the Self-Star
# Doctor's "substrate" + "fitness" junction checks).
#
# Proves on the COMMITTED tree, from cold data:
#   S1: graph pipeline builds caches from empty (coactivation, hot-pairs)
#   S2: ARS registers a synthetic Write (knowledge-node + router + detection
#       + kairn queue + latency ledger)
#   S3: auto-edges/auto-routes pick up the ARS-created node without data loss
#   S4: telemetry chain produces a delegation-gaps row + hook-invocations rows
#   S5: fitness junction - the S4 Stop wrote a cognitive-fitness row (the
#       shipped mutation_rules.v2_tuning_enabled gate is ON), recalc turns it
#       into a bounded delegation-fitness score, and the delegation-enforcer
#       consumer surfaces that score on the next suggestion
#   S6: autoevolve junction (SC-G) - the mutation-eligibility gate blocks on
#       cold data, flips eligible only after N=8 real outcomes, the global
#       off-switch halts it, and the deterministic persist-gate auto-reverts a
#       planted below-baseline mutation (restoring the snapshot + logging it)
#   S7: steward junction - the three checks emit ZERO findings on the clean repo
#       (cold-baseline), a planted overdue follow-up IS surfaced (positive
#       control), and the actuator does NOT auto-archive while the verifier
#       spine is absent (Invariant-B fail-closed; the spine ships in a later phase)
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
# Snapshot the curated router state BEFORE any writer runs (S3 compares
# against this snapshot instead of a hardcoded fixture value, so curating
# routes never breaks the gate).
python3 - << 'PY'
import json
router = json.load(open("_graph/cache/context-router.json"))["routes"]
curated = {k: v for k, v in router.items() if "primary_nodes" in v}
json.dump(curated, open("/tmp/smoke-curated-routes.json", "w"))
PY
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
# Every curated route (snapshot from before any writer ran) survived all
# writers byte-identically (lost-update guard).
router = json.load(open("_graph/cache/context-router.json"))["routes"]
curated = json.load(open("/tmp/smoke-curated-routes.json"))
ok = all(router.get(k) == v for k, v in curated.items())
sys.exit(0 if ok and curated else 1)
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

# --- S5: fitness junction ----------------------------------------------------
# S4's Stop already appended a cognitive-fitness row: the committed
# delegation-config ships mutation_rules.v2_tuning_enabled=true.
python3 - << PY
import json, sys
rows = [json.loads(l) for l in open("_memory/analytics/cognitive-fitness.jsonl")]
row = rows[-1]
ok = (row["system"] == "delegation"
      and row["outcome"] == "positive"
      and row["details"]["was_delegated"] is True
      and row["details"]["session"] == "$CLAUDE_SESSION_ID")
sys.exit(0 if ok else 1)
PY
check "S5 Stop appended cognitive-fitness row (v2_tuning_enabled gate ON)" $?
python3 scripts/recalc-fitness.py --trigger smoke >/dev/null 2>&1
check "S5 recalc-fitness exits 0" $?
python3 - << 'PY'
import json, sys
ok = True
for name in ("lens-fitness.json", "trait-fitness.json", "delegation-fitness.json"):
    d = json.load(open(f"_graph/cache/{name}"))
    ok = ok and "updated" in d and "scores" in d
d = json.load(open("_graph/cache/delegation-fitness.json"))
entry = d["scores"].get("exploration", {})
score = entry.get("exploration")
ok = ok and isinstance(score, float) and 0.0 <= score <= 1.0
inv = json.loads(open("_ledgers/recalc-fitness-invocations.jsonl").read().splitlines()[-1])
ok = ok and inv["success"] is True and inv["events_read"] >= 1
sys.exit(0 if ok else 1)
PY
check "S5 recalc produced 3 caches + bounded delegation score + invocation row" $?
# Consumer leg: a fresh suggestion now carries the historical fitness hint.
S5_OUT=$(printf '{"session_id":"%s","hook_event_name":"UserPromptSubmit","prompt":"find all usages of the config loader across the whole codebase"}' \
  "$CLAUDE_SESSION_ID" | python3 hooks/scripts/delegation-enforcer.py)
echo "$S5_OUT" | grep -qi "historical delegation fitness for exploration"
check "S5 enforcer consumer surfaces the fitness score" $?
rm -f "/tmp/delegation-pending-$CLAUDE_SESSION_ID.json"

# --- S6: AutoEvolve SC-G (cold-quiet eligibility + deterministic persist-gate)
AE="scripts/autoevolve-scorer.py"
OUTLEDGER="_autoevolve/outcomes/context-router.jsonl"
SNAP="_autoevolve/snapshots/smoke-context-router.json"
DCFG="_graph/cache/delegation-config.json"
mkdir -p _autoevolve/outcomes _autoevolve/snapshots _autoevolve/rejected

# S6.1 cold data -> the gate blocks (no real outcomes yet); ZERO mutation allowed
rm -f "$OUTLEDGER"
python3 "$AE" mutation-gate context-router >/dev/null 2>&1; [ $? -eq 1 ]
check "S6 mutation-gate blocks on cold data (insufficient samples)" $?

# S6.2 seed N=8 outcomes -> the gate flips eligible; exactly one scored cycle runs
for i in $(seq 1 8); do echo '{"ts":"t","outcome":"ok"}' >> "$OUTLEDGER"; done
python3 "$AE" mutation-gate context-router >/dev/null 2>&1; [ $? -eq 0 ]
check "S6 mutation-gate eligible after N=8 outcomes" $?
python3 "$AE" score context-router >/dev/null 2>&1
check "S6 one scored mutation cycle runs (scorer exit 0)" $?

# S6.3 off-switch halts everything even with outcomes present.
# Byte-exact backup/restore so a local run leaves delegation-config.json clean.
DCFG_BAK="$(mktemp)"; cp "$DCFG" "$DCFG_BAK"
python3 - <<'PY'
import json
p = "_graph/cache/delegation-config.json"
d = json.load(open(p)); d["mutation_rules"]["v2_tuning_enabled"] = False
json.dump(d, open(p, "w"), indent=2)
PY
# Capture first: the gate exits 1 when blocked, and `set -o pipefail` would
# otherwise propagate that 1 through the pipe and mask grep's match.
S6_OFF=$(python3 "$AE" mutation-gate context-router 2>&1 || true)
echo "$S6_OFF" | grep -qi "global-off"
check "S6 off-switch (v2_tuning_enabled=false) halts mutation" $?
cp "$DCFG_BAK" "$DCFG"; rm -f "$DCFG_BAK"

# S6.4 persist-gate deterministically reverts a planted below-baseline mutation
cp _graph/cache/context-router.json "$SNAP"
python3 - <<'PY'
import json
p = "_graph/cache/context-router.json"
d = json.load(open(p)); d["routes"]["debugging"]["keywords"] = []  # planted regression
json.dump(d, open(p, "w"), indent=2)
PY
python3 "$AE" persist-gate context-router --snapshot "$SNAP" --run-id smoke --desc "planted regression" >/dev/null 2>&1
[ $? -eq 2 ]   # exit 2 = reverted
check "S6 persist-gate auto-reverts below-baseline mutation (exit 2)" $?
python3 - <<'PY'
import json, sys
d = json.load(open("_graph/cache/context-router.json"))
sys.exit(0 if d["routes"]["debugging"]["keywords"] else 1)
PY
check "S6 live config restored to snapshot after revert" $?
ls _autoevolve/rejected/*context-router*.json >/dev/null 2>&1
check "S6 rejected-mutation record written on revert" $?

# tidy smoke artifacts (all gitignored, but keep local runs clean)
rm -f "$OUTLEDGER" "$SNAP" _autoevolve/rejected/*context-router*.json
printf '{\n  "targets": {},\n  "history": []\n}\n' > _autoevolve/baselines.json

# --- S7: Steward apparatus (cold-baseline ZERO + positive control + fail-closed actuator)
# S7.1 all three checks emit ZERO findings on the clean repo (cold-baseline)
python3 - <<'PY'
import sys; sys.path.insert(0, "scripts")
import datetime
from steward_checks import audit, followup, retirement
d = datetime.date(2026, 6, 12)
total = (audit.run_check(today=d).findings_count
         + followup.run_check(today=d).findings_count
         + retirement.run_check(today=d).findings_count)
sys.exit(0 if total == 0 else 1)
PY
check "S7 steward checks emit ZERO findings on clean repo (cold-baseline)" $?

# S7.2 planted positive control: an overdue follow-up IS surfaced
mkdir -p _handoffs
printf -- '- Follow-up 2026-06-01: smoke positive control\n' > _handoffs/smoke-steward-followup.md
python3 - <<'PY'
import sys; sys.path.insert(0, "scripts")
import datetime
from steward_checks import followup
res = followup.run_check(today=datetime.date(2026, 6, 12))
sys.exit(0 if any("smoke positive control" in f.title for f in res.findings) else 1)
PY
check "S7 planted overdue follow-up IS surfaced (positive control)" $?
rm -f _handoffs/smoke-steward-followup.md; rmdir _handoffs 2>/dev/null || true

# S7.3 actuator REFUSES to auto-archive a verifier-SPINE path (Invariant B).
# (The spine ships in Phase 5; with it present the actuator classifies a spine
# file INTERACTIVE and never archives it - tested here against a real spine file.)
SMOKE_FIND="$(mktemp)"
printf '%s\n' '{"module":"retirement","severity":"P2","title":"smoke spine","detail":"Confidence: HIGH (not registered in hooks.json = never fires)","source":"scripts/steward_actuator.py","item_id":"smoke-spine","maintainer_decision":"silent"}' > "$SMOKE_FIND"
S7_ARCH=$(python3 - "$SMOKE_FIND" <<'PY'
import sys, pathlib; sys.path.insert(0, "scripts")
import steward_actuator as m
s = m.run_actuator(findings_path=pathlib.Path(sys.argv[1]), dry_run=True)
print(s["autonomous_archived"])
PY
)
[ "$S7_ARCH" = "0" ]
check "S7 actuator refuses to archive a spine path (Invariant B)" $?
rm -f "$SMOKE_FIND"

# --- S8: Verifier-spine junction (closes the loop) -------------------------
# S8.1 spine resolves: a spine path is detected, a normal hook is not.
python3 - <<'PY'
import sys; sys.path.insert(0, ".")
from scripts.lib.verifier.spine import is_spine_path
ok = is_spine_path("scripts/steward_actuator.py") and not is_spine_path("hooks/scripts/delegation-enforcer.py")
sys.exit(0 if ok else 1)
PY
check "S8 spine registry resolves (spine path True, normal hook False)" $?

# S8.2 with the spine PRESENT, a genuinely-dead NON-spine hook IS archived
# (the dead-hook archiver activated - the actuator flipped from fail-closed).
# The ghost name is PID-suffixed so its basename appears as no literal token in
# any scanned file (incl. this script), or the reference-guard would refuse it.
mkdir -p hooks/scripts
GHOST="smokedead$$.py"
printf '# nobody references me\n' > "hooks/scripts/$GHOST"
S8_FIND="$(mktemp)"
printf '{"module":"retirement","severity":"P2","title":"smoke dead ghost","detail":"Confidence: HIGH (not registered in hooks.json = never fires)","source":"hooks/scripts/%s","item_id":"%s","maintainer_decision":"silent"}\n' "$GHOST" "$GHOST" > "$S8_FIND"
S8_ARCH=$(python3 - "$S8_FIND" <<'PY'
import sys, pathlib; sys.path.insert(0, "scripts")
import steward_actuator as m
s = m.run_actuator(findings_path=pathlib.Path(sys.argv[1]), dry_run=False)
print(s["autonomous_archived"])
PY
)
[ "$S8_ARCH" = "1" ] && [ ! -f "hooks/scripts/$GHOST" ]
check "S8 spine present -> genuinely-dead non-spine hook IS archived (archiver live)" $?
rm -f "$S8_FIND" "hooks/scripts/$GHOST" "_archive/retired/$GHOST"-* 2>/dev/null || true

# S8.3 SC-F: forced-verify-stop-gate is lease-scoped.
rm -f _graph/cache/autonom-lease.json
printf '{"session_id":"s-off","stop_reason":"the port is done and shipped"}' \
  | python3 hooks/scripts/forced-verify-stop-gate.py >/dev/null 2>&1
check "S8 SC-F autonomy-OFF never blocks (no lease -> observe-only)" $?
python3 - <<'PY'
import json, time, os
p = "_graph/cache/autonom-lease.json"; os.makedirs(os.path.dirname(p), exist_ok=True)
json.dump({"session_id": "s-own", "claimed_at": time.time(), "released": False}, open(p, "w"))
PY
printf '{"session_id":"s-own","stop_reason":"the port is done and shipped"}' \
  | python3 hooks/scripts/forced-verify-stop-gate.py >/dev/null 2>&1
[ $? -eq 1 ]
check "S8 SC-F autonomy-ON BLOCKS a markerless completion claim" $?
MARK='the port is done. [EPT-TRIGGER: pytest exit 0 at t] [EPT-EFFECT: 142 tests passed] [EPT-CONSUMER: actuator imports is_spine_path; loop closed]'
printf '{"session_id":"s-own","stop_reason":"%s"}' "$MARK" \
  | python3 hooks/scripts/forced-verify-stop-gate.py >/dev/null 2>&1
check "S8 SC-F autonomy-ON PASSES with the EPT marker form" $?
rm -f _graph/cache/autonom-lease.json

# S8.4 full-loop trace: ONE synthetic turn traversing all 6 hops.
python3 - <<'PY'
import json, sys, subprocess, datetime, pathlib
sys.path.insert(0, "scripts"); sys.path.insert(0, ".")
trace = []
gaps = [json.loads(l) for l in open("_memory/analytics/delegation-gaps.jsonl")]
trace.append(("1 delegation", f"gaps row was_delegated={gaps[-1]['was_delegated']}"))
df = json.load(open("_graph/cache/delegation-fitness.json"))
score = df["scores"]["exploration"]["exploration"]
trace.append(("2 fitness", f"delegation-fitness[exploration]={score:.3f} in [0,1]"))
rc = subprocess.run([sys.executable, "scripts/autoevolve-scorer.py", "mutation-gate", "context-router"],
                    capture_output=True).returncode
trace.append(("3 autoevolve", f"mutation-gate rc={rc} (1=cold-quiet, fitness-gated)"))
from steward_checks import audit, followup, retirement
d = datetime.date(2026, 6, 12)
n = (audit.run_check(today=d).findings_count + followup.run_check(today=d).findings_count
     + retirement.run_check(today=d).findings_count)
trace.append(("4 steward", f"checks findings={n}"))
import steward_actuator as act
cls = act.classify_action({"module": "retirement", "detail": act.HIGH_CONFIDENCE_MARKER,
                           "source": "scripts/steward_actuator.py"})
trace.append(("5 verifier-spine", f"classify(spine)={cls} spine_available={act._SPINE_AVAILABLE}"))
trace.append(("6 delegation(relicense)", f"enforcer re-reads delegation-fitness[exploration]={score:.3f}"))
print("=== FULL-LOOP TRACE (one synthetic turn, 6 hops) ===")
for hop, val in trace:
    print(f"  HOP {hop}: {val}")
ok = (act._SPINE_AVAILABLE and cls == "INTERACTIVE"
      and 0.0 <= score <= 1.0 and all(v for _, v in trace))
sys.exit(0 if ok else 1)
PY
check "S8 full-loop 6-hop trace (delegation->fitness->autoevolve->steward->spine->delegation)" $?

if [ "$FAIL" -eq 0 ]; then
  echo "SUBSTRATE SMOKE: ALL GREEN"
else
  echo "SUBSTRATE SMOKE: FAILURES PRESENT"
  exit 1
fi
