"""Canonical reader for delegation outcome ledgers.

Single point of sanitization for ``was_delegated`` consumers. Any script
that aggregates over ``cognitive-fitness.jsonl`` rows with
``system=="delegation"`` SHOULD use ``iter_delegation_events`` from this
module rather than re-implementing the filter logic inline.

WHY a shared lib: a producer regression (tool rename, schema drift, silent
no-op) can poison the ``was_delegated`` field for every row it writes. When
each consumer re-implements its own filter, fixing such a regression means
sweeping every consumer script; with this lib it is a one-line fix.

The library encapsulates THREE responsibilities:

1. **Quarantine filter** - skip rows carrying a data-quality quarantine
   flag (``quarantined: true``). When a producer bug is discovered after
   the fact, annotate the affected rows instead of deleting them; every
   consumer then excludes them automatically while the raw history stays
   auditable. Extend ``QUARANTINE_FLAGS`` to add further flags without
   re-touching consumers.

2. **Schema validation** - ``was_delegated`` MUST be Python ``bool`` or
   ``None`` (the legitimate "no marker" case). Integer 0/1 or string
   "true"/"false" indicate producer drift and must not flow through.
   Validation failures are logged via stderr (fail-open: the row is
   excluded silently from the caller's iteration).

3. **Producer-drift surveillance** - optional ``DriftCounter`` accumulates
   recent-window statistics (was_delegated True/False/None rates) that a
   drift scanner can read to detect producer regressions (the empirical
   signature is a True-rate collapsing to near-zero or jumping absurdly
   high).

USAGE::

    from scripts.lib.delegation_outcomes import iter_delegation_events

    for event in iter_delegation_events(COGNITIVE_FITNESS_PATH):
        # event is guaranteed clean: system=="delegation",
        # was_delegated is bool|None, not quarantined
        ...

OPT-OUT::

    # Diagnostic / audit-trail use case - keep quarantined rows:
    for event in iter_delegation_events(path, include_quarantined=True):
        ...
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional

# Rows where any of these top-level keys is exactly True are excluded from
# production iteration (data-quality quarantine; see module docstring #1).
QUARANTINE_FLAGS = ("quarantined",)


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not isinstance(ts, str):
        return None
    s = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_valid_was_delegated(value) -> bool:
    """``was_delegated`` MUST be Python ``bool`` (True/False) or ``None``.

    Integer 0/1 or string forms indicate producer drift - reject them
    silently to keep consumer aggregations honest. Caller must accept
    that drift produces gaps in the timeline; a drift scanner surfaces
    the gap to the operator.
    """
    return value is None or isinstance(value, bool)


def is_quarantined(row: Dict) -> bool:
    """True when the row carries any data-quality quarantine flag."""
    return any(row.get(flag) is True for flag in QUARANTINE_FLAGS)


def iter_delegation_events(
    path: Path,
    *,
    include_quarantined: bool = False,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    drift_counter: Optional["DriftCounter"] = None,
) -> Iterator[Dict]:
    """Yield validated, filtered delegation events from a fitness ledger.

    Args:
        path: Path to ``cognitive-fitness.jsonl`` (or any ledger with the
            same row shape). Missing file -> empty iteration (fail-open).
        include_quarantined: When True, yield rows carrying a quarantine
            flag (diagnostic use only). Default False (production use).
        since: Optional inclusive lower bound on event ``ts``.
        until: Optional exclusive upper bound on event ``ts``.
        drift_counter: Optional ``DriftCounter`` instance to receive
            per-row stats for surveillance. Counter is updated AFTER
            filtering, so clean-rows-only stats are accumulated.
    """
    if not path.exists():
        return
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if row.get("system") != "delegation":
                continue
            if not include_quarantined and is_quarantined(row):
                continue
            # Time window filter
            if since is not None or until is not None:
                ts = _parse_ts(row.get("ts"))
                if ts is None:
                    continue
                if since is not None and ts < since:
                    continue
                if until is not None and ts >= until:
                    continue
            # Schema validation: was_delegated must be bool|None
            details = row.get("details") or {}
            if isinstance(details, dict):
                wd = details.get("was_delegated")
                if not _is_valid_was_delegated(wd):
                    try:
                        print(
                            f"[delegation_outcomes] schema warning: "
                            f"was_delegated={wd!r} (type={type(wd).__name__}) "
                            f"in row ts={row.get('ts')!r}; row excluded.",
                            file=sys.stderr,
                        )
                    except Exception:  # noqa: BLE001 - fail-open
                        pass
                    continue
            if drift_counter is not None:
                drift_counter.observe(row)
            yield row


class DriftCounter:
    """Accumulate per-window stats on was_delegated true/false/none rates.

    Producer-drift surveillance: if the True rate collapses to near-zero
    (a silently-dead producer) or jumps absurdly high (an over-permissive
    new producer), a scanner can emit a warning.

    Thread-unsafe (intended for single-process scanner use).
    """

    def __init__(self):
        self.true_count = 0
        self.false_count = 0
        self.none_count = 0
        # Track first/last via parsed datetime (tz-normalized to UTC) so
        # tz-naive and tz-aware/Z-suffix timestamp forms compare correctly;
        # store the canonical ISO string of whichever row's parsed dt is
        # the actual extreme.
        self._first_dt: Optional[datetime] = None
        self._last_dt: Optional[datetime] = None
        self.first_ts: Optional[str] = None
        self.last_ts: Optional[str] = None

    def observe(self, row: Dict) -> None:
        details = row.get("details") or {}
        wd = details.get("was_delegated") if isinstance(details, dict) else None
        if wd is True:
            self.true_count += 1
        elif wd is False:
            self.false_count += 1
        else:
            self.none_count += 1
        ts = row.get("ts")
        if isinstance(ts, str):
            dt = _parse_ts(ts)
            if dt is not None:
                if self._first_dt is None or dt < self._first_dt:
                    self._first_dt = dt
                    self.first_ts = ts
                if self._last_dt is None or dt > self._last_dt:
                    self._last_dt = dt
                    self.last_ts = ts

    @property
    def total(self) -> int:
        return self.true_count + self.false_count + self.none_count

    @property
    def true_rate(self) -> float:
        """Fraction of rows with was_delegated=True over total observed.

        Returns 0.0 if no rows observed (caller decides how to handle).
        """
        return self.true_count / self.total if self.total else 0.0

    def as_dict(self) -> Dict:
        return {
            "total": self.total,
            "true": self.true_count,
            "false": self.false_count,
            "none": self.none_count,
            "true_rate": round(self.true_rate, 4),
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
        }


def collect_session_outcomes(
    path: Path,
    *,
    since: Optional[datetime] = None,
) -> List[Dict]:
    """Convenience: collect filtered delegation events into a list.

    Wraps ``iter_delegation_events`` for callers that need a materialized
    list (e.g. for sort/group-by operations).
    """
    return list(iter_delegation_events(path, since=since))
