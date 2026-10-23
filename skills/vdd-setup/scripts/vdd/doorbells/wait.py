"""The wait for a Doorbell, its marker, and arming the Codex Stop hook (the
armed file itself belongs to armed.py).

A running wait keeps <tracker>/doorbell-wait-<role> fresh, so the Role holds
one wait at a time. The wait returns its outcome as a fact, Found or Timeout,
and each caller words it: `doorbell wait` naming the running copy, the Codex
Stop hook the Shared one (ADR 0008).
"""

from __future__ import annotations

import os
import re
import time
from typing import Callable, Union

from .. import armed, seams, textfile
from ..harness import Harness
from ..out import Failure
from .commands import paste_command, take_command, wait_next
from .files import Place, pending, plan_signed_off
from .lines import OTHER, Entry


WAIT_PREFIX = "vdd doorbell-wait "
WAIT_VERSION = "1"
SIGNED_OFF_NEXT = "Nothing to wait for: the plan Loop is over. Go on as your skill says."
# A Codex thread id: CODEX_THREAD_ID, and session_id in the hook input.
THREAD_ID = re.compile(r"^[0-9A-Za-z_-]+$")

# How often a wait reads the Doorbell file and how long it waits in all; the
# tests shorten both.
POLL_SECONDS = 10.0
TIMEOUT_SECONDS = 2700.0
# A wait marker untouched for this many polls, plus the grace, is stale.
STALE_POLLS = 3
STALE_GRACE_SECONDS = 5.0


def timings() -> tuple[float, float]:
    """(poll, total) seconds of a wait, each from its test seam."""
    return (seams.seconds("VDD_WAIT_POLL_SECONDS", POLL_SECONDS),
            seams.seconds("VDD_WAIT_TIMEOUT_SECONDS", TIMEOUT_SECONDS))


class Found:
    """A wait's outcome: a new Doorbell is pending, the entry in the
    Doorbell file and the command that takes it."""

    def __init__(self, doorbell: Entry, take: str) -> None:
        self.doorbell = doorbell
        self.take = take


class Timeout:
    """A wait's outcome: no Doorbell came in time, and the step after it."""

    def __init__(self, next_step: str) -> None:
        self.next_step = next_step


Outcome = Union[Found, Timeout]


def wait_for(place: Place, role: str, harness: Harness, entry: str | None = None, floor: int = 0,
             beat: Callable[[], None] | None = None) -> Outcome:
    """Wait until a new Doorbell addressed to role is pending, or the timeout.
    The commands in the outcome and in a refusal name the copy at entry (the
    running one by default). floor raises the handled count, as the armed
    file records it; beat, when given, runs once per poll. Raises Failure
    when the files cannot be read."""
    poll, total = timings()
    deadline = time.monotonic() + total
    while True:
        if beat:
            beat()
        try:
            entries = place.entries(role)
            state = place.load_state(role)
        except OSError as error:
            raise Failure("The wait could not read its files: %s" % textfile.described(error),
                          hand_relay(role, harness, place.slug, entry))
        state.count = max(state.count, floor)
        _, new = pending(entries, state)
        if new:
            return Found(new[-1], take_command(role, harness, place.slug, entry))
        if time.monotonic() >= deadline:
            return Timeout(timeout_next(role, harness, place.slug, entry))
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
        lines = textfile.lines(path)
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
    if not harness.waits_through_stop_hook() and wait_runs(place, role):
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


def hand_relay(role: str, harness: Harness, slug: str, entry: str | None = None) -> str:
    return (
        "Tell the user in one line that this wait cannot run, so they paste the %s's next Doorbell here. "
        "With the pasted line, run: %s" % (OTHER[role], paste_command(role, harness, slug, entry))
    )


def arm(place: Place, role: str, harness: Harness) -> None:
    thread = os.environ.get("CODEX_THREAD_ID", "")
    if not THREAD_ID.match(thread):
        raise Failure(
            "Cannot arm the Codex Stop hook: CODEX_THREAD_ID is empty or not a thread id.",
            hand_relay(role, harness, place.slug),
        )
    try:
        state = place.load_state(role)
        entries = place.entries(role)
    except OSError as error:
        raise Failure("The wait could not read its files: %s" % textfile.described(error),
                      hand_relay(role, harness, place.slug))
    try:
        armed.arm(place.dir, thread, role, min(state.count, len(entries)))
    except OSError as error:
        raise Failure("Cannot write the armed file: %s" % textfile.described(error),
                      hand_relay(role, harness, place.slug))
