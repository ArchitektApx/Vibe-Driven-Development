"""Command-line options: --name value, --name=value, and --flag."""

from .out import Failure
from . import harness

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
            values[name] = value
        i += 1
    return values


def require(values, names, usage):
    missing = [name for name in names if values.get(name) is None]
    if missing:
        raise Failure(
            "Missing: %s" % ", ".join("--" + name for name in missing),
            "Run %s for this command's usage." % usage,
        )


def harness_of(values, usage):
    """The Harness the --harness option names."""
    name = values.get("harness")
    if name is None:
        require(values, ["harness"], usage)
    found = harness.get(name)
    if found is None:
        raise Failure(
            "Unknown Harness: %s. --harness takes one of: %s." % (name, ", ".join(harness.NAMES)),
            "Run again with --harness set to one of: %s." % ", ".join(harness.NAMES),
        )
    return found
