"""The idea store: .scratch/_brainstorming/ in layout 2, one flat folder.

<slug>.md holds one idea, open or closed. .layout holds the layout number,
removed.md one line per idea cleanup removed, research/<slug>/ an idea's
research. .state/ is the tool's own: the write lock, the ledger of each idea
file's hash as the tool last wrote it, and the journal of a write in
progress. Store loads every idea at once and collects one command's writes,
which save writes together.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
from typing import Callable

from .. import textfile
from ..out import Failure
from .ideafile import (DEPTH_MAX, SLUG, Idea, frontmatter_reads_whole, is_idea_name, seam_set, stamp_text, today,
                       unread_line)

# Written with "/" because it is printed, and so are the backup, staging and
# lock paths built from it; Windows takes "/" in a path as well.
STORE = ".scratch/_brainstorming"
LAYOUT = "2"
LAYOUT_FILE = ".layout"
STATE = ".state"
LEDGER = "ledger.json"
REMOVED = "removed.md"
REMOVED_HEAD = ("# Removed ideas\n\nIdeas brainstorm cleanup removed from the store, one line each: slug | title | "
                "status | closed | removed | the Decision's gist.\n\n")

def store_dir(root: str) -> str:
    return os.path.join(root, STORE)


def state_dir(root: str) -> str:
    return os.path.join(store_dir(root), STATE)


def rel(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ledger_sha(data: bytes) -> str:
    """The ledger's hash of an idea file: of its text as read (UTF-8, LF, no
    byte order mark), so an editor that only changes line ends or adds a BOM
    makes no edit."""
    return sha(textfile.decode(data).encode("utf-8"))


def utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def read_once(path: str) -> str | None:
    """A file the store reads once per command, retried while another
    process holds it."""
    return textfile.read(path)


def layout(root: str) -> str | None:
    """The store's layout: the marker's text, "damaged" for an empty marker,
    "lost" for a layout-2 store without its marker, "1" for a 0.15 store,
    None for no store. A store without a marker is layout 2 when its idea
    files have History, or when .state/ or removed.md sit beside a stale
    index.md (M7)."""
    base = store_dir(root)
    try:
        names = os.listdir(base)
    except OSError:
        return None
    if LAYOUT_FILE in names:
        value = (read_once(os.path.join(base, LAYOUT_FILE)) or "").strip()
        return value or "damaged"
    if STATE in names or REMOVED in names:
        return "lost"
    if "index.md" in names:
        return "1"
    ideas = [n for n in names if is_idea_name(n)]
    for name in ideas:
        if Idea(name[:-3], os.path.join(base, name), textfile.read(os.path.join(base, name)) or "").created():
            return "lost"
    return "1" if ideas else None


def require_layout(root: str) -> None:
    """Refuse a store that is not layout 2, naming the way out."""
    found = layout(root)
    if found == LAYOUT:
        return
    if found is None:
        raise Failure("This project has no idea store yet (.scratch/_brainstorming/).",
                      "Capture the first idea with brainstorm new; it creates the store.")
    if found == "1":
        raise Failure("The idea store is still in the 0.15 layout (index.md). Nothing was written.",
                      "Run brainstorm start: it shows the migration to ask the user about (brainstorm migrate).")
    if found in ("damaged", "lost"):
        raise Failure("The idea store's .layout marker is %s. Nothing was written."
                      % ("empty" if found == "damaged" else "missing"),
                      "Run brainstorm migrate --write: it checks the store and writes the marker back.")
    raise Failure(
        "The idea store has layout %s, which this copy of the VDD tool does not know (it knows %s): a newer VDD "
        "wrote it. Nothing was read or written." % (found, LAYOUT),
        "Tell the user this copy of the VDD tool is older than their idea store: update VDD, rerun Setup "
        "(vdd-setup), then start again. Stop.")


# --- removed.md -----------------------------------------------------------------


def removed_entries(root: str) -> list[dict[str, str]]:
    """[{slug, title, status, closed, removed, gist}] of removed.md, oldest
    first."""
    text = read_once(os.path.join(store_dir(root), REMOVED)) or ""
    out: list[dict[str, str]] = []
    for line in text.split("\n"):
        if not line.startswith("- "):
            continue
        bits = [b.strip() for b in line[2:].split(" | ")]
        if len(bits) < 6 or not SLUG.match(bits[0]):
            continue
        out.append({"slug": bits[0], "title": bits[1], "status": bits[2],
                    "closed": bits[3].replace("closed ", ""), "removed": bits[4].replace("removed ", ""),
                    "gist": " | ".join(bits[5:])})
    return out


def removed_entry(root: str, slug: str) -> dict[str, str] | None:
    found = [e for e in removed_entries(root) if e["slug"] == slug]
    return found[-1] if found else None


def removed_line(idea: Idea, closed: str | None, gist: str) -> str:
    return "- %s | %s | %s | closed %s | removed %s | %s\n" % (
        idea.slug, idea.title.replace("|", "/"), idea.status, closed or "unknown", today(),
        " ".join(gist.replace(" | ", " / ").split()))


def removed_reopen(entry: dict[str, str]) -> str:
    match = re.search(r"Reopen when:\s*(.+)$", entry["gist"])
    return match.group(1).strip() if match else ""


# --- the ledger -----------------------------------------------------------------


def read_ledger(root: str) -> dict[str, str]:
    text = read_once(os.path.join(state_dir(root), LEDGER))
    try:
        data = json.loads(text) if text else {}
    except ValueError:
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def ledger_bytes(hashes: dict[str, str]) -> bytes:
    return json.dumps(hashes, sort_keys=True, indent=0).encode("utf-8")


def update_ledger(root: str, hashes: dict[str, str], gone: list[str]) -> None:
    led = read_ledger(root)
    led.update(hashes)
    for slug in gone:
        led.pop(slug, None)
    os.makedirs(state_dir(root), exist_ok=True)
    textfile.write(os.path.join(state_dir(root), LEDGER), ledger_bytes(led))


# --- unknown slugs ----------------------------------------------------------------


def close_slugs(slug: str, names: list[str], n: int = 3) -> list[str]:
    def score(other: str) -> tuple[int, int]:
        common = len(set(slug.split("-")) & set(other.split("-")))
        prefix = 0
        for x, y in zip(slug, other):
            if x != y:
                break
            prefix += 1
        return (common, prefix)

    ranked = sorted(names, key=score, reverse=True)
    return [s for s in ranked[:n] if score(s) != (0, 0)]


def unknown_lines(slug: str, names: list[str]) -> list[str]:
    near = close_slugs(slug, names)
    lines = ["No idea named %s." % slug]
    if near:
        lines.append("Closest: %s." % ", ".join(near))
    return lines


# --- the store ------------------------------------------------------------------


class Store:
    """Every idea of a layout-2 store, loaded at once, and the writes of one
    command, done together by save."""

    def __init__(self, root: str) -> None:
        self.root = root
        self.dir = store_dir(root)
        self.ideas: dict[str, Idea] = {}
        self.disk: dict[str, bytes] = {}
        self.dirty: set[str] = set()
        self.deleted: set[str] = set()
        self.extra: dict[str, bytes] = {}
        self.dir_moves: list[tuple[str, str]] = []
        self.stamped: list[str] = []
        # The Next: line of a dry run, when the command words its own.
        self.dry_next: str | None = None
        try:
            names = sorted(os.listdir(self.dir))
        except OSError:
            names = []
        for name in names:
            path = os.path.join(self.dir, name)
            if not is_idea_name(name) or not os.path.isfile(path):
                continue
            data = textfile.read_bytes(path)
            slug = name[:-3]
            self.disk[slug] = data
            self.ideas[slug] = Idea.read(slug, path, data)
        self.ledger = read_ledger(root)
        # Each idea's parent as loaded, so a loop the command did not make is
        # told apart from one it makes.
        self.loaded_parents = {slug: idea.parent for slug, idea in self.ideas.items()}
        self.stamp_hand_edits()

    def stamp_hand_edits(self) -> None:
        """An idea whose text differs from what the tool last wrote was
        edited by hand or by the model: its last-updated becomes the edit's
        day (the file's modification day, or VDD_TODAY), in memory for a read
        and on disk with the next write, which changes that one line. A file
        whose frontmatter does not parse is left as it is (M11): one with a
        line the reader does not read, or bytes that are not UTF-8."""
        for slug, data in sorted(self.disk.items()):
            idea = self.ideas[slug]
            if slug not in self.ledger or self.ledger[slug] == ledger_sha(data):
                continue
            if not utf8(data) or not frontmatter_reads_whole(textfile.decode(data)):
                continue
            day = today() if seam_set() else datetime.date.fromtimestamp(os.path.getmtime(idea.path)).isoformat()
            if idea.get("last-updated") != day:
                idea.set("last-updated", day)
                self.stamped.append(slug)

    def get(self, slug: str) -> Idea:
        idea = self.ideas.get(slug)
        if idea is not None:
            return idea
        gone = removed_entry(self.root, slug)
        if gone:
            raise Failure(["%s was removed from the store by cleanup on %s; removed.md keeps its line:"
                           % (slug, gone["removed"]),
                           "  > %s [%s, closed %s]: %s" % (gone["title"], gone["status"], gone["closed"],
                                                           gone["gist"])],
                          "Answer the user from that line; the idea itself is gone.")
        raise Failure(unknown_lines(slug, sorted(self.ideas)),
                      "Run the command again with the slug as the user meant it, from the list above or the start "
                      "read. If none fits, ask the user which idea they mean.")

    def path(self, slug: str) -> str:
        return os.path.join(self.dir, slug + ".md")

    def add(self, idea: Idea) -> None:
        self.ideas[idea.slug] = idea
        self.dirty.add(idea.slug)

    # Every walk over a family keeps a visited set, so a parent loop written
    # by hand ends it instead of hanging it.

    def children(self, slug: str) -> list[str]:
        return sorted(s for s, i in self.ideas.items() if i.parent == slug and s != slug)

    def descendants(self, slug: str) -> list[str]:
        """Every idea below slug, depth first."""
        out: list[str] = []
        seen = {slug}
        todo = self.children(slug)
        while todo:
            s = todo.pop(0)
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
            todo = self.children(s) + todo
        return out

    def parent_walk(self, slug: str, parent_of: Callable[[str], str | None] | None = None
                    ) -> tuple[list[str], str | None]:
        """(the ancestors of slug, nearest first, and the idea where the walk
        met a parent loop, or None). The walk ends at a parent that is no
        idea, or at the first idea it meets twice. parent_of gives each
        idea's parent, the current one by default."""
        parent = parent_of or (lambda s: self.ideas[s].parent)
        out: list[str] = []
        seen = {slug}
        cur = parent(slug)
        while cur and cur in self.ideas:
            if cur in seen:
                return out, cur
            seen.add(cur)
            out.append(cur)
            cur = parent(cur)
        return out, None

    def ancestors(self, slug: str) -> list[str]:
        return self.parent_walk(slug)[0]

    def in_cycle(self, slug: str) -> bool:
        """Whether following parents from slug leads back to slug."""
        return self.parent_walk(slug)[1] == slug

    def under_loop(self, slug: str) -> bool:
        """Whether following parents from slug runs into a loop."""
        return self.parent_walk(slug)[1] is not None

    def depth(self, slug: str) -> int:
        return 1 + len(self.ancestors(slug))

    def top(self, slug: str) -> str:
        found = self.ancestors(slug)
        return found[-1] if found else slug

    def relations(self) -> list[tuple[str, str, str, str]]:
        """[(from, kind, to, reason)] of every relation line whose slug names
        an idea, on the side it is written."""
        out: list[tuple[str, str, str, str]] = []
        for s, idea in sorted(self.ideas.items()):
            for kind, slugs, reason, _ in idea.relation_items():
                for t in slugs:
                    if t in self.ideas and t != s:
                        out.append((s, kind, t, reason))
        return out

    def waits_on(self) -> dict[str, list[str]]:
        """slug -> sorted slugs it waits on: its own "depends on" lines and
        the "enables" lines of others that name it."""
        out: dict[str, set[str]] = {}
        for frm, kind, to, _ in self.relations():
            if kind == "depends on":
                out.setdefault(frm, set()).add(to)
            elif kind == "enables":
                out.setdefault(to, set()).add(frm)
        return {k: sorted(v) for k, v in out.items()}

    def waited_by(self, slug: str) -> list[str]:
        return sorted(s for s, on in self.waits_on().items() if slug in on)

    def open_below(self, slug: str) -> list[str]:
        return [s for s in self.descendants(slug) if self.ideas[s].is_open]

    def touch(self, slug: str, date: str | None = None) -> None:
        self.ideas[slug].set("last-updated", date or today())
        self.dirty.add(slug)

    def loaded_loop(self, slug: str) -> bool:
        """Whether slug sat in or under a parent loop as the store was
        loaded, and the command left its parent and every parent above it
        as they were."""
        if slug not in self.ideas:
            return False
        chain, loop = self.parent_walk(slug, self.loaded_parents.get)
        return loop is not None and all(self.ideas[s].parent == self.loaded_parents.get(s) for s in [slug] + chain)

    def structure_problems(self, slugs: set[str] | list[str]) -> list[str]:
        """Parent loops and families deeper than DEPTH_MAX among slugs and
        everything below them; a loop the command found as it is, and did
        not change, is no problem of this command (existing_loops names
        it)."""
        probs: list[str] = []
        for s in sorted(self.looked_at(slugs)):
            if self.under_loop(s):
                if not self.loaded_loop(s):
                    probs.append("%s sits in or under a parent loop: %s" % (s, " -> ".join([s] + self.ancestors(s))))
            elif self.depth(s) > DEPTH_MAX:
                probs.append("%s would sit %d levels deep; a family keeps at most %d"
                             % (s, self.depth(s), DEPTH_MAX))
        return probs

    def looked_at(self, slugs: set[str] | list[str]) -> set[str]:
        look: set[str] = set()
        for s in slugs:
            if s in self.ideas:
                look.add(s)
                look.update(self.descendants(s))
        return look

    def existing_loops(self) -> list[str]:
        """The ideas of a parent loop the store was loaded with that this
        command writes, sorted: in the loop itself, not only under it."""
        return sorted(s for s in self.looked_at(self.dirty) if self.in_cycle(s) and self.loaded_loop(s))

    def unread(self, slugs: set[str] | list[str]) -> list[str]:
        """"<slug>.md line <n>: ..." for each idea among slugs whose file, as
        loaded, holds what a rewrite would lose."""
        out: list[str] = []
        for slug in sorted(slugs):
            idea = self.ideas.get(slug)
            if idea is not None and idea.loaded is not None:
                found = unread_line(idea.loaded)
                if found:
                    out.append("%s %s" % (idea.loaded_name, found))
        return out

    def ops(self) -> list[tuple[str, bytes | None, bytes | None]]:
        """[(name, bytes before, bytes after)] of the command's file writes,
        after the family-tree guard."""
        unread = self.unread(self.dirty)
        if unread:
            raise Failure(["Refused, nothing was written: this command would rewrite idea files that hold what this "
                           "tool does not read."] + unread,
                          "Tell the user the file and line above and ask them to fix it; then run the same command "
                          "again.")
        probs = self.structure_problems(self.dirty)
        if probs:
            raise Failure(["Refused, nothing was written: the change would break the family tree."] + probs,
                          "Ask the user where the idea belongs instead.")
        ops: list[tuple[str, bytes | None, bytes | None]] = []
        for slug in sorted(self.dirty | set(self.stamped)):
            if slug in self.deleted or slug not in self.ideas:
                continue
            if slug in self.dirty:
                data = self.ideas[slug].render().encode("utf-8")
            else:
                data = stamp_text(self.disk[slug].decode("utf-8"),
                                  self.ideas[slug].get("last-updated")).encode("utf-8")
            if self.disk.get(slug) != data:
                ops.append((slug + ".md", self.disk.get(slug), data))
        for slug in sorted(self.deleted):
            if slug in self.disk:
                ops.append((slug + ".md", self.disk[slug], None))
        for name, data in sorted(self.extra.items()):
            path = os.path.join(self.dir, name)
            before = textfile.read_bytes(path) if os.path.isfile(path) else None
            ops.append((name, before, data))
        return ops

    def planned(self) -> list[str]:
        """What save would write, for a dry run: file names, a removal
        marked."""
        names = [n if after is not None else n + " (removed)" for n, _, after in self.ops()]
        return names + ["research/%s/ (renamed to research/%s/)" % (old.split("/", 1)[1], new.split("/", 1)[1])
                        for old, new in self.dir_moves]

    def written(self, ops: list[tuple[str, bytes | None, bytes | None]]) -> None:
        """Record ops as on disk, and write the ledger with them: the save's
        step after the files (journal.save)."""
        for name, _, after in ops:
            slug = name[:-3]
            if not is_idea_name(name):
                continue
            if after is None:
                self.disk.pop(slug, None)
            elif slug in self.ideas:
                self.disk[slug] = after
        hashes = {s: ledger_sha(d) for s, d in self.disk.items() if s in self.ideas}
        update_ledger(self.root, hashes, sorted(self.deleted))
        self.dirty, self.deleted, self.extra, self.dir_moves, self.stamped = set(), set(), {}, [], []

