"""Reading the Working files the tool frames: PLAN-REVIEW.md, CODEREVIEW.md
and FIXES.md.

Only the lines the tool framed are read: the title, the "##" and "###"
headings, and the label lines under them. Prose is never parsed. A line inside
an HTML comment or a fenced code block is never a heading or a label, so a
finding that quotes Markdown cannot break the frame.
"""

from __future__ import annotations

import re
from typing import Iterable

from ..markdown import Line, split, walk

FINDING = re.compile(r"^### ([0-9]+)\. (\S+) \(([^)]*)\): (.+?)\s*$")
GUIDE_START = "<!-- VDD:"


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
