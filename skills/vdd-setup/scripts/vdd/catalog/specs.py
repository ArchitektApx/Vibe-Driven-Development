"""Every command as data: its group, its name and its options, each with a
kind, whether it is required and the values it takes. The catalog is the
only list of the groups and their commands."""

from __future__ import annotations

from typing import Dict, Tuple

VALUE = "value"
FLAG = "flag"
# An option that may be given more than once; its value is the list of its
# values in order, empty when not given.
LIST = "list"

# Command group -> one-line summary, for the top-level help.
GROUPS = {
    "brainstorm": "The Brainstormer's idea store: the overview, one idea, a search, and every write to it.",
    "codex-stop": "The Codex Stop hook. Codex runs it at a turn end; a Role never does.",
    "coder": "The Coder's round: start it on the feature branch, then check FIXES.md and record its end.",
    "doorbell": "Ring, wait for and take Doorbells between the Planner and the Orchestrator.",
    "loop": "Start a loop, and show, change, close or reopen its Loop file.",
    "pr": "The PR-Author's PR: check the template, history and preflight, then push, open and close.",
    "orchestrator": "The Orchestrator's steps: place the Workflow, and act on each hosted Role's return.",
    "review": "The Plan-Reviewer's and the Code-Reviewer's round: write its frame, then check it.",
    "setup": "Check this repository and machine for a VDD loop, and make the changes Setup owns.",
    "wayfinder": "The Wayfinder's start: the effort's map, Matt Pocock's wayfinder, and the briefing.",
}

# The Roles an option names. Loop show's are the keys of loopfile.ROLES and
# review's of review.rounds.REVIEWERS, in their order.
ROLES = ("Planner", "Plan-Reviewer", "Coder", "Code-Reviewer", "Orchestrator", "PR-Author")
DOORBELL_ROLES = ("Planner", "Orchestrator")
REVIEWERS = ("Plan-Reviewer", "Code-Reviewer")
HOSTED = ("Plan-Reviewer", "Coder", "Code-Reviewer")


class Option:
    """One option of a command: --<name>, its kind, whether the command
    refuses to run without it, and the values it takes (any when empty)."""

    def __init__(self, name: str, kind: str = VALUE, required: bool = False, choices: Tuple[str, ...] = ()) -> None:
        self.name = name
        self.kind = kind
        self.required = required
        self.choices = choices


def value(name: str, required: bool = False, choices: Tuple[str, ...] = ()) -> Option:
    return Option(name, VALUE, required, choices)


def flag(name: str) -> Option:
    return Option(name, FLAG)


def listed(name: str, required: bool = False) -> Option:
    return Option(name, LIST, required)


class Command:
    """One command: its group, its name ("" in a group that is one
    command) and its options in order. An option given twice keeps its first
    place and takes the later entry, so a command can tighten a group-common
    option."""

    def __init__(self, group: str, name: str, *options: Option) -> None:
        self.group = group
        self.name = name
        self.options: Dict[str, Option] = {}
        for option in options:
            self.options[option.name] = option

    @property
    def label(self) -> str:
        """The command as typed after the tool: "loop new", "setup"."""
        return "%s %s" % (self.group, self.name) if self.name else self.group


def group(name: str, common: Tuple[Option, ...], commands: Dict[str, Tuple[Option, ...]]) -> Dict[str, Command]:
    return {command: Command(name, command, *(common + options)) for command, options in commands.items()}


WRITE = flag("write")
SLUG = value("slug", required=True)
HARNESS = value("harness", required=True)

LOOP = group("loop", (value("slug"), value("harness")), {
    "new": (SLUG, HARNESS, value("base"), value("branch"), value("minors"), value("pr"),
            value("leftover", choices=("continue",)), WRITE),
    "aside": (SLUG, WRITE),
    "show": (value("role", choices=ROLES),),
    # --feature, --base-branch, --feature-branch, --base and --branch are
    # named only to refuse them: a running loop's identity never changes.
    "set": (value("minors"), value("pr"), value("harness-line"), WRITE, value("feature"), value("base-branch"),
            value("feature-branch"), value("base"), value("branch")),
    "fold": (SLUG, HARNESS, flag("escalation-refused"), WRITE),
    "close": (WRITE,),
    "reopen": (WRITE,),
})

DOORBELL = group("doorbell", (value("role", required=True, choices=DOORBELL_ROLES), HARNESS, value("slug")), {
    "ring": (WRITE,),
    "wait": (),
    "take": (value("pasted"), flag("resumed")),
})

PR = group("pr", (SLUG, HARNESS), {
    "check": (),
    "open": (value("path", required=True, choices=("open", "push-only", "existing")), WRITE),
})

CODER = group("coder", (value("slug"), WRITE), {
    "start": (),
    "check": (),
})

REVIEW = group("review", (), {
    "start": (value("role", required=True, choices=REVIEWERS), value("slug"), WRITE),
    "check": (value("role", required=True, choices=REVIEWERS), value("slug"), WRITE),
    "add": (SLUG, value("from", required=True), WRITE),
})

ORCHESTRATOR = group("orchestrator", (value("slug"), value("harness")), {
    "start": (),
    "return": (HARNESS, value("role", required=True, choices=("Planner",) + HOSTED)),
    "respawn": (value("role", required=True, choices=HOSTED), value("policy"), flag("once"), WRITE),
    "tokens": (value("role", required=True, choices=HOSTED), value("tokens", required=True)),
})

WAYFINDER = group("wayfinder", (), {
    "start": (value("effort", required=True), value("skill-dir", required=True)),
})

METRICS = (value("importance"), value("size"), value("fog"))

# An option another command takes is refused on this one, never silently
# ignored.
BRAINSTORM = group("brainstorm", (), {
    "start": (value("page"),),
    "show": (value("idea", required=True),),
    "find": (listed("text", required=True),),
    "check": (),
    "new": (value("slug", required=True), value("title", required=True), value("tldr", required=True),
            value("parent"), value("summary"), listed("relate"), listed("despite"), WRITE) + METRICS,
    "note": (value("idea", required=True), value("section"), listed("text"), value("tick"), WRITE),
    "set": (listed("idea", required=True), value("status"), value("decision"), value("reopen-when"), value("tldr"),
            value("title"), WRITE) + METRICS,
    "move": (listed("set", required=True), WRITE),
    "split": (value("idea", required=True), listed("part", required=True), WRITE),
    "merge": (value("idea", required=True), value("into", required=True), value("reason", required=True),
              value("reopen-when", required=True), WRITE),
    "rename": (value("idea", required=True), value("to", required=True), WRITE),
    "cleanup": (listed("status"), listed("idea"), value("older"), WRITE),
    "migrate": (listed("event"), WRITE),
})

# Group -> its commands, for a group whose first word is a command.
COMMANDS: Dict[str, Dict[str, Command]] = {
    "brainstorm": BRAINSTORM,
    "coder": CODER,
    "doorbell": DOORBELL,
    "loop": LOOP,
    "orchestrator": ORCHESTRATOR,
    "pr": PR,
    "review": REVIEW,
    "wayfinder": WAYFINDER,
}

# A group that is one command: its options follow the group.
SINGLE: Dict[str, Command] = {
    "setup": Command("setup", "", HARNESS, value("listed", required=True),
                     value("glossary-named", required=True, choices=("yes", "no", "absent")),
                     value("user-answer", choices=("resolves", "does-not-resolve")), WRITE),
}

# codex-stop has its own entry and is not parsed here: it exits 0 on every
# path (ADR 0008), and a refusal exits non-zero.
