"""The format of removed.md, cleanup's record of the ideas it removed from
the store: one line per idea, slug | title | status | closed | removed |
the Decision's gist."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .ideafile import SLUG, today

if TYPE_CHECKING:
    from .ideafile import Idea

REMOVED = "removed.md"
REMOVED_HEAD = ("# Removed ideas\n\nIdeas brainstorm cleanup removed from the store, one line each: slug | title | "
                "status | closed | removed | the Decision's gist.\n\n")


def entries(text: str) -> list[dict[str, str]]:
    """[{slug, title, status, closed, removed, gist}] of removed.md's text,
    oldest first."""
    out: list[dict[str, str]] = []
    for line in text.split("\n"):
        if not line.startswith("- "):
            continue
        bits = [b.strip() for b in line[2:].split(" | ")]
        if len(bits) < 6 or not SLUG.match(bits[0]):
            continue
        out.append({"slug": bits[0], "title": bits[1], "status": bits[2],
                    "closed": bits[3].replace("closed ", ""), "removed": bits[4].replace("removed ", ""),
                    "gist": " | ".join(bits[5:])})
    return out


def removed_line(idea: Idea, closed: str | None, gist: str) -> str:
    return "- %s | %s | %s | closed %s | removed %s | %s\n" % (
        idea.slug, idea.title.replace("|", "/"), idea.status, closed or "unknown", today(),
        " ".join(gist.replace(" | ", " / ").split()))


def removed_reopen(entry: dict[str, str]) -> str:
    match = re.search(r"Reopen when:\s*(.+)$", entry["gist"])
    return match.group(1).strip() if match else ""
