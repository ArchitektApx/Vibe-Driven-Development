"""The refusals of a command line: an unknown option or command, a missing
option, a value outside an option's choices, and a slug that does not match
its pattern."""

from __future__ import annotations

import difflib
import re
from typing import Iterable, NoReturn, Sequence

from ..out import Failure, or_list
from .builder import line


def unknown_option(name: str, options: Iterable[str], usage: str) -> Failure:
    """The Failure for an option the command does not take: the options it
    takes, and the closest one when one is close."""
    takes = sorted(options)
    close = difflib.get_close_matches(name, takes, n=1, cutoff=0.6)
    lines = ["Unknown option: --%s" % name,
             "This command takes: %s." % ", ".join("--" + n for n in takes) if takes
             else "This command takes no options."]
    if close:
        lines.append("Closest: --%s." % close[0])
        return Failure(
            lines,
            "Run the command again with --%s, or with the option your skill writes from the list above." % close[0],
        )
    return Failure(
        lines,
        "Run the command again %s, as your skill writes it (%s shows the usage). If your skill writes --%s exactly, "
        "this copy of the VDD tool is older than the skill: tell the user to rerun Setup."
        % ("with the options above" if takes else "without --%s" % name, usage, name),
    )


def unknown_command(typed: str, usage: str) -> NoReturn:
    """Raise the Failure for a word in a command's place that names no
    command. typed is the command as far as it was read ("loop --slug"); usage
    is the --help command that lists the commands there. An option in that
    place is out of order, not a command from a newer skill, so it gets the
    order and not "rerun Setup"."""
    word = typed.split(" ")[-1]
    if word.startswith("-"):
        raise Failure(
            "Option before its command: %s" % word,
            "Put every option after the group and its command, as in %s, and run it again. Run %s for the "
            "commands." % (line("loop", "show", role="<Role>", slug="<slug>"), usage),
        )
    raise Failure(
        [
            "Unknown command: %s" % typed,
            "This copy of the VDD tool may be older than the skill that called it: rerun Setup.",
        ],
        "Tell the user this copy of the VDD tool is out of date and to rerun Setup, then retry.",
    )


def missing(names: Sequence[str], usage: str, either: bool = False) -> Failure:
    """The Failure for the options in names, which were not given: each one
    needed, or with either one of them."""
    options = ["--" + name for name in names]
    return Failure(
        "Missing: %s" % (or_list(options) if either else ", ".join(options)),
        "Run %s for this command's usage." % usage,
    )


def shown(text: str) -> str:
    """A value as a refusal names it: quoted when it holds a space or is
    empty."""
    return '"%s"' % text if not text or " " in text else text


def not_a_choice(name: str, given: str, choices: Sequence[str], usage: str = "", step: str = "") -> Failure:
    """The Failure for a value of --name outside its choices. Its Next: is
    step when the caller gives one, else the command's usage."""
    return Failure(
        "--%s takes %s, not %s." % (name, or_list(shown(choice) for choice in choices), shown(given)),
        step or "Run %s for this command's usage." % usage,
    )


def check_slug(slug: str | None, pattern: str, named: str, short: str, joiners: str) -> None:
    """Raise unless slug matches the regular expression pattern. named is the
    slug as the first line calls it ("a Feature slug"), short as the rest do
    ("a slug"), joiners what may join its words ("hyphens")."""
    if not slug or re.match("^" + pattern + "$", slug) is None:
        raise Failure(
            "Not %s: %s. %s matches %s: lowercase letters and digits, in words joined by single %s."
            % (named, slug, short[0].upper() + short[1:], pattern, joiners),
            "Ask the user for %s that matches %s, then run the command again with it." % (short, pattern),
        )
