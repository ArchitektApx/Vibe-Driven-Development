"""A loop's state file, .scratch/<slug>/loop-state, version 2: the one owner
of its name, header, versions, reads and appends.

The file is append-only and later lines win. It opens with a version header,
then "loop open" and "loop closed" lines, the last one winning, and the round
lines below. Version 1, which only 0.16.0-beta.3 wrote, still reads as open or
closed; the round commands refuse it. Besides the loop lines it holds:

  plan <r> review-started
  code <r> review-started
  <plan|code> <r> reviewed <open|signed-off> <numbers|-> counts <b> <m> <p> next <n> new <k> closed <c>
      checks <text>
  code <r> user open <numbers> counts <b> <m> <p> next <n> new <k>
  code <r> start <sha>
  code <r> end <sha>
  respawn <Role> <every round|never|over <n>k>
  respawn-once <Role>
  orchestrator session <s>
  spawn <Role> <r> session <s> [reason <text>]
  resume <Role> <r> session <s>
  return <Role> <r> ok
  return <Role> <r> miss
  tokens <Role> <r> <count>
  fold folded <new tip> signed <sha>
  fold skipped <signed sha> <reason>

A reviewed line names the findings still open after the round, the open
counts per severity, the number the next round's new findings start at, how
many findings the round added and closed, and its Checks lines. A user line,
written only by review add after the signed-off line of round <r>, names the
findings the user raised after that Sign-off: all of them open, counted per
severity, the number the next new finding takes and how many the entry holds;
the last user line after a round wins. It has no closed and no checks part,
and the plan Loop takes none. Every line kind starts with its own word or
words, so no line reads as another.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Literal

from .. import textfile
from ..out import TELL, Failure
from .lines import STATE_PREFIX, code_mark_line, header_line, loop_line, review_started_line

if TYPE_CHECKING:
    from ..loopfile import Loop

STATE_NAME = "loop-state"
# The versions State reads. Version 1 has only loop lines.
STATE_VERSIONS = ("1", "2")
OPEN = "open"
CLOSED = "closed"

SEVERITIES = ("blocker", "major", "minor")

REVIEWED = re.compile(
    r"^(plan|code) ([1-9][0-9]*) reviewed (open|signed-off) ([0-9,]+|-) counts ([0-9]+) ([0-9]+) ([0-9]+)(.*)$"
)
EXTRA = re.compile(r" (next|new|closed) ([0-9]+)")
USER = re.compile(r"^code ([1-9][0-9]*) user open ([0-9,]+) counts ([0-9]+) ([0-9]+) ([0-9]+) next ([0-9]+) new ([0-9]+)$")


class Review:
    """One recorded review: its round, outcome, open findings and counts."""

    def __init__(
        self, kind: str, round_number: int, outcome: str, open_numbers: list[int], counts: tuple[int, int, int],
        next_number: int, new: int, closed: int, checks: str, user: bool = False,
    ) -> None:
        self.kind = kind
        self.round = round_number
        self.signed_off = outcome == "signed-off"
        self.open = open_numbers
        self.counts = counts
        self.next = next_number
        self.new = new
        self.closed = closed
        self.checks = checks
        # Whether this is the user's entry after round <round>'s Sign-off,
        # standing in for that round's review.
        self.user = user

    def raised(self) -> list[int]:
        """The finding numbers a user entry holds, which run without gaps
        up to its next number."""
        return list(range(self.next - self.new, self.next))


class Fold:
    """One recorded fold outcome: "folded" with the branch's new tip, or
    "skipped" with the reason, and the signed commit it ran on."""

    def __init__(self, kind: Literal["folded", "skipped"], signed: str, tip: str = "", reason: str = "") -> None:
        self.kind = kind
        self.signed = signed
        self.tip = tip
        self.reason = reason


class Damaged(Failure):
    """A state file whose header this tool never wrote."""


def header(path: str, lines: list[str]) -> str:
    """The version of the state file whose lines these are. Raises Damaged
    when its header is not one this tool wrote, and the Failure for a version
    this copy does not know."""
    version = textfile.check_header(path, lines, STATE_PREFIX, STATE_VERSIONS)
    if version is None:
        raise Damaged(
            "%s is not a loop state file this tool wrote." % textfile.shown(path),
            "Tell the user the loop state file is damaged, and stop.",
        )
    return version


def start_state(directory: str) -> None:
    """Write a new state file holding one open loop, replacing a damaged one."""
    textfile.write_text(os.path.join(directory, STATE_NAME), header_line() + "\n" + loop_line(OPEN) + "\n")


class State:
    """Every line of the state file, read once per command: its version,
    whether the loop is open, and the round lines."""

    def __init__(self, directory: str) -> None:
        self.dir = directory
        self.path = os.path.join(directory, STATE_NAME)
        lines = textfile.lines(self.path)
        # None when there is no state file.
        self.version: str | None = None if lines is None else header(self.path, lines)
        self.lines: list[str] = (lines or [])[1:]

    @property
    def status(self) -> str | None:
        """OPEN or CLOSED, the last loop line winning, or None when there is
        no state file. A file with no loop line reads as CLOSED."""
        if self.version is None:
            return None
        status = CLOSED
        for line in self.lines:
            parts = line.split()
            if len(parts) == 2 and parts[0] == "loop" and parts[1] in (OPEN, CLOSED):
                status = parts[1]
        return status

    @property
    def is_open(self) -> bool:
        return self.status == OPEN

    def refuse_v1(self, slug: str, command: str) -> None:
        """Refuse a command that reads the loop's rounds on a version 1 state
        file: this version reads no rounds from it."""
        if self.version != "1":
            return
        raise Failure(
            [
                "The loop %s has state file version 1, which this VDD no longer reads. %s does not run on it."
                % (slug, command),
                TELL % (
                    "The loop %s has state file version 1, which this VDD no longer reads. Move it aside with "
                    "loop aside --slug %s --write, and start the loop afresh with vdd-start-loop." % (slug, slug)
                ),
            ],
            "Relay the Tell the user verbatim line above unchanged, and stop.",
        )

    # --- reading ---

    def reviewer_reviews(self, kind: str) -> dict[int, Review]:
        """round -> Review, the reviewers' rounds only, the last line for a
        round winning."""
        found: dict[int, Review] = {}
        for line in self.lines:
            match = REVIEWED.match(line)
            if not match or match.group(1) != kind:
                continue
            numbers = [] if match.group(4) == "-" else [int(n) for n in match.group(4).split(",") if n]
            rest = match.group(8)
            checks = ""
            if " checks " in rest:
                rest, checks = rest.split(" checks ", 1)
            extra = dict((key, int(value)) for key, value in EXTRA.findall(rest))
            round_number = int(match.group(2))
            next_number = extra.get("next", (max(numbers) + 1) if numbers else 1)
            found[round_number] = Review(
                kind, round_number, match.group(3), numbers,
                (int(match.group(5)), int(match.group(6)), int(match.group(7))),
                next_number, extra.get("new", 0), extra.get("closed", 0), checks.strip(),
            )
        return found

    def user_entries(self) -> dict[int, Review]:
        """round -> the user's entry after that round's Sign-off, the last
        line for a round winning."""
        found: dict[int, Review] = {}
        for line in self.lines:
            match = USER.match(line)
            if not match:
                continue
            round_number = int(match.group(1))
            found[round_number] = Review(
                "code", round_number, "open", [int(n) for n in match.group(2).split(",") if n],
                (int(match.group(3)), int(match.group(4)), int(match.group(5))),
                int(match.group(6)), int(match.group(7)), 0, "", user=True,
            )
        return found

    def reviews(self, kind: str) -> dict[int, Review]:
        """round -> Review as the Workflow places it: a user entry stands in
        for the review of the round it follows, open and not signed off."""
        found = self.reviewer_reviews(kind)
        if kind == "code":
            found.update(self.user_entries())
        return found

    def user_raised(self) -> dict[int, int]:
        """finding number -> the round whose Sign-off the user raised it
        after."""
        found: dict[int, int] = {}
        for round_number, entry in self.user_entries().items():
            for number in entry.raised():
                found[number] = round_number
        return found

    def last_review(self, kind: str) -> Review | None:
        reviews = self.reviews(kind)
        return reviews[max(reviews)] if reviews else None

    def review(self, kind: str, round_number: int) -> Review | None:
        return self.reviews(kind).get(round_number)

    def review_started(self, kind: str, round_number: int) -> bool:
        return review_started_line(kind, round_number) in self.lines

    def code_mark(self, which: Literal["start", "end"], round_number: int) -> str | None:
        """The sha of a code round's start or end line, the last winning, or
        None."""
        prefix = code_mark_line(which, round_number, "")
        sha: str | None = None
        for line in self.lines:
            if line.startswith(prefix):
                sha = line[len(prefix):].strip()
        return sha

    def code_round(self) -> int:
        """The newest code round with a start line, or 0."""
        newest = 0
        for line in self.lines:
            match = re.match(r"^code ([1-9][0-9]*) start ", line)
            if match:
                newest = max(newest, int(match.group(1)))
        return newest

    def folds(self) -> list[Fold]:
        """Every fold line, folded or skipped, as a Fold, in order."""
        found: list[Fold] = []
        for line in self.lines:
            match = re.match(r"^fold folded (\S+) signed (\S+)", line)
            if match:
                found.append(Fold("folded", match.group(2), tip=match.group(1)))
                continue
            match = re.match(r"^fold skipped (\S+) (.*)$", line)
            if match:
                found.append(Fold("skipped", match.group(1), reason=match.group(2)))
        return found

    def fold_record(self, kind: str | None = None) -> Fold | None:
        """The fold's last recorded outcome, of kind when given, or None."""
        wanted = [fold for fold in self.folds() if kind in (None, fold.kind)]
        return wanted[-1] if wanted else None

    def fold_signed(self) -> set[str]:
        """The signed commits a fold line, folded or skipped, names."""
        return {fold.signed for fold in self.folds()}

    def fold_owed(self) -> bool:
        """Whether the fold is owed: the newest code record is a reviewer's
        signed-off review, and no fold line exists or the last one ran on
        another commit than that round's recorded end."""
        review = self.last_review("code")
        if review is None or not review.signed_off:
            return False
        record = self.fold_record()
        return record is None or record.signed != self.code_mark("end", review.round)

    def next_number(self, kind: str) -> int:
        """The number a round's new findings start at: the last review's
        next, or 1."""
        last = self.last_review(kind)
        return last.next if last else 1

    # --- writing ---

    def append(self, *lines: str) -> None:
        """Append lines to the state file, or raise a refused Failure."""
        try:
            self.add(*lines)
        except OSError as error:
            raise textfile.write_refusal("the loop state file %s" % textfile.shown(self.path), error,
                                         "Otherwise tell the user the loop state file cannot be written, and stop.")

    def add(self, *lines: str) -> None:
        """Append lines to the state file in one write, for a caller that
        words its own refusal. Raises OSError."""
        textfile.append(self.path, "".join(line + "\n" for line in lines))
        self.lines.extend(lines)


# --- the Doorbell lines, byte-identical to the ones the Roles composed (ADR 0002) ---

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
