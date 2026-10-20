"""The code Sign-off, as the PR-Author and the Orchestrator meet it: the check
that the state file records it, and the Next: step after the fold or a skip."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import loopstate, places
from .out import Failure

if TYPE_CHECKING:
    from .loopfile import Loop


def require_code_sign_off(loop: Loop) -> None:
    """The PR-Author runs only once the state file records the code
    Sign-off: an unsigned review has no PR to open yet."""
    loopstate.refuse_v1(loop, "loop show --role PR-Author")
    review = loopstate.State(loop.dir).last_review("code")
    if review is None or not review.signed_off:
        where = "no code review is recorded" if review is None else "code round %d's review left findings open" % (
            review.round)
        raise Failure(
            "The code Loop is not signed off: %s. The Loop is not finished, so there is no PR to open yet."
            % where,
            "Stop, and tell the user the Loop is not finished: the code review has not signed off.",
        )


def pr_step(loop: Loop) -> str:
    """The Next: line after the fold or a skip: the PR step."""
    pr, _ = loop.setting("PR")
    branch, _ = loop.setting("Feature branch")
    if pr == "no":
        return ("Run %s loop close --slug %s --write, then print \"Loop signed off. `PR: no`: `%s` stays local, "
                "nothing pushed.\" and stop." % (places.command(), loop.slug, branch))
    return "Invoke the vdd-create-pr skill in your own Session, never as a subagent."
