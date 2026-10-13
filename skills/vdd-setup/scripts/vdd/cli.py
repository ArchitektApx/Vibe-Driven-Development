"""Dispatch and the top level of --help. Each command group lives in its own
module, imported only when that group runs."""

import importlib

from . import places
from .out import Failure, Output

# Command group -> (module, one-line summary). Each module has run(argv).
GROUPS = {
    "setup": ("setup", "Check this repository and machine for a VDD loop, and make the changes Setup owns."),
}

ABOUT = [
    "The VDD tool: the program Vibe Driven Development's Roles run.",
    "Run it as %s <group> ... (python3 on macOS and Linux, py -3 on native Windows).",
    "Every command prints plain text, one fact per line, and ends with a Next: line naming your next step.",
    'A line starting Tell the user verbatim: "..." is for the user: relay the quoted text unchanged.',
    "The exit code is zero or not; the reason is always in the text.",
]


def top_help():
    out = Output()
    for text in ABOUT:
        out.line(text % places.command() if "%s" in text else text)
    out.line()
    out.line("Command groups:")
    for name in sorted(GROUPS):
        out.line("  %-11s %s" % (name, GROUPS[name][1]))
    return out.finish("Run %s <group> --help for the group your skill names." % places.command())


def unknown(name):
    raise Failure(
        [
            "Unknown command: %s" % name,
            "This copy of the VDD tool may be older than the skill that called it: rerun Setup.",
        ],
        "Tell the user this copy of the VDD tool is out of date and to rerun Setup, then retry.",
    )


def main(argv):
    try:
        if not argv or argv[0] in ("-h", "--help", "help"):
            return top_help()
        group = GROUPS.get(argv[0])
        if group is None:
            unknown(argv[0])
        module = importlib.import_module("." + group[0], __package__)
        return module.run(argv[1:])
    except Failure as failure:
        return failure.emit()
