"""The entry format of FIXES.md, the Coder's Working file: the "##" headings
of a Ticket and of a finding, their labels and the entries of a parsed file.
The coder command lints and frames the file; the reviews read the Coder's
answers from it."""

from __future__ import annotations

import re
from typing import Iterable

from . import workfile

NAME = "FIXES.md"
TICKET_HEADING = re.compile(r"^## Ticket ([0-9]+): (.+?)\s*$")
FINDING_HEADING = re.compile(r"^## Finding ([0-9]+)\. (\S+): (.+?)\s*$")
TICKET_LABELS = ("Files", "Change", "Verified", "Deviations", "Why")
FINDING_LABELS = ("Answer", "Why")


class Entry:
    """One "##" entry of FIXES.md and its labels."""

    def __init__(self, heading: workfile.Line) -> None:
        self.heading = heading
        self.body: list[workfile.Line] = []

    def labels(self, names: Iterable[str]) -> dict[str, tuple[str, workfile.Line]]:
        """label -> (joined text, Line): the label line plus every line after
        it up to the next label or heading, joined with single spaces."""
        # Not merged with workfile.Block.labels on purpose: in FIXES.md a
        # label runs across paragraphs, so a multi-paragraph Why: reaches the
        # reviewer whole; in a review file a blank line ends a label and
        # starts the finding's own text.
        found: dict[str, tuple[str, workfile.Line]] = {}
        # The label whose text the lines below run on, None after a repeated
        # label: only a label's first line counts.
        current = None
        for line in self.body:
            label = workfile.label_of(line, names)
            if label:
                current = None
                if label not in found:
                    found[label] = (line.text[len(label) + 1:].strip(), line)
                    current = label
                continue
            if current is not None and line.frame and line.text.strip():
                text, start = found[current]
                found[current] = ((text + " " + line.text.strip()).strip(), start)
        return found


def entries(parsed: workfile.Parsed) -> list[Entry]:
    out: list[Entry] = []
    current = None
    for line in parsed.lines:
        if line.frame and line.text.startswith("## "):
            current = Entry(line)
            out.append(current)
        elif line.frame and line.text.startswith("# "):
            current = None
        elif current is not None:
            current.body.append(line)
    return out
