"""The coder command group: the Coder's round, framed and checked by the
tool.

coder start checks the round's precondition, puts the Coder on the feature
branch, records where the round starts and writes the round's frame of
FIXES.md. coder check lints FIXES.md and the working tree and, with --write,
records where the round ends and prints the Coder's Doorbell line.
"""

import os
import re
import subprocess
import textwrap

from . import args, loopfile, loopstate, places, recap, textfile, workfile
from .out import Failure, Output, refused

SUBCOMMANDS = ("start", "check")
NAME = "FIXES.md"
TICKET_FILE = re.compile(r"^([0-9]+)-.+\.md$")
TICKET_HEADING = re.compile(r"^## Ticket ([0-9]+): (.+?)\s*$")
FINDING_HEADING = re.compile(r"^## Finding ([0-9]+)\. (\S+): (.+?)\s*$")
TICKET_LABELS = ("Files", "Change", "Verified", "Deviations", "Why")
FINDING_LABELS = ("Answer", "Why")
ANSWERS = ("fixed", "pushback")

HELP = [
    "coder start --slug <slug> --write",
    "  The Coder's first call each round. Refuses unless the plan Loop is signed off (round 1) or the last",
    "  code round's review left findings open (a later round). On the base branch it switches to the feature",
    "  branch, creating it from the base when it does not exist; on the feature branch it stays; on any other",
    "  branch it refuses. It records and prints \"Round <n> starts at <sha>.\" and writes the round's frame of",
    "  FIXES.md: one entry per Ticket in round 1, one per open finding later. A second start in a round",
    "  already started writes nothing and prints the same again.",
    "",
    "coder check --slug <slug> [--write]",
    "  Lint FIXES.md against its frame and refuse uncommitted changes to tracked files: every refusal names",
    "  the line or file and the fix and writes nothing. With --write on a passing round it removes the",
    "  guidance comment, records the branch tip as the round's end, copies round 1's Ticket entries to",
    "  .scratch/<slug>/RECAP.md and prints the Doorbell line to end your turn with.",
    "",
    "--slug names the loop; pass it on every call. Run every command from the repository root.",
]

SPEC = {"slug": args.VALUE, "write": args.FLAG}


def usage():
    return "%s coder --help" % places.command()


def run(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        out = Output()
        for line in HELP:
            out.line(line)
        return out.finish("Run the coder command your skill or the last Next: line names.")
    sub, rest = argv[0], argv[1:]
    if sub not in SUBCOMMANDS:
        args.unknown_command("coder " + sub, usage())
    values = args.parse(rest, SPEC, usage())
    if values["help"]:
        return run(["--help"])
    loop = loopfile.find(loopfile.project_root(os.getcwd()), values["slug"])
    state = loopstate.open_loop(loop, "coder %s" % sub)
    round_ = Round(loop, state)
    if sub == "start":
        return start(round_, values["write"])
    return check(round_, values["write"])


# --- git ---

def git(root, *argv):
    """(exit code, stdout as text) of a git command run in root."""
    try:
        proc = subprocess.run(["git"] + list(argv), cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as error:
        raise Failure("git could not run: %s" % error, "Tell the user git is needed for the Coder's round, and stop.")
    return proc.returncode, textfile.decode(proc.stdout).strip(), textfile.decode(proc.stderr).strip()


def head(root):
    code, sha, _ = git(root, "rev-parse", "HEAD")
    if code != 0 or not sha:
        raise Failure("This repository has no commit, so the round has no start.",
                      "Tell the user the repository needs a first commit on the base branch, and stop.")
    return sha


def branch_exists(root, branch):
    code, _, _ = git(root, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch)
    return code == 0


def dirty(root):
    """The tracked files with uncommitted changes."""
    code, text, error = git(root, "diff", "--name-only", "HEAD")
    if code != 0:
        raise Failure("git diff failed: %s" % error, "Tell the user git diff fails in this repository, and stop.")
    return [line.strip() for line in text.split("\n") if line.strip()]


class Round:
    """The code round a command acts on."""

    def __init__(self, loop, state):
        self.loop = loop
        self.state = state
        self.base = loop.setting("Base branch")[0]
        self.branch = loop.setting("Feature branch")[0]
        self.file = os.path.join(loop.dir, NAME)
        self.relative = "%s/%s" % (loop.tracker, NAME)
        newest = state.code_round()
        self.newest = newest
        self.started = bool(newest) and state.code_mark("end", newest) is None
        self.number = newest if self.started else newest + 1
        previous = state.review("code", self.number - 1) if self.number > 1 else None
        self.previous = previous
        self.open_numbers = list(previous.open) if previous else []

    def command(self, sub, write=True):
        return "%s coder %s --slug %s%s" % (places.command(), sub, self.loop.slug, " --write" if write else "")

    def path(self, name):
        return "%s/%s" % (self.loop.tracker, name)

    def read_list(self):
        names = (["CODEREVIEW.md"] if self.number > 1 else []) + ["spec.md", "issues/"]
        return [self.path(name) for name in names]


def tickets(loop):
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

def precondition(round_):
    """Refuse a round its loop is not ready for."""
    state = round_.state
    if round_.started:
        return
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
        return
    plan = state.last_review("plan")
    if plan is None or not plan.signed_off:
        raise Failure(
            "The plan Loop is not finished: the plan review has not signed off, so the Spec is no contract yet. "
            "Nothing was written.",
            "End your turn with BLOCKED: the plan Loop is not signed off.",
        )


def to_branch(round_, out, write=True):
    """Put the Coder on the feature branch, or refuse naming both branches.
    Without write, switch nothing and return whether a switch is owed."""
    root = round_.loop.root
    current = loopfile.current_branch(root)
    if current == round_.branch:
        out.line("On the feature branch %s." % round_.branch)
        return False
    if current != round_.base:
        raise Failure(
            "The checked-out branch is %s: neither the base branch %s nor the feature branch %s. Nothing was "
            "written." % (current or "none (a detached HEAD)", round_.base, round_.branch),
            "Return QUESTION: I am on %s, neither the base branch %s nor the feature branch %s. Which branch "
            "do I work on?" % (current or "a detached HEAD", round_.base, round_.branch),
        )
    if not write:
        if branch_exists(root, round_.branch):
            out.line("Would switch to the feature branch %s." % round_.branch)
        else:
            out.line("Would create the feature branch %s from %s and switch to it." % (round_.branch, round_.base))
        return True
    if branch_exists(root, round_.branch):
        code, _, error = git(root, "checkout", "-q", round_.branch)
        verb = "Switched to the feature branch %s." % round_.branch
    else:
        code, _, error = git(root, "checkout", "-q", "-b", round_.branch)
        verb = "Created the feature branch %s from %s and switched to it." % (round_.branch, round_.base)
    if code != 0:
        raise Failure(
            "git could not switch to %s: %s" % (round_.branch, error),
            "Tell the user git could not check out the feature branch %s, and stop." % round_.branch,
        )
    out.line(verb)
    return False


def ticket_guidance():
    return textwrap.wrap(
        "<!-- VDD: the VDD tool wrote this frame, and `coder check` reads it. Under each Ticket fill Files, "
        "Change and Verified. Verified is the result of each check you ran, never its output. Add Deviations: "
        "and Why: when you departed from the Ticket. Keep every line that starts with ##. The tool removes this "
        "comment when the file passes. -->", 76, break_long_words=False, break_on_hyphens=False)


def finding_guidance():
    return textwrap.wrap(
        "<!-- VDD: the VDD tool wrote this frame, and `coder check` reads it. Under each finding set Answer to "
        "`fixed` or `pushback`. Why is required for pushback, and optional for fixed: write it when your fix "
        "differs from the one the finding asks for. Keep every line that starts with ##. The tool removes this "
        "comment when the file passes. -->", 76, break_long_words=False, break_on_hyphens=False)


def open_findings(round_):
    """(number, severity, reference) of every finding the last review left
    open, from CODEREVIEW.md's headings, else carried-code.md's."""
    found = {}
    for name in ("CODEREVIEW.md", "carried-code.md"):
        text = textfile.read(os.path.join(round_.loop.dir, name))
        if text is None:
            continue
        for block in workfile.Parsed(text).blocks:
            if block.number in round_.open_numbers and block.number not in found and block.match:
                found[block.number] = (block.number, block.severity, block.reference)
    missing = [n for n in round_.open_numbers if n not in found]
    if missing:
        raise Failure(
            "CODEREVIEW.md has no heading for finding%s %s, which round %d's review left open. Nothing was "
            "written." % ("" if len(missing) == 1 else "s", workfile.join_numbers(missing), round_.number - 1),
            "Tell the user CODEREVIEW.md lost a finding the loop still has open, and stop.",
        )
    return [found[n] for n in round_.open_numbers]


def skeleton(round_):
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


def start(round_, write):
    precondition(round_)
    if round_.number == 1 and not tickets(round_.loop):
        raise Failure(
            "%s holds no Ticket file (NN-<slug>.md), so round 1 has nothing to build. Nothing was written."
            % round_.path("issues/"),
            "End your turn with BLOCKED: the loop has no Tickets.",
        )
    out = Output()
    # The fold commands in the Coder's skill name <base>, and a later round
    # runs no loop show (code review round 4, finding 11).
    out.line("Base branch: %s." % round_.base)
    again = round_.started
    if not write and not again:
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
        to_branch(round_, out)
        sha = head(round_.loop.root)
        try:
            textfile.write(round_.file, ("\n".join(lines) + "\n").encode("utf-8"))
        except OSError as error:
            raise refused(
                "Could not write %s: %s" % (round_.relative, error),
                "Otherwise tell the user FIXES.md cannot be written, and stop.",
            )
        round_.state.append("code %d start %s" % (round_.number, sha))
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

class Entry:
    """One "##" entry of FIXES.md and its labels."""

    def __init__(self, heading):
        self.heading = heading
        self.body = []

    def labels(self, names):
        """label -> (joined text, Line): the label line plus every line after
        it up to the next label or heading, joined with single spaces."""
        found = {}
        current = None
        for line in self.body:
            label = workfile.label_of(line, names)
            if label:
                current = [line.text[len(label) + 1:].strip(), line]
                if label not in found:
                    found[label] = current
                continue
            if current is not None and line.frame and line.text.strip():
                current[0] = (current[0] + " " + line.text.strip()).strip()
        return dict((label, tuple(value)) for label, value in found.items())


def entries(parsed):
    out = []
    current = None
    for line in parsed.lines:
        if line.frame and line.text.startswith("## "):
            current = Entry(line)
            out.append(current)
        elif line.frame and line.text.startswith("# "):
            current = None
        elif current is not None:
            current.body.append(line)
    return out


def lint(round_, parsed):
    problems = []

    def at(line, text):
        problems.append((line.number if line else 0, "%s line %d: %s" % (NAME, line.number, text) if line
                         else "%s: %s" % (NAME, text)))

    title = "# Fixes, round %d" % round_.number
    if parsed.title is None:
        at(None, "the title \"%s\" is missing. Put it back as the first line." % title)
    elif parsed.title.text.strip() != title:
        at(parsed.title, "the title is \"%s\", as the tool wrote it." % title)
    if parsed.unclosed is not None:
        at(parsed.unclosed, workfile.unclosed_text(parsed.unclosed))
    found = entries(parsed)
    if round_.number == 1:
        lint_tickets(round_, found, at)
    else:
        lint_findings(round_, found, at)
    return [text for _, text in sorted(problems, key=lambda p: p[0])]


def lint_tickets(round_, found, at):
    by_number = {}
    for entry in found:
        match = TICKET_HEADING.match(entry.heading.text)
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
        labels = entry.labels(TICKET_LABELS)
        for label in ("Files", "Change", "Verified"):
            text, line = labels.get(label, ("", None))
            if line is None:
                at(entry.heading, "Ticket %s has no %s: line. Put it back under its heading and fill it in."
                   % (number, label))
            elif not text:
                fix = {"Files": "the files you touched", "Change": "what you changed",
                       "Verified": "the result of each check you ran, not its output"}[label]
                at(line, "Ticket %s's %s: is empty. Write %s." % (number, label, fix))


def lint_findings(round_, found, at):
    by_number = {}
    for entry in found:
        match = FINDING_HEADING.match(entry.heading.text)
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
        labels = entry.labels(FINDING_LABELS)
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


def check(round_, write):
    if not round_.started:
        if round_.newest and round_.state.review("code", round_.newest) is None:
            out = Output()
            out.line("Round %d's end is already recorded. Nothing was written." % round_.newest)
            out.line(loopstate.coder_doorbell(round_.newest))
            return out.finish("End your turn with the Doorbell line above as your whole reply.")
        raise Failure(
            "Code round %d has not been started, so %s has no frame to check." % (round_.number, round_.relative),
            "Run %s first." % round_.command("start"),
        )
    root = round_.loop.root
    current = loopfile.current_branch(root)
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
    problems = lint(round_, parsed)
    changed = dirty(root)
    if changed:
        problems.append("The working tree has uncommitted changes to tracked files: %s. Uncommitted work is not "
                        "reviewed; commit it with git." % ", ".join(changed))
    if problems:
        raise Failure(problems + ["Nothing written."],
                      "Fix the lines above, then run %s again." % round_.command("check", write))
    out = Output()
    if not write:
        out.line("%s passes: round %d." % (NAME, round_.number))
        return out.finish("Run %s" % round_.command("check"))
    tip = head(root)
    cleaned = workfile.squeeze(workfile.without_guides(parsed.texts))
    try:
        textfile.write(round_.file, ("\n".join(cleaned) + "\n").encode("utf-8"))
    except OSError as error:
        raise refused(
            "Could not write %s: %s" % (round_.relative, error),
            "Otherwise tell the user FIXES.md cannot be written, and stop.",
        )
    if round_.number == 1:
        recap.write(round_.loop, round_.state, {"Tickets": recap_tickets(workfile.Parsed("\n".join(cleaned)))})
    round_.state.append("code %d end %s" % (round_.number, tip))
    out.line("%s: round %d checked and written." % (NAME, round_.number))
    out.line("Round %d ends at %s." % (round_.number, tip))
    if round_.number == 1:
        out.line("Copied the Ticket entries to %s." % round_.path(recap.NAME))
    out.line(loopstate.coder_doorbell(round_.number))
    return out.finish("End your turn with the Doorbell line above as your whole reply.")


def recap_tickets(parsed):
    lines = []
    for entry in entries(parsed):
        if lines:
            lines.append("")
        lines.append("#" + entry.heading.text)
        body = [line.text for line in entry.body]
        while body and not body[-1].strip():
            body.pop()
        lines += body
    return lines
