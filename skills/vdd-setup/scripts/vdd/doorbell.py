"""The Doorbell between the Planner and the Orchestrator: ring, wait, take.

A loop's tracker directory is .scratch/<slug>/, the loop --slug names or
the lookup finds. The Doorbell file, <tracker>/doorbells, holds one line per ring,
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

from . import args, gitcmd, loopfile, loopstate, places, textfile
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
    """The files of one loop: its tracker directory, the Doorbell file, the
    state files."""

    def __init__(self, root, slug):
        self.root = root
        self.slug = slug
        self.tracker = ".scratch/" + slug
        self.dir = loopfile.tracker_dir(root, slug)
        self.file = os.path.join(self.dir, FILE_NAME)

    @classmethod
    def find(cls, slug=None):
        """The Place of the loop --slug names, or the lookup finds."""
        loop = loopfile.find(gitcmd.project_root(os.getcwd()), slug)
        place = cls(loop.root, loop.slug)
        place.loop = loop
        return place

    def require_open(self, what):
        """Refuse ring and wait on a closed loop: no Session would ever answer."""
        if not self.loop.is_open():
            raise Failure(
                "The loop %s is closed, so %s would never be answered. Nothing was written." % (self.slug, what),
                "Tell the user the loop %s is closed. To carry on, they ask the Orchestrator to reopen it." % self.slug,
            )

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

# Every command the tool prints for a Role to run names the loop it ran on.

def take_command(role, harness, slug, entry=None):
    """The take command, naming the copy at entry (the running one by default)."""
    return "%s doorbell take --role %s --harness %s --slug %s" % (places.command(entry), role, harness.name, slug)


def wait_command(role, harness, slug, entry=None):
    return "%s doorbell wait --role %s --harness %s --slug %s" % (places.command(entry), role, harness.name, slug)


def ring_command(role, harness, slug):
    return "%s doorbell ring --role %s --harness %s --slug %s --write" % (places.command(), role, harness.name, slug)


def paste_command(role, harness, slug, entry=None):
    return '%s doorbell take --role %s --pasted "<the line the user pastes>" --harness %s --slug %s' % (
        places.command(entry), role, harness.name, slug)


def wait_next(role, harness, slug, entry=None):
    return harness.wait_next(role, wait_command(role, harness, slug, entry), paste_command(role, harness, slug, entry))


# --- the commands ---

HELP = [
    "doorbell ring --role <Planner|Orchestrator> --harness <h> --slug <slug> --write",
    "  Ring the other Role: append your Doorbell line, composed from the loop's state, to the Doorbell file,",
    "  addressed to it. Run it in the foreground. The Planner's line names the round after the last plan",
    "  review, or round 1; the Orchestrator's relays the last plan review, its open counts or SIGNED OFF.",
    "  Without --write it prints what it would append and changes nothing; ringing the same line twice",
    "  appends it once.",
    "",
    "doorbell wait --role <Planner|Orchestrator> --harness <h> --slug <slug>",
    "  Wait for a Doorbell addressed to your Role. Start it only as a Next: line names it. It reads the",
    "  Doorbell file every 10 seconds and exits when a new Doorbell is waiting, naming the take command,",
    "  or prints TIMEOUT after 45 minutes. While it runs, ring and take name no second wait: their Next:",
    "  says your wait still runs. On codex it arms the Stop hook instead and returns at once.",
    "",
    "doorbell take --role <Planner|Orchestrator> --harness <h> --slug <slug> [--pasted \"<line>\"] [--resumed]",
    "  Take the newest Doorbell addressed to your Role and record it, and every line before it, as handled.",
    "  Run it in the foreground on a wake, or with --pasted for a line the user pasted. A Doorbell already",
    "  handled (same sender and round) is reported and not acted on twice. A line that is not a Doorbell is",
    "  reported for the user and never acted on.",
    "  --resumed: the Planner's first take in a resumed Session. A wait an earlier Session started wakes",
    "  that Session, so it names a wait of your own; what you handled before stays handled.",
    "  Once the plan review is signed off and the Planner has rung no later round, take and ring name no",
    "  wait: the plan Loop is over.",
    "",
    "  ring and wait refuse on a closed loop.",
    "",
    "--harness takes claude-code, codex, cursor, copilot-cli or generic: the Harness the Loop file's Harness:",
    "line names. --slug names the loop; pass it on every call. Without it the tool takes the loop whose feature",
    "branch is checked out, else the only open loop. Run every command from the repository root.",
]

SPEC = {
    "role": args.VALUE,
    "harness": args.VALUE,
    "write": args.FLAG,
    "pasted": args.VALUE,
    "resumed": args.FLAG,
    "slug": args.VALUE,
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
        args.unknown_command("doorbell " + sub, usage())
    values = args.parse(rest, SPEC, usage())
    if values["help"]:
        return run(["--help"])
    harness = args.harness_of(values, usage())
    role = values["role"]
    if role not in ROLES:
        raise Failure("--role takes Planner or Orchestrator.", "Run %s for the usage." % usage())
    place = Place.find(values["slug"])
    if sub == "ring":
        return ring(place, role, harness, values["write"])
    if sub == "wait":
        return wait(place, role, harness)
    return take(place, role, harness, values["pasted"], values["resumed"])


def composed(place, role):
    """The Doorbell line role rings, from the loop's state: the Planner's
    round is the last plan review's plus one, or 1; the Orchestrator relays
    the last plan review."""
    loopfile.refuse_v1(place.loop, "doorbell ring")
    last = loopstate.State(place.dir).last_review("plan")
    if role == "Planner":
        return loopstate.planner_doorbell(place.tracker, last.round + 1 if last else 1)
    if last is None:
        raise Failure(
            "No plan review is recorded for the loop %s, so there is nothing to relay. Nothing was written."
            % place.slug,
            "Wait for the Plan-Reviewer's return, as your skill says.",
        )
    return loopstate.review_doorbell(last)


def ring(place, role, harness, write):
    to = OTHER[role]
    place.require_open("a ring")
    line = composed(place, role)
    doorbell = parse(line, to, place.tracker)
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
        launch = harness.orchestrator_launch(place.slug)
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
        return out.finish("A Doorbell for you is already waiting. Run: %s" % take_command(role, harness, place.slug))
    if role == "Orchestrator" and doorbell.signed_off:
        return out.finish(SIGNED_OFF_NEXT)
    return out.finish(wait_or_hold(place, role, harness))


def take(place, role, harness, pasted, resumed=False):
    if resumed:
        if role != "Planner":
            raise Failure(
                "--resumed is the Planner's.",
                "Place the Workflow with orchestrator start, as your skill says.",
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
    return out.finish(act_next(place, role, harness))


def mark_handled(place, role, out):
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
    return out.finish(act_next(place, role, harness))


def act_next(place, role, harness):
    """The step after a Doorbell take printed: the Orchestrator runs
    orchestrator return for the Planner's Doorbell."""
    if role == "Orchestrator":
        return "Run %s orchestrator return --role Planner --slug %s --harness %s" % (
            places.command(), place.slug, harness.name)
    return "Act on this Doorbell as your skill says."


def after_nothing(place, role, harness, entries, state):
    _, new = pending(entries, state)
    if new:
        return "A Doorbell for you is waiting in the Doorbell file. Run: %s" % take_command(role, harness, place.slug)
    return wait_or_hold(place, role, harness)


def last_plan_review(place):
    """The last plan review the state file records, or None."""
    return loopstate.State(place.dir).last_review("plan")


def plan_signed_off(place):
    """The last plan review signed off and the Planner has rung no round
    after it: the plan Loop is over and neither Role waits."""
    review = last_plan_review(place)
    if review is None or not review.signed_off:
        return False
    rung = [e.doorbell.round for e in place.entries("Orchestrator") if e.doorbell]
    return not rung or max(rung) <= review.round


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
    return wait_next(role, harness, place.slug)


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


def wait(place, role, harness):
    place.require_open("a wait")
    if harness.name == "codex":
        return arm(place, role, harness)
    end_on_signal()
    marker = Marker(place, role, timings()[0])
    try:
        found = watch(place, role, beat=marker.beat)
    except OSError as error:
        raise Failure(
            "The wait could not read its files: %s" % error,
            hand_relay(role, harness, place.slug),
        )
    finally:
        marker.clear()
    out = Output()
    if found:
        out.line("A Doorbell for the %s is waiting." % role)
        return out.finish("Run: %s" % take_command(role, harness, place.slug))
    out.line("TIMEOUT")
    return out.finish(timeout_next(role, harness, place.slug))


def timeout_next(role, harness, slug, entry=None):
    return (
        "Ask the user whether to keep waiting. On yes: %s On no, ask the user to paste the %s's next "
        "Doorbell here, then run: %s"
        % (wait_next(role, harness, slug, entry), OTHER[role], paste_command(role, harness, slug, entry))
    )


def hand_relay(role, harness, slug):
    return (
        "Tell the user in one line that this wait cannot run, so they paste the %s's next Doorbell here. "
        "With the pasted line, run: %s" % (OTHER[role], paste_command(role, harness, slug))
    )


def armed_path(place, thread):
    return os.path.join(place.dir, "codex-armed-" + thread)


def arm(place, role, harness):
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
        textfile.write(armed_path(place, thread), data.encode("utf-8"))
    except OSError as error:
        raise Failure("Cannot write the armed file: %s" % error, hand_relay(role, harness, place.slug))
    out = Output()
    out.line("Armed: the Codex Stop hook waits for the %s's next Doorbell when this turn ends." % role)
    return out.finish("End your turn now.")
