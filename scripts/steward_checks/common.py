"""Steward Checks shared library.

Common data structures, severity enum, config loader, and output rendering for
the steward-check modules (followup.py, audit.py, retirement.py) and the
consolidated steward-checker SessionStart hook.

Design contract:
  - Single shared dataclass schema (StewardFinding) consumed uniformly by the
    steward-checker hook and the steward_actuator (forward-compat via
    schema_version).
  - Fail-open: write_failure_ledger swallows its own errors; CLI rendering never
    raises to the caller. The hook chain must stay non-blocking.
  - Data root resolves via plugin_paths.plugin_root() (the plugin root, not the
    user's project) so caches/ledgers live next to the shipped code.
  - Severity P0 is RESERVED for security/data-loss detection. Stale items max out
    at P1. Preserves semantic clarity: P0 = "this leaks credentials", not "old".

Public API:
  - Severity (enum: P0|P1|P2|P3)
  - StewardFinding (dataclass with .to_dict())
  - CheckResult (dataclass with .to_dict())
  - load_steward_config(repo_root) -> dict   (optional override + defaults)
  - write_failure_ledger(module, error, context) -> None   (never raises)
  - render_output(result, human=False) -> str
  - add_argparse_output_flags(parser) -> None
  - utc_now_iso() -> str
  - REPO_ROOT, STEWARD_FAILURES_LEDGER, STEWARD_LEDGERS_DIR, SCHEMA_VERSION
"""

from __future__ import annotations

import argparse
import json
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Paths - resolve the plugin root via the shared helper (CLAUDE_PLUGIN_ROOT >
# walk-up plugin.json > CLAUDE_PROJECT_DIR > file-relative). steward_checks/
# lives under scripts/, so scripts/lib is the helper's home.
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
import sys as _sys

_LIB_DIR = str(_HERE.parent / "lib")
if _LIB_DIR not in _sys.path:
    _sys.path.insert(0, _LIB_DIR)
try:
    from plugin_paths import plugin_root as _plugin_root  # noqa: E402

    REPO_ROOT = _plugin_root()
except Exception:  # pragma: no cover - defensive; helper should always import
    # steward_checks/ -> scripts/ -> plugin root
    REPO_ROOT = _HERE.parent.parent

STEWARD_LEDGERS_DIR = REPO_ROOT / "_ledgers"
STEWARD_FAILURES_LEDGER = STEWARD_LEDGERS_DIR / "steward-failures.jsonl"
STEWARD_CONFIG_PATH = REPO_ROOT / "_graph" / "cache" / "steward-config.json"

SCHEMA_VERSION = "1.0"

# Contract token between retirement.py (producer) and steward_actuator (consumer).
# A retirement finding whose `detail` contains this exact substring is an
# unambiguously dead hook (registered nowhere, so it never fires) and is the ONLY
# finding class the actuator may AUTONOMOUS-archive. Genericized from upstream's
# settings.json wording to lite's hooks.json registry.
HIGH_CONFIDENCE_MARKER = "Confidence: HIGH (not registered in hooks.json = never fires)"


# ---------------------------------------------------------------------------
# Config (optional override file + safe defaults)
# ---------------------------------------------------------------------------

# All thresholds + the maintainer-editable allowlists live here. The file ships
# with these defaults; a user may override any key in
# _graph/cache/steward-config.json. Absent/corrupt file -> defaults (cold-safe).
_CONFIG_DEFAULTS: dict[str, Any] = {
    # followup.py
    "followup_marker_keywords": ["follow-up", "followup", "wiedervorlage"],
    "followup_upcoming_window_days": 7,
    "followup_lookback_days": 30,
    # audit.py
    "audit_reports_dirname": "audit-reports",
    "audit_stale_threshold_days": 8,
    # When True, a fresh repo with no audit reports yet emits NO finding
    # ("never audited is OK"). Prevents a cold-baseline false-positive storm.
    "audit_never_audited_is_ok": True,
    # retirement.py
    "retirement_critical_allowlist": [],
    "retirement_uninstalled_stale_days": 90,
    "retirement_installed_stale_days": 60,
    "retirement_session_count_threshold": 10,
}


def load_steward_config(repo_root: Optional[Path] = None) -> dict[str, Any]:
    """Return the steward config: defaults overlaid with the optional override
    file at <repo_root>/_graph/cache/steward-config.json. Never raises.
    """
    cfg = dict(_CONFIG_DEFAULTS)
    path = (
        (repo_root / "_graph" / "cache" / "steward-config.json")
        if repo_root is not None
        else STEWARD_CONFIG_PATH
    )
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k, v in data.items():
                    if k in cfg:
                        cfg[k] = v
    except Exception:
        pass  # fail-open to defaults
    return cfg


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    """Severity tags for steward findings.

    P0 is RESERVED for security/data-loss detection. Stale items max out at P1.
    """
    P0 = "P0"  # critical (security / data-loss)
    P1 = "P1"  # high (>7d overdue, dangerous-stale hook, parallel-session race)
    P2 = "P2"  # medium (1-7d overdue, retirement candidate)
    P3 = "P3"  # informational (upcoming, stub skills)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class StewardFinding:
    """Canonical finding unit emitted by every steward-check module.

    Consumed by the steward-checker SessionStart hook and the steward_actuator.
    Schema is forward-compatible: consumers MUST tolerate unknown fields.

    maintainer_decision defaults to "silent" (not yet adjudicated). A reaper /
    human review may later flip it to "unknown" / "keep" / "act".
    """
    module: str               # "followup" | "audit" | "retirement" | ...
    severity: Severity
    title: str
    detail: str
    source: str               # file path, "ps", "tasklist", etc.
    item_id: Optional[str] = None       # task ID, hook name, finding hash
    days_overdue: Optional[int] = None  # negative for upcoming, None if N/A
    maintainer_decision: str = "silent"
    decision_at: Optional[str] = None
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value if isinstance(self.severity, Severity) else self.severity
        return d


@dataclass
class CheckResult:
    """Per-module run result. Serialized as the module CLI's --json output."""
    module: str
    run_at: str               # ISO timestamp UTC
    duration_ms: float
    findings: list[StewardFinding] = field(default_factory=list)
    error: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    @property
    def findings_count(self) -> int:
        return len(self.findings)

    @property
    def findings_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            key = f.severity.value if isinstance(f.severity, Severity) else f.severity
            counts[key] = counts.get(key, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "module": self.module,
            "run_at": self.run_at,
            "duration_ms": round(self.duration_ms, 2),
            "error": self.error,
            "findings_count": self.findings_count,
            "findings_by_severity": self.findings_by_severity,
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Failure ledger
# ---------------------------------------------------------------------------

def write_failure_ledger(module: str, error: BaseException, context: str = "") -> None:
    """Append an error record to _ledgers/steward-failures.jsonl.

    Fail-open: any I/O or serialization error here is swallowed. The steward must
    never block its caller (the SessionStart hook chain).
    """
    try:
        STEWARD_LEDGERS_DIR.mkdir(parents=True, exist_ok=True)
        # Best-effort session attribution; fail-open if the helper is absent.
        session_value = None
        try:
            import sys as _sys_sa

            _lib = str(REPO_ROOT / "scripts" / "lib")
            if _lib not in _sys_sa.path:
                _sys_sa.path.insert(0, _lib)
            import session_attribution as _sa  # noqa: E402

            session_value = _sa.resolve_session_id()
        except Exception:
            session_value = None
        entry = {
            "ts": time.time(),
            "ts_iso": datetime.now(timezone.utc).isoformat(),
            "session": session_value,
            "module": module,
            "error_type": type(error).__name__,
            "error_msg": str(error)[:500],
            "context": context[:200],
            "traceback": traceback.format_exc(limit=3)[-1000:],
        }
        with open(STEWARD_FAILURES_LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # last-resort: swallow; the steward must not break the hook chain


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------

def render_output(result: CheckResult, human: bool = False) -> str:
    """Render a CheckResult as JSON (default) or human-readable text."""
    if not human:
        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    lines = [
        f"# Steward Check: {result.module}",
        f"Run at: {result.run_at}",
        f"Duration: {result.duration_ms:.1f}ms",
        f"Schema: {result.schema_version}",
        f"Findings: {result.findings_count}",
    ]
    if result.error:
        lines.append(f"ERROR: {result.error}")
    if result.findings_count == 0:
        lines.append("(no findings)")
        return "\n".join(lines)

    by_sev = result.findings_by_severity
    sev_summary = " ".join(f"{k}={v}" for k, v in sorted(by_sev.items()))
    lines.append(f"By severity: {sev_summary}")
    lines.append("")
    lines.append("## Findings")
    severity_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    sorted_findings = sorted(
        result.findings,
        key=lambda f: (
            severity_order.get(f.severity.value if isinstance(f.severity, Severity) else f.severity, 99),
            -(f.days_overdue or 0),
        ),
    )
    for f in sorted_findings:
        sev = f.severity.value if isinstance(f.severity, Severity) else f.severity
        overdue_marker = ""
        if f.days_overdue is not None:
            if f.days_overdue > 0:
                overdue_marker = f" [{f.days_overdue}d overdue]"
            elif f.days_overdue < 0:
                overdue_marker = f" [in {-f.days_overdue}d]"
            else:
                overdue_marker = " [due today]"
        lines.append(f"  [{sev}]{overdue_marker} {f.title}")
        if f.detail:
            lines.append(f"      {f.detail}")
        if f.source:
            lines.append(f"      source: {f.source}")
    return "\n".join(lines)


def add_argparse_output_flags(parser: argparse.ArgumentParser) -> None:
    """Add --json (default) and --human flags to a steward-check CLI parser."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--json", dest="human", action="store_false", default=False,
        help="Emit JSON output (default)",
    )
    group.add_argument(
        "--human", dest="human", action="store_true",
        help="Emit human-readable text output",
    )


def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string with timezone."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
