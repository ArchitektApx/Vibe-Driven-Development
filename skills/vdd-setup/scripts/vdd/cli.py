"""Dispatch into the command groups. Each group lives in its own module,
imported only when that group runs; the catalog lists them."""

from __future__ import annotations

import os
import sys
from types import ModuleType

from . import catalog, textfile
from .catalog import help as helps
from .out import Failure, refused


class NoGroupBranch(RuntimeError):
    """A group in the catalog's list that load has no import for."""


def load(name: str) -> ModuleType:
    """The module of a command group, which has run(argv). A plain relative
    import: the static check refuses an import by a computed name."""
    if name == "brainstorm":
        from .brainstorm import brainstorm as module
    elif name == "codex-stop":
        from . import codex_hook as module
    elif name == "coder":
        from .coder import coder as module
    elif name == "doorbell":
        from . import doorbell as module
    elif name == "loop":
        from .loop import loop as module
    elif name == "orchestrator":
        from .orchestrator import orchestrator as module
    elif name == "review":
        from .review import review as module
    elif name == "pr":
        from .pr import pr as module
    elif name == "wayfinder":
        from . import wayfinder as module
    elif name == "setup":
        from .setup import setup as module
    else:
        raise NoGroupBranch("cli.load has no branch for the group %s: add one beside the others." % name)
    return module


def main(argv: list[str]) -> int:
    try:
        return dispatch(argv)
    except BrokenPipeError:
        return closed_pipe()


def closed_pipe() -> int:
    """The end of a run whose reader closed the output pipe: nothing more is
    written, and standard output points at the null device, so the
    interpreter's flush at exit writes nowhere and prints no error."""
    try:
        null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null, sys.stdout.fileno())
        os.close(null)
    except (OSError, ValueError):
        pass
    return 1


def dispatch(argv: list[str]) -> int:
    try:
        if not argv or argv[0] in ("-h", "--help", "help"):
            return helps.top()
        if argv[0] not in catalog.GROUPS:
            catalog.unknown_command(argv[0], catalog.line("", help=True))
        return load(argv[0]).run(argv[1:])
    except Failure as failure:
        return failure.emit()
    except BrokenPipeError:
        raise
    except OSError as error:
        return refused(
            "A file could not be read or written: %s" % textfile.described(error),
            "Otherwise tell the user which file it names and that the command could not run, and stop.",
        ).emit()
    except Exception as error:  # noqa: B902 - the last resort; KeyboardInterrupt and SystemExit pass
        return Failure(
            "The VDD tool hit an internal error: %s: %s" % (type(error).__name__, error),
            "Tell the user the VDD tool hit an internal error and show them the line above, so they can report it; "
            "then stop.",
        ).emit()
