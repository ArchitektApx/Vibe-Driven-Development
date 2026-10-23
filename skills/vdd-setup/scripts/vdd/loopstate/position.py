"""Where the Workflow stands: the one position query every command asks,
and the code Sign-off as the PR-Author, the Orchestrator and the fold meet
it. Each command words its own refusal from these facts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from .. import places
from ..out import Failure
from .state import Review, State

if TYPE_CHECKING:
    from ..harness import Harness
    from ..loopfile import Loop


class Position:
    """Where one Loop stands: its phase and round, who owes the next move,
    whether the code Loop is signed off and whether the fold is owed. The
    fold is run by the Orchestrator; the user owes the move on a closed
    loop."""

    def __init__(
        self, phase: Literal["plan", "code"], round_number: int, owes: str, signed_off: bool = False,
        fold_owed: bool = False, ring_ignored: bool = False,
    ) -> None:
        self.phase = phase
        self.round = round_number
        self.owes = owes
        self.signed_off = signed_off
        self.fold_owed = fold_owed
        # The Planner rang a plan round after the plan Sign-off once the code
        # Loop had started: no Role reviews it.
        self.ring_ignored = ring_ignored

    def owed_by(self, role: str, round_number: int | None = None) -> bool:
        return self.owes == role and (round_number is None or self.round == round_number)


def position(state: State, planner_round: int) -> Position:
    """The one answer to where the Workflow stands. planner_round is the
    newest round the Planner rang, from the Doorbell file. A Planner ring
    after the plan Sign-off opens the next plan round while the code Loop has
    not started; once it has, the ring is ignored."""
    plan = state.last_review("plan")
    reviewed = plan.round if plan else 0
    code_started = state.code_mark("start", 1) is not None
    plan_signed = plan is not None and plan.signed_off
    rung = planner_round > reviewed
    # Once the code Loop has started, the plan Loop is over: coder start ran
    # only after its Sign-off.
    if not code_started and (not plan_signed or rung):
        owner = "Plan-Reviewer" if rung else "Planner"
        return Position("plan", reviewed + 1, owner if state.is_open else "user")
    found = code_position(state, ring_ignored=rung)
    if not state.is_open:
        found.owes = "user"
    return found


def code_position(state: State, ring_ignored: bool = False) -> Position:
    review = state.last_review("code")
    if review is not None and review.signed_off:
        owed = state.fold_owed()
        return Position("code", review.round, "Fold" if owed else "PR-Author", True, owed, ring_ignored)
    newest = state.code_round()
    if newest and state.code_mark("end", newest) is None:
        return Position("code", newest, "Coder", ring_ignored=ring_ignored)
    if newest and (review is None or review.round < newest):
        return Position("code", newest, "Code-Reviewer", ring_ignored=ring_ignored)
    return Position("code", review.round + 1 if review else 1, "Coder", ring_ignored=ring_ignored)


# --- the code Sign-off ---

def not_signed_off(review: Review | None) -> str:
    """What stands in the way of a code Sign-off, for a refusal's first line:
    the newest code record, which is not a reviewer's signed-off review."""
    if review is None:
        return "no code review is recorded"
    if review.user:
        return "the user's findings after code round %d are open" % review.round
    return "code round %d's review left findings open" % review.round


def sign_off_blocker(state: State) -> str | None:
    """What stands in the way of the code Sign-off the state records, or None
    once the newest code record is a reviewer's signed-off review."""
    review = state.last_review("code")
    if review is None or not review.signed_off:
        return not_signed_off(review)
    return None


def require_code_sign_off(state: State) -> None:
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


def fold_command(loop: Loop, harness: Harness, write: bool = True) -> str:
    """The command that runs the fold, as every caller names it."""
    return "%s loop fold --slug %s --harness %s%s" % (places.command(), loop.slug, harness.name,
                                                       " --write" if write else "")


def pr_step(loop: Loop) -> str:
    """The Next: line after the fold or a skip: the PR step."""
    pr = loop.pr
    branch = loop.branch
    if pr == "no":
        return ("Run %s loop close --slug %s --write, then print \"Loop signed off. `PR: no`: `%s` stays local, "
                "nothing pushed.\" and stop." % (places.command(), loop.slug, branch))
    return "Invoke the vdd-create-pr skill in your own Session, never as a subagent."
