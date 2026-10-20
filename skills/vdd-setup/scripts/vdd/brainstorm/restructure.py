"""The writes that change a family or an idea's name: split, move, merge and
rename.

Each takes the loaded Store and the parsed options and returns (lines, Next:
step, label), as the moves in moves.py do. A family stays at most three
levels deep and has no loop: the save's guard checks the changed ideas and
everything below them.
"""

from __future__ import annotations

import re
from typing import Any

from ..out import Failure
from .ideafile import DEPTH_MAX, Idea, lead_tokens, relation_lead, squash, today
from .moves import FIRST_STEP, Result, refuse_slug, tldr_warning, write_decision
from .store import Store


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
        fields = [("tldr", squash(tldr)), ("status", "idea"), ("parent", slug), ("importance", "unknown"),
                  ("size", "unknown"), ("fog", "unknown"), ("last-updated", day)]
        body = ["", "# %s" % squash(title), "", "## Summary", "", "Split out of %s on %s: %s" % (slug, day, squash(tldr)),
                "", "## Next Steps", "", "- [ ] " + FIRST_STEP, "", "## History", "",
                "- %s: created under %s" % (day, slug), ""]
        store.add(Idea.frame(part, store.path(part), fields, body))
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
    probs = store.structure_problems({c for c, _ in pairs})
    if probs:
        raise Failure(["Refused, nothing was written: the move would break the family tree."] + probs,
                      "Ask the user where else it belongs.")
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
                      + ["  brainstorm move --set %s=<parent>|top --write" % k for k in kids],
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
