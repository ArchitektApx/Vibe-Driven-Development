"""The coder command group: the Coder's round, framed and checked by the
tool.

coder start checks the round's precondition, puts the Coder on the feature
branch, records where the round starts and writes the round's frame of
FIXES.md. coder check lints FIXES.md and the working tree and, with --write,
records where the round ends and prints the Coder's Doorbell line.
"""

from __future__ import annotations

import os
import re
import textwrap
from typing import Any, Callable

from . import args, doorbells, fixes, gitcmd, loopfile, loopstate, places, recap, textfile, workfile
from .out import Failure, Output

SUBCOMMANDS = ("start", "check")
TICKET_FILE = re.compile(r"^([0-9]+)-.+\.md$")
ANSWERS = ("fixed", "pushback")
SNAPSHOT = "coder-untracked-%d"

HELP = [
    "coder start --slug <slug> --write",
    "  The Coder's first call each round. Refuses unless the plan Loop is signed off (round 1) or the last",
    "  code round's review left findings open (a later round). On the base branch it switches to the feature",
    "  branch, creating it from the base when it does not exist; on the feature branch it stays; on any other",
    "  branch it refuses. It records and prints \"Round <n> starts at <sha>.\", records the untracked files",
    "  already there and writes the round's frame of FIXES.md: one entry per Ticket in round 1, one per open",
    "  finding later. A second start in a round already started writes nothing and prints the same again.",
    "",
    "coder check --slug <slug> [--write]",
    "  Lint FIXES.md against its frame, and refuse uncommitted changes to tracked files, a file left untracked",
    "  since coder start, and a round whose recorded start is gone from the branch's history (an earlier",
    "  commit amended, rebased or reset): every refusal names the line or file and the fix and writes",
    "  nothing. With --write on a passing round it removes the guidance comment, records the branch tip as",
    "  the round's end, copies round 1's Ticket entries to .scratch/<slug>/RECAP.md and prints the Doorbell",
    "  line to end your turn with.",
    "",
    "--slug names the loop; pass it on every call. Run every command from the repository root.",
]

SPEC = {"slug": args.VALUE, "write": args.FLAG}


def usage() -> str:
    return "%s coder --help" % places.command()


def run(argv: list[str]) -> int:
    return args.run_group(argv, "coder", dict.fromkeys(SUBCOMMANDS, SPEC), HELP,
                          "Run the coder command your skill or the last Next: line names.", dispatch)


def dispatch(sub: str, values: dict[str, Any]) -> int:
    loop = loopfile.find(gitcmd.project_root(os.getcwd()), values["slug"])
    state = loopstate.open_loop(loop, "coder %s" % sub)
    round_ = Round(loop, state)
    if sub == "start":
        return start(round_, values["write"])
    return check(round_, values["write"])


# --- git ---

def git(root: str, *argv: str) -> gitcmd.Call:
    """The finished gitcmd.Call of a git command run in root; refuses when git
    cannot run."""
    call = gitcmd.git(root, *argv)
    if call.code is None:
        raise Failure("git could not run: %s" % call.err, "Tell the user git is needed for the Coder's round, and stop.")
    return call


def head(root: str) -> str:
    call = git(root, "rev-parse", "HEAD")
    sha = call.out.strip()
    if not call.ok or not sha:
        raise Failure("This repository has no commit, so the round has no start.",
                      "Tell the user the repository needs a first commit on the base branch, and stop.")
    return sha


def branch_exists(root: str, branch: str) -> bool:
    return git(root, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch).ok


def dirty(root: str) -> list[str]:
    """The tracked files with uncommitted changes."""
    call = git(root, "diff", "--name-only", "HEAD")
    if not call.ok:
        raise Failure("git diff failed: %s" % call.err.strip(), "Tell the user git diff fails in this repository, and stop.")
    return [line.strip() for line in call.out.strip().split("\n") if line.strip()]


def untracked(root: str) -> list[str]:
    """The work tree's untracked, not ignored files, from git's NUL-separated
    list. A path that holds a line break is left out: a snapshot keeps one
    path per line."""
    call = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if not call.ok:
        raise Failure("git ls-files failed: %s" % call.err.strip(),
                      "Tell the user git ls-files fails in this repository, and stop.")
    return [name for name in call.out.split("\0") if name and "\n" not in name]


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
        return "%s coder %s --slug %s%s" % (places.command(), sub, self.loop.slug, " --write" if write else "")

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


# --- start ---

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


def decide_branch(round_: Round) -> str | None:
    """The branch switch the round needs, read-only: None on the feature
    branch, "switch" to an existing one, "create" from the base branch. Refuses
    on any other branch, naming both."""
    root = round_.loop.root
    current = gitcmd.current_branch(root)
    if current == round_.branch:
        return None
    if current != round_.base:
        raise Failure(
            "The checked-out branch is %s: neither the base branch %s nor the feature branch %s. Nothing was "
            "written." % (current or "none (a detached HEAD)", round_.base, round_.branch),
            "Return QUESTION: I am on %s, neither the base branch %s nor the feature branch %s. Which branch "
            "do I work on?" % (current or "a detached HEAD", round_.base, round_.branch),
        )
    return "switch" if branch_exists(root, round_.branch) else "create"


def to_branch(round_: Round, out: Output, write: bool = True) -> bool:
    """Put the Coder on the feature branch, or refuse naming both branches.
    Without write, switch nothing and return whether a switch is owed."""
    decision = decide_branch(round_)
    if decision is None:
        out.line("On the feature branch %s." % round_.branch)
        return False
    if not write:
        if decision == "switch":
            out.line("Would switch to the feature branch %s." % round_.branch)
        else:
            out.line("Would create the feature branch %s from %s and switch to it." % (round_.branch, round_.base))
        return True
    apply_branch(round_, decision, out)
    return False


def apply_branch(round_: Round, decision: str, out: Output) -> None:
    """Switch to the feature branch as decide_branch decided."""
    root = round_.loop.root
    if decision == "switch":
        call = git(root, "checkout", "-q", round_.branch)
        verb = "Switched to the feature branch %s." % round_.branch
    else:
        call = git(root, "checkout", "-q", "-b", round_.branch)
        verb = "Created the feature branch %s from %s and switched to it." % (round_.branch, round_.base)
    if not call.ok:
        error = call.err.strip()
        if call.refused:
            raise gitcmd.sandbox_refusal(
                call, round_.command("start"),
                "tell the user git could not check out the feature branch %s, and stop." % round_.branch,
                ["git could not switch to %s." % round_.branch])
        raise Failure(
            "git could not switch to %s: %s" % (round_.branch, error),
            "Tell the user git could not check out the feature branch %s, and stop." % round_.branch,
        )
    out.line(verb)


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


def start(round_: Round, write: bool) -> int:
    precondition(round_)
    if round_.number == 1 and not tickets(round_.loop):
        raise Failure(
            "%s holds no Ticket file (NN-<slug>.md), so round 1 has nothing to build. Nothing was written."
            % round_.path("issues/"),
            "End your turn with BLOCKED: the loop has no Tickets.",
        )
    out = Output()
    again = round_.started
    if not write and not again:
        # Every read-only check of the write path runs before a dry run
        # returns, so it refuses wherever --write would.
        skeleton(round_)
        head(round_.loop.root)
        decide_branch(round_)
        untracked(round_.loop.root)
        out.line("Would start code round %d on %s and write the frame of %s." % (
            round_.number, round_.branch, round_.relative))
        return out.finish("Run the same command with --write.")
    if again:
        if to_branch(round_, out, write):
            out.line("Round %d was already started: %s stays as it is. Nothing was written."
                     % (round_.number, round_.relative))
            return out.finish("Run the same command with --write.")
        out.line("Round %d was already started: %s stays as it is. Nothing was written."
                 % (round_.number, round_.relative))
        sha = round_.state.code_mark("start", round_.number)
    else:
        lines = skeleton(round_)
        head(round_.loop.root)  # an unborn HEAD refuses before the switch
        to_branch(round_, out)
        sha = head(round_.loop.root)
        textfile.write_or_refuse(round_.file, "\n".join(lines) + "\n", round_.relative,
                                 "Otherwise tell the user FIXES.md cannot be written, and stop.")
        found = untracked(round_.loop.root)
        textfile.write_or_refuse(os.path.join(round_.loop.dir, round_.snapshot_name()),
                                 "".join(name + "\n" for name in found), round_.path(round_.snapshot_name()),
                                 "Otherwise tell the user the round's snapshot cannot be written, and stop.")
        round_.state.append(loopstate.code_mark_line("start", round_.number, sha))
        out.line("Wrote the frame of %s." % round_.relative)
    out.line("Round %d starts at %s." % (round_.number, sha))
    if round_.number == 1:
        out.line("Entries: one per Ticket, %s." % workfile.join_numbers([n for n, _ in tickets(round_.loop)]))
    else:
        out.line("Entries: one per open finding, %s." % workfile.join_numbers(round_.open_numbers))
    out.line("Read: %s" % ", ".join(round_.read_list()))
    work = "Build the Tickets in order" if round_.number == 1 else "Answer every open finding"
    return out.finish(
        "%s, committing on %s as your skill says, and fill each entry of %s. Then run %s. Pass --slug %s on "
        "every VDD tool call from here on." % (work, round_.branch, round_.relative, round_.command("check"),
                                               round_.loop.slug)
    )


# --- check ---

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
    for number, name in tickets(round_.loop):
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
                                for n, severity, reference in open_findings(round_))
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


def check(round_: Round, write: bool) -> int:
    if not round_.started:
        if round_.newest and round_.state.review("code", round_.newest) is None:
            return already_recorded(round_, write)
        raise Failure(
            "Code round %d has not been started, so %s has no frame to check." % (round_.number, round_.relative),
            "Run %s first." % round_.command("start"),
        )
    root = round_.loop.root
    current = gitcmd.current_branch(root)
    if current != round_.branch:
        raise Failure(
            "The checked-out branch is %s, not the feature branch %s, so the round's end cannot be read. Nothing "
            "was written." % (current or "none (a detached HEAD)", round_.branch),
            "Check out %s with git, then run %s again." % (round_.branch, round_.command("check", write)),
        )
    text = textfile.read(round_.file)
    if text is None:
        raise Failure("%s does not exist. Nothing was written." % round_.relative,
                      "Tell the user FIXES.md is gone in the middle of round %d, and stop." % round_.number)
    parsed = workfile.Parsed(text)
    lint_ = lint(round_, parsed)
    rewritten = start_gone(round_)
    if rewritten:
        lint_.last(rewritten)
    changed = dirty(root)
    if changed:
        lint_.last("The working tree has uncommitted changes to tracked files: %s. Uncommitted work is not "
                   "reviewed; commit it with git." % ", ".join(changed))
    left = new_untracked(round_)
    if left:
        lint_.last("The round left untracked files that were not untracked when it started: %s. A file never "
                   "added misses the commits, the fold and the PR: commit it with git if it belongs to the "
                   "work, or delete it if it is a by-product." % ", ".join(left))
    lint_.refuse("Fix the lines above, then run %s again." % round_.command("check", write))
    store = recap.Records.load(round_.loop)
    out = Output()
    if not write:
        out.line("%s passes: round %d." % (fixes.NAME, round_.number))
        return out.finish("Run %s" % round_.command("check"))
    tip = head(root)
    cleaned = cleaned_text(parsed)
    records = []
    if round_.number == 1:
        records.append(recap.Record(recap.TICKETS_KEY, "Tickets", recap_tickets(workfile.Parsed(cleaned))))
    recap.record(round_.loop, round_.state, store, records, [loopstate.code_mark_line("end", round_.number, tip)])
    write_recorded(round_, cleaned)
    out.line("%s: round %d checked and written." % (fixes.NAME, round_.number))
    out.line("Round %d ends at %s." % (round_.number, tip))
    if round_.number == 1:
        out.line("Copied the Ticket entries to %s." % round_.path(recap.NAME))
    out.line(loopstate.coder_doorbell(round_.number))
    return out.finish("End your turn with the Doorbell line above as your whole reply.")


def cleaned_text(parsed: workfile.Parsed) -> str:
    """FIXES.md after a passing check: no guidance comment. Computed from its
    own result it gives the same text."""
    return "\n".join(workfile.squeeze(workfile.without_guides(parsed.texts))) + "\n"


def write_recorded(round_: Round, text: str) -> None:
    """Step 5: FIXES.md rewritten, after the commit point."""
    textfile.write_or_refuse(round_.file, text, round_.relative,
                             "Otherwise tell the user the round is recorded and FIXES.md cannot be written; once it "
                             "can be, the same command run again writes it. Then stop.")


def already_recorded(round_: Round, write: bool) -> int:
    """A rerun after the commit point: RECAP.md and FIXES.md written again
    where a failure left them behind, the round not recorded twice."""
    out = Output()
    written = []
    store = recap.Records.load(round_.loop)
    if write:
        if recap.render_recap(round_.loop, round_.state, store):
            written.append(round_.path(recap.NAME))
        text = textfile.read(round_.file)
        parsed = workfile.Parsed(text) if text is not None else None
        title = parsed.title if parsed is not None else None
        if parsed is not None and title is not None and title.text.strip() == "# Fixes, round %d" % round_.newest:
            cleaned = cleaned_text(parsed)
            if cleaned != text:
                write_recorded(round_, cleaned)
                written.append(round_.relative)
    if written:
        out.line("Round %d's end is already recorded. Wrote %s again." % (round_.newest, " and ".join(written)))
    else:
        out.line("Round %d's end is already recorded. Nothing was written." % round_.newest)
    out.line(loopstate.coder_doorbell(round_.newest))
    return out.finish("End your turn with the Doorbell line above as your whole reply.")


def new_untracked(round_: Round) -> list[str]:
    """The untracked, not ignored files the round's start did not record. A
    round with no snapshot (started on an older version) has none."""
    before = round_.snapshot()
    if before is None:
        return []
    known = set(before)
    known.add(round_.path(round_.snapshot_name()))
    return [name for name in untracked(round_.loop.root) if name not in known]


def start_gone(round_: Round) -> str | None:
    """The refusal for a round whose recorded start is no longer in HEAD's
    history, or None. The fold after the code Sign-off reads every round's
    recorded end; an amend, rebase or reset of an earlier round's commit
    loses it (ticket 71)."""
    start = round_.state.code_mark("start", round_.number)
    if not start:
        return None
    if git(round_.loop.root, "merge-base", "--is-ancestor", start, "HEAD").ok:
        return None
    return ("Round %d started at %s, and that commit is no longer in %s's history: an earlier commit was amended, "
            "rebased or reset. Bring the earlier commits back with `git reset --soft %s`, which keeps your "
            "changes, then commit the change as a new commit." % (round_.number, start, round_.branch, start))


def recap_tickets(parsed: workfile.Parsed) -> list[str]:
    lines = []
    for entry in fixes.entries(parsed):
        if lines:
            lines.append("")
        lines.append("#" + entry.heading.text)
        body = [line.text for line in entry.body]
        while body and not body[-1].strip():
            body.pop()
        lines += body
    return lines
