"""What the brainstorm commands print around idea text: the quote that sets
an idea's own line apart from the tool's, and the result every write
returns."""

from __future__ import annotations

from typing import List, Tuple

from .ideafile import squash

QUOTE = "  > "

# A write's (lines, Next: step, label): the group saves the Store, or prints
# a dry run.
Result = Tuple[List[str], str, str]


def quoted(text: str) -> str:
    return QUOTE + squash(text)


def step_line(text: str) -> str:
    return QUOTE + "[ ] " + squash(text)
