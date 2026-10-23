"""The writes on single ideas: new, note and set.

Each takes the loaded Store and the parsed options, changes ideas in memory,
and returns (lines, Next: step, label); the group saves the Store, or prints a
dry run. A refusal raises Failure before anything is saved.
"""

from __future__ import annotations

import re
from typing import Any

from ..out import Failure
from . import dupes
from .ideafile import (CLOSED, DEPTH_MAX, HISTORY, KIND_RE, KINDS, METRICS, ORDER, RESERVED, SLUG_PATTERN,
                       STATUSES, TLDR_MAX, Idea, is_open_step, squash, today, usable_slug)
from .printed import Result, quoted, step_line
from .store import Store, rel, removed_entry, unknown_lines

LIST_SECTIONS = ("Pro", "Con", "Open Questions", "Evidence", "Related Ideas", "Next Steps", "Prior Art")
FIRST_STEP = "Talk it through with the user."
WORD = {"done": "Done", "dropped": "Dropped", "decided": "Decided", "shaped": "Shaped", "discussed": "Discussed",
        "in-progress": "In progress", "idea": "Reopened"}


def norm_value(value: str | None, allowed: tuple[str, ...], name: str) -> str:
    """value as one of allowed, "in progress" read as in-progress; a
    Failure naming the values otherwise."""
    v = "-".join((value or "").strip().lower().split())
    if v == "inprogress":
        v = "in-progress"
    if v not in allowed:
        raise Failure("--%s %s is not one of: %s. Nothing was written." % (name, value, ", ".join(allowed)),
                      "Run the command again with one of those values.")
    return v


def metrics_of(values: dict[str, Any], default: str | None) -> dict[str, str]:
    """importance, size and fog from the options, each checked; default for
    one not given, or left out when default is None."""
    out: dict[str, str] = {}
    for key in ("importance", "size", "fog"):
        if values[key]:
            out[key] = norm_value(values[key], METRICS, key)
        elif default is not None:
            out[key] = default
    return out


def refuse_slug(store: Store, slug: str | None, option: str) -> None:
    """Refuse a slug that is not kebab-case, is reserved, names an idea, or
    names one cleanup removed (M5): relation lines and research of the
    removed idea still name it, and would attach to the new one."""
    if not usable_slug(slug):
        raise Failure("%s %s is not a usable idea slug: a slug matches %s and is not %s. Nothing was written."
                      % (option, slug, SLUG_PATTERN, " or ".join(RESERVED)),
                      "Run the command again with another kebab-case slug.")
    assert slug is not None
    if slug in store.ideas:
        raise Failure("%s %s is taken: an idea named %s exists (%s). Nothing was written."
                      % (option, slug, slug, store.ideas[slug].status),
                      "Run brainstorm show --idea %s, or pick another slug." % slug)
    gone = removed_entry(store.root, slug)
    if gone:
        raise Failure("%s named an idea cleanup removed on %s (removed.md keeps its line); other ideas and "
                      "research/%s/ may still name it. Nothing was written." % (slug, gone["removed"], slug),
                      "Run the command again with another slug; if the user meant the removed idea, tell them it "
                      "was removed and what its line in removed.md says.")


def relation_line(store: Store, slug: str, text: str) -> str:
    """A --relate value as the line it becomes: '<kind> <slug>: <why>'."""
    match = KIND_RE.match(squash(text))
    if not match:
        raise Failure("--relate %r does not start with one of: %s. Nothing was written." % (text, ", ".join(KINDS)),
                      "Run the command again with '<kind> <slug>: <why>'.")
    kind, rest = match.group(1).lower(), match.group(2)
    target, _, reason = rest.partition(":")
    target = target.strip()
    if target not in store.ideas or target == slug:
        raise Failure(["--relate %r names no other idea. Nothing was written." % text]
                      + unknown_lines(target, sorted(store.ideas))[1:],
                      "Run the command again with the slug of an existing idea.")
    return "%s %s%s" % (kind, target, (": " + reason.strip()) if reason.strip() else "")


def tldr_warning(slug: str, tldr: str) -> list[str]:
    if len(tldr) > TLDR_MAX:
        return ["The tldr of %s is %d characters; the start read shows every tldr, so offer the user a shorter one "
                "(under %d) with set --tldr." % (slug, len(tldr), TLDR_MAX)]
    return []


def check_parent(store: Store, parent: str) -> None:
    store.get(parent)
    if store.depth(parent) >= DEPTH_MAX:
        raise Failure("%s already sits %d levels deep; a part under it would be the %dth. Nothing was written."
                      % (parent, DEPTH_MAX, DEPTH_MAX + 1), "Ask the user where else the idea belongs.")


def new_idea(store: Store, slug: str, title: str, tldr: str, parent: str | None, summary: str,
             metrics: dict[str, str], relates: list[str], created: str) -> Idea:
    """A new idea's frame: frontmatter, H1, Summary, Related Ideas, a first
    Next Step and the created History line."""
    day = today()
    fields = [("tldr", squash(tldr)), ("status", "idea"), ("parent", parent or ""),
              ("importance", metrics.get("importance", "unknown")), ("size", metrics.get("size", "unknown")),
              ("fog", metrics.get("fog", "unknown")), ("last-updated", day)]
    body = ["", "# %s" % squash(title), "", "## Summary", "", summary.strip()]
    if relates:
        body += ["", "## Related Ideas", ""] + ["- " + r for r in relates]
    body += ["", "## Next Steps", "", "- [ ] " + FIRST_STEP, "", "## " + HISTORY, ""]
    body += ["- %s: %s" % (day, created), ""]
    return Idea.frame(slug, store.path(slug), fields, body)


def new(store: Store, values: dict[str, Any]) -> Result:
    slug, parent = values["slug"], values["parent"]
    refuse_slug(store, slug, "--slug")
    if parent:
        check_parent(store, parent)
    metrics = metrics_of(values, "unknown")
    relates = [relation_line(store, slug, r) for r in values["relate"]]
    hits = dupes.similar(store, " ".join([slug.replace("-", " "), values["title"], values["tldr"],
                                          values["summary"] or ""]),
                         exclude=list(values["despite"]) + ([parent] if parent else []))
    looks = match_lines(store, hits[:3])
    idea = new_idea(store, slug, values["title"], values["tldr"], parent, values["summary"] or values["tldr"],
                    metrics, relates, "created" + ((" under " + parent) if parent else ""))
    store.add(idea)
    if parent:
        store.ideas[parent].add_history("part added %s" % slug)
        store.touch(parent)
    lines = ["Captured %s [idea]%s, file %s." % (slug, (" as a part of " + parent) if parent else "",
                                                 rel(store.root, idea.path))]
    lines += tldr_warning(slug, idea.tldr)
    nxt = "Tell the user in one line what you captured and where it sits, then carry on with them."
    if not values["write"]:
        if looks:
            store.dry_next = (
                "Before capturing, tell the user which ideas above theirs looks like (a closed one with its Reopen "
                "when) and ask whether it is one of them. If it is a new idea, run the same command again with "
                "--write; if it is one of them, work the new thought into that idea instead (note, or set --status "
                "idea to reopen a closed one).")
        else:
            looks = ["No idea in the store, open, closed or removed, looks like this one."]
    elif looks:
        nxt = ("Tell the user in one line what you captured. If you have not asked them yet whether it is one of the "
               "ideas it looks like, ask now; if it is, offer to merge it into that idea.")
    return lines + looks, nxt, "new " + slug


def match_lines(store: Store, hits: list[dupes.Match]) -> list[str]:
    """The likely matches of a new idea, each with its status, tldr or
    removed line, the words it shares, and a closed one's Reopen when."""
    if not hits:
        return []
    lines = ["It looks like %s (shared words in the slug and title, tldr or Reopen when):"
             % ("this idea" if len(hits) == 1 else "these ideas")]
    for hit in hits:
        shared = ", ".join(hit.shared)
        if hit.where == "removed":
            entry = removed_entry(store.root, hit.slug) or {}
            lines.append("%s [removed %s, was %s]: %s (shared: %s)" % (hit.slug, entry.get("removed", "?"),
                                                                       entry.get("status", "?"),
                                                                       entry.get("title", ""), shared))
            lines.append(quoted(entry.get("gist", "")))
            continue
        idea = store.ideas[hit.slug]
        lines.append("%s [%s, %s]: %s (shared: %s)" % (hit.slug, idea.status, idea.get("last-updated"), idea.tldr,
                                                       shared))
        if not idea.is_open:
            lines.append(quoted("Reopen when: " + (idea.reopen_when() or "not recorded")))
    return lines


def section_name(idea: Idea, name: str) -> str:
    want = squash(name).lower()
    for known in list(ORDER) + idea.section_names():
        if known.lower() == want:
            return known
    return squash(name).title()


def note(store: Store, values: dict[str, Any]) -> Result:
    idea = store.get(values["idea"])
    if not values["tick"] and not values["section"]:
        raise Failure("note needs --section with --text, or --tick. Nothing was written.",
                      "Run the command again with --section <name> --text <text>, or --tick <start of a step>.")
    if values["section"] and not [t for t in values["text"] if t.strip()]:
        raise Failure("--section needs --text. Nothing was written.",
                      "Run the command again with --text <text> for what to add.")
    if values["text"] and not values["section"]:
        raise Failure("--text needs --section. Nothing was written.",
                      "Run the command again with --section <name> for where the text goes.")
    lines: list[str] = []
    if values["tick"]:
        lines.append(tick(idea, values["tick"]))
    if values["section"]:
        name = section_name(idea, values["section"])
        if name in (HISTORY, "Decision"):
            raise Failure("The tool writes %s itself. Nothing was written." % name,
                          "For a decision use brainstorm set --decision; History needs nothing from you.")
        texts = [t for t in values["text"] if t.strip()]
        if name == "Related Ideas":
            texts = [relation_line(store, idea.slug, t) for t in texts]
        for text in texts:
            if name == "Next Steps":
                idea.append(name, text, item="- [ ] ")
            elif name == "Evidence":
                dated = text if re.match(r"^\d{4}-\d{2}-\d{2}", text.strip()) else "%s: %s" % (today(), text.strip())
                idea.append(name, dated, item="- ")
            elif name in LIST_SECTIONS:
                idea.append(name, text, item="- ")
            else:
                idea.append(name, text)
        lines.append("Added to %s of %s." % (name, idea.slug))
    store.touch(idea.slug)
    return lines, "Tell the user in one line where it is recorded, then carry on.", "note " + idea.slug


def tick(idea: Idea, start: str) -> str:
    """Tick the one open Next Step whose text starts with start."""
    want = squash(start).lower()
    steps = idea.open_steps()
    match = [t for t in steps if squash(t).lower().startswith(want)]
    if len(match) != 1:
        raise Failure(["%s open Next Steps of %s start with %r. Nothing was written."
                       % ("No" if not match else "Several", idea.slug, start)] + [step_line(t) for t in steps],
                      "Run the command again with --tick set to the start of one step above.")
    index = steps.index(match[0])
    out: list[str] = []
    seen = 0
    for line in idea.section("Next Steps").split("\n"):
        if is_open_step(line):
            if seen == index:
                line = "- " + line[2:].replace("[ ]", "[x]", 1)
            seen += 1
        out.append(line)
    idea.replace_section("Next Steps", "\n".join(out))
    return "Ticked in %s: %s" % (idea.slug, squash(match[0])[:120])


def write_decision(idea: Idea, status: str, text: str | None, reopen: str | None, was_open: bool) -> None:
    """Add the Decision paragraph of a status change: "<Word> <date>: text",
    then "Reopen when: ..."."""
    if not text and not reopen:
        return
    if status in CLOSED or was_open:
        word = WORD.get(status, status.title())
    else:
        word = "Reopened" if status == "idea" else "Reopened as %s" % status
    para = "%s %s%s" % (word, today(), (": " + squash(text)) if text else ".")
    if reopen:
        para += "\nReopen when: %s" % squash(reopen)
    cur = idea.decision()
    if cur.startswith("<") or cur in ("None.", "None", ""):
        idea.replace_section("Decision", para)
    else:
        idea.append("Decision", para)


def stale_naming(store: Store, slug: str) -> list[str]:
    """Open ideas that name slug (a relation either way, or the family) and
    were last updated before today: what a landing may have made stale."""
    near: set[str] = set()
    for frm, _, to, _ in store.relations():
        if slug in (frm, to):
            near.add(to if frm == slug else frm)
    parent = store.ideas[slug].parent
    if parent in store.ideas:
        near.add(parent)
    near.update(store.children(slug))
    day = today()
    return sorted(s for s in near if s in store.ideas and store.ideas[s].is_open
                  and (store.ideas[s].get("last-updated") or "") < day)


def set_cmd(store: Store, values: dict[str, Any]) -> Result:
    slugs: list[str] = []
    for s in values["idea"]:
        store.get(s)
        if s not in slugs:
            slugs.append(s)
    status = norm_value(values["status"], STATUSES, "status") if values["status"] else None
    fields = metrics_of(values, None)
    if not (status or fields or values["decision"] or values["reopen-when"] or values["tldr"] or values["title"]):
        raise Failure("set needs something to set: --status, --decision, --reopen-when, --importance, --size, "
                      "--fog, --tldr or --title. Nothing was written.", "Run the command again with what changes.")
    if status in ("done", "dropped", "decided") and not values["decision"]:
        raise Failure("--status %s needs --decision: the reason, the PR or the commit. Nothing was written." % status,
                      "Run the command again with --decision.")
    if status == "dropped" and not values["reopen-when"]:
        raise Failure("--status dropped needs --reopen-when. Nothing was written.",
                      "Ask the user when it should come back if they did not say, then run again with --reopen-when.")
    lines: list[str] = []
    changed: list[tuple[str, str, str]] = []
    for slug in slugs:
        idea = store.ideas[slug]
        was = idea.status
        if status == was and not fields and not values["tldr"] and not values["title"]:
            # A repeated status writes nothing (U14), whatever else it carries.
            lines.append("%s is %s already; nothing changed." % (slug, was))
            continue
        for key, val in fields.items():
            idea.set(key, val)
        if values["tldr"]:
            idea.set("tldr", squash(values["tldr"]))
            lines += tldr_warning(slug, idea.tldr)
        if values["title"]:
            idea.set_title(values["title"])
        if status and status != was:
            changed += [(m, w, status) for m, w in change_status(store, slugs, slug, status, values)]
        else:
            if status == was and was in CLOSED and (values["decision"] or values["reopen-when"]):
                # A repeated close with another field: the idea closed once,
                # so its Decision gets no second paragraph (M15).
                lines.append("%s is %s already; its Decision stays as written." % (slug, was))
            elif values["decision"] or values["reopen-when"]:
                write_decision(idea, idea.status, values["decision"], values["reopen-when"], True)
            store.touch(slug)
            changed.append((slug, was, idea.status))
    lines += change_lines(store, slugs, changed, fields, status)
    nxt = "Tell the user in a line or two what changed."
    if status == "decided":
        nxt = ("Tell the user it is decided, and give them the line to start the Role they chose in a fresh Session: "
               "vdd-start-loop for one loop or vdd-wayfinder for more, as their Harness types it, with the path "
               "above as what to plan.")
    return lines, nxt, "set " + ", ".join(slugs)


def change_status(store: Store, slugs: list[str], slug: str, status: str,
                  values: dict[str, Any]) -> list[tuple[str, str]]:
    """Give slug the new status; a drop takes its open parts at every level
    with it. The parent's History records a part's close or reopen, unless
    the parent is in the same command. Returns [(member, status it had)]."""
    idea = store.ideas[slug]
    was = idea.status
    family = [slug]
    if status == "dropped":
        family += [d for d in store.open_below(slug) if d not in slugs]
    done: list[tuple[str, str]] = []
    for member in family:
        m = store.ideas[member]
        m_was = m.status
        m.set("status", status)
        text = values["decision"] if member == slug else "with %s: %s" % (slug, values["decision"])
        write_decision(m, status, text, values["reopen-when"], m_was not in CLOSED)
        m.add_history("status %s" % status)
        store.touch(member)
        done.append((member, m_was))
    parent = idea.parent
    if parent in store.ideas and parent not in slugs:
        assert parent is not None
        if status in CLOSED and was not in CLOSED:
            store.ideas[parent].add_history("part %s %s" % (slug, status))
            store.touch(parent)
        elif status not in CLOSED and was in CLOSED:
            store.ideas[parent].add_history("part %s reopened" % slug)
            store.touch(parent)
    return done


def change_lines(store: Store, slugs: list[str], changed: list[tuple[str, str, str]], fields: dict[str, str],
                 status: str | None) -> list[str]:
    """What set prints beside the change: for a close, the kept open steps,
    the parts still open, the parent's open parts, the ideas that waited on
    it, and for done the open ideas a landing may have made stale; for
    decided the idea file's path."""
    lines: list[str] = []
    extra = "" if not fields else ", " + ", ".join("%s %s" % kv for kv in sorted(fields.items()))
    for slug, was, now in changed:
        lines.append("%s: %s%s." % (slug, ("%s -> %s" % (was, now)) if was != now else now, extra))
    waits = store.waits_on()
    changed_slugs = [c[0] for c in changed]
    for slug, was, now in changed:
        if now in CLOSED and was not in CLOSED:
            waiting = sorted(s for s, on in waits.items() if slug in on and store.ideas[s].is_open)
            if waiting:
                lines.append("Open ideas that waited on %s: %s." % (slug, ", ".join(waiting)))
    for slug in slugs:
        idea = store.ideas[slug]
        if idea.status in CLOSED and slug in changed_slugs:
            kept = idea.open_steps() if idea.status == "done" else []
            if kept:
                lines.append("Open Next Steps kept in %s (ask the user whether they are done):" % slug)
                lines += [step_line(t) for t in kept]
            open_kids = store.open_below(slug)
            if open_kids:
                lines.append("Parts of %s still open: %s." % (slug, ", ".join(open_kids)))
            parent = idea.parent
            if parent in store.ideas and store.ideas[parent].is_open:
                assert parent is not None
                left = [k for k in store.children(parent) if store.ideas[k].is_open]
                lines.append("Its parent %s [%s] has %s." % (parent, store.ideas[parent].status,
                                                              ("open parts left: " + ", ".join(left)) if left
                                                              else "no open parts left"))
            if idea.status == "done":
                stale = [s for s in stale_naming(store, slug) if s not in changed_slugs]
                if stale:
                    lines.append("Open ideas that name %s and were last updated before today (check whether this "
                                 "landing changes them): %s." % (slug, ", ".join(
                                     "%s (%s)" % (s, store.ideas[s].get("last-updated")) for s in stale)))
        if idea.status == "decided" and status == "decided":
            lines.append("Decided idea for the next Role: %s" % rel(store.root, idea.path))
    return lines
