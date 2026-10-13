"""Reading files: bytes decoded as UTF-8 with replacement, CRLF and CR read as
LF, a leading byte order mark dropped. The default encoding is never relied
on: on Windows it is the ANSI code page. Writing files: whole, through a
temporary file in the same directory renamed over the target."""

import os
import time


def decode(data):
    text = data.decode("utf-8", "replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read(path, retry_seconds=0.0):
    """The file's text, or None when it does not exist.

    With retry_seconds, a PermissionError is retried until that much time has
    passed: on Windows a sharing violation and a denial look alike."""
    deadline = time.monotonic() + retry_seconds
    while True:
        try:
            with open(path, "rb") as handle:
                return decode(handle.read())
        except FileNotFoundError:
            return None
        except NotADirectoryError:
            return None
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


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
