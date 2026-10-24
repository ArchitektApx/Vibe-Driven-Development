"""Brainstorm's write runner and its store guard: a write takes the lock,
settles a write a killed run left half done and saves through the journal;
a dry run plans against the same store and prints the lines the write would
print, indented under what it would write. The guard refuses a command the
store's layout cannot take."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Tuple

from .. import textfile
from ..out import TELL, Failure, Output
from . import journal, migrate, moves, printed
from .lock import Lock
from .migrate import require_layout
from .store import LAYOUT, LAYOUT_FILE, Store, layout, store_dir

Move = Callable[[Store, Dict[str, Any]], Tuple[List[str], str, str]]
TOLD = TELL.split('"')[0]


def guard(root: str, command: str, values: dict[str, Any]) -> None:
    """Refuse a command the store cannot take: one between the migration's
    two renames, or one on a store of another layout. The first idea's
    --write creates the store, once the command checks out."""
    if migrate.STEPS["1"].half(root):
        # Between the migration's two renames there is no store: a new one
        # here would leave two half stores (F2).
        raise Failure("A migration was interrupted after the backup; the idea store is not in place yet. Nothing was "
                      "written.", "Run %s, then %s." % (printed.MIGRATE, printed.START))
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


def recover_quietly(root: str) -> list[str]:
    """Before a read: settle a write a killed run left half done, when no
    live writer holds the lock. A read never waits for the lock."""
    if not journal.pending(root):
        return []
    with Lock(root, wait=False, on_take=journal.recover) as lock:
        return lock.lines


def write(root: str, command: str, handler: Move, values: dict[str, Any]) -> int:
    out = Output()
    if not values["write"]:
        # A dry run plans against the store the --write will see: a write a
        # killed run left half done is settled first, as a read does.
        for line in recover_quietly(root):
            out.line(line)
        store = Store(root)
        lines, _, _ = handler(store, values)
        would = store.planned()
        out.line("Dry run, nothing was written. With --write, brainstorm %s would write %s:"
                 % (command, ", ".join(would) or "nothing"))
        for line in shown(lines + loop_lines(store), written(root, handler, values)):
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


def written(root: str, handler: Move, values: dict[str, Any]) -> set[str]:
    """The lines the same command's --write would print, planned against a
    store of its own and never saved."""
    store = Store(root)
    lines, _, _ = handler(store, dict(values, write=True))
    return set(lines + loop_lines(store))


def shown(lines: list[str], written: set[str]) -> list[str]:
    """A dry run's lines, each line the --write prints too indented under
    the dry run's first line, so the write repeats no line of the dry run.
    A Tell line stays as it is."""
    return ["  " + line if line in written and not line.startswith(TOLD) else line for line in lines]


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
                     "top level: %s" % (" and ".join(sorted(chain)), " -> ".join(chain), slug,
                                        printed.command("move", set="%s=top" % slug, write=True)))
    return lines


