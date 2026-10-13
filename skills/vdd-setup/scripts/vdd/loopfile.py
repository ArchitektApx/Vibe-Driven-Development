"""LOOP.md: the Feature slug, the tracker and the Harness: line."""

import os
import re

from . import textfile
from .out import Failure

LINE = re.compile(r"^([A-Za-z][A-Za-z ]*):[ \t]*(.*?)[ \t]*$")


class Loop:
    def __init__(self, root, fields):
        self.root = root
        self.fields = fields
        self.slug = fields.get("Feature", "")
        self.harness_label = fields.get("Harness", "")
        tracker = fields.get("Tracker", "").replace("\\", "/").strip()
        while tracker.endswith("/"):
            tracker = tracker[:-1]
        self.tracker = tracker

    def tracker_ok(self):
        """A tracker path inside the project: relative, no .. segment."""
        if not self.tracker or self.tracker.startswith("/") or re.match(r"^[A-Za-z]:", self.tracker):
            return False
        return ".." not in self.tracker.split("/")

    def tracker_dir(self):
        return os.path.join(self.root, *self.tracker.split("/"))

    def is_codex(self):
        """The Harness: line names Codex, as the 0.15 hook read it: Codex, then
        nothing or a character that cannot continue a name."""
        return re.match(r"^Codex(?![A-Za-z0-9_-])", self.harness_label) is not None


def read(root):
    """The Loop file in root, or None when there is none."""
    lines = textfile.lines(os.path.join(root, "LOOP.md"))
    if lines is None:
        return None
    fields = {}
    for line in lines:
        match = LINE.match(line)
        if match and match.group(1) not in fields:
            fields[match.group(1)] = match.group(2)
    return Loop(root, fields)


def require(root):
    """The Loop file with a usable tracker, or a Failure naming the fix."""
    loop = read(root)
    if loop is None:
        raise Failure(
            "No LOOP.md in %s." % root,
            "Run the command from the repository root. If LOOP.md is not there either, tell the user "
            "to start a loop with vdd-start-loop.",
        )
    if not loop.tracker_ok():
        raise Failure(
            "LOOP.md names no usable Tracker: line (a path inside the repository, such as .scratch/<slug>/).",
            "Tell the user LOOP.md's Tracker: line is missing or malformed, and stop.",
        )
    return loop
