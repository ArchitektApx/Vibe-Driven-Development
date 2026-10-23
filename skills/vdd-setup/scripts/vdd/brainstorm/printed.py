"""What the brainstorm commands print around idea text: the quote that sets
an idea's own line apart from the tool's, and the result every write
returns."""

from __future__ import annotations

from typing import List, Tuple

from .. import catalog
from .ideafile import squash

QUOTE = "  > "


def command(name: str, **options: catalog.Value) -> str:
    """A brainstorm command as the group's own lines name it: without the
    tool's path, the form the Brainstormer's skill teaches."""
    return catalog.bare("brainstorm", name, **options)


MIGRATE = command("migrate", write=True)
START = command("start")

# A write's (lines, Next: step, label): the group saves the Store, or prints
# a dry run.
Result = Tuple[List[str], str, str]


def quoted(text: str) -> str:
    return QUOTE + squash(text)


def step_line(text: str) -> str:
    return QUOTE + "[ ] " + squash(text)
