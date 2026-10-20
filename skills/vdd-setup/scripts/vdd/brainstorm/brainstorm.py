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
from ..out import Output
from . import journal, moves, reads
from .lock import Lock
from .store import LAYOUT, LAYOUT_FILE, Store, layout, require_layout, store_dir

V, W, L = args.VALUE, args.FLAG, args.LIST
METRIC_OPTIONS = {"importance": V, "size": V, "fog": V}
# The first sentence of the overview's Next: step.
ANSWER = "Answer the user's message from this overview; read or run nothing else unless it needs more."

# One option table per command: an option another command takes is refused
# on this one, never silently ignored.
SPECS: dict[str, dict[str, str]] = {
    "start": {},
    "show": {"idea": V},
    "new": dict({"slug": V, "title": V, "tldr": V, "parent": V, "summary": V, "relate": L, "write": W},
                **METRIC_OPTIONS),
    "note": {"idea": V, "section": V, "text": L, "tick": V, "write": W},
    "set": dict({"idea": L, "status": V, "decision": V, "reopen-when": V, "tldr": V, "title": V, "write": W},
                **METRIC_OPTIONS),
}
REQUIRED = {
    "show": ["idea"],
    "new": ["slug", "title", "tldr"],
    "note": ["idea"],
    "set": ["idea"],
}

HELP = [
    "brainstorm start",
    "  The Session's first call: the open ideas, each part under its parent, with status, importance/size/fog,",
    "  last update, what each waits on, and the tldr.",
    "brainstorm show --idea <slug>",
    "  One idea and its family at every level: status, Decision, open Next Steps and open questions of every",
    "  open member, what it waits on and what waits on it, and the file's path.",
    "brainstorm new --slug <slug> --title <title> --tldr <one sentence> [--parent <slug>] [--summary <text>]",
    "    [--importance|--size|--fog <xsmall..xlarge|unknown>] [--relate '<kind> <slug>: <why>' ...]",
    "  Captures an idea: its file with frontmatter, title, Summary and a created History line.",
    "brainstorm note --idea <slug> (--section <name> --text <text> [--text ...] | --tick <step>)",
    "  Adds prose to a section (Evidence items are dated, Next Steps become open steps), or ticks the open",
    "  Next Step that starts with --tick. To rewrite a section, Read the file and Edit it.",
    "brainstorm set --idea <slug> [--idea ...] [--status <s>] [--decision <text>] [--reopen-when <text>]",
    "    [--importance|--size|--fog <m>] [--tldr <text>] [--title <text>]",
    "  Status idea, discussed, shaped, decided, in-progress, done or dropped. done, dropped and decided need",
    "  --decision, dropped also --reopen-when; dropping an idea drops its open parts at every level; an open",
    "  status on a closed idea reopens it.",
    "",
    "Run every command from the repository root. Every write needs --write; without it the command is a dry run.",
]

Move = Callable[[Store, Dict[str, Any]], Tuple[List[str], str, str]]
WRITES: dict[str, Move] = {"new": moves.new, "note": moves.note, "set": moves.set_cmd}


def usage() -> str:
    return "%s brainstorm --help" % places.command()


def run(argv: list[str]) -> int:
    return args.run_group(argv, "brainstorm", SPECS, HELP, "Run the brainstorm command your skill names.", dispatch)


def dispatch(command: str, values: dict[str, Any]) -> int:
    args.require(values, REQUIRED.get(command, []), usage())
    root = gitcmd.project_root(os.getcwd())
    if command == "start":
        return start(root, values)
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
    return reads.show(store, values, out)


def recover_quietly(root: str) -> list[str]:
    """Before a read: settle a write a killed run left half done, when no
    live writer holds the lock. A read never waits for the lock."""
    if not journal.pending(root):
        return []
    with Lock(root, wait=False, on_take=journal.recover) as lock:
        return lock.recovered


def write(root: str, command: str, values: dict[str, Any]) -> int:
    handler = WRITES[command]
    out = Output()
    if not values["write"]:
        store = Store(root)
        lines, _, _ = handler(store, values)
        would = store.planned()
        out.line("Dry run, nothing was written. With --write, brainstorm %s would write %s:"
                 % (command, ", ".join(would) or "nothing"))
        for line in lines:
            out.line(line)
        return out.finish(store.dry_next or "If this is what the user asked for, run the same command again with "
                          "--write.")
    # The lock is taken before the store is read, so no update is lost;
    # inside it, a write a killed run left half done is settled first.
    with Lock(root, on_take=journal.recover) as lock:
        store = Store(root)
        lines, nxt, label = handler(store, values)
        stamped = list(store.stamped)
        lines += loop_lines(store)
        journal.save(store, label, lock)
    for line in lock.recovered:
        out.line(line)
    for line in lines:
        out.line(line)
    if stamped:
        out.line("last-updated set for ideas edited since the tool last wrote them: %s." % ", ".join(stamped))
    return out.finish(nxt)


def start(root: str, values: dict[str, Any]) -> int:
    found = layout(root)
    out = Output()
    if found is None:
        out.line("This project has no idea store yet (.scratch/_brainstorming/).")
        return out.finish("Answer the user's message; when they bring an idea, capture it with brainstorm new, "
                          "which creates the store.")
    if found == "1":
        out.line("The idea store is in the 0.15 layout (index.md and one file per idea); brainstorm migrate "
                 "converts it.")
        return out.finish("Run brainstorm migrate to see the migration plan, and ask the user before migrate "
                          "--write. No other brainstorm command reads the 0.15 layout.")
    if found in ("lost", "damaged"):
        out.line("The idea store's .layout marker is %s." % ("missing" if found == "lost" else "empty"))
        return out.finish("Run brainstorm migrate --write: it checks the store and writes the marker back. Then "
                          "run brainstorm start again.")
    require_layout(root)
    for line in recover_quietly(root):
        out.line(line)
    store = Store(root)
    for line in reads.overview(store):
        out.line(line)
    return out.finish("Answer the user's message from this overview; read or run nothing else unless it needs more.")

