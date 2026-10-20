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


def fold_owed(state: loopstate.State) -> bool:
    """Whether the fold is owed: the newest code record is a reviewer's
    signed-off review, and no fold line exists or the last one ran on another
    commit than that round's recorded end."""
    review = state.last_review("code")
    if review is None or not review.signed_off:
        return False
    record = state.fold_record()
    return record is None or record.signed != state.code_mark("end", review.round)


def require_code_sign_off(loop: Loop) -> None:
    """The PR-Author runs only once the state file records the code
    Sign-off: an unsigned review has no PR to open yet."""
    loopstate.refuse_v1(loop, "loop show --role PR-Author")
    review = loopstate.State(loop.dir).last_review("code")
    if review is None or not review.signed_off:
        where = not_signed_off(review)
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
