"""pr-body.md, the PR-Author's Working file: the title on its first line, a
blank line, then the body."""

from __future__ import annotations

import os
import re

from .. import loopfile, textfile
from ..out import Failure

NAME = "pr-body.md"


def read_body(loop: loopfile.Loop) -> tuple[str, str]:
    """(title, body) from pr-body.md, or a Failure naming what is wrong."""
    relative = "%s/%s" % (loop.tracker, NAME)
    text = textfile.read(os.path.join(loop.dir, NAME))
    problem = None
    if text is None:
        problem = "%s does not exist" % relative
    else:
        lines = text.split("\n")
        if not title_of(lines[0]):
            problem = "%s has no title on its first line" % relative
        elif len(lines) < 2 or lines[1].strip():
            problem = "%s has no blank second line between the title and the body" % relative
        elif not "\n".join(lines[2:]).strip():
            problem = "%s has no body after the blank line" % relative
    if problem or text is None:
        raise Failure(
            "%s. Nothing was pushed." % problem,
            "Write %s with your file tool: the title as the first line, a blank line, then the body, as the user "
            "confirmed them. Then run the same command again." % relative,
        )
    lines = text.split("\n")
    body = "\n".join(lines[2:]).strip("\n") + "\n"
    return title_of(lines[0]), body


def title_of(line: str) -> str:
    """The title line as plain text: a Markdown heading's "# " is not part of
    the title."""
    return re.sub(r"^#{1,6}\s+", "", line.strip()).strip()
