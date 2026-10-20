"""The Recap, .scratch/<slug>/RECAP.md: the account of one loop that only
the tool writes and no Role reads during the loop.

Its header and rounds table are rendered from the state file every time it
is written. Its sections, Tickets, Plan findings, Code findings, Commits and
Not carried, keep what earlier writes put there, and each write appends to them.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from . import textfile, workfile

if TYPE_CHECKING:
    from .loopfile import Loop
    from .loopstate import Review, State

NAME = "RECAP.md"
SECTIONS = ("Tickets", "Plan findings", "Code findings", "Commits", "Not carried")


def path(loop: Loop) -> str:
    return os.path.join(loop.dir, NAME)


def read_sections(loop: Loop) -> dict[str, list[str]]:
    """Section name -> its lines, from the RECAP.md on disk."""
    sections: dict[str, list[str]] = dict((name, []) for name in SECTIONS)
    text = textfile.read(path(loop))
    if text is None:
        return sections
    current = None
    # A heading quoted in a fence or comment is prose.
    for line in workfile.classify(text.split("\n")):
        if line.frame and line.text.startswith("## ") and line.text[3:].strip() in SECTIONS:
            current = line.text[3:].strip()
            continue
        if current is not None:
            sections[current].append(line.text)
    for name in SECTIONS:
        lines = sections[name]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
    return sections


def open_after(review: Review) -> str:
    if review.signed_off:
        if review.counts[2]:
            return "SIGNED OFF, %d minor left" % review.counts[2]
        return "SIGNED OFF"
    return "%d blocker, %d major, %d minor" % tuple(review.counts)


def loop_line(name: str, reviews: dict[int, Review]) -> str:
    if not reviews:
        return "%s Loop: not started." % name
    last = reviews[max(reviews)]
    count = len(reviews)
    rounds = "%d round%s" % (count, "" if count == 1 else "s")
    if last.signed_off:
        return "%s Loop: %s, signed off in round %d." % (name, rounds, last.round)
    return "%s Loop: %s, open after round %d." % (name, rounds, last.round)


def code_line(state: State) -> str:
    """The code Loop's line, naming a Coder round no review has recorded
    yet."""
    reviews = state.reviews("code")
    line = loop_line("Code", reviews)
    newest = state.code_round()
    if not newest or newest in reviews:
        return line[:-1] + fold_text(state) + "."
    if not reviews:
        return "Code Loop: round %d, not reviewed yet." % newest
    return "%s; round %d not reviewed yet." % (line[:-1], newest)


def fold_text(state: State) -> str:
    """The fold's outcome for the Code Loop line: folded or not folded."""
    outcome = state.fold_outcome()
    if outcome is None:
        return ""
    if outcome[0] == "folded":
        return "; folded"
    return "; not folded: " + outcome[2]


def render(loop: Loop, state: State, sections: dict[str, list[str]]) -> str:
    base, _ = loop.setting("Base branch")
    branch, _ = loop.setting("Feature branch")
    plan = state.reviews("plan")
    code = state.reviews("code")
    lines = [
        "# Recap: %s" % loop.slug,
        "",
        "Written by the VDD tool only. No Role reads it during the loop.",
        "",
        "Branch: %s from %s." % (branch, base),
        loop_line("Plan", plan),
        code_line(state),
        "",
        "| Loop | Round | New findings | Closed | Open after | Checks |",
        "|---|---|---|---|---|---|",
    ]
    for kind, reviews in (("plan", plan), ("code", code)):
        for number in sorted(reviews):
            review = reviews[number]
            lines.append("| %s | %d | %d | %d | %s | %s |" % (
                kind, number, review.new, review.closed, open_after(review), review.checks or "none"))
    for name in SECTIONS:
        lines += ["", "## " + name]
        if sections[name]:
            lines += [""] + sections[name]
    return "\n".join(lines) + "\n"


def write(loop: Loop, state: State, additions: dict[str, list[str]]) -> None:
    """Append each section's new lines in additions (name -> lines) and write
    RECAP.md whole, the header and table from state."""
    sections = read_sections(loop)
    for name, lines in additions.items():
        if not lines:
            continue
        if sections[name]:
            sections[name].append("")
        sections[name].extend(lines)
    textfile.write_or_refuse(path(loop), render(loop, state, sections), path(loop),
                             "Otherwise tell the user the Recap cannot be written, and stop.")
