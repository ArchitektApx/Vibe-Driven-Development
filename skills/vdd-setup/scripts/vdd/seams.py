"""Test seams: environment values that set one of the tool's timings, so a
test need not wait the real time. A user never sets one."""

from __future__ import annotations

import os


def seconds(name: str, default: float) -> float:
    """The seam's value in seconds, or default when it is unset or not a
    finite positive number: "ten", "0", "-1", "nan" and "inf" all fall back,
    so a bad value neither crashes, busy-polls nor waits for ever."""
    text = os.environ.get(name)
    if not text:
        return default
    try:
        value = float(text)
    except ValueError:
        return default
    return value if 0 < value < float("inf") else default
