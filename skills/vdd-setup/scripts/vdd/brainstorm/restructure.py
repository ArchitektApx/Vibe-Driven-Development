"""The writes that change a family or an idea's name: split, move, merge and
rename.

Each takes the loaded Store and the parsed options and returns (lines, Next:
step, label), as the moves in moves.py do. A family stays at most three
levels deep and has no loop: the save's guard checks the changed ideas and
everything below them.
"""

from __future__ import annotations

import os
import re
from typing import Any

from ..out import Failure
from . import printed
from .ideafile import (DEPTH_MAX, HISTORY, KIND_RE, Idea, is_open_step, lead_end, reflow,
                       section_spans, squash, today)
from .moves import new_idea, refuse_slug, tldr_warning, write_decision
from .printed import QUOTE, Result
from .store import Store

# How many prose lines that still name an old slug rename lists.
PROSE_MAX = 5


def split(store: Store, values: dict[str, Any]) -> Result:
    slug = values["idea"]
    idea = store.get(slug)
    if store.depth(slug) >= DEPTH_MAX:
        raise Failure("%s sits %d levels deep; its parts would be deeper. Nothing was written." % (slug, DEPTH_MAX),
                      "Ask the user whether to split it at the level above.")
    parts: list[list[str]] = []
    for item in values["part"]:
        bits = [b.replace("\\|", "|").strip() for b in re.split(r"(?<!\\)\|", item)]
        if len(bits) != 3 or not all(bits):
            raise Failure("--part %r is not '<slug> | <title> | <tldr>'. Nothing was written." % item,
                          "Run the command again with every part in that form.")
        if bits[0] in [p[0] for p in parts]:
            raise Failure("--part %s is given twice. Nothing was written." % bits[0],
                          "Run the command again with each part once.")
        refuse_slug(store, bits[0], "--part")
        parts.append(bits)
    day = today()
    lines: list[str] = []
    for part, title, tldr in parts:
        store.add(new_idea(store, part, title, tldr, slug, "Split out of %s on %s: %s" % (slug, day, squash(tldr)),
                           {}, [], "created under " + slug))
        idea.add_history("split into %s" % part)
        lines += tldr_warning(part, squash(tldr))
    store.touch(slug)
    lines.insert(0, "Split %s into %s; it stays their parent [%s]." % (slug, ", ".join(p[0] for p in parts),
                                                                        idea.status))
    return lines, ("Tell the user in one line, and ask whether the parent's own text should now say only what the "
                   "parts share; on a yes, Read its file and Edit that section."), "split " + slug


def strip_part_prefix(idea: Idea, parent: str) -> None:
    """Drop the 0.15 workaround "Part <n> of <parent>." from a tldr once the
    idea is filed under that parent."""
    tldr = idea.get("tldr")
    stripped = re.sub(r"^Part (?:\d+ )?of %s[.:,]?\s*" % re.escape(parent), "", tldr)
    if stripped != tldr and stripped:
        idea.set("tldr", stripped[0].upper() + stripped[1:])


def move(store: Store, values: dict[str, Any]) -> Result:
    pairs: list[tuple[str, str | None]] = []
    for item in values["set"]:
        if "=" not in item:
            raise Failure("--set %r is not <part>=<parent> or <part>=top. Nothing was written." % item,
                          "Run the command again with --set <part>=<parent>.")
        child, parent = [x.strip() for x in item.split("=", 1)]
        store.get(child)
        if parent != "top":
            store.get(parent)
        pairs.append((child, None if parent == "top" else parent))
    lines: list[str] = []
    for child, parent in pairs:
        idea = store.ideas[child]
        old = idea.parent
        if parent == old:
            lines.append("%s is already %s." % (child, ("under " + parent) if parent else "at the top level"))
            continue
        if parent and (parent == child or parent in store.descendants(child)):
            raise Failure("%s cannot go under %s, which is one of its own parts. Nothing was written."
                          % (child, parent), "Ask the user where it belongs.")
        idea.set("parent", parent or "")
        idea.add_history(("moved under %s" % parent) if parent else "moved to top level")
        store.touch(child)
        if old in store.ideas:
            assert old is not None
            store.ideas[old].add_history("part removed %s" % child)
            store.touch(old)
        if parent:
            strip_part_prefix(idea, parent)
            store.ideas[parent].add_history("part added %s" % child)
            store.touch(parent)
        lines.append("%s is now %s." % (child, ("a part of " + parent) if parent else "at the top level"))
    return lines, "Tell the user in one line what moved.", "move " + ", ".join(c for c, _ in pairs)


def merge(store: Store, values: dict[str, Any]) -> Result:
    a, b = values["idea"], values["into"]
    absorbed, survivor = store.get(a), store.get(b)
    if a == b:
        raise Failure("An idea cannot merge into itself. Nothing was written.", "Ask the user which two ideas.")
    if not absorbed.is_open:
        raise Failure("%s is already %s. Nothing was written." % (a, absorbed.status),
                      "Tell the user it is closed already; ask whether to reopen it first.")
    if not survivor.is_open:
        raise Failure("%s is %s; an idea merges only into an open one. Nothing was written." % (b, survivor.status),
                      "Ask the user whether to reopen %s first." % b)
    if b in store.descendants(a):
        raise Failure("%s is a part of %s (at some level); merging an idea into its own part would loop the family. "
                      "Nothing was written." % (b, a), "Ask the user which way round they mean.")
    kids = store.open_below(a)
    if kids:
        raise Failure(["%s has open parts: %s. An idea with open parts cannot merge, and its parts never move "
                       "with it. Nothing was written." % (a, ", ".join(kids)),
                       "Each moves with its own command, under the parent the user names or to the top level:"]
                      + ["  " + printed.command("move", set="%s=<parent>|top" % k, write=True)
                         for k in kids],
                      "Ask the user where those parts go; on their word file each with the brainstorm move above, "
                      "then run the merge again.")
    steps = absorbed.open_steps()
    if steps:
        drop_open_steps(absorbed)
    absorbed.set("status", "dropped")
    write_decision(absorbed, "dropped", "merged into %s, %s" % (b, values["reason"]), values["reopen-when"], True)
    absorbed.add_history("merged into %s" % b)
    absorbed.add_history("status dropped")
    store.touch(a)
    survivor.append("Summary", "Merged in %s on %s: %s" % (a, today(), absorbed.tldr))
    held = {squash(t) for t in survivor.open_steps()}
    moved = [t for t in steps if squash(t) not in held]
    for text in moved:
        survivor.append("Next Steps", "%s (from %s)" % (squash(text), a), item="- [ ] ")
    survivor.add_history("merged from %s" % a)
    store.touch(b)
    parent = absorbed.parent
    if parent in store.ideas and parent != b:
        assert parent is not None
        store.ideas[parent].add_history("part %s dropped" % a)
        store.touch(parent)
    lines = ["%s is merged into %s and dropped; %d open step%s moved over." % (
        a, b, len(moved), "" if len(moved) == 1 else "s")]
    closed = [k for k in store.children(a)]
    if closed:
        lines.append("Its closed parts stay under %s: %s." % (a, ", ".join(closed)))
    return lines, "Tell the user in one line.", "merge %s into %s" % (a, b)


def drop_open_steps(idea: Idea) -> None:
    """Remove the open Next Steps, continuation lines included, so a merged
    idea's steps live in the survivor only."""
    out: list[str] = []
    skipping = False
    for line in idea.section("Next Steps").split("\n"):
        if line.startswith("- "):
            skipping = is_open_step(line)
        elif not (skipping and line.strip() and line[:1] in (" ", "\t")):
            skipping = False
        if not skipping:
            out.append(line)
    idea.replace_section("Next Steps", "\n".join(out).strip("\n") or "None.")


def rewrite_span(text: str, a: str, b: str) -> str:
    """A code span that is exactly slug a, as slug b."""
    return text.replace("`%s`" % a, "`%s`" % b)


def rewrite_refs(text: str, a: str, b: str) -> str:
    """Rewrite the references to slug a that rename owns, never prose: link
    targets to a's file (with ./ and an #anchor), paths into research/a/, and
    code spans that are exactly the slug."""
    text = re.sub(r"\]\((\./)?%s\.md(#[^)\s]*)?\)" % re.escape(a),
                  lambda m: "](%s%s.md%s)" % (m.group(1) or "", b, m.group(2) or ""), text)
    text = re.sub(r"(?<![A-Za-z0-9_-])research/%s(?=/|\)|`|\s|$)" % re.escape(a), "research/" + b, text)
    return rewrite_span(text, a, b)


def rewrite_relations(idea: Idea, a: str, b: str) -> None:
    """Rewrite slug a in the lead of every ## Related Ideas line, before its
    first colon outside brackets, never in its reason."""
    section = idea.section("Related Ideas")
    if not section:
        return
    word = re.compile(r"(?<![a-z0-9-])%s(?![a-z0-9-])" % re.escape(a))
    out: list[str] = []
    for line in section.split("\n"):
        match = KIND_RE.match(line[2:]) if line.startswith("- ") else None
        if match:
            rest = line[2:]
            end = lead_end(rest, match.start(2))
            line = "- " + word.sub(b, rest[:end]) + rest[end:]
        out.append(line)
    if out != section.split("\n"):
        idea.replace_section("Related Ideas", "\n".join(out))


def rewrite_idea(idea: Idea, a: str, b: str) -> None:
    """Every structural reference to a in one idea, History left as written."""
    spans = [s for s in section_spans(idea.body) if s[0] == HISTORY]
    head, history = (idea.body[:spans[0][1]], idea.body[spans[0][1]:]) if spans else (idea.body, "")
    idea.body = rewrite_refs(head, a, b) + history
    rewrite_relations(idea, a, b)
    tldr = idea.get("tldr")
    if rewrite_span(tldr, a, b) != tldr:
        idea.set("tldr", rewrite_span(tldr, a, b))
    if idea.parent == a:
        idea.set("parent", b)


def rename(store: Store, values: dict[str, Any]) -> Result:
    a, b = values["idea"], values["to"]
    idea = store.get(a)
    refuse_slug(store, b, "--to")
    research_old = os.path.join(store.dir, "research", a)
    if os.path.exists(os.path.join(store.dir, "research", b)):
        raise Failure("research/%s/ exists already. Nothing was written." % b, "Ask the user for another name.")
    rewritten: list[str] = []
    for slug, other in sorted(store.ideas.items()):
        before = (other.body, [list(p) for p in other.fm])
        rewrite_idea(other, a, b)
        if (other.body, other.fm) != before:
            store.dirty.add(slug)
            if slug != a:
                rewritten.append(slug)
    idea.add_history("renamed from %s" % a)
    store.touch(a)
    store.ideas[b] = store.ideas.pop(a)
    idea.slug, idea.path = b, store.path(b)
    store.dirty.discard(a)
    store.dirty.add(b)
    store.deleted.add(a)
    has_research = os.path.isdir(research_old)
    if has_research:
        store.dir_moves.append(("research/" + a, "research/" + b))
    word = re.compile(r"(?<![a-z0-9-])%s(?![a-z0-9-])" % re.escape(a))
    prose = list(dict.fromkeys(
        (slug, squash(line)) for slug, other in sorted(store.ideas.items())
        for line in [other.tldr] + reflow(other.text()) if word.search(line)))
    lines = ["Renamed %s to %s%s; relation lines, parent fields and links in %d other idea%s now name %s." % (
        a, b, ", with research/%s/" % b if has_research else "", len(rewritten),
        "" if len(rewritten) == 1 else "s", b)]
    nxt = "Tell the user in one line."
    if prose:
        count = len(prose)
        lines.append("Prose that still names %s, left as written (%d line%s):" % (a, count, "" if count == 1 else "s"))
        for slug, line in prose[:PROSE_MAX]:
            lines.append("%s: %s" % (slug, QUOTE + (line if len(line) <= 200 else line[:200] + " ...")))
        nxt = ("Tell the user in one line, quote the %d line%s of prose that still name%s %s, and ask whether to "
               "change them; on a yes, Read each idea file and Edit those lines." % (
                   count, "" if count == 1 else "s", "s" if count == 1 else "", a))
    return lines, nxt, "rename %s to %s" % (a, b)
