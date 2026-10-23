"""The line builder: the exact text of a command the tool tells a Role to
run, the tool's path, the group, the command and its options in the order
given. It never refuses: a wrong option name here is a developer's slip, and
the tests' Next: check, which runs every printed command with --help, catches
it before a Role could meet it."""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

from .. import places

# An option's value as a caller gives it: a value's text, as it is printed (a
# value that needs quotes comes quoted, see quoted()); True for a flag, or
# for a value option a line names without its value; a sequence for an
# option given once per item; None or False to leave it out.
Value = Union[str, bool, None, Sequence[str]]


def quoted(value: str) -> str:
    """value in double quotes when it holds a space, so a shell reads it as
    one argument."""
    return '"%s"' % value if " " in value else value


def words(group: str, command: str, options: dict[str, Value]) -> List[str]:
    """The group, the command and every option given; no group for the
    tool's own --help. An option's keyword is its name with "-" written as
    "_", and a trailing "_" dropped (from_ for --from)."""
    out = [group] if group else []
    if command:
        out.append(command)
    for key, value in options.items():
        name = "--" + key.rstrip("_").replace("_", "-")
        if value is None or value is False:
            continue
        if value is True:
            out.append(name)
        elif isinstance(value, str):
            out += [name, value]
        else:
            for item in value:
                out += [name, item]
    return out


def line(group: str, command: str = "", entry: Optional[str] = None, **options: Value) -> str:
    """The command as a Role runs it, naming the copy of the tool at entry
    (the running one by default)."""
    return " ".join([places.command(entry)] + words(group, command, options))


def bare(group: str, command: str = "", **options: Value) -> str:
    """The command without the tool's path, as brainstorm's lines name the
    group's own commands: the Brainstormer's skill teaches that form."""
    return " ".join(words(group, command, options))
