#!/usr/bin/env python3
"""
Auto-Archival - Stop hook for experience and session cleanup.
Adapted from Evolving (~3693 lines across module -> ~120 lines).

Archives:
- Experiences older than 90 days with access_count < 2 and relevance < 30
- Session summaries older than 30 days

Tier 3: Only active from session 10+.
Frequency limit: Max once per 24 hours.

Removed from Evolving version:
- Consolidation, distillation
- Rule archival, backup cleanup
- Modular archival/ package
"""

import json
import os
import sys
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from common import (
    PLUGIN_ROOT, EXPERIENCES_DIR, SESSIONS_DIR, ANALYTICS_DIR,
    write_sentinel, is_tier_active, safe_read_json, safe_write_json,
    log_evolution_event
)

FREQUENCY_FILE = ANALYTICS_DIR / ".last-archival"
ARCHIVE_DIR = PLUGIN_ROOT / "_memory" / "archives"
EXP_MAX_AGE_DAYS = 90
SESSION_MAX_AGE_DAYS = 30
MIN_ACCESS_FOR_KEEP = 2
MIN_RELEVANCE_FOR_KEEP = 30


def should_run() -> bool:
    """Check 24h frequency limit."""
    if not FREQUENCY_FILE.exists():
        return True
    try:
        last_run = float(FREQUENCY_FILE.read_text(encoding="utf-8").strip())
        return (time.time() - last_run) > 86400  # 24 hours
    except (ValueError, OSError):
        return True


def archive_old_experiences() -> int:
    """Archive experiences older than 90 days with low access + relevance."""
    if not EXPERIENCES_DIR.exists():
        return 0

    archived = 0
    cutoff = datetime.now() - timedelta(days=EXP_MAX_AGE_DAYS)
    archive_exp_dir = ARCHIVE_DIR / "experiences"
    archive_exp_dir.mkdir(parents=True, exist_ok=True)

    for exp_file in EXPERIENCES_DIR.glob("exp-*.json"):
        data = safe_read_json(exp_file)
        if not data:
            continue

        # Skip pre-warmed (they're in a subdirectory, but check just in case)
        if data.get("source") == "prewarmed":
            continue

        created_str = data.get("created", "")
        try:
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00").split("+")[0])
        except (ValueError, AttributeError):
            continue

        if created > cutoff:
            continue  # Too young

        access_count = data.get("access_count", 0)
        relevance = data.get("effective_relevance", 50)

        # Only archive if BOTH low access AND low relevance
        if access_count >= MIN_ACCESS_FOR_KEEP or relevance >= MIN_RELEVANCE_FOR_KEEP:
            continue

        # Archive: move to archives directory
        try:
            shutil.move(str(exp_file), str(archive_exp_dir / exp_file.name))
            archived += 1
        except (OSError, shutil.Error):
            continue

    return archived


def archive_old_sessions() -> int:
    """Archive session summaries older than 30 days."""
    if not SESSIONS_DIR.exists():
        return 0

    archived = 0
    cutoff_ts = time.time() - (SESSION_MAX_AGE_DAYS * 86400)
    archive_sess_dir = ARCHIVE_DIR / "sessions"
    archive_sess_dir.mkdir(parents=True, exist_ok=True)

    for sess_file in SESSIONS_DIR.glob("session-*.md"):
        try:
            mtime = sess_file.stat().st_mtime
            if mtime < cutoff_ts:
                shutil.move(str(sess_file), str(archive_sess_dir / sess_file.name))
                archived += 1
        except OSError:
            continue

    # Also archive old handoffs
    for handoff_file in SESSIONS_DIR.glob("handoff-*.md"):
        try:
            mtime = handoff_file.stat().st_mtime
            if mtime < cutoff_ts:
                shutil.move(str(handoff_file), str(archive_sess_dir / handoff_file.name))
                archived += 1
        except OSError:
            continue

    return archived


def main():
    try:
        # Tier gate
        if not is_tier_active(3):
            write_sentinel("auto-archival", "skip-tier")
            sys.exit(0)

        # Frequency gate
        if not should_run():
            write_sentinel("auto-archival", "skip-frequency")
            sys.exit(0)

        exp_archived = archive_old_experiences()
        sess_archived = archive_old_sessions()

        # Update frequency marker
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            FREQUENCY_FILE.write_text(str(time.time()), encoding="utf-8")
        except OSError:
            pass

        # Log to evolution log
        if exp_archived > 0 or sess_archived > 0:
            log_evolution_event(
                "archival",
                f"Archived {exp_archived} experiences, {sess_archived} sessions",
                source="auto-archival"
            )

        write_sentinel("auto-archival", "ok")

    except Exception:
        write_sentinel("auto-archival", "error")

    sys.exit(0)


if __name__ == "__main__":
    main()
