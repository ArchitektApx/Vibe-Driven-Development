"""The coder command group: the Coder's round, framed and checked by the
tool.

coder start checks the round's precondition, puts the Coder on the feature
branch, records where the round starts and writes the round's frame of
FIXES.md. coder check lints FIXES.md and the working tree and, with --write,
records where the round ends and prints the Coder's Doorbell line.
"""

from __future__ import annotations

import os

from .. import catalog, doorbells, fixes, gitcmd, loopfile, loopstate, runner, textfile, workfile
from ..loopstate import recap, records
from ..out import Failure
from .branch import dirty, head, new_untracked, start_gone
from .frame import start
from .lint import lint
from .rounds import Round

END = "End your turn with the Doorbell line above as your whole reply."

HELP = catalog.Help({
    "start": [
        "coder start --slug <slug> --write",
        "  The Coder's first call each round. Refuses unless the plan Loop is signed off (round 1) or the last",
        "  code round's review left findings open (a later round). On the base branch it switches to the feature",
        "  branch, creating it from the base when it does not exist; on the feature branch it stays; on any other",
        "  branch it refuses. It records and prints \"Round <n> starts at <sha>.\", records the untracked files",
        "  already there and writes the round's frame of FIXES.md: one entry per Ticket in round 1, one per open",
        "  finding later. A second start in a round already started writes nothing and prints the same again.",
    ],
    "check": [
        "coder check --slug <slug> [--write]",
        "  Lint FIXES.md against its frame, and refuse uncommitted changes to tracked files, a file left untracked",
        "  since coder start, and a round whose recorded start is gone from the branch's history (an earlier",
        "  commit amended, rebased or reset): every refusal names the line or file and the fix and writes",
        "  nothing. With --write on a passing round it removes the guidance comment, records the branch tip as",
        "  the round's end, copies round 1's Ticket entries to .scratch/<slug>/RECAP.md and prints the Doorbell",
        "  line to end your turn with.",
    ]},
    [
        "--slug names the loop; pass it on every call.",
    ])

def run(argv: list[str]) -> int:
    return catalog.run("coder", argv, HELP, "Run the coder command your skill or the last Next: line names.", dispatch)


def dispatch(ctx: catalog.Context) -> int:
    sub, values = ctx.command, ctx.values
    loop = loopfile.find(gitcmd.project_root(os.getcwd()), values["slug"])
    state = runner.open_loop(loop, "coder %s" % sub)
    round_ = Round(loop, state)
    if sub == "start":
        return runner.run(ctx, lambda: start(round_))
    return runner.run(ctx, lambda: check(round_, values["write"]))


def check(round_: Round, write: bool) -> runner.Plan:
    """The round's end as a plan: FIXES.md linted, then the round's end and
    round 1's Tickets recorded and FIXES.md rewritten without its guidance."""
    if not round_.started:
        if round_.newest and round_.state.review("code", round_.newest) is None:
            return already_recorded(round_)
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
    store = records.Records.load(round_.loop)
    tip = head(root)
    cleaned = cleaned_text(parsed)
    found = []
    if round_.number == 1:
        found.append(records.Record(records.TICKETS_KEY, "Tickets", recap_tickets(workfile.Parsed(cleaned))))
    done = ["%s: round %d checked and written." % (fixes.NAME, round_.number),
            "Round %d ends at %s." % (round_.number, tip)]
    if round_.number == 1:
        done.append("Copied the Ticket entries to %s." % round_.path(recap.NAME))
    done.append(doorbells.coder_doorbell(round_.number))
    effects = runner.record_step(store, round_.state, found, [loopstate.code_mark_line("end", round_.number, tip)],
                                 dry=["%s passes: round %d." % (fixes.NAME, round_.number)], done=done)
    effects.append(rewrite(round_, cleaned))
    return runner.Plan(effects, END, dry_next="Run %s" % round_.command("check"))


def cleaned_text(parsed: workfile.Parsed) -> str:
    """FIXES.md after a passing check: no guidance comment. Computed from its
    own result it gives the same text."""
    return "\n".join(workfile.squeeze(workfile.without_guides(parsed.texts))) + "\n"


def rewrite(round_: Round, text: str) -> runner.WriteFile:
    """FIXES.md rewritten, after the commit point."""
    return runner.WriteFile(round_.file, text, round_.relative, RECORDED, after=True)


RECORDED = ("Otherwise tell the user the round is recorded and FIXES.md cannot be written; once it can be, the "
            "same command run again writes it. Then stop.")


def already_recorded(round_: Round) -> runner.Plan:
    """A rerun after the commit point: RECAP.md and FIXES.md written again
    where a failure left them behind, the round not recorded twice."""
    store = records.Records.load(round_.loop)
    doorbell = doorbells.coder_doorbell(round_.newest)

    def finish() -> list[str]:
        written = []
        if recap.render_recap(round_.loop, round_.state, store):
            written.append(round_.path(recap.NAME))
        text = textfile.read(round_.file)
        parsed = workfile.Parsed(text) if text is not None else None
        title = parsed.title if parsed is not None else None
        if parsed is not None and title is not None and title.text.strip() == "# Fixes, round %d" % round_.newest:
            cleaned = cleaned_text(parsed)
            if cleaned != text:
                rewrite(round_, cleaned).apply()
                written.append(round_.relative)
        if not written:
            return nothing
        return ["Round %d's end is already recorded. Wrote %s again." % (round_.newest, " and ".join(written)),
                doorbell]

    nothing = ["Round %d's end is already recorded. Nothing was written." % round_.newest, doorbell]
    return runner.Plan([runner.Step(finish, dry=nothing)], END, dry_next=END)


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
