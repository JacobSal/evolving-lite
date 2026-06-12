"""Steward hook routing helpers.

Date-based dispatch + throttle markers for the consolidated steward-checker
SessionStart hook. Pure functions, no repo coupling.

Fail-open contract: every public function returns a safe default on unexpected
input rather than raising. The hook MUST never block the SessionStart chain.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path


def should_run_today(
    today: datetime.date,
    weekday: int | None = None,
    day_of_month: int | None = None,
    throttle_marker: str | Path | None = None,
    throttle_days: int | None = None,
) -> bool:
    """Decide whether a check should run today.

    A gate set to None is treated as PASS (no constraint). Returns True only if
    ALL set gates pass.
    """
    if weekday is not None and today.weekday() != weekday:
        return False
    if day_of_month is not None and today.day != day_of_month:
        return False
    if throttle_marker is not None and throttle_days is not None:
        if not marker_is_old(throttle_marker, throttle_days):
            return False
    return True


def read_input_fingerprint(inputs: list[str | Path]) -> str:
    """SHA256 over file mtimes + sizes for the listed inputs. Never raises on
    individual file errors; missing files contribute a stable sentinel."""
    h = hashlib.sha256()
    for raw in inputs:
        p = Path(raw)
        try:
            st = p.stat()
            h.update(f"{p}|{st.st_mtime_ns}|{st.st_size}\n".encode())
        except (FileNotFoundError, PermissionError, OSError):
            h.update(f"{p}|MISSING\n".encode())
    return h.hexdigest()


def cache_is_fresh(fingerprint: str, cache_path: str | Path) -> bool:
    """True iff the cache file contains the same fingerprint string. Missing or
    corrupt cache returns False."""
    p = Path(cache_path)
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, PermissionError, OSError):
        return False
    if not isinstance(data, dict):
        return False
    return data.get("fingerprint") == fingerprint


def write_throttle_marker(marker_path: str | Path) -> None:
    """Touch the marker file with the current UTC timestamp as content.

    Atomic write-rename so concurrent SessionStart hooks cannot produce a
    truncated marker. Fail-open: permission/OS errors are swallowed.
    """
    p = Path(marker_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        tmp = p.parent / f".{p.name}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps({"touched_at": now}) + "\n", encoding="utf-8")
        tmp.replace(p)  # atomic on POSIX
    except (PermissionError, OSError):
        pass


def marker_is_old(marker_path: str | Path, days: int) -> bool:
    """True iff the marker is missing OR its mtime is older than N days.

    A missing marker counts as old (default-fire on first invocation).
    Negative/zero `days` returns True (always-fire).
    """
    if days <= 0:
        return True
    p = Path(marker_path)
    try:
        st = p.stat()
    except (FileNotFoundError, PermissionError, OSError):
        return True
    age_sec = datetime.datetime.now().timestamp() - st.st_mtime
    return age_sec > days * 86400
