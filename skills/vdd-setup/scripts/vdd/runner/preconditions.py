"""The precondition kinds a command's plan starts from: a loop open for a
round command, a closed loop's refusal, and a question for the user."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..out import Failure

if TYPE_CHECKING:
    from ..loopfile import Loop
    from ..loopstate import State


class Ask(Failure):
    """A command that needs the user's answer before it can plan: the
    runner prints its lines and Next: step, exiting 0 on a dry run, which
    asks, and 1 on --write, which cannot write without the answer."""


def closed_loop(slug: str, why: str = "") -> Failure:
    """The Failure for a command that needs an open loop. why, when given,
    follows "is closed" in the first line."""
    return Failure(
        "The loop %s is closed%s. Nothing was written." % (slug, why),
        "Tell the user the loop %s is closed. To carry on, they ask the Orchestrator to reopen it." % slug,
    )


def open_loop(loop: Loop, command: str) -> State:
    """The loop's State, read once; refuses a round command on a version 1 or
    a closed loop."""
    state = loop.load_state()
    state.refuse_v1(loop.slug, command)
    if not state.is_open:
        raise closed_loop(loop.slug)
    return state
