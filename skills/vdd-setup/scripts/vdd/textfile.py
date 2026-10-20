"""Reading files: bytes decoded as UTF-8 with replacement, CRLF and CR read as
LF, a leading byte order mark dropped. The default encoding is never relied
on: on Windows it is the ANSI code page. Writing files: whole, through a
temporary file in the same directory renamed over the target."""

import os
import time

from .out import Failure, refused


def decode(data):
    text = data.decode("utf-8", "replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_bytes(path, retry_seconds=0.0):
    """The file's bytes. Raises OSError, FileNotFoundError included.

    With retry_seconds, a PermissionError is retried until that much time has
    passed: on Windows a sharing violation and a denial look alike."""
    deadline = time.monotonic() + retry_seconds
    while True:
        try:
            with open(path, "rb") as handle:
                return handle.read()
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


def read(path, retry_seconds=0.0):
    """The file's text, or None when it does not exist. retry_seconds as in
    read_bytes."""
    try:
        return decode(read_bytes(path, retry_seconds))
    except FileNotFoundError:
        return None
    except NotADirectoryError:
        return None


def lines(path, retry_seconds=0.0):
    """The file's lines without line ends, or None when it does not exist."""
    text = read(path, retry_seconds)
    if text is None:
        return None
    if text.endswith("\n"):
        text = text[:-1]
    return text.split("\n") if text else []


def write(path, data):
    """Write bytes to path whole: a reader sees the old file or the new one.

    The rename is retried on PermissionError for two seconds: on Windows a
    reader holding the file open makes os.replace fail for a moment. Raises
    OSError when the write fails, leaving the old file in place."""
    temp = "%s.vdd-new-%d" % (path, os.getpid())
    try:
        with open(temp, "wb") as handle:
            handle.write(data)
        for attempt in range(20):
            try:
                os.replace(temp, path)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.1)
    finally:
        if os.path.lexists(temp):
            try:
                os.remove(temp)
            except OSError:
                pass


def write_text(path, text):
    """write, with text encoded as UTF-8."""
    write(path, text.encode("utf-8"))


def write_refusal(what, error, otherwise, extra=()):
    """The Failure for a write that failed: "Could not write <what>: <error>",
    then the extra lines. otherwise is its Next: step after the one escalated
    retry (out.refused)."""
    return refused(["Could not write %s: %s" % (what, error)] + list(extra), otherwise)


def write_or_refuse(path, text, what, otherwise, extra=()):
    """write_text, or raise write_refusal when the write fails."""
    try:
        write_text(path, text)
    except OSError as error:
        raise write_refusal(what, error, otherwise, extra)


def append(path, text, header=""):
    """Append text to path, whole in one write; header goes first when the
    file is new, missing or empty. Raises OSError when the write fails."""
    data = text
    if header and (not os.path.exists(path) or os.path.getsize(path) == 0):
        data = header + text
    with open(path, "ab") as handle:
        handle.write(data.encode("utf-8"))


def check_header(path, lines, prefix, versions):
    """The version a file's first line carries after prefix, or None when the
    file has no such header. Raises the Failure for a version not in versions:
    this copy of the VDD tool is older than the file."""
    if not lines or not lines[0].startswith(prefix):
        return None
    version = lines[0][len(prefix):].strip()
    if version not in versions:
        raise Failure(
            "%s has format version %s, which this copy of the VDD tool does not know." % (path, version),
            "Tell the user this copy of the VDD tool is out of date and to rerun Setup.",
        )
    return version
