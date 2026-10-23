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
from typing import Any, Callable, Dict, List, Tuple

from .. import args, gitcmd, places, textfile
from ..out import TELL, Failure, Output
from . import cleanup, journal, layout1, migrate, moves, reads, restructure
from .lock import Lock
from .migrate import require_layout
from .store import LAYOUT, LAYOUT_FILE, Store, layout, store_dir

V, W, L = args.VALUE, args.FLAG, args.LIST
METRIC_OPTIONS = {"importance": V, "size": V, "fog": V}
# The first sentence of the overview's Next: step.
ANSWER = "Answer the user's message from this overview; read or run nothing else unless it needs more."

# One option table per command: an option another command takes is refused
# on this one, never silently ignored.
SPECS: dict[str, dict[str, str]] = {
    "start": {"page": V},
    "show": {"idea": V},
    "find": {"text": L},
    "check": {},
    "new": dict({"slug": V, "title": V, "tldr": V, "parent": V, "summary": V, "relate": L, "despite": L, "write": W},
                **METRIC_OPTIONS),
    "note": {"idea": V, "section": V, "text": L, "tick": V, "write": W},
    "set": dict({"idea": L, "status": V, "decision": V, "reopen-when": V, "tldr": V, "title": V, "write": W},
                **METRIC_OPTIONS),
    "move": {"set": L, "write": W},
    "split": {"idea": V, "part": L, "write": W},
    "merge": {"idea": V, "into": V, "reason": V, "reopen-when": V, "write": W},
    "rename": {"idea": V, "to": V, "write": W},
    "cleanup": {"status": L, "idea": L, "older": V, "write": W},
    "migrate": {"event": L, "write": W},
}
REQUIRED = {
    "show": ["idea"],
    "find": ["text"],
    "new": ["slug", "title", "tldr"],
    "note": ["idea"],
    "set": ["idea"],
    "move": ["set"],
    "split": ["idea", "part"],
    "merge": ["idea", "into", "reason", "reopen-when"],
    "rename": ["idea", "to"],
}

HELP = [
    "brainstorm start [--page <n>]",
    "  The Session's first call: the open ideas, each part under its parent, with status, importance/size/fog,",
    "  last update, what each waits on, and the tldr. A large store is paged, the most recently updated",
    "  families first; --page shows the next page.",
    "brainstorm show --idea <slug>",
    "  One idea and its family at every level: status, Decision, open Next Steps and open questions of every",
    "  open member, what it waits on and what waits on it, and the file's path.",
    "brainstorm find --text <words> [--text <words> ...]",
    "  Every idea, open, closed or removed, whose text holds any of the words; the matching lines.",
    "brainstorm check",
    "  The store's problems: links that do not resolve, relations to no idea, parents missing, looping or too",
    "  deep, a leftover index.md, an idea file without History.",
    "brainstorm new --slug <slug> --title <title> --tldr <one sentence> [--parent <slug>] [--summary <text>]",
    "    [--importance|--size|--fog <xsmall..xlarge|unknown>] [--relate '<kind> <slug>: <why>' ...]",
    "    [--despite <slug> ...]",
    "  Captures an idea: its file with frontmatter, title, Summary and a created History line. Without --write",
    "  it lists the ideas, open, closed or removed, that look like the same one, to ask the user about before",
    "  capturing; --despite <slug> leaves one out of that list.",
    "brainstorm note --idea <slug> (--section <name> --text <text> [--text ...] | --tick <step>)",
    "  Adds prose to a section (Evidence items are dated, Next Steps become open steps), or ticks the open",
    "  Next Step that starts with --tick. To rewrite a section, Read the file and Edit only that section in place.",
    "brainstorm set --idea <slug> [--idea ...] [--status <s>] [--decision <text>] [--reopen-when <text>]",
    "    [--importance|--size|--fog <m>] [--tldr <text>] [--title <text>]",
    "  Status idea, discussed, shaped, decided, in-progress, done or dropped. done, dropped and decided need",
    "  --decision, dropped also --reopen-when; dropping an idea drops its open parts at every level; an open",
    "  status on a closed idea reopens it.",
    "brainstorm move --set <part>=<parent>|top [--set ...]",
    "  Files a part under a parent, or back at the top level.",
    "brainstorm split --idea <slug> --part '<slug> | <title> | <tldr>' [--part ...]",
    "  New parts under the idea, which stays their parent.",
    "brainstorm merge --idea <slug> --into <slug> --reason <text> --reopen-when <text>",
    "  Drops the first idea into the second, which takes its open Next Steps. An idea with an open part, at any",
    "  level, cannot merge; its closed parts stay under it.",
    "brainstorm rename --idea <slug> --to <slug>",
    "  New slug for an idea and its research folder; relation lines, parent fields, links, research paths and",
    "  slug code spans follow. Prose and History are never rewritten; prose that still names the old slug is",
    "  listed.",
    "brainstorm cleanup (--status done|dropped [--status ...] | --idea <slug> [--idea ...]) [--older <N>d|<N>w]",
    "  Removes closed ideas from the store, each kept as one line in removed.md; --older counts from the day",
    "  the idea closed. Never removes an open idea, a closed idea with an open part, a closed idea an open",
    "  idea waits on, or a part whose family stays. Research folders stay.",
    "brainstorm migrate [--event '<date> <slug> split into|merged into|folded into|renamed from <slug>' ...]",
    "  Converts a 0.15 store (index.md) to one file per idea with History, keeping the old store as",
    "  .scratch/_brainstorming.pre-0.16/; moves a 0.16 beta store's dates into its files; finishes an",
    "  interrupted migration; writes back a lost .layout marker.",
    "  Without --write it prints the plan and the Log sentences each --event may carry.",
    "",
    "Run every command from the repository root. Every write needs --write; without it the command is a dry run.",
]

Move = Callable[[Store, Dict[str, Any]], Tuple[List[str], str, str]]
WRITES: dict[str, Move] = {"new": moves.new, "note": moves.note, "set": moves.set_cmd, "move": restructure.move,
                           "split": restructure.split, "merge": restructure.merge, "rename": restructure.rename,
                           "cleanup": cleanup.cleanup}
Read = Callable[[Store, Dict[str, Any], Output], int]
READS: dict[str, Read] = {"show": reads.show, "find": reads.find, "check": reads.check}


def usage() -> str:
    return "%s brainstorm --help" % places.command()


def run(argv: list[str]) -> int:
    return args.run_group(argv, "brainstorm", SPECS, HELP, "Run the brainstorm command your skill names.", dispatch)


def dispatch(command: str, values: dict[str, Any]) -> int:
    args.require(values, REQUIRED.get(command, []), usage())
    root = gitcmd.project_root(os.getcwd())
    if command == "start":
        return start(root, values)
    if command == "migrate":
        return migrate_cmd(root, values)
    if migrate.STEPS["1"].half(root):
        # Between the migration's two renames there is no store: a new one
        # here would leave two half stores (F2).
        raise Failure("A migration was interrupted after the backup; the idea store is not in place yet. Nothing was "
                      "written.", "Run brainstorm migrate --write, then brainstorm start.")
    found = layout(root)
    if command == "new" and found is None:
        if values["write"]:
            # The first idea creates the store, but only once the command
            # checks out: a refused new leaves no store behind (M16).
            moves.new(Store(root), values)
            os.makedirs(store_dir(root), exist_ok=True)
            textfile.write(os.path.join(store_dir(root), LAYOUT_FILE), (LAYOUT + "\n").encode("ascii"))
    else:
        require_layout(root)
    if command in WRITES:
        return write(root, command, values)
    out = Output()
    for line in recover_quietly(root):
        out.line(line)
    store = Store(root)
    return READS[command](store, values, out)


def recover_quietly(root: str) -> list[str]:
    """Before a read: settle a write a killed run left half done, when no
    live writer holds the lock. A read never waits for the lock."""
    if not journal.pending(root):
        return []
    with Lock(root, wait=False, on_take=journal.recover) as lock:
        return lock.lines


def write(root: str, command: str, values: dict[str, Any]) -> int:
    handler = WRITES[command]
    out = Output()
    if not values["write"]:
        store = Store(root)
        lines, _, _ = handler(store, values)
        would = store.planned()
        out.line("Dry run, nothing was written. With --write, brainstorm %s would write %s:"
                 % (command, ", ".join(would) or "nothing"))
        for line in lines + loop_lines(store):
            out.line(line)
        return out.finish(store.dry_next or "If this is what the user asked for, run the same command again with "
                          "--write.")
    # The lock is taken before the store is read, so no update is lost;
    # inside it, a write a killed run left half done is settled first.
    with Lock(root, on_take=journal.recover) as lock:
        store = Store(root)
        lines, nxt, label = handler(store, values)
        lines += loop_lines(store)
        journal.save(store, label)
    for line in lock.lines:
        out.line(line)
    for line in lines:
        out.line(line)
    return out.finish(nxt)


def loop_lines(store: Store) -> list[str]:
    """A parent loop written by hand among the ideas the command writes:
    named, with the move that breaks it."""
    lines: list[str] = []
    seen: set[str] = set()
    for slug in store.existing_loops():
        if slug in seen:
            continue
        chain = [slug] + store.ancestors(slug)
        seen.update(chain)
        lines.append("%s sit in a parent loop written by hand, left as it is: %s -> %s. To break it, file one at the "
                     "top level: brainstorm move --set %s=top --write" % (" and ".join(sorted(chain)),
                                                                          " -> ".join(chain), slug, slug))
    return lines


def page_number(value: str | None) -> int:
    if value is None:
        return 1
    if not value.strip().isdigit():
        raise Failure("--page %s is not a number. Nothing was read." % value, "Run brainstorm start --page <n>.")
    return int(value.strip())


def start(root: str, values: dict[str, Any]) -> int:
    found = layout(root)
    out = Output()
    if migrate.STEPS["1"].half(root):
        out.line("A migration was interrupted after the backup: %s/ is complete and %s/ waits beside it; brainstorm "
                 "migrate --write finishes it." % (layout1.BACKUP, layout1.STAGING))
        return out.finish("Run brainstorm migrate --write, then brainstorm start again.")
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
        return out.finish("Run brainstorm migrate --write: it checks the store and writes the marker back. Then "
                          "run brainstorm start again.")
    require_layout(root)
    for line in recover_quietly(root):
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


def told(lines: list[str]) -> int:
    """How many of lines are Tell lines."""
    return sum(1 for line in lines if line.startswith(TELL.split('"')[0]))


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
        return out.finish("If the user agrees, run brainstorm migrate --write.")
    if what == "noop":
        tells = told(lines)
        return out.finish("Relay the Tell line%s above to the user, then run brainstorm start."
                          % ("s" if tells > 1 else "") if tells else "Run brainstorm start.")
    named, offer = parts_named(Store(root))
    for line in named:
        out.line(line)
    tells = told(lines)
    relay = "" if not tells else ", relaying the Tell line above" if tells == 1 else ", relaying the Tell lines above"
    return out.finish("Tell the user the migration is done%s, then answer their message, running brainstorm start "
                      "first if it needs the store's overview." % relay + offer)
