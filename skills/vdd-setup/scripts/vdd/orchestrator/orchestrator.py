"""The orchestrator command group: the Orchestrator acting on the tool's
output, reading no Working file.

orchestrator start places the Workflow from the state file and the Doorbell
file, on a first start or after a restart, and records the session. While the
Coder's Respawn policy is unset it asks for it instead, and the respawn that
answers records the session and places the Workflow.
orchestrator return runs after every hosted Role's return that is not a
QUESTION or a BLOCKED, and after a Planner Doorbell: it reads the round's
outcome from the state its check --write recorded and prints the one next
step. Neither rings, spawns or resumes anything: the Orchestrator takes every
outward step itself, so the user can pause the Loop before any of them.
"""

from __future__ import annotations

from typing import NoReturn

from .. import catalog, doorbells, loopstate, runner
from ..out import TELL, Failure, Output
from .flow import Flow
from .respawn import counting, policies_line, respawn, respawn_question, step, tokens
from .spawn import resume, spawn

USER_REASON = "for the user's findings"

HELP = catalog.Help({
    "start": [
        "orchestrator start --slug <slug> [--harness <h>]",
        "  Run on every start of the Orchestrator's Session, a restart included. Records a new session, names the",
        "  Harness and its Harness file, says where each Loop stands, and prints the one next step: a spawn, the",
        "  ring to the Planner, the wait for the Planner's Doorbell, the fold at a code Sign-off, or the PR",
        "  step. Every spawn after a restart is fresh. After the user's findings it spawns the Coder fresh for",
        "  the next round, with no ring. While the Coder's Respawn policy is not set it records nothing and asks",
        "  the Respawn question instead; the respawn that answers it records the session and prints that step.",
    ],
    "return": [
        "orchestrator return --role <Planner|Plan-Reviewer|Coder|Code-Reviewer> --slug <slug> --harness <h>",
        "  Run after every hosted Role's return whose last line does not start with QUESTION: or BLOCKED:, and",
        "  with --role Planner once doorbell take printed the Planner's Doorbell. It takes no return line and no",
        "  token count: the round's outcome is the one its check --write recorded. It prints the next step, a",
        "  spawn with its Read and Write lists, a resume with its message, the ring, the wait or the fold; a",
        "  second return for a round already acted on, and a round with no check --write, each say what to do.",
    ],
    "respawn": [
        "orchestrator respawn --role <Plan-Reviewer|Coder|Code-Reviewer> (--policy \"<p>\" | --once) --slug <slug>",
        "    [--harness <h>] --write",
        "  On the user's word: --policy sets the Role's Respawn policy, \"every round\", never or \"over <n>k\"",
        "  (%s only, from the Coder's subagent_tokens); --once makes the Role's next spawn fresh, and"
        % counting(),
        "  after a BLOCKED prints that fresh spawn for the unfinished round at once. The reviewers start at never;",
        "  the Coder's policy is asked by the first start, and the --write that answers it records the session",
        "  and places the Workflow as start does.",
    ],
    "tokens": [
        "orchestrator tokens --role <Role> --tokens <n> --slug <slug> [--harness <h>]",
        "  %s only, when a Next: line asks for it: record the Role's subagent_tokens from its latest"
        % counting(),
        "  completion notice and print the step that waited for the count.",
    ]},
    [
        catalog.Only(("start", "return", "tokens"),
                     "start, return and tokens ring, spawn and resume nothing, and take no --write: you take each step "
                     "they",
                     "print. --slug names the loop; pass it on every call."),
        catalog.Only(("respawn",), "--slug names the loop; pass it on every call.", group=False),
    ])

def run(argv: list[str]) -> int:
    return catalog.run("orchestrator", argv, HELP,
                       "Run the orchestrator command above that your step needs, or the one the last Next: line names.", dispatch)


def dispatch(ctx: catalog.Context) -> int:
    return runner.run(ctx, lambda: plan(ctx))


def plan(ctx: catalog.Context) -> runner.Plan:
    flow = Flow.find(ctx)
    if ctx.command == "start":
        return start(flow)
    if ctx.command == "respawn":
        return respawn(flow, ctx, place)
    if ctx.command == "tokens":
        return tokens(flow, ctx.values)
    return returned(flow, ctx.values["role"])


def planner_wait(flow: Flow) -> str:
    return doorbells.wait_or_hold(flow.place, "Orchestrator", flow.harness)


def ring_then_wait(flow: Flow, out: Output) -> runner.Plan:
    return flow.plan(
        out,
        "Relay the last plan review to the Planner: run %s in the foreground, then do what its Next: line says: it names the wait for the Planner's next "
        "Doorbell." % flow.ring_command()
    )


def after_sign_off(flow: Flow, out: Output) -> runner.Plan:
    """The step after the code Sign-off: the fold while no fold outcome is
    recorded, on every PR: value, else the PR step."""
    out.line("Code Loop: signed off.")
    if flow.position().fold_owed:
        out.line("Fold: not run yet.")
        return flow.plan(
            out,
            "Run %s, relay its Tell the user verbatim line, then do what its Next: line says."
            % loopstate.fold_command(flow.loop, flow.harness)
        )
    # Not owed after a signed-off review means a fold line is recorded.
    outcome = flow.state.fold_record()
    out.line("Fold: %s." % (outcome.kind if outcome else "not run yet"))
    return flow.plan(out, loopstate.pr_step(flow.loop))


def describe(flow: Flow) -> str:
    where = flow.position()
    plan = flow.state.last_review("plan")
    rung = flow.rung()
    if plan and plan.signed_off and where.owed_by("Plan-Reviewer"):
        plan_text = "signed off in round %d; the Planner rang round %d after it, not reviewed yet" % (
            plan.round, rung)
    elif plan and plan.signed_off:
        plan_text = "signed off in round %d" % plan.round
    elif rung > (plan.round if plan else 0):
        plan_text = "the Planner rang round %d, not reviewed yet" % rung
    elif plan:
        plan_text = "round %d reviewed, %d blocker, %d major, %d minor open; the Planner owns the next move" % (
            (plan.round,) + tuple(plan.counts))
    else:
        plan_text = "the Planner has rung no round yet"
    code = flow.state.last_review("code")
    if where.phase == "plan":
        code_text = "not started"
    elif where.signed_off:
        code_text = "signed off in round %d" % where.round
    elif where.owed_by("Code-Reviewer"):
        code_text = "Coder round %d done, not reviewed" % where.round
    elif flow.state.code_mark("start", where.round) is not None:
        code_text = "Coder round %d started, not finished" % where.round
    elif code and code.user:
        code_text = "reopened by the user's findings after round %d, %d blocker, %d major, %d minor open" % (
            (code.round,) + tuple(code.counts))
    elif code:
        code_text = "round %d reviewed, %d blocker, %d major, %d minor open" % ((code.round,) + tuple(code.counts))
    else:
        code_text = "not started"
    return "Plan Loop: %s. Code Loop: %s." % (plan_text, code_text)


def start(flow: Flow) -> runner.Plan:
    out = Output()
    out.line("Loop: %s, open. Harness: %s. Read %s, the Harness file this skill's Harnesses index links, now, once."
             % (flow.slug, flow.harness_label, flow.loop.harness_file()))
    out.line(describe(flow))
    out.line(policies_line(flow))
    if flow.policy("Coder") is None:
        out.line(respawn_question(flow))
        return flow.plan(
            out,
            "Ask Model approval and the Respawn question above in one message, and wait for the user. Then run %s"
            % flow.command("respawn", role="Coder", policy='"<answer>"', slug=flow.slug, write=True)
        )
    return place(flow, out)


def place(flow: Flow, out: Output) -> runner.Plan:
    """Record the next session and place the Workflow: after start's lines,
    or after the respawn that answered the Respawn question start asked."""
    previous = flow.session()
    flow.append(loopstate.session_line(previous + 1))
    # A wait an earlier session started wakes that session, not this one.
    flow.before.append(runner.Step(lambda: cleared(flow)))
    # The placement below acts on every Doorbell rung so far.
    beyond, handled = doorbells.mark_handled(flow.place, "Orchestrator")
    doorbells.tell_not_doorbells(out, beyond)
    if handled is not None:
        flow.before.append(runner.Step(lambda: saved(flow, handled)))
    reason = "after a restart" if previous else None
    code = flow.state.last_review("code")
    if code and code.user and flow.state.code_mark("start", code.round + 1) is None:
        # The plan Loop is long over: no ring, and nothing restarted.
        return spawn(flow, out, "Coder", code.round + 1, USER_REASON)
    where = flow.position()
    if where.phase == "code":
        # A Planner that took the plan Sign-off has finished; a ring would ask
        # the user to paste into its Session.
        first = (None if doorbells.sign_off_taken(flow.place) else
                 "Run %s in the foreground; the plan Loop is over, so it names no wait." % flow.ring_command())
        if where.signed_off:
            if first:
                out.line("First: %s" % first)
            return after_sign_off(flow, out)
        return spawn(flow, out, where.owes, where.round, reason, first)
    if where.owed_by("Plan-Reviewer"):
        return spawn(flow, out, "Plan-Reviewer", where.round, reason)
    if flow.state.last_review("plan"):
        return ring_then_wait(flow, out)
    # Worded once the marker is cleared: no wait of this Role runs then.
    return flow.plan(out, lambda: planner_wait(flow))


def cleared(flow: Flow) -> list[str]:
    doorbells.clear_marker(flow.place, "Orchestrator")
    return []


def saved(flow: Flow, handled: doorbells.State) -> list[str]:
    flow.place.save_state("Orchestrator", handled)
    return []


def fixed_resume(flow: Flow, role: str, number: int) -> str:
    return ("Round %d is not finished: `%s` has not passed. Run it, fix what it reports until it passes, then end "
            "your turn with the line it prints." % (number, flow.check_command(role)))


def already(role: str, number: int) -> NoReturn:
    raise Failure(
        "%s round %d was already acted on." % (role, number),
        "Nothing to do for this return; go on with the step the tool printed before it.",
    )


def returned(flow: Flow, role: str) -> runner.Plan:
    if role == "Planner":
        return planner_returned(flow)
    live = flow.out(role)
    if live is None:
        raise Failure(
            "No %s is out in this Orchestrator session, so there is no return to act on." % role,
            "Run %s" % flow.start_command(),
        )
    number = live[1]
    if flow.acted(role, number):
        already(role, number)
    out = Output()
    if not flow.done(role, number):
        flow.append(loopstate.return_line(role, number, False))
        if flow.misses(role, number) == 1:
            out.line("%s round %d ended without `%s`: the round is not finished." % (
                role, number, flow.check_command(role, bare=True)))
            return resume(flow, out, role, number, fixed_resume(flow, role, number))
        out.line("%s round %d ended without `%s` a second time."
                 % (role, number, flow.check_command(role, bare=True)))
        out.tell("The %s ended round %d twice without finishing it. Answer resume to resume it once more, respawn "
                 "to start a fresh %s for round %d, or stop." % (role, number, role, number))
        return flow.plan(
            out,
            "Relay the line above and end your turn; the user decides. On resume, resume the same %s with the "
            "user's words as the message. On respawn, run %s. On stop, stop." % (
                role, flow.command("respawn", role=role, once=True, slug=flow.slug, write=True))
        )
    flow.append(loopstate.return_line(role, number, True))
    if role == "Coder":
        out.line("Code Loop: Coder round %d done." % number)
        fresh = USER_REASON if flow.spawn_reason("Coder", number) == USER_REASON else None
        return step(flow, out, "Code-Reviewer", number, fresh=fresh)
    if role == "Code-Reviewer":
        review = flow.state.review("code", number)
        if review is None:
            raise RuntimeError("done found no code review for round %d." % number)
        if review.signed_off:
            return after_sign_off(flow, out)
        out.line("Code Loop: round %d reviewed, %d blocker, %d major, %d minor open." % (
            (number,) + tuple(review.counts)))
        return step(flow, out, "Coder", number + 1)
    review = flow.state.review("plan", number)
    if review is None:
        raise RuntimeError("done found no plan review for round %d." % number)
    if review.signed_off:
        out.line("Plan Loop: signed off in round %d." % number)
        first = "Run %s in the foreground; the plan Loop is over, so it names no wait." % flow.ring_command()
        return step(flow, out, "Coder", 1, first)
    out.line("Plan Loop: round %d reviewed, %d blocker, %d major, %d minor open." % (
        (number,) + tuple(review.counts)))
    return ring_then_wait(flow, out)


def planner_returned(flow: Flow) -> runner.Plan:
    """After doorbell take printed the Planner's Doorbell: the Plan-Reviewer's
    spawn for the rung round, or its resume when one is live."""
    plan = flow.state.last_review("plan")
    number = (plan.round if plan else 0) + 1
    if plan is not None and plan.signed_off and flow.position().ring_ignored:
        raise Failure(
            [
                "The Planner rang plan round %d after the plan Sign-off in round %d, and the code Loop has started: "
                "no Plan-Reviewer reviews it." % (flow.rung(), plan.round),
                TELL % ("The plan Loop is signed off and the code Loop is running, so the Planner's plan round %d "
                        "is not reviewed. The code Loop goes on with the Spec as it was signed off." % flow.rung()),
            ],
            "Relay the Tell the user verbatim line above unchanged, then go on with the step you were on before "
            "the Planner's Doorbell. Spawn no Plan-Reviewer.",
        )
    if flow.rung() < number:
        raise Failure(
            "The Planner has rung no round after the last plan review: there is nothing to act on.",
            "Nothing to do for this return; go on with the step the tool printed before it.",
        )
    live = flow.out("Plan-Reviewer")
    if flow.acted("Planner", number) or (live is not None and live[1] == number):
        already("Planner", number)
    flow.append(loopstate.return_line("Planner", number, True))
    out = Output()
    out.line("Plan Loop: the Planner rang round %d." % number)
    return step(flow, out, "Plan-Reviewer", number)
