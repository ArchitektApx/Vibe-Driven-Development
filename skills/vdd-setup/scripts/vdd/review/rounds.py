"""A review round: the reviewers' constants, the Round a command acts on
and its precondition, and the status line a check writes. The review and
add modules both read it, so it imports neither."""

from __future__ import annotations

import os
import re

from .. import doorbells, gitcmd, loopfile, loopstate, places, workfile
from ..out import Failure
from . import agentdocs

REVIEWERS = {"Plan-Reviewer": "plan", "Code-Reviewer": "code"}
TITLES = {"plan": "Plan review", "code": "Code review"}
NO_AGENT_DOCUMENT = "no Agent document in this round's diff"
NO_COMMITS = "not needed, no commits in this round"
LABELS = ("Resolution", "Coder", "Reviewer")

STATUS_LINE = re.compile(r"^(Open: [0-9]+ blocker, [0-9]+ major, [0-9]+ minor\.|SIGNED OFF\. Nothing open\."
                         r"|SIGNED OFF\. Open minors left, as Minors: leave allows: [0-9]+\.)\s*$")

CHECKS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "plan": (("writing-for-agents", ("ran", "did not resolve")),),
    "code": (
        ("code-review", ("ran", "did not resolve, the Spec reviewed by hand")),
        ("writing-for-agents", ("ran", "did not resolve")),
    ),
}

NOT_NEEDED = "not needed, "


class Round:
    """The review round a command acts on: the next one after the last
    recorded review."""

    def __init__(self, loop: loopfile.Loop, state: loopstate.State, role: str, number: int | None = None) -> None:
        """The next round, or with number the round number as it stood before
        it was recorded."""
        self.loop = loop
        self.state = state
        self.role = role
        self.kind = REVIEWERS[role]
        files = workfile.WORKING_FILES[role]
        self.name = files.review
        self.file = os.path.join(loop.dir, self.name)
        self.relative = "%s/%s" % (loop.tracker, self.name)
        reviews = state.reviews(self.kind)
        earlier = [r for r in reviews if number is None or r < number]
        self.last = reviews[max(earlier)] if earlier else None
        self.number = (self.last.round + 1) if self.last else 1
        self.carried_numbers: list[int] = list(self.last.open) if self.last else []
        self.first_new = self.last.next if self.last else 1
        self.carried_file = os.path.join(loop.dir, files.carried)
        self._documents: list[str] | None = None

    def command(self, sub: str, write: bool = True) -> str:
        return "%s review %s --role %s --slug %s%s" % (
            places.command(), sub, self.role, self.loop.slug, " --write" if write else "")

    def minors(self) -> str:
        return self.loop.minors

    def path(self, name: str) -> str:
        return self.loop.path(name)

    def read_list(self) -> list[str]:
        return [self.path(name) for name in workfile.WORKING_FILES[self.role].read(self.number)]

    def base(self) -> str:
        return self.loop.base

    def branch(self) -> str:
        return self.loop.branch

    def fixed_point(self) -> str:
        """code-review's fixed point: the base branch in round 1, and in a
        later code round the previous round's recorded end, so the round is
        reviewed on its own diff (ticket 90). When the fold rewrote the branch
        after the previous round's Sign-off, the branch as folded."""
        if self.kind == "code" and self.number > 1:
            end = self.state.code_mark("end", self.number - 1)
            folded = self.folded_tip()
            if folded:
                return folded
            if end:
                return end
        return self.base()

    def folded_tip(self) -> str | None:
        """The branch's tip as the last fold left it, when that fold ran on
        the previous code round's recorded end, else None."""
        record = self.state.fold_record()
        end = self.state.code_mark("end", self.number - 1)
        if record is not None and record.kind == "folded" and record.signed == end:
            return record.tip
        return None

    def review_range(self) -> str:
        return "%s...%s" % (self.fixed_point(), self.branch())

    def no_commits(self) -> bool:
        """Whether a later code round's range holds no commit."""
        if self.kind != "code" or self.number == 1:
            return False
        call = gitcmd.answered(gitcmd.git(self.loop.root, "rev-list", "--count",
                                          "%s..%s" % (self.fixed_point(), self.branch())))
        return call.ok and call.out.strip() == "0"

    def agent_documents(self) -> list[str]:
        """The Agent documents in the review range, computed once."""
        if self._documents is None:
            found = agentdocs.listed(self.loop.root, self.fixed_point(), self.branch())
            if found is None:
                raise Failure(
                    "git cannot read the review range %s. Nothing was written." % self.review_range(),
                    "Tell the user git cannot diff %s in this repository, and stop." % self.review_range(),
                )
            self._documents = found
        return self._documents

    def accepted_checks(self, name: str, accepted: tuple[str, ...]) -> tuple[str, ...]:
        if self.kind == "code" and name == "writing-for-agents" and not self.agent_documents():
            return accepted + (NO_AGENT_DOCUMENT,)
        return accepted

    def filled(self, name: str) -> str | None:
        """The value the tool fills a Checks line with, or None."""
        if self.kind != "code":
            return None
        if name == "writing-for-agents" and not self.agent_documents():
            return NO_AGENT_DOCUMENT
        if name == "code-review" and self.no_commits():
            return NO_COMMITS
        return None

    def skip_allowed(self, name: str) -> bool:
        """Whether the Checks line takes "not needed, <reason>": on
        writing-for-agents in any round, and on code-review from round 2
        (ticket 90): round 1 gets one full Borrowed review."""
        if name == "writing-for-agents":
            return True
        return name == "code-review" and self.number > 1

    def placeholder(self, name: str) -> str:
        """The frame's placeholder: exactly the values the line takes in this
        round."""
        values = list(dict(CHECKS[self.kind])[name])
        if self.skip_allowed(name):
            values.append(NOT_NEEDED + "<reason>")
        return "<%s>" % " | ".join(values)


def require_round(round_: Round) -> None:
    """Refuse a round the position does not owe this reviewer."""
    place = doorbells.Place(round_.loop.root, round_.loop.slug, round_.loop, round_.state)
    if place.position().owed_by(round_.role, round_.number):
        return
    if round_.last and round_.last.signed_off:
        raise Failure(
            "The %s Loop signed off in round %d: there is no round %d to review. Nothing was written."
            % (round_.kind, round_.last.round, round_.number),
            "End your turn with BLOCKED: the %s Loop is already signed off." % round_.kind,
        )
    if round_.kind == "code" and round_.state.code_mark("end", round_.number) is None:
        raise Failure(
            "The Coder's end of code round %d is not recorded: there is no code round %d to review yet. Nothing "
            "was written." % (round_.number, round_.number),
            "End your turn with BLOCKED: code round %d has no recorded Coder end." % round_.number,
        )
    if round_.kind == "plan":
        rung = place.planner_round()
        if rung < round_.number:
            last = "round %d" % round_.last.round if round_.last else "none yet"
            raise Failure(
                "The Planner has rung no round after the last plan review (%s): there is no plan round %d to "
                "review. Nothing was written." % (last, round_.number),
                "End your turn with BLOCKED: the Planner has not rung plan round %d." % round_.number,
            )
    owner = place.position().owes
    raise Failure(
        "There is no %s round %d to review now: the %s owes the next move. Nothing was written."
        % (round_.kind, round_.number, owner),
        "End your turn with BLOCKED: the %s owes the next move, not the %s." % (owner, round_.role),
    )


def round_available(round_: Round) -> bool:
    try:
        require_round(round_)
    except Failure:
        return False
    return True


def status_line(counts: tuple[int, ...], signed_off: bool) -> str:
    if signed_off and counts[2]:
        return "SIGNED OFF. Open minors left, as Minors: leave allows: %d." % counts[2]
    if signed_off:
        return "SIGNED OFF. Nothing open."
    return "Open: %d blocker, %d major, %d minor." % counts
