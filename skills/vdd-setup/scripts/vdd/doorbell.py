"""The Doorbell between the Planner and the Orchestrator: ring, wait, take.

The Doorbell file, <tracker>/doorbells, holds one line per ring,
"<HH:MM:SS> to: <Role> <Doorbell line>", LF, append-only, after a version
header. Each Role's state file, <tracker>/doorbell-state-<role>, records what
that Role has handled: how many lines addressed to it, and the sender and
round of each Doorbell it acted on. A running wait keeps
<tracker>/doorbell-wait-<role> fresh, so the Role holds one wait at a time.
The model carries no count, no record and no wait.
"""

import os
import re
import signal
import time

from . import args, loopfile, places, textfile
from .out import Failure, Output, refused

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

    def __init__(self, text, sender, round_number, signed_off=False):
        self.text = text
        self.sender = sender
        self.round = round_number
        self.signed_off = signed_off

    def key(self):
        return (self.sender, self.round)


def templates_to(role, tracker):
    """The templates of a Doorbell addressed to role, as text for the user."""
    if role == "Orchestrator":
        return ["VDD Planner: %s/ ready, round <n>. Read spec.md and issues/." % tracker]
    return [
        "VDD Plan-Reviewer: PLAN-REVIEW.md written, round <n>: <b> blocker, <m> major, <p> minor. Read it.",
        "VDD Plan-Reviewer: PLAN-REVIEW.md SIGNED OFF, round <n>.",
        "VDD Plan-Reviewer: PLAN-REVIEW.md written, round <n>. Read it.",
    ]


def parse(text, to_role, tracker):
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

    def __init__(self, number, raw, text, doorbell):
        self.number = number
        self.raw = raw
        self.text = text
        self.doorbell = doorbell


class Place:
    """The files of one loop: LOOP.md's tracker, the Doorbell file, the
    state files."""

    def __init__(self, root=None):
        self.loop = loopfile.require(root or os.getcwd())
        self.tracker = self.loop.tracker
        self.dir = self.loop.tracker_dir()
        self.file = os.path.join(self.dir, FILE_NAME)

    def state_path(self, role):
        return os.path.join(self.dir, "doorbell-state-" + role.lower())

    def entries(self, role, retry=0.0):
        """Every line addressed to role, oldest first."""
        lines = textfile.lines(self.file, retry)
        if lines is None:
            return []
        if lines and lines[0].startswith(HEADER_PREFIX):
            version = lines[0][len(HEADER_PREFIX):].strip()
            if version != FILE_VERSION:
                raise Failure(
                    "%s has format version %s, which this copy of the VDD tool does not know." % (self.file, version),
                    "Tell the user this copy of the VDD tool is out of date and to rerun Setup.",
                )
        out = []
        for number, line in enumerate(lines, 1):
            match = ADDRESS.match(line)
            if not match or match.group(2) != role:
                continue
            text = match.group(3)
            out.append(Entry(number, line, text, parse(text, role, self.tracker)))
        return out

    def load_state(self, role):
        lines = textfile.lines(self.state_path(role), LOCK_RETRY_SECONDS)
        state = State()
        if not lines:
            return state
        if not lines[0].startswith(STATE_PREFIX):
            raise Failure(
                "%s is not a Doorbell state file this tool wrote." % self.state_path(role),
                "Tell the user the file is damaged; deleting it makes the Role re-read every Doorbell. Then stop.",
            )
        version = lines[0][len(STATE_PREFIX):].strip()
        if version != STATE_VERSION:
            raise Failure(
                "%s has format version %s, which this copy of the VDD tool does not know."
                % (self.state_path(role), version),
                "Tell the user this copy of the VDD tool is out of date and to rerun Setup.",
            )
        for line in lines[1:]:
            parts = line.split()
            if len(parts) == 2 and parts[0] == "count" and parts[1].isdigit():
                state.count = int(parts[1])
            elif len(parts) == 3 and parts[0] == "handled" and parts[2].isdigit():
                state.handled.add((parts[1], int(parts[2])))
        return state

    def save_state(self, role, state):
        """Write the state file whole, or raise a refused Failure and record
        nothing: a Doorbell is printed only once it is recorded as handled."""
        lines = [STATE_PREFIX + STATE_VERSION, "count %d" % state.count]
        lines += ["handled %s %d" % key for key in sorted(state.handled)]
        try:
            textfile.write(self.state_path(role), ("\n".join(lines) + "\n").encode("utf-8"))
        except OSError as error:
            raise refused(
                [
                    "Could not write the Doorbell state file %s: %s" % (self.state_path(role), error),
                    "Nothing was recorded as handled.",
                ],
                "Otherwise tell the user the Doorbell state file cannot be written, and stop.",
            )

    def append(self, role, text):
        os.makedirs(self.dir, exist_ok=True)
        new = not os.path.exists(self.file) or os.path.getsize(self.file) == 0
        data = ""
        if new:
            data += HEADER_PREFIX + FILE_VERSION + "\n"
        data += "%s to: %s %s\n" % (time.strftime("%H:%M:%S"), role, text)
        with open(self.file, "ab") as handle:
            handle.write(data.encode("utf-8"))


class State:
    def __init__(self):
        self.count = 0
        self.handled = set()


def pending(entries, state):
    """The lines beyond the handled count, and of them the Doorbells not yet
    handled."""
    beyond = entries[state.count:] if state.count <= len(entries) else []
    new = [e for e in beyond if e.doorbell and e.doorbell.key() not in state.handled]
    return beyond, new


def tell_not_doorbells(out, entries):
    for entry in entries:
        if entry.doorbell is None:
            out.tell(
                "Line %d of the Doorbell file is not a Doorbell, so it was not acted on: %s"
                % (entry.number, entry.text)
            )


# --- the command lines ---

def command(group_args, harness):
    return "%s doorbell %s --harness %s" % (places.command(), group_args, harness.name)


def take_command(role, harness, entry=None):
    """The take command, naming the copy at entry (the running one by default)."""
    return "%s doorbell take --role %s --harness %s" % (places.command(entry), role, harness.name)


def wait_command(role, harness, entry=None):
    return "%s doorbell wait --role %s --harness %s" % (places.command(entry), role, harness.name)


def ring_command(role, line, harness):
    return command('ring --role %s --line "%s"' % (role, line), harness) + " --write"


def paste_command(role, harness, entry=None):
    return '%s doorbell take --role %s --pasted "<the line the user pastes>" --harness %s' % (
        places.command(entry), role, harness.name)


def wait_next(role, harness, entry=None):
    return harness.wait_next(role, wait_command(role, harness, entry), paste_command(role, harness, entry))


# --- the commands ---

HELP = [
    "doorbell ring --role <Planner|Orchestrator> --line \"<Doorbell>\" --harness <h> --write",
    "  Ring the other Role: append the Doorbell line to the Doorbell file, addressed to it. Run it in the",
    "  foreground. It refuses a line that matches no Doorbell template for your Role and names the template.",
    "  Without --write it prints what it would append and changes nothing; ringing the same line twice",
    "  appends it once.",
    "",
    "doorbell wait --role <Planner|Orchestrator> --harness <h>",
    "  Wait for a Doorbell addressed to your Role. Start it only as a Next: line names it. It reads the",
    "  Doorbell file every 10 seconds and exits when a new Doorbell is waiting, naming the take command,",
    "  or prints TIMEOUT after 45 minutes. While it runs, ring and take name no second wait: their Next:",
    "  says your wait still runs. On codex it arms the Stop hook instead and returns at once.",
    "",
    "doorbell take --role <Planner|Orchestrator> --harness <h> [--pasted \"<line>\"] [--restart | --resumed]",
    "  Take the newest Doorbell addressed to your Role and record it, and every line before it, as handled.",
    "  Run it in the foreground on a wake, or with --pasted for a line the user pasted. A Doorbell already",
    "  handled (same sender and round) is reported and not acted on twice. A line that is not a Doorbell is",
    "  reported for the user and never acted on.",
    "  --restart: the Orchestrator starting a Session before the plan Loop signs off. It clears what the",
    "  Orchestrator handled before, since a Plan-Reviewer an earlier Session started is gone. With no",
    "  PLAN-REVIEW.md it names the newest Planner Doorbell to act on, or the wait; with one, it compares the",
    "  Doorbell file with its Round line and names the relay to ring or the Doorbell to act on.",
    "  --resumed: the Planner's first take in a resumed Session. A wait an earlier Session started wakes",
    "  that Session, so it names a wait of your own; what you handled before stays handled.",
    "  Once PLAN-REVIEW.md is signed off and the Planner has rung no later round, take and ring name no",
    "  wait: the plan Loop is over.",
    "",
    "--harness takes claude-code, codex, cursor, copilot-cli or generic: the Harness LOOP.md's Harness: line",
    "names (generic when it has none). Run every command from the repository root.",
]

SPEC = {
    "role": args.VALUE,
    "line": args.VALUE,
    "harness": args.VALUE,
    "write": args.FLAG,
    "pasted": args.VALUE,
    "restart": args.FLAG,
    "resumed": args.FLAG,
}


def usage():
    return "%s doorbell --help" % places.command()


def run(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        out = Output()
        for line in HELP:
            out.line(line)
        return out.finish("Run the command your skill or the last Next: line names.")
    sub, rest = argv[0], argv[1:]
    if sub not in ("ring", "wait", "take"):
        raise Failure(
            [
                "Unknown command: doorbell %s" % sub,
                "This copy of the VDD tool may be older than the skill that called it: rerun Setup.",
            ],
            "Tell the user this copy of the VDD tool is out of date and to rerun Setup, then retry.",
        )
    values = args.parse(rest, SPEC, usage())
    if values["help"]:
        return run(["--help"])
    harness = args.harness_of(values, usage())
    role = values["role"]
    if role not in ROLES:
        raise Failure("--role takes Planner or Orchestrator.", "Run %s for the usage." % usage())
    if sub == "ring":
        args.require(values, ["line"], usage())
        return ring(role, values["line"], harness, values["write"])
    if sub == "wait":
        return wait(role, harness)
    return take(role, harness, values["pasted"], values["restart"], values["resumed"])


def ring(role, line, harness, write):
    place = Place()
    to = OTHER[role]
    doorbell = parse(line, to, place.tracker)
    if doorbell is None:
        lines = ["Not a Doorbell the %s rings: %s" % (role, line), "The %s rings:" % role]
        lines += ["  " + t for t in templates_to(to, place.tracker)]
        raise Failure(lines, "Fill in the template exactly and ring again. Nothing was written.")
    out = Output()
    last = place.entries(to)
    already = bool(last) and last[-1].text == line
    if not write:
        out.line("Would append, addressed to the %s: %s" % (to, line) if not already else "Already rung: %s" % line)
        return out.finish("Run the same command with --write.")
    if already:
        out.line("Already rung: the newest line to the %s is this Doorbell." % to)
    else:
        try:
            place.append(to, line)
        except OSError as error:
            raise refused(
                "Could not write the Doorbell file %s: %s" % (place.file, error),
                "Otherwise print the Doorbell line for the user to paste into the %s's Session, and stop." % to,
            )
        out.line("Rung: the Doorbell file now holds it, addressed to the %s." % to)
    if role == "Planner" and doorbell.round == 1:
        launch = harness.orchestrator_launch()
        out.tell("Start the Orchestrator now: %s." % launch)
        if harness.name == "generic":
            out.tell("Paste the Doorbell below into it once it is up.")
        else:
            out.tell(
                "It picks up the Doorbell below from the Doorbell file; paste it in only if it does not "
                "start the review."
            )
        out.tell(line)
    else:
        out.tell("If the %s's Session does not wake, paste this into it: %s" % (to, line))
    entries = place.entries(role)
    _, new = pending(entries, place.load_state(role))
    if new:
        return out.finish("A Doorbell for you is already waiting. Run: %s" % take_command(role, harness))
    if role == "Orchestrator" and doorbell.signed_off:
        return out.finish(SIGNED_OFF_NEXT)
    return out.finish(wait_or_hold(place, role, harness))


def take(role, harness, pasted, restart, resumed=False):
    place = Place()
    if restart:
        if role != "Orchestrator":
            raise Failure("--restart is the Orchestrator's.", "Run take without --restart.")
        return take_restart(place, harness)
    if resumed:
        if role != "Planner":
            raise Failure(
                "--resumed is the Planner's.",
                "Place the Workflow as your skill says; your take on a start is take --restart.",
            )
        # A wait an earlier Session started wakes that Session, not this one.
        clear_marker(place, role)
    entries = place.entries(role, LOCK_RETRY_SECONDS)
    state = place.load_state(role)
    out = Output()
    if pasted is not None:
        return take_pasted(place, role, harness, entries, state, pasted.strip(), out)
    beyond, new = pending(entries, state)
    tell_not_doorbells(out, beyond)
    for entry in beyond:
        if entry.doorbell:
            state.handled.add(entry.doorbell.key())
    state.count = len(entries)
    place.save_state(role, state)
    if not new:
        out.line("No new Doorbell for the %s." % role)
        return out.finish(wait_or_hold(place, role, harness))
    out.line("Doorbell: %s" % new[-1].text)
    return out.finish("Act on this Doorbell as your skill says.")


def take_pasted(place, role, harness, entries, state, line, out):
    doorbell = parse(line, role, place.tracker)
    if doorbell is None:
        out.tell("This is not a Doorbell for the %s, so it was not acted on: %s" % (role, line))
        return out.finish(after_nothing(place, role, harness, entries, state))
    if doorbell.key() in state.handled:
        out.line("Already handled, nothing to do: %s" % line)
        return out.finish(after_nothing(place, role, harness, entries, state))
    state.handled.add(doorbell.key())
    for index, entry in enumerate(entries):
        if index >= state.count and entry.doorbell and entry.doorbell.key() == doorbell.key():
            state.count = index + 1
    place.save_state(role, state)
    out.line("Doorbell: %s" % line)
    return out.finish("Act on this Doorbell as your skill says.")


def after_nothing(place, role, harness, entries, state):
    _, new = pending(entries, state)
    if new:
        return "A Doorbell for you is waiting in the Doorbell file. Run: %s" % take_command(role, harness)
    return wait_or_hold(place, role, harness)


def review_round(place):
    """(lines of PLAN-REVIEW.md or None, its Round number or None)."""
    review = textfile.lines(os.path.join(place.dir, "PLAN-REVIEW.md"))
    for line in review or []:
        match = re.match(r"^Round ([0-9]+)\s*$", line)
        if match:
            return review, int(match.group(1))
    return review, None


def plan_signed_off(place):
    """PLAN-REVIEW.md opens with SIGNED OFF and the Planner has rung no round
    after its Round: the plan Loop is over and neither Role waits."""
    review, round_number = review_round(place)
    if not review or review[0].strip() != "SIGNED OFF" or round_number is None:
        return False
    rung = [e.doorbell.round for e in place.entries("Orchestrator") if e.doorbell]
    return not rung or max(rung) <= round_number


def take_restart(place, harness):
    """The Orchestrator's start: placing the Workflow clears the handled
    record and the count, because a hosted Role that a Doorbell started
    before the restart is gone and that Doorbell has to be acted on again."""
    role = "Orchestrator"
    entries = place.entries(role, LOCK_RETRY_SECONDS)
    before = place.load_state(role)
    state = State()
    out = Output()
    review, round_number = review_round(place)
    if review is not None and round_number is None:
        raise Failure(
            "PLAN-REVIEW.md has no Round line in %s." % place.dir,
            "Place the Workflow again from the files, as your skill says; --restart is for the plan Loop open.",
        )
    tell_not_doorbells(out, entries[before.count:])
    planner = [e for e in entries if e.doorbell]
    state.count = len(entries)
    newest = planner[-1] if planner else None
    if newest:
        state.handled.add(newest.doorbell.key())
    place.save_state(role, state)
    # A wait an earlier Session started wakes that Session, not this one.
    clear_marker(place, role)
    if newest and (round_number is None or newest.doorbell.round > round_number):
        out.line("Doorbell: %s" % newest.text)
        if round_number is None:
            out.line("No PLAN-REVIEW.md yet, so no review answers it.")
        else:
            out.line(
                "The Planner rang round %d after PLAN-REVIEW.md's round %d." % (newest.doorbell.round, round_number))
        return out.finish("Spawn the Plan-Reviewer fresh with this Doorbell, as your skill says.")
    if round_number is None:
        out.line("No Planner Doorbell in the Doorbell file yet.")
        return out.finish(wait_next(role, harness))
    relay = "VDD Plan-Reviewer: PLAN-REVIEW.md written, round %d. Read it." % round_number
    if newest:
        out.line("The newest Planner Doorbell, round %d, is already handled." % newest.doorbell.round)
    else:
        out.line("No Planner Doorbell in the Doorbell file.")
    return out.finish("Relay the restart line to the Planner. Run: %s" % ring_command(role, relay, harness))


# --- the wait ---

def timings():
    poll = float(os.environ.get("VDD_WAIT_POLL_SECONDS") or POLL_SECONDS)
    total = float(os.environ.get("VDD_WAIT_TIMEOUT_SECONDS") or TIMEOUT_SECONDS)
    return poll, total


def watch(place, role, floor=0, beat=None):
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

def marker_path(place, role):
    return os.path.join(place.dir, "doorbell-wait-" + role.lower())


def read_marker(place, role):
    """(token, poll seconds, age in seconds), or None when there is no
    readable marker."""
    path = marker_path(place, role)
    try:
        lines = textfile.lines(path, LOCK_RETRY_SECONDS)
        age = time.time() - os.path.getmtime(path)
    except OSError:
        return None
    if not lines or not lines[0].startswith(WAIT_PREFIX):
        return None
    version = lines[0][len(WAIT_PREFIX):].strip()
    if version != WAIT_VERSION:
        raise Failure(
            "%s has format version %s, which this copy of the VDD tool does not know." % (path, version),
            "Tell the user this copy of the VDD tool is out of date and to rerun Setup.",
        )
    parts = lines[1].split() if len(lines) > 1 else []
    try:
        poll = float(parts[1]) if len(parts) == 2 else None
    except ValueError:
        poll = None
    if poll is None:
        return None
    return parts[0], poll, age


def wait_runs(place, role):
    marker = read_marker(place, role)
    if marker is None:
        return False
    _, poll, age = marker
    return age <= STALE_POLLS * poll + STALE_GRACE_SECONDS


def wait_or_hold(place, role, harness):
    """The Next: step that waits: the Harness's wait, or, while a wait of the
    Role still runs, ending the turn; after the plan Sign-off, none."""
    if plan_signed_off(place):
        return SIGNED_OFF_NEXT
    if harness.name != "codex" and wait_runs(place, role):
        return (
            "Your wait for the %s's Doorbell still runs and wakes you when one arrives: end your turn, "
            "and start no other wait." % OTHER[role]
        )
    return wait_next(role, harness)


def own_marker(place, role, token):
    try:
        lines = textfile.lines(marker_path(place, role)) or []
    except OSError:
        return False
    return len(lines) > 1 and lines[1].split()[:1] == [token]


def clear_marker(place, role, token=None):
    """Remove the marker: any marker, or with token only the wait's own."""
    if token is not None and not own_marker(place, role, token):
        return
    try:
        os.remove(marker_path(place, role))
    except OSError:
        pass


class Marker:
    """The marker of the wait this process runs."""

    def __init__(self, place, role, poll):
        self.place = place
        self.role = role
        self.token = "%d-%s" % (os.getpid(), os.urandom(6).hex())
        data = "%s%s\n%s %s\n" % (WAIT_PREFIX, WAIT_VERSION, self.token, poll)
        try:
            os.makedirs(place.dir, exist_ok=True)
            textfile.write(marker_path(place, role), data.encode("ascii"))
        except OSError:
            pass

    def beat(self):
        if own_marker(self.place, self.role, self.token):
            try:
                os.utime(marker_path(self.place, self.role), None)
            except OSError:
                pass

    def clear(self):
        clear_marker(self.place, self.role, self.token)


def end_on_signal():
    """Turn SIGTERM and SIGHUP into SystemExit, so a wait its Harness stops
    still removes its marker."""
    def stop(signum, frame):
        raise SystemExit(1)
    for name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            try:
                signal.signal(getattr(signal, name), stop)
            except (OSError, ValueError):
                pass


def wait(role, harness):
    place = Place()
    if harness.name == "codex":
        return arm(place, role, harness)
    end_on_signal()
    marker = Marker(place, role, timings()[0])
    try:
        found = watch(place, role, beat=marker.beat)
    except OSError as error:
        raise Failure(
            "The wait could not read its files: %s" % error,
            hand_relay(role, harness),
        )
    finally:
        marker.clear()
    out = Output()
    if found:
        out.line("A Doorbell for the %s is waiting." % role)
        return out.finish("Run: %s" % take_command(role, harness))
    out.line("TIMEOUT")
    return out.finish(timeout_next(role, harness))


def timeout_next(role, harness, entry=None):
    return (
        "Ask the user whether to keep waiting. On yes: %s On no, ask the user to paste the %s's next "
        "Doorbell here, then run: %s"
        % (wait_next(role, harness, entry), OTHER[role], paste_command(role, harness, entry))
    )


def hand_relay(role, harness):
    return (
        "Tell the user in one line that this wait cannot run, so they paste the %s's next Doorbell here. "
        "With the pasted line, run: %s" % (OTHER[role], paste_command(role, harness))
    )


def armed_path(place, thread):
    return os.path.join(place.dir, "codex-armed-" + thread)


def arm(place, role, harness):
    thread = os.environ.get("CODEX_THREAD_ID", "")
    if not THREAD_ID.match(thread):
        raise Failure(
            "Cannot arm the Codex Stop hook: CODEX_THREAD_ID is empty or not a thread id.",
            hand_relay(role, harness),
        )
    try:
        state = place.load_state(role)
        entries = place.entries(role, LOCK_RETRY_SECONDS)
    except OSError as error:
        raise Failure("The wait could not read its files: %s" % error, hand_relay(role, harness))
    count = min(state.count, len(entries))
    data = "%s%s\n%s %d\n" % (ARMED_PREFIX, ARMED_VERSION, role, count)
    try:
        os.makedirs(place.dir, exist_ok=True)
        textfile.write(armed_path(place, thread), data.encode("utf-8"))
    except OSError as error:
        raise Failure("Cannot write the armed file: %s" % error, hand_relay(role, harness))
    out = Output()
    out.line("Armed: the Codex Stop hook waits for the %s's next Doorbell when this turn ends." % role)
    return out.finish("End your turn now.")
