"""A command's options from its argv: --name value, --name=value, and
--flag, checked against the command's spec."""

from __future__ import annotations

import re
from typing import Any, Container, Mapping, Sequence

from ..out import Failure
from .refusals import missing, not_a_choice, unexpected_argument, unknown_option
from .specs import FLAG, LIST, Command, Option

# A quote and an option name inside a value: what Windows PowerShell 5.1
# makes of a value ending in a backslash followed by more options.
JOINED = re.compile(r'" --([A-Za-z][A-Za-z0-9-]*)')


def parse(argv: Sequence[str], command: Command, usage: str) -> dict[str, Any]:
    """The options in argv as a dict, every option of command present (None
    or False when not given, [] for a LIST). A VALUE given twice is refused.
    usage is the --help command to name when argv is wrong. --help and -h set
    "help". A value outside its option's choices is refused, with --help
    too; without --help a required option not given is refused."""
    spec = command.options
    values: dict[str, Any] = {
        name: (False if option.kind == FLAG else [] if option.kind == LIST else None)
        for name, option in spec.items()
    }
    values["help"] = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            values["help"] = True
            i += 1
            continue
        if not arg.startswith("--"):
            raise unexpected_argument(arg, usage, "slug" in spec and lone(argv, spec))
        name, eq, value = arg[2:].partition("=")
        option = spec.get(name)
        if option is None:
            raise unknown_option(name, spec, usage)
        if option.kind == FLAG:
            if eq:
                raise Failure("--%s takes no value." % name, "Run %s for this command's usage." % usage)
            values[name] = True
        else:
            if not eq:
                i += 1
                if i >= len(argv):
                    raise Failure(
                        "--%s needs a value." % name,
                        "Run %s for this command's usage." % usage,
                    )
                value = argv[i]
                if value.startswith("--"):
                    # A shell that drops an empty argument (Windows PowerShell
                    # 5.1 does) shifts the next option into this value.
                    raise Failure(
                        "--%s has no value: the next argument is %s." % (name, value),
                        "Run the command again with a value after --%s, or --%s=<value> for a value that "
                        "starts with --." % (name, name),
                    )
            joined = mangled(value, spec)
            if joined is not None:
                raise Failure(
                    "--%s's value holds '\" --%s': %s. A shell joined the options after it into this value "
                    "(Windows PowerShell 5.1 does when a value ends in a backslash). Nothing was done."
                    % (name, joined, value),
                    "Run the command again with no value ending in a backslash: drop it or add a space after "
                    "it. If the value really holds that text, reword it.",
                )
            if option.kind == LIST:
                values[name].append(value)
            elif values[name] is not None:
                raise Failure(
                    "--%s is given twice (%s, then %s); this command takes it once. Nothing was done."
                    % (name, values[name], value),
                    "Run the command again with --%s once." % name,
                )
            else:
                values[name] = value
        i += 1
    check(values, command, usage, required=not values["help"])
    return values


def given(value: Any) -> bool:
    """Whether an option's parsed value was given: a VALUE that is not None,
    a LIST that is not empty, a FLAG that is set."""
    return value is not None and value != [] and value is not False


def check(values: dict[str, Any], command: Command, usage: str, required: bool = True) -> None:
    """Refuse the required options not given, unless required is False,
    then a value outside its option's choices."""
    absent = [name for name, option in command.options.items() if option.required and not given(values[name])]
    if absent and required:
        raise missing(absent, usage)
    for name, option in command.options.items():
        if not option.choices or values[name] is None:
            continue
        for value in values[name] if option.kind == LIST else [values[name]]:
            if value not in option.choices:
                raise not_a_choice(name, value, option.choices, usage)


def lone(argv: Sequence[str], spec: Mapping[str, Option]) -> bool:
    """Whether argv holds exactly one bare argument and no --slug. The word
    after a value option is its value, not a bare argument."""
    bare = 0
    i = 0
    while i < len(argv):
        arg = argv[i]
        name, eq, _ = arg[2:].partition("=")
        if not arg.startswith("-"):
            bare += 1
        elif name == "slug":
            return False
        elif arg.startswith("--") and not eq and name in spec and spec[name].kind != FLAG:
            i += 1
        i += 1
    return bare == 1


def mangled(value: str, spec: Container[str]) -> str | None:
    """The name of the first option of spec that value holds as `" --<name>`,
    or None. A word that is no option of the command is text."""
    for match in JOINED.finditer(value):
        if match.group(1) in spec:
            return match.group(1)
    return None
