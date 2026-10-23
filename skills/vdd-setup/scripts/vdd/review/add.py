"""review add: the user's findings after a code Sign-off.

The user writes findings in a file, each a heading "### <severity>:
<reference>" and a body, with no number. The command lints the file, numbers
the findings from the state file's next number, rewrites CODEREVIEW.md as the
user's open review, records a user line in the state file, writes the Recap
with a row for the entry and reopens a closed Loop file. The Coder's next
round and the Code-Reviewer's run on it through the usual commands.
"""

from __future__ import annotations

import os
import re
from typing import Callable

from .. import loopfile, loopstate, places, recap, textfile, workfile
from ..out import Failure, Output, and_list
from . import review

NAME = "CODEREVIEW.md"
NUMBERED = re.compile(r"^### [0-9]+[.)]")
HEADING = re.compile(r"^### ([^:]*):(.*)$")
FORM = "### <blocker|major|minor>: <reference>"


class Finding:
    """One finding of the user's file: its severity, reference and body."""

    def __init__(self, line: int, severity: str, reference: str) -> None:
        self.line = line
        self.severity = severity
        self.reference = reference
        self.body: list[workfile.Line] = []


# --- the user's file ---

def read_findings(source: str) -> list[Finding]:
    """The findings of the file source, or a Failure naming every line to
    fix."""
    try:
        text = textfile.decode(textfile.read_bytes(source))
    except OSError as error:
        raise Failure("--from %s cannot be read: %s. Nothing was written." % (source, textfile.reason(error)),
                      "Run the command again with --from naming a file that holds the findings.")
    lines, opener = workfile.walk(workfile.split(text))
    problems: list[tuple[int, str]] = []

    def at(number: int, message: str) -> None:
        problems.append((number, "%s line %d: %s" % (source, number, message)))

    found: list[Finding] = []
    stray = False
    for line in lines:
        if line.frame and line.text.startswith("### "):
            found.append(heading(line, at))
        elif not found:
            if line.text.strip() and not stray:
                stray = True
                at(line.number, "text before the first finding. The file holds findings only, each starting with "
                   "\"%s\". Move this text into a finding's body, or delete it." % FORM)
        elif line.frame and line.text.startswith(("# ", "## ")):
            at(line.number, "a # or ## heading in a finding's body would break CODEREVIEW.md's sections. Write it "
               "as plain text or a #### heading, or put it in a code block.")
        else:
            found[-1].body.append(line)
    for finding in found:
        if not any(line.text.strip() for line in finding.body):
            at(finding.line, "this finding has no body. Write what is wrong and a concrete fix under its heading.")
    if opener is not None:
        at(opener.number, workfile.unclosed_text(opener))
    if not found:
        problems.append((0, "%s holds no finding. Write each as \"%s\" and a body." % (source, FORM)))
    if problems:
        raise Failure([text for _, text in sorted(problems, key=lambda p: p[0])] + ["Nothing was written."],
                      "Fix the lines above in %s, then run the command again." % source)
    return found


def heading(line: workfile.Line, at: Callable[[int, str], None]) -> Finding:
    """The Finding a heading line starts; every problem the heading has goes
    to at, and the Finding is still returned so its body is read."""
    text = line.text.strip()
    if NUMBERED.match(text):
        at(line.number, "\"%s\" carries a number. The tool numbers the findings; write \"%s\"." % (text, FORM))
        return Finding(line.number, "", "")
    match = HEADING.match(text)
    if match is None:
        at(line.number, "\"%s\" is not a finding heading. Write \"%s\"." % (text, FORM))
        return Finding(line.number, "", "")
    severity, reference = match.group(1).strip(), match.group(2).strip()
    if severity not in loopstate.SEVERITIES:
        at(line.number, "\"%s\": the severity is blocker, major or minor, in lower case." % text)
    elif not reference:
        at(line.number, "\"%s\" has no reference. Write \"%s\" with a file and line, or the Spec or the doc it "
           "is about." % (text, FORM))
    return Finding(line.number, severity, reference)


def body_lines(body: list[workfile.Line]) -> list[str]:
    lines = [line.text.rstrip() for line in body]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


# --- the loop as the command meets it ---

class Entry:
    """Where the findings go: the round whose Sign-off they follow, the
    number the first new finding takes, and the user's open entry they join,
    if there is one."""

    def __init__(self, state: loopstate.State, loop: loopfile.Loop) -> None:
        last = state.last_review("code")
        if last is None:
            raise Failure(
                "The code Loop of %s has no recorded review. Nothing was written." % loop.slug,
                "Tell the user review add takes findings only after a code Sign-off, and stop.",
            )
        self.joined: loopstate.Review | None = None
        if last.user:
            if state.code_mark("start", last.round + 1) is not None:
                raise Failure(
                    "The Coder has started code round %d on the findings added after round %d. Nothing was "
                    "written." % (last.round + 1, last.round),
                    "Tell the user review add waits for the next code Sign-off, and stop.",
                )
            self.joined = last
        elif not last.signed_off:
            raise Failure(
                "Code round %d's review left findings open. Nothing was written." % last.round,
                "Tell the user review add takes findings only after a code Sign-off, and stop.",
            )
        self.round = last.round
        self.first = last.next
        self.review = last


def kept_blocks(loop: loopfile.Loop, entry: Entry) -> list[workfile.Block]:
    """The headings and bodies of the open entry a second add joins, as the
    first add left CODEREVIEW.md."""
    if entry.joined is None:
        return []
    text = textfile.read(os.path.join(loop.dir, NAME)) or ""
    found = dict((b.number, b) for b in workfile.Parsed(text).blocks if b.match and b.number is not None)
    wanted = entry.joined.raised()
    missing = [n for n in wanted if n not in found]
    if missing:
        raise Failure(
            "%s/%s no longer holds the heading of finding%s %s of the user's entry after round %d. Nothing was "
            "written." % (loop.tracker, NAME, "" if len(missing) == 1 else "s", workfile.join_numbers(missing),
                          entry.round),
            "Tell the user CODEREVIEW.md lost a finding the loop still has open, and stop.",
        )
    return [found[n] for n in wanted]


def not_carried(loop: loopfile.Loop, entry: Entry) -> str | None:
    """The line naming the minors a Minors: leave Sign-off left open, whose
    text the rewrite drops, or None."""
    review = entry.review
    if entry.joined is not None or not review.open:
        return None
    text = textfile.read(os.path.join(loop.dir, NAME)) or ""
    references = dict((b.number, b.reference) for b in workfile.Parsed(text).blocks if b.match)
    named = ["%d (%s)" % (n, references[n]) if n in references else str(n) for n in review.open]
    return "Not carried: the minors left open at round %d's Sign-off, %s." % (review.round, and_list(named))


# --- the command ---

def run(loop: loopfile.Loop, source: str, write: bool) -> int:
    state = loop.load_state()
    state.refuse_v1(loop.slug, "review add")
    refuse_moved_fold(state, loop, source)
    entry = Entry(state, loop)
    every = read_findings(source)
    kept = kept_blocks(loop, entry)
    # A finding the open entry already holds was added by an earlier run
    # whose commit point passed: a rerun adds it no second time.
    findings = [f for f in every if not any(same(block, f) for block in kept)]
    if not findings:
        return already_added(loop, state, entry, source, write)
    carried = not_carried(loop, entry)
    number = entry.first
    blocks: list[list[str]] = [block.text_lines() for block in kept]
    severities = [block.severity for block in kept]
    headings = [block.heading.text for block in kept]
    for finding in findings:
        head = "### %d. %s (open): %s" % (number, finding.severity, finding.reference)
        headings.append(head)
        blocks.append([head, ""] + body_lines(finding.body))
        severities.append(finding.severity)
        number += 1
    counts = tuple(severities.count(name) for name in loopstate.SEVERITIES)
    numbers = (entry.joined.raised() if entry.joined else []) + list(range(entry.first, number))
    status = review.status_line(counts, False)
    lines = ["# %s, round %d" % (review.TITLES["code"], entry.round), "", status, "",
             "Findings raised by the user after the round-%d Sign-off." % entry.round, "", "## New findings"]
    for block in blocks:
        lines += [""] + block
    review_path = "%s/%s" % (loop.tracker, NAME)
    reopening = state.status == loopstate.CLOSED
    user = loopstate.user_line(entry.round, numbers, counts, number, len(numbers))
    out = Output()
    if not write:
        out.line("Would add %d finding%s after round %d's Sign-off%s:" % (
            len(findings), "" if len(findings) == 1 else "s", entry.round,
            ", joining the open entry of findings %s" % workfile.join_numbers(entry.joined.raised())
            if entry.joined else ""))
        for head in headings:
            out.line(head)
        out.line(status)
        out.line("Would rewrite %s, record the findings in %s/%s and write %s/%s." % (
            review_path, loop.tracker, loopstate.STATE_NAME, loop.tracker, recap.NAME))
        if reopening:
            out.line("Would reopen the closed loop %s." % loop.slug)
        if carried:
            out.line(carried)
        return out.finish("Run %s" % command(loop, source))
    # CODEREVIEW.md first: the committed user line names headings that must
    # already be in it. A rerun before the commit point numbers the same
    # findings the same way and writes the same file.
    textfile.write_or_refuse(os.path.join(loop.dir, NAME), "\n".join(lines) + "\n", review_path,
                             "Otherwise tell the user CODEREVIEW.md cannot be written, and stop.")
    recap.record(loop, state, [], [user] + ([loopstate.loop_line(loopstate.OPEN)] if reopening else []))
    out.line("Wrote %s." % review_path)
    out.line("Wrote %s/%s." % (loop.tracker, recap.NAME))
    out.line("Recorded in %s/%s: %s" % (loop.tracker, loopstate.STATE_NAME, user))
    if reopening:
        out.line("Reopened the loop %s." % loop.slug)
    out.line("Findings %s open: %d blocker, %d major, %d minor." % ((workfile.join_numbers(numbers),) + counts))
    if carried:
        out.line(carried)
    return out.finish(
        "Tell the Orchestrator the loop has your findings; it carries on with orchestrator start."
    )


def same(block: workfile.Block, finding: Finding) -> bool:
    """Whether block is finding as an earlier add wrote it: the same
    severity, reference and text."""
    body = block.text_lines()[1:]
    while body and not body[0].strip():
        body.pop(0)
    return (block.severity == finding.severity and block.reference.strip() == finding.reference
            and [line.rstrip() for line in body] == body_lines(finding.body))


def already_added(loop: loopfile.Loop, state: loopstate.State, entry: Entry, source: str, write: bool) -> int:
    """Every finding of source is in the open entry: a rerun after the commit
    point, which writes RECAP.md again where a failure left it behind."""
    joined = entry.joined
    if joined is None:
        raise RuntimeError("already_added without an open entry.")
    store = recap.Records.load(loop)
    out = Output()
    numbers = workfile.join_numbers(joined.raised())
    wrote = write and recap.render_recap(loop, state, store)
    out.line("The findings of %s are already added after round %d's Sign-off, as findings %s. %s" % (
        source, entry.round, numbers,
        "Wrote %s/%s again." % (loop.tracker, recap.NAME) if wrote else "Nothing was written."))
    out.line("Findings %s open: %d blocker, %d major, %d minor." % ((numbers,) + tuple(joined.counts)))
    return out.finish(
        "Tell the Orchestrator the loop has your findings; it carries on with orchestrator start."
    )


def command(loop: loopfile.Loop, source: str) -> str:
    quoted = '"%s"' % source if " " in source else source
    return "%s review add --slug %s --from %s --write" % (places.command(), loop.slug, quoted)
