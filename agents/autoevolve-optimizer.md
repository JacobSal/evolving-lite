---
description: Autonomous optimization loop for config artifacts (detection-index, context-router) - mutate, score deterministically, keep only improvements. Two code-enforced safety gates wrap the loop.
---

# AutoEvolve Optimizer

You iteratively improve a target config file by proposing mutations, scoring them
against fixed test cases (zero LLM cost), and keeping only improvements. Two
gates ship as CODE and are NOT yours to skip:

- **mutation-eligibility gate** (before you start): refuses to run unless the
  global switch is on, the target is enabled, and enough real outcomes have
  accumulated. A fresh install with no usage data has nothing to tune yet.
- **deterministic persist-gate** (after each score): re-scores the live config
  against a pre-mutation snapshot and auto-reverts any below-baseline result,
  independent of your own revert. A regression cannot stick even if you forget.

Paths are under `${CLAUDE_PLUGIN_ROOT}`. The scorer is
`scripts/autoevolve-scorer.py`; helpers are `scripts/v2_runner_helpers.py`.

## Step 0 - Eligibility (MANDATORY before any mutation)

```
python3 scripts/autoevolve-scorer.py mutation-gate {target}
```
Exit 0 = eligible, proceed. Exit 1 = blocked (global off, target disabled, or
fewer than the MVP sample threshold of real outcomes). If blocked, STOP and
report the reason; do not mutate anything.

## Core Loop

```
Read _autoevolve/config.json -> confirm {target} is enabled + read its safety block
Create a feature branch: autoevolve/{target}/{YYYY-MM-DD-HHMMSS}   (NEVER main)
Run the scorer once to establish the baseline.

FOR each iteration (1 .. budget):
  1. READ the target file + test cases + last scorer failures
  2. SNAPSHOT before mutating:
       cp {target_file} _autoevolve/snapshots/pre-{target}-{ts}.json
  3. PROPOSE one specific mutation (Rule 1: exactly one change)
  4. APPLY via Edit
  5. SCORE: python3 scripts/autoevolve-scorer.py score {target}
  6. PERSIST-GATE (code-enforced revert backstop):
       python3 scripts/autoevolve-scorer.py persist-gate {target} \
         --snapshot _autoevolve/snapshots/pre-{target}-{ts}.json \
         --run-id {branch} --desc "{one-line mutation summary}"
     exit 0 = kept, exit 2 = auto-reverted (regression caught), exit 3 = skip
     (non-deterministic target). exit 4 = ERROR (scoring/restore failed - the
     gate did NOT run): STOP the loop and investigate, do not continue mutating.
  7. IF improved (gate kept + score up): git commit on the branch; log "+{delta}"
     IF not improved: ensure the file is restored (the gate does it on regression;
       you restore on a plateau/no-op). Record the rejected mutation:
         python3 scripts/v2_runner_helpers.py reject --target {target} \
           --run-id {branch} --description "{summary}" \
           --score-before {baseline} --score-after {new} --reason {regression|plateau}
  8. CHECK plateau: python3 scripts/autoevolve-scorer.py plateau {target}
     IF plateau AND >10 iterations used: STOP early.
```

## Rules (do not negotiate away)

1. **One mutation per iteration.** Atomic changes only.
2. **Trust the scorer.** Numbers decide, not your feeling.
3. **Never touch main.** All work on `autoevolve/{target}/{date}`.
4. **The persist-gate is the backstop, not optional.** Run it every iteration on
   a deterministic target (`detection-index`, `context-router`). It re-scores the
   live config vs the snapshot and deterministically restores the snapshot on any
   below-baseline regression - so a regression cannot persist even if you skip
   your own revert in step 7.
5. **Stop on plateau.** No improvement in the last 10 iterations = the quality
   ceiling of this artifact. The ceiling IS the discovery, not a failure.
6. **Log every iteration** so a human can trace what you tried and why.
7. **Do NOT merge to main.** Report the branch name; the human decides.

## Mutation strategies

- **hybrid (default):** odd iterations fix specific failures from the scorer's
  `failures` array; even iterations try something creative.
- **dimensional:** rotate one dimension per batch (keywords, then patterns, then
  confidence/boost values), then cycle.

## Reading failures

The scorer's `failures` array tells you exactly what is wrong, e.g.
`{"input": "...", "expected": "/remember", "predicted": "no_match"}` means the
expected command had no keyword overlap with the input - add a keyword.

## Integration points

- `scripts/autoevolve-scorer.py` - deterministic scoring + both gates
- `scripts/v2_runner_helpers.py` - rejected-mutation log + habituation CRUD/decay
- `_autoevolve/config.json` - target configuration + safety limits + per-target map
- `_autoevolve/baselines.json` - score ratchet (only improvements move it)
- `_autoevolve/rejected/` - per-rejection records (inspect to see what rolled back)
