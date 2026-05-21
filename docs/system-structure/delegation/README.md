# Adaptive Routing with Audit Trail

A reference pattern for deciding which agent gets which task in a multi-agent system, with the decision, its inputs, and its outcome preserved together for review.

## The operator-side problem

Multi-agent systems route work. The router has options: which model, which subagent, which capability level, which personality trait. Static rules fall behind as the system grows; dynamic rules drift unless they are observable.

Operators need a router that:
- Adapts to context (current load, recent successes, available capacity)
- Is reversible (if a routing call was wrong, the operator can see why)
- Does not drift into unsafe shortcuts (delegating critical work to too-cheap a model)
- Distinguishes between "I should delegate this" and "I should not delegate this" with auditable thresholds

The hard part is making the dynamic behaviour inspectable, and keeping the routing logic from quietly collapsing into a one-rule shortcut.

## Score factors and adaptive threshold

The router computes a delegation score on every inbound task. The score is a sum of factors. The threshold is itself adaptive.

| Score factor | Direction | Why |
|---|---|---|
| Scope spans more than 2 files | +2 | Multi-file work benefits from a dedicated subagent |
| Bulk operation | +2 | Parallel-friendly, low-coordination cost |
| Research / exploration / search | +3 | Explore-class subagents are cheap and parallelisable |
| Code review | +2 | Reviewer subagent is specialised |
| Independent task | +2 | No back-and-forth with the parent agent needed |
| Critical keyword detected | -10 | Hard down-weight on production / deploy / payment / password / secret |
| Operator wants to see | -5 | "Show me" / "explain" signals stay on the main agent |
| Complexity above threshold | -3 | High-complexity work has too much delegation overhead |

The adaptive threshold formula:

```
effective_threshold = base
                    + modifier_context_load
                    + modifier_recent_outcome_streak
                    + modifier_active_agent_count
```

Concrete example: base = 3.0, lowered by 0.5 when context-percent is below 40 (fresh context, room to delegate), lowered by 0.3 if the last three delegations succeeded, raised by 0.5 when two or more agents are already active (anti-stampede). The threshold lives in a cache file readable on every routing call.

## The pattern

```
Task input
   |
   v
Score factors  ->  Critical-keyword denylist (out-of-band hard veto)
   |
   v
Adaptive threshold
   |
   v
Decision  ->  Audit log entry (score record + threshold record + decision record)
   |
   v
Apply
   |
   v
Outcome  ->  Outcome tracker (feeds back into threshold modifier)
```

Score, threshold, decision, and outcome are all recorded together. After-the-fact review can answer "why did the router send this task to this agent" without re-running the system.

## Three safety-relevant properties

**Reversibility.** A bad routing decision is traceable. The audit entry contains the inputs that led to it, the threshold in effect, and the outcome. Operators can build rules from the audit log retroactively. The router itself is stateless between decisions; reversal means changing the score-factor weights or the threshold formula, not rewinding state.

**Drift detection.** If the router starts routing differently over time, the audit log shows it. The threshold-adaptation logic is the most likely source of drift, and exposing it explicitly makes the drift visible instead of hidden. A separate analysis script over the audit log can flag "router is routing N% more to X model this week than last."

**Operator override.** The pattern lets operators inject keyword-based overrides on top of the score (always-delegate / never-delegate / specific-agent forcing). Override-on-top-of-score is safer than override-replacing-score because the override leaves the score record intact for audit.

## Trade-offs and limits

**Score-factor design is open.** What goes into the score is the operator's design choice. Reasonable defaults: scope, complexity, exploration value, recent success rate. Bad defaults: cost-only, length-only, popularity-only. The factor set is a constant subject to revision; document the version with each audit entry.

**Adaptive threshold can collapse.** If recent outcomes drive the threshold and recent outcomes are biased (one bad week), the threshold tracks the bias. Damping (slow EMA) and exploration-rate floors prevent the collapse but require explicit design.

**Audit log noise.** A router that fires on every interaction generates a large audit stream. Triage discipline (priority routing decisions versus routine ones) matters for keeping the log readable. Tag entries with a class field so consumers can filter.

**Critical-keyword denylist sits outside the score.** It cannot be downgraded by the score. The denylist is the safety net of last resort. Operators choose what counts as critical and review the list periodically; an outdated denylist is worse than a too-aggressive one.

**Personality-trait injection.** Operators can layer personality traits onto the routing decision (a curious agent for exploration, a cautious agent for debugging, a perfectionist for code review). The traits are a separate dimension from the score; documented mappings prevent ad-hoc overrides.

## Application to operator-side multi-agent safety

Routing is where capability allocation happens. A multi-agent system's safety surface depends heavily on which agent gets which task; an adaptive router with hidden logic is a safety problem. An adaptive router with an audit trail and operator-readable thresholds is the operator-side answer.

This pattern is the policy layer through which most other behaviour is mediated. It is also where most operator interventions land. Investing in audit-quality early pays off every time the operator wants to understand why the system behaved a certain way.
