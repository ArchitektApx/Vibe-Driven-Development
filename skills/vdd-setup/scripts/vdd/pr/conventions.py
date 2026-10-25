"""The repository's PR conventions: its PR template, and else its merged-PR
history with each body's headings."""

from __future__ import annotations

import json
import os
import re
import shutil
from typing import Iterable

from .. import markdown
from ..gitcmd import Refused
from .path import gh

TEMPLATE_DIRS = ("", ".github", "docs")
TEMPLATE_NAMES = ("PULL_REQUEST_TEMPLATE.md", "pull_request_template.md")
ISSUE_LINK = re.compile(r"(^|[^\w&])#[0-9]+\b|\b(close[sd]?|fix(e[sd])?|resolve[sd]?)\b[:\s]+\S*[0-9]+", re.I)
HEADING = re.compile(r"^#{1,6}\s+\S")


def template(root: str) -> str | None:
    """The repository-relative path of the first PR template, or None. Names
    are matched exactly, so a case-insensitive file system finds the name on
    disk, not the one asked for."""
    for directory in TEMPLATE_DIRS:
        full = os.path.join(root, directory) if directory else root
        try:
            names = set(os.listdir(full))
        except OSError:
            continue
        for name in TEMPLATE_NAMES:
            if name in names and os.path.isfile(os.path.join(full, name)):
                return "%s/%s" % (directory, name) if directory else name
    return None


class History:
    """The merged-PR history: outcome "history", "none" or "unread", the PRs
    (title, body) newest first, and why."""

    def __init__(self, outcome: str, prs: Iterable[tuple[str, str]] = (), why: str | None = "") -> None:
        self.outcome = outcome
        self.prs = list(prs)
        self.why = why


def history(root: str) -> History:
    """The history, or Refused."""
    if shutil.which("gh") is None:
        return History("none", why="gh is not on PATH")
    result = gh(root, "pr", "list", "--state", "merged", "--limit", "10", "--json", "title,body")
    if result.refused:
        raise Refused(result)
    if result.code != 0:
        return History("unread", why=result.first_error())
    try:
        data = json.loads(result.out or "[]")
    except ValueError:
        return History("unread", why="gh pr list printed no JSON")
    if not isinstance(data, list):
        return History("unread", why="gh pr list printed no list")
    prs = [(str(item.get("title") or ""), str(item.get("body") or "")) for item in data if isinstance(item, dict)]
    if not prs:
        return History("none", why="no merged PR")
    return History("history", prs)


def headings(body: str) -> list[str]:
    lines = markdown.outside_fences(body.replace("\r\n", "\n").split("\n"))
    return [line.strip() for line in lines if HEADING.match(line)]
