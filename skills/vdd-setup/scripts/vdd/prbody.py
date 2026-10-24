"""pr-body.md, the PR-Author's Working file: the title on its first line, a
blank line, then the body."""

from __future__ import annotations

import os
import re
from typing import NamedTuple

from . import loopfile, textfile

NAME = "pr-body.md"


class Body(NamedTuple):
    """pr-body.md as read: the title and the body, or the problem that keeps
    it from being read as one."""
    title: str
    body: str
    problem: str


def relative(loop: loopfile.Loop) -> str:
    """pr-body.md's path from the repository root."""
    return "%s/%s" % (loop.tracker, NAME)


def read(loop: loopfile.Loop) -> Body:
    """pr-body.md's title and body, or its problem: it does not exist, has no
    title, no blank second line or no body."""
    text = textfile.read(os.path.join(loop.dir, NAME))
    if text is None:
        return Body("", "", "%s does not exist" % relative(loop))
    lines = text.split("\n")
    if not title_of(lines[0]):
        return Body("", "", "%s has no title on its first line" % relative(loop))
    if len(lines) < 2 or lines[1].strip():
        return Body("", "", "%s has no blank second line between the title and the body" % relative(loop))
    if not "\n".join(lines[2:]).strip():
        return Body("", "", "%s has no body after the blank line" % relative(loop))
    return Body(title_of(lines[0]), "\n".join(lines[2:]).strip("\n") + "\n", "")


def title_of(line: str) -> str:
    """The title line as plain text: a Markdown heading's "# " is not part of
    the title."""
    return re.sub(r"^#{1,6}\s+", "", line.strip()).strip()
