"""The Loop file, .scratch/<slug>/loop.md.

The Loop file holds a loop's settings, format 2, one "<Name>: <value>" line
each. A line it no longer names, such as the Coder's respawn line a loop
from 0.16.0-beta.3 wrote, is read and ignored. The loop's state file,
.scratch/<slug>/loop-state, belongs to loopstate.py; this module asks it
whether a loop is open or closed.

A loop is a directory under .scratch/ that holds the Loop file and the state file, and its slug is that
directory's name. A root LOOP.md is a format-1 Loop file from before this
version: no command reads it, and every command that needs a loop refuses
while it exists.
"""

from __future__ import annotations

import os
import re
from typing import Iterable

from . import args, armed, gitcmd, loopstate, textfile
from .out import TELL, Failure

SLUG_PATTERN = "[a-z0-9]+(-[a-z0-9]+)*"
FORMAT = 2
NAME = "loop.md"
ROOT_FILE = "LOOP.md"
ROOT_FIX = (
    "Delete `LOOP.md`. To carry on the loop it belongs to, run `vdd-start-loop` with its slug and answer continue."
)

LINE = re.compile(r"^([A-Za-z][A-Za-z ]*):[ \t]*(.*?)[ \t]*$")

IDENTITY = ("Feature", "Base branch", "Feature branch")
SETTINGS = ("Minors", "PR", "Harness")
ORDER = ("Format",) + IDENTITY + SETTINGS
DEFAULTS = {"Minors": "leave", "PR": "ask at sign-off", "Harness": "Generic"}
MINORS = ("fix", "leave")
PR = ("yes", "ask at sign-off", "manual", "no")
LABELS = {
    "claude-code": "Claude Code",
    "codex": "Codex",
    "cursor": "Cursor",
    "copilot-cli": "Copilot CLI",
    "generic": "Generic",
}

# The lines each Role acts on, as loop show --role prints them.
ROLES: dict[str, tuple[str, ...]] = {
    "Planner": ("Feature", "Harness"),
    "Plan-Reviewer": ("Minors", "Harness"),
    "Coder": ("Base branch", "Feature branch", "Harness"),
    "Code-Reviewer": ("Base branch", "Minors", "Harness"),
    "Orchestrator": IDENTITY + SETTINGS,
    "PR-Author": ("Base branch", "Feature branch", "PR", "Harness"),
}

NO_STATE = "no-state"


def accepted(name: str, value: str) -> bool:
    """Whether value is one the line name accepts, matched exactly."""
    if name == "Minors":
        return value in MINORS
    if name == "PR":
        return value in PR
    if name == "Harness":
        return value in LABELS.values()
    return bool(value)


def accepted_text(name: str) -> str:
    if name == "Minors":
        return "fix or leave"
    if name == "PR":
        return "yes, ask at sign-off, manual or no"
    if name == "Harness":
        return ", ".join(LABELS.values())
    return "a value"


def harness_slug(label: str) -> str:
    for slug, text in LABELS.items():
        if text == label:
            return slug
    return "generic"


def fields_of(lines: Iterable[str]) -> dict[str, str]:
    """The first value of every "<Name>: <value>" line."""
    fields: dict[str, str] = {}
    for line in lines:
        match = LINE.match(line)
        if match and match.group(1) not in fields:
            fields[match.group(1)] = match.group(2)
    return fields


def scratch(root: str) -> str:
    return os.path.join(root, ".scratch")


def tracker_dir(root: str, slug: str) -> str:
    return os.path.join(scratch(root), slug)


def check_slug(slug: str) -> None:
    args.check_slug(slug, SLUG_PATTERN, "a Feature slug", "a slug", "hyphens")


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


def kind(root: str, slug: str) -> str | None:
    """What .scratch/<slug> is: None when it does not exist, OPEN or CLOSED
    for a loop, NO_STATE for any other existing path, a damaged state file
    included. A state file of a newer format version still refuses."""
    directory = tracker_dir(root, slug)
    if not os.path.lexists(directory):
        return None, None
    state = probe(directory)
    if state is not None and state.status:
        return state.status, state
    return NO_STATE, None


# --- closing and reopening ---

def close(state: loopstate.State) -> list[str]:
    """Close the loop: append "loop closed" and delete its Codex armed files
    and claim markers. The names of the armed files deleted, for the caller
    to print. Raises OSError when the state file cannot be appended to."""
    state.add(loopstate.loop_line(loopstate.CLOSED))
    return armed.delete(state.dir)


def reopen(state: loopstate.State, *lines: str) -> None:
    """Append lines, then "loop open", in one write. Raises OSError."""
    state.add(*(lines + (loopstate.loop_line(loopstate.OPEN),)))


def closed_line(slug: str) -> str:
    """The line loop close and pr open print once a loop is closed."""
    return "Closed: the loop %s. Its files stay in .scratch/%s/ as the record." % (slug, slug)


# --- the Loop file ---

class Loop:
    """One loop: its slug, its tracker directory and its Loop file's lines."""

    def __init__(self, root: str, slug: str, state: loopstate.State | None = None) -> None:
        self.root = root
        self.slug = slug
        self.dir = tracker_dir(root, slug)
        self.tracker = ".scratch/" + slug
        self.file = os.path.join(self.dir, NAME)
        self.relative = ".scratch/%s/%s" % (slug, NAME)
        self.lines: list[str] = textfile.lines(self.file) or []
        self.fields = fields_of(self.lines)
        self._state = state

    def check(self) -> Loop:
        """Refuse a Loop file this copy does not read, or one that lacks a
        line naming the loop."""
        value = self.fields.get("Format", "")
        if not value.isdigit() or int(value) != FORMAT:
            if value.isdigit() and int(value) > FORMAT:
                why = "%s has format %s, which this copy of the VDD tool does not know." % (self.relative, value)
            elif value:
                why = "%s has format %s, which this copy of the VDD tool does not read." % (self.relative, value)
            else:
                why = "%s has no Format: line, so this copy of the VDD tool does not read it." % self.relative
            raise Failure(
                [why, TELL % ("The Loop file %s is not one this copy of VDD reads: rerun Setup." % self.relative)],
                "Relay the Tell the user verbatim line above unchanged: rerun Setup. Then stop.",
            )
        for name in IDENTITY:
            if not self.fields.get(name):
                raise Failure(
                    "%s has no %s: line." % (self.relative, name),
                    "Tell the user the Loop file %s is damaged: it does not name the loop's %s. Then stop."
                    % (self.relative, name.lower()),
                )
        return self

    def setting(self, name: str) -> tuple[str, str | None]:
        """(value, fault): the line's value, or its default with fault
        "missing" or "malformed"."""
        if name not in self.fields:
            if name in DEFAULTS:
                return DEFAULTS[name], "missing"
            return "", "missing"
        value = self.fields[name]
        if name in DEFAULTS and not accepted(name, value):
            return DEFAULTS[name], "malformed"
        return value, None

    def harness_file(self) -> str:
        return "harness-%s.md" % harness_slug(self.setting("Harness")[0])

    def load_state(self) -> loopstate.State:
        """The loop's state file, read once: by the lookup that found the
        loop, or on the first call."""
        if self._state is None:
            self._state = loopstate.State(self.dir)
        return self._state


def render(fields: dict[str, str]) -> str:
    """A Loop file's text from its lines' values, in the fixed order."""
    lines = ["# VDD Loop", ""]
    for name in ORDER:
        lines.append("%s: %s" % (name, fields[name]))
    return "\n".join(lines) + "\n"


def write(directory: str, fields: dict[str, str]) -> None:
    os.makedirs(directory, exist_ok=True)
    textfile.write_text(os.path.join(directory, NAME), render(fields))


def replace_line(lines: Iterable[str], name: str, value: str) -> list[str]:
    """lines with name's line set to value: in place when it exists, else
    inserted after the last line that comes before it in the fixed order."""
    out = list(lines)
    for index, line in enumerate(out):
        match = LINE.match(line)
        if match and match.group(1) == name:
            out[index] = "%s: %s" % (name, value)
            return out
    position = len(out)
    earlier = ORDER[: ORDER.index(name)]
    for index, line in enumerate(out):
        match = LINE.match(line)
        if match and match.group(1) in earlier:
            position = index + 1
    out.insert(position, "%s: %s" % (name, value))
    return out


# --- finding the loop ---

def loops(root: str) -> list[tuple[str, loopstate.State]]:
    """Every loop under .scratch/: (slug, its State), by slug."""
    try:
        names = sorted(os.listdir(scratch(root)))
    except OSError:
        return []
    found: list[tuple[str, loopstate.State]] = []
    for name in names:
        try:
            state = probe(os.path.join(scratch(root), name))
        except Failure:
            continue
        if state is not None:
            found.append((name, state))
    return found


def find(root: str, slug: str | None = None) -> Loop:
    """The loop --slug names, else the loop whose Feature branch is checked
    out, else the only open loop; a checked Loop. Refuses otherwise."""
    refuse_root(root)
    if slug is not None:
        return named(root, slug)
    every = loops(root)
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
