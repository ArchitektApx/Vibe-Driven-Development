"""The code Sign-off, as the PR-Author, the Orchestrator and the fold meet it:
the check that the state file records it, whether the fold is owed, and the
Next: step after the fold or a skip."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import loopstate, places
from .out import Failure

if TYPE_CHECKING:
    from .loopfile import Loop


def not_signed_off(review: loopstate.Review | None) -> str:
    """What stands in the way of a code Sign-off, for a refusal's first line:
    the newest code record, which is not a reviewer's signed-off review."""
    if review is None:
        return "no code review is recorded"
    if review.user:
        return "the user's findings after code round %d are open" % review.round
    return "code round %d's review left findings open" % review.round


def sign_off_blocker(state: loopstate.State) -> str | None:
    """What stands in the way of the code Sign-off the state records, or None
    once the newest code record is a reviewer's signed-off review."""
    review = state.last_review("code")
    if review is None or not review.signed_off:
        return not_signed_off(review)
    return None


def require_code_sign_off(state: loopstate.State) -> None:
    """The PR-Author runs only once the state file records the code
    Sign-off: an unsigned review has no PR to open yet. pr and loop show
    --role PR-Author print this refusal word for word."""
    where = sign_off_blocker(state)
    if where is not None:
        raise Failure(
            "The code Loop is not signed off: %s. The Loop is not finished, so there is no PR to open yet."
            % where,
            "Stop, and tell the user the Loop is not finished: the code review has not signed off.",
        )


def pr_step(loop: Loop) -> str:
    """The Next: line after the fold or a skip: the PR step."""
    pr = loop.pr
    branch = loop.branch
    if pr == "no":
        return ("Run %s loop close --slug %s --write, then print \"Loop signed off. `PR: no`: `%s` stays local, "
                "nothing pushed.\" and stop." % (places.command(), loop.slug, branch))
    return "Invoke the vdd-create-pr skill in your own Session, never as a subagent."
