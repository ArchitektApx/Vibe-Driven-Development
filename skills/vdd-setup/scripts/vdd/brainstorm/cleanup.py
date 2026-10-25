"""brainstorm cleanup: removing closed ideas from the store, selectively,
each kept as one line in removed.md.

It never removes every closed idea at once, an open idea, a closed idea with
an open part, a closed idea an open idea waits on, or a part whose family
stays. Research folders stay.
"""

from __future__ import annotations

import datetime
import os
import re
from typing import Any

from .. import textfile
from ..out import Failure
from .ideafile import CLOSED, Idea, squash, today
from .moves import norm_value
from .printed import Result
from .removed import REMOVED, REMOVED_HEAD, removed_line
from .store import Store


def gist(idea: Idea) -> str:
    """The Decision in one line: its closing paragraph, then Reopen when."""
    paras = [p for p in re.split(r"\n\s*\n", idea.decision()) if p.strip()]
    pick = [p for p in paras if re.match(r"^(Done|Dropped)\b", p.strip())]
    text = (pick or paras or ["no Decision recorded"])[-1]
    text = squash(re.sub(r"Reopen when:.*", "", text, flags=re.S))
    if len(text) > 200:
        text = text[:200].rsplit(" ", 1)[0] + " ..."
    reopen = idea.reopen_when()
    return text + ((" Reopen when: " + reopen) if reopen else "")


def older_days(value: str | None) -> int | None:
    """--older as days, None when not given. An empty value is refused, never
    read as any age, so a missing age cannot remove every closed idea."""
    if value is None:
        return None
    if not value.strip():
        raise Failure("--older is empty; it takes <N>d or <N>w (days or weeks since the idea closed). An empty value "
                      "is never read as 'any age'. Nothing was written.",
                      "If the user gave no age, ask them for one, then run again; leave --older out only when they "
                      "want every age.")
    match = re.match(r"^\s*(\d+)\s*([dw])\s*$", value.lower())
    if not match:
        raise Failure("--older %s is not <N>d or <N>w (days or weeks since the idea closed). Nothing was written."
                      % value, "If the user gave no age, ask them for one, then run again.")
    return int(match.group(1)) * (7 if match.group(2) == "w" else 1)


def age_of(closed: str) -> int | None:
    """Days since closed, None for a date that does not exist,
    such as February 30, which would otherwise end the command with a
    traceback."""
    try:
        return (datetime.date.fromisoformat(today()) - datetime.date.fromisoformat(closed)).days
    except ValueError:
        return None


def closed_to_remove(store: Store, statuses: list[str], named: list[str],
               days: int | None) -> tuple[list[str], list[tuple[str, str]]]:
    """(picked, kept with the reason) before the family checks."""
    kept: list[tuple[str, str]] = []
    if named:
        cands = [s for s in named if not statuses or store.ideas[s].status in statuses]
        kept += [(s, "it is %s, not %s" % (store.ideas[s].status, " or ".join(statuses))) for s in named
                 if s not in cands]
    else:
        cands = [s for s, i in sorted(store.ideas.items()) if i.status in statuses]
    picked: list[str] = []
    for s in cands:
        idea = store.ideas[s]
        if idea.is_open:
            kept.append((s, "it is open (%s)" % idea.status))
            continue
        if days is not None:
            closed = idea.closed_on()
            if not closed:
                kept.append((s, "its History has no line for when it closed"))
                continue
            age = age_of(closed)
            if age is None:
                kept.append((s, "its History line for when it closed has no real date (%s)" % closed))
                continue
            if age < days:
                continue
        picked.append(s)
    return picked, kept


def family_checks(store: Store, picked: list[str]) -> list[tuple[str, str]]:
    """Take out of picked, with the reason, every idea with an open part, an
    open idea waiting on it, or a part that stays; until none is left."""
    kept: list[tuple[str, str]] = []
    waits = store.waits_on()
    changed = True
    while changed:
        changed = False
        for s in list(picked):
            open_parts = store.open_below(s)
            waiting = sorted(w for w, on in waits.items() if s in on and store.ideas[w].is_open)
            staying = [k for k in store.children(s) if k not in picked]
            reason = None
            if open_parts:
                reason = "its part %s is open" % ", ".join(open_parts)
            elif waiting:
                reason = "the open idea %s waits on it" % ", ".join(waiting)
            elif staying:
                reason = "its part %s stays in the store; remove them together" % ", ".join(staying)
            if reason:
                picked.remove(s)
                kept.append((s, reason))
                changed = True
    return kept


def cleanup(store: Store, values: dict[str, Any]) -> Result:
    if not values["status"] and not values["idea"]:
        raise Failure("cleanup needs --status done, --status dropped or --idea <slug>: it never removes every closed "
                      "idea at once. Nothing was written.",
                      "Ask the user which closed ideas to remove: done, dropped, or named ones, and how old.")
    statuses = [norm_value(s, CLOSED, "status") for s in values["status"]]
    days = older_days(values["older"])
    for s in values["idea"]:
        store.get(s)
    named = list(dict.fromkeys(values["idea"]))
    picked, kept = closed_to_remove(store, statuses, named, days)
    kept += family_checks(store, picked)
    refused = [(s, r) for s, r in kept if s in named]
    if refused:
        raise Failure(["Refused, nothing was written:"] + ["%s: %s." % (s, r) for s, r in refused],
                      "Tell the user which idea cannot be removed and why, in one line each.")
    lines: list[str] = []
    if not picked:
        lines.append("Nothing to remove: no closed idea matches%s."
                     % (" that closed %d days ago or more" % days if days is not None else ""))
    else:
        lines.append("%s %d idea%s from the store, each with one line in .scratch/_brainstorming/%s:" % (
            "Removed" if values["write"] else "Would remove", len(picked), "" if len(picked) == 1 else "s", REMOVED))
    path = os.path.join(store.dir, REMOVED)
    record = textfile.read(path) or REMOVED_HEAD
    if not record.endswith("\n"):
        record += "\n"
    for s in picked:
        idea = store.ideas[s]
        closed = idea.closed_on()
        lines.append("- %s [%s, closed %s]: %s" % (s, idea.status, closed or "unknown", idea.title))
        record += removed_line(idea, closed, gist(idea))
        store.deleted.add(s)
    for s, reason in kept:
        lines.append("Kept %s: %s." % (s, reason))
    research = [s for s in picked if os.path.isdir(os.path.join(store.dir, "research", s))]
    if research:
        lines.append("Their research folders stay: %s." % ", ".join("research/%s/" % s for s in research))
    if picked:
        store.extra[REMOVED] = record.encode("utf-8")
        store.dry_next = ("Tell the user what this would remove and keep, in a line or two; if it is what they asked "
                          "for, run the same command again with --write.")
    return lines, ("Tell the user in one line how many ideas were removed and that removed.md keeps a line for each"
                   "%s." % (", and that their research folders stay" if research else "")), \
        "cleanup " + ", ".join(picked)
