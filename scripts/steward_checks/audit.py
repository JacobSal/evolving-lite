#!/usr/bin/env python3
"""Steward Check: Audit Freshness.

Surfaces stale-audit findings by file-age inspection of an `audit-reports/*.md`
directory (configurable). File-age only; no subprocess.

Cold-baseline rule (the key genericization vs upstream): on a FRESH install with
no audit reports yet, this emits NO finding when `audit_never_audited_is_ok` is
True (the default). "Never audited" is the expected state of a new repo, not a
problem - emitting a finding there would create a cold-baseline false-positive
storm and break the steward's "zero findings on a clean repo" contract.

Severity rules (P0 reserved for security per common.py):
  - No audit report files found, never_audited_is_ok=True   -> NO finding (cold)
  - No audit report files found, never_audited_is_ok=False  -> P2 ("never audited")
  - Latest report older than threshold (default 8d)         -> P2 ("stale")
  - Latest report within threshold                          -> NO finding (fresh)

Public API for hook consumption:
  run_check(repo_root, today=None) -> CheckResult
"""

from __future__ import annotations

import argparse
import re
import signal
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

# Make the steward_checks package importable when run as a script.
_HERE = Path(__file__).parent.resolve()
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from steward_checks.common import (  # noqa: E402
    REPO_ROOT,
    CheckResult,
    Severity,
    StewardFinding,
    add_argparse_output_flags,
    load_steward_config,
    render_output,
    utc_now_iso,
    write_failure_ledger,
)

MODULE_NAME = "audit"
HARD_TIMEOUT_S = 30

# Date regex YYYY-MM-DD anywhere in a filename.
FILENAME_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def find_latest_audit_report(audit_reports_dir: Path) -> Optional[tuple[Path, date]]:
    """Return (path, parsed_date) of the newest report by date-in-filename.

    Falls back to mtime-based newest if no filename carries a parseable date.
    Returns None if the directory is missing or empty. Never raises.
    """
    try:
        if not audit_reports_dir.exists() or not audit_reports_dir.is_dir():
            return None
        candidates: list[tuple[Path, Optional[date], float]] = []
        for entry in audit_reports_dir.iterdir():
            if not entry.is_file() or entry.suffix != ".md":
                continue
            parsed_date: Optional[date] = None
            m = FILENAME_DATE_RE.search(entry.name)
            if m:
                try:
                    parsed_date = date.fromisoformat(m.group(1))
                except ValueError:
                    parsed_date = None
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            candidates.append((entry, parsed_date, mtime))
        if not candidates:
            return None
        dated = [(p, d, m) for p, d, m in candidates if d is not None]
        if dated:
            dated.sort(key=lambda t: t[1], reverse=True)
            chosen, d, _ = dated[0]
            return (chosen, d)
        candidates.sort(key=lambda t: t[2], reverse=True)
        chosen, _, mtime = candidates[0]
        return (chosen, datetime.fromtimestamp(mtime).date())
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, f"find_latest_audit_report: {audit_reports_dir}")
        return None


def check_audit_freshness(
    repo_root: Path,
    today: date,
    audit_reports_dirname: str,
    stale_threshold_days: int,
    never_audited_is_ok: bool,
) -> list[StewardFinding]:
    """Inspect the audit-reports dir and emit freshness findings. Never raises."""
    findings: list[StewardFinding] = []
    audit_dir = repo_root / audit_reports_dirname
    try:
        latest = find_latest_audit_report(audit_dir)
        if latest is None:
            if never_audited_is_ok:
                # Cold-baseline: a fresh repo has never been audited. That is the
                # expected state, not a finding. Stay silent.
                return findings
            findings.append(StewardFinding(
                module=MODULE_NAME,
                severity=Severity.P2,
                title="No audit reports found",
                detail=(
                    f"Directory {audit_reports_dirname}/ is missing or empty. "
                    "Run an audit to produce a baseline report."
                ),
                source=f"{audit_reports_dirname}/",
            ))
            return findings
        report_path, report_date = latest
        days_overdue = (today - report_date).days
        try:
            source = str(report_path.relative_to(repo_root))
        except ValueError:
            source = str(report_path)
        if days_overdue > stale_threshold_days:
            findings.append(StewardFinding(
                module=MODULE_NAME,
                severity=Severity.P2,
                title=f"Audit reports stale ({days_overdue}d old)",
                detail=(
                    f"Latest report: {report_path.name} ({report_date}). "
                    f"Threshold: {stale_threshold_days}d. Run an audit."
                ),
                source=source,
                item_id=report_path.name,
                days_overdue=days_overdue,
            ))
        # Within threshold -> fresh -> no finding (was P3 informational upstream;
        # dropped so a healthy repo reports zero findings, not noise).
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, "check_audit_freshness")
    return findings


def run_check(
    repo_root: Optional[Path] = None,
    today: Optional[date] = None,
) -> CheckResult:
    """Entry point for the steward-checker hook + CLI. Never raises."""
    if repo_root is None:
        repo_root = REPO_ROOT
    if today is None:
        today = date.today()
    cfg = load_steward_config(repo_root)

    start = time.perf_counter()
    error_msg: Optional[str] = None
    findings: list[StewardFinding] = []
    try:
        findings = check_audit_freshness(
            repo_root,
            today,
            audit_reports_dirname=cfg["audit_reports_dirname"],
            stale_threshold_days=int(cfg["audit_stale_threshold_days"]),
            never_audited_is_ok=bool(cfg["audit_never_audited_is_ok"]),
        )
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, "run_check outer")
        error_msg = f"{type(e).__name__}: {e}"

    duration_ms = (time.perf_counter() - start) * 1000.0
    return CheckResult(
        module=MODULE_NAME,
        run_at=utc_now_iso(),
        duration_ms=duration_ms,
        findings=findings,
        error=error_msg,
    )


def _install_timeout(seconds: int = HARD_TIMEOUT_S) -> None:
    def _handler(signum, frame):
        sys.stderr.write(f"[{MODULE_NAME}] HARD TIMEOUT after {seconds}s\n")
        sys.exit(124)
    try:
        signal.signal(signal.SIGALRM, _handler)
        signal.alarm(seconds)
    except (AttributeError, ValueError):
        pass


def main() -> int:
    _install_timeout()
    parser = argparse.ArgumentParser(
        prog="audit",
        description="Steward check: audit-report freshness (file-age only)",
    )
    add_argparse_output_flags(parser)
    parser.add_argument(
        "--today", type=str, default=None,
        help="Override today's date (YYYY-MM-DD); for tests/replay",
    )
    args = parser.parse_args()

    today_override: Optional[date] = None
    if args.today:
        try:
            today_override = date.fromisoformat(args.today)
        except ValueError:
            sys.stderr.write(f"Invalid --today value: {args.today}\n")
            return 2

    result = run_check(today=today_override)
    print(render_output(result, human=args.human))
    return 0


if __name__ == "__main__":
    sys.exit(main())
