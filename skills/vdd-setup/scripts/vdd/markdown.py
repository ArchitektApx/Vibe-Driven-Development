"""The shared Markdown line scanner: a file's lines, which of them sit
inside an HTML comment or a fenced code block, and the refusal for one left
open. The Working files, the idea files, the PR conventions and the Recap
read Markdown through it, so every reader agrees on where a fence or a
comment starts and ends."""

from __future__ import annotations

import re
from typing import Iterable, overload

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


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


def walk(texts: Iterable[str], comments: bool = True) -> tuple[list[Line], Line | None]:
    """(the Lines as classify gives them, the Line that opens a comment or
    fence still open at the end of the file, or None). With comments False,
    HTML comments are read as text and only fences are walked."""
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
        elif comments and stripped.startswith("<!--"):
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


def fenced(texts: Iterable[str]) -> list[bool]:
    """For each line, whether it is a fence line or sits inside a fenced code
    block; HTML comments are not skipped."""
    return [not line.frame for line in walk(texts, comments=False)[0]]


def outside_fences(texts: Iterable[str]) -> list[str]:
    """The lines that sit outside a fenced code block and are no fence line,
    by the same fence rule: HTML comments are not skipped."""
    texts = list(texts)
    return [text for text, inside in zip(texts, fenced(texts)) if not inside]


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
