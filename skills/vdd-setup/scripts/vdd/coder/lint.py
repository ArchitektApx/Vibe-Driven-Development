"""The lint of FIXES.md against its frame: the Ticket entries of round 1
and the finding answers of a later round."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from .. import fixes, workfile

if TYPE_CHECKING:
    from .rounds import Round

ANSWERS = ("fixed", "pushback")


def lint(round_: Round, parsed: workfile.Parsed) -> workfile.Lint:
    lint_ = workfile.Lint(fixes.NAME)
    lint_.title(parsed, "# Fixes, round %d" % round_.number)
    found = fixes.entries(parsed)
    if round_.number == 1:
        lint_tickets(round_, found, lint_.at)
    else:
        lint_findings(round_, found, lint_.at)
    return lint_


def lint_tickets(round_: Round, found: list[fixes.Entry], at: Callable[[workfile.Line | None, str], None]) -> None:
    by_number = {}
    for entry in found:
        match = fixes.TICKET_HEADING.match(entry.heading.text)
        if not match:
            at(entry.heading, "\"%s\" is not an entry of this file. An entry is \"## Ticket <NN>: <file name>\", "
               "as the tool wrote it." % entry.heading.text)
            continue
        by_number[match.group(1)] = entry
    for number, name in round_.tickets():
        entry = by_number.get(number)
        if entry is None:
            at(None, "Ticket %s's entry \"## Ticket %s: %s\" is missing. Put it back and fill it in: every "
               "Ticket gets an entry." % (number, number, name))
            continue
        labels = entry.labels(fixes.TICKET_LABELS)
        for label in ("Files", "Change", "Verified"):
            text, line = labels.get(label, ("", None))
            if line is None:
                at(entry.heading, "Ticket %s has no %s: line. Put it back under its heading and fill it in."
                   % (number, label))
            elif not text:
                fix = {"Files": "the files you touched", "Change": "what you changed",
                       "Verified": "the result of each check you ran, not its output"}[label]
                at(line, "Ticket %s's %s: is empty. Write %s." % (number, label, fix))


def lint_findings(round_: Round, found: list[fixes.Entry], at: Callable[[workfile.Line | None, str], None]) -> None:
    by_number = {}
    for entry in found:
        match = fixes.FINDING_HEADING.match(entry.heading.text)
        if not match:
            at(entry.heading, "\"%s\" is not an entry of this file. An entry is \"## Finding <n>. <severity>: "
               "<reference>\", as the tool wrote it." % entry.heading.text)
            continue
        by_number[int(match.group(1))] = entry
    headings = None
    for number in round_.open_numbers:
        entry = by_number.get(number)
        if entry is None:
            if headings is None:
                headings = dict((n, "## Finding %d. %s: %s" % (n, severity, reference))
                                for n, severity, reference in round_.open_findings())
            at(None, "finding %d's entry is missing. Put back \"%s\" as the tool wrote it and answer it: every "
               "open finding gets an entry." % (number, headings[number]))
            continue
        labels = entry.labels(fixes.FINDING_LABELS)
        answer, line = labels.get("Answer", ("", None))
        if line is None:
            at(entry.heading, "finding %d has no Answer: line. Write \"Answer: fixed\" or \"Answer: pushback\" "
               "under it." % number)
            continue
        if answer not in ANSWERS:
            at(line, "finding %d: \"Answer: %s\": the answer is fixed or pushback." % (number, answer))
            continue
        why = labels.get("Why", ("", None))[0]
        if answer == "pushback" and not why:
            at(line, "finding %d answers pushback with no Why:. A pushback needs its reason for the reviewer."
               % number)
