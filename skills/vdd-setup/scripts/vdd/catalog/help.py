"""The helps the catalog prints: a group's help text, and the top-level help
with the list of groups."""

from __future__ import annotations

from typing import Iterable

from .. import places
from ..out import Output
from .specs import GROUPS

ABOUT = [
    "The VDD tool: the program Vibe Driven Development's Roles run.",
    "Run it as %s <group> ... (python3 on macOS and Linux, py -3 on native Windows).",
    "Every command prints plain text, one fact per line, and ends with a Next: line naming your next step.",
    'A line starting Tell the user verbatim: "..." is for the user: relay the quoted text unchanged.',
    "The exit code is zero or not; the reason is always in the text.",
]


def group(lines: Iterable[str], next_step: str) -> int:
    """Print a group's help lines and its Next: step."""
    out = Output()
    for line in lines:
        out.line(line)
    return out.finish(next_step)


def top() -> int:
    """The top-level help: what the tool is, and every group."""
    out = Output()
    for text in ABOUT:
        out.line(text % places.command() if "%s" in text else text)
    out.line()
    out.line("Command groups:")
    for name in sorted(GROUPS):
        out.line("  %-13s %s" % (name, GROUPS[name]))
    return out.finish("Run %s <group> --help for the group your skill names." % places.command())
