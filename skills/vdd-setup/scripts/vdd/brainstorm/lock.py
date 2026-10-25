"""The idea store's locks: one writer at a time, held by the kernel.

A lock file is permanent: opened with create, never deleted. Its holder
takes a non-blocking exclusive kernel lock on it (flock on POSIX, one byte at
LOCK_OFFSET on Windows), so a dead holder's lock is free at once, and writes
its pid at offset 0 for another Session's refusal. A writer waits up to
WAIT_SECONDS for a holder; a read tries once.
"""

from __future__ import annotations

import errno
import os
import sys
import time
from typing import Callable

from .. import textfile
from ..out import Failure
from .store import rel, state_dir

WAIT_SECONDS = 5.0
POLL_SECONDS = 0.2
# Windows locks a byte here, beyond the pid at offset 0, so a reader of the
# pid never meets the locked range.
LOCK_OFFSET = 1 << 20

if sys.platform == "win32":
    import msvcrt

    HELD = (errno.EACCES, errno.EDEADLOCK)

    def lock_fd(fd: int) -> None:
        os.lseek(fd, LOCK_OFFSET, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def unlock_fd(fd: int) -> None:
        os.lseek(fd, LOCK_OFFSET, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    HELD = (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES)

    def lock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def unlock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


def holder(path: str) -> str:
    """Who holds the lock at path, as its file says: "process <pid>", or "a
    process that wrote no pid"."""
    try:
        with open(path, "rb", buffering=0) as handle:
            text = handle.read(32).decode("ascii", "replace").strip()
    except OSError:
        text = ""
    return "process %s" % text if text.isdigit() else "a process that wrote no pid"


class Lock:
    """The lock at path, the store's .state/lock by default. With wait
    False, a held lock is tried once and left alone (fd stays None);
    otherwise a holder is waited for up to WAIT_SECONDS, then refused. doing
    words what a refused Session was doing. on_take runs once the lock is
    taken, still inside it: the store's recovery. lines holds what the
    command prints first: the fallback's line and the recovery's."""

    def __init__(self, root: str, path: str | None = None, wait: bool = True,
                 doing: str = "writing to the idea store",
                 on_take: Callable[[Lock], list[str]] | None = None) -> None:
        self.root = root
        self.path = path or os.path.join(state_dir(root), "lock")
        self.wait = wait
        self.doing = doing
        self.on_take = on_take
        self.fd: int | None = None
        self.lines: list[str] = []

    def where(self) -> str:
        return rel(self.root, self.path)

    def open(self) -> int:
        """The lock file opened for reading and writing, created when
        missing; a Failure naming it when it cannot be opened."""
        try:
            return os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        except OSError as error:
            raise Failure("The idea store's lock file %s could not be opened (%s). Nothing was written."
                          % (self.where(), textfile.reason(error)),
                          "Tell the user %s cannot be opened as a file and needs a look (a folder or a permission "
                          "in its place?), then stop." % self.where())

    def take(self) -> str:
        """One try: "taken", "held", "replaced" (the path names another file
        now) or "unsupported" (the fallback's line is in lines)."""
        fd = self.open()
        try:
            lock_fd(fd)
        except OSError as error:
            os.close(fd)
            if error.errno in HELD:
                return "held"
            self.lines.append("The idea store's lock is not supported here (%s); this command went ahead without it."
                              % textfile.reason(error))
            return "unsupported"
        try:
            on_disk = os.stat(self.path)
            mine = os.fstat(fd)
            if (on_disk.st_dev, on_disk.st_ino) != (mine.st_dev, mine.st_ino):
                raise FileNotFoundError(self.path)
        except OSError:
            unlock_fd(fd)
            os.close(fd)
            return "replaced"
        try:
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, str(os.getpid()).encode("ascii"))
        except BaseException:
            unlock_fd(fd)
            os.close(fd)
            raise
        self.fd = fd
        return "taken"

    def __enter__(self) -> Lock:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        deadline = time.monotonic() + WAIT_SECONDS
        while True:
            got = self.take()
            if got in ("taken", "unsupported"):
                break
            # "held" or "replaced": a path that keeps naming another file
            # waits and refuses as a held lock does.
            if not self.wait:
                return self
            if time.monotonic() >= deadline:
                who = holder(self.path)
                raise Failure("Another Session is %s right now (%s). Nothing was written." % (self.doing, who),
                              "Run the same command again. If it refuses again, tell the user another VDD command "
                              "(%s) is %s, and stop." % (who, self.doing))
            time.sleep(POLL_SECONDS)
        if self.on_take is not None:
            try:
                self.lines += self.on_take(self)
            except BaseException:
                self.release()
                raise
        return self

    def release(self) -> None:
        if self.fd is not None:
            fd, self.fd = self.fd, None
            try:
                unlock_fd(fd)
            finally:
                os.close(fd)

    def __exit__(self, kind: object, error: object, trace: object) -> None:
        """Release the lock. A refusal inside it carries lines first: the
        journal is settled and gone, so they are never printed again."""
        self.release()
        if isinstance(error, Failure) and self.lines:
            error.lines = self.lines + error.lines
            self.lines = []
