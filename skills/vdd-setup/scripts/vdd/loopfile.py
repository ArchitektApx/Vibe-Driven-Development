"""The Loop file, .scratch/<slug>/loop.md, and the loop's state file,
.scratch/<slug>/loop-state.

The Loop file holds a loop's settings, format 2, one "<Name>: <value>" line
each. The state file is append-only: a version header, then "loop open" and
"loop closed" lines, the last one winning. A loop is a directory under
.scratch/ that holds both, and its slug is that directory's name. A root
LOOP.md is a format-1 Loop file from before this version: no command reads
it, and every command that needs a loop refuses while it exists.
"""

import os
import re
import subprocess

from . import textfile
from .out import TELL, Failure

SLUG_PATTERN = "[a-z0-9]+(-[a-z0-9]+)*"
SLUG = re.compile("^" + SLUG_PATTERN + "$")
FORMAT = 2
NAME = "loop.md"
STATE_NAME = "loop-state"
STATE_PREFIX = "vdd loop-state "
STATE_VERSION = "1"
ARMED_PREFIX = "codex-armed-"
ROOT_FILE = "LOOP.md"
ROOT_FIX = (
    "Delete `LOOP.md`. To carry on the loop it belongs to, run `vdd-start-loop` with its slug and answer continue."
)

LINE = re.compile(r"^([A-Za-z][A-Za-z ]*):[ \t]*(.*?)[ \t]*$")

IDENTITY = ("Feature", "Base branch", "Feature branch")
SETTINGS = ("Minors", "PR", "Fresh Coder", "Harness")
ORDER = ("Format",) + IDENTITY + SETTINGS
DEFAULTS = {"Minors": "leave", "PR": "ask at sign-off", "Fresh Coder": "never", "Harness": "Generic"}
MINORS = ("fix", "leave")
PR = ("yes", "ask at sign-off", "manual", "no")
FRESH_CODER = re.compile(r"^(every round|never|over [1-9][0-9]*k)$")
LABELS = {
    "claude-code": "Claude Code",
    "codex": "Codex",
    "cursor": "Cursor",
    "copilot-cli": "Copilot CLI",
    "generic": "Generic",
}

# The lines each Role acts on, as loop show --role prints them.
ROLES = {
    "Planner": ("Feature", "Harness"),
    "Plan-Reviewer": ("Minors", "Harness"),
    "Coder": ("Base branch", "Feature branch", "Harness"),
    "Code-Reviewer": ("Base branch", "Minors", "Harness"),
    "Orchestrator": IDENTITY + SETTINGS,
    "PR-Author": ("Base branch", "Feature branch", "PR", "Harness"),
}

OPEN = "open"
CLOSED = "closed"
NO_STATE = "no-state"


def accepted(name, value):
    """Whether value is one the line name accepts, matched exactly."""
    if name == "Minors":
        return value in MINORS
    if name == "PR":
        return value in PR
    if name == "Fresh Coder":
        return FRESH_CODER.match(value) is not None
    if name == "Harness":
        return value in LABELS.values()
    return bool(value)


def accepted_text(name):
    if name == "Minors":
        return "fix or leave"
    if name == "PR":
        return "yes, ask at sign-off, manual or no"
    if name == "Fresh Coder":
        return "every round, never, or over <n>k with <n> a whole number from 1"
    if name == "Harness":
        return ", ".join(LABELS.values())
    return "a value"


def harness_slug(label):
    for slug, text in LABELS.items():
        if text == label:
            return slug
    return "generic"


def fields_of(lines):
    """The first value of every "<Name>: <value>" line."""
    fields = {}
    for line in lines:
        match = LINE.match(line)
        if match and match.group(1) not in fields:
            fields[match.group(1)] = match.group(2)
    return fields


def scratch(root):
    return os.path.join(root, ".scratch")


def tracker_dir(root, slug):
    return os.path.join(scratch(root), slug)


def check_slug(slug):
    if not slug or SLUG.match(slug) is None:
        raise Failure(
            "Not a Feature slug: %s. A slug matches %s: lowercase letters and digits, in words joined by "
            "single hyphens." % (slug, SLUG_PATTERN),
            "Ask the user for a slug that matches %s, then run the command again with it." % SLUG_PATTERN,
        )


def refuse_root(root):
    """Refuse while a format-1 root LOOP.md exists."""
    if os.path.exists(os.path.join(root, ROOT_FILE)):
        raise Failure(
            [
                "LOOP.md at the repository root is a Loop file from before this version of VDD (format 1). "
                "No command reads it.",
                TELL % ROOT_FIX,
            ],
            "Relay the Tell the user verbatim line above unchanged, and stop.",
        )


# --- the state file ---

def read_state(directory):
    """OPEN or CLOSED from the state file in directory, or None when there is
    none. A file with no loop line reads as CLOSED."""
    path = os.path.join(directory, STATE_NAME)
    lines = textfile.lines(path, 2.0)
    if lines is None:
        return None
    if not lines or not lines[0].startswith(STATE_PREFIX):
        raise Failure(
            "%s is not a loop state file this tool wrote." % path,
            "Tell the user the loop state file is damaged, and stop.",
        )
    version = lines[0][len(STATE_PREFIX):].strip()
    if version != STATE_VERSION:
        raise Failure(
            "%s has format version %s, which this copy of the VDD tool does not know." % (path, version),
            "Tell the user this copy of the VDD tool is out of date and to rerun Setup.",
        )
    state = CLOSED
    for line in lines[1:]:
        parts = line.split()
        if len(parts) == 2 and parts[0] == "loop" and parts[1] in (OPEN, CLOSED):
            state = parts[1]
    return state


def append_state(directory, state):
    """Append "loop <state>" to the state file, writing its header first when
    the file is new."""
    path = os.path.join(directory, STATE_NAME)
    data = ""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        data += STATE_PREFIX + STATE_VERSION + "\n"
    data += "loop %s\n" % state
    with open(path, "ab") as handle:
        handle.write(data.encode("utf-8"))


def kind(root, slug):
    """What .scratch/<slug> is: None when it does not exist, OPEN or CLOSED
    for a loop, NO_STATE for any other existing path."""
    directory = tracker_dir(root, slug)
    if not os.path.lexists(directory):
        return None
    if os.path.isdir(directory) and os.path.isfile(os.path.join(directory, NAME)):
        state = read_state(directory)
        if state is not None:
            return state
    return NO_STATE


def delete_armed(directory):
    """Delete every Codex armed file in directory; the names deleted."""
    gone = []
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return gone
    for name in names:
        if name.startswith(ARMED_PREFIX):
            try:
                os.remove(os.path.join(directory, name))
                gone.append(name)
            except OSError:
                pass
    return gone


# --- the Loop file ---

class Loop:
    """One loop: its slug, its tracker directory and its Loop file's lines."""

    def __init__(self, root, slug):
        self.root = root
        self.slug = slug
        self.dir = tracker_dir(root, slug)
        self.tracker = ".scratch/" + slug
        self.file = os.path.join(self.dir, NAME)
        self.relative = ".scratch/%s/%s" % (slug, NAME)
        self.lines = textfile.lines(self.file, 2.0) or []
        self.fields = fields_of(self.lines)

    def check(self):
        """Refuse a Loop file this copy does not read, or one that lacks a
        line naming the loop."""
        value = self.fields.get("Format", "")
        if not value.isdigit() or int(value) != FORMAT:
            if value.isdigit() and int(value) > FORMAT:
                why = "%s has format %s, which this copy of the VDD tool does not know." % (self.relative, value)
            elif value:
                why = "%s has format %s, which this copy of the VDD tool does not read." % (self.relative, value)
            else:
                why = "%s has no Format: line, so this copy of the VDD tool does not read it." % self.relative
            raise Failure(
                [why, TELL % ("The Loop file %s is not one this copy of VDD reads: rerun Setup." % self.relative)],
                "Relay the Tell the user verbatim line above unchanged: rerun Setup. Then stop.",
            )
        for name in IDENTITY:
            if not self.fields.get(name):
                raise Failure(
                    "%s has no %s: line." % (self.relative, name),
                    "Tell the user the Loop file %s is damaged: it does not name the loop's %s. Then stop."
                    % (self.relative, name.lower()),
                )
        return self

    def setting(self, name):
        """(value, fault): the line's value, or its default with fault
        "missing" or "malformed"."""
        if name not in self.fields:
            if name in DEFAULTS:
                return DEFAULTS[name], "missing"
            return "", "missing"
        value = self.fields[name]
        if name in DEFAULTS and not accepted(name, value):
            return DEFAULTS[name], "malformed"
        return value, None

    def harness_file(self):
        return "harness-%s.md" % harness_slug(self.setting("Harness")[0])

    def state(self):
        return read_state(self.dir)

    def is_open(self):
        return self.state() == OPEN


def render(fields):
    """A Loop file's text from its lines' values, in the fixed order."""
    lines = ["# VDD Loop", ""]
    for name in ORDER:
        lines.append("%s: %s" % (name, fields[name]))
    return "\n".join(lines) + "\n"


def write(directory, fields):
    os.makedirs(directory, exist_ok=True)
    textfile.write(os.path.join(directory, NAME), render(fields).encode("utf-8"))


def replace_line(lines, name, value):
    """lines with name's line set to value: in place when it exists, else
    inserted after the last line that comes before it in the fixed order."""
    out = list(lines)
    for index, line in enumerate(out):
        match = LINE.match(line)
        if match and match.group(1) == name:
            out[index] = "%s: %s" % (name, value)
            return out
    position = len(out)
    earlier = ORDER[: ORDER.index(name)]
    for index, line in enumerate(out):
        match = LINE.match(line)
        if match and match.group(1) in earlier:
            position = index + 1
    out.insert(position, "%s: %s" % (name, value))
    return out


# --- finding the loop ---

def loops(root):
    """Every loop under .scratch/: (slug, state), by slug."""
    try:
        names = sorted(os.listdir(scratch(root)))
    except OSError:
        return []
    found = []
    for name in names:
        directory = os.path.join(scratch(root), name)
        if os.path.isdir(directory) and os.path.isfile(os.path.join(directory, NAME)):
            try:
                state = read_state(directory)
            except Failure:
                continue
            if state is not None:
                found.append((name, state))
    return found


def current_branch(root):
    """The checked-out branch, or "" on a detached HEAD or outside git."""
    try:
        proc = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError:
        return ""
    if proc.returncode != 0:
        return ""
    return textfile.decode(proc.stdout).strip()


def find(root, slug=None):
    """The loop --slug names, else the loop whose Feature branch is checked
    out, else the only open loop; a checked Loop. Refuses otherwise."""
    refuse_root(root)
    if slug is not None:
        return named(root, slug)
    every = loops(root)
    branch = current_branch(root)
    if branch:
        on_branch = [(name, state) for name, state in every if branch_of(root, name) == branch]
        for state in (OPEN, CLOSED):
            matches = [name for name, s in on_branch if s == state]
            if len(matches) == 1:
                return Loop(root, matches[0]).check()
            if len(matches) > 1:
                raise Failure(
                    "Several %s loops have the checked-out branch %s as their feature branch: %s."
                    % (state, branch, ", ".join(matches)),
                    "Ask the user which loop this is, then run the command again with --slug <slug>.",
                )
    opened = [name for name, state in every if state == OPEN]
    if len(opened) == 1:
        return Loop(root, opened[0]).check()
    if opened:
        raise Failure(
            "Several loops are open: %s. The tool cannot tell which one you mean." % ", ".join(opened),
            "Ask the user which loop this is, then run the command again with --slug <slug>.",
        )
    raise Failure(
        "No open loop under .scratch/, and none has the checked-out branch as its feature branch.",
        "Run the command again with --slug <slug> for the loop you mean; with none, ask the user for the slug, "
        "or tell them to start a loop with vdd-start-loop.",
    )


def branch_of(root, slug):
    lines = textfile.lines(os.path.join(tracker_dir(root, slug), NAME)) or []
    return fields_of(lines).get("Feature branch", "")


def named(root, slug):
    check_slug(slug)
    found = kind(root, slug)
    if found is None:
        raise Failure(
            "No loop %s: .scratch/%s/ does not exist." % (slug, slug),
            "Check the slug with the user, then run the command again with the right --slug.",
        )
    if found == NO_STATE:
        raise Failure(
            ".scratch/%s/ holds no loop the VDD tool started: it lacks %s or %s." % (slug, NAME, STATE_NAME),
            "Tell the user to run vdd-start-loop with the slug %s and answer continue, and stop." % slug,
        )
    return Loop(root, slug).check()


# --- the format-1 Loop file, read by the Doorbell and the hook until they
# move to the loop's tracker directory ---

class RootLoop:
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
        if not self.tracker or self.tracker.startswith("/") or re.match(r"^[A-Za-z]:", self.tracker):
            return False
        return ".." not in self.tracker.split("/")

    def tracker_dir(self):
        return os.path.join(self.root, *self.tracker.split("/"))

    def is_codex(self):
        return re.match(r"^Codex(?![A-Za-z0-9_-])", self.harness_label) is not None


def read(root):
    lines = textfile.lines(os.path.join(root, ROOT_FILE))
    if lines is None:
        return None
    return RootLoop(root, fields_of(lines))


def require(root):
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
