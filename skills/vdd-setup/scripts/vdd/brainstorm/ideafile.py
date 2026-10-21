"""One idea file: frontmatter, an H1 title, prose sections and ## History last.

The frontmatter holds tldr, status, parent, importance, size, fog and
last-updated. The sections keep the order of ORDER; a section the tool adds
goes before the first later one that exists. ## History holds one
"- YYYY-MM-DD: <event>" line per structural event. Ideas name each other by
slug: a bare slug at the head of a ## Related Ideas line, a code span in
prose.
"""

from __future__ import annotations

import datetime
import os
import re
from typing import Iterable, List, Optional, Tuple

from .. import workfile

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
# Where a raw file's frontmatter ends, in any line ending, and its
# last-updated line.
FM_END = re.compile(r"(\r\n|\r|\n)---(\r\n|\r|\n)")
LAST_UPDATED = re.compile(r"(?<![^\r\n])last-updated:[^\r\n]*")
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


def seam_set() -> bool:
    return bool(DATE.match(os.environ.get("VDD_TODAY", "")))


def is_idea_name(name: str) -> bool:
    return name.endswith(".md") and name[:-3] not in RESERVED and bool(SLUG.match(name[:-3]))


def usable_slug(slug: str | None) -> bool:
    return bool(slug) and bool(SLUG.match(slug or "")) and slug not in RESERVED


def squash(text: str | None) -> str:
    """Text as one line with single spaces."""
    return " ".join((text or "").split())


# --- Markdown -------------------------------------------------------------------


def split_frontmatter(text: str) -> tuple[list[list[str]], str]:
    """(fields as an ordered list of [key, value], body). A key with list
    items below it keeps them joined with newlines. No frontmatter, or one
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
            pairs.append([match.group(1), match.group(2).strip()])
            continue
        match = FM_ITEM.match(line)
        if match and pairs:
            pairs[-1][1] = (pairs[-1][1] + "\n" + match.group(1).strip()).strip("\n")
    return pairs, text[end + 5:]


def frontmatter_reads_whole(text: str) -> bool:
    """Whether split_frontmatter reads every line of the frontmatter: a
    folded value, a comment or a key it does not match make it False, as
    does no frontmatter at all. A blank line it skips loses nothing."""
    if not text.startswith("---\n"):
        return False
    end = text.find("\n---\n", 3)
    if end < 0:
        return False
    for line in text[4:end].split("\n"):
        if line.strip() and not (FM_KEY.match(line) or FM_ITEM.match(line)):
            return False
    return True


def stamp_text(text: str, day: str) -> str:
    """The file's raw text, a byte order mark and its line endings kept,
    with its last-updated line set to day, every other byte as it was; a
    file without the line gets it last in its frontmatter, in the line
    ending that closes the frontmatter. A text with no frontmatter end comes
    back as it was."""
    match = FM_END.search(text, 3)
    if match is None:
        return text
    eol = match.group(1)
    head, tail = text[:match.start() + len(eol)], text[match.start() + len(eol):]
    line = "last-updated: %s" % day
    if LAST_UPDATED.search(head):
        head = LAST_UPDATED.sub(lambda _: line, head, count=1)
    else:
        head += line + eol
    return head + tail


def fenced(lines: Iterable[str]) -> list[bool]:
    """For each line, whether it is a fence line or sits inside a fenced code
    block, by the shared Markdown reader's fence rule."""
    out: list[bool] = []
    run = None
    for line in lines:
        if run is not None:
            out.append(True)
            if workfile.closes(line, run):
                run = None
            continue
        run = workfile.fence_run(line)
        out.append(run is not None)
    return out


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


# --- one idea -------------------------------------------------------------------


class Idea:
    """One idea file: its slug, path, frontmatter and body."""

    def __init__(self, slug: str, path: str, text: str) -> None:
        self.slug = slug
        self.path = path
        self.fm, self.body = split_frontmatter(text)

    @classmethod
    def frame(cls, slug: str, path: str, fields: Iterable[tuple[str, str]], body: Iterable[str]) -> Idea:
        """A new idea from its fields and its body's lines."""
        idea = cls(slug, path, "")
        for key, value in fields:
            idea.set(key, value)
        idea.body = "\n".join(body)
        return idea

    def get(self, key: str, default: str = "") -> str:
        for k, v in self.fm:
            if k == key:
                return v
        return default

    def set(self, key: str, value: str | None) -> None:
        """Set a field; an empty value removes it. A new field goes in
        FIELDS order."""
        for pair in self.fm:
            if pair[0] == key:
                if not value:
                    self.fm.remove(pair)
                else:
                    pair[1] = value
                return
        if not value:
            return
        pos = len(self.fm)
        if key in FIELDS:
            later = FIELDS[FIELDS.index(key) + 1:]
            for i, (k, _) in enumerate(self.fm):
                if k in later:
                    pos = i
                    break
        self.fm.insert(pos, [key, value])

    @property
    def status(self) -> str:
        return self.get("status")

    @property
    def is_open(self) -> bool:
        return self.status not in CLOSED

    @property
    def parent(self) -> str | None:
        return self.get("parent") or None

    @property
    def tldr(self) -> str:
        return squash(self.get("tldr"))

    @property
    def title(self) -> str:
        match = re.search(r"^# (.+)$", self.body, re.M)
        return match.group(1).strip() if match else self.slug

    def set_title(self, title: str) -> None:
        line = "# " + squash(title)
        if re.search(r"^# .+$", self.body, re.M):
            self.body = re.sub(r"^# .+$", lambda _: line, self.body, count=1, flags=re.M)
        else:
            self.body = "\n" + line + "\n" + self.body

    def section(self, name: str) -> str:
        for n, _, content, end in section_spans(self.body):
            if n == name:
                return self.body[content:end].strip("\n")
        return ""

    def section_names(self) -> list[str]:
        return [n for n, _, _, _ in section_spans(self.body)]

    def replace_section(self, name: str, content: str) -> None:
        """Replace a section's content, adding the section before the first
        later one in ORDER, or at the end, when it is missing."""
        content = content.strip("\n")
        spans = section_spans(self.body)
        for n, _, start, end in spans:
            if n == name:
                tail = self.body[end:]
                self.body = self.body[:start] + "\n" + content + "\n" + ("\n" if tail else "") + tail
                return
        block = "## %s\n\n%s\n\n" % (name, content)
        later = ORDER[ORDER.index(name) + 1:] if name in ORDER else (HISTORY,)
        for n, head, _, _ in spans:
            if n in later:
                self.body = self.body[:head] + block + self.body[head:]
                return
        self.body = self.body.rstrip("\n") + "\n\n" + block.rstrip("\n") + "\n"

    def append(self, name: str, text: str, item: str | None = None) -> None:
        """Add text at the end of a section: a list item ("- " or "- [ ] ")
        when item is given, else a paragraph."""
        cur = self.section(name)
        empty = cur.strip() in EMPTY
        if item is not None:
            lines = text.strip("\n").split("\n")
            new = item + lines[0] + "".join("\n  " + line if line.strip() else "\n" for line in lines[1:])
            content = new if empty else cur.rstrip("\n") + "\n" + new
        else:
            content = text.strip("\n") if empty else cur.rstrip("\n") + "\n\n" + text.strip("\n")
        self.replace_section(name, content)

    def history(self) -> list[tuple[str, str]]:
        """[(date, event)] of the ## History lines, oldest first."""
        out: list[tuple[str, str]] = []
        for line in self.section(HISTORY).split("\n"):
            match = re.match(r"^- (\d{4}-\d{2}-\d{2}): (.+)$", line.strip())
            if match:
                out.append((match.group(1), match.group(2).strip()))
        return out

    def add_history(self, event: str, date: str | None = None) -> None:
        line = "- %s: %s" % (date or today(), event)
        if HISTORY not in self.section_names():
            self.body = self.body.rstrip("\n") + "\n\n## %s\n\n%s\n" % (HISTORY, line)
            return
        cur = self.section(HISTORY)
        self.replace_section(HISTORY, (cur.rstrip("\n") + "\n" + line) if cur.strip() else line)

    def created(self) -> str | None:
        for date, event in self.history():
            if event.startswith("created"):
                return date
        return None

    def closed_on(self) -> str | None:
        """The date of the History line that gave the idea its closed status,
        or None."""
        found = None
        for date, event in self.history():
            if event == "status %s" % self.status:
                found = date
        return found

    def next_steps(self) -> list[tuple[bool, str]]:
        """[(ticked, text)] of the Next Steps checklist."""
        out: list[tuple[bool, str]] = []
        for item in list_items(self.section("Next Steps")):
            match = re.match(r"^\[( |x|X)\]\s*(.*)$", item, re.S)
            if match:
                out.append((match.group(1) != " ", match.group(2).strip()))
        return out

    def open_steps(self) -> list[str]:
        return [text for ticked, text in self.next_steps() if not ticked]

    def questions(self) -> list[tuple[str, bool, bool]]:
        """[(question, settled, noted)]: the question up to its first "?";
        settled when the text after it starts with Settled or Answer, noted
        when other text follows it."""
        out: list[tuple[str, bool, bool]] = []
        for item in list_items(self.section("Open Questions")):
            q = item.strip()
            if not q or q.startswith("<"):
                continue
            i = q.find("?")
            head, rest = (q[:i + 1], q[i + 1:].strip()) if i >= 0 else (q, "")
            settled = bool(re.match(r"^(settled|answer|answered|decided)\b", rest, re.I))
            out.append((head, settled, bool(rest) and not settled))
        return out

    def decision(self) -> str:
        return self.section("Decision").strip()

    def reopen_when(self) -> str:
        found = re.findall(r"Reopen when:\s*(.+?)(?:\n\s*\n|\Z)", self.decision(), re.S)
        return squash(found[-1]) if found else ""

    def relation_items(self) -> list[Relation]:
        """[(kind, [slugs], reason, raw)] of the ## Related Ideas lines."""
        out: list[Relation] = []
        for item in list_items(self.section("Related Ideas")):
            found = relation_lead(item)
            if found:
                kind, lead, reason = found
                out.append((kind, lead_tokens(lead), reason, item))
        return out

    def text(self) -> str:
        """The prose: the body without ## History."""
        for n, head, _, end in section_spans(self.body):
            if n == HISTORY:
                return self.body[:head] + self.body[end:]
        return self.body

    def render(self) -> str:
        lines = ["---"]
        for key, value in self.fm:
            if "\n" in value:
                lines.append("%s:" % key)
                lines.extend("  - %s" % x for x in value.split("\n"))
            else:
                lines.append("%s: %s" % (key, value))
        lines.append("---")
        body = self.body if self.body.startswith("\n") else "\n" + self.body
        text = "\n".join(lines) + "\n" + body
        return text if text.endswith("\n") else text + "\n"
