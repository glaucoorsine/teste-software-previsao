# -*- coding: utf-8 -*-
"""Lock de arquivo portátil (Windows + Linux) sem depender só de fcntl."""
from __future__ import annotations
import os
import time
import uuid
from pathlib import Path
from contextlib import contextmanager

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore

try:
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore


@contextmanager
def file_lock(lock_path: Path, timeout: float = 30.0, poll: float = 0.05):
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a+b")
    start = time.time()
    locked = False
    try:
        while True:
            try:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                    break
                elif msvcrt is not None:
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                else:
                    # fallback: exclusive create of sibling lock token
                    token = lock_path.with_suffix(lock_path.suffix + f".{os.getpid()}.{uuid.uuid4().hex}.tok")
                    try:
                        fd = os.open(str(token), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        os.close(fd)
                        # claim master by rename if not exists
                        master = lock_path.with_suffix(lock_path.suffix + ".taken")
                        if not master.exists():
                            os.rename(str(token), str(master))
                            locked = True
                            fh._tok_master = master  # type: ignore
                            break
                        else:
                            token.unlink(missing_ok=True)
                    except FileExistsError:
                        token.unlink(missing_ok=True)
            except (BlockingIOError, OSError, PermissionError):
                pass
            if time.time() - start > timeout:
                raise TimeoutError(f"lock timeout: {lock_path}")
            time.sleep(poll)
        yield
    finally:
        try:
            if locked:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                elif msvcrt is not None:
                    try:
                        fh.seek(0)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                else:
                    master = getattr(fh, "_tok_master", None)
                    if master is not None:
                        Path(master).unlink(missing_ok=True)
        finally:
            fh.close()


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.{uuid.uuid4().hex}.tmp")
    with open(tmp, "w", encoding=encoding) as f:
        f.write(text)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    os.replace(str(tmp), str(path))
