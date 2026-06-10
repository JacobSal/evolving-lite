"""The ONE knowledge-nodes.json write discipline: locked, in-place RMW.

WHY THIS EXISTS
---------------
_graph/knowledge-nodes.json has multiple writers (ARS upsert on every
PostToolUse[Write] across all concurrent sessions, the dedup operator tool,
and a few cold-path graph-maintenance scripts). The original ARS writer used a
bare temp-file + ``os.replace`` (lock-free inode swap). Two concurrent writers
each do read -> modify -> os.replace; the second os.replace overwrites the
first writer's append. Result: a committed node silently disappears.

A lock alone does NOT fix this if writers use ``os.replace``: os.replace swaps
the file's inode, and an advisory ``flock`` another writer holds on the OLD
inode's fd cannot see the new inode. The two writers stop serializing.

THE DISCIPLINE (single source of truth, used by every writer)
-------------------------------------------------------------
1. ``open(path, "r+")`` and hold ``fcntl.LOCK_EX`` on THAT fd across the WHOLE
   read -> modify -> write cycle (not just the write - the read must be inside
   the lock or you re-introduce the lost-update).
2. Write IN PLACE on the locked fd (``seek(0)`` / ``write`` / ``truncate`` /
   ``flush`` / ``fsync``). NEVER ``os.replace`` for this file - that would swap
   the inode and break the lock for every other cooperating writer.

Because every cooperating writer locks the SAME inode, they serialize: no
writer can lose another's append. A non-cooperating ``os.replace`` writer (none
remain in-tree) would at worst make a locked writer's in-place write fail to
stick (it targets the now-unlinked old inode); the os.replace writer's content
- itself a read-current-then-write superset - survives. So the worst case
across the whole class is "re-run", never node loss.

HOT-PATH SAFETY
---------------
The ARS caller runs under a 2s SIGALRM in a fail-open PostToolUse hook. Lock
acquisition is therefore BOUNDED + non-blocking (``LOCK_NB`` retry until a
deadline) so it can never hang past the hook budget: on contention timeout it
raises :class:`LockTimeout`, which the caller treats as fail-open (the node is
not registered this Write and re-registers idempotently on the next one). The
actual in-place write of the ~1.5 MB file is sub-millisecond, well inside the
remaining budget once the (bounded) lock is held.

On a filesystem without ``flock`` the helper degrades to a single best-effort
lock-free pass (correctness then relies on low concurrency, as before).
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Tuple

__all__ = ["locked_rmw_json", "locked_write_remerge", "LockTimeout",
           "_locked_overwrite_raw"]

# A mutate-fn takes the parsed JSON document and returns (new_doc, changed).
# changed=False => no write is performed (idempotent / nothing to do).
MutateFn = Callable[[Any], Tuple[Any, bool]]


class LockTimeout(TimeoutError):
    """Raised when the exclusive lock could not be acquired within the bound.

    Subclasses TimeoutError so existing broad ``except Exception`` fail-open
    handlers (ARS dispatch per-target try/except) catch it transparently.
    """


def locked_rmw_json(
    path: str | os.PathLike[str],
    mutate: MutateFn,
    *,
    acquire_timeout_s: float = 1.0,
    poll_interval_s: float = 0.02,
    pre_write: Callable[[str], None] | None = None,
) -> bool:
    """Read-modify-write a JSON file under an exclusive lock, IN PLACE.

    The lock is held across read + mutate + write. The write is performed in
    place on the locked fd (never os.replace) so the data-file inode stays
    stable and the lock serializes all cooperating writers.

    Args:
        path: target JSON file. MUST already exist (callers decide policy for
            missing files; we never create one, to avoid masking a wrong path).
        mutate: ``fn(doc) -> (new_doc, changed)``. If ``changed`` is False the
            file is left byte-for-byte untouched (no write at all).
        acquire_timeout_s: max wall-clock to wait for the lock before raising
            :class:`LockTimeout`. Keep well under any caller SIGALRM budget.
        poll_interval_s: sleep between non-blocking lock attempts.
        pre_write: optional ``fn(raw_text)`` invoked with the EXACT bytes read
            under the lock, immediately before the in-place write, and ONLY
            when a write will happen (mutate returned changed=True). Used by the
            dedup operator tool to take its exact pre-write backup under the
            same lock. Hot-path callers (ARS) leave this None.

    Returns:
        The ``changed`` bool from ``mutate`` (False => no write happened).

    Raises:
        FileNotFoundError: ``path`` does not exist.
        LockTimeout: lock not acquired within ``acquire_timeout_s``.
        json.JSONDecodeError: ``path`` is not valid JSON.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    with open(p, "r+", encoding="utf-8") as fh:
        _acquire_locked(fh.fileno(), acquire_timeout_s, poll_interval_s)
        try:
            fh.seek(0)
            raw = fh.read()
            doc = json.loads(raw)

            new_doc, changed = mutate(doc)
            if not changed:
                return False

            if pre_write is not None:
                pre_write(raw)  # exact-bytes backup, still under the lock

            payload = json.dumps(new_doc, indent=2, ensure_ascii=False)
            fh.seek(0)
            fh.write(payload)
            fh.truncate()
            fh.flush()
            os.fsync(fh.fileno())
            return True
        finally:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


def _acquire_locked(fd: int, timeout_s: float, poll_s: float) -> None:
    """Acquire LOCK_EX with a bounded non-blocking retry loop.

    Bounded (not a blocking ``LOCK_EX``) so a SIGALRM-budgeted hot-path caller
    never hangs: on timeout raise LockTimeout. On a platform/filesystem without
    flock support, degrade to a single lock-free pass (return without locking).
    """
    deadline = time.monotonic() + max(0.0, timeout_s)
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except (AttributeError, NotImplementedError):
            return  # no flock on this platform: best-effort lock-free
        except OSError as e:
            # Genuine "this filesystem has no flock" -> degrade lock-free rather
            # than fail the write (NFS=ENOLCK, vfat/exfat=ENOTSUP/EOPNOTSUPP).
            # NOT EINVAL/EBADF: those are programming errors (bad/closed fd) and
            # must surface, not be silently swallowed into an unprotected write.
            no_flock = {errno.ENOTSUP, errno.ENOLCK,
                        getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)}
            if e.errno in no_flock:
                return
            # EWOULDBLOCK/EAGAIN: lock held by someone else -> retry until deadline.
            if e.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                if time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"could not acquire LOCK_EX within {timeout_s}s"
                    ) from e
                time.sleep(poll_s)
                continue
            raise  # EINVAL/EBADF/etc.: real error, propagate


def locked_write_remerge(
    path: str | os.PathLike[str],
    apply_fn: Callable[[Any], bool],
    *,
    acquire_timeout_s: float = 5.0,
) -> bool:
    """Re-read ``path`` under the exclusive lock, run ``apply_fn(fresh_doc)``
    (mutates the freshly-read doc IN PLACE, returns whether it changed), then
    write IN PLACE on the locked fd (the shared :func:`locked_rmw_json`
    discipline). For the multi-writer cache targets several concurrent sessions
    touch at once (context-router.json, edges.json, detection-index.json,
    knowledge-nodes.json, _stats.json): ARS / qr-scan / full-sync write the same
    files, and an ``os.replace``/``tmp.replace``/``mv`` inode swap silently
    clobbers a concurrent flock-protected append (lost-update class).
    Re-applying an idempotent ``apply_fn`` on freshly-read data loses nothing.

    The mutation MUST be idempotent and computed against the *fresh* doc passed
    in (NOT a start-of-run snapshot) - else the lost-update is re-introduced.

    Fails OPEN (returns False, no write) on lock-timeout / missing file / a
    mid-write unparseable read / any OSError - the caller re-fires next cycle.

    Returns the ``changed`` bool (also False on fail-open).
    """
    box = {"changed": False}

    def _mutate(fresh: Any) -> Tuple[Any, bool]:
        changed = bool(apply_fn(fresh))
        box["changed"] = changed
        return fresh, changed

    try:
        locked_rmw_json(path, _mutate, acquire_timeout_s=acquire_timeout_s)
    except (LockTimeout, FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    return box["changed"]


# ---------------------------------------------------------------------------
# Raw (non-JSON) locked overwrite helper
# ---------------------------------------------------------------------------

def _locked_overwrite_raw(
    target: str | os.PathLike[str],
    payload: str | bytes,
    *,
    acquire_timeout_s: float = 30.0,
) -> None:
    """Overwrite *target* in-place under an exclusive flock.

    Works for both JSON and non-JSON (e.g. Markdown) targets because it does
    NOT json.loads the existing content - it just replaces it.  The inode stays
    stable (seek0/write/truncate/fsync), so every cooperating writer that holds
    an flock on the same inode serialises correctly.

    The file is opened with ``os.open(O_RDWR | O_CREAT)`` (creates if missing,
    NEVER truncates on open, and crucially NOT ``O_APPEND``), so the
    create-if-missing case goes through the SAME bounded lock + fsync as the
    overwrite case.  There is NO separate ``p.exists()`` fast-path: that branch
    was TOCTOU-racy (a concurrent creator between the check and the write would
    be clobbered, and it skipped fsync).

    NOTE: ``O_APPEND`` (Python ``"a+b"``) is deliberately avoided here.  In
    append mode every write is forced to EOF regardless of ``seek(0)``, so a
    ``seek(0)+write+truncate`` cycle DOUBLES the file instead of overwriting it.
    ``O_RDWR | O_CREAT`` (no ``O_APPEND``, no ``O_TRUNC``) is the correct atomic
    create-or-open that still honours ``seek(0)`` for in-place overwrite.

    Args:
        target: path to overwrite or create.
        payload: new content as str or bytes.  Must be non-empty (callers
            validate before calling).
        acquire_timeout_s: max wall-clock seconds to wait for the lock.

    Raises:
        LockTimeout: exclusive lock not acquired within the deadline.
        OSError: I/O error during write (propagated; target state is uncertain
            - callers should treat this as a hard failure).
    """
    p = Path(target)
    raw: bytes = payload.encode("utf-8") if isinstance(payload, str) else payload

    # O_RDWR | O_CREAT: create if missing, no truncate-on-open, NO O_APPEND.
    # O_APPEND would force every write to EOF (seek(0) ignored) and double the
    # file. This is the atomic create-or-open with correct in-place overwrite.
    fd = os.open(p, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fh = os.fdopen(fd, "r+b")
    except Exception:
        os.close(fd)
        raise
    with fh:
        _acquire_locked(fh.fileno(), acquire_timeout_s, poll_s=0.02)
        try:
            fh.seek(0)
            fh.write(raw)
            fh.truncate()
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# CLI entrypoint  (invoke as: python3 scripts/lib/locked_json_rmw.py ...)
# ---------------------------------------------------------------------------

def _cli() -> None:
    """Command-line interface for concurrency-safe JSON writes from bash scripts.

    Two modes:

    --jq FILTER TARGET [--jq-arg KEY VAL]... [--jq-argjson KEY VAL]...
        Lock TARGET, re-read its FRESH content under the lock, apply the jq
        FILTER to that fresh content, write the result in-place.  The
        read+transform happens inside the lock so a concurrent appender cannot
        lose its write.  Use for SHARED/APPENDED files (knowledge-nodes.json,
        _stats.json, context-router.json, edges.json, detection-index.json).

        --jq-arg KEY VAL     passed through as ``jq --arg KEY VAL`` (string)
        --jq-argjson KEY VAL passed through as ``jq --argjson KEY VAL`` (JSON)

    --write-from SRCFILE TARGET
        Validate SRCFILE is non-empty (and valid JSON if TARGET ends in .json),
        then lock TARGET and overwrite its content in-place from SRCFILE.  Use
        for DERIVED VIEWS that full-sync regenerates wholesale
        (core-nodes.json, by-type.json, by-domain.json).

    Exit codes: 0 = success (wrote or no-op); non-zero = error.
    One-line status is written to stderr.
    """
    import argparse
    import subprocess
    import sys

    parser = argparse.ArgumentParser(
        description="Concurrency-safe in-place JSON write helper.",
        prog="locked_json_rmw",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--jq",
        metavar=("FILTER", "TARGET"),
        nargs=2,
        help="Apply jq FILTER to TARGET's fresh content under lock, write in-place.",
    )
    mode.add_argument(
        "--write-from",
        metavar=("SRCFILE", "TARGET"),
        nargs=2,
        help="Overwrite TARGET in-place with content from SRCFILE (locked).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="Lock-acquire timeout in seconds (default: 30).",
    )
    # jq passthrough args (only relevant for --jq mode; silently ignored otherwise)
    parser.add_argument(
        "--jq-arg",
        action="append",
        nargs=2,
        metavar=("KEY", "VAL"),
        default=[],
        dest="jq_args",
        help="Pass --arg KEY VAL to jq (string). Repeatable.",
    )
    parser.add_argument(
        "--jq-argjson",
        action="append",
        nargs=2,
        metavar=("KEY", "VAL"),
        default=[],
        dest="jq_argjsons",
        help="Pass --argjson KEY VAL to jq (JSON). Repeatable.",
    )
    args = parser.parse_args()

    # ---- Mode 1: --jq -------------------------------------------------------
    if args.jq is not None:
        jq_filter, target_path = args.jq
        target = Path(target_path)

        if not target.exists():
            print(
                f"locked_json_rmw --jq: target not found: {target}",
                file=sys.stderr,
            )
            sys.exit(1)

        # Build jq argv prefix for --arg / --argjson passthrough
        jq_extra: list[str] = []
        for key, val in (args.jq_args or []):
            jq_extra += ["--arg", key, val]
        for key, val in (args.jq_argjsons or []):
            jq_extra += ["--argjson", key, val]

        wrote: bool = False

        def _jq_mutate(fresh_doc: Any) -> Tuple[Any, bool]:
            fresh_text = json.dumps(fresh_doc, indent=2, ensure_ascii=False)
            cmd = ["jq"] + jq_extra + [jq_filter]
            # The lock is HELD across this subprocess call; a hung/slow jq would
            # otherwise hold LOCK_EX indefinitely and deadlock cooperating
            # writers. Bound it by the same lock timeout. On timeout we raise
            # RuntimeError (caught by the jq-error path) so the live file is
            # left untouched and the error surfaces.
            try:
                result = subprocess.run(
                    cmd,
                    input=fresh_text,
                    capture_output=True,
                    text=True,
                    timeout=args.timeout,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"jq timed out after {args.timeout}s (lock held)"
                ) from exc
            if result.returncode != 0:
                msg = result.stderr.strip() or "(no jq stderr)"
                raise RuntimeError(
                    f"jq exited {result.returncode}: {msg}"
                )
            try:
                new_doc = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"jq produced unparseable output: {exc}"
                ) from exc
            changed = new_doc != fresh_doc
            return new_doc, changed

        try:
            wrote = locked_rmw_json(
                target,
                _jq_mutate,
                acquire_timeout_s=args.timeout,
            )
        except LockTimeout as exc:
            print(f"locked_json_rmw --jq: lock timeout: {exc}", file=sys.stderr)
            sys.exit(2)
        except RuntimeError as exc:
            # jq error - live file is UNTOUCHED (exception raised inside mutate
            # before any write happens, so locked_rmw_json skips the write).
            print(f"locked_json_rmw --jq: filter error: {exc}", file=sys.stderr)
            sys.exit(3)
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            print(f"locked_json_rmw --jq: error: {exc}", file=sys.stderr)
            sys.exit(1)

        status = "wrote" if wrote else "no-op (unchanged)"
        print(f"locked_json_rmw --jq: {status}: {target}", file=sys.stderr)
        sys.exit(0)

    # ---- Mode 2: --write-from -----------------------------------------------
    if args.write_from is not None:
        src_path, target_path = args.write_from
        src = Path(src_path)
        target = Path(target_path)

        # Validate source non-empty
        if not src.exists() or src.stat().st_size == 0:
            print(
                f"locked_json_rmw --write-from: source empty or missing: {src}",
                file=sys.stderr,
            )
            sys.exit(1)

        payload = src.read_text(encoding="utf-8")

        # JSON targets: validate before touching the live file
        if target_path.endswith(".json"):
            try:
                json.loads(payload)
            except json.JSONDecodeError as exc:
                print(
                    f"locked_json_rmw --write-from: source is not valid JSON "
                    f"({src}): {exc}",
                    file=sys.stderr,
                )
                sys.exit(1)

        try:
            _locked_overwrite_raw(target, payload, acquire_timeout_s=args.timeout)
        except LockTimeout as exc:
            print(
                f"locked_json_rmw --write-from: lock timeout: {exc}",
                file=sys.stderr,
            )
            sys.exit(2)
        except OSError as exc:
            print(
                f"locked_json_rmw --write-from: I/O error: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)

        print(
            f"locked_json_rmw --write-from: wrote {target} from {src}",
            file=sys.stderr,
        )
        sys.exit(0)


if __name__ == "__main__":
    _cli()
