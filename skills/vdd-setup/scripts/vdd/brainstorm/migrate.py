"""brainstorm migrate: an idea store of an older layout to the current one.

STEPS maps a found layout to the step module that takes the store one
layout on. Each step module offers NEEDS_USER, plan_lines and, when it needs
the user, ask; its run applies it under --write. migrate runs the steps from
the found layout to the current one, re-reading the layout after each, so a
stop between two steps leaves a store the next run takes on from there. A
store whose .layout marker is missing or empty is checked here and the
marker written back: 2 while the layout 2 ledger is there, else the current
layout.
"""

from __future__ import annotations

import os
from types import ModuleType
from typing import List, Tuple

from .. import textfile
from ..out import Failure
from . import journal, layout1, layout2
from .ideafile import STATUSES, real_date, today
from .lock import Lock
from .store import LAYOUT, LAYOUT_FILE, STORE, Store, layout

# (lines, what happened, what a dry run's --write would write)
Result = Tuple[List[str], str, List[str]]

STEPS: dict[str, ModuleType] = {"1": layout1, "2": layout2}


def path(found: str) -> list[ModuleType]:
    """The steps from the found layout to the current one, in order."""
    out: list[ModuleType] = []
    while found in STEPS:
        out.append(STEPS[found])
        found = STEPS[found].TO
    return out


def plan_lines(root: str) -> list[str]:
    """The plan of every step from the store's layout to the current one."""
    lines: list[str] = []
    for step in path(layout(root) or ""):
        lines += step.plan_lines(root)
    return lines


def needs_user(found: str) -> bool:
    return any(step.NEEDS_USER for step in path(found))


def plan_next(root: str) -> str:
    """The Next: of start and of a dry run on an older store: the ask of the
    steps that need the user, once, or the migration straight away."""
    asks = [step.ask(root) for step in path(layout(root) or "") if step.NEEDS_USER]
    return " ".join(asks) if asks else "Run brainstorm migrate --write, then answer the user's message."


def require_layout(root: str) -> None:
    """Refuse a store that is not in the current layout, naming the way
    out."""
    found = layout(root)
    if found == LAYOUT:
        return
    if found is None:
        raise Failure("This project has no idea store yet (.scratch/_brainstorming/).",
                      "Capture the first idea with brainstorm new; it creates the store.")
    if found in STEPS:
        raise Failure("The idea store is still in the 0.15 layout (index.md). Nothing was written." if found == "1"
                      else "The idea store is in layout %s; this copy of the VDD tool reads layout %s. Nothing was "
                      "written." % (found, LAYOUT),
                      "Run brainstorm start." if needs_user(found)
                      else "Run brainstorm migrate --write, then the same command again.")
    if found in ("damaged", "lost"):
        raise Failure("The idea store's .layout marker is %s. Nothing was written."
                      % ("empty" if found == "damaged" else "missing"),
                      "Run brainstorm migrate --write: it checks the store and writes the marker back.")
    raise Failure(
        "The idea store has layout %s, which this copy of the VDD tool does not know (it knows %s): a newer VDD "
        "wrote it. Nothing was read or written." % (found, LAYOUT),
        "Tell the user this copy of the VDD tool is older than their idea store: update VDD, rerun Setup "
        "(vdd-setup), then start again. Stop.")


def repair_marker(root: str, write: bool) -> Result:
    """A layout-2 store whose .layout is missing or empty: every idea file
    needs a known status and a created History line. A file with a known
    status but no History, as a 0.15 skill on another Harness writes it
    (M7), is named and gets its created line; a file with no known status
    fails the repair."""
    found = layout(root)
    what = "missing" if found == "lost" else "empty"
    target = marker_for(root)
    if not write:
        # A dry run reads only: no lock, no recovery, no .state/.
        return repair_lines(root, Store(root), what, target, False)
    with Lock(root, on_take=journal.recover) as lock:
        store = Store(root)
        lines, _, _ = repair_lines(root, store, what, target, True)
        journal.save(store, "migrate marker repair")
        textfile.write(os.path.join(store.dir, LAYOUT_FILE), (target + "\n").encode("ascii"))
    lines = lock.lines + lines
    lines.append("The .layout marker was %s; it now reads %s." % (what, target))
    return lines, "repaired", []


def marker_for(root: str) -> str:
    """The layout a lost marker is written back as: 2 while the layout 2
    ledger is there, so its step carries the dates, else the current one."""
    return layout2.FROM if os.path.isfile(layout2.ledger_path(root)) else LAYOUT


def repair_lines(root: str, store: Store, what: str, target: str, write: bool) -> Result:
    """The repair's lines over the loaded store, its created lines added in
    memory; a Failure when an idea file has no known status."""
    bad = ["%s.md: status %r" % (s, i.status) for s, i in sorted(store.ideas.items()) if i.status not in STATUSES]
    if bad:
        raise Failure(["The idea store has no usable .layout marker, and these idea files have no status this "
                       "tool knows, so it is not repaired. Nothing was written:"] + ["- " + b for b in bad],
                      "Tell the user the store at .scratch/_brainstorming/ lost its .layout marker and holds the "
                      "files above; ask them to check each one's status. Stop.")
    seeded = [s for s, i in sorted(store.ideas.items()) if not i.created()]
    for slug in seeded:
        idea = store.ideas[slug]
        day = idea.get("created") or idea.get("last-updated")
        idea.add_history("created", day if real_date(day) else today())
        store.dirty.add(slug)
    lines = ["The idea store is in layout %s, but its .layout marker is %s; every idea file has a status this "
             "tool knows." % (target, what)]
    if seeded:
        lines.append("Written without History, as a VDD 0.15 Brainstormer writes an idea: %s; %s a created "
                     "History line." % (", ".join(s + ".md" for s in seeded),
                                        "each gets" if write else "migrate --write gives each"))
    if not write:
        lines.append("migrate --write writes the marker back%s." % (" and those lines" if seeded else
                                                                    "; nothing else changes"))
        if journal.pending(root):
            lines.append("A write a killed run left half done waits in .scratch/_brainstorming/.state/journal/; "
                         "migrate --write settles it first.")
        return lines, "dry-repair", store.planned() + [LAYOUT_FILE]
    return lines, "", []


def migrate(root: str, events_raw: list[str], write: bool) -> Result:
    """The migration's lines and what happened first: "dry", "dry-half",
    "noop", "dry-repair", "repaired", "finished", "migrated" or "updated".
    A dry run shows the first step and the plan of the steps after it; a
    write runs every step to the current layout."""
    lines: list[str] = []
    whats: list[str] = []
    would: list[str] = []
    for _ in range(10):
        if layout1.half(root) or not os.path.isdir(os.path.join(root, STORE)):
            got, after = layout1.run(root, events_raw, write), layout1.TO
        else:
            found = layout(root) or ""
            if found == LAYOUT:
                break
            if found in ("lost", "damaged"):
                after = marker_for(root)
                got = repair_marker(root, write)
            elif found in STEPS:
                after = STEPS[found].TO
                got = STEPS[found].run(root, events_raw, write)
            else:
                require_layout(root)
                break
        step_lines, what, step_would = got
        if what == "moved":
            # Another Session moved the store on while this one waited.
            lines += step_lines
            continue
        lines += step_lines
        whats.append(what)
        would += step_would
        if not write:
            for step in path(after):
                lines += step.plan_lines(root)
            break
    if not whats:
        return ["The idea store is already in layout %s; nothing to migrate." % LAYOUT], "noop", []
    return lines, whats[0], would
