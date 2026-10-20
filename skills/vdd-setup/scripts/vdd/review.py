"""The review command group: the Plan-Reviewer's and the Code-Reviewer's
round, framed and checked by the tool.

review start writes the round's frame of the review file, every finding
still open carried whole, and records the round as started. review check
lints the reviewer's file against that frame and, with --write, writes the
status line, moves every closed finding to the Recap, records the round's
outcome in the state file and prints the Doorbell line.
"""

from __future__ import annotations

import os
import re
import textwrap
from typing import Any, Iterable

from . import agentdocs, args, doorbells, fixes, gitcmd, loopfile, loopstate, places, recap, textfile, workfile
from .out import Failure, Output

SUBCOMMANDS = ("start", "check")
REVIEWERS = {"Plan-Reviewer": "plan", "Code-Reviewer": "code"}
FILES = {"plan": "PLAN-REVIEW.md", "code": "CODEREVIEW.md"}
TITLES = {"plan": "Plan review", "code": "Code review"}
CARRIED = "carried-%s.md"
NO_AGENT_DOCUMENT = "no Agent document in this round's diff"
NO_COMMITS = "not needed, no commits in this round"
NOT_CARRIED_GUIDE = [
    "<!-- VDD: One line for each problem the code-review reports raise that you",
    "do not turn into a finding, a wrong one included. A report line that finds",
    "nothing wrong gets no line.",
    "- <the problem, in one line>: <why not> -->",
]
LABELS = ("Resolution", "Coder", "Reviewer")
STATUS_LINE = re.compile(r"^(Open: [0-9]+ blocker, [0-9]+ major, [0-9]+ minor\.|SIGNED OFF\. Nothing open\."
                         r"|SIGNED OFF\. Open minors left, as Minors: leave allows: [0-9]+\.)\s*$")
STATES = ("open", "fixed", "accepted")

CHECKS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "plan": (("writing-for-agents", ("ran", "did not resolve")),),
    "code": (
        ("code-review", ("ran", "did not resolve, the Spec reviewed by hand")),
        ("writing-for-agents", ("ran", "did not resolve")),
    ),
}
NOT_NEEDED = "not needed, "

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


def usage() -> str:
    return "%s review --help" % places.command()


def run(argv: list[str]) -> int:
    return args.run_group(argv, "review", dict.fromkeys(SUBCOMMANDS, SPEC), HELP,
                          "Run the review command your skill or the last Next: line names.", dispatch)


def dispatch(sub: str, values: dict[str, Any]) -> int:
    role = values["role"]
    args.choice(role, REVIEWERS, "--role takes Plan-Reviewer or Code-Reviewer.", "Run %s for the usage." % usage())
    loop = loopfile.find(gitcmd.project_root(os.getcwd()), values["slug"])
    state = loopstate.open_loop(loop, "review %s" % sub)
    round_ = Round(loop, state, role)
    if sub == "start":
        return start(round_, values["write"])
    return check(round_, values["write"])


class Round:
    """The review round a command acts on: the next one after the last
    recorded review."""

    def __init__(self, loop: loopfile.Loop, state: loopstate.State, role: str) -> None:
        self.loop = loop
        self.state = state
        self.role = role
        self.kind = REVIEWERS[role]
        self.name = FILES[self.kind]
        self.file = os.path.join(loop.dir, self.name)
        self.relative = "%s/%s" % (loop.tracker, self.name)
        self.last = state.last_review(self.kind)
        self.number = (self.last.round + 1) if self.last else 1
        self.carried_numbers: list[int] = list(self.last.open) if self.last else []
        self.first_new = state.next_number(self.kind)
        self.carried_file = os.path.join(loop.dir, CARRIED % self.kind)

    def command(self, sub: str, write: bool = True) -> str:
        return "%s review %s --role %s --slug %s%s" % (
            places.command(), sub, self.role, self.loop.slug, " --write" if write else "")

    def minors(self) -> str:
        return self.loop.setting("Minors")[0]

    def path(self, name: str) -> str:
        return "%s/%s" % (self.loop.tracker, name)

    def read_list(self) -> list[str]:
        names = [self.name] if self.number > 1 else []
        names += ["spec.md", "issues/"]
        if self.kind == "code" and self.number == 1:
            names.append("FIXES.md")
        return [self.path(name) for name in names]

    def base(self) -> str:
        return self.loop.setting("Base branch")[0]

    def branch(self) -> str:
        return self.loop.setting("Feature branch")[0]

    def fixed_point(self) -> str:
        """code-review's fixed point: the base branch in round 1, and in a
        later code round the previous round's recorded end, so the round is
        reviewed on its own diff (ticket 90)."""
        if self.kind == "code" and self.number > 1:
            end = self.state.code_mark("end", self.number - 1)
            if end:
                return end
        return self.base()

    def review_range(self) -> str:
        return "%s...%s" % (self.fixed_point(), self.branch())

    def no_commits(self) -> bool:
        """Whether a later code round's range holds no commit."""
        if self.kind != "code" or self.number == 1:
            return False
        call = gitcmd.git(self.loop.root, "rev-list", "--count", "%s..%s" % (self.fixed_point(), self.branch()))
        return call.ok and call.out.strip() == "0"

    def agent_documents(self) -> list[str]:
        """The Agent documents in the review range, computed once."""
        if not hasattr(self, "_documents"):
            found = agentdocs.listed(self.loop.root, self.fixed_point(), self.branch())
            if found is None:
                raise Failure(
                    "git cannot read the review range %s. Nothing was written." % self.review_range(),
                    "Tell the user git cannot diff %s in this repository, and stop." % self.review_range(),
                )
            self._documents = found
        return self._documents

    def accepted_checks(self, name: str, accepted: tuple[str, ...]) -> tuple[str, ...]:
        if self.kind == "code" and name == "writing-for-agents" and not self.agent_documents():
            return accepted + (NO_AGENT_DOCUMENT,)
        return accepted

    def filled(self, name: str) -> str | None:
        """The value the tool fills a Checks line with, or None."""
        if self.kind != "code":
            return None
        if name == "writing-for-agents" and not self.agent_documents():
            return NO_AGENT_DOCUMENT
        if name == "code-review" and self.no_commits():
            return NO_COMMITS
        return None

    def skip_allowed(self, name: str) -> bool:
        """Whether the Checks line takes "not needed, <reason>": on
        writing-for-agents in any round, and on code-review from round 2
        (ticket 90): round 1 gets one full Borrowed review."""
        if name == "writing-for-agents":
            return True
        return name == "code-review" and self.number > 1

    def placeholder(self, name: str) -> str:
        """The frame's placeholder: exactly the values the line takes in this
        round."""
        values = list(dict(CHECKS[self.kind])[name])
        if self.skip_allowed(name):
            values.append(NOT_NEEDED + "<reason>")
        return "<%s>" % " | ".join(values)


# --- start ---

def planner_rung(loop: loopfile.Loop) -> int:
    """The newest round the Planner rang, or 0."""
    place = doorbells.Place(loop.root, loop.slug)
    rounds = [e.doorbell.round for e in place.entries("Orchestrator") if e.doorbell]
    return max(rounds) if rounds else 0


def require_round(round_: Round) -> None:
    if round_.last and round_.last.signed_off:
        raise Failure(
            "The %s Loop signed off in round %d: there is no round %d to review. Nothing was written."
            % (round_.kind, round_.last.round, round_.number),
            "End your turn with BLOCKED: the %s Loop is already signed off." % round_.kind,
        )
    if round_.kind == "code" and round_.state.code_mark("end", round_.number) is None:
        raise Failure(
            "The Coder's end of code round %d is not recorded: there is no code round %d to review yet. Nothing "
            "was written." % (round_.number, round_.number),
            "End your turn with BLOCKED: code round %d has no recorded Coder end." % round_.number,
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


def round_available(round_: Round) -> bool:
    try:
        require_round(round_)
    except Failure:
        return False
    return True


def carried_blocks(round_: Round) -> list[list[str]]:
    """number -> the block's lines, for every finding still open, from the
    review file as the last check left it, else from the carried file."""
    blocks: dict[int, list[str]] = {}
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


def start(round_: Round, write: bool) -> int:
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
        cannot = "Otherwise tell the user the review file cannot be written, and stop."
        textfile.write_or_refuse(round_.carried_file, carried_text + "\n" if carried_text else "",
                                 round_.relative, cannot)
        textfile.write_or_refuse(round_.file, "\n".join(skeleton(round_, blocks)) + "\n", round_.relative, cannot)
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
    if round_.kind == "code":
        out.line("Base branch: %s" % round_.base())
        out.line("Harness file: %s" % round_.loop.harness_file())
        if round_.number == 1:
            out.line("Review range: %s, with %s as code-review's fixed point and Step 2's diff." % (
                round_.review_range(), round_.base()))
        else:
            out.line("Fixed point: %s, code round %d's recorded end." % (round_.fixed_point(), round_.number - 1))
            out.line("Review range: %s, this round's own diff: code-review's fixed point is %s, and Step 2 reads "
                     "the diff over this range. The verification runs on the whole branch." % (
                         round_.review_range(), round_.fixed_point()))
            if round_.no_commits():
                out.line("No commits in this round's range, so the code-review line is filled: %s." % NO_COMMITS)
        documents = round_.agent_documents()
        if documents:
            out.line("Agent documents in the range: %s" % ", ".join(documents))
        else:
            out.line("Agent documents in the range: none, so the writing-for-agents line is filled.")
    return out.finish(
        "Review, write your findings into %s under the headings it has, then run %s. Pass --slug %s on every "
        "VDD tool call from here on." % (round_.relative, round_.command("check"), round_.loop.slug)
    )


# --- check ---

class Lint:
    """The refusals of one check, in file order."""

    def __init__(self, round_: Round) -> None:
        self.round = round_
        self.problems: list[tuple[int, list[str]]] = []

    def at(self, line: workfile.Line | None, text: str) -> None:
        if line is None:
            self.problems.append((0, ["%s: %s" % (self.round.name, text)]))
        else:
            self.problems.append((line.number, ["%s line %d: %s" % (self.round.name, line.number, text)]))

    def block(self, text: str, block_lines: list[str]) -> None:
        """A refusal followed by a block to put back, one output line per
        line of the block."""
        self.problems.append((10 ** 9, ["%s: %s" % (self.round.name, text)] + block_lines))


def sections_expected(round_: Round) -> list[str]:
    names = ["Checks"]
    if round_.number > 1:
        names.append("Open findings")
    names.append("New findings")
    if round_.kind == "code":
        names.append("Not carried")
    return names


def lint(round_: Round, parsed: workfile.Parsed) -> Lint:
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
    if parsed.unclosed is not None:
        lint_.at(parsed.unclosed, workfile.unclosed_text(parsed.unclosed))
    lint_checks(round_, parsed, lint_)
    lint_findings(round_, parsed, lint_)
    if round_.kind == "code":
        lint_kept_open(round_, parsed, lint_)
        not_carried(parsed, lint_)
    return lint_


def lint_kept_open(round_: Round, parsed: workfile.Parsed, lint_: Lint) -> None:
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


def not_carried(parsed: workfile.Parsed, lint_: Lint | None) -> list[tuple[str, list[int]]]:
    """The Not carried lines, a wrapped line joined: [(text, [line numbers])].
    A line that is neither a "- " line nor an indented continuation, and a
    "- " line with nothing after it, are refused when lint_ is given."""
    section = parsed.section("Not carried")
    items: list[tuple[str, list[int]]] = []
    if section is None:
        return items
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
        elif lint_ is not None:
            lint_.at(line, "under ## Not carried every line starts with \"- \": \"- <the problem, in one line>: "
                     "<why not>\". A wrapped line goes on an indented next line.")
    if lint_ is not None:
        for (text, _), line in zip(items, firsts):
            if not text:
                lint_.at(line, "this Not carried line is empty. Write \"- <the problem, in one line>: <why not>\", "
                         "or remove it.")
    return items


def lint_checks(round_: Round, parsed: workfile.Parsed, lint_: Lint) -> None:
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


def lint_findings(round_: Round, parsed: workfile.Parsed, lint_: Lint) -> None:
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


def outcome(
    round_: Round, parsed: workfile.Parsed,
) -> tuple[list[workfile.Block], list[workfile.Block], tuple[int, ...], bool]:
    """(open blocks, closed blocks, counts, signed off)."""
    findings = [b for b in parsed.blocks if b.match is not None]
    open_blocks = [b for b in findings if b.state == "open"]
    closed = [b for b in findings if b.state in ("fixed", "accepted")]
    counts = tuple(sum(1 for b in open_blocks if b.severity == s) for s in loopstate.SEVERITIES)
    signed_off = counts[0] == 0 and counts[1] == 0 and (counts[2] == 0 or round_.minors() == "leave")
    return open_blocks, closed, counts, signed_off


def status_line(counts: tuple[int, ...], signed_off: bool) -> str:
    if signed_off and counts[2]:
        return "SIGNED OFF. Open minors left, as Minors: leave allows: %d." % counts[2]
    if signed_off:
        return "SIGNED OFF. Nothing open."
    return "Open: %d blocker, %d major, %d minor." % counts


def checks_text(round_: Round, parsed: workfile.Parsed) -> str:
    section = parsed.section("Checks")
    if section is None:
        return ""
    found = []
    for line in section.body:
        if line.frame and ":" in line.text:
            name, _, value = line.text.partition(":")
            if name.strip() in dict(CHECKS[round_.kind]):
                found.append("%s %s" % (name.strip(), value.strip()))
    return "; ".join(found)


def cleaned(
    parsed: workfile.Parsed, status: str, closed: list[workfile.Block], dropped: Iterable[int] = (),
) -> list[str]:
    """The review file after a passing check: no guidance comment, the status
    line under the title, no closed finding and none of the dropped lines."""
    drop = set(dropped)
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


def recap_findings(round_: Round, closed: list[workfile.Block]) -> list[str]:
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


def recap_not_carried(round_: Round, items: list[tuple[str, list[int]]]) -> list[str]:
    """Each Not carried line with its round in front."""
    return ["- Code round %d: %s" % (round_.number, text) for text, _ in items]


def check(round_: Round, write: bool) -> int:
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
    numbers = sorted(b.number for b in open_blocks if b.number is not None)
    next_number = max([round_.first_new - 1] + [b.number for b in parsed.blocks if b.number is not None]) + 1
    line = loopstate.reviewed_line(round_.kind, round_.number, signed_off, numbers, counts, next_number, new,
                                   len(closed), checks_text(round_, parsed))
    round_.state.lines.append(line)
    review = round_.state.reviews(round_.kind)[round_.number]
    section = "Plan findings" if round_.kind == "plan" else "Code findings"
    items = not_carried(parsed, None) if round_.kind == "code" else []
    dropped = [number for _, numbers in items for number in numbers]
    textfile.write_or_refuse(round_.file, "\n".join(cleaned(parsed, status, closed, dropped)) + "\n",
                             round_.relative, "Otherwise tell the user the review file cannot be written, and stop.")
    recap.write(round_.loop, round_.state, {section: recap_findings(round_, closed),
                                            "Not carried": recap_not_carried(round_, items)})
    round_.state.persist(line)
    out.line("%s: round %d checked and written." % (round_.name, round_.number))
    out.line(status)
    if closed:
        out.line("Moved to %s: finding%s %s." % (
            round_.path(recap.NAME), "" if len(closed) == 1 else "s",
            workfile.join_numbers([b.number for b in closed if b.number is not None])))
    if items:
        out.line("Moved to %s: %d Not carried line%s." % (
            round_.path(recap.NAME), len(items), "" if len(items) == 1 else "s"))
    out.line(loopstate.review_doorbell(review))
    return out.finish("End your turn with the Doorbell line above as your whole reply.")


def already_recorded(round_: Round, review: loopstate.Review) -> int:
    out = Output()
    out.line("Round %d of the %s review is already recorded. Nothing was written." % (review.round, round_.kind))
    out.line(loopstate.review_doorbell(review))
    return out.finish("End your turn with the Doorbell line above as your whole reply.")
