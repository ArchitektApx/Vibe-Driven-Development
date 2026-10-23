"""The lint of a review file against its frame: its sections, the Checks
lines, the findings and the Not carried lines."""

from __future__ import annotations

from .. import loopstate, textfile, workfile
from .rounds import CHECKS, LABELS, NOT_NEEDED, TITLES, Round

STATES = ("open", "fixed", "accepted")


def sections_expected(round_: Round) -> list[str]:
    names = ["Checks"]
    if round_.number > 1:
        names.append("Open findings")
    names.append("New findings")
    if round_.kind == "code":
        names.append("Not carried")
    return names


def lint(round_: Round, parsed: workfile.Parsed) -> workfile.Lint:
    lint_ = workfile.Lint(round_.name)
    lint_.title(parsed, "# %s, round %d" % (TITLES[round_.kind], round_.number))
    expected = sections_expected(round_)
    for section in parsed.sections:
        if section.name not in expected:
            lint_.at(section.line, "\"%s\" is not a heading of this file. Its headings are %s; put what is "
                     "under it under one of those, or remove it." % (
                         section.line.text, ", ".join("## " + name for name in expected)))
    for name in expected:
        if parsed.section(name) is None:
            lint_.at(None, "the heading \"## %s\" is missing. Put it back as the tool wrote it." % name)
    lint_checks(round_, parsed, lint_)
    lint_findings(round_, parsed, lint_)
    if round_.kind == "code":
        lint_kept_open(round_, parsed, lint_)
        lint_not_carried(parsed, lint_)
    return lint_


def lint_kept_open(round_: Round, parsed: workfile.Parsed, lint_: workfile.Lint) -> None:
    """A carried finding the Coder answered this round and the reviewer keeps
    open needs the reviewer's reason."""
    marker = "in round %d." % round_.number
    for block in parsed.blocks_in("Open findings"):
        if block.match is None or block.state != "open":
            continue
        labels = block.labels(LABELS)
        answered = [text for label, text, _ in labels
                    if label == "Coder" and text.startswith(("fixed " + marker, "pushed back " + marker))]
        if not answered:
            continue
        kept = [text for label, text, _ in labels if label == "Reviewer" and text.startswith("kept open " + marker)]
        if not kept:
            lint_.at(block.heading, "finding %d keeps the Coder's round-%d answer and stays open, but has no "
                     "\"Reviewer: kept open in round %d.\" line. Write one with why the answer does not hold."
                     % (block.number, round_.number, round_.number))


def parse_not_carried(
    parsed: workfile.Parsed,
) -> tuple[list[tuple[str, list[int]]], list[tuple[workfile.Line, str]]]:
    """The Not carried lines, a wrapped line joined: ([(text, [line numbers])],
    [(line, problem)]). A line that is neither a "- " line nor an indented
    continuation, and a "- " line with nothing after it, are problems."""
    section = parsed.section("Not carried")
    items: list[tuple[str, list[int]]] = []
    problems: list[tuple[workfile.Line, str]] = []
    if section is None:
        return items, problems
    firsts = []
    for line in section.body:
        if not line.frame or not line.text.strip():
            continue
        if line.text.startswith("- "):
            items.append((line.text[2:].strip(), [line.number]))
            firsts.append(line)
        elif line.text[:1] in (" ", "\t") and items:
            items[-1] = ((items[-1][0] + " " + line.text.strip()).strip(), items[-1][1])
            items[-1][1].append(line.number)
        else:
            problems.append((line, "under ## Not carried every line starts with \"- \": \"- <the problem, in one "
                             "line>: <why not>\". A wrapped line goes on an indented next line."))
    for (text, _), line in zip(items, firsts):
        if not text:
            problems.append((line, "this Not carried line is empty. Write \"- <the problem, in one line>: <why "
                             "not>\", or remove it."))
    return items, problems


def not_carried(parsed: workfile.Parsed) -> list[tuple[str, list[int]]]:
    """The Not carried lines, parsed."""
    return parse_not_carried(parsed)[0]


def lint_not_carried(parsed: workfile.Parsed, lint_: workfile.Lint) -> None:
    for line, text in parse_not_carried(parsed)[1]:
        lint_.at(line, text)


def lint_checks(round_: Round, parsed: workfile.Parsed, lint_: workfile.Lint) -> None:
    section = parsed.section("Checks")
    if section is None:
        return
    seen: dict[str, tuple[workfile.Line, str]] = {}
    for line in section.body:
        if not line.frame or ":" not in line.text:
            continue
        name, _, value = line.text.partition(":")
        seen[name.strip()] = (line, value.strip())
    for name, accepted in CHECKS[round_.kind]:
        accepted = round_.accepted_checks(name, accepted)
        if name not in seen:
            lint_.at(section.line, "the Checks line \"%s: %s\" is missing. Put it back and fill it in."
                     % (name, round_.placeholder(name)))
            continue
        line, value = seen[name]
        if value in accepted:
            continue
        if value.startswith("not needed"):
            problem = skip_problem(round_, name, value)
            if problem:
                lint_.at(line, problem)
            continue
        written = ["%s: %s" % (name, a) for a in accepted]
        if round_.skip_allowed(name):
            written.append("%s: %s<reason>" % (name, NOT_NEEDED))
        lint_.at(line, "\"%s\" is not filled in. Write one of: %s." % (line.text.strip(), ", ".join(written)))


def skip_problem(round_: Round, name: str, value: str) -> str | None:
    """The refusal for a "not needed" Checks value, or None when it is
    accepted: "not needed, " and a reason with no "|", which would break the
    Recap's table row."""
    if not round_.skip_allowed(name):
        return ("\"%s: %s\": round 1's code-review is never skipped; every code Loop gets one full Borrowed "
                "review. Run it and write \"%s: ran\", or \"%s: did not resolve, the Spec reviewed by hand\"."
                % (name, value, name, name))
    reason = value[len(NOT_NEEDED):].strip() if value.startswith(NOT_NEEDED) else ""
    if not reason:
        return ("\"%s: %s\" gives no reason. Write \"%s: %s<reason>\" with why the check was not needed."
                % (name, value, name, NOT_NEEDED))
    if "|" in reason:
        return ("\"%s: %s\": the reason holds a |, which breaks the Recap's table. Write the reason without it."
                % (name, value))
    return None


def lint_findings(round_: Round, parsed: workfile.Parsed, lint_: workfile.Lint) -> None:
    carried = set(round_.carried_numbers)
    seen = set()
    new_numbers = []
    for block in parsed.blocks:
        section = block.section.name if block.section else None
        if section not in ("Open findings", "New findings"):
            lint_.at(block.heading, "a finding heading belongs under ## New findings." if round_.number == 1 else
                     "a finding heading belongs under ## Open findings or ## New findings.")
            continue
        if block.match is None:
            lint_.at(block.heading, "\"%s\": a finding heading is \"### <n>. <blocker|major|minor> "
                     "(<open|fixed|accepted>): <reference>\"." % block.heading.text)
            continue
        if block.severity not in loopstate.SEVERITIES:
            lint_.at(block.heading, "\"%s\": the severity is blocker, major or minor, in lower case."
                     % block.heading.text)
        if block.state not in STATES:
            lint_.at(block.heading, "\"%s\": the state is open, fixed or accepted." % block.heading.text)
        if block.number in seen:
            lint_.at(block.heading, "finding %d appears twice. Each finding has one heading." % block.number)
            continue
        seen.add(block.number)
        if section == "Open findings" and block.number not in carried:
            lint_.at(block.heading, "a finding under ## Open findings must have been carried by the tool. Move "
                     "new findings under ## New findings.")
        if section == "New findings":
            if block.number in carried:
                lint_.at(block.heading, "finding %d was carried; it stays under ## Open findings." % block.number)
            else:
                new_numbers.append((block.number, block))
        if block.state in ("fixed", "accepted"):
            if not [label for label in block.labels(LABELS) if label[0] == "Resolution" and label[1]]:
                lint_.at(block.heading, "finding %d is %s but has no Resolution: line. Write one under it: what "
                         "changed and where, or the pushback you accepted." % (block.number, block.state))
    expected = round_.first_new
    for number, block in new_numbers:
        if number != expected:
            lint_.at(block.heading, "finding %d is numbered %d; new findings this round start at %d and run "
                     "without gaps." % (expected, number, round_.first_new))
            break
        expected += 1
    present = set(n for n, _ in new_numbers) | set(
        b.number for b in parsed.blocks_in("Open findings") if b.match is not None)
    missing = [n for n in round_.carried_numbers if n not in present]
    if missing:
        blocks = dict((b.number, b.text_lines()) for b in workfile.Parsed(textfile.read(round_.carried_file) or "").blocks)
        for number in missing:
            lint_.block("finding %d was open at the start of round %d and is missing. Put this block back under "
                        "## Open findings and set its state:" % (number, round_.number), [""] + blocks.get(number, []))
