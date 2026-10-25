"""The Loop file, .scratch/<slug>/loop.md: its format and the loop it names.

The Loop file holds a loop's settings, format 2, one "<Name>: <value>" line
each. A line it no longer names, such as the Coder's respawn line a loop
from 0.16.0-beta.3 wrote, is read and ignored. The loop's state file,
.scratch/<slug>/loop-state, belongs to the loopstate package; a Loop reads
it once, for whether the loop is open or closed.
"""

from __future__ import annotations

import os
import re
from typing import Iterable

from .. import harness as harnesses, loopstate, textfile
from ..harness import Harness, generic
from ..out import TELL, Failure

FORMAT = 2
NAME = "loop.md"

LINE = re.compile(r"^([A-Za-z][A-Za-z ]*):[ \t]*(.*?)[ \t]*$")

IDENTITY = ("Feature", "Base branch", "Feature branch")
SETTINGS = ("Minors", "PR", "Harness")
ORDER = ("Format",) + IDENTITY + SETTINGS
DEFAULTS = {"Minors": "leave", "PR": "ask at sign-off", "Harness": generic.HARNESS.label}
MINORS = ("fix", "leave")
PR = ("yes", "ask at sign-off", "manual", "no")

# The lines each Role acts on, as loop show --role prints them.
ROLES: dict[str, tuple[str, ...]] = {
    "Planner": ("Feature", "Harness"),
    "Plan-Reviewer": ("Minors", "Harness"),
    "Coder": ("Base branch", "Feature branch", "Harness"),
    "Code-Reviewer": ("Base branch", "Minors", "Harness"),
    "Orchestrator": IDENTITY + SETTINGS,
    "PR-Author": ("Base branch", "Feature branch", "PR", "Harness"),
}


def accepted(name: str, value: str) -> bool:
    """Whether value is one the line name accepts, matched exactly."""
    if name in ("Minors", "PR", "Harness"):
        return value in choices(name)
    return bool(value)


def choices(name: str) -> tuple[str, ...]:
    """The values the line name accepts: Minors, PR or Harness."""
    if name == "Minors":
        return MINORS
    if name == "PR":
        return PR
    return tuple(found.label for found in harnesses.every())


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
                "Stop.",
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

    # --- the settings: a setting with a default falls back to it; Base
    # branch and Feature branch have none, as check() refuses them missing ---

    @property
    def base(self) -> str:
        return self.setting("Base branch")[0]

    @property
    def branch(self) -> str:
        return self.setting("Feature branch")[0]

    @property
    def pr(self) -> str:
        return self.setting("PR")[0]

    @property
    def minors(self) -> str:
        return self.setting("Minors")[0]

    @property
    def harness_label(self) -> str:
        """The Harness: line's own value, as the lines that quote the Loop
        file print it."""
        return self.setting("Harness")[0]

    @property
    def harness(self) -> Harness:
        return harnesses.of_label(self.harness_label)

    def harness_file(self) -> str:
        return "harness-%s.md" % self.harness.name

    def path(self, name: str) -> str:
        """A path under the tracker directory, as the tool prints it."""
        return "%s/%s" % (self.tracker, name)

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
