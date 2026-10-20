"""The entry format of FIXES.md, the Coder's Working file: the "##" headings
of a Ticket and of a finding, their labels and the entries of a parsed file.
The coder command lints and frames the file; the reviews read the Coder's
answers from it."""

import re

from . import workfile

NAME = "FIXES.md"
TICKET_HEADING = re.compile(r"^## Ticket ([0-9]+): (.+?)\s*$")
FINDING_HEADING = re.compile(r"^## Finding ([0-9]+)\. (\S+): (.+?)\s*$")
TICKET_LABELS = ("Files", "Change", "Verified", "Deviations", "Why")
FINDING_LABELS = ("Answer", "Why")


class Entry:
    """One "##" entry of FIXES.md and its labels."""

    def __init__(self, heading):
        self.heading = heading
        self.body = []

    def labels(self, names):
        """label -> (joined text, Line): the label line plus every line after
        it up to the next label or heading, joined with single spaces."""
        found = {}
        current = None
        for line in self.body:
            label = workfile.label_of(line, names)
            if label:
                current = [line.text[len(label) + 1:].strip(), line]
                if label not in found:
                    found[label] = current
                continue
            if current is not None and line.frame and line.text.strip():
                current[0] = (current[0] + " " + line.text.strip()).strip()
        return dict((label, tuple(value)) for label, value in found.items())


def entries(parsed):
    out = []
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
