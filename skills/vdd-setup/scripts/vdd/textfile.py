"""Reading files: bytes decoded as UTF-8 with replacement, CRLF and CR read as
LF, a leading byte order mark dropped. The default encoding is never relied
on: on Windows it is the ANSI code page. Writing files: whole, through a
temporary file in the same directory renamed over the target."""

from __future__ import annotations

import os
import time
from typing import Callable, Container, Iterable, TypeVar

from .out import Failure, refused


def decode(data: bytes) -> str:
    text = data.decode("utf-8", "replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


# A PermissionError is retried this long on Windows, where a file another
# process holds open for a moment (a sharing violation) and a denial look
# alike. On POSIX a PermissionError is a denial and is raised at once.
RETRY_SECONDS = 2.0
WINDOWS = os.name == "nt"

T = TypeVar("T")


def retried(action: Callable[[], T]) -> T:
    """action(), with a PermissionError retried for RETRY_SECONDS on Windows
    only. Raises the last error when the time runs out, and at once on
    POSIX."""
    deadline = time.monotonic() + RETRY_SECONDS
    while True:
        try:
            return action()
        except PermissionError:
            if not WINDOWS or time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


def read_bytes(path: str) -> bytes:
    """The file's bytes, retried as retried says. Raises OSError,
    FileNotFoundError included."""

    def read_once() -> bytes:
        with open(path, "rb") as handle:
            return handle.read()

    return retried(read_once)


def read(path: str) -> str | None:
    """The file's text, or None when it does not exist."""
    try:
        return decode(read_bytes(path))
    except FileNotFoundError:
        return None
    except NotADirectoryError:
        return None


def lines(path: str) -> list[str] | None:
    """The file's lines without line ends, or None when it does not exist."""
    text = read(path)
    if text is None:
        return None
    if text.endswith("\n"):
        text = text[:-1]
    return text.split("\n") if text else []


def write(path: str, data: bytes) -> None:
    """Write bytes to path whole: a reader sees the old file or the new one.

    The rename is retried as retried says: on Windows a reader holding the
    file open makes os.replace fail for a moment. Raises OSError when the
    write fails, leaving the old file in place."""
    temp = "%s.vdd-new-%d" % (path, os.getpid())
    try:
        with open(temp, "wb") as handle:
            handle.write(data)
        retried(lambda: os.replace(temp, path))
    finally:
        if os.path.lexists(temp):
            try:
                os.remove(temp)
            except OSError:
                pass


def write_text(path: str, text: str) -> None:
    """write, with text encoded as UTF-8."""
    write(path, text.encode("utf-8"))


def write_refusal(what: str, error: OSError, otherwise: str, extra: Iterable[str] = ()) -> Failure:
    """The Failure for a write that failed: "Could not write <what>: <error>",
    then the extra lines. <error> is reason(error). otherwise is its Next:
    step after the one escalated retry (out.refused)."""
    return refused(["Could not write %s: %s" % (what, reason(error))] + list(extra), otherwise)


def reason(error: Exception) -> str:
    """An error's strerror, or the whole error when it has none (an OSError
    raised with a message, or another exception): the whole OSError repeats
    the absolute path, escaped on Windows."""
    return getattr(error, "strerror", None) or str(error)


def described(error: Exception) -> str:
    """reason(error), after the file it names as shown() prints it, for a
    line that does not name the file itself. A failed rename or replace
    names its target too."""
    filename = getattr(error, "filename", None)
    if isinstance(filename, str) and getattr(error, "strerror", None):
        target = getattr(error, "filename2", None)
        if isinstance(target, str):
            return "%s, moving it to %s: %s" % (shown(filename), shown(target), reason(error))
        return "%s: %s" % (shown(filename), reason(error))
    return reason(error)


def shown(path: str) -> str:
    """A path in a loop's tracker directory as the tool prints it, from
    .scratch/ on with / between its parts; any other path as it is."""
    parts = os.path.normpath(path).split(os.sep)
    if ".scratch" not in parts:
        return path
    start = len(parts) - 1 - parts[::-1].index(".scratch")
    return "/".join(parts[start:])


def write_or_refuse(path: str, text: str, what: str, otherwise: str, extra: Iterable[str] = ()) -> None:
    """write_text, or raise write_refusal when the write fails."""
    try:
        write_text(path, text)
    except OSError as error:
        raise write_refusal(what, error, otherwise, extra)


def append(path: str, text: str, header: str = "") -> None:
    """Append text to path, whole in one write; header goes first when the
    file is new, missing or empty. Raises OSError when the write fails."""
    data = text
    if header and (not os.path.exists(path) or os.path.getsize(path) == 0):
        data = header + text
    with open(path, "ab") as handle:
        handle.write(data.encode("utf-8"))


def check_header(path: str, lines: list[str], prefix: str, versions: Container[str]) -> str | None:
    """The version a file's first line carries after prefix, or None when the
    file has no such header. Raises the Failure for a version not in versions:
    this copy of the VDD tool is older than the file."""
    if not lines or not lines[0].startswith(prefix):
        return None
    version = lines[0][len(prefix):].strip()
    if version not in versions:
        raise Failure(
            "%s has format version %s, which this copy of the VDD tool does not know." % (shown(path), version),
            "Tell the user this copy of the VDD tool is out of date and to rerun Setup.",
        )
    return version
