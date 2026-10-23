"""brainstorm migrate: an idea store of an older layout to the current one.

STEPS maps a found layout to the step module that takes the store one
layout on. Each step module offers NEEDS_USER, plan_lines and, when it needs
the user, ask; its run applies it under --write. migrate runs the steps from
the found layout to the current one. A store whose .layout marker is missing
or empty is checked here and the marker written back.
"""

from __future__ import annotations

import os
from types import ModuleType
from typing import List, Tuple

from .. import textfile
from ..out import Failure
from . import journal, layout1
from .ideafile import STATUSES, real_date, today
from .lock import Lock
from .store import LAYOUT, LAYOUT_FILE, STORE, Store, layout, require_layout

# (lines, what happened, what a dry run's --write would write)
Result = Tuple[List[str], str, List[str]]

STEPS: dict[str, ModuleType] = {"1": layout1}


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


def plan_next(root: str) -> str:
    """The Next: of start and of a dry run on an older store: the ask of the
    steps that need the user, once."""
    return " ".join(step.ask(root) for step in path(layout(root) or "") if step.NEEDS_USER)


def repair_marker(root: str, write: bool) -> Result:
    """A layout-2 store whose .layout is missing or empty: every idea file
    needs a known status and a created History line. A file with a known
    status but no History, as a 0.15 skill on another Harness writes it
    (M7), is named and gets its created line; a file with no known status
    fails the repair."""
    found = layout(root)
    what = "missing" if found == "lost" else "empty"
    if not write:
        # A dry run reads only: no lock, no recovery, no .state/.
        return repair_lines(root, Store(root), what, False)
    with Lock(root, on_take=journal.recover) as lock:
        store = Store(root)
        lines, _, _ = repair_lines(root, store, what, True)
        journal.save(store, "migrate marker repair")
        textfile.write(os.path.join(store.dir, LAYOUT_FILE), (LAYOUT + "\n").encode("ascii"))
    lines = lock.lines + lines
    lines.append("The .layout marker was %s; it now reads %s." % (what, LAYOUT))
    return lines, "repaired", []


def repair_lines(root: str, store: Store, what: str, write: bool) -> Result:
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
             "tool knows." % (LAYOUT, what)]
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
    """The migration's lines and what happened: "dry", "dry-half", "noop",
    "dry-repair", "repaired", "finished" or "migrated". A half migration or a
    missing store is the layout 1 step's to finish or name."""
    if layout1.half(root) or not os.path.isdir(os.path.join(root, STORE)):
        return layout1.run(root, events_raw, write)
    found = layout(root)
    if found in ("lost", "damaged"):
        return repair_marker(root, write)
    if found == LAYOUT:
        return ["The idea store is already in layout %s; nothing to migrate." % LAYOUT], "noop", []
    if found not in STEPS:
        require_layout(root)
    lines, what, would = STEPS[found or ""].run(root, events_raw, write)
    if what == "moved":
        # Another Session moved the store on while this one waited.
        return migrate(root, events_raw, write)
    return lines, what, would
