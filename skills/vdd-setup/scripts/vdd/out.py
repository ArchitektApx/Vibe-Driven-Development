"""The output contract.

Plain text, one fact per line, written to standard output as UTF-8 bytes with
LF line ends and every CR removed, whatever the console's code page. The last
line is "Next: <command or action>". A line the user must see is
'Tell the user verbatim: "<text>"', and the Next: line after one opens with
the step that relays it, or, when that step starts a wait, ends with it. The exit code is zero or not; the reason
is always in the text.
"""

from __future__ import annotations

import errno
import sys
from typing import Iterable

TELL = 'Tell the user verbatim: "%s"'
TELL_START = TELL.split('"')[0]
RELAY = "Relay every Tell the user verbatim line above unchanged; only after doing that, "
# The relay of a Tell that hands the user a step only they can take, on an
# output whose step starts a wait and ends the turn: a relay asked for before
# the wait is dropped by a model that writes its text at the end of a turn.
# A step that holds RELAY_HELD words its own relay of the Tell lines.
RELAY_HELD = "holds every Tell the user verbatim line above, unchanged"
RELAY_LAST = ("Start the wait before you write anything to the user; the reply that ends your turn comes after "
              "it and %s." % RELAY_HELD)
ESCALATE = (
    "If a sandbox refused it and your tools offer a way to rerun the command outside the sandbox, "
    "rerun it once that way."
)


def one_line(text: str) -> str:
    """Text as one printable line: CR and LF become spaces, other control
    characters go."""
    text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return "".join(c for c in text if c == "\t" or ord(c) >= 32 and ord(c) != 127)


def lower_first(text: str) -> str:
    """text with its first letter lowercased, unless its first word is an
    acronym such as PR."""
    if len(text) > 1 and text[0].isupper() and not text[1].isupper():
        return text[0].lower() + text[1:]
    return text


def and_list(items: Iterable[str]) -> str:
    """"1", "1 and 2", "1, 2 and 3" for the strings in items."""
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return "%s and %s" % (", ".join(items[:-1]), items[-1])


def or_list(items: Iterable[str]) -> str:
    """"1", "1 or 2", "1, 2 or 3" for the strings in items."""
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return "%s or %s" % (", ".join(items[:-1]), items[-1])


# Lines a command prints first, whatever it prints after: what the loop
# lookup left out. One command runs per process.
NOTICES: list[str] = []


def notice(text: str) -> None:
    NOTICES.append(one_line(text))


class Output:
    """Collects lines and writes them once, ending in the Next: line. A line
    that records something done, a push or a closed loop, also prints before
    the lines of a Failure raised after it."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.done_lines: list[str] = []

    def line(self, text: str = "") -> None:
        self.lines.append(one_line(text))

    def tell(self, text: str) -> None:
        self.lines.append(TELL % one_line(text))

    def done(self, text: str) -> None:
        """A line that records something done."""
        self.line(text)
        self.done_lines.append(self.lines[-1])

    def done_tell(self, text: str) -> None:
        """A Tell line that records something done."""
        self.tell(text)
        self.done_lines.append(self.lines[-1])

    def failing(self, failure: Failure) -> Failure:
        """failure, with the lines already done printed before its own."""
        failure.lines = self.done_lines + failure.lines
        self.done_lines = []
        return failure

    def finish(self, next_step: str, code: int = 0) -> int:
        """Print the lines and the Next: line, which opens with RELAY when
        a Tell line printed, unless the step words its own relay, as one
        that holds RELAY_HELD does."""
        told = any(line.startswith(TELL_START) for line in NOTICES + self.lines)
        if told and RELAY_HELD not in next_step:
            next_step = RELAY + lower_first(next_step)
        self.lines.append("Next: " + one_line(next_step))
        write(NOTICES + self.lines)
        del NOTICES[:]
        return code


class Failure(Exception):
    """A refused command: its lines, its Next: step, and a non-zero exit."""

    def __init__(self, lines: str | Iterable[str], next_step: str) -> None:
        Exception.__init__(self, next_step)
        self.lines = [lines] if isinstance(lines, str) else list(lines)
        self.next_step = next_step

    def emit(self) -> int:
        out = Output()
        for text in self.lines:
            out.line(text)
        return out.finish(self.next_step, 1)


def relay_last(wait_step: str) -> str:
    """wait_step, a step that starts a wait and ends the turn, with the relay
    of the Tell lines after it, in the reply that ends the turn."""
    return "%s %s" % (wait_step, RELAY_LAST)


def escalate(otherwise: str) -> str:
    """The Next: step after a refused command: the one escalated retry, then
    what to do otherwise."""
    return ESCALATE + " " + otherwise


def refused(lines: str | Iterable[str], otherwise: str) -> Failure:
    """A Failure for a file operation the system refused."""
    return Failure(lines, escalate(otherwise))


def write(lines: Iterable[str]) -> None:
    """Print lines to standard output. A reader that closed the pipe raises
    BrokenPipeError, on every platform: Windows reports the write as EINVAL."""
    text = "".join(one_line(line) + "\n" for line in lines)
    data = text.encode("utf-8", "replace")
    stream = getattr(sys.stdout, "buffer", None)
    try:
        if stream is None:
            sys.stdout.write(data.decode("utf-8"))
            sys.stdout.flush()
            return
        stream.write(data)
        stream.flush()
    except BrokenPipeError:
        raise
    except OSError as error:
        if error.errno in (errno.EPIPE, errno.EINVAL):
            raise BrokenPipeError(errno.EPIPE, "the output pipe is closed") from error
        raise
