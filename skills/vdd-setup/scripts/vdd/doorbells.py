"""The Doorbell machinery the Doorbell command, the Orchestrator, the
reviews and the Codex Stop hook share: the Doorbell file, its lines and the
Role's state file, the wait and its marker, the Codex armed file and the
command lines a Role is told to run.

A loop's tracker directory is .scratch/<slug>/, the loop --slug names or
the lookup finds. The Doorbell file, <tracker>/doorbells, holds one line per ring,
"<HH:MM:SS> to: <Role> <Doorbell line>", LF, append-only, after a version
header. Each Role's state file, <tracker>/doorbell-state-<role>, records what
that Role has handled: how many lines addressed to it, and the sender and
round of each Doorbell it acted on. A running wait keeps
<tracker>/doorbell-wait-<role> fresh, so the Role holds one wait at a time.
The model carries no count, no record and no wait.
"""

from __future__ import annotations

import os
import re
import time
from typing import Callable

from . import gitcmd, loopfile, loopstate, places, textfile
from .harness import Harness
from .out import Failure, Output


ROLES = ("Planner", "Orchestrator")
OTHER = {"Planner": "Orchestrator", "Orchestrator": "Planner"}

FILE_NAME = "doorbells"
HEADER_PREFIX = "# vdd doorbells "
FILE_VERSION = "1"
STATE_PREFIX = "vdd doorbell-state "
STATE_VERSION = "1"
ARMED_PREFIX = "vdd codex-armed "
ARMED_VERSION = "1"
WAIT_PREFIX = "vdd doorbell-wait "
WAIT_VERSION = "1"

ADDRESS = re.compile(r"^([0-9]{2}:[0-9]{2}:[0-9]{2}) to: (Planner|Orchestrator) (.*)$")
ROUND = r"(?P<round>[1-9][0-9]*)"
REVIEW_WRITTEN = re.compile(
    r"^VDD Plan-Reviewer: PLAN-REVIEW\.md written, round " + ROUND
    + r": [0-9]+ blocker, [0-9]+ major, [0-9]+ minor\. Read it\.$"
)
REVIEW_SIGNED_OFF = re.compile(r"^VDD Plan-Reviewer: PLAN-REVIEW\.md SIGNED OFF, round " + ROUND + r"\.$")
REVIEW_RESTART = re.compile(r"^VDD Plan-Reviewer: PLAN-REVIEW\.md written, round " + ROUND + r"\. Read it\.$")
SIGNED_OFF_NEXT = "Nothing to wait for: the plan Loop is over. Go on as your skill says."
# A Codex thread id: CODEX_THREAD_ID, and session_id in the hook input.
THREAD_ID = re.compile(r"^[0-9A-Za-z_-]+$")

# How often a wait reads the Doorbell file and how long it waits in all; the
# tests shorten both.
POLL_SECONDS = 10.0
TIMEOUT_SECONDS = 2700.0
# How long a read retries on PermissionError: on Windows a sharing violation
# and a denial look alike.
LOCK_RETRY_SECONDS = 2.0
# A wait marker untouched for this many polls, plus the grace, is stale.
STALE_POLLS = 3
STALE_GRACE_SECONDS = 5.0


class Doorbell:
    """A Doorbell line, parsed: who sent it and for which round."""

    def __init__(self, text: str, sender: str, round_number: int, signed_off: bool = False) -> None:
        self.text = text
        self.sender = sender
        self.round = round_number
        self.signed_off = signed_off

    def key(self) -> tuple[str, int]:
        return (self.sender, self.round)


def parse(text: str, to_role: str, tracker: str) -> Doorbell | None:
    """The Doorbell text holds when addressed to to_role, or None when it
    matches no template for that Role."""
    if to_role == "Orchestrator":
        planner = re.compile(
            r"^VDD Planner: " + re.escape(tracker) + r"/ ready, round " + ROUND
            + r"\. Read spec\.md and issues/\.$"
        )
        match = planner.match(text)
        return Doorbell(text, "Planner", int(match.group("round"))) if match else None
    for pattern, signed in ((REVIEW_WRITTEN, False), (REVIEW_SIGNED_OFF, True), (REVIEW_RESTART, False)):
        match = pattern.match(text)
        if match:
            return Doorbell(text, "Plan-Reviewer", int(match.group("round")), signed)
    return None


class Entry:
    """One line of the Doorbell file addressed to a Role."""

    def __init__(self, number: int, raw: str, text: str, doorbell: Doorbell | None) -> None:
        self.number = number
        self.raw = raw
        self.text = text
        self.doorbell = doorbell


class Place:
    """The files of one loop: its tracker directory, the Doorbell file, the
    state files."""

    def __init__(self, root: str, slug: str, loop: loopfile.Loop | None = None) -> None:
        self.root = root
        self.slug = slug
        self.tracker = ".scratch/" + slug
        self.dir = loopfile.tracker_dir(root, slug)
        self.file = os.path.join(self.dir, FILE_NAME)
        # The checked Loop, when the Place is built from one; the Codex Stop
        # hook builds it from a slug alone.
        self.loop = loop

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
        if not self.require_loop().is_open():
            raise loopstate.closed_loop(self.slug, ", so %s would never be answered" % what)

    def state_path(self, role: str) -> str:
        return os.path.join(self.dir, "doorbell-state-" + role.lower())

    def entries(self, role: str, retry: float = 0.0) -> list[Entry]:
        """Every line addressed to role, oldest first."""
        lines = textfile.lines(self.file, retry)
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
        lines = textfile.lines(self.state_path(role), LOCK_RETRY_SECONDS)
        state = State()
        if not lines:
            return state
        if textfile.check_header(self.state_path(role), lines, STATE_PREFIX, (STATE_VERSION,)) is None:
            raise Failure(
                "%s is not a Doorbell state file this tool wrote." % self.state_path(role),
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
            self.state_path(role), "\n".join(lines) + "\n", "the Doorbell state file %s" % self.state_path(role),
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


# --- the command lines ---

# Every command the tool prints for a Role to run names the loop it ran on.


def take_command(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    """The take command, naming the copy at entry (the running one by default)."""
    return "%s doorbell take --role %s --harness %s --slug %s" % (places.command(entry), role, harness.name, slug)


def wait_command(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    return "%s doorbell wait --role %s --harness %s --slug %s" % (places.command(entry), role, harness.name, slug)


def ring_command(role: str, harness: Harness, slug: str) -> str:
    return "%s doorbell ring --role %s --harness %s --slug %s --write" % (places.command(), role, harness.name, slug)


def paste_command(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    return '%s doorbell take --role %s --pasted "<the line the user pastes>" --harness %s --slug %s' % (
        places.command(entry), role, harness.name, slug)


def wait_next(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    return harness.wait_next(role, wait_command(role, harness, slug, entry), paste_command(role, harness, slug, entry))


def mark_handled(place: Place, role: str, out: Output) -> None:
    """Record every line addressed to role so far as handled, as take does,
    without printing a Doorbell: the Orchestrator's start acts on what was
    rung before it from the state, so the relay after it names the wait
    rather than a Doorbell already acted on."""
    entries = place.entries(role, LOCK_RETRY_SECONDS)
    state = place.load_state(role)
    beyond, _ = pending(entries, state)
    if not beyond:
        return
    tell_not_doorbells(out, beyond)
    for entry in beyond:
        if entry.doorbell:
            state.handled.add(entry.doorbell.key())
    state.count = len(entries)
    place.save_state(role, state)


def last_plan_review(place: Place) -> loopstate.Review | None:
    """The last plan review the state file records, or None."""
    return loopstate.State(place.dir).last_review("plan")


def plan_signed_off(place: Place) -> bool:
    """The last plan review signed off and the Planner has rung no round
    after it: the plan Loop is over and neither Role waits."""
    review = last_plan_review(place)
    if review is None or not review.signed_off:
        return False
    rung = [e.doorbell.round for e in place.entries("Orchestrator") if e.doorbell]
    return not rung or max(rung) <= review.round


# --- the wait ---


def timings() -> tuple[float, float]:
    poll = float(os.environ.get("VDD_WAIT_POLL_SECONDS") or POLL_SECONDS)
    total = float(os.environ.get("VDD_WAIT_TIMEOUT_SECONDS") or TIMEOUT_SECONDS)
    return poll, total


def watch(place: Place, role: str, floor: int = 0, beat: Callable[[], None] | None = None) -> bool:
    """Wait until a new Doorbell addressed to role is pending. Returns True on
    one, False on the timeout. Raises Failure or OSError when the file cannot
    be read. beat, when given, runs once per poll."""
    poll, total = timings()
    deadline = time.monotonic() + total
    while True:
        if beat:
            beat()
        entries = place.entries(role, LOCK_RETRY_SECONDS)
        state = place.load_state(role)
        state.count = max(state.count, floor)
        _, new = pending(entries, state)
        if new:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(max(0.0, min(poll, deadline - time.monotonic())))


# --- the wait marker ---
#
# A running wait keeps <tracker>/doorbell-wait-<role> fresh: a version line,
# then the wait's own token and its poll interval. It touches the file once a
# poll while the token is its own and removes it on exit, so take and ring
# know a wait of the Role still runs and never name a second one. A marker
# older than a few polls is stale: its wait was killed without cleaning up.


def marker_path(place: Place, role: str) -> str:
    return os.path.join(place.dir, "doorbell-wait-" + role.lower())


def read_marker(place: Place, role: str) -> tuple[str, float, float] | None:
    """(token, poll seconds, age in seconds), or None when there is no
    readable marker."""
    path = marker_path(place, role)
    try:
        lines = textfile.lines(path, LOCK_RETRY_SECONDS)
        age = time.time() - os.path.getmtime(path)
    except OSError:
        return None
    if lines is None or textfile.check_header(path, lines, WAIT_PREFIX, (WAIT_VERSION,)) is None:
        return None
    parts = lines[1].split() if len(lines) > 1 else []
    try:
        poll = float(parts[1]) if len(parts) == 2 else None
    except ValueError:
        poll = None
    if poll is None:
        return None
    return parts[0], poll, age


def wait_runs(place: Place, role: str) -> bool:
    marker = read_marker(place, role)
    if marker is None:
        return False
    _, poll, age = marker
    return age <= STALE_POLLS * poll + STALE_GRACE_SECONDS


def wait_or_hold(place: Place, role: str, harness: Harness) -> str:
    """The Next: step that waits: the Harness's wait, or, while a wait of the
    Role still runs, ending the turn; after the plan Sign-off, none."""
    if plan_signed_off(place):
        return SIGNED_OFF_NEXT
    if harness.name != "codex" and wait_runs(place, role):
        return (
            "Your wait for the %s's Doorbell still runs and wakes you when one arrives: end your turn, "
            "and start no other wait." % OTHER[role]
        )
    return wait_next(role, harness, place.slug)


def own_marker(place: Place, role: str, token: str) -> bool:
    try:
        lines = textfile.lines(marker_path(place, role)) or []
    except OSError:
        return False
    return len(lines) > 1 and lines[1].split()[:1] == [token]


def clear_marker(place: Place, role: str, token: str | None = None) -> None:
    """Remove the marker: any marker, or with token only the wait's own."""
    if token is not None and not own_marker(place, role, token):
        return
    try:
        os.remove(marker_path(place, role))
    except OSError:
        pass


class Marker:
    """The marker of the wait this process runs."""

    def __init__(self, place: Place, role: str, poll: float) -> None:
        self.place = place
        self.role = role
        self.token = "%d-%s" % (os.getpid(), os.urandom(6).hex())
        data = "%s%s\n%s %s\n" % (WAIT_PREFIX, WAIT_VERSION, self.token, poll)
        try:
            os.makedirs(place.dir, exist_ok=True)
            textfile.write_text(marker_path(place, role), data)
        except OSError:
            pass

    def beat(self) -> None:
        if own_marker(self.place, self.role, self.token):
            try:
                os.utime(marker_path(self.place, self.role), None)
            except OSError:
                pass

    def clear(self) -> None:
        clear_marker(self.place, self.role, self.token)


def timeout_next(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    return (
        "Ask the user whether to keep waiting. On yes: %s On no, ask the user to paste the %s's next "
        "Doorbell here, then run: %s"
        % (wait_next(role, harness, slug, entry), OTHER[role], paste_command(role, harness, slug, entry))
    )


def hand_relay(role: str, harness: Harness, slug: str) -> str:
    return (
        "Tell the user in one line that this wait cannot run, so they paste the %s's next Doorbell here. "
        "With the pasted line, run: %s" % (OTHER[role], paste_command(role, harness, slug))
    )


def armed_path(place: Place, thread: str) -> str:
    return os.path.join(place.dir, loopfile.ARMED_PREFIX + thread)


def claim_path(place: Place, thread: str) -> str:
    """The claim marker of the Codex Stop hook for the thread's armed file."""
    return os.path.join(place.dir, loopfile.CLAIM_PREFIX + thread)


def arm(place: Place, role: str, harness: Harness) -> None:
    thread = os.environ.get("CODEX_THREAD_ID", "")
    if not THREAD_ID.match(thread):
        raise Failure(
            "Cannot arm the Codex Stop hook: CODEX_THREAD_ID is empty or not a thread id.",
            hand_relay(role, harness, place.slug),
        )
    try:
        state = place.load_state(role)
        entries = place.entries(role, LOCK_RETRY_SECONDS)
    except OSError as error:
        raise Failure("The wait could not read its files: %s" % error, hand_relay(role, harness, place.slug))
    count = min(state.count, len(entries))
    data = "%s%s\n%s %d\n" % (ARMED_PREFIX, ARMED_VERSION, role, count)
    try:
        os.makedirs(place.dir, exist_ok=True)
        # A claim marker a killed hook left would block this wait.
        try:
            os.remove(claim_path(place, thread))
        except FileNotFoundError:
            pass
        textfile.write_text(armed_path(place, thread), data)
    except OSError as error:
        raise Failure("Cannot write the armed file: %s" % error, hand_relay(role, harness, place.slug))
