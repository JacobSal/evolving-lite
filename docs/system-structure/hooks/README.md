# Tool-Call Instrumentation Substrate

A reference pattern for placing observability and policy enforcement at the tool-invocation boundary in a multi-agent system, with concrete event taxonomy and lateral-channel discipline.

## The operator-side problem

Multi-agent systems run many tools per session: file reads, edits, shell commands, subagent dispatches, web fetches, MCP calls. Each invocation is a place where behaviour can drift, side effects accumulate, telemetry should be captured, or a safety check might need to fire. Frameworks usually expose tool invocation as a single function call. Operators need a layer between the agent and the tool that they own and can extend, so observability and enforcement attach without modifying the agent or the tool.

## Event taxonomy

The substrate is event-driven. A typical multi-agent runtime fires these named events; hooks register against the events they care about:

| Event | Fires when | Common hook responsibilities |
|---|---|---|
| `PreToolUse` | Before any tool call is dispatched | Permission check, input sanitisation, dispatch routing, resource-budget gate |
| `PostToolUse` | After tool returns | Telemetry capture, finding extraction, side-effect log, error classification |
| `SessionStart` | New conversation begins | Memory bootup, coordination-state read, freshness checks |
| `UserPromptSubmit` | User sends a message | Intent classification, delegation scoring, denylist check |
| `Stop` | Conversation pause point | Auto-archival, learning-loop emit, pending-task flush |
| `SubagentStop` | Spawned subagent finishes | Result sanitisation, finding propagation, outcome recording |
| `PreCompact` / `PostCompact` | Context window approaches limit | Snapshot to disk, state preserve / restore |

Each event can have many registered hooks. The substrate runs them in declared order. A hook can pass through, modify the payload, or veto (returning an exit code that aborts the chain).

## The pattern

```
Agent invokes tool
       |
       v
  [PreToolUse hooks]   ->  N independent hooks in order
       |                   any can veto
       v
   Tool executes
       |
       v
  [PostToolUse hooks]  ->  N independent hooks
       |                   capture, classify, log
       v
  Result to agent
```

Hooks are single-responsibility scripts. Each one reads JSON on stdin, writes JSON on stdout, exits with a status code. The orchestrator dispatches in order, collects outputs, and either continues or aborts.

## Three safety-relevant properties

**Inspectability.** Every tool call passes through hooks the operator owns. The substrate is the audit point. Concrete: a `PostToolUse` hook that writes one JSON line per call into an append-only log gives full session reproducibility. If a behaviour happened, the line exists.

**Compositional enforcement.** Multiple hooks fire on the same event without coordinating. A permission check, a sanitisation pass, and a telemetry writer all attach to `PreToolUse` independently. New enforcement adds a new hook; removing it removes that file. No central registry to corrupt.

**Lateral-channel awareness.** Hooks that share state outside the orchestrator (temp files, environment variables, sockets, sqlite databases) form a hidden coupling layer. Mapping the shared channels is what surfaces the bug class where two hooks both write to or read from the same place with different key derivation.

Concrete example of the shared-channel failure mode: hook A writes a state file at `/tmp/state-{$SESSION_ID}.json` where `$SESSION_ID` resolves to the runtime's session UUID. Hook B reads `/tmp/state-{$SESSION_ID}.json` where `$SESSION_ID` resolves to the parent process PID because the env-var wasn't exported into B's subshell. Both hooks pass individual review. The read silently returns "file not found" and B's downstream behaviour quietly degrades. The bug is invisible to per-hook inspection; it is only visible when the lateral channel is mapped explicitly.

## Trade-offs and limits

**Cost.** Every hook adds latency. A substrate with 30+ active hooks runs the full chain on every tool call. Operators need a per-hook runtime budget and a way to disable slow hooks individually.

**Execution-order sensitivity.** When multiple hooks fire on the same event, order matters. The substrate must document the order explicitly (often by filename prefix or by an explicit priority field) or non-determinism creeps in.

**Shared-channel risk.** The substrate does not eliminate races between hooks that share state. It makes the surface inspectable. Mapping shared channels is a separate discipline; without it, the substrate creates a new class of bug that didn't exist before.

**Fail-open vs fail-closed posture.** A hook that errors out has to fail one way or the other. Fail-open keeps the system running but loses the enforcement (good for telemetry, bad for safety checks). Fail-closed enforces but introduces an availability dependency on every hook. The posture must be explicit per hook, not inherited from a substrate-wide default.

**Subagent / sidechain coverage.** Hooks defined for the main agent loop may not fire when a subagent spawns its own tool calls inside its own loop. Whether subagent tool calls run the same hook chain is a runtime design choice the operator must check explicitly; assuming yes is a common bug.

## Application to operator-side multi-agent safety

The instrumentation substrate is the layer where drift detection runs. A drift detector that lives outside the hook layer cannot see the actual tool calls; one that lives at the hook layer sees every call and can correlate across them. This is the architectural reason drift detectors are implemented as hooks rather than as out-of-band monitoring.

For operators choosing whether to add this layer: nearly every other deployment-side safety control depends on having a hook substrate to attach to (drift detection, telemetry, audit trail, permission enforcement, configuration safety, even the self-tuning loop). Build it once with the failure modes above acknowledged; reuse it for every subsequent enforcement, observability, or audit need. The cost of retrofitting it later is much higher than the cost of building it first.
