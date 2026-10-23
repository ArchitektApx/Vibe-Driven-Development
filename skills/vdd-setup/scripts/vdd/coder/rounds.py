"""A code round: the Round a coder command acts on, the round's Tickets
and open findings, and the precondition a round starts from."""

from __future__ import annotations

import os
import re

from .. import catalog, doorbells, fixes, loopfile, loopstate, textfile, workfile
from ..out import Failure

TICKET_FILE = re.compile(r"^([0-9]+)-.+\.md$")
SNAPSHOT = "coder-untracked-%d"


class Round:
    """The code round a command acts on."""

    def __init__(self, loop: loopfile.Loop, state: loopstate.State) -> None:
        self.loop = loop
        self.state = state
        self.base = loop.base
        self.branch = loop.branch
        self.file = os.path.join(loop.dir, fixes.NAME)
        self.relative = "%s/%s" % (loop.tracker, fixes.NAME)
        newest = state.code_round()
        self.newest = newest
        self.started = bool(newest) and state.code_mark("end", newest) is None
        self.number = newest if self.started else newest + 1
        previous = state.review("code", self.number - 1) if self.number > 1 else None
        self.previous = previous
        self.open_numbers: list[int] = list(previous.open) if previous else []

    def command(self, sub: str, write: bool = True) -> str:
        return catalog.line("coder", sub, slug=self.loop.slug, write=write)

    def snapshot_name(self) -> str:
        return SNAPSHOT % self.number

    def snapshot(self) -> list[str] | None:
        """The untracked files recorded when the round started, or None for a
        round started on a version that recorded none."""
        text = textfile.read(os.path.join(self.loop.dir, self.snapshot_name()))
        if text is None:
            return None
        return [line for line in text.split("\n") if line]

    def path(self, name: str) -> str:
        return self.loop.path(name)

    def read_list(self) -> list[str]:
        return [self.path(name) for name in workfile.WORKING_FILES["Coder"].read(self.number)]

    def tickets(self) -> list[tuple[str, str]]:
        return tickets(self.loop)

    def open_findings(self) -> list[tuple[int, str, str]]:
        return open_findings(self)


def tickets(loop: loopfile.Loop) -> list[tuple[str, str]]:
    """(NN, file name) of every Ticket file, in NN order."""
    directory = os.path.join(loop.dir, "issues")
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    found = []
    for name in names:
        match = TICKET_FILE.match(name)
        if match and os.path.isfile(os.path.join(directory, name)):
            found.append((match.group(1), name))
    return sorted(found, key=lambda item: (int(item[0]), item[1]))


def precondition(round_: Round) -> None:
    """Refuse a round the position does not owe the Coder."""
    state = round_.state
    where = doorbells.Place(round_.loop.root, round_.loop.slug, round_.loop, state).position()
    if where.owed_by("Coder", round_.number):
        return
    plan = state.last_review("plan")
    if where.owed_by("Plan-Reviewer") and plan is not None and plan.signed_off:
        raise Failure(
            "The Planner rang plan round %d after the plan Sign-off: the changed Spec is reviewed before the "
            "code Loop starts. Nothing was written." % where.round,
            "End your turn with BLOCKED: plan round %d is not reviewed yet." % where.round,
        )
    if round_.newest:
        review = state.review("code", round_.newest)
        if review is None:
            raise Failure(
                "Code round %d ended and waits for its review: there is no round %d for the Coder yet. Nothing "
                "was written." % (round_.newest, round_.number),
                "End your turn with BLOCKED: code round %d is not reviewed yet." % round_.newest,
            )
        if review.signed_off:
            raise Failure(
                "The code Loop signed off in round %d: there is no round %d for the Coder. Nothing was written."
                % (round_.newest, round_.number),
                "End your turn with BLOCKED: the code Loop is already signed off.",
            )
        raise Failure(
            "There is no code round %d for the Coder now: the %s owes the next move. Nothing was written."
            % (round_.number, where.owes),
            "End your turn with BLOCKED: the %s owes the next move." % where.owes,
        )
    raise Failure(
        "The plan Loop is not finished: the plan review has not signed off, so the Spec is no contract yet. "
        "Nothing was written.",
        "End your turn with BLOCKED: the plan Loop is not signed off.",
    )


def open_findings(round_: Round) -> list[tuple[int, str, str]]:
    """(number, severity, reference) of every finding the last review left
    open, from CODEREVIEW.md's headings, else carried-code.md's."""
    blocks, missing = workfile.open_blocks(round_.loop.dir, workfile.WORKING_FILES["Coder"], round_.open_numbers)
    found = dict((n, (n, b.severity, b.reference)) for n, b in blocks.items())
    if missing:
        raise Failure(
            "CODEREVIEW.md has no heading for finding%s %s, which round %d's review left open. Nothing was "
            "written." % ("" if len(missing) == 1 else "s", workfile.join_numbers(missing), round_.number - 1),
            "Tell the user CODEREVIEW.md lost a finding the loop still has open, and stop.",
        )
    return [found[n] for n in round_.open_numbers]
