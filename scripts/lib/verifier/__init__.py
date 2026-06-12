"""Evolving Lite verification + safety spine (loop-closure subset).

This package ships the two load-bearing pieces that CLOSE the self-* loop:
  - spine.py     : the safety-spine path registry (Invariant B). The steward
                   actuator imports is_spine_path from here; its presence flips
                   the actuator from fail-closed (nothing auto-acted) to live
                   per-path classification.
  - stop_gate.py : the EPT Stop-gate (non-skippable 3-leg completion proof),
                   consumed by hooks/scripts/forced-verify-stop-gate.py.

The cost-tiered adversarial VERDICT engine (deterministic / risk_classifier /
llm_judge) and the judge-calibration instrument are a SEPARATE verification-
harness slice - they are the RC grading tool, not a hop on the self-* loop - and
are intentionally NOT imported here so the actuator's spine-import path stays
dependency-free.

SAFETY SPINE INVARIANT: no autonomous session may modify this package or its
tests. Any change requires explicit human review.
"""

from .spine import SPINE_PATH_PATTERNS, first_spine_match, is_spine_path
from .stop_gate import EPTEvidence, StopGateResult, check_stop_gate

__all__ = [
    "SPINE_PATH_PATTERNS",
    "first_spine_match",
    "is_spine_path",
    "EPTEvidence",
    "StopGateResult",
    "check_stop_gate",
]
