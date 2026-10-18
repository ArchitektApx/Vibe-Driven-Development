"""Command-line options: --name value, --name=value, and --flag."""

from .out import Failure
from . import harness, places

VALUE = "value"
FLAG = "flag"


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
            raise Failure(
                [
                    "Unknown option: --%s" % name,
                    "If your skill names this option, this copy of the VDD tool is "
                    "older than the skill: rerun Setup.",
                ],
                "Run %s for this command's usage, or rerun Setup." % usage,
            )
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
            values[name] = value
        i += 1
    return values


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
