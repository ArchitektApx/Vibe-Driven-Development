"""Dispatch and the top level of --help. Each command group lives in its own
module, imported only when that group runs."""

from __future__ import annotations

from types import ModuleType

from . import args, places
from .out import Failure, Output, refused

# Command group -> one-line summary.
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

ABOUT = [
    "The VDD tool: the program Vibe Driven Development's Roles run.",
    "Run it as %s <group> ... (python3 on macOS and Linux, py -3 on native Windows).",
    "Every command prints plain text, one fact per line, and ends with a Next: line naming your next step.",
    'A line starting Tell the user verbatim: "..." is for the user: relay the quoted text unchanged.',
    "The exit code is zero or not; the reason is always in the text.",
]


def top_help() -> int:
    out = Output()
    for text in ABOUT:
        out.line(text % places.command() if "%s" in text else text)
    out.line()
    out.line("Command groups:")
    for name in sorted(GROUPS):
        out.line("  %-13s %s" % (name, GROUPS[name]))
    return out.finish("Run %s <group> --help for the group your skill names." % places.command())


def load(name: str) -> ModuleType:
    """The module of a command group, which has run(argv). A plain relative
    import: the static check refuses an import by a computed name."""
    if name == "brainstorm":
        from .brainstorm import brainstorm as module
    elif name == "codex-stop":
        from . import codex_hook as module
    elif name == "coder":
        from . import coder as module
    elif name == "doorbell":
        from . import doorbell as module
    elif name == "loop":
        from .loop import loop as module
    elif name == "orchestrator":
        from . import orchestrator as module
    elif name == "review":
        from .review import review as module
    elif name == "pr":
        from . import pr as module
    elif name == "wayfinder":
        from . import wayfinder as module
    else:
        from .setup import setup as module
    return module


def main(argv: list[str]) -> int:
    try:
        if not argv or argv[0] in ("-h", "--help", "help"):
            return top_help()
        if argv[0] not in GROUPS:
            args.unknown_command(argv[0], "%s --help" % places.command())
        return load(argv[0]).run(argv[1:])
    except Failure as failure:
        return failure.emit()
    except OSError as error:
        return refused(
            "A file could not be read or written: %s" % error,
            "Otherwise tell the user which file it names and that the command could not run, and stop.",
        ).emit()
