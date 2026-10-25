"""An idea file's text read as a library: the vocabulary (statuses,
metrics, relation kinds, section order), the frontmatter split, the
sections outside fenced code, list items and relation leads. The idea model
in idea.py builds on it; the store and the moves read it too."""

from __future__ import annotations

import datetime
import os
import re
from typing import List, Optional, Tuple

from ... import textfile
from ...markdown import fenced

OPEN = ("idea", "discussed", "shaped", "decided", "in-progress")
CLOSED = ("done", "dropped")
STATUSES = OPEN + CLOSED
METRICS = ("xsmall", "small", "medium", "large", "xlarge", "unknown")
KINDS = ("depends on", "benefits from", "enables", "helps", "related", "absorbs")
FIELDS = ("tldr", "status", "parent", "importance", "size", "fog", "last-updated")
# File names at the store's top that are never an idea: the 0.15 index a
# stale skill may still write, and cleanup's record.
RESERVED = ("index", "removed")
SLUG_PATTERN = "[a-z0-9]+(-[a-z0-9]+)*"
SLUG = re.compile("^" + SLUG_PATTERN + "$")
KIND_RE = re.compile(r"^(depends on|benefits from|enables|helps|related|absorbs)\s+(.*)$", re.I | re.S)
TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HISTORY = "History"
ORDER = ("Key Metrics", "Summary", "Proposal", "Pro", "Con", "Open Questions", "Evidence", "Prior Art",
         "Related Ideas", "Decision", "Next Steps", HISTORY)
KNOWN = {name.lower(): name for name in ORDER}
TLDR_MAX = 200
# A frontmatter line split_frontmatter reads: a key with its value, and a
# list item under the key before it.
FM_KEY = re.compile(r"^([A-Za-z][A-Za-z0-9-]*):\s*(.*)$")
FM_ITEM = re.compile(r"^\s+-\s+(.*)$")
# A YAML block indicator as a key's whole value: | or >, a chomping sign and
# an indentation digit in either order, a comment. Its text sits on the lines
# below, which split_frontmatter does not read; render quotes such a value.
BLOCK = re.compile(r"^[>|](?:[-+]?[1-9]?|[1-9][-+])(?:\s+#.*)?$")
DEPTH_MAX = 3
# A section's text that holds nothing yet.
EMPTY = ("", "None.", "None", "- [ ] <smallest step that moves status forward>")

Span = Tuple[str, int, int, int]
Relation = Tuple[str, List[str], str, str]


def today() -> str:
    """The date every write records: VDD_TODAY when it holds YYYY-MM-DD
    (the tests' date seam), else the local date."""
    seam = os.environ.get("VDD_TODAY", "")
    if DATE.match(seam):
        return seam
    return datetime.date.today().isoformat()


def real_date(text: str) -> bool:
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def is_idea_name(name: str) -> bool:
    return name.endswith(".md") and name[:-3] not in RESERVED and bool(SLUG.match(name[:-3]))


def usable_slug(slug: str | None) -> bool:
    return bool(slug) and bool(SLUG.match(slug or "")) and slug not in RESERVED


def squash(text: str | None) -> str:
    """Text as one line with single spaces."""
    return " ".join((text or "").split())


# --- Markdown -------------------------------------------------------------------


def quoted_block(value: str) -> bool:
    """Whether render quotes the value: a block indicator, or a value that
    is such a quoted value itself ("|", ""|""), so one pair of quotes read
    off gives back what was written."""
    while value[:1] == value[-1:] == '"' and len(value) > 1:
        value = value[1:-1]
    return bool(BLOCK.match(value))


def split_frontmatter(text: str) -> tuple[list[list[str]], str]:
    """(fields as an ordered list of [key, value], body). A key with list
    items below it keeps them joined with newlines, and a block indicator
    render quoted ("|", ""|"") is read without one pair of quotes. No frontmatter, or one
    that is never closed, gives no fields and the whole text as body."""
    if not text.startswith("---\n"):
        return [], text
    end = text.find("\n---\n", 3)
    if end < 0:
        return [], text
    pairs: list[list[str]] = []
    for line in text[4:end].split("\n"):
        match = FM_KEY.match(line)
        if match:
            value = match.group(2).strip()
            if value[:1] == value[-1:] == '"' and len(value) > 1 and quoted_block(value[1:-1]):
                value = value[1:-1]
            pairs.append([match.group(1), value])
            continue
        match = FM_ITEM.match(line)
        if match and pairs:
            pairs[-1][1] = (pairs[-1][1] + "\n" + match.group(1).strip()).strip("\n")
    return pairs, text[end + 5:]


def unread_line(data: bytes) -> str | None:
    """Where a file's bytes hold what a rewrite would lose: "line <n>: bytes
    that are not UTF-8" at the line of the first such byte, or "line <n>: a
    frontmatter line this tool does not read: <line>"; None when the file
    reads whole. Lines count from 1, the opening --- being line 1. A key
    whose value is a block indicator (tldr: >) is the unread line, else the
    first line that is neither a key nor a list item. A file without a
    closed frontmatter is unread at line 1. A blank line loses nothing."""
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as error:
        head = data[:error.start].decode("utf-8")
        return "line %d: bytes that are not UTF-8" % (head.replace("\r\n", "\n").replace("\r", "\n").count("\n") + 1)
    text = textfile.decode(data)
    unread = "line %d: a frontmatter line this tool does not read: %s"
    end = text.find("\n---\n", 3)
    if not text.startswith("---\n") or end < 0:
        return unread % (1, text.split("\n", 1)[0])
    for n, line in enumerate(text[4:end].split("\n"), 2):
        key = FM_KEY.match(line)
        if key and BLOCK.match(key.group(2).strip()):
            return unread % (n, line)
        if line.strip() and not (key or FM_ITEM.match(line)):
            return unread % (n, line)
    return None


def section_spans(body: str) -> list[Span]:
    """[(name, heading start, content start, end)] of the H2 sections, as
    character offsets, outside fenced code. A heading that names a section
    of ORDER in other case gets ORDER's name."""
    lines = body.split("\n")
    inside = fenced(lines)
    starts: list[tuple[str, int, int]] = []
    offset = 0
    for i, line in enumerate(lines):
        if not inside[i] and line.startswith("## "):
            name = line[3:].strip()
            name = KNOWN.get(" ".join(name.split()).lower(), name)
            starts.append((name, offset, offset + len(line) + 1))
        offset += len(line) + 1
    spans: list[Span] = []
    for n, (name, head, content) in enumerate(starts):
        end = starts[n + 1][1] if n + 1 < len(starts) else len(body)
        spans.append((name, head, min(content, len(body)), end))
    return spans


def list_items(text: str) -> list[str]:
    """The top-level "- " items, continuation lines joined with a space."""
    items: list[str] = []
    cur: Optional[str] = None
    for line in text.split("\n"):
        if line.startswith("- "):
            if cur is not None:
                items.append(cur)
            cur = line[2:].strip()
        elif cur is not None and line.strip() and line[:1] in (" ", "\t"):
            cur += " " + line.strip()
        elif cur is not None:
            items.append(cur)
            cur = None
    if cur is not None:
        items.append(cur)
    return items


def is_open_step(line: str) -> bool:
    """A Next Steps line that opens an open step, read as next_steps reads
    it: a "- " item whose text starts with "[ ]"."""
    return line.startswith("- ") and line[2:].strip().startswith("[ ]")


def reflow(text: str) -> list[str]:
    """Paragraphs and list items as single lines, so a quoted phrase is read
    and searched whole."""
    out: list[str] = []
    cur: Optional[str] = None
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if cur is not None:
                out.append(cur)
                cur = None
            continue
        starts = bool(re.match(r"^(\s*)([-*]|\d+\.)\s", line)) or stripped[:1] in ("#", "|")
        if cur is None or starts:
            if cur is not None:
                out.append(cur)
            cur = line.rstrip()
        else:
            cur += " " + stripped
    if cur is not None:
        out.append(cur)
    return out


def lead_end(rest: str, start: int = 0) -> int:
    """The offset of the first colon outside brackets in rest from start, or
    len(rest): where a relation line's lead ends and its reason begins."""
    depth = 0
    for i in range(start, len(rest)):
        ch = rest[i]
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            return i
    return len(rest)


def relation_lead(item: str) -> tuple[str, str, str] | None:
    """(kind, lead, reason) of a Related Ideas item, or None."""
    match = KIND_RE.match(item)
    if not match:
        return None
    rest = match.group(2)
    end = lead_end(rest)
    return match.group(1).lower(), rest[:end], rest[end + 1:].strip()


def lead_tokens(lead: str) -> list[str]:
    return [t for t in TOKEN.findall(lead.lower()) if t not in ("and", "or")]
