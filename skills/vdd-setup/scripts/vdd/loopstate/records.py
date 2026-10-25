"""The Recap's records, .scratch/<slug>/recap.json: one record per key,
each with its section and Markdown lines, in order. A record put under an
existing key replaces it, so a rerun never adds a section twice. A loop open
across the upgrade to the records has a RECAP.md and no recap.json: the
first load parses each section of it into one seed record, placed first in
its section."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Sequence

from .. import gitcmd, textfile
from ..out import Failure
from .recap import SECTIONS, read_sections

if TYPE_CHECKING:
    from ..loopfile import Loop

RECORDS_NAME = "recap.json"
RECORDS_FORMAT = 1

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
