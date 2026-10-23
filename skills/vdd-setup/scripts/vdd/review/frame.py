"""review start: the round's frame of the review file, the findings still
open carried whole with the Coder's answers, and the guidance comment."""

from __future__ import annotations

import os
import textwrap

from .. import fixes, loopstate, runner, textfile, workfile
from ..out import Failure
from .rounds import CHECKS, NO_COMMITS, TITLES, Round, require_round

NOT_CARRIED_GUIDE = [
    "<!-- VDD: One line for each problem the code-review reports raise that you",
    "do not turn into a finding, a wrong one included. A report line that finds",
    "nothing wrong gets no line.",
    "- <the problem, in one line>: <why not> -->",
]


def carried_blocks(round_: Round) -> list[list[str]]:
    """number -> the block's lines, for every finding still open, from the
    review file as the last check left it, else from the carried file."""
    found, missing = workfile.open_blocks(round_.loop.dir, workfile.WORKING_FILES[round_.role],
                                          round_.carried_numbers)
    blocks = dict((number, block.text_lines()) for number, block in found.items())
    if missing:
        raise Failure(
            "%s no longer holds finding%s %s, which round %d left open. Nothing was written."
            % (round_.relative, "" if len(missing) == 1 else "s", workfile.join_numbers(missing),
               round_.number - 1),
            "Tell the user %s lost a finding the loop still has open, and stop." % round_.relative,
        )
    if round_.kind == "code":
        answers = coder_answers(round_)
        for number in round_.carried_numbers:
            if number in answers:
                blocks[number] = blocks[number] + ["", answers[number]]
    return [blocks[n] for n in round_.carried_numbers]


def coder_answers(round_: Round) -> dict[int, str]:
    """number -> this round's Coder: line, from FIXES.md's answers."""
    text = textfile.read(os.path.join(round_.loop.dir, fixes.NAME))
    if text is None:
        return {}
    found: dict[int, str] = {}
    for entry in fixes.entries(workfile.Parsed(text)):
        match = fixes.FINDING_HEADING.match(entry.heading.text)
        if not match:
            continue
        labels = entry.labels(fixes.FINDING_LABELS)
        answer = labels.get("Answer", ("", None))[0]
        why = labels.get("Why", ("", None))[0]
        if answer == "fixed":
            line = "Coder: fixed in round %d." % round_.number + (" " + why if why else "")
        elif answer == "pushback":
            line = "Coder: pushed back in round %d. %s" % (round_.number, why)
        else:
            continue
        found[int(match.group(1))] = line.rstrip()
    return found


def guidance(round_: Round) -> list[str]:
    reference = "<Spec section or Ticket NN>" if round_.kind == "plan" else "<file>:<line>"
    head = textwrap.wrap("<!-- VDD: the VDD tool wrote this frame, and `review check` reads it. Fill each "
                         "Checks line. Add each finding under New findings as a heading", 76)
    head.append("`### <n>. <blocker|major|minor> (open): %s`," % reference)
    words = ["then what is wrong and a concrete fix."]
    if round_.kind == "code":
        words.append("The code-review reports are not pasted here: turn each item you carry into a finding.")
    if round_.number > 1:
        words.append("For each carried finding, set the state in its heading: `fixed`, `accepted` or `open`. "
                     "Under a fixed or accepted finding write one `Resolution:` line: what changed and where, "
                     "or the pushback you accepted.")
        if round_.kind == "code":
            words.append("Under a finding you keep open after a Coder's answer, write one "
                         "`Reviewer: kept open in round %d.` line with why." % round_.number)
    words.append("Keep every line that starts with ###. The tool removes this comment when the file passes. -->")
    return head + textwrap.wrap(" ".join(words), 76, break_long_words=False, break_on_hyphens=False)


def skeleton(round_: Round, blocks: list[list[str]]) -> list[str]:
    lines = ["# %s, round %d" % (TITLES[round_.kind], round_.number), ""]
    lines += guidance(round_)
    lines += ["", "## Checks", ""]
    for name, _ in CHECKS[round_.kind]:
        lines.append("%s: %s" % (name, round_.filled(name) or round_.placeholder(name)))
    if round_.number > 1:
        lines += ["", "## Open findings"]
        for block in blocks:
            lines += [""] + block
    lines += ["", "## New findings"]
    if round_.kind == "code":
        lines += ["", "## Not carried", ""] + NOT_CARRIED_GUIDE
    return lines


def start(round_: Round) -> runner.Plan:
    """The round's start as a plan: the carried findings and the frame
    written and the round recorded as started. A round already started
    writes nothing."""
    require_round(round_)
    if round_.state.review_started(round_.kind, round_.number):
        again = ("Round %d was already started: %s stays as it is. Nothing was written."
                 % (round_.number, round_.relative))
        return runner.Plan([], work(round_), lines=[again] + started(round_))
    blocks = carried_blocks(round_)
    carried_text = "\n\n".join("\n".join(block) for block in blocks)
    cannot = "Otherwise tell the user the review file cannot be written, and stop."
    frame = "\n".join(skeleton(round_, blocks)) + "\n"
    effects: list[runner.Effect] = [
        runner.WriteFile(round_.carried_file, carried_text + "\n" if carried_text else "", round_.relative, cannot,
                         dry=["Would write the frame of %s for round %d." % (round_.relative, round_.number)]),
        runner.WriteFile(round_.file, frame, round_.relative, cannot),
        runner.StateLines(round_.state, [loopstate.review_started_line(round_.kind, round_.number)],
                          done=["Wrote the frame of %s." % round_.relative] + started(round_)),
    ]
    return runner.Plan(effects, work(round_))


def work(round_: Round) -> str:
    """The Next: step once the round started."""
    return ("Review, write your findings into %s under the headings it has, then run %s. Pass --slug %s on every "
            "VDD tool call from here on." % (round_.relative, round_.command("check"), round_.loop.slug))


def started(round_: Round) -> list[str]:
    """The lines that name the round, what it carries and what to read."""
    lines: list[str] = []
    if round_.carried_numbers:
        carried = "finding%s %s carried open" % (
            "" if len(round_.carried_numbers) == 1 else "s", workfile.join_numbers(round_.carried_numbers))
    else:
        carried = "no finding carried"
    lines.append("Round %d: %s, new findings start at %d." % (round_.number, carried, round_.first_new))
    lines.append("Read: %s" % ", ".join(round_.read_list()))
    lines.append("Minors: %s" % round_.minors())
    if round_.kind == "code":
        lines.append("Base branch: %s" % round_.base())
        lines.append("Harness file: %s" % round_.loop.harness_file())
        if round_.number == 1:
            lines.append("Review range: %s, with %s as code-review's fixed point and the diff you check against the "
                         "Tickets." % (round_.review_range(), round_.base()))
        else:
            if round_.folded_tip():
                lines.append("Fixed point: %s, the branch as folded after round %d's Sign-off." % (
                    round_.fixed_point(), round_.number - 1))
            else:
                lines.append("Fixed point: %s, code round %d's recorded end." % (round_.fixed_point(),
                                                                                  round_.number - 1))
            lines.append("Review range: %s, this round's own diff: code-review's fixed point is %s, and the diff you "
                         "check against the Tickets is this range. The verification runs on the whole branch." % (
                             round_.review_range(), round_.fixed_point()))
            if round_.no_commits():
                lines.append("No commits in this round's range, so the code-review line is filled: %s."
                             % NO_COMMITS)
        documents = round_.agent_documents()
        if documents:
            lines.append("Agent documents in the range: %s" % ", ".join(documents))
        else:
            lines.append("Agent documents in the range: none, so the writing-for-agents line is filled.")
    return lines
