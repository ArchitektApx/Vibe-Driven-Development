"""One idea file: frontmatter, an H1 title, prose sections and ## History last.

The frontmatter holds tldr, status, parent, importance, size, fog and
last-updated. The sections keep the order of ORDER; a section the tool adds
goes before the first later one that exists. ## History holds one
"- YYYY-MM-DD: <event>" line per structural event. Ideas name each other by
slug: a bare slug at the head of a ## Related Ideas line, a code span in
prose.
"""

from __future__ import annotations

import os
import re
from typing import Iterable

from ... import textfile
from .text import (
    CLOSED,
    EMPTY,
    FIELDS,
    HISTORY,
    ORDER,
    Relation,
    lead_tokens,
    list_items,
    quoted_block,
    real_date,
    relation_lead,
    section_spans,
    split_frontmatter,
    squash,
    today,
)


class Idea:
    """One idea file: its slug, path, frontmatter and body."""

    def __init__(self, slug: str, path: str, text: str) -> None:
        self.slug = slug
        self.path = path
        self.fm, self.body = split_frontmatter(text)
        # The file as loaded: its name and bytes, whether it began with a
        # byte order mark, and its first line break, which render writes back.
        self.loaded_name = ""
        # The file's modification day as loaded, in local time.
        self.file_day = ""
        self.loaded: bytes | None = None
        self.bom = False
        self.eol = "\n"

    @classmethod
    def read(cls, slug: str, path: str, data: bytes) -> Idea:
        """An idea from its file's bytes."""
        idea = cls(slug, path, textfile.decode(data))
        idea.loaded_name = os.path.basename(path)
        idea.loaded = data
        idea.bom = data.startswith(b"\xef\xbb\xbf")
        found = re.search(b"\r\n|\r|\n", data)
        if found:
            idea.eol = found.group(0).decode("ascii")
        return idea

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

    def shown_day(self) -> str:
        """The day every read shows and compares: the later of last-updated
        and the file's modification day, never after today, so an edit by
        hand shows without a write."""
        updated = self.get("last-updated")
        day = min(self.file_day, today()) if self.file_day else ""
        if not real_date(updated):
            return day or updated
        return max(updated, day)

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
                lines.append(("%s: \"%s\"" if quoted_block(value) else "%s: %s") % (key, value))
        lines.append("---")
        body = self.body if self.body.startswith("\n") else "\n" + self.body
        text = "\n".join(lines) + "\n" + body
        text = text if text.endswith("\n") else text + "\n"
        return ("\ufeff" if self.bom else "") + text.replace("\n", self.eol)
