"""Atomic-write utility for `_graph/cache/` and similar JSON state files.

Hooks that write `_graph/cache/*.json` via a bare `open(path, "w")` can leave a
half-written/corrupted JSON on crash or concurrent write that downstream
consumers parse-fail on.

Pattern: tempfile.mkstemp + os.fdopen + json.dump + os.replace, optionally
wrapped in fcntl.LOCK_EX for cross-process serialization.

Use this from any hook or script that mutates a shared cache file.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

try:
    import fcntl  # POSIX-only; macOS + Linux. Not present on Windows.
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False


SchemaValidator = Callable[[Any], None]


class CacheWriteError(Exception):
    """Raised when atomic write fails after fallback attempts."""


def atomic_write_json(
    path: str | Path,
    data: Any,
    *,
    schema: SchemaValidator | None = None,
    indent: int = 2,
    ensure_ascii: bool = False,
    lock: bool = False,
) -> None:
    """Write `data` as JSON to `path` atomically.

    Args:
        path: Target file path. Parent dirs are NOT created (caller's responsibility).
        data: JSON-serializable Python object.
        schema: Optional callable that raises if `data` is invalid.
                Runs BEFORE the write so a failed validation does not corrupt the target.
        indent: json.dump indent.
        ensure_ascii: json.dump ensure_ascii.
        lock: If True, hold an fcntl.LOCK_EX on the target file path during the
              swap. Lock file is `<path>.lock`. Reader-side does NOT need to
              participate; os.replace is itself atomic - the lock only serializes
              concurrent WRITERS.

    Raises:
        CacheWriteError: if the write cannot complete (disk full, permission, etc).
        Exception: if `schema(data)` raises (validation propagates).

    Notes:
        - Temp file is created in the SAME directory as `path` (required for
          os.replace to be a same-filesystem rename).
        - On any error AFTER tempfile creation, the temp file is removed.
    """
    target = Path(path)
    if schema is not None:
        schema(data)  # Raise early; do not touch the file.

    parent = target.parent
    if not parent.exists():
        raise CacheWriteError(f"parent directory does not exist: {parent}")

    fd, tmp_path = tempfile.mkstemp(
        prefix=target.name + ".tmp.",
        dir=str(parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=indent, ensure_ascii=ensure_ascii)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        # fdopen owns the fd on success; on failure also try to clean up.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    if lock and _HAS_FCNTL:
        with _exclusive_lock(target):
            try:
                os.replace(tmp_path, target)
            except OSError as e:
                _remove_silently(tmp_path)
                raise CacheWriteError(f"replace failed: {e}") from e
    else:
        try:
            os.replace(tmp_path, target)
        except OSError as e:
            _remove_silently(tmp_path)
            raise CacheWriteError(f"replace failed: {e}") from e


def atomic_consume_json(path: str | Path) -> Any | None:
    """One-shot atomic read: rename-then-read, returns None if file does not exist.

    Use for hook-to-hook handoff files
    where exactly-one-consumer semantics matter. Returns None if another consumer
    won the rename race or if the file was missing.

    Known operational gap: if the process is SIGKILL'd between the rename and
    the read, an orphaned `<path>.consumed` file is left in the directory. The
    next consumer call returns None correctly (source is gone), but the orphan
    is not reaped. Acceptable for hook-to-hook semantics. Mitigation: a periodic
    janitor sweep of stale `.consumed` files older than e.g. 1h. Not built here.
    """
    src = Path(path)
    consumed = src.with_suffix(src.suffix + ".consumed")
    try:
        os.rename(src, consumed)
    except FileNotFoundError:
        return None
    except OSError:
        return None
    try:
        with open(consumed, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    finally:
        _remove_silently(consumed)


def safe_read_json(path: str | Path, default: Any = None) -> Any:
    """Read JSON, returning `default` on missing-file or parse-error.

    Use this everywhere consumer code needs to tolerate the cache being
    absent or transiently half-written.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError):
        return default


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    """fcntl.LOCK_EX held on `<path>.lock`, released on exit.

    Instrumented for lock-contention telemetry: captures ``time.monotonic()`` immediately before fcntl.flock(LOCK_EX)
    and again after acquisition + after release, then forwards the deltas
    to ``lock_telemetry.record_lock_event`` for threshold-gated logging.
    Telemetry is fail-open: any error in the recording path is swallowed
    so the lock-release path still runs (close+LOCK_UN).
    """
    if not _HAS_FCNTL:
        # Lockless fallback. os.replace is still atomic; we just lose
        # serialization between concurrent writers.
        yield
        return
    import time as _time  # local import keeps top-level lean
    lock_path = path.with_suffix(path.suffix + ".lock")
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    t_request = _time.monotonic()
    t_acquired: float | None = None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        t_acquired = _time.monotonic()
        try:
            yield
        finally:
            t_released = _time.monotonic()
            try:
                _record_lock_event_safe(path, t_request, t_acquired, t_released)
            except Exception:  # noqa: BLE001 - fail-open contract
                pass
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def _record_lock_event_safe(
    path: Path,
    t_request: float,
    t_acquired: float | None,
    t_released: float,
) -> None:
    """Compute wait/hold deltas and delegate to lock_telemetry.

    Isolated so cache_writer stays dependency-free at module-import time;
    the ``lock_telemetry`` import is lazy and a missing module is silently
    ignored (telemetry is best-effort).
    """
    if t_acquired is None:
        # Acquisition raised before we got the lock - nothing to record.
        return
    wait_ms = (t_acquired - t_request) * 1000.0
    hold_ms = (t_released - t_acquired) * 1000.0
    try:
        from lib.lock_telemetry import record_lock_event  # lazy
    except ImportError:
        try:
            from lock_telemetry import record_lock_event  # lazy (same-dir path)
        except ImportError:
            return  # Telemetry module absent; fail-open.
    record_lock_event(path, wait_ms=wait_ms, hold_ms=hold_ms)


def _remove_silently(p: str | Path) -> None:
    try:
        os.unlink(p)
    except OSError:
        pass


# Public alias of _exclusive_lock for cross-module RMW guards: callers wrap an
# entire load+mutate+save in this context manager to prevent lost-update under
# concurrent writers.
exclusive_lock = _exclusive_lock


__all__ = [
    "CacheWriteError",
    "atomic_write_json",
    "atomic_consume_json",
    "safe_read_json",
    "exclusive_lock",
]
