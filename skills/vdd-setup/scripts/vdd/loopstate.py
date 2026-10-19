"""The round lines of a loop's state file, .scratch/<slug>/loop-state,
version 2.

The file is append-only and later lines win. Besides "loop open" and "loop
closed" (loopfile.py) it holds:

  plan <r> review-started
  code <r> review-started
  <plan|code> <r> reviewed <open|signed-off> <numbers|-> counts <b> <m> <p> next <n> new <k> closed <c>
      checks <text>
  code <r> start <sha>
  code <r> end <sha>
  respawn <Role> <every round|never|over <n>k>
  respawn-once <Role>
  orchestrator session <s>
  spawn <Role> <r> session <s> [once] [reason <text>]
  resume <Role> <r> session <s>
  return <Role> <r> ok
  return <Role> <r> miss
  tokens <Role> <r> <count>

A reviewed line names the findings still open after the round, the open
counts per severity, the number the next round's new findings start at, how
many findings the round added and closed, and its Checks lines. Every line
kind starts with its own word or words, so no line reads as another.
"""

import os
import re

from . import loopfile, textfile
from .out import Failure, refused

KINDS = ("plan", "code")
ROLES = ("Plan-Reviewer", "Coder", "Code-Reviewer")
SEVERITIES = ("blocker", "major", "minor")

REVIEWED = re.compile(
    r"^(plan|code) ([1-9][0-9]*) reviewed (open|signed-off) ([0-9,]+|-) counts ([0-9]+) ([0-9]+) ([0-9]+)(.*)$"
)
EXTRA = re.compile(r" (next|new|closed) ([0-9]+)")


class Review:
    """One recorded review: its round, outcome, open findings and counts."""

    def __init__(self, kind, round_number, outcome, open_numbers, counts, next_number, new, closed, checks):
        self.kind = kind
        self.round = round_number
        self.signed_off = outcome == "signed-off"
        self.open = open_numbers
        self.counts = counts
        self.next = next_number
        self.new = new
        self.closed = closed
        self.checks = checks


class State:
    """Every line of the state file, read once."""

    def __init__(self, directory):
        self.dir = directory
        self.path = os.path.join(directory, loopfile.STATE_NAME)
        self.lines = (textfile.lines(self.path, 2.0) or [])[1:]

    # --- reading ---

    def reviews(self, kind):
        """round -> Review, the last line for a round winning."""
        found = {}
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

    def last_review(self, kind):
        reviews = self.reviews(kind)
        return reviews[max(reviews)] if reviews else None

    def review(self, kind, round_number):
        return self.reviews(kind).get(round_number)

    def review_started(self, kind, round_number):
        return ("%s %d review-started" % (kind, round_number)) in self.lines

    def code_mark(self, which, round_number):
        """The sha of a code round's start or end line, the last winning, or
        None."""
        prefix = "code %d %s " % (round_number, which)
        sha = None
        for line in self.lines:
            if line.startswith(prefix):
                sha = line[len(prefix):].strip()
        return sha

    def code_round(self):
        """The newest code round with a start line, or 0."""
        newest = 0
        for line in self.lines:
            match = re.match(r"^code ([1-9][0-9]*) start ", line)
            if match:
                newest = max(newest, int(match.group(1)))
        return newest

    def next_number(self, kind):
        """The number a round's new findings start at: the last review's
        next, or 1."""
        last = self.last_review(kind)
        return last.next if last else 1

    # --- writing ---

    def append(self, *lines):
        """Append lines to the state file, or raise a refused Failure."""
        self.persist(*lines)
        self.lines.extend(lines)

    def persist(self, *lines):
        """Append lines to the state file on disk only: for lines already
        added to self.lines so the files written before them saw them."""
        try:
            with open(self.path, "ab") as handle:
                handle.write("".join(line + "\n" for line in lines).encode("utf-8"))
        except OSError as error:
            raise refused(
                "Could not write the loop state file %s: %s" % (self.path, error),
                "Otherwise tell the user the loop state file cannot be written, and stop.",
            )


def reviewed_line(kind, round_number, signed_off, open_numbers, counts, next_number, new, closed, checks):
    numbers = ",".join(str(n) for n in open_numbers) or "-"
    return "%s %d reviewed %s %s counts %d %d %d next %d new %d closed %d checks %s" % (
        kind, round_number, "signed-off" if signed_off else "open", numbers, counts[0], counts[1], counts[2],
        next_number, new, closed, checks)


# --- the Doorbell lines, byte-identical to the ones the Roles composed (ADR 0002) ---

REVIEW_FILES = {"plan": ("Plan-Reviewer", "PLAN-REVIEW.md"), "code": ("Code-Reviewer", "CODEREVIEW.md")}


def review_doorbell(review):
    role, name = REVIEW_FILES[review.kind]
    if review.signed_off:
        return "VDD %s: %s SIGNED OFF, round %d." % (role, name, review.round)
    return "VDD %s: %s written, round %d: %d blocker, %d major, %d minor. Read it." % (
        (role, name, review.round) + tuple(review.counts))


def planner_doorbell(tracker, round_number):
    return "VDD Planner: %s/ ready, round %d. Read spec.md and issues/." % (tracker, round_number)


def coder_doorbell(round_number):
    return "VDD Coder: FIXES.md written, round %d. Read it." % round_number


def open_loop(loop, command):
    """Refuse a round command on a version 1 or a closed loop."""
    loopfile.refuse_v1(loop, command)
    if not loop.is_open():
        raise Failure(
            "The loop %s is closed. Nothing was written." % loop.slug,
            "Tell the user the loop %s is closed. To carry on, they ask the Orchestrator to reopen it." % loop.slug,
        )
    return State(loop.dir)
