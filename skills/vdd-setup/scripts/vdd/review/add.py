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

from .. import catalog, gitcmd, loopfile, loopstate, runner, textfile, workfile
from ..loopstate import recap, records
from ..out import Failure, and_list
from . import rounds

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
    lint = workfile.Lint(source)
    at = lint.at

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
        lint.problems.append((0, ["%s holds no finding. Write each as \"%s\" and a body." % (source, FORM)]))
    if lint.problems:
        raise Failure(lint.lines() + ["Nothing was written."],
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


def refuse_moved_fold(state: loopstate.State, loop: loopfile.Loop, source: str) -> None:
    """The refusal while a fold moved the branch and stopped before its
    state line: a user line recorded now would drop that fold's Commits from
    the Recap once a later round runs. Any other unfolded Sign-off is
    accepted."""
    if not loopstate.code_position(state).fold_owed:
        return
    review = state.last_review("code")
    if review is None:
        return
    signed = state.code_mark("end", review.round)
    if not signed:
        return
    try:
        moved = records.moved_fold(records.Records.load(loop), loop.root, loop.branch, signed)
    except gitcmd.Refused as error:
        raise gitcmd.sandbox_refusal(error.call, command(loop, source), "tell the user %s was refused, and stop."
                                     % gitcmd.call_text(error.call), ["Nothing was written."])
    if moved is None:
        return
    fold = loopstate.fold_command(loop, loop.harness)
    steps = [fold, "this command again"]
    if state.status == loopstate.CLOSED:
        steps.insert(0, catalog.line("loop", "reopen", slug=loop.slug, write=True))
    raise Failure(
        "Code round %d was folded but its fold is not recorded. Nothing was written." % review.round,
        "Run %s." % ", then ".join(steps),
    )


def kept_blocks(loop: loopfile.Loop, entry: Entry) -> list[workfile.Block]:
    """The headings and bodies of the open entry a second add joins, as the
    first add left CODEREVIEW.md."""
    if entry.joined is None:
        return []
    wanted = entry.joined.raised()
    found, missing = workfile.open_blocks(loop.dir, workfile.WORKING_FILES["Code-Reviewer"], wanted)
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

def plan(loop: loopfile.Loop, source: str) -> runner.Plan:
    """The user's findings added as a plan: CODEREVIEW.md rewritten as the
    user's open review before the commit point, since the user line it
    records names its headings; a rerun before the commit point numbers the
    same findings the same way and writes the same file."""
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
        return already_added(loop, state, entry, source)
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
    status = rounds.status_line(counts, False)
    lines = ["# %s, round %d" % (rounds.TITLES["code"], entry.round), "", status, "",
             "Findings raised by the user after the round-%d Sign-off." % entry.round, "", "## New findings"]
    for block in blocks:
        lines += [""] + block
    review_path = "%s/%s" % (loop.tracker, NAME)
    reopening = state.status == loopstate.CLOSED
    user = loopstate.user_line(entry.round, numbers, counts, number, len(numbers))
    store = records.Records.load(loop)
    dry = ["Would add %d finding%s after round %d's Sign-off%s:" % (
        len(findings), "" if len(findings) == 1 else "s", entry.round,
        ", joining the open entry of findings %s" % workfile.join_numbers(entry.joined.raised())
        if entry.joined else "")]
    dry += headings
    dry.append(status)
    dry.append("Would rewrite %s, record the findings in %s/%s and write %s/%s." % (
        review_path, loop.tracker, loopstate.STATE_NAME, loop.tracker, recap.NAME))
    done = ["Wrote %s." % review_path, "Wrote %s/%s." % (loop.tracker, recap.NAME),
            "Recorded in %s/%s: %s" % (loop.tracker, loopstate.STATE_NAME, user)]
    if reopening:
        dry.append("Would reopen the closed loop %s." % loop.slug)
        done.append("Reopened the loop %s." % loop.slug)
    done.append("Findings %s open: %d blocker, %d major, %d minor." % ((workfile.join_numbers(numbers),) + counts))
    if carried:
        dry.append(carried)
        done.append(carried)
    effects: list[runner.Effect] = [runner.WriteFile(
        os.path.join(loop.dir, NAME), "\n".join(lines) + "\n", review_path,
        "Otherwise tell the user CODEREVIEW.md cannot be written, and stop.", dry, done)]
    effects += runner.record_step(store, state, [], [user], reopen_loop=reopening)
    return runner.Plan(effects, CARRY_ON, dry_next="Run %s" % command(loop, source))


def same(block: workfile.Block, finding: Finding) -> bool:
    """Whether block is finding as an earlier add wrote it: the same
    severity, reference and text."""
    body = block.text_lines()[1:]
    while body and not body[0].strip():
        body.pop(0)
    return (block.severity == finding.severity and block.reference.strip() == finding.reference
            and [line.rstrip() for line in body] == body_lines(finding.body))


def already_added(loop: loopfile.Loop, state: loopstate.State, entry: Entry, source: str) -> runner.Plan:
    """Every finding of source is in the open entry: a rerun after the commit
    point, which writes RECAP.md again where a failure left it behind."""
    joined = entry.joined
    if joined is None:
        raise RuntimeError("already_added without an open entry.")
    store = records.Records.load(loop)
    numbers = workfile.join_numbers(joined.raised())
    added = "The findings of %s are already added after round %d's Sign-off, as findings %s. " % (
        source, entry.round, numbers)
    still = "Findings %s open: %d blocker, %d major, %d minor." % ((numbers,) + tuple(joined.counts))
    recap_ = runner.RenderRecap(store, state, dry=[added + "Nothing was written.", still],
                                done=[added + "Wrote %s/%s again." % (loop.tracker, recap.NAME), still],
                                unchanged=[added + "Nothing was written.", still])
    return runner.Plan([recap_], CARRY_ON, dry_next=CARRY_ON)


CARRY_ON = ("Tell the Orchestrator the loop has your findings; it carries on with %s."
            % catalog.bare("orchestrator", "start"))


def command(loop: loopfile.Loop, source: str) -> str:
    return catalog.line("review", "add", slug=loop.slug, from_=catalog.quoted(source), write=True)
