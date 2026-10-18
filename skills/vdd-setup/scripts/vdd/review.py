"""The review command group: the Plan-Reviewer's and the Code-Reviewer's
round, framed and checked by the tool.

review start writes the round's frame of the review file, every finding
still open carried whole, and records the round as started. review check
lints the reviewer's file against that frame and, with --write, writes the
status line, moves every closed finding to the Recap, records the round's
outcome in the state file and prints the Doorbell line.
"""

import os
import re
import textwrap

from . import args, doorbell, loopfile, loopstate, places, recap, textfile, workfile
from .out import Failure, Output, refused

SUBCOMMANDS = ("start", "check")
REVIEWERS = {"Plan-Reviewer": "plan", "Code-Reviewer": "code"}
FILES = {"plan": "PLAN-REVIEW.md", "code": "CODEREVIEW.md"}
TITLES = {"plan": "Plan review", "code": "Code review"}
CARRIED = "carried-%s.md"
LABELS = ("Resolution", "Coder", "Reviewer")
STATUS_LINE = re.compile(r"^(Open: [0-9]+ blocker, [0-9]+ major, [0-9]+ minor\.|SIGNED OFF\. Nothing open\."
                         r"|SIGNED OFF\. Open minors left, as Minors: leave allows: [0-9]+\.)\s*$")
STATES = ("open", "fixed", "accepted")

CHECKS = {
    "plan": (("writing-for-agents", ("ran", "did not resolve")),),
    "code": (
        ("code-review", ("ran", "did not resolve, the Spec reviewed by hand")),
        ("writing-for-agents", ("ran", "did not resolve", "no Agent document in this round's diff")),
    ),
}
PLACEHOLDERS = {
    "code-review": "<ran | did not resolve, the Spec reviewed by hand>",
    "writing-for-agents": "<ran | did not resolve>",
}

HELP = [
    "review start --role <Plan-Reviewer|Code-Reviewer> --slug <slug> --write",
    "  The reviewer's first call each round. Writes the round's frame of PLAN-REVIEW.md or CODEREVIEW.md:",
    "  the title, a guidance comment, ## Checks, ## Open findings with every still-open finding carried",
    "  whole (round 2 on), ## New findings and, for the Code-Reviewer, ## Not carried. Prints the round, the",
    "  carried findings, the number new findings start at, the files to read and the Minors: line. A second",
    "  start in a round already started writes nothing and prints the same again.",
    "",
    "review check --role <Plan-Reviewer|Code-Reviewer> --slug <slug> [--write]",
    "  Lint the review file against its frame: every refusal names the line and the fix and writes nothing.",
    "  With --write on a passing file it removes the guidance comments, writes the status line under the",
    "  title, moves every closed finding to .scratch/<slug>/RECAP.md, records the round in the state file",
    "  and prints the Doorbell line to end your turn with.",
    "",
    "--slug names the loop; pass it on every call. Run every command from the repository root.",
]

SPEC = {"role": args.VALUE, "slug": args.VALUE, "write": args.FLAG}


def usage():
    return "%s review --help" % places.command()


def run(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        out = Output()
        for line in HELP:
            out.line(line)
        return out.finish("Run the review command your skill or the last Next: line names.")
    sub, rest = argv[0], argv[1:]
    if sub not in SUBCOMMANDS:
        args.unknown_command("review " + sub, usage())
    values = args.parse(rest, SPEC, usage())
    if values["help"]:
        return run(["--help"])
    role = values["role"]
    if role not in REVIEWERS:
        raise Failure("--role takes Plan-Reviewer or Code-Reviewer.", "Run %s for the usage." % usage())
    loop = loopfile.find(loopfile.project_root(os.getcwd()), values["slug"])
    state = loopstate.open_loop(loop, "review %s" % sub)
    round_ = Round(loop, state, role)
    if sub == "start":
        return start(round_, values["write"])
    return check(round_, values["write"])


class Round:
    """The review round a command acts on: the next one after the last
    recorded review."""

    def __init__(self, loop, state, role):
        self.loop = loop
        self.state = state
        self.role = role
        self.kind = REVIEWERS[role]
        self.name = FILES[self.kind]
        self.file = os.path.join(loop.dir, self.name)
        self.relative = "%s/%s" % (loop.tracker, self.name)
        self.last = state.last_review(self.kind)
        self.number = (self.last.round + 1) if self.last else 1
        self.carried_numbers = list(self.last.open) if self.last else []
        self.first_new = state.next_number(self.kind)
        self.carried_file = os.path.join(loop.dir, CARRIED % self.kind)

    def command(self, sub, write=True):
        return "%s review %s --role %s --slug %s%s" % (
            places.command(), sub, self.role, self.loop.slug, " --write" if write else "")

    def minors(self):
        return self.loop.setting("Minors")[0]

    def path(self, name):
        return "%s/%s" % (self.loop.tracker, name)

    def read_list(self):
        names = [self.name] if self.number > 1 else []
        names += ["spec.md", "issues/"]
        return [self.path(name) for name in names]


# --- start ---

def planner_rung(loop):
    """The newest round the Planner rang, or 0."""
    place = doorbell.Place(loop.root, loop.slug)
    rounds = [e.doorbell.round for e in place.entries("Orchestrator") if e.doorbell]
    return max(rounds) if rounds else 0


def require_round(round_):
    if round_.last and round_.last.signed_off:
        raise Failure(
            "The %s Loop signed off in round %d: there is no round %d to review. Nothing was written."
            % (round_.kind, round_.last.round, round_.number),
            "End your turn with BLOCKED: the %s Loop is already signed off." % round_.kind,
        )
    if round_.kind == "plan":
        rung = planner_rung(round_.loop)
        if rung < round_.number:
            last = "round %d" % round_.last.round if round_.last else "none yet"
            raise Failure(
                "The Planner has rung no round after the last plan review (%s): there is no plan round %d to "
                "review. Nothing was written." % (last, round_.number),
                "End your turn with BLOCKED: the Planner has not rung plan round %d." % round_.number,
            )


def round_available(round_):
    try:
        require_round(round_)
    except Failure:
        return False
    return True


def carried_blocks(round_):
    """number -> the block's lines, for every finding still open, from the
    review file as the last check left it, else from the carried file."""
    blocks = {}
    for path in (round_.file, round_.carried_file):
        text = textfile.read(path)
        if text is None:
            continue
        for block in workfile.Parsed(text).blocks:
            if block.number in round_.carried_numbers and block.number not in blocks:
                blocks[block.number] = block.text_lines()
    missing = [n for n in round_.carried_numbers if n not in blocks]
    if missing:
        raise Failure(
            "%s no longer holds finding%s %s, which round %d left open. Nothing was written."
            % (round_.relative, "" if len(missing) == 1 else "s", workfile.join_numbers(missing),
               round_.number - 1),
            "Tell the user %s lost a finding the loop still has open, and stop." % round_.relative,
        )
    return [blocks[n] for n in round_.carried_numbers]


def guidance(round_):
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


def skeleton(round_, blocks):
    lines = ["# %s, round %d" % (TITLES[round_.kind], round_.number), ""]
    lines += guidance(round_)
    lines += ["", "## Checks", ""]
    for name, _ in CHECKS[round_.kind]:
        lines.append("%s: %s" % (name, PLACEHOLDERS[name]))
    if round_.number > 1:
        lines += ["", "## Open findings"]
        for block in blocks:
            lines += [""] + block
    lines += ["", "## New findings"]
    return lines


def start(round_, write):
    require_round(round_)
    out = Output()
    again = round_.state.review_started(round_.kind, round_.number)
    if again:
        out.line("Round %d was already started: %s stays as it is. Nothing was written."
                 % (round_.number, round_.relative))
    elif not write:
        out.line("Would write the frame of %s for round %d." % (round_.relative, round_.number))
        return out.finish("Run the same command with --write.")
    else:
        blocks = carried_blocks(round_)
        carried_text = "\n\n".join("\n".join(block) for block in blocks)
        try:
            textfile.write(round_.carried_file, (carried_text + "\n" if carried_text else "").encode("utf-8"))
            textfile.write(round_.file, ("\n".join(skeleton(round_, blocks)) + "\n").encode("utf-8"))
        except OSError as error:
            raise refused(
                "Could not write %s: %s" % (round_.relative, error),
                "Otherwise tell the user the review file cannot be written, and stop.",
            )
        round_.state.append("%s %d review-started" % (round_.kind, round_.number))
        out.line("Wrote the frame of %s." % round_.relative)
    if round_.carried_numbers:
        carried = "finding%s %s carried open" % (
            "" if len(round_.carried_numbers) == 1 else "s", workfile.join_numbers(round_.carried_numbers))
    else:
        carried = "no finding carried"
    out.line("Round %d: %s, new findings start at %d." % (round_.number, carried, round_.first_new))
    out.line("Read: %s" % ", ".join(round_.read_list()))
    out.line("Minors: %s" % round_.minors())
    return out.finish(
        "Review, write your findings into %s under the headings it has, then run %s. Pass --slug %s on every "
        "VDD tool call from here on." % (round_.relative, round_.command("check"), round_.loop.slug)
    )


# --- check ---

class Lint:
    """The refusals of one check, in file order."""

    def __init__(self, round_):
        self.round = round_
        self.problems = []

    def at(self, line, text):
        if line is None:
            self.problems.append((0, ["%s: %s" % (self.round.name, text)]))
        else:
            self.problems.append((line.number, ["%s line %d: %s" % (self.round.name, line.number, text)]))

    def block(self, text, block_lines):
        """A refusal followed by a block to put back, one output line per
        line of the block."""
        self.problems.append((10 ** 9, ["%s: %s" % (self.round.name, text)] + block_lines))


def sections_expected(round_):
    names = ["Checks"]
    if round_.number > 1:
        names.append("Open findings")
    names.append("New findings")
    return names


def lint(round_, parsed):
    lint_ = Lint(round_)
    title = "# %s, round %d" % (TITLES[round_.kind], round_.number)
    if parsed.title is None:
        lint_.at(None, "the title \"%s\" is missing. Put it back as the first line." % title)
    elif parsed.title.text.strip() != title:
        lint_.at(parsed.title, "the title is \"%s\", as the tool wrote it." % title)
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
    return lint_


def lint_checks(round_, parsed, lint_):
    section = parsed.section("Checks")
    if section is None:
        return
    seen = {}
    for line in section.body:
        if not line.frame or ":" not in line.text:
            continue
        name, _, value = line.text.partition(":")
        seen[name.strip()] = (line, value.strip())
    for name, accepted in CHECKS[round_.kind]:
        if name not in seen:
            lint_.at(section.line, "the Checks line \"%s: %s\" is missing. Put it back and fill it in."
                     % (name, PLACEHOLDERS[name]))
            continue
        line, value = seen[name]
        if value not in accepted:
            lint_.at(line, "\"%s\" is not filled in. Write one of: %s." % (
                line.text.strip(), ", ".join("%s: %s" % (name, a) for a in accepted)))


def lint_findings(round_, parsed, lint_):
    carried = set(round_.carried_numbers)
    seen = set()
    new_numbers = []
    for block in parsed.blocks:
        section = block.section.name if block.section else None
        if section not in ("Open findings", "New findings"):
            lint_.at(block.heading, "a finding heading belongs under ## Open findings or ## New findings.")
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


def outcome(round_, parsed):
    """(open blocks, closed blocks, counts, signed off)."""
    findings = [b for b in parsed.blocks if b.match is not None]
    open_blocks = [b for b in findings if b.state == "open"]
    closed = [b for b in findings if b.state in ("fixed", "accepted")]
    counts = tuple(sum(1 for b in open_blocks if b.severity == s) for s in loopstate.SEVERITIES)
    signed_off = counts[0] == 0 and counts[1] == 0 and (counts[2] == 0 or round_.minors() == "leave")
    return open_blocks, closed, counts, signed_off


def status_line(counts, signed_off):
    if signed_off and counts[2]:
        return "SIGNED OFF. Open minors left, as Minors: leave allows: %d." % counts[2]
    if signed_off:
        return "SIGNED OFF. Nothing open."
    return "Open: %d blocker, %d major, %d minor." % counts


def checks_text(round_, parsed):
    section = parsed.section("Checks")
    found = []
    for line in section.body:
        if line.frame and ":" in line.text:
            name, _, value = line.text.partition(":")
            if name.strip() in dict(CHECKS[round_.kind]):
                found.append("%s %s" % (name.strip(), value.strip()))
    return "; ".join(found)


def cleaned(parsed, status, closed):
    """The review file after a passing check: no guidance comment, the status
    line under the title, no closed finding."""
    drop = set()
    for block in closed:
        drop.add(block.heading.number)
        for line in block.body:
            drop.add(line.number)
    texts = [line.text for line in parsed.lines if line.number not in drop]
    texts = workfile.without_guides(texts)
    out = []
    # Only a line under the title in the shape status_line writes is replaced.
    under_title = titled = False
    for text in texts:
        if under_title and text.strip():
            under_title = False
            if STATUS_LINE.match(text):
                continue
        out.append(text)
        if parsed.title is not None and text == parsed.title.text and not titled:
            out += ["", status]
            under_title = titled = True
    return workfile.squeeze(out)


def recap_findings(round_, closed):
    lines = []
    for block in closed:
        if lines:
            lines.append("")
        lines.append("### %d. %s, %s in round %d: %s" % (
            block.number, block.severity, block.state, round_.number, block.reference))
        problem = block.problem(LABELS)
        lines.append("")
        if problem:
            lines.append("Problem: " + problem[0])
            lines += problem[1:]
        else:
            lines.append("Problem:")
        resolution = [label[1] for label in block.labels(LABELS) if label[0] == "Resolution"]
        lines += ["", "Resolution: " + " ".join(resolution)]
    return lines


def check(round_, write):
    if not round_.state.review_started(round_.kind, round_.number):
        if round_.last and not round_available(round_):
            return already_recorded(round_, round_.last)
        raise Failure(
            "Round %d of the %s review has not been started, so %s has no frame to check."
            % (round_.number, round_.kind, round_.relative),
            "Run %s first." % round_.command("start"),
        )
    text = textfile.read(round_.file)
    if text is None:
        raise Failure(
            "%s does not exist. Nothing was written." % round_.relative,
            "Run %s; it writes the frame again, then fill it in." % round_.command("start"),
        )
    parsed = workfile.Parsed(text)
    lint_ = lint(round_, parsed)
    if lint_.problems:
        lines = []
        for _, texts in sorted(lint_.problems, key=lambda p: p[0]):
            lines += texts
        lines.append("Nothing written; RECAP.md and the state file are unchanged.")
        raise Failure(lines, "Fix the lines above, then run %s again." % round_.command("check", write))
    open_blocks, closed, counts, signed_off = outcome(round_, parsed)
    status = status_line(counts, signed_off)
    new = sum(1 for b in parsed.blocks_in("New findings") if b.match is not None)
    out = Output()
    if not write:
        out.line("%s passes: round %d, %d new finding%s, %d closed." % (
            round_.name, round_.number, new, "" if new == 1 else "s", len(closed)))
        out.line(status)
        return out.finish("Run %s" % round_.command("check"))
    numbers = sorted(b.number for b in open_blocks)
    next_number = max([round_.first_new - 1] + [b.number for b in parsed.blocks if b.match is not None]) + 1
    line = loopstate.reviewed_line(round_.kind, round_.number, signed_off, numbers, counts, next_number, new,
                                   len(closed), checks_text(round_, parsed))
    round_.state.lines.append(line)
    review = round_.state.review(round_.kind, round_.number)
    section = "Plan findings" if round_.kind == "plan" else "Code findings"
    try:
        textfile.write(round_.file, ("\n".join(cleaned(parsed, status, closed)) + "\n").encode("utf-8"))
    except OSError as error:
        raise refused(
            "Could not write %s: %s" % (round_.relative, error),
            "Otherwise tell the user the review file cannot be written, and stop.",
        )
    recap.write(round_.loop, round_.state, {section: recap_findings(round_, closed)})
    round_.state.persist(line)
    out.line("%s: round %d checked and written." % (round_.name, round_.number))
    out.line(status)
    if closed:
        out.line("Moved to %s: finding%s %s." % (
            round_.path(recap.NAME), "" if len(closed) == 1 else "s",
            workfile.join_numbers([b.number for b in closed])))
    out.line(loopstate.review_doorbell(review))
    return out.finish("End your turn with the Doorbell line above as your whole reply.")


def already_recorded(round_, review):
    out = Output()
    out.line("Round %d of the %s review is already recorded. Nothing was written." % (review.round, round_.kind))
    out.line(loopstate.review_doorbell(review))
    return out.finish("End your turn with the Doorbell line above as your whole reply.")
