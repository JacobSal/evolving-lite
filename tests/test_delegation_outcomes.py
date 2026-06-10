"""Unit tests for scripts/lib/delegation_outcomes.py (canonical ledger reader).

The lib is the single point of sanitization for delegation-outcome consumers:
quarantine-flag filtering, was_delegated schema validation, and drift
surveillance. Tests are pure in-process (no subprocess, no plugin tree).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.lib.delegation_outcomes import (  # noqa: E402
    DriftCounter,
    _is_valid_was_delegated,
    collect_session_outcomes,
    iter_delegation_events,
)


def _row(**over):
    base = {
        "ts": "2026-06-10T12:00:00Z",
        "system": "delegation",
        "entity": "exploration",
        "domain": "exploration",
        "outcome": "positive",
        "details": {"was_delegated": True, "score": 5.0, "threshold": 3.0},
    }
    base.update(over)
    return base


def _write_ledger(tmp_path, rows):
    p = tmp_path / "cognitive-fitness.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


class TestWasDelegatedValidation:
    def test_bools_and_none_valid(self):
        assert _is_valid_was_delegated(True)
        assert _is_valid_was_delegated(False)
        assert _is_valid_was_delegated(None)

    def test_producer_drift_forms_invalid(self):
        assert not _is_valid_was_delegated(1)
        assert not _is_valid_was_delegated(0)
        assert not _is_valid_was_delegated("true")
        assert not _is_valid_was_delegated("False")
        assert not _is_valid_was_delegated(1.0)


class TestIterDelegationEvents:
    def test_missing_file_yields_nothing(self, tmp_path):
        assert list(iter_delegation_events(tmp_path / "absent.jsonl")) == []

    def test_yields_clean_rows_only(self, tmp_path):
        rows = [
            _row(),
            _row(system="lens"),  # wrong system
            _row(quarantined=True),  # data-quality quarantine flag
            _row(details={"was_delegated": 1}),  # producer drift
        ]
        path = _write_ledger(tmp_path, rows)
        got = list(iter_delegation_events(path))
        assert len(got) == 1
        assert got[0]["details"]["was_delegated"] is True

    def test_include_quarantined_optin(self, tmp_path):
        path = _write_ledger(tmp_path, [_row(), _row(quarantined=True)])
        assert len(list(iter_delegation_events(path))) == 1
        assert len(list(iter_delegation_events(path, include_quarantined=True))) == 2

    def test_malformed_lines_skipped(self, tmp_path):
        p = tmp_path / "ledger.jsonl"
        p.write_text(json.dumps(_row()) + "\nNOT-JSON{{{\n\n")
        assert len(list(iter_delegation_events(p))) == 1

    def test_time_window(self, tmp_path):
        rows = [
            _row(ts="2026-06-01T00:00:00Z"),
            _row(ts="2026-06-05T00:00:00Z"),
            _row(ts="2026-06-09T00:00:00Z"),
        ]
        path = _write_ledger(tmp_path, rows)
        since = datetime(2026, 6, 2, tzinfo=timezone.utc)
        until = datetime(2026, 6, 8, tzinfo=timezone.utc)
        got = list(iter_delegation_events(path, since=since, until=until))
        assert [r["ts"] for r in got] == ["2026-06-05T00:00:00Z"]

    def test_collect_session_outcomes_materializes(self, tmp_path):
        path = _write_ledger(tmp_path, [_row(), _row()])
        assert len(collect_session_outcomes(path)) == 2


class TestDriftCounter:
    def test_counts_and_rate(self, tmp_path):
        rows = [
            _row(details={"was_delegated": True}),
            _row(details={"was_delegated": False}),
            _row(details={"was_delegated": None}),
            _row(details={"was_delegated": True}),
        ]
        path = _write_ledger(tmp_path, rows)
        counter = DriftCounter()
        list(iter_delegation_events(path, drift_counter=counter))
        d = counter.as_dict()
        assert d["total"] == 4
        assert d["true"] == 2 and d["false"] == 1 and d["none"] == 1
        assert d["true_rate"] == 0.5

    def test_ts_extremes_tz_safe(self, tmp_path):
        rows = [
            _row(ts="2026-06-05T00:00:00Z"),
            _row(ts="2026-06-01T00:00:00+00:00"),
            _row(ts="2026-06-09T00:00:00Z"),
        ]
        path = _write_ledger(tmp_path, rows)
        counter = DriftCounter()
        list(iter_delegation_events(path, drift_counter=counter))
        assert counter.first_ts == "2026-06-01T00:00:00+00:00"
        assert counter.last_ts == "2026-06-09T00:00:00Z"
