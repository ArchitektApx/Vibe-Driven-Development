"""Reading the Working files the tool frames: PLAN-REVIEW.md, CODEREVIEW.md
and FIXES.md.

Only the lines the tool framed are read: the title, the "##" and "###"
headings, and the label lines under them. Prose is never parsed. A line inside
an HTML comment or a fenced code block is never a heading or a label, so a
finding that quotes Markdown cannot break the frame.
"""

import re

FINDING = re.compile(r"^### ([0-9]+)\. (\S+) \(([^)]*)\): (.+?)\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
GUIDE_START = "<!-- VDD:"


class Line:
    """One line of a file: its number from 1, its text, and whether it is
    frame (outside every comment and fence)."""

    def __init__(self, number, text, frame):
        self.number = number
        self.text = text
        self.frame = frame


def split(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def classify(texts):
    """Every line as a Line, a comment's or a fence's lines marked as not
    frame."""
    out = []
    in_comment = False
    in_fence = False
    for number, text in enumerate(texts, 1):
        frame = not in_comment and not in_fence
        stripped = text.strip()
        if in_fence:
            if FENCE.match(text):
                in_fence = False
        elif in_comment:
            if "-->" in text:
                in_comment = False
        elif stripped.startswith("<!--"):
            frame = False
            if "-->" not in stripped[4:]:
                in_comment = True
        elif FENCE.match(text):
            frame = False
            in_fence = True
        out.append(Line(number, text, frame))
    return out


class Section:
    def __init__(self, name, line):
        self.name = name
        self.line = line
        self.body = []


class Block:
    """A "###" heading and the lines under it, up to the next heading."""

    def __init__(self, heading, section):
        self.heading = heading
        self.section = section
        self.body = []
        match = FINDING.match(heading.text)
        self.match = match
        if match:
            self.number = int(match.group(1))
            self.severity = match.group(2)
            self.state = match.group(3)
            self.reference = match.group(4)
        else:
            self.number = None

    def text_lines(self):
        """The heading and its body as text, trailing blank lines dropped."""
        lines = [self.heading.text] + [line.text for line in self.body]
        while lines and not lines[-1].strip():
            lines.pop()
        return lines

    def labels(self, names):
        """(label, joined text, Line) for each frame line under the heading
        that starts with "<label>:", the text running on over the following
        non-blank frame lines that start no other label."""
        out = []
        current = None
        for line in self.body:
            label = label_of(line, names)
            if label:
                current = [label, line.text[len(label) + 1:].strip(), line]
                out.append(current)
            elif current is not None and line.frame and line.text.strip():
                current[1] = (current[1] + " " + line.text.strip()).strip()
            else:
                current = None
        return [tuple(item) for item in out]

    def problem(self, names):
        """The body without its label spans, blank lines at either end
        dropped: what the finding said was wrong."""
        lines = []
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


def label_of(line, names):
    if not line.frame:
        return None
    for name in names:
        if line.text.startswith(name + ":"):
            return name
    return None


class Parsed:
    """A framed file: its title line, its "##" sections in order and the
    "###" blocks of each."""

    def __init__(self, text):
        self.texts = split(text)
        self.lines = classify(self.texts)
        self.title = None
        self.preamble = []
        self.sections = []
        self.blocks = []
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

    def section(self, name):
        for section in self.sections:
            if section.name == name:
                return section
        return None

    def blocks_in(self, name):
        return [block for block in self.blocks if block.section is not None and block.section.name == name]


def without_guides(texts):
    """The lines with every tool guidance comment (one starting "<!-- VDD:")
    removed."""
    out = []
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


def squeeze(texts):
    """No two blank lines in a row, none at the end."""
    out = []
    for text in texts:
        if not text.strip() and out and not out[-1].strip():
            continue
        out.append(text.rstrip() if not text.strip() else text)
    while out and not out[-1].strip():
        out.pop()
    return out


def join_numbers(numbers):
    """1 -> "1"; 1, 2 -> "1 and 2"; 1, 2, 3 -> "1, 2 and 3"."""
    words = [str(n) for n in numbers]
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]
