"""The Doorbell lines: the grammar a Doorbell file line and a Doorbell follow,
and the composers that write each Role's Doorbell, byte-identical to the ones
the Roles composed (ADR 0002)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..catalog.specs import DOORBELL_ROLES as ROLES  # noqa: F401 - the Roles a Doorbell is addressed to

if TYPE_CHECKING:
    from ..loopstate import Review


OTHER = {"Planner": "Orchestrator", "Orchestrator": "Planner"}

ADDRESS = re.compile(r"^([0-9]{2}:[0-9]{2}:[0-9]{2}) to: (Planner|Orchestrator) (.*)$")
ROUND = r"(?P<round>[1-9][0-9]*)"
REVIEW_WRITTEN = re.compile(
    r"^VDD Plan-Reviewer: PLAN-REVIEW\.md written, round " + ROUND
    + r": [0-9]+ blocker, [0-9]+ major, [0-9]+ minor\. Read it\.$"
)
REVIEW_SIGNED_OFF = re.compile(r"^VDD Plan-Reviewer: PLAN-REVIEW\.md SIGNED OFF, round " + ROUND + r"\.$")
REVIEW_RESTART = re.compile(r"^VDD Plan-Reviewer: PLAN-REVIEW\.md written, round " + ROUND + r"\. Read it\.$")


class Doorbell:
    """A Doorbell line, parsed: who sent it and for which round."""

    def __init__(self, text: str, sender: str, round_number: int, signed_off: bool = False) -> None:
        self.text = text
        self.sender = sender
        self.round = round_number
        self.signed_off = signed_off

    def key(self) -> tuple[str, int]:
        return (self.sender, self.round)


def parse(text: str, to_role: str, tracker: str) -> Doorbell | None:
    """The Doorbell text holds when addressed to to_role, or None when it
    matches no template for that Role."""
    if to_role == "Orchestrator":
        planner = re.compile(
            r"^VDD Planner: " + re.escape(tracker) + r"/ ready, round " + ROUND
            + r"\. Read spec\.md and issues/\.$"
        )
        match = planner.match(text)
        return Doorbell(text, "Planner", int(match.group("round"))) if match else None
    for pattern, signed in ((REVIEW_WRITTEN, False), (REVIEW_SIGNED_OFF, True), (REVIEW_RESTART, False)):
        match = pattern.match(text)
        if match:
            return Doorbell(text, "Plan-Reviewer", int(match.group("round")), signed)
    return None


class Entry:
    """One line of the Doorbell file addressed to a Role."""

    def __init__(self, number: int, raw: str, text: str, doorbell: Doorbell | None) -> None:
        self.number = number
        self.raw = raw
        self.text = text
        self.doorbell = doorbell


# --- the composers ---

REVIEW_FILES = {"plan": ("Plan-Reviewer", "PLAN-REVIEW.md"), "code": ("Code-Reviewer", "CODEREVIEW.md")}


def review_doorbell(review: Review) -> str:
    role, name = REVIEW_FILES[review.kind]
    if review.signed_off:
        return "VDD %s: %s SIGNED OFF, round %d." % (role, name, review.round)
    return "VDD %s: %s written, round %d: %d blocker, %d major, %d minor. Read it." % (
        (role, name, review.round) + tuple(review.counts))


def planner_doorbell(tracker: str, round_number: int) -> str:
    return "VDD Planner: %s/ ready, round %d. Read spec.md and issues/." % (tracker, round_number)


def coder_doorbell(round_number: int) -> str:
    return "VDD Coder: FIXES.md written, round %d. Read it." % round_number
