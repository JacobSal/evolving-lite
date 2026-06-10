"""session_attribution.py - shared session-id resolution + row/doc attribution.

Lifts ``_resolve_session_id`` out of ``hook_telemetry`` so non-context-manager
callers (the new tmp-archiver, future ambient writers, decision-md generators,
session-end staging routines) have one canonical resolver instead of grepping
the cascade pattern across 5+ files.

Two naming conventions coexist in production ledger rows:

  * ``session``    - hook_telemetry library writers (hook-invocations,
                     lens-fitness-drainer, delegation-outcome-tracker)
  * ``session_id`` - pipeline writers (status-aggregator -> _stale.jsonl)

Consumers reading these ledgers must accept BOTH conventions or they silently
under-count. ``normalize_session_key()`` is the safety helper for that.

API
---

  * ``resolve_session_id(input_data, fallback)`` - Cascade
    ``input_data['session_id'|'session']`` -> ``$CLAUDE_SESSION_ID`` ->
    ``f"pid-{getppid()}"``. Used at write-time when wiring a new ledger.

  * ``normalize_session_key(row)`` - Read-time canonicalization. If either
    ``session`` or ``session_id`` is non-empty in the row, both keys are
    populated with the canonical value (preferring ``session`` if both
    exist and differ - that's the hook_telemetry-precedence rule).
    Idempotent. Never deletes data.

  * ``attribute_row(row, session_id, input_data)`` - Write-time inject.
    Sets ``row["session"]`` if currently absent/empty. Resolves session_id
    via ``resolve_session_id()`` cascade if not passed explicitly. Returns
    row (mutated in place + returned for chaining).

  * ``attribute_decision_md(md_body, session_id)`` - Inject
    ``session_id: <value>`` into the YAML frontmatter of a generated
    decision document. Creates frontmatter if absent. Idempotent.

  * ``get_unknown_session_id()`` - Deterministic bucket name for files
    whose session_id is unrecoverable. Used by the /tmp archiver when
    extracting session-id from filename returns no match.

Design constraints
------------------

* Fail-open is NOT this module's contract - resolvers must always return a
  string (the ``"unknown"`` final fallback covers that). Callers should
  treat the return value as authoritative.
* No I/O. Pure-function helpers. Tests can run without filesystem.
* Stdlib-only. Importable from any hook.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional


UNKNOWN_SESSION_PREFIX = "unknown-session"
CANONICAL_KEY = "session"
ALTERNATE_KEY = "session_id"


def resolve_session_id(
    input_data: Optional[Dict[str, Any]] = None,
    fallback: Optional[str] = None,
) -> str:
    """Cascade-resolve session_id.

    Order:
      1. ``input_data['session_id']`` or ``input_data['session']`` if dict.
      2. ``$CLAUDE_SESSION_ID`` env var.
      3. ``fallback`` arg if provided (caller's last-resort suggestion).
      4. ``pid-{getppid()}``.
      5. ``"unknown"`` (terminal, should be unreachable but kept for safety).

    Extends ``scripts/hook_telemetry._resolve_session_id`` with the optional
    ``fallback`` arg between env and pid levels. NOT a drop-in replacement
    for the private original (the original has no fallback level): same row
    in same context produces same session_id only when ``fallback=None``.
    Cross-hook rows agree on session attribution under the input-data + env
    branches (the most common cases).
    """
    sid: Optional[str] = None
    if isinstance(input_data, dict):
        sid = input_data.get("session_id") or input_data.get("session")
    if not sid:
        sid = os.environ.get("CLAUDE_SESSION_ID")
    if not sid and fallback:
        sid = fallback
    if not sid:
        sid = f"pid-{os.getppid()}"
    return sid or "unknown"


def normalize_session_key(row: Dict[str, Any]) -> Dict[str, Any]:
    """Read-time canonicalization across ``session`` / ``session_id``.

    Producer-side schema completeness != consumer-side query correctness
    (schema-inconsistency hazard). A consumer ``select(.session_id
    != null)`` would silently miss rows where producer used ``session``,
    and vice-versa.

    Behavior:
      * If neither key is present (or both empty/None) - no-op.
      * If only one key is non-empty - populate the OTHER key with the
        same value. Both keys end up identical.
      * If both keys are present and equal - no-op.
      * If both are present but differ - ``session`` wins (hook_telemetry
        precedence); ``session_id`` gets rewritten.

    Mutates ``row`` in place AND returns it (chain-friendly).
    """
    if not isinstance(row, dict):
        return row
    s = row.get(CANONICAL_KEY)
    sid = row.get(ALTERNATE_KEY)
    s_present = isinstance(s, str) and s
    sid_present = isinstance(sid, str) and sid
    if not s_present and not sid_present:
        return row
    if s_present and not sid_present:
        row[ALTERNATE_KEY] = s
        return row
    if sid_present and not s_present:
        row[CANONICAL_KEY] = sid
        return row
    # both present
    if s == sid:
        return row
    # KNOWN OVERWRITE: when both keys differ, ``session_id`` gets rewritten
    # to ``session``'s value (hook_telemetry precedence). Add producers HERE
    # if they treat session_id as authoritative AND have a downstream
    # consumer that would silently diverge.
    row[ALTERNATE_KEY] = s
    return row


def attribute_row(
    row: Dict[str, Any],
    session_id: Optional[str] = None,
    input_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write-time inject ``session`` (canonical key) into a row.

    If ``row[CANONICAL_KEY]`` is already non-empty, no-op (idempotent).
    Otherwise resolves session_id via ``resolve_session_id(input_data)``
    unless an explicit ``session_id`` is passed.

    Returns ``row`` (mutated in place + returned for chaining).
    """
    if not isinstance(row, dict):
        return row
    existing = row.get(CANONICAL_KEY)
    if isinstance(existing, str) and existing:
        return row  # idempotent
    sid = session_id or resolve_session_id(input_data)
    row[CANONICAL_KEY] = sid
    return row


_SESSION_ID_LINE_RE = re.compile(r"^session_id:", re.MULTILINE)


def attribute_decision_md(md_body: str, session_id: str) -> str:
    """Inject ``session_id: <value>`` into the YAML frontmatter of a
    decision-md generated by the /knowledge/decisions pipeline.

    Behavior:
      * If no frontmatter (no leading ``---`` line) - prepend a fresh
        frontmatter block.
      * If frontmatter exists AND already has ``session_id:`` line -
        no-op (idempotent).
      * If frontmatter exists AND lacks ``session_id:`` - insert the
        line immediately after the opening ``---``.

    Returns the modified markdown string. Does NOT validate that
    ``session_id`` looks like a UUID (caller's responsibility).
    """
    if not isinstance(md_body, str):
        return md_body  # defensive; non-str = pass-through
    if not session_id:
        return md_body  # don't inject empty
    # Already has session_id in frontmatter -> idempotent no-op.
    if _SESSION_ID_LINE_RE.search(md_body):
        return md_body
    # Detect existing frontmatter (open delim must be on line 1 OR
    # immediately preceded by start-of-string).
    if md_body.startswith("---\n") or md_body.startswith("---\r\n"):
        # Find end of opening delim line.
        first_nl = md_body.find("\n")
        if first_nl == -1:
            return md_body  # malformed
        head = md_body[: first_nl + 1]
        rest = md_body[first_nl + 1 :]
        injection = f"session_id: {session_id}\n"
        return head + injection + rest
    # No frontmatter -> prepend a fresh one.
    return f"---\nsession_id: {session_id}\n---\n\n{md_body}"


def get_unknown_session_id(archive_ts: Optional[str] = None) -> str:
    """Deterministic bucket name for files whose session_id is
    unrecoverable. Used by the /tmp archiver.

    Default ``archive_ts`` = current UTC ISO timestamp. Tests can pin it.
    """
    ts = archive_ts or datetime.now(timezone.utc).isoformat()
    return f"{UNKNOWN_SESSION_PREFIX}-{ts}"


__all__ = [
    "UNKNOWN_SESSION_PREFIX",
    "CANONICAL_KEY",
    "ALTERNATE_KEY",
    "resolve_session_id",
    "normalize_session_key",
    "attribute_row",
    "attribute_decision_md",
    "get_unknown_session_id",
]
