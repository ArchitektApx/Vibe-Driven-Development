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
from typing import Iterable

from .. import catalog, doorbells, gitcmd, loopfile, loopstate, runner, textfile, workfile
from ..loopstate import recap, records
from ..out import Failure, and_list
from .frame import start
from .lint import lint, not_carried
from .rounds import CHECKS, LABELS, STATUS_LINE, TITLES, Round, require_round, round_available, status_line

HELP = catalog.Help({
    "start": [
        "review start --role <Plan-Reviewer|Code-Reviewer> --slug <slug> --write",
        "  The reviewer's first call each round. Writes the round's frame of PLAN-REVIEW.md or CODEREVIEW.md:",
        "  the title, a guidance comment, ## Checks, ## Open findings with every still-open finding carried",
        "  whole (round 2 on), ## New findings and, for the Code-Reviewer, ## Not carried. Prints the round, the",
        "  carried findings, the number new findings start at, the files to read and the Minors: line. A second",
        "  start in a round already started writes nothing and prints the same again, naming the new findings",
        "  the file already holds and the number the next one takes.",
    ],
    "check": [
        "review check --role <Plan-Reviewer|Code-Reviewer> --slug <slug> [--write]",
        "  Lint the review file against its frame: every refusal names the line and the fix and writes nothing.",
        "  With --write on a passing file it removes the guidance comments, writes the status line under the",
        "  title, moves every closed finding to .scratch/<slug>/RECAP.md, records the round in the state file",
        "  and prints the Doorbell line to end your turn with.",
    ],
    "add": [
        "review add --slug <slug> --from <file> [--write]",
        "  For the user, not a Role: sends the user's findings back into a signed-off code Loop.",
        "  The file holds only findings, unnumbered, each a heading and a body:",
        "",
        "      ### major: src/app.py:12",
        "",
        "      What is wrong, and the fix.",
        "",
        "  Severity is blocker, major or minor. Refused unless the code Loop is signed off; a second add before",
        "  the Coder starts joins the first. Without --write it shows the result; with --write it reopens the",
        "  loop. Then tell the Orchestrator to run orchestrator start.",
    ]},
    [
        "--slug names the loop; pass it on every call.",
    ])

def run(argv: list[str]) -> int:
    return catalog.run("review", argv, HELP,
                       "Run the review command above that your step needs, or the one the last Next: line names.",
                       dispatch)


def dispatch(ctx: catalog.Context) -> int:
    sub, values = ctx.command, ctx.values
    if sub == "add":
        from . import add
        found = loopfile.find(gitcmd.project_root(os.getcwd()), values["slug"])
        return runner.run(ctx, lambda: add.plan(found, values["from"]))
    role = values["role"]
    loop = loopfile.find(gitcmd.project_root(os.getcwd()), values["slug"])
    state = runner.open_loop(loop, "review %s" % sub)
    round_ = Round(loop, state, role)
    if sub == "start":
        return runner.run(ctx, lambda: start(round_))
    return runner.run(ctx, lambda: check(round_, values["write"]))


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
    raised = round_.state.user_raised()
    for block in closed:
        if lines:
            lines.append("")
        if block.number in raised:
            lines.append("### %d. %s, raised by the user after round %d, %s in round %d: %s" % (
                block.number, block.severity, raised[block.number], block.state, round_.number, block.reference))
        else:
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


def check(round_: Round, write: bool) -> runner.Plan:
    """The round's outcome as a plan: the review file linted, then the
    closed findings moved to the Recap, the round recorded and the review
    file rewritten with its status line."""
    if not round_.state.review_started(round_.kind, round_.number):
        if round_.last and not round_available(round_):
            if round_.last.user:
                # The user's entry is not this reviewer's round: its counts
                # are never answered as the reviewer's own.
                require_round(round_)
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
    lint(round_, parsed).refuse("Fix the lines above, then run %s again." % round_.command("check", write))
    open_blocks, closed, counts, signed_off = outcome(round_, parsed)
    status = status_line(counts, signed_off)
    new = sum(1 for b in parsed.blocks_in("New findings") if b.match is not None)
    store = records.Records.load(round_.loop)
    numbers = sorted(b.number for b in open_blocks if b.number is not None)
    next_number = max([round_.first_new - 1] + [b.number for b in parsed.blocks if b.number is not None]) + 1
    line = loopstate.reviewed_line(round_.kind, round_.number, signed_off, numbers, counts, next_number, new,
                                   len(closed), checks_text(round_, parsed))
    section = "Plan findings" if round_.kind == "plan" else "Code findings"
    items = not_carried(parsed) if round_.kind == "code" else []
    dropped = [number for _, numbers in items for number in numbers]
    rewritten = "\n".join(cleaned(parsed, status, closed, dropped)) + "\n"
    found = [records.Record(records.findings_key(round_.kind, round_.number), section, recap_findings(round_, closed))]
    if round_.kind == "code":
        found.append(records.Record(records.not_carried_key(round_.number), "Not carried",
                                    recap_not_carried(round_, items)))
    dry = ["%s passes: round %d, %d new finding%s, %d closed." % (
        round_.name, round_.number, new, "" if new == 1 else "s", len(closed)), status]
    done = ["%s: round %d checked and written." % (round_.name, round_.number), status]
    if closed:
        done.append("Moved to %s: finding%s %s." % (
            round_.path(recap.NAME), "" if len(closed) == 1 else "s",
            and_list(map(str, [b.number for b in closed if b.number is not None]))))
    if items:
        done.append("Moved to %s: %d Not carried line%s." % (
            round_.path(recap.NAME), len(items), "" if len(items) == 1 else "s"))
    effects = runner.record_step(store, round_.state, found, [line], dry=dry, done=done)
    effects.append(rewrite(round_, rewritten))
    # The Doorbell line reads the round as the state file now records it.
    effects.append(runner.Step(lambda: [doorbells.review_doorbell(round_.state.reviews(round_.kind)[round_.number])],
                               after=True))
    return runner.Plan(effects, END, dry_next="Run %s" % round_.command("check"))


END = "End your turn with the Doorbell line above as your whole reply."
RECORDED = ("Otherwise tell the user the round is recorded and the review file cannot be written; once it can be, "
            "the same command run again writes it. Then stop.")


def rewrite(round_: Round, text: str) -> runner.WriteFile:
    """The review file rewritten, after the commit point."""
    return runner.WriteFile(round_.file, text, round_.relative, RECORDED, after=True)


def rewrite_recorded(round_: Round, review: loopstate.Review) -> bool:
    """The review file again for a recorded round, as the round's check
    left it, computed from the file as it is. Whether it wrote."""
    text = textfile.read(round_.file)
    if text is None:
        return False
    recorded = Round(round_.loop, round_.state, round_.role, review.round)
    parsed = workfile.Parsed(text)
    if parsed.title is None or parsed.title.text.strip() != "# %s, round %d" % (TITLES[round_.kind], review.round):
        return False
    _, closed, _, _ = outcome(recorded, parsed)
    items = not_carried(parsed) if round_.kind == "code" else []
    dropped = [number for _, numbers in items for number in numbers]
    rewritten = "\n".join(cleaned(parsed, status_line(review.counts, review.signed_off), closed, dropped)) + "\n"
    if rewritten == text:
        return False
    rewrite(round_, rewritten).apply()
    return True


def already_recorded(round_: Round, review: loopstate.Review) -> runner.Plan:
    """A rerun after the commit point: RECAP.md and the review file written
    again where a failure left them behind, the round not recorded twice."""
    store = records.Records.load(round_.loop)
    doorbell = doorbells.review_doorbell(review)
    nothing = ["Round %d of the %s review is already recorded. Nothing was written." % (review.round, round_.kind),
               doorbell]

    def finish() -> list[str]:
        written = []
        if recap.render_recap(round_.loop, round_.state, store):
            written.append(round_.path(recap.NAME))
        if rewrite_recorded(round_, review):
            written.append(round_.relative)
        if not written:
            return nothing
        return ["Round %d of the %s review is already recorded. Wrote %s again." % (
            review.round, round_.kind, " and ".join(written)), doorbell]

    return runner.Plan([runner.Step(finish, dry=nothing)], END, dry_next=END)
