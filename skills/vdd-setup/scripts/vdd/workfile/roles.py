"""The Working files each hosted Role reads and writes, and where an open
finding's text lives."""

from __future__ import annotations

import os
from typing import Iterable

from .. import textfile
from .frame import Block, Parsed

SPEC = "spec.md"
ISSUES = "issues/"


class RoleFiles:
    """One hosted Role's Working files, as names under the tracker
    directory: what it reads in round 1 and in a later round (the carried
    file exists from round 2), what it writes, the review file it reads
    findings from and the carried file behind it."""

    def __init__(
        self, first: tuple[str, ...], later: tuple[str, ...], write: tuple[str, ...], own: str, review: str,
        carried: str,
    ) -> None:
        self.first = first
        self.later = later
        self.write = write
        self.own = own
        self.review = review
        self.carried = carried

    def read(self, number: int) -> tuple[str, ...]:
        return self.first if number == 1 else self.later


WORKING_FILES = {
    "Plan-Reviewer": RoleFiles((SPEC, ISSUES), ("PLAN-REVIEW.md", SPEC, ISSUES), ("PLAN-REVIEW.md",),
                               "PLAN-REVIEW.md", "PLAN-REVIEW.md", "carried-plan.md"),
    "Coder": RoleFiles((SPEC, ISSUES), ("CODEREVIEW.md", SPEC, ISSUES),
                       ("FIXES.md", ISSUES + " (the ticked checkboxes)"), "FIXES.md", "CODEREVIEW.md",
                       "carried-code.md"),
    "Code-Reviewer": RoleFiles((SPEC, ISSUES, "FIXES.md"), ("CODEREVIEW.md", SPEC, ISSUES), ("CODEREVIEW.md",),
                               "CODEREVIEW.md", "CODEREVIEW.md", "carried-code.md"),
}


def own_files() -> list[str]:
    """Each hosted Role's own file, in the Workflow's order."""
    return [files.own for files in WORKING_FILES.values()]



def open_blocks(directory: str, files: RoleFiles, numbers: Iterable[int]) -> tuple[dict[int, Block], list[int]]:
    """(number -> Block, the numbers not found) of the given open findings:
    from the review file as the last check left it first, then from the
    carried file. One rule decides where an open finding's text lives; each
    caller words its own refusal for the missing."""
    wanted = list(numbers)
    found: dict[int, Block] = {}
    for name in (files.review, files.carried):
        text = textfile.read(os.path.join(directory, name))
        if text is None:
            continue
        for block in Parsed(text).blocks:
            if block.match and block.number in wanted and block.number not in found:
                found[block.number] = block
    return found, [n for n in wanted if n not in found]
