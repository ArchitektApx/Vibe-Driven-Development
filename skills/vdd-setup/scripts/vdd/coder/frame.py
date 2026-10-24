"""coder start: the round's frame of FIXES.md, one entry per Ticket in round
1 and one per open finding later, the branch switch, and the record of where
the round starts."""

from __future__ import annotations

import os
import textwrap

from .. import loopstate, runner
from ..out import Failure, and_list
from .branch import apply_branch, decide_branch, head, on_branch, tip_after, untracked, would_branch
from .rounds import Round, open_findings, precondition, tickets


def ticket_guidance() -> list[str]:
    return textwrap.wrap(
        "<!-- VDD: the VDD tool wrote this frame, and `coder check` reads it. Under each Ticket fill Files, "
        "Change and Verified. Verified is the result of each check you ran, never its output. Add Deviations: "
        "and Why: when you departed from the Ticket. Keep every line that starts with ##. The tool removes this "
        "comment when the file passes. -->", 76, break_long_words=False, break_on_hyphens=False)


def finding_guidance() -> list[str]:
    return textwrap.wrap(
        "<!-- VDD: the VDD tool wrote this frame, and `coder check` reads it. Under each finding set Answer to "
        "`fixed` or `pushback`. Why is required for pushback, and optional for fixed: write it when your fix "
        "differs from the one the finding asks for. Keep every line that starts with ##. The tool removes this "
        "comment when the file passes. -->", 76, break_long_words=False, break_on_hyphens=False)


def skeleton(round_: Round) -> list[str]:
    lines = ["# Fixes, round %d" % round_.number, ""]
    if round_.number == 1:
        lines += ticket_guidance()
        for number, name in tickets(round_.loop):
            lines += ["", "## Ticket %s: %s" % (number, name), "", "Files:", "Change:", "Verified:"]
    else:
        lines += finding_guidance()
        for number, severity, reference in open_findings(round_):
            lines += ["", "## Finding %d. %s: %s" % (number, severity, reference), "",
                      "Answer: <fixed | pushback>", "Why:"]
    return lines


def start(round_: Round) -> runner.Plan:
    """The round's start as a plan. A round already started writes nothing,
    and only switches to the feature branch when the Coder left it."""
    precondition(round_)
    if round_.number == 1 and not tickets(round_.loop):
        raise Failure(
            "%s holds no Ticket file (NN-<slug>.md), so round 1 has nothing to build. Nothing was written."
            % round_.path("issues/"),
            "End your turn with BLOCKED: the loop has no Tickets.",
        )
    if round_.started:
        return started_again(round_)
    lines = skeleton(round_)
    head(round_.loop.root)  # an unborn HEAD refuses before the switch
    found = untracked(round_.loop.root)
    decision = decide_branch(round_)
    sha = tip_after(round_, decision)
    snapshot = round_.snapshot_name()
    effects: list[runner.Effect] = [
        runner.Step(lambda: apply_branch(round_, decision), dry=[
            "Would start code round %d on %s and write the frame of %s." % (round_.number, round_.branch,
                                                                            round_.relative)]),
        runner.WriteFile(round_.file, "\n".join(lines) + "\n", round_.relative,
                         "Otherwise tell the user FIXES.md cannot be written, and stop.",
                         done=["Wrote the frame of %s." % round_.relative]),
        runner.WriteFile(os.path.join(round_.loop.dir, snapshot), "".join(name + "\n" for name in found),
                         round_.path(snapshot), "Otherwise tell the user the round's snapshot cannot be written, and "
                         "stop."),
        runner.StateLines(round_.state, [loopstate.code_mark_line("start", round_.number, sha)],
                          done=started(round_, sha)),
    ]
    return runner.Plan(effects, work(round_))


def started_again(round_: Round) -> runner.Plan:
    """A second start in a round: nothing written, the Coder put back on the
    feature branch when it left it."""
    again = "Round %d was already started: %s stays as it is. Nothing was written." % (round_.number,
                                                                                     round_.relative)
    sha = round_.state.code_mark("start", round_.number)
    decision = decide_branch(round_)
    if decision is None:
        return runner.Plan([], work(round_), lines=[on_branch(round_), again] + started(round_, sha))
    step = runner.Step(lambda: apply_branch(round_, decision) + [again] + started(round_, sha),
                       dry=[would_branch(round_, decision), again])
    return runner.Plan([step], work(round_))


def started(round_: Round, sha: str | None) -> list[str]:
    """The lines that say where the round starts and what it holds."""
    lines = ["Round %d starts at %s." % (round_.number, sha)]
    if round_.number == 1:
        lines.append("Entries: one per Ticket, %s." % and_list(map(str, [n for n, _ in tickets(round_.loop)])))
    else:
        lines.append("Entries: one per open finding, %s." % and_list(map(str, round_.open_numbers)))
    lines.append("Read: %s" % ", ".join(round_.read_list()))
    return lines


def work(round_: Round) -> str:
    """The Next: step once the round started."""
    what = "Build the Tickets in order" if round_.number == 1 else "Answer every open finding"
    return ("%s, committing on %s as your skill says, and fill each entry of %s. Then run %s. Pass --slug %s on "
            "every VDD tool call from here on." % (what, round_.branch, round_.relative, round_.command("check"),
                                                   round_.loop.slug))
