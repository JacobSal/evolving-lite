#!/usr/bin/env python3
"""Steward Check: Retirement Candidates (dead hooks).

Surfaces hook scripts that appear DEAD: present on disk under hooks/scripts/ but
registered nowhere in hooks.json, so they never fire. These are the candidates
the steward_actuator may AUTONOMOUS-archive (reversibly), gated by its own
library/test/reference safety guard.

Genericized + leaned vs upstream: the cc-inspector session-count "installed but
stale" path and the detection-index skill-stub path are upstream-specific
telemetry sources; lite ships the dead-hook path only (the one that feeds the
reversible archiver). The session-count config keys remain for forward-compat:
a user who wires a session-count source can enable the LOW-confidence path.

Cold-baseline rule: on a fresh install every hook is registered AND every file
is young, so this emits ZERO findings. Age-grace (uninstalled_stale_days,
default 90) means a freshly-added-but-not-yet-registered file is given time
before it is ever flagged.

Scoring (config-driven):
  - basename in critical_allowlist                  -> never a candidate (None)
  - not registered AND file_age > uninstalled_days  -> P2 (HIGH conf if not a
        test/shared-lib; LOW conf otherwise so the actuator never auto-archives)
  - not registered AND file_age <= uninstalled_days -> None (age-grace)
  - registered                                      -> None (live)

Public API for hook consumption:
  run_check(repo_root, today=None) -> CheckResult
"""

from __future__ import annotations

import argparse
import json
import re
import signal
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).parent.resolve()
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from steward_checks.common import (  # noqa: E402
    HIGH_CONFIDENCE_MARKER,
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

MODULE_NAME = "retirement"
HARD_TIMEOUT_S = 30

HOOKS_JSON_DEFAULT = "hooks/hooks.json"
HOOK_SCRIPTS_DIRNAME = "hooks/scripts"

# Filenames referenced inside hooks.json command strings.
_HOOK_FILE_RE = re.compile(r"[\w./-]+\.(?:py|sh)\b")

_TEST_FILE_PATTERNS = (
    re.compile(r"^test[-_].*\.(sh|py)$"),
    re.compile(r".*[-_]test\.(sh|py)$"),
)

ARCHIVED_MARKER_LINES = 30


def load_registered_basenames(hooks_json_path: Path) -> set[str]:
    """Return the set of hook-script basenames referenced anywhere in hooks.json.

    Parses every command string for *.py / *.sh tokens (the ${CLAUDE_PLUGIN_ROOT}
    prefix and python3 wrapper are irrelevant; only the basename is matched).
    Fail-open: unreadable/missing -> empty set (so nothing is assumed registered;
    age-grace still protects fresh files).
    """
    try:
        if not hooks_json_path.exists():
            return set()
        raw = hooks_json_path.read_text(encoding="utf-8")
    except OSError as e:
        write_failure_ledger(MODULE_NAME, e, f"load_registered_basenames: {hooks_json_path}")
        return set()
    names: set[str] = set()
    for m in _HOOK_FILE_RE.finditer(raw):
        names.add(Path(m.group(0)).name)
    return names


def load_hook_files_on_disk(hook_scripts_dir: Path) -> list[Path]:
    """Return *.py / *.sh files directly under hook_scripts_dir (non-recursive,
    so the lib/ subdir of shared libraries is excluded). Never raises."""
    out: list[Path] = []
    try:
        if not hook_scripts_dir.exists():
            return []
        for entry in hook_scripts_dir.iterdir():
            if entry.is_file() and entry.suffix in (".py", ".sh"):
                out.append(entry)
    except OSError as e:
        write_failure_ledger(MODULE_NAME, e, f"load_hook_files_on_disk: {hook_scripts_dir}")
    return out


def _is_test_file(path: Path) -> bool:
    if any(part in ("tests", "test") for part in path.parts):
        return True
    return any(pat.match(path.name) for pat in _TEST_FILE_PATTERNS)


def _has_shared_library_marker(path: Path) -> bool:
    """True if the file's header declares it a sourced/shared library. Such a
    file is never an event handler and must not be archived. Never raises."""
    try:
        head = "\n".join(path.read_text(encoding="utf-8", errors="ignore").splitlines()[:ARCHIVED_MARKER_LINES])
    except OSError:
        return False
    low = head.lower()
    return ("shared util" in low or "shared lib" in low
            or "source this file" in low or "sourced by" in low)


def _file_age_days(path: Path, today: date) -> int:
    try:
        return (today - date.fromtimestamp(path.stat().st_mtime)).days
    except OSError:
        return -1


def check_retirement(
    repo_root: Path,
    today: date,
    critical_allowlist: set[str],
    uninstalled_stale_days: int,
) -> list[StewardFinding]:
    """Emit dead-hook retirement findings. Never raises."""
    findings: list[StewardFinding] = []
    try:
        registered = load_registered_basenames(repo_root / HOOKS_JSON_DEFAULT)
        on_disk = load_hook_files_on_disk(repo_root / HOOK_SCRIPTS_DIRNAME)
        for path in on_disk:
            name = path.name
            if name in critical_allowlist:
                continue
            if name in registered:
                continue  # live hook
            age = _file_age_days(path, today)
            if age < 0 or age <= uninstalled_stale_days:
                continue  # age-grace: too fresh to call dead
            # Unregistered + old -> dead candidate. HIGH confidence only when it
            # is plausibly an event handler (not a test, not a shared library);
            # otherwise LOW confidence so the actuator never auto-archives it.
            is_handler = not _is_test_file(path) and not _has_shared_library_marker(path)
            if is_handler:
                confidence = HIGH_CONFIDENCE_MARKER
                severity = Severity.P2
            else:
                confidence = "Confidence: LOW (test/shared-lib; manual review only)"
                severity = Severity.P2
            try:
                source = str(path.relative_to(repo_root))
            except ValueError:
                source = str(path)
            findings.append(StewardFinding(
                module=MODULE_NAME,
                severity=severity,
                title=f"Retirement candidate: {name} ({age}d, unregistered)",
                detail=(
                    f"{name} exists on disk but is not registered in hooks.json, "
                    f"so it never fires. File age {age}d > {uninstalled_stale_days}d. "
                    f"{confidence}"
                ),
                source=source,
                item_id=name,
                days_overdue=age,
            ))
    except Exception as e:
        write_failure_ledger(MODULE_NAME, e, "check_retirement")
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
        findings = check_retirement(
            repo_root,
            today,
            critical_allowlist=set(cfg["retirement_critical_allowlist"]),
            uninstalled_stale_days=int(cfg["retirement_uninstalled_stale_days"]),
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
        prog="retirement",
        description="Steward check: dead-hook retirement candidates",
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
