"""Verification + safety spine path registry - Invariant B enforcement.

This module is the single source of truth for "what lives OUTSIDE the
autonomous session's self-modification scope". A self-improving system that
can edit its own verifier or guardrail can degrade it; the spine is the set of
paths that the self-* actuators must classify INTERACTIVE (never AUTONOMOUS) so
that a change to them always requires a human.

SAFETY SPINE INVARIANT: this module lives inside the spine it protects
(scripts/lib/verifier/) and lists itself. No autonomous session may modify it.

Consumers:
    from scripts.lib.verifier.spine import is_spine_path
    if is_spine_path(finding.get("source", "")):
        return AutonomyClass.INTERACTIVE

Cross-repo: SPINE_PATH_PATTERNS is the DEFAULT set for this plugin; callers may
pass their own pattern list to is_spine_path()/first_spine_match() to extend or
replace it. Patterns are matched with re.search against a REPO_ROOT-relative or
absolute path string, so a leading repo prefix is fine.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

# Authoritative spine path patterns for evolving-lite. Each entry protects one
# load-bearing piece of the verification/autonomy spine.
SPINE_PATH_PATTERNS: tuple[str, ...] = (
    # The verifier harness itself (spine registry, stop gate, and any verdict
    # engine added later) + its tests.
    r"scripts/lib/verifier/",
    r"tests/test_verifier_",
    r"tests/test_stop_gate",
    r"tests/test_spine",
    # The live Stop-gate hook.
    r"hooks/scripts/forced-verify-stop-gate\.py",
    # The autonomous-session infrastructure (lease / governor / producer) -
    # editing these could let a session extend its own lease or forge its queue.
    r"scripts/autonom/",
    r"tests/test_autonom_",
    # The actuator that ENFORCES this invariant - if a session could rewrite it,
    # it could remove the guard. Self-protecting.
    r"scripts/steward_actuator\.py",
)

_COMPILED: tuple[re.Pattern[str], ...] = tuple(re.compile(p) for p in SPINE_PATH_PATTERNS)


def _compile(patterns: Optional[Iterable[str]]) -> tuple[re.Pattern[str], ...]:
    if patterns is None:
        return _COMPILED
    return tuple(re.compile(p) for p in patterns)


def is_spine_path(path_str: str, patterns: Optional[Iterable[str]] = None) -> bool:
    """Return True if path_str touches the verification/safety spine.

    Args:
        path_str: A file path (REPO_ROOT-relative or absolute). Empty/None-ish
            input returns False (fail-open: an unresolvable path is not treated
            as spine, so the caller's other rules still apply).
        patterns: Optional caller-supplied pattern list to use instead of the
            module default (cross-repo extension seam). None = the default set.

    Returns:
        True if the path matches any spine pattern.
    """
    if not path_str:
        return False
    text = str(path_str)
    return any(pat.search(text) for pat in _compile(patterns))


def first_spine_match(path_str: str, patterns: Optional[Iterable[str]] = None) -> Optional[str]:
    """Return the first matching spine pattern for diagnostics, or None."""
    if not path_str:
        return None
    text = str(path_str)
    for pat in _compile(patterns):
        if pat.search(text):
            return pat.pattern
    return None
