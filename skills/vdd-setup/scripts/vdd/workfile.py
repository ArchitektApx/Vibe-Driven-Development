"""Reading the Working files the tool frames: PLAN-REVIEW.md, CODEREVIEW.md
and FIXES.md.

Only the lines the tool framed are read: the title, the "##" and "###"
headings, and the label lines under them. Prose is never parsed. A line inside
an HTML comment or a fenced code block is never a heading or a label, so a
finding that quotes Markdown cannot break the frame.
"""

from __future__ import annotations

import os
import re
from typing import Iterable, overload

from . import textfile
from .out import Failure, and_list

FINDING = re.compile(r"^### ([0-9]+)\. (\S+) \(([^)]*)\): (.+?)\s*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
GUIDE_START = "<!-- VDD:"


class Line:
    """One line of a file: its number from 1, its text, and whether it is
    frame (outside every comment and fence)."""

    def __init__(self, number: int, text: str, frame: bool) -> None:
        self.number = number
        self.text = text
        self.frame = frame


def split(text: str) -> list[str]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def classify(texts: Iterable[str]) -> list[Line]:
    """Every line as a Line, a comment's or a fence's lines marked as not
    frame."""
    return walk(texts)[0]


def walk(texts: Iterable[str]) -> tuple[list[Line], Line | None]:
    """(the Lines as classify gives them, the Line that opens a comment or
    fence still open at the end of the file, or None)."""
    out: list[Line] = []
    in_comment = False
    # The run the open fence was opened with, None outside a fence.
    fence = None
    opener = None
    for number, text in enumerate(texts, 1):
        frame = not in_comment and fence is None
        stripped = text.strip()
        line = Line(number, text, frame)
        if fence is not None:
            if closes(text, fence):
                fence = None
        elif in_comment:
            if "-->" in text:
                in_comment = False
        elif stripped.startswith("<!--"):
            line.frame = False
            if "-->" not in stripped[4:]:
                in_comment = True
                opener = line
        elif fence_run(text):
            line.frame = False
            fence = fence_run(text)
            opener = line
        out.append(line)
    return out, (opener if in_comment or fence is not None else None)


def fence_run(text: str) -> str | None:
    """The backtick or tilde run a line opens a fence with, or None: at most
    three spaces of indent, three or more of one character, and for
    backticks no backtick after the run."""
    match = FENCE.match(text)
    if match is None or (match.group(1)[0] == "`" and "`" in match.group(2)):
        return None
    return match.group(1)


def closes(text: str, run: str) -> bool:
    """Whether the line closes a fence opened with run: at most three spaces
    of indent, a run of the same character at least as long, and nothing
    after it but whitespace."""
    match = FENCE.match(text)
    return (match is not None and match.group(1)[0] == run[0] and len(match.group(1)) >= len(run)
            and not match.group(2).strip())


def outside_fences(texts: Iterable[str]) -> list[str]:
    """The lines that sit outside a fenced code block and are no fence line,
    by the same fence rule: HTML comments are not skipped."""
    out: list[str] = []
    run = None
    for text in texts:
        if run is not None:
            if closes(text, run):
                run = None
            continue
        run = fence_run(text)
        if run is None:
            out.append(text)
    return out


@overload
def unclosed_text(opener: Line) -> str: ...
@overload
def unclosed_text(opener: None) -> None: ...
def unclosed_text(opener: Line | None) -> str | None:
    """The refusal for a comment or fence left open, or None."""
    if opener is None:
        return None
    if opener.text.strip().startswith("<!--"):
        return ("the comment that opens here is never closed, so every line after it is read as part of it. "
                "Close it with \"-->\".")
    return ("the code fence that opens here is never closed, so every line after it is read as part of it. "
            "Close it with a line holding %s." % fence_run(opener.text))


class Section:
    def __init__(self, name: str, line: Line) -> None:
        self.name = name
        self.line = line
        self.body: list[Line] = []


class Block:
    """A "###" heading and the lines under it, up to the next heading."""

    def __init__(self, heading: Line, section: Section | None) -> None:
        self.heading = heading
        self.section = section
        self.body: list[Line] = []
        match = FINDING.match(heading.text)
        self.match = match
        self.number: int | None
        if match:
            self.number = int(match.group(1))
            self.severity = match.group(2)
            self.state = match.group(3)
            self.reference = match.group(4)
        else:
            self.number = None

    def text_lines(self) -> list[str]:
        """The heading and its body as text, trailing blank lines dropped."""
        lines = [self.heading.text] + [line.text for line in self.body]
        while lines and not lines[-1].strip():
            lines.pop()
        return lines

    def labels(self, names: Iterable[str]) -> list[tuple[str, str, Line]]:
        """(label, joined text, Line) for each frame line under the heading
        that starts with "<label>:", the text running on over the following
        non-blank frame lines that start no other label."""
        # Not merged with fixes.Entry.labels on purpose: in a review file a
        # blank line ends a label and starts the finding's own text; in
        # FIXES.md a label runs across paragraphs, so a multi-paragraph Why:
        # reaches the reviewer whole.
        out: list[tuple[str, str, Line]] = []
        # Whether the lines below run on the text of the last label in out.
        running = False
        for line in self.body:
            label = label_of(line, names)
            if label:
                out.append((label, line.text[len(label) + 1:].strip(), line))
                running = True
            elif running and line.frame and line.text.strip():
                name, text, start = out[-1]
                out[-1] = (name, (text + " " + line.text.strip()).strip(), start)
            else:
                running = False
        return out

    def problem(self, names: Iterable[str]) -> list[str]:
        """The body without its label spans, blank lines at either end
        dropped: what the finding said was wrong."""
        lines: list[str] = []
        inside = False
        for line in self.body:
            if label_of(line, names):
                inside = True
                continue
            if inside and line.frame and line.text.strip():
                continue
            inside = False
            lines.append(line.text)
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return lines


def label_of(line: Line, names: Iterable[str]) -> str | None:
    if not line.frame:
        return None
    for name in names:
        if line.text.startswith(name + ":"):
            return name
    return None


class Parsed:
    """A framed file: its title line, its "##" sections in order and the
    "###" blocks of each."""

    def __init__(self, text: str) -> None:
        self.texts = split(text)
        self.lines, self.unclosed = walk(self.texts)
        self.title: Line | None = None
        self.preamble: list[Line] = []
        self.sections: list[Section] = []
        self.blocks: list[Block] = []
        section = None
        block = None
        for line in self.lines:
            text = line.text
            if line.frame and self.title is None and text.startswith("# "):
                self.title = line
                continue
            if line.frame and text.startswith("## "):
                section = Section(text[3:].strip(), line)
                self.sections.append(section)
                block = None
                continue
            if line.frame and text.startswith("### "):
                block = Block(line, section)
                self.blocks.append(block)
                continue
            if block is not None:
                block.body.append(line)
            elif section is not None:
                section.body.append(line)
            else:
                self.preamble.append(line)

    def section(self, name: str) -> Section | None:
        for section in self.sections:
            if section.name == name:
                return section
        return None

    def blocks_in(self, name: str) -> list[Block]:
        return [block for block in self.blocks if block.section is not None and block.section.name == name]


def without_guides(texts: Iterable[str]) -> list[str]:
    """The lines with every tool guidance comment (one starting "<!-- VDD:")
    removed."""
    out: list[str] = []
    inside = False
    for text in texts:
        if inside:
            if "-->" in text:
                inside = False
            continue
        if text.strip().startswith(GUIDE_START):
            if "-->" not in text.strip()[len(GUIDE_START):]:
                inside = True
            continue
        out.append(text)
    return out


def squeeze(texts: Iterable[str]) -> list[str]:
    """No two blank lines in a row, none at the end."""
    out: list[str] = []
    for text in texts:
        if not text.strip() and out and not out[-1].strip():
            continue
        out.append(text.rstrip() if not text.strip() else text)
    while out and not out[-1].strip():
        out.pop()
    return out


def join_numbers(numbers: Iterable[int | str]) -> str:
    """1 -> "1"; 1, 2 -> "1 and 2"; 1, 2, 3 -> "1, 2 and 3"."""
    return and_list(str(n) for n in numbers)


# --- the Working files each hosted Role reads and writes ---

SPEC = "spec.md"
ISSUES = "issues/"


class RoleFiles:
    """One hosted Role's Working files, as names under the tracker
    directory: what it reads in round 1 and in a later round (the carried
    file exists from round 2), what it writes, the review file it reads
    findings from and the carried file behind it."""

    def __init__(
        self, first: tuple[str, ...], later: tuple[str, ...], write: tuple[str, ...], own: str, review: str,
        carried: str,
    ) -> None:
        self.first = first
        self.later = later
        self.write = write
        self.own = own
        self.review = review
        self.carried = carried

    def read(self, number: int) -> tuple[str, ...]:
        return self.first if number == 1 else self.later


WORKING_FILES = {
    "Plan-Reviewer": RoleFiles((SPEC, ISSUES), ("PLAN-REVIEW.md", SPEC, ISSUES), ("PLAN-REVIEW.md",),
                               "PLAN-REVIEW.md", "PLAN-REVIEW.md", "carried-plan.md"),
    "Coder": RoleFiles((SPEC, ISSUES), ("CODEREVIEW.md", SPEC, ISSUES),
                       ("FIXES.md", ISSUES + " (the ticked checkboxes)"), "FIXES.md", "CODEREVIEW.md",
                       "carried-code.md"),
    "Code-Reviewer": RoleFiles((SPEC, ISSUES, "FIXES.md"), ("CODEREVIEW.md", SPEC, ISSUES), ("CODEREVIEW.md",),
                               "CODEREVIEW.md", "CODEREVIEW.md", "carried-code.md"),
}


def own_files() -> list[str]:
    """Each hosted Role's own file, in the Workflow's order."""
    return [files.own for files in WORKING_FILES.values()]


# --- the open findings' text ---

def open_blocks(directory: str, files: RoleFiles, numbers: Iterable[int]) -> tuple[dict[int, Block], list[int]]:
    """(number -> Block, the numbers not found) of the given open findings:
    from the review file as the last check left it first, then from the
    carried file. One rule decides where an open finding's text lives; each
    caller words its own refusal for the missing."""
    wanted = list(numbers)
    found: dict[int, Block] = {}
    for name in (files.review, files.carried):
        text = textfile.read(os.path.join(directory, name))
        if text is None:
            continue
        for block in Parsed(text).blocks:
            if block.match and block.number in wanted and block.number not in found:
                found[block.number] = block
    return found, [n for n in wanted if n not in found]


# --- the lint collector ---

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
