"""The helps the catalog prints: a group's help, one command's help, and the
top-level help with the list of groups."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple, Union

from .. import places
from ..out import Output
from .builder import line
from .specs import GROUPS

ABOUT = [
    "The VDD tool: the program Vibe Driven Development's Roles run.",
    "Run it as %s <group> ... (python3 on macOS and Linux, py -3 on native Windows).",
    "Every command prints plain text, one fact per line, and ends with a Next: line naming your next step.",
    'A line starting Tell the user verbatim: "..." is for the user: relay the quoted text unchanged.',
    "The exit code is zero or not; the reason is always in the text.",
]


class Only:
    """Group-wide lines that apply to the commands named, and are left out
    of every other command's help. With group=False they are left out of the
    group's help too: a command's own wording of a line the group's help
    words for several commands."""

    def __init__(self, commands: Sequence[str], *lines: str, group: bool = True) -> None:
        self.commands = tuple(commands)
        self.lines = lines
        self.group = group


class Help:
    """A group's help text: one block per command, in the order the group's
    help prints them, and the group-wide lines printed after every block. A
    group-wide entry is a line, or an Only for lines that apply to some
    commands. A group that is one command has one block, named "". apart
    puts a blank line between two blocks."""

    def __init__(self, blocks: Dict[str, List[str]], common: Sequence[Union[str, Only]] = (),
                 apart: bool = True) -> None:
        self.blocks = blocks
        self.common: List[Tuple[Optional[Tuple[str, ...]], bool, str]] = []
        for entry in common:
            if isinstance(entry, Only):
                self.common += [(entry.commands, entry.group, text) for text in entry.lines]
            else:
                self.common.append((None, True, entry))
        self.apart = apart

    def tail(self, name: Optional[str] = None) -> List[str]:
        """The group-wide lines after a blank line: every one, or those that
        apply to the command name, with no blank line left doubled or
        trailing."""
        lines: List[str] = []
        for commands, group, text in self.common:
            if name is None and not group:
                continue
            if name is not None and commands is not None and name not in commands:
                continue
            if text or (lines and lines[-1]):
                lines.append(text)
        while lines and not lines[-1]:
            lines.pop()
        return [""] + lines if lines else []

    def whole(self) -> List[str]:
        """Every block, then the group-wide lines."""
        lines: List[str] = []
        for block in self.blocks.values():
            if lines and self.apart:
                lines.append("")
            lines += block
        return lines + self.tail()

    def command(self, name: str) -> List[str]:
        """One command's block, then the group-wide lines that apply to it."""
        return self.blocks[name] + self.tail(name)


def show(lines: Sequence[str], next_step: str) -> int:
    """Print help lines and their Next: step."""
    out = Output()
    for text in lines:
        out.line(text)
    return out.finish(next_step)


def command(text: Help, group: str, name: str) -> int:
    """The help of one command in a group of several."""
    return show(text.command(name), "Run %s with the options above." % line(group, name))


def top() -> int:
    """The top-level help: what the tool is, and every group."""
    out = Output()
    for text in ABOUT:
        out.line(text % places.command() if "%s" in text else text)
    out.line()
    out.line("Command groups:")
    for name in sorted(GROUPS):
        out.line("  %-13s %s" % (name, GROUPS[name]))
    return out.finish("Run %s to list a group's commands, or %s for one command's usage."
                      % (line("<group>", help=True), line("<group>", "<command>", help=True)))
