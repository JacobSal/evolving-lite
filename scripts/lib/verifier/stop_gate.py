"""Forced-verify Stop-gate - non-skippable EPT enforcement (library).

BLOCKS a "done" claim that lacks 3-leg EPT evidence (trigger + effect + consumer).
The gate checks PRESENCE and MINIMUM LENGTH of each leg - it cannot verify truth,
but it forces the producer to articulate each leg explicitly.

Usage as a callable library function:
    from scripts.lib.verifier.stop_gate import check_stop_gate, EPTEvidence
    evidence = EPTEvidence(
        trigger="pytest run at 14:32Z returned exit 0",
        effect="tests/test_verifier_spine.py::test_known_pass PASSED",
        consumer="CI badge green; downstream phase unblocked",
    )
    result = check_stop_gate(claim="Verifier spine is complete", evidence=evidence)
    if not result.passed:
        raise SystemExit(f"STOP-GATE BLOCKED: {result.block_reason}")

The live CC Stop-hook wrapper that calls this lives at
hooks/scripts/forced-verify-stop-gate.py and is lease-scoped (observe-only unless
an autonomous lease is held - autonomy is OFF by default).

SAFETY SPINE INVARIANT: this module lives under scripts/lib/verifier/ (spine-
protected, see spine.py). No autonomous session may modify it.

Cross-repo: the trigger-word list defaults to English completion words; pass a
custom set to check_stop_gate(trigger_words=...) to extend it for other languages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

# English completion words that trigger EPT validation. Override per-call via the
# trigger_words parameter to add localized words.
_DEFAULT_TRIGGER_WORDS: frozenset[str] = frozenset([
    "done", "works", "working", "tested", "shipped", "verified", "ready",
    "complete", "passing", "live", "deployed", "integrated", "fixed",
    "resolved", "ok", "green", "validated", "confirmed", "in place",
    "hooked up", "wired", "registered", "active", "operational",
])

# Minimum non-empty length for each EPT leg to be considered present.
_MIN_LEG_LENGTH = 10


@dataclass
class EPTEvidence:
    """Three-leg Empirical Completion Proof evidence.

    Attributes:
        trigger: Leg 1 - what fired/ran/activated under realistic conditions,
            with timestamp.
        effect: Leg 2 - the expected effect on real system state (output slice,
            file diff, log entry).
        consumer: Leg 3 - downstream consumer can use the effect.
    """
    trigger: str = ""
    effect: str = ""
    consumer: str = ""

    def legs_present(self) -> dict[str, bool]:
        return {
            "trigger": len(self.trigger.strip()) >= _MIN_LEG_LENGTH,
            "effect": len(self.effect.strip()) >= _MIN_LEG_LENGTH,
            "consumer": len(self.consumer.strip()) >= _MIN_LEG_LENGTH,
        }

    def all_present(self) -> bool:
        return all(self.legs_present().values())


@dataclass
class StopGateResult:
    """Result of the Stop-gate check.

    Attributes:
        passed: True only if the claim is permitted to proceed. False = BLOCKED.
        block_reason: Non-empty explanation when passed=False.
        missing_legs: Which EPT legs are absent or too short.
        claim_triggered: Whether the claim text contained a trigger word.
        evidence: The EPTEvidence that was evaluated.
    """
    passed: bool
    block_reason: str = ""
    missing_legs: list[str] = field(default_factory=list)
    claim_triggered: bool = False
    evidence: Optional[EPTEvidence] = None


def check_stop_gate(
    claim: str,
    evidence: EPTEvidence | None = None,
    *,
    require_trigger_word: bool = True,
    trigger_words: Optional[Iterable[str]] = None,
) -> StopGateResult:
    """Check whether a completion claim is permitted to pass the Stop-gate.

    A claim is BLOCKED if:
    1. The claim text contains a trigger word (completion words), AND
    2. The provided evidence does not have all three EPT legs filled with at
       least _MIN_LEG_LENGTH characters each.

    A claim with NO trigger words is allowed through (status update, not a
    completion claim).

    Args:
        claim: The text of the completion claim.
        evidence: EPTEvidence with trigger/effect/consumer filled in. None =
            all-missing.
        require_trigger_word: If False, ALWAYS require EPT evidence regardless of
            trigger words (strict mode - every iteration must prove all 3 legs).
        trigger_words: Optional custom completion-word set (default = English).

    Returns:
        StopGateResult with .passed indicating whether the claim may proceed.
    """
    if evidence is None:
        evidence = EPTEvidence()

    words = frozenset(trigger_words) if trigger_words is not None else _DEFAULT_TRIGGER_WORDS
    triggered = _has_trigger_word(claim.lower(), words)

    if not triggered and require_trigger_word:
        return StopGateResult(passed=True, claim_triggered=False, evidence=evidence)

    legs = evidence.legs_present()
    missing = [leg for leg, present in legs.items() if not present]

    if missing:
        leg_descriptions = {
            "trigger": "Leg 1 (trigger): what fired under realistic conditions + timestamp",
            "effect": "Leg 2 (effect): expected effect on real system state, paste artifact slice",
            "consumer": "Leg 3 (consumer): downstream consumer can use the effect, paste result",
        }
        missing_desc = [leg_descriptions[m] for m in missing]
        block_reason = (
            f"STOP-GATE BLOCKED: claim '{claim[:80]}...' contains completion trigger "
            f"but is missing EPT evidence legs: {missing}. "
            f"Required: {'; '.join(missing_desc)}. "
            "Work is DEFERRED-AND-UNTESTED until all 3 legs are provided."
        )
        return StopGateResult(
            passed=False,
            block_reason=block_reason,
            missing_legs=missing,
            claim_triggered=triggered,
            evidence=evidence,
        )

    return StopGateResult(passed=True, missing_legs=[], claim_triggered=triggered, evidence=evidence)


def _has_trigger_word(text_lower: str, words: Iterable[str]) -> bool:
    """Return True if text_lower contains any completion trigger word."""
    for word in words:
        if " " in word:
            if word in text_lower:
                return True
        elif re.search(r"\b" + re.escape(word) + r"\b", text_lower):
            return True
    return False
