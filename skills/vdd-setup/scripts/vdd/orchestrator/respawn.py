"""The Respawn policy: whether a Role is spawned fresh or resumed for its
next round, orchestrator respawn and orchestrator tokens."""

from __future__ import annotations

import re
from typing import Any, Callable

from .. import catalog, harness as harnesses, loopstate, runner
from ..out import Failure, Output, or_list
from .flow import Flow
from .spawn import handoff, resume, spawn

POLICY = re.compile(r"^(every round|never|over ([1-9][0-9]*)(k?))$")


def counting() -> str:
    """The Harnesses whose subagents report a token count, as a line names
    them."""
    return or_list(found.display_name for found in harnesses.every() if found.reports_subagent_tokens())


def size(count: int) -> str:
    return "%dk" % round(count / 1000.0) if count >= 1000 else str(count)


def limit_of(policy: str | None) -> int | None:
    match = POLICY.match(policy or "")
    if not match or not match.group(2):
        return None
    return int(match.group(2)) * (1000 if match.group(3) else 1)


def step(flow: Flow, out: Output, role: str, number: int, first: str | None = None,
         fresh: str | None = None) -> runner.Plan:
    """Spawn or resume role for round number, by its Respawn policy: a Role
    with no live subagent in this session is spawned, for fresh when given;
    one with a live subagent is respawned on a once request, every round, or
    over its limit, and resumed otherwise."""
    live = flow.out(role)
    if live is None:
        reason = fresh or ("after a restart" if flow.spawned_before(role) else None)
        return spawn(flow, out, role, number, reason, first)
    if flow.once_pending(role):
        return spawn(flow, out, role, number, "respawn on request", first)
    policy = flow.policy(role) or "never"
    if live[1] != number and policy == "every round":
        return spawn(flow, out, role, number, "respawn every round", first)
    limit = limit_of(policy)
    if live[1] != number and limit is not None and flow.harness.reports_subagent_tokens():
        count = flow.tokens(role, live[1])
        if count is None:
            if first:
                out.line("First: %s" % first)
            out.line("The %s's Respawn policy is %s, and no token count is recorded for its round %d."
                     % (role, policy, live[1]))
            return flow.plan(
                out,
                "Run %s, with subagent_tokens from the %s's latest completion notice; it records the count and "
                "prints the step that waits for it."
                % (flow.command("tokens", role=role, tokens="<subagent_tokens>", slug=flow.slug), role)
            )
        if count > limit:
            return spawn(flow, out, role, number, "respawn at %s" % size(count), first)
    return resume(flow, out, role, number, handoff(flow, role, number), first)


def policies_line(flow: Flow) -> str:
    return "Respawn policies: %s." % ", ".join(
        "%s %s" % (role, flow.policy(role) or "not set") for role in ("Coder", "Plan-Reviewer", "Code-Reviewer"))


def respawn_question(flow: Flow) -> str:
    recommended, limit = flow.harness.respawn_recommendation()
    answers = [("Every round", "every round"), ("Never", "never")]
    if limit:
        answers.append(("Over a limit of the Coder's token count, for example %s; the user may name another "
                        "number" % limit, limit))
    parts = []
    for label, value in answers:
        mark = " (recommended)" if value == recommended else ""
        parts.append("\"%s\"%s (--policy %s)." % (label, mark, catalog.quoted(value)))
    return ("Respawn question: When should the Orchestrator respawn the Coder, spawning it anew for a round in "
            "place of resuming the one before? Answers, in this order: " + " ".join(parts))


def respawn(flow: Flow, ctx: catalog.Context, place: Callable[[Flow, Output], runner.Plan]) -> runner.Plan:
    """The respawn command's plan; place(flow, out) records the session and
    places the Workflow when it answers the Respawn question start asked."""
    values = ctx.values
    role = values["role"]
    ctx.require_one_of("policy", "once")
    # With one of them given, this holds only when both are.
    if (values["policy"] is None) == (not values["once"]):
        raise Failure("Give --policy or --once, not both.", "Run %s for the usage." % ctx.usage)
    out = Output()
    flow.always = False
    if values["once"]:
        flow.dry = ["Would make the %s's next spawn fresh." % role]
        flow.append(loopstate.respawn_once_line(role))
        live = flow.out(role)
        if live is not None and not flow.acted(role, live[1]) and not flow.done(role, live[1]):
            out.line("The %s's round %d is unfinished: a fresh %s takes it over." % (role, live[1], role))
            return spawn(flow, out, role, live[1], "respawn on request")
        out.line("The %s's next spawn is fresh." % role)
        if live is not None and not flow.acted(role, live[1]):
            # A BLOCKED after the round's check --write passed: the round is
            # done and its return is still owed.
            out.line("The %s's round %d is finished and not acted on yet." % (role, live[1]))
            return flow.plan(out, "Run %s" % flow.return_command(role))
        return flow.plan(out, "Go on with the step the tool printed before it.")
    policy = " ".join(values["policy"].split()).lower()
    match = POLICY.match(policy)
    if match is None:
        raise Failure(
            "--policy %s is not a Respawn policy. It takes \"every round\", never, or \"over <n>k\" with <n> a whole "
            "number from 1." % values["policy"],
            "Ask the user again with those answers, then run the command with one of them.",
        )
    if match.group(2) and not flow.harness.reports_subagent_tokens():
        raise Failure(
            "over <n> works only on %s: %s reports no subagent token count." % (counting(), flow.harness_label),
            "Ask the user for \"every round\" or never instead.",
        )
    # The answer to the Respawn question start asks while the Coder's policy
    # is unset: start's placement follows, so starting takes two calls.
    answers_start = role == "Coder" and flow.policy("Coder") is None
    flow.dry = ["Would set: respawn %s %s." % (role, policy)]
    flow.append(loopstate.respawn_line(role, policy))
    out.line(policies_line(flow))
    if answers_start:
        flow.dry.append("Would then record orchestrator session %d and place the Workflow." % (flow.session() + 1))
        return place(flow, out)
    if flow.any_spawn():
        return flow.plan(out, "The policy applies from the Role's next round; go on with the step the tool printed "
                              "before it.")
    return flow.plan(out, "Run %s" % flow.start_command())


def tokens(flow: Flow, values: dict[str, Any]) -> runner.Plan:
    role = values["role"]
    if not flow.harness.reports_subagent_tokens():
        raise Failure(
            "%s reports no subagent token count, so there is none to record." % flow.harness_label,
            "Go on with the step the tool printed before it.",
        )
    if not re.fullmatch(r"[0-9]+", values["tokens"]):
        raise Failure("--tokens takes a whole number: subagent_tokens from the completion notice.",
                      "Run the command again with the number.")
    live = flow.out(role)
    if live is None:
        raise Failure(
            "No %s is out in this Orchestrator session, so no count is asked for." % role,
            "Go on with the step the tool printed before it.",
        )
    count = int(values["tokens"])
    flow.append(loopstate.tokens_line(role, live[1], count))
    out = Output()
    out.line("Recorded: %s round %d, %s tokens." % (role, live[1], size(count)))
    waiting = waiting_step(flow, role)
    if waiting is None or waiting == live[1]:
        return flow.plan(out, "Go on with the step the tool printed before it.")
    return step(flow, out, role, waiting)


def waiting_step(flow: Flow, role: str) -> int | None:
    """The round of role the Workflow waits to spawn or resume, or None."""
    where = flow.position()
    return where.round if where.owed_by(role) else None
