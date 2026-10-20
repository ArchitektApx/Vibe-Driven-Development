"""The Doorbell command between the Planner and the Orchestrator: ring, wait,
take. The Doorbell file, its lines and states, the wait and its marker live in
doorbells.py, which the Orchestrator, the reviews and the Codex Stop hook
share.
"""

import signal

from . import args, doorbells, loopstate, places
from .out import Failure, Output


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
    if role not in doorbells.ROLES:
        raise Failure("--role takes Planner or Orchestrator.", "Run %s for the usage." % usage())
    place = doorbells.Place.find(values["slug"])
    if sub == "ring":
        return ring(place, role, harness, values["write"])
    if sub == "wait":
        return wait(place, role, harness)
    return take(place, role, harness, values["pasted"], values["resumed"])


def composed(place, role):
    """The Doorbell line role rings, from the loop's state: the Planner's
    round is the last plan review's plus one, or 1; the Orchestrator relays
    the last plan review."""
    loopstate.refuse_v1(place.loop, "doorbell ring")
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
    to = doorbells.OTHER[role]
    place.require_open("a ring")
    line = composed(place, role)
    doorbell = doorbells.parse(line, to, place.tracker)
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
            raise textfile.write_refusal(
                "the Doorbell file %s" % place.file, error,
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
    _, new = doorbells.pending(entries, place.load_state(role))
    if new:
        return out.finish("A Doorbell for you is already waiting. Run: %s" % doorbells.take_command(role, harness, place.slug))
    if role == "Orchestrator" and doorbell.signed_off:
        return out.finish(doorbells.SIGNED_OFF_NEXT)
    return out.finish(doorbells.wait_or_hold(place, role, harness))


def take(place, role, harness, pasted, resumed=False):
    if resumed:
        if role != "Planner":
            raise Failure(
                "--resumed is the Planner's.",
                "Place the Workflow with orchestrator start, as your skill says.",
            )
        # A wait an earlier Session started wakes that Session, not this one.
        doorbells.clear_marker(place, role)
    entries = place.entries(role, doorbells.LOCK_RETRY_SECONDS)
    state = place.load_state(role)
    out = Output()
    if pasted is not None:
        return take_pasted(place, role, harness, entries, state, pasted.strip(), out)
    beyond, new = doorbells.pending(entries, state)
    doorbells.tell_not_doorbells(out, beyond)
    for entry in beyond:
        if entry.doorbell:
            state.handled.add(entry.doorbell.key())
    state.count = len(entries)
    place.save_state(role, state)
    if not new:
        out.line("No new Doorbell for the %s." % role)
        return out.finish(doorbells.wait_or_hold(place, role, harness))
    out.line("Doorbell: %s" % new[-1].text)
    return out.finish(act_next(place, role, harness))


def take_pasted(place, role, harness, entries, state, line, out):
    doorbell = doorbells.parse(line, role, place.tracker)
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
    _, new = doorbells.pending(entries, state)
    if new:
        return "A Doorbell for you is waiting in the Doorbell file. Run: %s" % doorbells.take_command(role, harness, place.slug)
    return doorbells.wait_or_hold(place, role, harness)


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
        doorbells.arm(place, role, harness)
        out = Output()
        out.line("Armed: the Codex Stop hook waits for the %s's next Doorbell when this turn ends." % role)
        return out.finish("End your turn now.")
    end_on_signal()
    marker = doorbells.Marker(place, role, doorbells.timings()[0])
    try:
        found = doorbells.watch(place, role, beat=marker.beat)
    except OSError as error:
        raise Failure(
            "The wait could not read its files: %s" % error,
            doorbells.hand_relay(role, harness, place.slug),
        )
    finally:
        marker.clear()
    out = Output()
    if found:
        out.line("A Doorbell for the %s is waiting." % role)
        return out.finish("Run: %s" % doorbells.take_command(role, harness, place.slug))
    out.line("TIMEOUT")
    return out.finish(doorbells.timeout_next(role, harness, place.slug))
