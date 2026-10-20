"""The output contract.

Plain text, one fact per line, written to standard output as UTF-8 bytes with
LF line ends and every CR removed, whatever the console's code page. The last
line is "Next: <command or action>". A line the user must see is
'Tell the user verbatim: "<text>"'. The exit code is zero or not; the reason
is always in the text.
"""

import sys

TELL = 'Tell the user verbatim: "%s"'
ESCALATE = (
    "If a sandbox refused it and your tools offer a way to rerun the command outside the sandbox, "
    "rerun it once that way."
)


def one_line(text):
    """Text as one printable line: CR and LF become spaces, other control
    characters go."""
    text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return "".join(c for c in text if c == "\t" or ord(c) >= 32 and ord(c) != 127)


def and_list(items):
    """"1", "1 and 2", "1, 2 and 3" for the strings in items."""
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return "%s and %s" % (", ".join(items[:-1]), items[-1])


class Output:
    """Collects lines and writes them once, ending in the Next: line."""

    def __init__(self):
        self.lines = []

    def line(self, text=""):
        self.lines.append(one_line(text))

    def tell(self, text):
        self.lines.append(TELL % one_line(text))

    def finish(self, next_step, code=0):
        self.lines.append("Next: " + one_line(next_step))
        write(self.lines)
        return code


class Failure(Exception):
    """A refused command: its lines, its Next: step, and a non-zero exit."""

    def __init__(self, lines, next_step):
        Exception.__init__(self, next_step)
        self.lines = [lines] if isinstance(lines, str) else list(lines)
        self.next_step = next_step

    def emit(self):
        out = Output()
        for text in self.lines:
            out.line(text)
        return out.finish(self.next_step, 1)


def escalate(otherwise):
    """The Next: step after a refused command: the one escalated retry, then
    what to do otherwise."""
    return ESCALATE + " " + otherwise


def refused(lines, otherwise):
    """A Failure for a file operation the system refused."""
    return Failure(lines, escalate(otherwise))


def write(lines):
    text = "".join(one_line(line) + "\n" for line in lines)
    data = text.encode("utf-8", "replace")
    stream = getattr(sys.stdout, "buffer", None)
    if stream is None:
        sys.stdout.write(data.decode("utf-8"))
        sys.stdout.flush()
        return
    stream.write(data)
    stream.flush()
