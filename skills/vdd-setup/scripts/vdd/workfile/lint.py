"""The lint collector: the problems one lint of a Working file found,
printed in line order."""

from __future__ import annotations

from ..markdown import Line, unclosed_text
from ..out import Failure
from .frame import Parsed

class Lint:
    """The problems of one lint, each prefixed with the file and line, printed
    in line order: a problem with no line first, a block to put back after
    every line's, and a problem of the whole round last."""

    BLOCK = 10 ** 9

    def __init__(self, name: str) -> None:
        self.name = name
        self.problems: list[tuple[int, list[str]]] = []

    def at(self, line: Line | int | None, text: str) -> None:
        number = line.number if isinstance(line, Line) else line
        if not number:
            self.problems.append((0, ["%s: %s" % (self.name, text)]))
        else:
            self.problems.append((number, ["%s line %d: %s" % (self.name, number, text)]))

    def block(self, text: str, block_lines: list[str]) -> None:
        """A refusal followed by a block to put back, one output line per
        line of the block."""
        self.problems.append((self.BLOCK, ["%s: %s" % (self.name, text)] + block_lines))

    def last(self, text: str) -> None:
        """A problem of the whole round, not of a line of the file."""
        self.problems.append((self.BLOCK + 1, [text]))

    def title(self, parsed: Parsed, title: str) -> None:
        """The title the tool wrote, and a comment or fence left open."""
        if parsed.title is None:
            self.at(None, "the title \"%s\" is missing. Put it back as the first line." % title)
        elif parsed.title.text.strip() != title:
            self.at(parsed.title, "the title is \"%s\", as the tool wrote it." % title)
        if parsed.unclosed is not None:
            self.at(parsed.unclosed, unclosed_text(parsed.unclosed))

    def lines(self) -> list[str]:
        found: list[str] = []
        for _, texts in sorted(self.problems, key=lambda problem: problem[0]):
            found += texts
        return found

    def refuse(self, next_step: str) -> None:
        """Raise the Failure for a file that does not pass: its problems, then
        "Nothing written."."""
        if self.problems:
            raise Failure(self.lines() + ["Nothing written."], next_step)
