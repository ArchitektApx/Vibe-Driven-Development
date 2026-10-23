"""Finding a loop: a directory under .scratch/ that holds the Loop file and
the state file, its slug that directory's name. A root LOOP.md is a format-1
Loop file from before this version: no command reads it, and every command
that needs a loop refuses while it exists.
"""

from __future__ import annotations

import os

from .. import catalog, gitcmd, loopstate, textfile
from ..out import TELL, Failure, notice
from .format import NAME, Loop, fields_of, scratch, tracker_dir

SLUG_PATTERN = "[a-z0-9]+(-[a-z0-9]+)*"
ROOT_FILE = "LOOP.md"
ROOT_FIX = (
    "Delete `LOOP.md`. To carry on the loop it belongs to, run `vdd-start-loop` with its slug and answer continue."
)

NO_STATE = "no-state"


def check_slug(slug: str) -> None:
    catalog.check_slug(slug, SLUG_PATTERN, "a Feature slug", "a slug", "hyphens")


def has_root_file(root: str) -> bool:
    """Whether root holds a file named exactly LOOP.md. A listing, not a path
    test: on a case-insensitive file system the path LOOP.md also finds a
    loop.md."""
    try:
        return ROOT_FILE in os.listdir(root)
    except OSError:
        return False


def refuse_root(root: str) -> None:
    """Refuse while a format-1 root LOOP.md exists."""
    if has_root_file(root):
        raise Failure(
            [
                "LOOP.md at the repository root is a Loop file from before this version of VDD (format 1). "
                "No command reads it.",
                TELL % ROOT_FIX,
            ],
            "Relay the Tell the user verbatim line above unchanged, and stop.",
        )


def probe(directory: str) -> loopstate.State | None:
    """The State of the loop in directory, read once, or None when directory
    holds no Loop file or no readable state file. A state file of a newer
    format version still refuses."""
    if not (os.path.isdir(directory) and os.path.isfile(os.path.join(directory, NAME))):
        return None
    return readable(directory)


def readable(directory: str) -> loopstate.State | None:
    """The State in directory, or None when it has no readable state file. A
    state file of a newer format version still refuses."""
    try:
        state = loopstate.State(directory)
    except loopstate.Damaged:
        return None
    return state if state.version is not None else None


def look(root: str, slug: str) -> tuple[str | None, loopstate.State | None]:
    """What .scratch/<slug> is, and the State probe() read for a loop: None when
    it does not exist, OPEN or CLOSED for a loop, NO_STATE for any other
    existing path, a damaged state file included. A state file of a newer
    format version beside a Loop file still refuses."""
    directory = tracker_dir(root, slug)
    if not os.path.lexists(directory):
        return None, None
    state = probe(directory)
    if state is not None and state.status:
        return state.status, state
    return NO_STATE, None


def loops(root: str) -> tuple[list[tuple[str, loopstate.State]], list[tuple[str, str]]]:
    """Every loop under .scratch/: ([(slug, its State)], [(slug, why)]), by
    slug. A loop whose state file a newer VDD wrote is left out, with the
    line saying why; a damaged one is no loop."""
    try:
        names = sorted(os.listdir(scratch(root)))
    except OSError:
        return [], []
    found: list[tuple[str, loopstate.State]] = []
    left: list[tuple[str, str]] = []
    for name in names:
        try:
            state = probe(os.path.join(scratch(root), name))
        except Failure as failure:
            left.append((name, failure.lines[0]))
            continue
        if state is not None:
            found.append((name, state))
    return found, left


def find(root: str, slug: str | None = None) -> Loop:
    """The loop --slug names, else the loop whose Feature branch is checked
    out, else the only open loop; a checked Loop. Refuses otherwise."""
    refuse_root(root)
    if slug is not None:
        return named(root, slug)
    every, left = loops(root)
    for name, why in left:
        notice("Left out the loop %s: %s" % (name, why))
    states = dict(every)
    branch = gitcmd.current_branch(root)
    if branch:
        on_branch = [(name, state.status) for name, state in every if branch_of(root, name) == branch]
        for state in (loopstate.OPEN, loopstate.CLOSED):
            matches = [name for name, s in on_branch if s == state]
            if len(matches) == 1:
                return Loop(root, matches[0], states[matches[0]]).check()
            if len(matches) > 1:
                raise Failure(
                    "Several %s loops have the checked-out branch %s as their feature branch: %s."
                    % (state, branch, ", ".join(matches)),
                    "Ask the user which loop this is, then run the command again with --slug <slug>.",
                )
    opened = [name for name, state in every if state.is_open]
    if len(opened) == 1:
        return Loop(root, opened[0], states[opened[0]]).check()
    if opened:
        raise Failure(
            "Several loops are open: %s. The tool cannot tell which one you mean." % ", ".join(opened),
            "Ask the user which loop this is, then run the command again with --slug <slug>.",
        )
    raise Failure(
        "No open loop under .scratch/, and none has the checked-out branch as its feature branch.",
        "Run the command again with --slug <slug> for the loop you mean; with none, ask the user for the slug, "
        "or tell them to start a loop with vdd-start-loop.",
    )


def branch_of(root: str, slug: str) -> str:
    lines = textfile.lines(os.path.join(tracker_dir(root, slug), NAME)) or []
    return fields_of(lines).get("Feature branch", "")


def named(root: str, slug: str) -> Loop:
    check_slug(slug)
    directory = tracker_dir(root, slug)
    if not os.path.lexists(directory):
        raise Failure(
            "No loop %s: .scratch/%s/ does not exist." % (slug, slug),
            "Check the slug with the user, then run the command again with the right --slug.",
        )
    state = probe(directory)
    if state is None:
        raise Failure(
            ".scratch/%s/ holds no loop the VDD tool started: it lacks %s or %s." % (slug, NAME, loopstate.STATE_NAME),
            "Tell the user to run vdd-start-loop with the slug %s and answer continue, and stop." % slug,
        )
    return Loop(root, slug, state).check()
