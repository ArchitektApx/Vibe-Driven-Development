"""One loop as the Orchestrator sees it: its state file, its Doorbell file
and the Harness the Loop file names, with the spawn ledger's lines parsed once
at load into records."""

from __future__ import annotations

import os
import re
from typing import Any

from .. import args, doorbells, gitcmd, loopfile, loopstate, places
from ..out import Failure

HOSTED = ("Plan-Reviewer", "Coder", "Code-Reviewer")


def usage() -> str:
    return "%s orchestrator --help" % places.command()


# The spawn ledger's lines, as loopstate's builders write them.
SESSION = re.compile(r"^orchestrator session ([0-9]+)$")
SPAWNED = re.compile(r"^(spawn|resume) (\S+) ([0-9]+) session ([0-9]+)(?: reason (.*))?$")
ONCE = re.compile(r"^respawn-once (\S+)$")
RESPAWN = re.compile(r"^respawn (\S+) (.+)$")
RETURNED = re.compile(r"^return (\S+) ([0-9]+) (ok|miss)$")
TOKENS = re.compile(r"^tokens (\S+) ([0-9]+) ([0-9]+)$")


class Spawned:
    """One spawn or resume line."""

    def __init__(self, kind: str, role: str, round_number: int, session: int, reason: str | None) -> None:
        self.kind = kind
        self.role = role
        self.round = round_number
        self.session = session
        self.reason = reason


class Flow:
    """One loop as the Orchestrator sees it: its state file, its Doorbell
    file and the Harness the Loop file names."""

    @classmethod
    def find(cls, values: dict[str, Any], command: str) -> Flow:
        loop = loopfile.find(gitcmd.project_root(os.getcwd()), values["slug"])
        state = loopstate.open_loop(loop, command)
        flow = cls(loop, state)
        if values["harness"] is not None:
            given = args.harness_of(values, usage())
            if given.name != flow.harness.name:
                raise Failure(
                    "--harness %s does not match the Loop file's Harness: %s." % (given.name, flow.harness_label),
                    "Run the command again with --harness %s." % flow.harness.name,
                )
        return flow

    def __init__(self, loop: loopfile.Loop, state: loopstate.State) -> None:
        self.loop = loop
        self.state = state
        self.slug = loop.slug
        self.harness = loop.harness
        self.harness_label = loop.harness_label
        self.place = doorbells.Place(loop.root, loop.slug, loop, state)
        self.last_session = 0
        self.spawns: list[Spawned] = []
        self.once: dict[str, bool] = {}
        self.policies: dict[str, str] = {}
        self.returns: list[tuple[str, int, bool]] = []
        self.counts: dict[tuple[str, int], int] = {}
        for line in state.lines:
            self.read(line)

    # --- the spawn ledger, parsed once at load ---

    def read(self, line: str) -> None:
        """Add one state line to the records it belongs to."""
        match = SESSION.match(line)
        if match:
            self.last_session = int(match.group(1))
            return
        match = SPAWNED.match(line)
        if match:
            record = Spawned(match.group(1), match.group(2), int(match.group(3)), int(match.group(4)),
                             match.group(5))
            self.spawns.append(record)
            if record.kind == "spawn":
                self.once[record.role] = False
            return
        match = ONCE.match(line)
        if match:
            self.once[match.group(1)] = True
            return
        match = RESPAWN.match(line)
        if match:
            self.policies[match.group(1)] = match.group(2).strip()
            return
        match = RETURNED.match(line)
        if match:
            self.returns.append((match.group(1), int(match.group(2)), match.group(3) == "ok"))
            return
        match = TOKENS.match(line)
        if match:
            self.counts[(match.group(1), int(match.group(2)))] = int(match.group(3))

    def append(self, line: str) -> None:
        """Append a built state line and add it to the records."""
        self.state.append(line)
        self.read(line)

    def session(self) -> int:
        return self.last_session

    def out(self, role: str, session: int | None = None) -> tuple[str, int] | None:
        """(kind, round) of the Role's last spawn or resume in the session,
        or None: whether a live subagent of that Role is out."""
        session = self.session() if session is None else session
        last: tuple[str, int] | None = None
        for record in self.spawns:
            if record.role == role and record.session == session:
                last = (record.kind, record.round)
        return last

    def policy(self, role: str) -> str | None:
        """The Role's Respawn policy: its last respawn line, else never for a
        reviewer and None (unset) for the Coder."""
        found = self.policies.get(role)
        if found is None and role != "Coder":
            return "never"
        return found

    def once_pending(self, role: str) -> bool:
        """Whether a respawn-once request for the Role waits for its next
        spawn."""
        return self.once.get(role, False)

    def spawned_before(self, role: str) -> bool:
        """Whether an earlier session spawned or resumed the Role."""
        session = self.session()
        return any(r.role == role and r.session < session for r in self.spawns)

    def spawn_reason(self, role: str, number: int) -> str | None:
        """The reason of the Role's last spawn for the round in this
        session, or None."""
        session = self.session()
        found: str | None = None
        for record in self.spawns:
            if record.kind == "spawn" and record.role == role and record.round == number and record.session == session:
                found = record.reason
        return found

    def tokens(self, role: str, number: int) -> int | None:
        return self.counts.get((role, number))

    def any_spawn(self) -> bool:
        """Whether this session has recorded a spawn or resume."""
        session = self.session()
        return bool(session) and any(r.session == session for r in self.spawns)

    def acted(self, role: str, number: int) -> bool:
        return (role, number, True) in self.returns

    def misses(self, role: str, number: int) -> int:
        return self.returns.count((role, number, False))

    def rung(self) -> int:
        return self.place.planner_round()

    def position(self) -> loopstate.Position:
        return self.place.position()

    def done(self, role: str, number: int) -> bool:
        if role == "Coder":
            return self.state.code_mark("end", number) is not None
        kind = "plan" if role == "Plan-Reviewer" else "code"
        return self.state.review(kind, number) is not None

    def path(self, name: str) -> str:
        return self.loop.path(name)

    # --- the lines printed ---

    def command(self, text: str) -> str:
        return "%s %s" % (places.command(), text)

    def return_command(self, role: str) -> str:
        return self.command("orchestrator return --role %s --slug %s --harness %s" % (role, self.slug,
                                                                                      self.harness.name))

    def ring_command(self) -> str:
        return doorbells.ring_command("Orchestrator", self.harness, self.slug)

    def check_command(self, role: str) -> str:
        if role == "Coder":
            return "coder check --slug %s --write" % self.slug
        return "review check --role %s --slug %s --write" % (role, self.slug)
