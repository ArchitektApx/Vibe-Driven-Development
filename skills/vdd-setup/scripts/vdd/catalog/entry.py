"""The entry of a command group: its help, a command it does not know, the
command's options, and the command context its handler receives."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

from . import help as helps
from .builder import line
from .parse import given, parse
from .refusals import missing, unknown_command
from .specs import COMMANDS, SINGLE, Command


class Context:
    """One command as its handler runs it: the group, the command ("" in a
    group that is one command), the option values, and the --help command a
    refusal names."""

    def __init__(self, command: Command, values: dict[str, Any], usage: str) -> None:
        self.group = command.group
        self.command = command.name
        self.label = command.label
        self.values = values
        self.usage = usage

    def require(self, *names: str) -> None:
        """Refuse the options in names that were not given, for a requirement
        that holds only on some runs of the command."""
        absent = [name for name in names if not given(self.values.get(name))]
        if absent:
            raise missing(absent, self.usage)

    def require_one_of(self, *names: str) -> None:
        """Refuse unless at least one of the options in names was given."""
        if not any(given(self.values.get(name)) for name in names):
            raise missing(names, self.usage, either=True)


def usage(group: str) -> str:
    """The --help command a refusal in group names."""
    return line(group, help=True)


def run(
    group: str,
    argv: Sequence[str],
    help_lines: Iterable[str],
    help_next: str,
    handle: Callable[[Context], int],
) -> int:
    """Run argv in group: its help, or the command it names with its options
    parsed and checked. handle(context) runs the command and returns its exit
    code. In a group that is one command, argv is that command's options."""
    named = usage(group)
    single = SINGLE.get(group)
    if single is not None:
        command, rest = single, argv
    else:
        if not argv or argv[0] in ("-h", "--help", "help"):
            return helps.group(help_lines, help_next)
        commands = COMMANDS[group]
        if argv[0] not in commands:
            unknown_command("%s %s" % (group, argv[0]), named)
        command, rest = commands[argv[0]], argv[1:]
    values = parse(rest, command, named)
    if values["help"]:
        return helps.group(help_lines, help_next)
    return handle(Context(command, values, named))
