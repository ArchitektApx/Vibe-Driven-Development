"""Setup's report: what one run printed, the changes it planned or made, the
questions for the user, the writes that did not land and the git-too-old
flag. Every check fills it; the group's finish reads it."""

from __future__ import annotations

from typing import NoReturn

from .. import textfile
from ..out import Output, refused


class Change:
    """A change Setup plans or makes. key is what it touches (".gitignore",
    "shared", "hooks.json"); text is its line after the verb, the same for a
    dry run and a write."""

    def __init__(self, key: str, text: str) -> None:
        self.key = key
        self.text = text


class Report:
    def __init__(self, write: bool) -> None:
        self.write = write
        self.out = Output()
        self.changes: list[Change] = []
        self.questions: list[str] = []       # what the model asks the user before --write
        self.failed: list[str] = []          # the keys of changes whose write did not land
        self.git_too_old: str | None = None  # the version found, when git is older than VDD needs
        self.user_answer_needed = False      # whether writing-for-agents' answer has to come from the user

    def change(self, key: str, text: str) -> None:
        """Record a change and print its line: "Planned change" on a dry run,
        "Changed" on a write."""
        self.changes.append(Change(key, text))
        self.out.line("%s: %s" % ("Changed" if self.write else "Planned change", text))

    def not_changed(self, key: str, what: str, error: Exception) -> None:
        """Record a write that did not land, and print its line."""
        self.failed.append(key)
        self.out.line("Not changed: %s (%s)." % (what, textfile.reason(error)))

    def read(self, path: str, what: str) -> str | None:
        """The file's text, or None when it does not exist. A file that
        exists and cannot be read stops the run, keeping every line printed
        so far; what names it in the refusal."""
        try:
            return textfile.read(path)
        except OSError as error:
            self.refuse_read(what, error)

    def refuse_read(self, what: str, error: OSError) -> NoReturn:
        """Stop the run on a file Setup cannot read, keeping what it printed."""
        raise refused(
            self.out.lines + ["Could not read %s: %s" % (what, textfile.reason(error))],
            "Otherwise tell the user Setup could not read %s, and stop." % what,
        )
