"""The Doorbell files of one loop: the Doorbell file, each Role's state
file, and what is pending for a Role.

A loop's tracker directory is .scratch/<slug>/, the loop --slug names or
the lookup finds. The Doorbell file, <tracker>/doorbells, holds one line per ring,
"<HH:MM:SS> to: <Role> <Doorbell line>", LF, append-only, after a version
header. Each Role's state file, <tracker>/doorbell-state-<role>, records what
that Role has handled: how many lines addressed to it, and the sender and
round of each Doorbell it acted on. The model carries no count and no record.
"""

from __future__ import annotations

import os
import time

from .. import gitcmd, loopfile, loopstate, runner, textfile
from ..out import Failure, Output
from .lines import ADDRESS, Entry, parse


FILE_NAME = "doorbells"
HEADER_PREFIX = "# vdd doorbells "
FILE_VERSION = "1"
STATE_PREFIX = "vdd doorbell-state "
STATE_VERSION = "1"


class Place:
    """The files of one loop: its tracker directory, the Doorbell file, the
    state files."""

    def __init__(
        self, root: str, slug: str, loop: loopfile.Loop | None = None, state: loopstate.State | None = None,
    ) -> None:
        self.root = root
        self.slug = slug
        self.tracker = ".scratch/" + slug
        self.dir = loopfile.tracker_dir(root, slug)
        self.file = os.path.join(self.dir, FILE_NAME)
        # The checked Loop, when the Place is built from one; the Codex Stop
        # hook builds it from a slug alone.
        self.loop = loop
        self._state = state

    @property
    def state(self) -> loopstate.State:
        """The loop's state file, read once per command."""
        if self._state is None:
            self._state = self.loop.load_state() if self.loop is not None else loopstate.State(self.dir)
        return self._state

    @classmethod
    def find(cls, slug: str | None = None) -> Place:
        """The Place of the loop --slug names, or the lookup finds."""
        loop = loopfile.find(gitcmd.project_root(os.getcwd()), slug)
        return cls(loop.root, loop.slug, loop)

    def require_loop(self) -> loopfile.Loop:
        """The Loop the Place was built from."""
        if self.loop is None:
            raise RuntimeError("The Place of %s was built without its Loop." % self.slug)
        return self.loop

    def require_open(self, what: str) -> None:
        """Refuse ring and wait on a closed loop: no Session would ever answer."""
        self.require_loop()
        if not self.state.is_open:
            raise runner.closed_loop(self.slug, ", so %s would never be answered" % what)

    def planner_round(self) -> int:
        """The newest round the Planner rang, from the Doorbell file, or 0."""
        rounds = [e.doorbell.round for e in self.entries("Orchestrator") if e.doorbell]
        return max(rounds) if rounds else 0

    def position(self) -> loopstate.Position:
        return loopstate.position(self.state, self.planner_round())

    def state_path(self, role: str) -> str:
        return os.path.join(self.dir, "doorbell-state-" + role.lower())

    def entries(self, role: str) -> list[Entry]:
        """Every line addressed to role, oldest first."""
        lines = textfile.lines(self.file)
        if lines is None:
            return []
        textfile.check_header(self.file, lines, HEADER_PREFIX, (FILE_VERSION,))
        out: list[Entry] = []
        for number, line in enumerate(lines, 1):
            match = ADDRESS.match(line)
            if not match or match.group(2) != role:
                continue
            text = match.group(3)
            out.append(Entry(number, line, text, parse(text, role, self.tracker)))
        return out

    def load_state(self, role: str) -> State:
        lines = textfile.lines(self.state_path(role))
        state = State()
        if not lines:
            return state
        if textfile.check_header(self.state_path(role), lines, STATE_PREFIX, (STATE_VERSION,)) is None:
            raise Failure(
                "%s is not a Doorbell state file this tool wrote." % textfile.shown(self.state_path(role)),
                "Tell the user the file is damaged; deleting it makes the Role re-read every Doorbell. Then stop.",
            )
        for line in lines[1:]:
            parts = line.split()
            if len(parts) == 2 and parts[0] == "count" and parts[1].isdigit():
                state.count = int(parts[1])
            elif len(parts) == 3 and parts[0] == "handled" and parts[2].isdigit():
                state.handled.add((parts[1], int(parts[2])))
        return state

    def save_state(self, role: str, state: State) -> None:
        """Write the state file whole, or raise a refused Failure and record
        nothing: a Doorbell is printed only once it is recorded as handled."""
        lines = [STATE_PREFIX + STATE_VERSION, "count %d" % state.count]
        lines += ["handled %s %d" % key for key in sorted(state.handled)]
        textfile.write_or_refuse(
            self.state_path(role), "\n".join(lines) + "\n",
            "the Doorbell state file %s" % textfile.shown(self.state_path(role)),
            "Otherwise tell the user the Doorbell state file cannot be written, and stop.",
            ["Nothing was recorded as handled."],
        )

    def append(self, role: str, text: str) -> None:
        os.makedirs(self.dir, exist_ok=True)
        textfile.append(self.file, "%s to: %s %s\n" % (time.strftime("%H:%M:%S"), role, text),
                        HEADER_PREFIX + FILE_VERSION + "\n")


class State:
    def __init__(self) -> None:
        self.count = 0
        self.handled: set[tuple[str, int]] = set()


def pending(entries: list[Entry], state: State) -> tuple[list[Entry], list[Entry]]:
    """The lines beyond the handled count, and of them the Doorbells not yet
    handled."""
    beyond = entries[state.count:] if state.count <= len(entries) else []
    new = [e for e in beyond if e.doorbell and e.doorbell.key() not in state.handled]
    return beyond, new


def tell_not_doorbells(out: Output, entries: list[Entry]) -> None:
    for entry in entries:
        if entry.doorbell is None:
            out.tell(
                "Line %d of the Doorbell file is not a Doorbell, so it was not acted on: %s"
                % (entry.number, entry.text)
            )


def mark_handled(place: Place, role: str) -> tuple[list[Entry], State | None]:
    """Every line addressed to role so far recorded as handled, as take does,
    without printing a Doorbell: the Orchestrator's start acts on what was
    rung before it from the state, so the relay after it names the wait
    rather than a Doorbell already acted on. The lines beyond the handled
    count, and the state recording them handled for the caller to save, or
    None when there are none."""
    entries = place.entries(role)
    state = place.load_state(role)
    beyond, _ = pending(entries, state)
    if not beyond:
        return beyond, None
    for entry in beyond:
        if entry.doorbell:
            state.handled.add(entry.doorbell.key())
    state.count = len(entries)
    return beyond, state


def sign_off_taken(place: Place) -> bool:
    """Whether the newest line to the Planner is the plan Sign-off's Doorbell
    and the Planner has taken it."""
    entries = place.entries("Planner")
    newest = entries[-1].doorbell if entries else None
    if newest is None or not newest.signed_off:
        return False
    return newest.key() in place.load_state("Planner").handled


def plan_signed_off(place: Place) -> bool:
    """The plan Loop is over and neither Role waits: the position is in the
    code Loop."""
    return place.position().phase == "code"

