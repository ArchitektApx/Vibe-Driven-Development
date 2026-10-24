"""The Doorbell command between the Planner and the Orchestrator: ring, wait,
take. The Doorbell file, its lines and states, the wait and its marker live in
the doorbells package, which the Orchestrator, the reviews and the Codex Stop
hook share.
"""

from __future__ import annotations

import signal
from types import FrameType
from typing import NoReturn

from . import catalog, doorbells, harness as harnesses, runner, textfile
from .harness import Harness
from .out import TELL, Failure, Output, one_line, or_list


# --- the commands ---

HELP = catalog.Help({
    "ring": [
        "doorbell ring --role <Planner|Orchestrator> --harness <h> --slug <slug> --write",
        "  At the end of every turn that wrote your Working file, ring the other Role: append your Doorbell",
        "  line, composed from the loop's state, to the Doorbell file, addressed to it. Run it in the foreground.",
        "  The Planner's line names the round after the last plan review, or round 1; the Orchestrator's relays",
        "  the last plan review, its open counts or SIGNED OFF. Without --write it prints what it would append",
        "  and changes nothing; ringing the same line twice appends it once. A Planner ring is refused once the",
        "  plan review is signed off: the Spec stays as signed off.",
    ],
    "wait": [
        "doorbell wait --role <Planner|Orchestrator> --harness <h> --slug <slug>",
        "  Wait for a Doorbell addressed to your Role. Start it only as a Next: line names it. It reads the",
        "  Doorbell file every 10 seconds and exits when a new Doorbell is waiting, naming the take command,",
        "  or prints TIMEOUT after 45 minutes. While it runs, ring and take name no second wait: their Next:",
        "  says your wait still runs. On %s it arms the Stop hook instead and returns at once."
        % or_list(found.name for found in harnesses.every() if found.waits_through_stop_hook()),
    ],
    "take": [
        "doorbell take --role <Planner|Orchestrator> --harness <h> --slug <slug> [--pasted \"<line>\"] [--resumed]",
        "  Take the newest Doorbell addressed to your Role and record it, and every line before it, as handled.",
        "  Run it in the foreground on a wake, or with --pasted for a line the user pasted. A Doorbell already",
        "  handled (same sender and round) is reported and not acted on twice. A line that is not a Doorbell is",
        "  reported for the user and never acted on.",
        "  --resumed: the Planner's first take in a resumed Session. A wait an earlier Session started wakes",
        "  that Session, so it names a wait of your own; what you handled before stays handled.",
        "  Once the plan review is signed off, take and ring name no wait: the plan Loop is over. The Planner's",
        "  take of the Sign-off says its work is done.",
    ]},
    [
        catalog.Only(("ring", "wait"), "  ring and wait refuse on a closed loop."),
        "",
        "--harness takes %s: the Harness the Loop file's Harness:"
        % or_list(found.name for found in harnesses.every()),
        "line names. --slug names the loop; pass it on every call. Without it the tool takes the loop whose feature",
        "branch is checked out, else the only open loop.",
    ])


def run(argv: list[str]) -> int:
    return catalog.run("doorbell", argv, HELP,
                       "Run the doorbell command above that your step needs, or the one the last Next: line names.", dispatch)


def dispatch(ctx: catalog.Context) -> int:
    return runner.run(ctx, lambda: plan(ctx))


def plan(ctx: catalog.Context) -> runner.Plan:
    sub, values = ctx.command, ctx.values
    harness = harnesses.from_option(values, ctx.usage)
    role = values["role"]
    place = doorbells.Place.find(values["slug"])
    if sub == "ring":
        return ring(place, role, harness)
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
            "Wait for the Plan-Reviewer's return and act on its last line as your skill says for a Role's return.",
        )
    return doorbells.review_doorbell(last)


def ring(place: doorbells.Place, role: str, harness: Harness) -> runner.Plan:
    to = doorbells.OTHER[role]
    place.require_open("a ring")
    if role == "Planner":
        refuse_after_sign_off(place)
    line = composed(place, role)
    doorbell = doorbells.parse(line, to, place.tracker)
    if doorbell is None:
        raise RuntimeError("The composed Doorbell line does not parse: %s" % line)
    last = place.entries(to)
    rung: runner.Effect
    if bool(last) and last[-1].text == line:
        rung = runner.Effect(["Already rung: %s" % line],
                             ["Already rung: the newest line to the %s is this Doorbell." % to])
    else:
        rung = runner.Step(lambda: append(place, to, line),
                           ["Would append, addressed to the %s: %s" % (to, line)])
    if role == "Planner" and doorbell.round == 1:
        launch = harness.orchestrator_launch(place.slug)
        tells = ["Start the Orchestrator now: %s." % launch]
        if harness.picks_up_doorbell():
            tells.append("It picks up the Doorbell below from the Doorbell file; paste it in only if it does not "
                         "start the review.")
        else:
            tells.append("Paste the Doorbell below into it once it is up.")
        tells.append(line)
    else:
        tells = ["If the %s's Session does not wake, paste this into it: %s" % (to, line)]
    return runner.Plan([rung, runner.Effect(done=[TELL % one_line(text) for text in tells])],
                       lambda: after_ring(place, role, harness, doorbell))


def refuse_after_sign_off(place: doorbells.Place) -> None:
    """Refuse a Planner ring once the plan review is signed off: the code
    Loop builds from the Spec and the Tickets as they were signed off."""
    last = place.state.last_review("plan")
    if last is None or not last.signed_off:
        return
    raise Failure(
        "The plan Loop signed off in round %d, so the Planner rings no further round. Nothing was written."
        % last.round,
        "The plan Loop is over and the Spec stays as signed off: change nothing more in the Spec or the Tickets, "
        "ring nothing, and end your turn. Tell the user that a change they still want goes in as a finding with "
        "%s once the code Loop signs off." % catalog.line("review", "add", slug=place.slug, from_="<file>"),
    )


def append(place: doorbells.Place, to: str, line: str) -> list[str]:
    try:
        place.append(to, line)
    except OSError as error:
        raise textfile.write_refusal(
            "the Doorbell file %s" % textfile.shown(place.file), error,
            "Otherwise print the Doorbell line for the user to paste into the %s's Session, and stop." % to,
        )
    return ["Rung: the Doorbell file now holds it, addressed to the %s." % to]


def after_ring(place: doorbells.Place, role: str, harness: Harness, doorbell: doorbells.Doorbell) -> str:
    """The Next: step once the ring is in the Doorbell file: the Orchestrator's
    relay of the plan Sign-off names no wait, and a wait after Tells that hand
    the user a step comes before their relay."""
    _, new = doorbells.pending(place.entries(role), place.load_state(role))
    if new:
        return "Take the Doorbell already waiting for you: run %s" % doorbells.take_command(role, harness, place.slug)
    if role == "Orchestrator" and doorbell.signed_off:
        return doorbells.signed_off_next(role)
    step = doorbells.wait_or_hold(place, role, harness)
    if hands_user_a_step(role, harness, doorbell) and step == doorbells.wait_next(role, harness, place.slug):
        return doorbells.relayed_wait_next(role, harness, place.slug)
    return step


def hands_user_a_step(role: str, harness: Harness, doorbell: doorbells.Doorbell) -> bool:
    """Whether the ring's Tells hand the user a step only they can take: start
    the Orchestrator, or paste the Doorbell into a Session that does not pick
    it up."""
    return (role == "Planner" and doorbell.round == 1) or not harness.picks_up_doorbell()


def take(place: doorbells.Place, role: str, harness: Harness, pasted: str | None,
         resumed: bool = False) -> runner.Plan:
    effects: list[runner.Effect] = []
    if resumed:
        if role != "Planner":
            raise Failure(
                "--resumed is the Planner's.",
                "Run %s instead: it places the Workflow."
                % catalog.line("orchestrator", "start", slug=place.slug, harness=harness.name),
            )
        # A wait an earlier Session started wakes that Session, not this one.
        effects.append(runner.Step(lambda: cleared(place, role)))
    entries = place.entries(role)
    state = place.load_state(role)
    if pasted is not None:
        return take_pasted(place, role, harness, entries, state, pasted.strip(), effects)
    beyond, new = doorbells.pending(entries, state)
    lines = not_doorbells(beyond)
    for entry in beyond:
        if entry.doorbell:
            state.handled.add(entry.doorbell.key())
    state.count = len(entries)
    effects.append(saved(place, role, state))
    if not new:
        lines.append("No new Doorbell for the %s." % role)
        return taken(effects, lines, lambda: doorbells.wait_or_hold(place, role, harness))
    lines.append("Doorbell: %s" % new[-1].text)
    return taken(effects, lines, act_next(place, role, harness, new[-1].doorbell))


def take_pasted(place: doorbells.Place, role: str, harness: Harness, entries: list[doorbells.Entry],
                state: doorbells.State, line: str, effects: list[runner.Effect]) -> runner.Plan:
    doorbell = doorbells.parse(line, role, place.tracker)
    if doorbell is None:
        return taken(effects, [TELL % one_line("This is not a Doorbell for the %s, so it was not acted on: %s"
                                               % (role, line))],
                     lambda: after_nothing(place, role, harness, entries, state))
    if doorbell.key() in state.handled:
        return taken(effects, ["Already handled, nothing to do: %s" % line],
                     lambda: after_nothing(place, role, harness, entries, state))
    state.handled.add(doorbell.key())
    for index, entry in enumerate(entries):
        if index >= state.count and entry.doorbell and entry.doorbell.key() == doorbell.key():
            state.count = index + 1
    effects.append(saved(place, role, state))
    return taken(effects, ["Doorbell: %s" % line], act_next(place, role, harness, doorbell))


def taken(effects: list[runner.Effect], lines: list[str], next_step: runner.Next) -> runner.Plan:
    """take's plan, which always applies: its lines print once its state file
    is saved, since a Doorbell is printed only once it is recorded as
    handled."""
    return runner.Plan(effects + [runner.Effect(done=lines)], next_step, always=True)


def not_doorbells(entries: list[doorbells.Entry]) -> list[str]:
    out = Output()
    doorbells.tell_not_doorbells(out, entries)
    return out.lines


def saved(place: doorbells.Place, role: str, state: doorbells.State) -> runner.Step:
    def save() -> list[str]:
        place.save_state(role, state)
        return []
    return runner.Step(save)


def cleared(place: doorbells.Place, role: str) -> list[str]:
    doorbells.clear_marker(place, role)
    return []


def act_next(place: doorbells.Place, role: str, harness: Harness, doorbell: doorbells.Doorbell | None) -> str:
    """The step after a Doorbell take printed: the Orchestrator runs
    orchestrator return for the Planner's Doorbell; the plan Sign-off ends
    the Planner's work."""
    if role == "Orchestrator":
        return "Run %s" % catalog.line("orchestrator", "return", role="Planner", slug=place.slug, harness=harness.name)
    if doorbell is not None and doorbell.signed_off:
        return ("The plan Loop is signed off and your work as the Planner is done: change nothing more in the Spec "
                "or the Tickets, ring nothing and run no wait. End your turn.")
    return "Read the Working file this Doorbell names and continue your Role."


def after_nothing(place: doorbells.Place, role: str, harness: Harness, entries: list[doorbells.Entry],
                  state: doorbells.State) -> str:
    _, new = doorbells.pending(entries, state)
    if new:
        return ("Take the Doorbell waiting for you in the Doorbell file: run %s"
                % doorbells.take_command(role, harness, place.slug))
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


def wait(place: doorbells.Place, role: str, harness: Harness) -> runner.Plan:
    place.require_open("a wait")
    if harness.waits_through_stop_hook():
        def armed() -> list[str]:
            doorbells.arm(place, role, harness)
            return ["Armed: the %s Stop hook waits for the %s's next Doorbell when this turn ends."
                    % (harness.display_name, role)]
        return runner.Plan([runner.Step(armed)], "End your turn now.", always=True)
    outcome: list[doorbells.Outcome] = []

    def waited() -> list[str]:
        end_on_signal()
        marker = doorbells.Marker(place, role, doorbells.timings()[0])
        try:
            outcome.append(doorbells.wait_for(place, role, harness, beat=marker.beat))
        finally:
            marker.clear()
        if isinstance(outcome[0], doorbells.Found):
            return ["A Doorbell for the %s is waiting." % role]
        return ["TIMEOUT"]

    def then() -> str:
        found = outcome[0]
        return "Run: %s" % found.take if isinstance(found, doorbells.Found) else found.next_step

    return runner.Plan([runner.Step(waited)], then, always=True)
