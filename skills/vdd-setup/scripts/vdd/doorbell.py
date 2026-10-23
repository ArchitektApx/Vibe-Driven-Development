"""The Doorbell command between the Planner and the Orchestrator: ring, wait,
take. The Doorbell file, its lines and states, the wait and its marker live in
the doorbells package, which the Orchestrator, the reviews and the Codex Stop
hook share.
"""

from __future__ import annotations

import signal
from types import FrameType
from typing import NoReturn

from . import catalog, doorbells, harness as harnesses, textfile
from .harness import Harness
from .out import Failure, Output, or_list


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
    "--harness takes %s: the Harness the Loop file's Harness:"
    % or_list(found.name for found in harnesses.every()),
    "line names. --slug names the loop; pass it on every call. Without it the tool takes the loop whose feature",
    "branch is checked out, else the only open loop. Run every command from the repository root.",
]


def run(argv: list[str]) -> int:
    return catalog.run("doorbell", argv, HELP, "Run the command your skill or the last Next: line names.", dispatch)


def dispatch(ctx: catalog.Context) -> int:
    sub, values = ctx.command, ctx.values
    harness = harnesses.from_option(values, ctx.usage)
    role = values["role"]
    place = doorbells.Place.find(values["slug"])
    if sub == "ring":
        return ring(place, role, harness, values["write"])
    if sub == "wait":
        return wait(place, role, harness)
    return take(place, role, harness, values["pasted"], values["resumed"])


def composed(place: doorbells.Place, role: str) -> str:
    """The Doorbell line role rings, from the loop's state: the Planner's
    round is the last plan review's plus one, or 1; the Orchestrator relays
    the last plan review."""
    place.state.refuse_v1(place.require_loop().slug, "doorbell ring")
    last = place.state.last_review("plan")
    if role == "Planner":
        return doorbells.planner_doorbell(place.tracker, last.round + 1 if last else 1)
    if last is None:
        raise Failure(
            "No plan review is recorded for the loop %s, so there is nothing to relay. Nothing was written."
            % place.slug,
            "Wait for the Plan-Reviewer's return, as your skill says.",
        )
    return doorbells.review_doorbell(last)


def ring(place: doorbells.Place, role: str, harness: Harness, write: bool) -> int:
    to = doorbells.OTHER[role]
    place.require_open("a ring")
    line = composed(place, role)
    doorbell = doorbells.parse(line, to, place.tracker)
    if doorbell is None:
        raise RuntimeError("The composed Doorbell line does not parse: %s" % line)
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
                "the Doorbell file %s" % textfile.shown(place.file), error,
                "Otherwise print the Doorbell line for the user to paste into the %s's Session, and stop." % to,
            )
        out.line("Rung: the Doorbell file now holds it, addressed to the %s." % to)
    if role == "Planner" and doorbell.round == 1:
        launch = harness.orchestrator_launch(place.slug)
        out.tell("Start the Orchestrator now: %s." % launch)
        if harness.picks_up_doorbell():
            out.tell(
                "It picks up the Doorbell below from the Doorbell file; paste it in only if it does not "
                "start the review."
            )
        else:
            out.tell("Paste the Doorbell below into it once it is up.")
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


def take(place: doorbells.Place, role: str, harness: Harness, pasted: str | None, resumed: bool = False) -> int:
    if resumed:
        if role != "Planner":
            raise Failure(
                "--resumed is the Planner's.",
                "Place the Workflow with %s, as your skill says." % catalog.bare("orchestrator", "start"),
            )
        # A wait an earlier Session started wakes that Session, not this one.
        doorbells.clear_marker(place, role)
    entries = place.entries(role)
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


def take_pasted(place: doorbells.Place, role: str, harness: Harness, entries: list[doorbells.Entry],
                state: doorbells.State, line: str, out: Output) -> int:
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


def act_next(place: doorbells.Place, role: str, harness: Harness) -> str:
    """The step after a Doorbell take printed: the Orchestrator runs
    orchestrator return for the Planner's Doorbell."""
    if role == "Orchestrator":
        return "Run %s" % catalog.line("orchestrator", "return", role="Planner", slug=place.slug, harness=harness.name)
    return "Act on this Doorbell as your skill says."


def after_nothing(place: doorbells.Place, role: str, harness: Harness, entries: list[doorbells.Entry],
                  state: doorbells.State) -> str:
    _, new = doorbells.pending(entries, state)
    if new:
        return "A Doorbell for you is waiting in the Doorbell file. Run: %s" % doorbells.take_command(role, harness, place.slug)
    return doorbells.wait_or_hold(place, role, harness)


def end_on_signal() -> None:
    """Turn SIGTERM and SIGHUP into SystemExit, so a wait its Harness stops
    still removes its marker."""
    def stop(signum: int, frame: FrameType | None) -> NoReturn:
        raise SystemExit(1)
    for name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            try:
                signal.signal(getattr(signal, name), stop)
            except (OSError, ValueError):
                pass


def wait(place: doorbells.Place, role: str, harness: Harness) -> int:
    place.require_open("a wait")
    if harness.waits_through_stop_hook():
        doorbells.arm(place, role, harness)
        out = Output()
        out.line("Armed: the Codex Stop hook waits for the %s's next Doorbell when this turn ends." % role)
        return out.finish("End your turn now.")
    end_on_signal()
    marker = doorbells.Marker(place, role, doorbells.timings()[0])
    try:
        outcome = doorbells.wait_for(place, role, harness, beat=marker.beat)
    finally:
        marker.clear()
    out = Output()
    if isinstance(outcome, doorbells.Found):
        out.line("A Doorbell for the %s is waiting." % role)
        return out.finish("Run: %s" % outcome.take)
    out.line("TIMEOUT")
    return out.finish(outcome.next_step)
