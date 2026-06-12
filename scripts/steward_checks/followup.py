#!/usr/bin/env python3
"""Steward Check: Scheduled Follow-up Extractor.

Extracts overdue and upcoming scheduled-follow-up items from markdown files
under `_handoffs/` (and any configured follow-up source dir). A follow-up is a
line carrying a configurable marker keyword (default: "follow-up" / "followup")
immediately followed by a target date YYYY-MM-DD. Severity is assigned by
days-overdue.

This is the genericized form of an upstream "Wiedervorlage" extractor: the
CC-session-TaskList plumbing (reading task_reminder events out of session JSONL)
is upstream-specific and was dropped; lite scans the user's own markdown
follow-up notes instead. The marker keyword list is configurable in
`_graph/cache/steward-config.json` (followup_marker_keywords).

Fail-open: empty/absent sources -> zero findings (cold-baseline safe).

Severity rules (days_overdue = today - target_date):
  dso < -window   : skipped (too-far-future noise)
  -window..-1     : P3 (upcoming)
  0               : P2 (due today)
  1..3            : P2 (recently overdue)
  4+              : P1 (over a few days stale)

Public API for hook consumption:
  run_check(repo_root, today=None) -> CheckResult
"""

from __future__ import annotations

import argparse
import re
import signal
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

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

MODULE_NAME = "followup"
HARD_TIMEOUT_S = 30

# Explicit resolution markers that flag a follow-up line as DONE (so a handoff
# noting a completed follow-up is not re-surfaced). Conservative: bare prose
# ("resolved"/"done") is NOT matched, so "to be resolved at follow-up X" still
# surfaces; only a completed checkbox, the check emoji, or a closed bracketed
# status tag suppresses.
RESOLUTION_MARKER_RE = re.compile(
    r"\[[xX]\]|✅|\[(?:RESOLVED|CLOSED|DONE)\b[^\[\]]*\]", re.IGNORECASE
)


def build_marker_re(keywords: list[str]) -> re.Pattern[str]:
    """Compile a regex matching any configured marker keyword followed by a
    YYYY-MM-DD date (allowing whitespace, '#', ':' between)."""
    alts = "|".join(re.escape(k) for k in keywords if k)
    if not alts:
        alts = "follow-up|followup"
    return re.compile(rf"(?:{alts})[s]?[\s:#]*(\d{{4}}-\d{{2}}-\d{{2}})", re.IGNORECASE)


def parse_target_date(text: str, marker_re: re.Pattern[str]) -> Optional[date]:
    """Find the YYYY-MM-DD following a marker keyword in `text`."""
    if not text:
        return None
    m = marker_re.search(text)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except (ValueError, TypeError):
        return None


def severity_from_days(days_overdue: int, upcoming_window_days: int) -> Optional[Severity]:
    """Map days-overdue to severity. None = outside the window (too-far-future)."""
    if days_overdue < -upcoming_window_days:
        return None
    if days_overdue < 0:
        return Severity.P3
    if days_overdue <= 3:
        return Severity.P2
    return Severity.P1


def _format_title(text: str, days_overdue: int, marker_keywords: list[str]) -> str:
    """Strip markdown markers + the follow-up prefix for a clean title."""
    cleaned = text.strip()
    cleaned = re.sub(r"^[\-\*\+\|]+\s*", "", cleaned)
    cleaned = re.sub(r"^\[[xX ]\]\s*", "", cleaned)
    cleaned = re.sub(r"^#\d+\s+", "", cleaned)
    alts = "|".join(re.escape(k) for k in marker_keywords if k) or "follow-up"
    cleaned = re.sub(
        rf"^(?:{alts})[s]?\s+#?\d*\s*\d{{4}}-\d{{2}}-\d{{2}}[:\s]*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.strip()
    if len(cleaned) > 100:
        cleaned = cleaned[:97] + "..."
    if days_overdue > 0:
        return f"Follow-up overdue {days_overdue}d: {cleaned}"
    if days_overdue == 0:
        return f"Follow-up due today: {cleaned}"
    return f"Follow-up upcoming in {-days_overdue}d: {cleaned}"


def scan_followup_dir(
    source_dir: Path,
    today: date,
    marker_re: re.Pattern[str],
    marker_keywords: list[str],
    upcoming_window_days: int,
    lookback_days: int,
) -> list[StewardFinding]:
    """Scan *.md files (non-recursive) under source_dir for follow-up markers.

    Limited to files modified within lookback_days. Never raises.
    """
    findings: list[StewardFinding] = []
    try:
        if not source_dir.exists() or not source_dir.is_dir():
            return []
        cutoff_ord = (today - timedelta(days=lookback_days)).toordinal()
        lowered_keywords = [k.lower() for k in marker_keywords if k]
        for md_file in sorted(source_dir.glob("*.md")):
            if md_file.name.startswith("."):
                continue  # skip ephemeral rolling files (.session-journal.md etc.)
            try:
                mtime_ord = datetime.fromtimestamp(md_file.stat().st_mtime).date().toordinal()
                if mtime_ord < cutoff_ord:
                    continue
                content = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in content.splitlines():
                low = line.lower()
                if not any(k in low for k in lowered_keywords):
                    continue
                target = parse_target_date(line, marker_re)
                if target is None:
                    continue
                days_overdue = (today - target).days
                severity = severity_from_days(days_overdue, upcoming_window_days)
                if severity is None:
                    continue
                if RESOLUTION_MARKER_RE.search(line):
                    continue
                try:
                    source_path = str(md_file.relative_to(REPO_ROOT))
                except ValueError:
                    source_path = str(md_file)
                findings.append(
                    StewardFinding(
                        module=MODULE_NAME,
                        severity=severity,
                        title=_format_title(line.strip(), days_overdue, marker_keywords),
                        detail=(
                            f"Found in {md_file.name}: due {target}, "
                            f"{days_overdue}d overdue" if days_overdue > 0
                            else f"Found in {md_file.name}: due {target}"
                        ),
                        source=source_path,
                        item_id=f"{md_file.stem}:{target.isoformat()}",
                        days_overdue=days_overdue,
                    )
                )
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, f"scan_followup_dir: {source_dir}")
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
    keywords = list(cfg["followup_marker_keywords"])
    marker_re = build_marker_re(keywords)

    start = time.perf_counter()
    error_msg: Optional[str] = None
    findings: list[StewardFinding] = []
    try:
        findings = scan_followup_dir(
            repo_root / "_handoffs",
            today,
            marker_re,
            keywords,
            upcoming_window_days=int(cfg["followup_upcoming_window_days"]),
            lookback_days=int(cfg["followup_lookback_days"]),
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
        prog="followup",
        description="Steward check: extract overdue/upcoming scheduled follow-ups",
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
