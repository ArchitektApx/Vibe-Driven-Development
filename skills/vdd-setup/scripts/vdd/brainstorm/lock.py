"""The idea store's write lock: one writer at a time.

The lock file is created exclusively and holds "<pid> <token> <host>". A lock
whose process is gone on this machine is taken over at once, whatever its
age; one whose process runs is never taken over, however old. Age decides
only where the process cannot be checked: on another machine sharing the
folder, or on a Windows Python without ctypes. A save checks before each
change that the lock still holds its own token, and stops when it does not.
"""

from __future__ import annotations

import binascii
import os
import time
from typing import Any, Callable

from .. import textfile
from ..out import Failure
from .store import rel, state_dir

# A lock whose process cannot be checked is taken over at this age.
LOCK_STALE_SECONDS = 30
# A lock file with no owner in it yet: its writer died between creating it
# and writing its pid, which a live one does within microseconds. It is
# waited for this long, plus a half second, then taken over.
LOCK_EMPTY_SECONDS = 1.0
# The pause seam: a save sleeps this many seconds after it took the lock and
# before its journal, so a test can take the lock over from outside.
PAUSE = "VDD_SAVE_PAUSE_SECONDS"


def host_name() -> str:
    """This machine's name, "" when unknown, so a lock taken on another
    machine that shares the folder is never judged by a local pid."""
    if os.name == "nt":
        return os.environ.get("COMPUTERNAME", "")
    return os.uname().nodename


def pid_alive(pid: int) -> bool | None:
    """Whether process pid runs on this machine: True, False, or None when
    it cannot be told. POSIX: signal 0 checks the pid and sends nothing.
    Windows: os.kill would end the process, so kernel32 is asked."""
    if pid <= 0:
        return None
    if pid == os.getpid():
        return True
    if os.name == "nt":
        return windows_pid_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def windows_pid_alive(pid: int) -> bool | None:
    """OpenProcess with the least right there is: no such process gives
    ERROR_INVALID_PARAMETER (dead), another user's gives ERROR_ACCESS_DENIED
    (alive); an open handle is alive while GetExitCodeProcess says
    STILL_ACTIVE. None on any ctypes failure."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32: Any = getattr(ctypes, "WinDLL")("kernel32", use_last_error=True)
        last_error: Callable[[], int] = getattr(ctypes, "get_last_error")
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        process_query_limited_information, error_access_denied, error_invalid_parameter = 0x1000, 5, 87
        still_active = 259
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            error = last_error()
            if error == error_invalid_parameter:
                return False
            if error == error_access_denied:
                return True
            return None
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return None
            return code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None


class Owner:
    """What a lock file says: its text, pid, host and age in seconds."""

    def __init__(self, raw: str, age: float) -> None:
        self.raw = raw
        bits = raw.split()
        self.pid = int(bits[0]) if bits and bits[0].isdigit() else None
        self.host = bits[2] if len(bits) > 2 else ""
        self.age = max(0.0, age)

    def verdict(self) -> str:
        """"free" (its process is gone, or it is an abandoned empty lock),
        "alive" (its process runs), "starting" (empty, its writer may be about
        to write its pid), or "unknown" (cannot be checked, and not yet
        LOCK_STALE_SECONDS old)."""
        if self.pid is None:
            return "free" if self.age > LOCK_EMPTY_SECONDS else "starting"
        here = host_name()
        alive = pid_alive(self.pid) if not self.host or not here or self.host == here else None
        if alive is False:
            return "free"
        if alive:
            return "alive"
        return "free" if self.age > LOCK_STALE_SECONDS else "unknown"


def read_owner(path: str) -> Owner | None:
    """The lock file's owner, None when it is gone or cannot be read this
    moment (Windows: a lock being deleted)."""
    try:
        age = time.time() - os.path.getmtime(path)
        raw = textfile.read_bytes(path).decode("utf-8", "replace").strip()
    except (FileNotFoundError, PermissionError):
        return None
    return Owner(raw, age)


class LockLost(Failure):
    """This run's lock was taken over while it ran."""


class Lock:
    """The lock at path, the store's .state/lock by default. With wait
    False, a lock held by another process is left alone instead of refused
    (held stays False). wait_seconds is how long a live holder is waited for
    before the refusal. doing words what a refused Session was doing.
    on_take runs once the lock is taken, still inside it: the store's
    recovery."""

    def __init__(self, root: str, path: str | None = None, wait: bool = True, wait_seconds: float = 0.0,
                 doing: str = "writing to the idea store",
                 on_take: Callable[[Lock], list[str]] | None = None) -> None:
        self.root = root
        self.path = path or os.path.join(state_dir(root), "lock")
        self.wait = wait
        self.wait_seconds = wait_seconds
        self.doing = doing
        self.on_take = on_take
        self.held = False
        self.mine = ""
        self.recovered: list[str] = []

    def where(self) -> str:
        return rel(self.root, self.path)

    def take(self) -> bool:
        self.mine = ("%d %s %s" % (os.getpid(), binascii.hexlify(os.urandom(8)).decode("ascii"), host_name())).strip()
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            return False
        except PermissionError:
            if os.name == "nt":
                return False  # a lock in Windows' delete-pending state
            raise
        try:
            os.write(fd, self.mine.encode("utf-8"))
        except BaseException:
            os.close(fd)
            try:
                os.remove(self.path)
            except OSError:
                pass
            raise
        os.close(fd)
        self.held = True
        return True

    def __enter__(self) -> Lock:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        start = time.monotonic()
        for _ in range(400):
            if self.take():
                break
            owner = read_owner(self.path)
            if owner is None:
                time.sleep(0.02)
                continue
            verdict = owner.verdict()
            if verdict == "free":
                self.clear(owner)
                continue
            waited = time.monotonic() - start
            if verdict == "starting" and waited < LOCK_EMPTY_SECONDS + 0.5:
                time.sleep(0.1)
                continue
            if verdict == "alive" and self.wait and waited < self.wait_seconds:
                time.sleep(0.2)
                continue
            if not self.wait:
                return self
            raise self.refusal(owner, verdict)
        else:
            raise Failure("The lock %s could not be taken. Nothing was written." % self.where(),
                          "Run the same command again.")
        if self.on_take is not None:
            try:
                self.recovered = self.on_take(self)
            except BaseException:
                self.release()
                raise
        return self

    def clear(self, owner: Owner) -> None:
        """Remove a lock judged free, unless it changed since it was read."""
        again = read_owner(self.path)
        if again is not None and again.raw == owner.raw:
            try:
                os.remove(self.path)
            except OSError:
                time.sleep(0.02)

    def refusal(self, owner: Owner, verdict: str) -> Failure:
        who = "process %s" % owner.pid if owner.pid else "a process that wrote no pid"
        if verdict == "alive":
            return Failure(
                "Another Session is %s right now: %s, still running, took %s %d s ago. Nothing was written."
                % (self.doing, who, self.where(), owner.age),
                "Run the same command again in a few seconds. If it still refuses after a minute, tell the user that "
                "%s holds %s: if no VDD command of theirs is running, they can delete that file. Then stop."
                % (who, self.where()))
        return Failure(
            "%s was taken %d s ago by %s%s, which cannot be checked from here. Nothing was written."
            % (self.where(), owner.age, who, (" on %s" % owner.host) if owner.host else ""),
            "Run the same command again in %d s: a lock whose process cannot be checked from here is taken over "
            "once it is %d s old." % (max(1, int(LOCK_STALE_SECONDS - owner.age) + 1), LOCK_STALE_SECONDS))

    def confirm(self) -> None:
        """Raise LockLost when the lock file no longer holds this run's
        token."""
        owner = read_owner(self.path)
        if owner is None or owner.raw != self.mine:
            self.held = False
            raise LockLost(
                "This command stalled, and another Session took over %s meanwhile. This command stopped before its "
                "next change and wrote nothing more; the next command finishes or rolls back what it began."
                % self.where(),
                "Run brainstorm start, then the same command again if the user still wants it.")

    def pause(self) -> None:
        """The pause seam, unset in every Role's run."""
        try:
            seconds = float(os.environ.get(PAUSE, "") or 0)
        except ValueError:
            seconds = 0.0
        if seconds > 0:
            time.sleep(seconds)

    def release(self) -> None:
        if self.held:
            self.held = False
            owner = read_owner(self.path)
            if owner is not None and owner.raw == self.mine:
                try:
                    os.remove(self.path)
                except OSError:
                    pass

    def __exit__(self, kind: object, error: object, trace: object) -> None:
        """Release the lock. A refusal inside it carries the recovery's lines
        first: the journal is settled and gone, so they are never printed
        again."""
        self.release()
        if isinstance(error, Failure) and self.recovered:
            error.lines = self.recovered + error.lines
            self.recovered = []
