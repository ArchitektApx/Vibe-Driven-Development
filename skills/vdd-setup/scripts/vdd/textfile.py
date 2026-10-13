"""Reading files: bytes decoded as UTF-8 with replacement, CRLF and CR read as
LF, a leading byte order mark dropped. The default encoding is never relied
on: on Windows it is the ANSI code page."""

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
