"""The reads: start's overview, show, find and check. None writes."""

from __future__ import annotations

import os
import re
from typing import Any

from ..out import Failure, Output
from .ideafile import DEPTH_MAX, STATUSES, Idea, is_idea_name, reflow, squash, unread_line
from .printed import QUOTE, quoted, step_line
from .store import REMOVED, Store, rel, removed_entries, removed_entry

FIND_MAX = 10
# The 0.15 workaround for a part: "Part 2 of <parent>." in its tldr.
PART_OF = re.compile(r"\bPart (?:\d+ )?of ([a-z0-9]+(?:-[a-z0-9]+)*)")
# The start read's idea lines stay within this many bytes.
START_BUDGET = 8000
TLDR_CUTS = (None, 200, 140, 100)
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def metrics(idea: Idea) -> str:
    return "/".join(idea.get(k) or "unknown" for k in ("importance", "size", "fog"))


def headline(store: Store, idea: Idea, waits: dict[str, list[str]], tldr_max: int | None = None) -> str:
    """One idea as the overview lists it: slug, status, metrics, last update,
    what it waits on, and its tldr, cut at tldr_max."""
    head = "%s [%s] %s, updated %s" % (idea.slug, idea.status, metrics(idea), idea.shown_day() or "?")
    open_waits = [w for w in waits.get(idea.slug, []) if store.ideas[w].is_open]
    if open_waits:
        head += ", waits on %s" % ", ".join(open_waits)
    tldr = idea.tldr
    if tldr_max is not None and len(tldr) > tldr_max:
        tldr = tldr[:tldr_max].rsplit(" ", 1)[0] + " ..."
    return head + ": " + tldr


def family_tops(store: Store) -> list[tuple[str, str]]:
    """[(slug, note)] of the open ideas that head a family in the overview:
    no open parent above them. note names a closed or missing parent."""
    out: list[tuple[str, str]] = []
    for slug, idea in sorted(store.ideas.items()):
        if not idea.is_open:
            continue
        parent = idea.parent
        if parent and parent in store.ideas and store.ideas[parent].is_open and not store.under_loop(slug):
            continue
        note = ""
        if parent and parent in store.ideas:
            note = " (part of %s, which is %s)" % (parent, store.ideas[parent].status)
        out.append((slug, note))
    return out


def family_members(store: Store, top: str) -> list[tuple[str, int]]:
    """[(slug, depth below top)] of top and its open parts, depth first. A
    part in or under a parent loop heads its own line (family_tops), so it
    is never listed twice."""
    out: list[tuple[str, int]] = []

    def walk(slug: str, depth: int, seen: set[str]) -> None:
        out.append((slug, depth))
        for kid in store.children(slug):
            if store.ideas[kid].is_open and kid not in seen and not store.under_loop(kid):
                walk(kid, depth + 1, seen | {kid})

    walk(top, 0, {top})
    return out


def overview_head(store: Store) -> str:
    open_n = sum(1 for i in store.ideas.values() if i.is_open)
    removed = len(removed_entries(store.root))
    return "Ideas: %d open, %d closed%s. Open ideas, parts under their parent; metrics are importance/size/fog:" % (
        open_n, len(store.ideas) - open_n, (", %d removed" % removed) if removed else "")


class Block:
    """One family as the overview prints it: its lines and how many ideas
    they list."""

    def __init__(self, lines: list[str], shown: int, recent: str, withheld: int = 0) -> None:
        self.lines = lines
        self.shown = shown
        self.recent = recent
        # Parts M13 leaves out of every page: show --idea lists them.
        self.withheld = withheld

    @property
    def size(self) -> int:
        return sum(len(line.encode("utf-8")) + 1 for line in self.lines)


def family_block(store: Store, top: str, note: str, waits: dict[str, list[str]], tldr_max: int | None,
                 budget: int) -> Block:
    """The lines of one family, tldrs cut at tldr_max. A family over budget
    on its own is cut further (M13): its parts' tldrs go first, then its
    deepest parts are listed by slug only, and last its tail is left out
    behind a line naming how many parts it leaves out."""
    members = family_members(store, top)
    recent = max(store.ideas[s].shown_day() for s, _ in members)

    def line(slug: str, depth: int, limit: int | None, bare: bool) -> str:
        idea = store.ideas[slug]
        if bare:
            text = "%s [%s] %s, updated %s" % (slug, idea.status, metrics(idea), idea.shown_day() or "?")
        else:
            text = headline(store, idea, waits, limit)
        return "%s- %s%s" % ("  " * depth, text, note if depth == 0 else "")

    block = Block([line(s, d, tldr_max, False) for s, d in members], len(members), recent)
    if block.size <= budget or len(members) == 1:
        return block
    block = Block([line(s, d, tldr_max, d > 0) for s, d in members], len(members), recent)
    if block.size <= budget:
        return block
    deepest = max(d for _, d in members)
    lines: list[str] = []
    for slug, depth in members:
        if depth == deepest and depth > 0:
            if lines and lines[-1].startswith("  " * depth + "- parts by slug: "):
                lines[-1] += ", " + slug
            else:
                lines.append("  " * depth + "- parts by slug: " + slug)
        else:
            lines.append(line(slug, depth, tldr_max, depth > 0))
    block = Block(lines, len(members), recent)
    if block.size <= budget:
        return block
    kept: list[str] = []
    size = 0
    reserve = 200
    for text in lines:
        if kept and size + len(text.encode("utf-8")) + 1 > budget - reserve:
            break
        kept.append(text)
        size += len(text.encode("utf-8")) + 1
    listed = sum(1 + text.count(", ") if "parts by slug: " in text else 1 for text in kept)
    kept.append("  - %d more parts of %s are left out of this read; brainstorm show --idea %s lists the whole "
                "family." % (len(members) - listed, top, top))
    return Block(kept, listed, recent, len(members) - listed)


def overview(store: Store, page: int = 1) -> list[str]:
    """The start read: open ideas as a tree, each part under its parent,
    within START_BUDGET bytes of idea lines. Past the budget tldrs are cut to
    200, 140, then 100 characters; past that whole families are paged, the
    most recently updated first. Page 1 is never empty while an open idea
    exists."""
    waits = store.waits_on()
    tops = family_tops(store)
    open_n = sum(1 for i in store.ideas.values() if i.is_open)
    cut: int | None = None
    blocks: list[Block] = []
    for cut in TLDR_CUTS:
        blocks = [family_block(store, t, n, waits, cut, START_BUDGET) for t, n in tops]
        if sum(b.size for b in blocks) <= START_BUDGET:
            break
    pages: list[list[Block]] = [blocks]
    if sum(b.size for b in blocks) > START_BUDGET:
        order = sorted(blocks, key=lambda b: (b.recent, b.lines[0]), reverse=True)
        pages, cur, size = [], [], 0
        for block in order:
            if cur and size + block.size > START_BUDGET:
                pages.append(cur)
                cur, size = [], 0
            cur.append(block)
            size += block.size
        if cur:
            pages.append(cur)
    if page < 1 or page > len(pages):
        raise Failure("There is no page %d; the start read has %d (the last is page %d)." % (page, len(pages),
                                                                                          len(pages)),
                      "Run brainstorm start, or brainstorm start --page with a number up to %d." % len(pages))
    lines = [overview_head(store)]
    for block in pages[page - 1]:
        lines += block.lines
    if len(pages) > 1:
        shown = sum(b.shown for b in pages[page - 1])
        withheld = sum(b.withheld for p in pages for b in p)
        elsewhere = open_n - shown - withheld
        text = "Page %d of %d: %d of %d open ideas, the most recently updated families first." % (
            page, len(pages), shown, open_n)
        if elsewhere:
            text += " %d open ideas are left out of this page; brainstorm start --page %d lists the %s ones." % (
                elsewhere, page + 1 if page < len(pages) else 1, "next" if page < len(pages) else "first")
        if withheld:
            text += (" %d parts of families too big for a page are on no page; brainstorm show --idea <family> lists "
                     "them, as the family's own line says." % withheld)
        lines.append(text)
    if cut is not None:
        lines.append("Long tldrs are cut at %d characters to keep this read small; show --idea prints one whole." % cut)
    lines.append("Closed ideas are not listed: find --text <words> searches them, show --idea <slug> opens one.")
    return lines


def open_items(out: Output, idea: Idea, indent: str = "") -> None:
    """An open idea's open Next Steps and unsettled questions, quoted."""
    steps = idea.open_steps()
    questions = [(q, noted) for q, settled, noted in idea.questions() if not settled]
    for text in steps:
        out.line(indent + step_line(text))
    for q, noted in questions:
        out.line(indent + QUOTE + "? " + squash(q) + ("  (has a note)" if noted else ""))
    if not steps and not questions:
        out.line(indent + "No open Next Steps or questions.")


def removed_out(out: Output, entry: dict[str, str]) -> None:
    out.line("%s [removed %s; was %s, closed %s]: %s" % (entry["slug"], entry["removed"], entry["status"],
                                                        entry["closed"], entry["title"]))
    out.line(QUOTE + entry["gist"])


def show(store: Store, values: dict[str, Any], out: Output) -> int:
    slug = values["idea"]
    if slug not in store.ideas:
        gone = removed_entry(store.root, slug)
        if gone:
            out.line("Removed from the store by cleanup; removed.md keeps this line:")
            removed_out(out, gone)
            return out.finish("Answer the user from this line; the idea's file is gone.")
    idea = store.get(slug)
    waits = store.waits_on()
    waited = store.waited_by(slug)
    out.line("%s, file %s" % (headline(store, idea, waits), rel(store.root, idea.path)))
    out.line("Title: %s" % idea.title)
    out.line("Waits on: %s. Waited on by: %s." % (
        ", ".join("%s [%s]" % (w, store.ideas[w].status) for w in waits.get(slug, [])) or "nothing",
        ", ".join("%s [%s]" % (w, store.ideas[w].status) for w in waited) or "nothing"))
    top = store.top(slug)
    members = [top] + store.descendants(top)
    if len(members) > 1:
        out.line("Family, every level:")
        base = store.depth(top)
        for s in members:
            out.line("%s- %s [%s]%s" % ("  " * (store.depth(s) - base), s, store.ideas[s].status,
                                        "  <- this idea" if s == slug else ""))
    decision = idea.decision()
    if decision:
        out.line("Decision:")
        for line in decision.split("\n"):
            if line.strip():
                out.line(quoted(line))
    if idea.is_open:
        out.line("Open in %s:" % slug)
        open_items(out, idea)
    else:
        out.line("Reopen when: %s" % (idea.reopen_when() or "not recorded"))
    for s in store.descendants(slug):
        other = store.ideas[s]
        if other.is_open:
            out.line("Part %s [%s] %s: %s" % (s, other.status, metrics(other), other.tldr))
            open_items(out, other, "  ")
    history = idea.history()
    if history:
        out.line("History: %s" % "; ".join("%s %s" % (d, t) for d, t in history[-4:]))
    return out.finish("Answer the user from these lines; Read the file above only when you need its full prose.")


def find(store: Store, values: dict[str, Any], out: Output) -> int:
    """Every idea, open, closed or removed, whose text holds any of the
    words, with the matching lines quoted."""
    words = [w.strip() for w in values["text"] if w.strip()]
    if not words:
        raise Failure("--text is empty. Nothing was searched.", "Run the command again with the words to find.")
    pats = [re.compile(re.escape(w), re.I) for w in words]
    hits: list[tuple[int, str, Idea, list[str]]] = []
    for slug, idea in sorted(store.ideas.items()):
        lines = [idea.title, idea.tldr] + reflow(idea.text())
        found = [line for line in lines if any(p.search(line) for p in pats)]
        if found:
            hits.append((len(found), slug, idea, found))
    hits.sort(key=lambda h: (-h[0], h[1]))
    gone = [e for e in removed_entries(store.root) if e["slug"] not in store.ideas
            and any(p.search(" ".join([e["slug"], e["title"], e["gist"]])) for p in pats)]
    if not hits and not gone:
        out.line("No idea, open, closed or removed, holds %s." % " or ".join(repr(w) for w in words))
        return out.finish("Tell the user nothing in the ideas mentions it.")
    for _, slug, idea, found in hits[:FIND_MAX]:
        out.line("%s [%s%s]: %s" % (slug, idea.status, "" if idea.is_open else ", closed", idea.tldr))
        for line in found[:2]:
            line = squash(line)
            match = next((m for m in (p.search(line) for p in pats) if m), None)
            if match and len(line) > 240:
                start = max(0, match.start() - 110)
                line = ("... " if start else "") + line[start:start + 230] + " ..."
            out.line(QUOTE + line)
    if len(hits) > FIND_MAX:
        out.line("%d more ideas match; search with more specific words." % (len(hits) - FIND_MAX))
    for entry in gone[:5]:
        removed_out(out, entry)
    return out.finish("Answer the user from these lines; show --idea <slug> opens one.")


def problems(store: Store) -> list[str]:
    """The store's problems: unknown statuses, files the tool did not write,
    missing or looping parents, families too deep, relations naming no idea,
    links that do not resolve, a leftover index.md. A slug removed.md holds
    counts as known."""
    out: list[str] = []
    known = set(store.ideas) | {e["slug"] for e in removed_entries(store.root)}
    for slug, idea in sorted(store.ideas.items()):
        if idea.status not in STATUSES:
            out.append("status: %s has status %r" % (slug, idea.status))
        if idea.loaded is not None and unread_line(idea.loaded):
            out.append("file: %s %s" % (idea.loaded_name, unread_line(idea.loaded)))
        if not idea.created():
            out.append("file: %s.md has no History line 'created'; this tool did not write it" % slug)
        parent = idea.parent
        if parent and parent not in store.ideas:
            out.append("parent: %s names %s, which is no idea" % (slug, parent))
        elif parent and store.in_cycle(slug):
            out.append("parent: %s sits in a parent loop: %s" % (slug, " -> ".join([slug] + store.ancestors(slug))))
        elif parent and store.depth(slug) > DEPTH_MAX:
            out.append("parent: %s sits deeper than %d levels" % (slug, DEPTH_MAX))
        for kind, tokens, _, raw in idea.relation_items():
            named = [t for t in tokens if t in known]
            missing = [t for t in tokens if "-" in t and t not in known]
            for token in missing:
                out.append("relation: %s %s %s names no idea" % (slug, kind, token))
            if not named and not missing:
                out.append("relation: %s line '%s' names no idea" % (slug, squash(raw)[:80]))
        base = os.path.dirname(idea.path)
        for match in LINK.finditer(idea.text()):
            target = match.group(1).split("#")[0]
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target):
                continue
            if not os.path.exists(os.path.normpath(os.path.join(base, target))):
                out.append("link: %s -> %s does not resolve" % (slug, match.group(1)))
    try:
        names = os.listdir(store.dir)
    except OSError:
        names = []
    if "index.md" in names:
        out.append("file: index.md is a 0.15 index; a Brainstormer from VDD 0.15 still writes this store")
    for name in sorted(names):
        if name.endswith(".md") and name not in ("index.md", REMOVED) and not is_idea_name(name):
            out.append("file: %s is not named as an idea (<slug>.md) and is not read" % name)
    return out


def check(store: Store, values: dict[str, Any], out: Output) -> int:
    found = problems(store)
    for line in found:
        out.line(line)
    if not found:
        out.line("No problems.")
    return out.finish("Tell the user only the problems that matter to what they asked; fix none unasked.")


def parts_named(store: Store) -> list[tuple[str, str]]:
    """[(slug, parent)] of open ideas whose tldr names a parent they are not
    filed under."""
    out: list[tuple[str, str]] = []
    for slug, idea in sorted(store.ideas.items()):
        match = PART_OF.search(idea.tldr)
        if idea.is_open and match and match.group(1) in store.ideas and match.group(1) != slug \
                and idea.parent != match.group(1):
            out.append((slug, match.group(1)))
    return out
