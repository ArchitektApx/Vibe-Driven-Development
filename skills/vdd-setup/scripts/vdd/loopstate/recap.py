"""The Recap, .scratch/<slug>/RECAP.md: the account of one loop that only
the tool writes and no Role reads during the loop, and its records,
.scratch/<slug>/recap.json.

RECAP.md is rendered whole on every write: its header and rounds table from
the state file, its sections, Tickets, Plan findings, Code findings, Commits
and Not carried, from the records. A record has a key, a section and its
Markdown lines; a record put under an existing key replaces it, so a rerun
never adds a section twice. A loop open across the upgrade to the records
has a RECAP.md and no recap.json: the first load parses each section of it
into one seed record, placed first in its section.

Every command that records a round runs one record step in a fixed order:
everything computed and every refusal checked, then the records written, then
the state line or lines appended in one write, the commit point, then
RECAP.md rendered, then the Role's own Working file rewritten. A rerun after
the commit point is "already recorded" and renders RECAP.md again.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Iterable, Sequence

from .. import gitcmd, loopfile, textfile, workfile
from ..out import Failure, refused

if TYPE_CHECKING:
    from ..loopfile import Loop
    from .state import Review, State

NAME = "RECAP.md"
RECORDS_NAME = "recap.json"
RECORDS_FORMAT = 1
SECTIONS = ("Tickets", "Plan findings", "Code findings", "Commits", "Not carried")


def path(loop: Loop) -> str:
    return os.path.join(loop.dir, NAME)


def read_sections(loop: Loop) -> dict[str, list[str]]:
    """Section name -> its lines, from the RECAP.md on disk: the seed of a
    loop that has no records yet."""
    sections: dict[str, list[str]] = dict((name, []) for name in SECTIONS)
    text = textfile.read(path(loop))
    if text is None:
        return sections
    current = None
    # A heading quoted in a fence or comment is prose.
    for line in workfile.classify(text.split("\n")):
        if line.frame and line.text.startswith("## ") and line.text[3:].strip() in SECTIONS:
            current = line.text[3:].strip()
            continue
        if current is not None:
            sections[current].append(line.text)
    for name in SECTIONS:
        lines = sections[name]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
    return sections


def open_after(review: Review) -> str:
    if review.signed_off:
        if review.counts[2]:
            return "SIGNED OFF, %d minor left" % review.counts[2]
        return "SIGNED OFF"
    return "%d blocker, %d major, %d minor" % tuple(review.counts)


def loop_line(name: str, reviews: dict[int, Review], placed: Review | None = None) -> str:
    """The Loop's line. reviews are the reviewers' rounds; placed, when given,
    is the newest record the Workflow places, which may be a user entry."""
    if not reviews:
        return "%s Loop: not started." % name
    last = placed or reviews[max(reviews)]
    count = len(reviews)
    rounds = "%d round%s" % (count, "" if count == 1 else "s")
    if last.user:
        return "%s Loop: %s, reopened by the user's findings after round %d." % (name, rounds, last.round)
    if last.signed_off:
        return "%s Loop: %s, signed off in round %d." % (name, rounds, last.round)
    return "%s Loop: %s, open after round %d." % (name, rounds, last.round)


def code_line(state: State) -> str:
    """The code Loop's line, naming a Coder round no review has recorded
    yet. It counts the reviewers' rounds only; the user's entries reopen it."""
    placed = state.reviews("code")
    line = loop_line("Code", state.reviewer_reviews("code"), placed[max(placed)] if placed else None)
    newest = state.code_round()
    if not newest or newest in placed:
        return line[:-1] + fold_text(state) + "."
    if not placed:
        return "Code Loop: round %d, not reviewed yet." % newest
    return "%s; round %d not reviewed yet." % (line[:-1], newest)


def fold_text(state: State) -> str:
    """The fold's outcome for the Code Loop line: folded or not folded."""
    outcome = state.fold_record()
    if outcome is None:
        return ""
    if outcome.kind == "folded":
        return "; folded"
    return "; not folded: " + outcome.reason


def render(loop: Loop, state: State, sections: dict[str, list[str]]) -> str:
    base = loop.base
    branch = loop.branch
    plan = state.reviewer_reviews("plan")
    code = state.reviewer_reviews("code")
    users = state.user_entries()
    lines = [
        "# Recap: %s" % loop.slug,
        "",
        "Written by the VDD tool only. No Role reads it during the loop.",
        "",
        "Branch: %s from %s." % (branch, base),
        loop_line("Plan", plan),
        code_line(state),
        "",
        "| Loop | Round | New findings | Closed | Open after | Checks |",
        "|---|---|---|---|---|---|",
    ]
    for kind, reviews in (("plan", plan), ("code", code)):
        for number in sorted(reviews):
            review = reviews[number]
            lines.append("| %s | %d | %d | %d | %s | %s |" % (
                kind, number, review.new, review.closed, open_after(review), review.checks or "none"))
            if kind == "code" and number in users:
                entry = users[number]
                lines.append("| code | %d, user | %d | 0 | %s | none |" % (number, entry.new, open_after(entry)))
    for name in SECTIONS:
        lines += ["", "## " + name]
        if sections[name]:
            lines += [""] + sections[name]
    return "\n".join(lines) + "\n"


# --- the records ---

class Record:
    """One record: its key, its section, its Markdown lines, and data the
    command that wrote it reads back on a rerun."""

    def __init__(self, key: str, section: str, lines: Sequence[str], data: dict[str, Any] | None = None) -> None:
        if section not in SECTIONS:
            raise ValueError("No Recap section %s." % section)
        self.key = key
        self.section = section
        self.lines = list(lines)
        self.data: dict[str, Any] = dict(data or {})

    def as_json(self) -> dict[str, Any]:
        found: dict[str, Any] = {"key": self.key, "section": self.section, "lines": self.lines}
        if self.data:
            found["data"] = self.data
        return found


def findings_key(kind: str, round_number: int) -> str:
    return "findings %s %d" % (kind, round_number)


def not_carried_key(round_number: int) -> str:
    return "not-carried code %d" % round_number


TICKETS_KEY = "tickets 1"


FOLD_PREFIX = "fold "


def fold_key(signed: str) -> str:
    """The key of a fold's record, Commits or Not folded: the signed sha, so
    a reopen and a second code Sign-off add a second fold."""
    return FOLD_PREFIX + signed


def moved_fold(store: Records, root: str, branch: str, signed: str) -> Record | None:
    """The fold record of the signed commit when the branch is at its
    recorded tip, as a fold that moved the ref and failed before its state
    line leaves it; else None. Raises gitcmd.Refused for a sandboxed call."""
    record = store.get(fold_key(signed))
    tip = record.data.get("tip") if record is not None else None
    if record is None or not isinstance(tip, str) or tip == signed:
        return None
    call = gitcmd.answered(gitcmd.git(root, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch))
    if call.refused:
        raise gitcmd.Refused(call)
    at = call.out.strip() if call.code == 0 else ""
    return record if at == tip else None


def records_path(loop: Loop) -> str:
    return os.path.join(loop.dir, RECORDS_NAME)


def unreadable(loop: Loop, why: str) -> Failure:
    shown = textfile.shown(records_path(loop))
    return Failure(
        "%s %s. Nothing was written." % (shown, why),
        "Tell the user the Recap's records file %s cannot be read, and stop: the tool leaves it as it is." % shown,
    )


class Records:
    """The loop's Recap records, in order."""

    def __init__(self, loop: Loop, records: list[Record]) -> None:
        self.loop = loop
        self.records = records

    @classmethod
    def load(cls, loop: Loop) -> Records:
        """The records from recap.json, or the seed from RECAP.md when there
        is no recap.json. Refuses a file that does not parse or has a newer
        format version."""
        text = textfile.read(records_path(loop))
        if text is None:
            return cls(loop, seed(loop))
        try:
            data = json.loads(text)
        except ValueError:
            raise unreadable(loop, "is not a Recap records file this tool wrote")
        version = data.get("format") if isinstance(data, dict) else None
        if isinstance(version, int) and not isinstance(version, bool) and version > RECORDS_FORMAT:
            raise Failure(
                "%s has format version %d, which this copy of the VDD tool does not know. Nothing was written."
                % (textfile.shown(records_path(loop)), version),
                "Tell the user this copy of the VDD tool is out of date and to rerun Setup.",
            )
        if version != RECORDS_FORMAT or not isinstance(data.get("records"), list):
            raise unreadable(loop, "is not a Recap records file this tool wrote")
        records: list[Record] = []
        for item in data["records"]:
            try:
                records.append(Record(str(item["key"]), str(item["section"]), [str(line) for line in item["lines"]],
                                      dict(item.get("data") or {})))
            except (KeyError, TypeError, ValueError):
                raise unreadable(loop, "is not a Recap records file this tool wrote")
        return cls(loop, records)

    def get(self, key: str) -> Record | None:
        for record in self.records:
            if record.key == key:
                return record
        return None

    def put(self, record: Record) -> None:
        """Add record, replacing the one with its key in place."""
        for index, found in enumerate(self.records):
            if found.key == record.key:
                self.records[index] = record
                return
        self.records.append(record)

    def save(self) -> None:
        """Write recap.json whole, or raise a refused Failure. Nothing counts
        before the commit point, so a failure here leaves nothing to undo."""
        data = {"format": RECORDS_FORMAT, "records": [record.as_json() for record in self.records]}
        textfile.write_or_refuse(records_path(self.loop), json.dumps(data, indent=1) + "\n",
                                 textfile.shown(records_path(self.loop)),
                                 "Otherwise tell the user the Recap's records cannot be written, and stop.")

    def sections(self, folds: set[str]) -> dict[str, list[str]]:
        """Section name -> its lines: each record's lines, a blank line
        between two records. A fold's record counts only when folds, the
        signed commits the state has a fold line for, holds its commit: the
        fold saves it before the ref moves, and a refusal or a kill there
        leaves it behind."""
        sections: dict[str, list[str]] = dict((name, []) for name in SECTIONS)
        for record in self.records:
            if record.key.startswith(FOLD_PREFIX) and record.key[len(FOLD_PREFIX):] not in folds:
                continue
            lines = list(record.lines)
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            if not lines:
                continue
            if sections[record.section]:
                sections[record.section].append("")
            sections[record.section].extend(lines)
        return sections


def seed(loop: Loop) -> list[Record]:
    """One seed record per section of the RECAP.md an earlier version wrote,
    or none."""
    sections = read_sections(loop)
    return [Record("seed %s" % name, name, sections[name]) for name in SECTIONS if sections[name]]


# --- the record step ---

def record(
    loop: Loop, state: State, store: Records, records: Iterable[Record], lines: Sequence[str], reopen: bool = False,
) -> None:
    """Steps 2 to 4 of the record step: the records, the state lines in one
    write, RECAP.md. store is the records the command loaded before its dry
    run returned and before its first write, so a records file it cannot
    read refuses before anything is written. The caller rewrites its Working
    file after it."""
    for item in records:
        store.put(item)
    store.save()
    commit(loop, state, store, lines, reopen)


def commit(loop: Loop, state: State, store: Records, lines: Sequence[str], reopen: bool = False) -> None:
    """Steps 3 and 4: the state lines appended in one write, the commit point,
    then RECAP.md rendered from store. With reopen, "loop open" goes in the
    same write."""
    if reopen:
        try:
            loopfile.reopen(state, *lines)
        except OSError as error:
            raise textfile.write_refusal(
                "the loop state file %s" % textfile.shown(state.path), error,
                "Otherwise tell the user the loop state file cannot be written, and stop.")
    else:
        state.append(*lines)
    render_recap(loop, state, store)


def render_recap(loop: Loop, state: State, store: Records) -> bool:
    """Write RECAP.md whole from the state and the caller's records, when its
    text differs from the file's; whether it wrote. A failure here comes after
    the commit point: the round is recorded."""
    text = render(loop, state, store.sections(state.fold_signed()))
    try:
        if textfile.read(path(loop)) == text:
            return False
        textfile.write_text(path(loop), text)
    except OSError as error:
        raise refused(
            ["Could not write %s: %s" % (textfile.shown(path(loop)), textfile.reason(error)),
             "Recorded in %s/%s; the Recap could not be written." % (loop.tracker, os.path.basename(state.path))],
            "Otherwise tell the user the round is recorded and the Recap %s cannot be written; once it can be, "
            "the same command run again writes it. Then stop." % textfile.shown(path(loop)),
        )
    return True
