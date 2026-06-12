#!/usr/bin/env python3
"""SessionStart hook: consolidated steward checker.

Date-routed dispatch across the steward check modules plus a false-completion
scanner and a parallel-session race detector. Surfaces the Top-N P0/P1 findings
as additionalContext without blocking the SessionStart chain, and appends every
finding to _inbox/steward-findings.jsonl (the steward_actuator's input).

Branches:
  1. ALWAYS   - followup.run_check        (overdue + upcoming scheduled follow-ups)
  2. Monday   - audit.run_check           (audit-report freshness, throttled > 6d)
  3. 1st-of-month - retirement.run_check  (dead-hook candidates, throttled > 25d)
  4. ALWAYS   - plan-rot                   (active plan untouched > N days)
  5. ALWAYS   - false-completion scan      (handoffs claiming done without evidence)
  6. ALWAYS   - parallel-session scan      (concurrent CC sessions = race risk)

Fail-open contract: every branch is try/except-wrapped; failures flow to
_ledgers/steward-failures.jsonl. The hook ALWAYS exits 0.

Cold-baseline: on a fresh repo every branch returns zero findings (no audit
reports -> never-audited-is-ok, no follow-up markers, no active plan, no
handoffs, no parallel sessions).
"""

from __future__ import annotations

import datetime
import fcntl
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path setup (before project-module imports)
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent           # hooks/scripts/
_CODE_ROOT = SCRIPT_DIR.parent.parent                  # hooks/ -> plugin root (code)


def _plugin_root() -> Path:
    """Data root (caches, ledgers, handoffs). Env-overridable for tests / multi
    -root installs; defaults to the code root."""
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return _CODE_ROOT


REPO_ROOT = _plugin_root()

# CODE imports resolve from the real code location (next to this file), NOT the
# data root, so a test/multi-root install with CLAUDE_PLUGIN_ROOT pointed at a
# different data dir still imports the shipped modules. hooks/scripts first (for
# `lib.steward_routing`); scripts/ for the steward_checks package; scripts/lib
# for hook_telemetry.
# steward_routing imported by its unique top-level name (NOT `lib.steward_routing`)
# to avoid colliding with scripts/lib, which is also a package named `lib`.
for _p in (str(SCRIPT_DIR / "lib"), str(_CODE_ROOT / "scripts"), str(_CODE_ROOT / "scripts" / "lib")):
    if _p not in sys.path:
        sys.path.append(_p)

from steward_routing import marker_is_old, write_throttle_marker  # noqa: E402
from steward_checks import audit, followup, retirement  # noqa: E402
from steward_checks.common import (  # noqa: E402
    SCHEMA_VERSION,
    Severity,
    StewardFinding,
    load_steward_config,
    utc_now_iso,
    write_failure_ledger,
)

MODULE_NAME = "steward-checker"

FINDINGS_OUT = REPO_ROOT / "_inbox" / "steward-findings.jsonl"
MARKER_AUDIT = REPO_ROOT / "_graph" / "cache" / "steward-audit-marker.json"
MARKER_RETIRE = REPO_ROOT / "_graph" / "cache" / "steward-retirement-marker.json"

AUDIT_THROTTLE_DAYS = 6
RETIRE_THROTTLE_DAYS = 25
PLAN_ROT_STALE_DAYS = 7

FALSE_COMPLETION_LOOKBACK_DAYS = 30
FALSE_COMPLETION_MAX_FILES = 50
FALSE_COMPLETION_MAX_BYTES_PER_FILE = 200_000

TOP_N_FINDINGS = 3
SYSTEM_MESSAGE_MAX_CHARS = 800

SEVERITY_RANK = {Severity.P0: 0, Severity.P1: 1, Severity.P2: 2, Severity.P3: 3}

# Completion-claim keywords (ReDoS-safe alternation).
COMPLETION_RE = re.compile(
    r"\b(done|shipped|complete|completed|verified|live|deployed|passing|green)\b",
    re.IGNORECASE,
)
# 3-leg evidence markers (trigger / effect / consumer), inflected forms included.
EVIDENCE_RE = re.compile(
    r"\b(trigger(?:ed|s|ing)?|effect(?:s|ed|ing)?|consum(?:e|es|ed|ing|er|ers|ption))\b",
    re.IGNORECASE,
)
# Explicit empirical-completion methodology markers: a handoff that references
# the methodology directly has demonstrated outcome-evidence even without the
# literal trigger+effect+consumer trigram.
METHODOLOGY_EVIDENCE_RE = re.compile(
    r"\b(?:deferred[- ]and[- ]untested|deferred\s*&\s*untested|3[- ]leg|empirical)\b"
    r"|\b(?:EPT|ECP)\b[ \-:]{0,3}(?:proof|proven|evidence|closed|gate|pass(?:ed|ing)?|verif\w*|done|complete|leg)\b"
    r"|(?:3[- ]leg|proof|proven|evidence|closed|done|complete|verif\w*|leg)[ \-:]{0,3}\b(?:EPT|ECP)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Branch runners (each try/except wrapped + fail-open)
# ---------------------------------------------------------------------------

def run_followup(today: datetime.date) -> list[StewardFinding]:
    try:
        return list(followup.run_check(repo_root=REPO_ROOT, today=today).findings)
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, "run_followup")
        return []


def run_audit_if_due(today: datetime.date) -> list[StewardFinding]:
    if today.weekday() != 0:
        return []
    if not marker_is_old(MARKER_AUDIT, AUDIT_THROTTLE_DAYS):
        return []
    try:
        result = audit.run_check(repo_root=REPO_ROOT, today=today)
        write_throttle_marker(MARKER_AUDIT)
        return list(result.findings)
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, "run_audit_if_due")
        return []


def run_retirement_if_due(today: datetime.date) -> list[StewardFinding]:
    if today.day != 1:
        return []
    if not marker_is_old(MARKER_RETIRE, RETIRE_THROTTLE_DAYS):
        return []
    try:
        result = retirement.run_check(repo_root=REPO_ROOT, today=today)
        write_throttle_marker(MARKER_RETIRE)
        return list(result.findings)
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, "run_retirement_if_due")
        return []


def run_plan_rot(today: datetime.date) -> list[StewardFinding]:
    """Flag an active plan untouched > PLAN_ROT_STALE_DAYS. Reads the active
    plan ref from _memory/index.json (tolerant of both an `active_plan` top-level
    key and an `active_context.active_plan` nested key). Cold-quiet when neither
    is present (the lite default). Returns [] on any failure."""
    try:
        import subprocess

        index_path = REPO_ROOT / "_memory" / "index.json"
        try:
            data = json.loads(index_path.read_text())
        except (json.JSONDecodeError, OSError):
            return []
        plan_rel = data.get("active_plan") or (
            (data.get("active_context", {}) or {}).get("active_plan")
        )
        if not plan_rel:
            return []
        plan_path = REPO_ROOT / plan_rel
        if not plan_path.is_file():
            return []
        try:
            file_age = (today - datetime.date.fromtimestamp(plan_path.stat().st_mtime)).days
        except OSError:
            file_age = -1
        commit_age = -1
        try:
            r = subprocess.run(
                ["git", "log", "-1", "--format=%aI", "--", str(plan_path)],
                capture_output=True, text=True, timeout=5, cwd=str(REPO_ROOT),
            )
            if r.returncode == 0 and r.stdout.strip():
                cd = datetime.datetime.fromisoformat(r.stdout.strip())
                commit_age = (datetime.datetime.now(cd.tzinfo) - cd).days
        except (subprocess.TimeoutExpired, ValueError, OSError):
            commit_age = -1
        ages = [a for a in (file_age, commit_age) if a >= 0]
        if not ages:
            return []
        effective_age = min(ages)
        if effective_age < PLAN_ROT_STALE_DAYS:
            return []
        return [
            StewardFinding(
                module="plan-rot",
                severity=Severity.P1,
                title=f"Active plan stale {effective_age}d: {Path(plan_rel).name}",
                detail=(
                    f"Active plan `{plan_rel}` untouched {effective_age}d "
                    f"(threshold {PLAN_ROT_STALE_DAYS}d). Update if work continues "
                    f"or clear active_plan in _memory/index.json if done."
                ),
                source=plan_rel,
                days_overdue=effective_age,
            )
        ]
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, "run_plan_rot")
        return []


def scan_false_completions(
    today: datetime.date,
    lookback_days: int = FALSE_COMPLETION_LOOKBACK_DAYS,
    repo_root: Optional[Path] = None,
) -> list[StewardFinding]:
    """Scan recent handoffs for completion claims lacking 3-leg evidence.

    A handoff modified within lookback_days that contains a completion keyword but
    lacks at least 3 distinct evidence concepts (trigger/effect/consumer) AND does
    not reference the methodology directly is flagged P1. Returns [] on I/O error.
    """
    if repo_root is None:
        repo_root = REPO_ROOT
    handoffs = repo_root / "_handoffs"
    findings: list[StewardFinding] = []
    if not handoffs.exists() or not handoffs.is_dir():
        return findings
    try:
        candidates: list[tuple[Path, float]] = []
        for path in handoffs.glob("*.md"):
            if path.name.startswith("."):
                continue
            try:
                st = path.stat()
            except (FileNotFoundError, PermissionError, OSError):
                continue
            candidates.append((path, st.st_mtime))
        candidates.sort(key=lambda t: t[1], reverse=True)
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, "scan_false_completions candidate-gather")
        return []

    today_ord = today.toordinal()
    for path, mtime in candidates[:FALSE_COMPLETION_MAX_FILES]:
        try:
            age_days = today_ord - datetime.date.fromtimestamp(mtime).toordinal()
            if age_days < 0 or age_days > lookback_days:
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read(FALSE_COMPLETION_MAX_BYTES_PER_FILE)
            except (FileNotFoundError, PermissionError, OSError, UnicodeDecodeError):
                continue
            if not COMPLETION_RE.search(text):
                continue
            if METHODOLOGY_EVIDENCE_RE.search(text):
                continue
            evidence: set[str] = set()
            for m in EVIDENCE_RE.finditer(text):
                w = m.group(1).lower()
                if w.startswith("trigger"):
                    evidence.add("trigger")
                elif w.startswith("effect"):
                    evidence.add("effect")
                elif w.startswith("consum"):
                    evidence.add("consumer")
            if len(evidence) < 3:
                try:
                    rel = str(path.relative_to(repo_root))
                except ValueError:
                    rel = str(path)
                findings.append(
                    StewardFinding(
                        module="false-completion",
                        severity=Severity.P1,
                        title=f"Completion claim missing 3-leg evidence: {path.name}",
                        detail=(
                            f"Handoff modified {age_days}d ago contains a completion "
                            f"keyword but lacks trigger+effect+consumer markers "
                            f"(found: {sorted(evidence) or 'none'})"
                        ),
                        source=rel,
                    )
                )
        except Exception as e:
            write_failure_ledger(MODULE_NAME, e, f"scan_false_completions: {path.name}")
            continue
    return findings


def scan_parallel_sessions() -> list[StewardFinding]:
    """Detect parallel CC sessions to surface race-condition risk. Fail-open: any
    exception -> []. Quiet when fewer than 2 short-lived `claude` PIDs are seen
    (the clean-room / solo-session case)."""
    try:
        import subprocess
        result = subprocess.run(
            ["ps", "-axo", "pid,etime,command"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0:
            return []
        active_pids: list[int] = []
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not (stripped.endswith(" claude") or stripped.endswith("\tclaude")):
                continue
            parts = stripped.split(None, 2)
            if len(parts) < 3:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            elapsed = parts[1]
            if "-" in elapsed:  # multi-day process (daemon/watchdog) - skip
                continue
            active_pids.append(pid)
        if len(active_pids) < 2:
            return []
        journal = REPO_ROOT / "_handoffs" / ".session-journal.md"
        journal_recent = False
        try:
            if journal.exists():
                journal_recent = (time.time() - journal.stat().st_mtime) < 30 * 60
        except OSError:
            pass
        title = f"PARALLEL CC sessions: {len(active_pids)} active non-watchdog PIDs"
        detail = (
            f"PIDs (excluded multi-day watchdogs): {sorted(active_pids)}. "
            f"session-journal active <30min: {'yes' if journal_recent else 'no'}. "
            "Before starting planned work: check for overlapping scope in other "
            "sessions to avoid duplicate work / write races."
        )
        return [
            StewardFinding(
                module="parallel-session-scanner",
                severity=Severity.P1,
                title=title,
                detail=detail,
                source="ps + session-journal",
            )
        ]
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, "scan_parallel_sessions")
        return []


# ---------------------------------------------------------------------------
# Output assembly
# ---------------------------------------------------------------------------

def write_findings_jsonl(out_path: Path, findings: list[StewardFinding]) -> None:
    """Append findings as JSONL rows under one flock-serialized write. Fail-open."""
    if not findings:
        return
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ts = utc_now_iso()
        rows: list[str] = []
        for f in findings:
            row = {
                "schema_version": SCHEMA_VERSION,
                "run_at": ts,
                "hook": MODULE_NAME,
                **f.to_dict(),
            }
            rows.append(json.dumps(row, ensure_ascii=False))
        payload = "\n".join(rows) + "\n"
        with open(out_path, "a", encoding="utf-8") as fh:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            except OSError:
                pass
            fh.write(payload)
    except (PermissionError, OSError):
        try:
            write_failure_ledger(MODULE_NAME, OSError("findings JSONL write failed"), "write_findings_jsonl")
        except Exception:
            pass


def select_top_n(findings: list[StewardFinding], n: int = TOP_N_FINDINGS) -> list[StewardFinding]:
    high_sev = [f for f in findings if f.severity in (Severity.P0, Severity.P1)]
    high_sev.sort(key=lambda f: (SEVERITY_RANK.get(f.severity, 99), -(f.days_overdue or 0)))
    return high_sev[:n]


def build_system_message(top: list[StewardFinding]) -> str:
    if not top:
        return ""
    lines = ["[steward] Top findings this session:"]
    for f in top:
        sev = f.severity.value if isinstance(f.severity, Severity) else str(f.severity)
        overdue = ""
        if f.days_overdue is not None and f.days_overdue > 0:
            overdue = f" [{f.days_overdue}d overdue]"
        lines.append(f"- [{sev}]{overdue} {f.title}")
        if f.source:
            lines.append(f"  source: {f.source}")
    text = "\n".join(lines)
    if len(text) > SYSTEM_MESSAGE_MAX_CHARS:
        text = text[: SYSTEM_MESSAGE_MAX_CHARS - 3].rstrip() + "..."
    return text


def emit_hook_output(message: str) -> None:
    if not message:
        return
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        }
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main(today: Optional[datetime.date] = None) -> int:
    """Returns 0 always. Today injectable for tests."""
    if today is None:
        today = datetime.date.today()

    # Touch config once (validates it loads; harmless if absent).
    try:
        load_steward_config(REPO_ROOT)
    except Exception:
        pass

    all_findings: list[StewardFinding] = []
    all_findings.extend(run_followup(today))
    all_findings.extend(run_audit_if_due(today))
    all_findings.extend(run_retirement_if_due(today))
    for fn, ctx in (
        (run_plan_rot, "main: plan_rot"),
        (lambda t=today: scan_false_completions(t), "main: false_completions"),
        (lambda *_: scan_parallel_sessions(), "main: parallel_sessions"),
    ):
        try:
            all_findings.extend(fn(today))
        except Exception as e:
            write_failure_ledger(MODULE_NAME, e, ctx)

    try:
        write_findings_jsonl(FINDINGS_OUT, all_findings)
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, "main: write_findings_jsonl wrapper")

    try:
        emit_hook_output(build_system_message(select_top_n(all_findings)))
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, "main: emit wrapper")

    return 0


if __name__ == "__main__":
    _session_id_override = None
    try:
        _raw_stdin = sys.stdin.read()
        sys.stdin = io.StringIO(_raw_stdin)
        if _raw_stdin.strip():
            try:
                _session_id_override = json.loads(_raw_stdin).get("session_id")
            except (json.JSONDecodeError, AttributeError):
                _session_id_override = None
    except Exception:
        pass

    try:
        from hook_telemetry import track_hook as _track_hook  # noqa: E402
        try:
            with _track_hook(MODULE_NAME, event="SessionStart", session_id=_session_id_override):
                main()
        except Exception:
            pass
    except ImportError:
        try:
            main()
        except Exception:
            pass

    sys.exit(0)
