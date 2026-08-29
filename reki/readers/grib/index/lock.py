"""Per-index advisory locking (POSIX v1 implementation)."""

from contextlib import contextmanager
import os
import time


@contextmanager
def target_lock(path, timeout=30.0):
    try:
        import fcntl
    except ImportError as error:  # pragma: no cover - Windows adapter follows later
        raise RuntimeError("persistent GRIB indexes require a platform lock") from error
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"timed out waiting for index lock: {path}")
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
