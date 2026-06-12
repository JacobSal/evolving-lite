"""Autonom Lease - single-session lease for the autonomy layer.

Claim a lease file with the session id; a SECOND concurrent claim is refused with
"already running in session X"; stale-lease expiry after a configurable TTL
(default 4 hours).

Design:
- Lease file is a JSON file at a caller-supplied path (the autonomy layer uses
  _graph/cache/autonom-lease.json).
- Claim is atomic via fcntl.flock + in-place write; the file may not exist yet,
  so we use O_RDWR | O_CREAT (never truncate on open).
- Stale check: a lease written > LEASE_TTL_SECONDS ago is treated as expired and
  the new claim succeeds.
- SAFETY SPINE INVARIANT: this module is outside the autonomous session's
  self-modification scope. A running autonomous session MUST NOT overwrite this
  file to extend its own lease.

Usage:
    from scripts.autonom.lease import claim_lease, release_lease, LeaseRefused

    try:
        claim_lease(session_id="abc123", lease_path="/path/to/lease.json")
    except LeaseRefused as e:
        print(f"Refused: {e}")
    ...
    release_lease(session_id="abc123", lease_path="/path/to/lease.json")
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEASE_TTL_SECONDS: float = 4 * 3600   # 4 hours; stale after this
_POLL_S: float = 0.02
_LOCK_TIMEOUT_S: float = 5.0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LeaseRefused(RuntimeError):
    """Raised when a second concurrent claim is attempted on an active lease."""

    def __init__(self, holder_session: str, lease_age_s: float) -> None:
        self.holder_session = holder_session
        self.lease_age_s = lease_age_s
        super().__init__(
            f"already running in session {holder_session!r} "
            f"(lease age: {lease_age_s:.0f}s)"
        )


class LeaseNotHeld(RuntimeError):
    """Raised when release_lease is called but session does not hold the lease."""


# ---------------------------------------------------------------------------
# Internal lock helper
# ---------------------------------------------------------------------------

def _acquire_flock(fd: int, timeout_s: float = _LOCK_TIMEOUT_S) -> None:
    """Acquire LOCK_EX on fd with bounded non-blocking retry. Degrades gracefully."""
    deadline = time.monotonic() + max(0.0, timeout_s)
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except (AttributeError, NotImplementedError):
            return  # no flock on this platform
        except OSError as e:
            no_flock = {errno.ENOTSUP, errno.ENOLCK,
                        getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)}
            if e.errno in no_flock:
                import warnings as _warnings
                _warnings.warn(
                    f"autonom lease: flock skipped (errno {e.errno} - filesystem does not support locking). "
                    "Lease atomicity is degraded; concurrent claims may not be safely serialized.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                return  # filesystem has no flock
            if e.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"could not acquire lease lock within {timeout_s}s"
                    ) from e
                time.sleep(_POLL_S)
                continue
            raise


# ---------------------------------------------------------------------------
# Core lease operations
# ---------------------------------------------------------------------------

@dataclass
class LeaseState:
    """Contents of the lease file."""
    session_id: str = ""
    claimed_at: float = 0.0
    released: bool = False

    def is_stale(self, ttl_s: float = LEASE_TTL_SECONDS) -> bool:
        return (time.time() - self.claimed_at) > ttl_s

    def age_s(self) -> float:
        return time.time() - self.claimed_at

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "claimed_at": self.claimed_at,
            "released": self.released,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LeaseState":
        return cls(
            session_id=str(d.get("session_id", "")),
            claimed_at=float(d.get("claimed_at", 0.0)),
            released=bool(d.get("released", False)),
        )

    @classmethod
    def empty(cls) -> "LeaseState":
        return cls(session_id="", claimed_at=0.0, released=True)


def _read_lease(fh) -> LeaseState:
    """Read lease state from an open file handle (position is reset)."""
    fh.seek(0)
    raw = fh.read()
    if not raw.strip():
        return LeaseState.empty()
    try:
        return LeaseState.from_dict(json.loads(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return LeaseState.empty()


def _write_lease(fh, state: LeaseState) -> None:
    """Write lease state in-place on open file handle."""
    payload = json.dumps(state.to_dict(), indent=2)
    fh.seek(0)
    fh.write(payload.encode("utf-8"))
    fh.truncate()
    fh.flush()
    os.fsync(fh.fileno())


def claim_lease(
    session_id: str,
    lease_path: str | Path,
    ttl_s: float = LEASE_TTL_SECONDS,
) -> LeaseState:
    """Claim the autonom lease for session_id.

    Succeeds if:
    - The lease file does not exist (first claim).
    - The existing lease is released=True or stale (older than ttl_s).
    - The existing holder IS this session_id (idempotent re-claim).

    Raises LeaseRefused if another session holds an active, non-stale lease.

    Returns the new LeaseState written to disk.
    """
    p = Path(lease_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    # O_RDWR | O_CREAT: create if missing; never truncate on open.
    fd = os.open(str(p), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fh = os.fdopen(fd, "r+b")
    except Exception:
        os.close(fd)
        raise

    with fh:
        _acquire_flock(fh.fileno())
        try:
            existing = _read_lease(fh)

            # Allow re-claim by the same session (idempotent)
            if existing.session_id == session_id and not existing.released:
                return existing

            # Refuse if another session holds an active, non-stale lease
            if not existing.released and existing.session_id and not existing.is_stale(ttl_s):
                raise LeaseRefused(
                    holder_session=existing.session_id,
                    lease_age_s=existing.age_s(),
                )

            # Claim
            new_state = LeaseState(
                session_id=session_id,
                claimed_at=time.time(),
                released=False,
            )
            _write_lease(fh, new_state)
            return new_state
        finally:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


def release_lease(
    session_id: str,
    lease_path: str | Path,
) -> None:
    """Release the autonom lease held by session_id.

    Raises LeaseNotHeld if the lease is held by a different session (does NOT
    raise if the lease is already released or the file is missing).
    """
    p = Path(lease_path)
    if not p.exists():
        return  # nothing to release

    fd = os.open(str(p), os.O_RDWR, 0o644)
    try:
        fh = os.fdopen(fd, "r+b")
    except Exception:
        os.close(fd)
        raise

    with fh:
        _acquire_flock(fh.fileno())
        try:
            existing = _read_lease(fh)

            if existing.released or not existing.session_id:
                return  # already released

            if existing.session_id != session_id:
                raise LeaseNotHeld(
                    f"lease held by {existing.session_id!r}, not {session_id!r}"
                )

            released_state = LeaseState(
                session_id=existing.session_id,
                claimed_at=existing.claimed_at,
                released=True,
            )
            _write_lease(fh, released_state)
        finally:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


def read_lease_state(lease_path: str | Path) -> Optional[LeaseState]:
    """Read current lease state without claiming. Returns None if file missing."""
    p = Path(lease_path)
    if not p.exists():
        return None
    try:
        raw = p.read_bytes()
        if not raw.strip():
            return LeaseState.empty()
        return LeaseState.from_dict(json.loads(raw))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# CLI (informational - does NOT auto-claim)
# ---------------------------------------------------------------------------

def _default_lease_path() -> Path:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    base = Path(root) if root else Path(__file__).resolve().parents[2]
    return base / "_graph" / "cache" / "autonom-lease.json"


def main(argv=None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Autonom lease inspector/manager.",
        prog="lease",
    )
    parser.add_argument(
        "--lease-path",
        default=str(_default_lease_path()),
        help="Path to lease file.",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status", help="Show current lease state.")

    claim_p = sub.add_parser("claim", help="Claim the lease.")
    claim_p.add_argument("session_id", help="Session ID to claim for.")

    release_p = sub.add_parser("release", help="Release the lease.")
    release_p.add_argument("session_id", help="Session ID releasing the lease.")

    args = parser.parse_args(argv)

    if args.cmd == "status":
        state = read_lease_state(args.lease_path)
        if state is None:
            print("No lease file found.")
            return 0
        print(json.dumps(state.to_dict(), indent=2))
        active = not state.released and not state.is_stale()
        print(f"Active: {active}  |  Stale: {state.is_stale()}  |  Age: {state.age_s():.0f}s")
        return 0

    if args.cmd == "claim":
        try:
            state = claim_lease(args.session_id, args.lease_path)
            print(f"Lease claimed for session {args.session_id!r}.")
            print(json.dumps(state.to_dict(), indent=2))
            return 0
        except LeaseRefused as e:
            print(f"REFUSED: {e}", file=sys.stderr)
            return 1

    if args.cmd == "release":
        try:
            release_lease(args.session_id, args.lease_path)
            print(f"Lease released by session {args.session_id!r}.")
            return 0
        except LeaseNotHeld as e:
            print(f"NOT HELD: {e}", file=sys.stderr)
            return 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main())
