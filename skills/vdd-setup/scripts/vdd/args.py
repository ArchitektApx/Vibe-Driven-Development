"""Command-line options: --name value, --name=value, and --flag."""

import difflib
import re

from .out import Failure
from . import harness, places

VALUE = "value"
FLAG = "flag"
# A quote and an option name inside a value: what Windows PowerShell 5.1
# makes of a value ending in a backslash followed by more options.
JOINED = re.compile(r'" --([A-Za-z][A-Za-z0-9-]*)')


def parse(argv, spec, usage):
    """The options in argv as a dict, every option in spec present (None or
    False when not given). spec maps an option name to VALUE or FLAG. usage is
    the --help command to name when argv is wrong. --help and -h set "help"."""
    values = {name: (False if kind == FLAG else None) for name, kind in spec.items()}
    values["help"] = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            values["help"] = True
            i += 1
            continue
        if not arg.startswith("--"):
            raise Failure(
                "Unexpected argument: %s" % arg,
                "Run %s for this command's usage." % usage,
            )
        name, eq, value = arg[2:].partition("=")
        kind = spec.get(name)
        if kind is None:
            raise unknown_option(name, spec, usage)
        if kind == FLAG:
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
            values[name] = value
        i += 1
    return values


def mangled(value, spec):
    """The name of the first option of spec that value holds as `" --<name>`,
    or None. A word that is no option of the command is text."""
    for match in JOINED.finditer(value):
        if match.group(1) in spec:
            return match.group(1)
    return None


def unknown_option(name, spec, usage):
    """The Failure for an option the command does not take: the options it
    takes, and the closest one when one is close."""
    takes = sorted(spec)
    close = difflib.get_close_matches(name, takes, n=1, cutoff=0.6)
    lines = ["Unknown option: --%s" % name, "This command takes: %s" % ", ".join("--" + n for n in takes)]
    if close:
        lines.append("Closest: --%s." % close[0])
        return Failure(
            lines,
            "Run the command again with --%s, or with the option your skill writes from the list above." % close[0],
        )
    return Failure(
        lines,
        "Run the command again with the options above, as your skill writes them (%s shows the usage). If your "
        "skill writes --%s exactly, this copy of the VDD tool is older than the skill: tell the user to rerun "
        "Setup." % (usage, name),
    )


def unknown_command(typed, usage):
    """Raise the Failure for a word in a command's place that names no
    command. typed is the command as far as it was read ("loop --slug"); usage
    is the --help command that lists the commands there. An option in that
    place is out of order, not a command from a newer skill, so it gets the
    order and not "rerun Setup"."""
    word = typed.split(" ")[-1]
    if word.startswith("-"):
        raise Failure(
            "Option before its command: %s" % word,
            "Put every option after the group and its command, as in %s loop show --role <Role> --slug <slug>, "
            "and run it again. Run %s for the commands." % (places.command(), usage),
        )
    raise Failure(
        [
            "Unknown command: %s" % typed,
            "This copy of the VDD tool may be older than the skill that called it: rerun Setup.",
        ],
        "Tell the user this copy of the VDD tool is out of date and to rerun Setup, then retry.",
    )


def choice(value, allowed, message, next_step):
    """Raise Failure(message, next_step) unless value is one of allowed. The
    site words both: what the option takes, and where to look."""
    if value not in allowed:
        raise Failure(message, next_step)


def require(values, names, usage):
    missing = [name for name in names if values.get(name) is None]
    if missing:
        raise Failure(
            "Missing: %s" % ", ".join("--" + name for name in missing),
            "Run %s for this command's usage." % usage,
        )


def harness_of(values, usage):
    """The Harness the --harness option names, as the slug or as the Loop
    file's Harness: line spells it ("Claude Code", "Copilot CLI")."""
    name = values.get("harness")
    if name is None:
        require(values, ["harness"], usage)
    found = harness.get("-".join(name.lower().split()))
    if found is None:
        raise Failure(
            "Unknown Harness: %s. --harness takes one of: %s." % (name, ", ".join(harness.NAMES)),
            "Run again with --harness set to one of: %s." % ", ".join(harness.NAMES),
        )
    return found
