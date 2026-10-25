"""The brainstorm command group: the Brainstormer's idea store.

Every move the user asks for is one command. A write needs --write; without
it the command runs as a dry run and prints what it would write. The tool
writes frontmatter, History and every structural line; the model passes
short prose as arguments and rewrites a section with its Harness's Read and
Edit. Idea text is quoted behind "  > ", so a line of an idea that reads like
Next: is never taken for the tool's own.
"""

from __future__ import annotations

import os
import re
from typing import Any, Callable, Dict

from .. import catalog, gitcmd
from ..out import Failure, Output
from . import cleanup, layout1, migrate, moves, printed, reads, restructure, runner
from .migrate import require_layout
from .runner import Move
from .store import Store, layout

# The first sentence of the overview's Next: step.
ANSWER = "Answer the user's message from this overview; read or run nothing else unless it needs more."

HELP = catalog.Help({
    "start": [
        "brainstorm start [--page <n>]",
        "  The Session's first call: the open ideas, each part under its parent, with status, importance/size/fog,",
        "  last update, what each waits on, and the tldr. A large store is paged, most recently updated families",
        "  first; --page shows the next.",
    ],
    "show": [
        "brainstorm show --idea <slug>",
        "  One idea and its family at every level: status, Decision, open Next Steps and open questions of every",
        "  open member, what it waits on and what waits on it, and the file's path.",
    ],
    "find": [
        "brainstorm find --text <words> [--text <words> ...]",
        "  Every idea, open, closed or removed, whose text holds any of the words; the matching lines.",
    ],
    "check": [
        "brainstorm check",
        "  The store's problems: links that do not resolve, relations to no idea, parents missing, looping or too",
        "  deep, a leftover index.md, an idea file without History.",
    ],
    "new": [
        "brainstorm new --slug <slug> --title <title> --tldr <one sentence> [--parent <slug>] [--summary <text>]",
        "    [--importance|--size|--fog <xsmall..xlarge|unknown>] [--relate '<kind> <slug>: <why>' ...]",
        "    [--despite <slug> ...]",
        "  Captures an idea: its file with frontmatter, title, Summary and a created History line. Without --write",
        "  it lists the ideas, open, closed or removed, that look like the same one, to ask the user about before",
        "  capturing; --despite <slug> leaves one out of that list. A --summary starts \"Goal: <the goal>.\" (the",
        "  user's goal), then what they said.",
    ],
    "note": [
        "brainstorm note --idea <slug> (--section <name> --text <text> [--text ...] | --tick <step>)",
        "  Adds prose to a section (Evidence, Summary, Proposal, Pro, Con, Open Questions, Prior Art, Next Steps,",
        "  Related Ideas as '<kind> <slug>: <why>'); Evidence items are dated, Next Steps become open steps.",
        "  --tick ticks the open Next Step that starts with <step>. To rewrite a section, Read the file and Edit",
        "  only that section in place.",
    ],
    "set": [
        "brainstorm set --idea <slug> [--idea ...] [--status <s>] [--decision <text>] [--reopen-when <text>]",
        "    [--importance|--size|--fog <m>] [--tldr <text>] [--title <text>]",
        "  Status idea, discussed, shaped, decided, in-progress, done or dropped. done, dropped and decided need",
        "  --decision, dropped also --reopen-when; dropping an idea drops its open parts at every level; an open",
        "  status on a closed idea reopens it.",
    ],
    "move": [
        "brainstorm move --set <part>=<parent>|top [--set ...]",
        "  Files a part under a parent, or back at the top level.",
    ],
    "split": [
        "brainstorm split --idea <slug> --part '<slug> | <title> | <tldr>' [--part ...]",
        "  New parts under the idea, which stays their parent.",
    ],
    "merge": [
        "brainstorm merge --idea <slug> --into <slug> --reason <text> --reopen-when <text>",
        "  Drops the first idea into the second, which takes its open Next Steps. An idea with an open part, at any",
        "  level, cannot merge; its closed parts stay under it.",
    ],
    "rename": [
        "brainstorm rename --idea <slug> --to <slug>",
        "  New slug for an idea and its research folder; relation lines, parent fields, links, research paths and",
        "  slug code spans follow. Prose and History are never rewritten; prose that still names the old slug is",
        "  listed.",
    ],
    "cleanup": [
        "brainstorm cleanup (--status done|dropped [--status ...] | --idea <slug> [--idea ...]) [--older <N>d|<N>w]",
        "  Removes closed ideas, each kept as one line in removed.md; --older counts from the day the idea closed.",
        "  Never removes an open idea, a closed idea with an open part, a closed idea an open idea waits on, or a",
        "  part whose family stays. Research folders stay.",
    ],
    "migrate": [
        "brainstorm migrate [--event '<date> <slug> split into|merged into|folded into|renamed from <slug>' ...]",
        "  Converts a 0.15 store (index.md) to one file per idea with History, keeping the old store as",
        "  .scratch/_brainstorming.pre-0.16/; moves a 0.16 beta store's dates into its files; finishes an",
        "  interrupted migration; writes back a lost .layout marker.",
        "  Without --write it prints the plan and the Log sentences each --event may carry.",
    ]},
    [
        "Every write needs --write; without it the command is a dry run. A line starting \"  > \" quotes an idea's own "
        "text.",
    ], apart=False)

WRITES: dict[str, Move] = {"new": moves.new, "note": moves.note, "set": moves.set_cmd, "move": restructure.move,
                           "split": restructure.split, "merge": restructure.merge, "rename": restructure.rename,
                           "cleanup": cleanup.cleanup}
Read = Callable[[Store, Dict[str, Any], Output], int]
READS: dict[str, Read] = {"show": reads.show, "find": reads.find, "check": reads.check}


def run(argv: list[str]) -> int:
    return catalog.run("brainstorm", argv, HELP, "Run the brainstorm command above that fits what the user said.",
                       dispatch)


def dispatch(ctx: catalog.Context) -> int:
    command, values = ctx.command, ctx.values
    root = gitcmd.project_root(os.getcwd())
    if command == "start":
        return start(root, values)
    if command == "migrate":
        return migrate_cmd(root, values)
    runner.guard(root, command, values)
    if command in WRITES:
        return runner.write(root, command, WRITES[command], values)
    out = Output()
    for line in runner.recover_quietly(root):
        out.line(line)
    store = Store(root)
    return READS[command](store, values, out)


def page_number(value: str | None) -> int:
    if value is None:
        return 1
    if not re.fullmatch(r"[0-9]+", value.strip()):
        raise Failure("--page %s is not a number. Nothing was read." % value,
                      "Run %s." % printed.command("start", page="<n>"))
    return int(value.strip())


def start(root: str, values: dict[str, Any]) -> int:
    found = layout(root)
    out = Output()
    if migrate.STEPS["1"].half(root):
        out.line("A migration was interrupted after the backup: %s/ is complete and %s/ waits beside it; %s "
                 "finishes it." % (layout1.BACKUP, layout1.STAGING, printed.MIGRATE))
        return out.finish("Run %s, then %s again." % (printed.MIGRATE, printed.START))
    if found is None:
        out.line("This project has no idea store yet (.scratch/_brainstorming/).")
        return out.finish("Answer the user's message; when they bring an idea, capture it with brainstorm new, "
                          "which creates the store.")
    if found in migrate.STEPS:
        for line in migrate.plan_lines(root):
            out.line(line)
        return out.finish(migrate.plan_next(root))
    if found in ("lost", "damaged"):
        out.line("The idea store's .layout marker is %s." % ("missing" if found == "lost" else "empty"))
        return out.finish("Run %s: it checks the store and writes the marker back. Then run %s again."
                          % (printed.MIGRATE, printed.START))
    require_layout(root)
    for line in runner.recover_quietly(root):
        out.line(line)
    store = Store(root)
    lines, offer = overview(root, store, page_number(values["page"]))
    for line in lines:
        out.line(line)
    return out.finish(ANSWER + offer)


def overview(root: str, store: Store, page: int = 1) -> tuple[list[str], str]:
    """The overview's lines with the backup line and the parts named only in
    a tldr, and the text its Next: step adds after its first sentence."""
    named, offer = parts_named(store)
    lines = reads.overview(store, page) + named
    if os.path.isdir(os.path.join(root, layout1.BACKUP)):
        lines.append("Backup of the 0.15 store: %s/ (the tool never deletes it)." % layout1.BACKUP)
    return lines, offer


def parts_named(store: Store) -> tuple[list[str], str]:
    """The line naming the parts filed only in a tldr, and the offer it adds
    to a Next: step; nothing when there are none."""
    named = reads.parts_named(store)
    if not named:
        return [], ""
    return (["Named as a part in their tldr but not filed under that parent: %s."
             % ", ".join("%s (%s)" % pair for pair in named)],
            " Offer once to file the parts named above under their parents (brainstorm move).")


def migrate_cmd(root: str, values: dict[str, Any]) -> int:
    lines, what, would = migrate.migrate(root, values["event"], values["write"])
    out = Output()
    if what in ("dry", "dry-half", "dry-repair"):
        out.line("Dry run, nothing was written. With --write, brainstorm migrate would write %s:" % ", ".join(would))
    for line in lines:
        out.line(line)
    if what == "dry":
        return out.finish(migrate.plan_next(root))
    if what in ("dry-half", "dry-repair"):
        return out.finish("If the user agrees, run %s." % printed.MIGRATE)
    if what == "noop":
        return out.finish("Run %s." % printed.START)
    named, offer = parts_named(Store(root))
    for line in named:
        out.line(line)
    return out.finish("Tell the user the migration is done, then answer their message, running %s first if it "
                      "needs the store's overview." % printed.START + offer)
