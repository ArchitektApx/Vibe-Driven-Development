"""A hosted Role's spawn, its resume and the resume message that hands
it the round."""

from __future__ import annotations

from .. import doorbells, loopstate, runner, workfile
from ..out import Output
from .flow import Flow


def lists(flow: Flow, role: str, number: int) -> tuple[list[str], list[str]]:
    """The Read and Write lists of a Role's round, every path under the
    tracker directory."""
    files = workfile.WORKING_FILES[role]
    return [flow.path(name) for name in files.read(number)], [flow.path(name) for name in files.write]


def handoff(flow: Flow, role: str, number: int) -> str:
    """The resume message that starts a live Role's round: the other Role's
    Doorbell line for it."""
    if role == "Coder":
        review = flow.state.review("code", number - 1)
        if review is None:
            raise RuntimeError("No code review is recorded for round %d." % (number - 1))
        return doorbells.review_doorbell(review)
    if role == "Code-Reviewer":
        return doorbells.coder_doorbell(number)
    return doorbells.planner_doorbell(flow.loop.tracker, number)


def next_after(flow: Flow, role: str) -> str:
    return ("When it returns, put a last line that starts QUESTION: or BLOCKED: to the user as your skill says for "
            "a Role's return; for anything else, run %s"
            % flow.return_command(role))


def spawn(flow: Flow, out: Output, role: str, number: int, reason: str | None = None,
          first: str | None = None) -> runner.Plan:
    """Record a fresh spawn and print it. first, when given, is a step to
    take before it."""
    flow.append(loopstate.spawn_line(role, number, flow.session(), reason))
    read, write = lists(flow, role, number)
    out.line("Spawning %s, <model>, round %d%s." % (role, number, ", " + reason if reason else ""))
    out.line("Read: %s" % ", ".join(read))
    out.line("Write: %s" % ", ".join(write))
    before = "%s Then print" % first if first else "Print"
    return flow.plan(
        out,
        "%s the Spawning line above in your reply, <model> filled in from Model approval, then spawn a fresh %s "
        "with the Spawn prompt, the slug %s, round %d and the Read and Write lists above. %s"
        % (before, role, flow.slug, number, next_after(flow, role))
    )


def resume(flow: Flow, out: Output, role: str, number: int, message: str, first: str | None = None) -> runner.Plan:
    flow.append(loopstate.resume_line(role, number, flow.session()))
    out.line("Resuming %s, round %d." % (role, number))
    out.line("Resume message:")
    out.line(message)
    before = "%s Then resume" % first if first else "Resume"
    return flow.plan(
        out,
        "%s the same %s with the resume message above as the whole message, nothing added but what your "
        "Harness file says every resume message carries. %s" % (before, role, next_after(flow, role))
    )
