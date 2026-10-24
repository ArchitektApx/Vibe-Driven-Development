"""pr-body.md, the PR-Author's Working file: the title on its first line, a
blank line, then the body."""

from __future__ import annotations

import os
import re
from typing import NamedTuple, Optional

from . import loopfile, textfile

NAME = "pr-body.md"


# Why pr-body.md cannot be read as a title and a body.
MISSING = "missing"
NO_TITLE = "no title"
NO_BLANK_LINE = "no blank line"
NO_BODY = "no body"


class Body(NamedTuple):
    """pr-body.md as read: the title and the body, or the problem that keeps
    it from being read as one: MISSING, NO_TITLE, NO_BLANK_LINE or NO_BODY,
    None when it reads."""
    title: str
    body: str
    problem: Optional[str]


def relative(loop: loopfile.Loop) -> str:
    """pr-body.md's path from the repository root."""
    return "%s/%s" % (loop.tracker, NAME)


def read(loop: loopfile.Loop) -> Body:
    """pr-body.md's title and body, or its problem."""
    text = textfile.read(os.path.join(loop.dir, NAME))
    if text is None:
        return Body("", "", MISSING)
    lines = text.split("\n")
    if not title_of(lines[0]):
        return Body("", "", NO_TITLE)
    if len(lines) < 2 or lines[1].strip():
        return Body("", "", NO_BLANK_LINE)
    if not "\n".join(lines[2:]).strip():
        return Body("", "", NO_BODY)
    return Body(title_of(lines[0]), "\n".join(lines[2:]).strip("\n") + "\n", None)


def title_of(line: str) -> str:
    """The title line as plain text: a Markdown heading's "# " is not part of
    the title."""
    return re.sub(r"^#{1,6}\s+", "", line.strip()).strip()
