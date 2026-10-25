"""Setup's report: what the checks found, as the effects of one plan, and the
changes Setup plans, the questions for the user, the writes that did not
land and the git-too-old flag. Every check fills it; the group's finish
reads it, and the runner prints the plan as the dry run or applies it."""

from __future__ import annotations

from typing import Callable, NoReturn, Sequence

from .. import runner, textfile
from ..out import TELL, one_line, refused


class Recorder:
    """What a check prints, kept in order as effects of the plan: a check's
    line prints on the dry run only, a Tell line on the dry run and the
    write alike."""

    def __init__(self, report: Report) -> None:
        self.report = report

    def line(self, text: str = "") -> None:
        self.report.effects.append(runner.Effect(dry=[one_line(text)]))

    def tell(self, text: str) -> None:
        told = TELL % one_line(text)
        self.report.effects.append(runner.Effect(dry=[told], done=[told]))

    @property
    def lines(self) -> list[str]:
        """Every line the dry run printed so far, the header first."""
        return [self.report.header] + [line for effect in self.report.effects for line in effect.dry]


class Change(runner.Effect):
    """A change Setup plans or makes. key is what it touches (".gitignore",
    "shared", "hooks.json"); texts, its lines after the verb, "Planned
    change" on the dry run and "Changed" once made; extra, the lines the dry
    run shows after them. write makes it and returns the lines of its check.
    A write that does not land prints "Not changed" and is recorded as
    failed."""

    def __init__(self, report: Report, key: str, what: str, texts: Sequence[str],
                 write: Callable[[], list[str]], extra: Sequence[str] = ()) -> None:
        runner.Effect.__init__(self, dry=["Planned change: %s" % one_line(text) for text in texts] + list(extra),
                               done=["Changed: %s" % one_line(text) for text in texts])
        self.report = report
        self.key = key
        self.what = what
        self.write = write

    def apply(self) -> list[str]:
        try:
            checked = self.write()
        except (OSError, ValueError) as error:
            self.report.failed.append(self.key)
            return ["Not changed: %s (%s)." % (self.what, textfile.reason(error))]
        return self.done + checked


class Report:
    def __init__(self, header: str) -> None:
        self.header = header
        self.effects: list[runner.Effect] = []
        self.out = Recorder(self)
        self.changes: list[Change] = []
        self.questions: list[str] = []       # what the model asks the user before --write
        self.failed: list[str] = []          # the keys of changes whose write did not land
        self.git_too_old: str | None = None  # the version found, when git is older than VDD needs
        self.user_answer_needed = False      # whether writing-for-agents' answer has to come from the user

    def change(self, key: str, what: str, texts: Sequence[str], write: Callable[[], list[str]],
               extra: Sequence[str] = ()) -> None:
        """Plan a change; the runner prints it or makes it."""
        change = Change(self, key, what, texts, write, extra)
        self.changes.append(change)
        self.effects.append(change)

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
