"""Setup's first check: the Borrowed skills, worded from borrowed.Verdict."""

from __future__ import annotations

from .. import stores
from ..harness import Harness
from . import borrowed
from .report import Report


def check(report: Report, harness: Harness, cwd: str, listed: str, glossary_named: str,
          user_answer: str | None) -> None:
    out = report.out
    hits = stores.search(harness.present_roots(cwd), borrowed.SKILLS)
    verdict = borrowed.Verdict(hits, borrowed.parse_listed(listed), glossary_named, user_answer)

    if verdict.ask_user:
        report.user_answer_needed = True
        out.line(
            "Borrowed skills: %d of %d Present in the stores this Harness reads, and your skill list "
            "shows none of the collection. Whether this Session can run them needs the user's answer."
            % (len(verdict.present), len(borrowed.SKILLS))
        )
        return

    if len(verdict.passed) == len(borrowed.SKILLS):
        out.line("Borrowed skills: all %d Present and Resolvable. Passed." % len(borrowed.SKILLS))
    elif verdict.passed:
        out.line("Borrowed skills Present and Resolvable, passed: %s." % ", ".join(verdict.passed))

    if verdict.no_hit:
        text = "%s: Resolvable from a store Setup does not search. Passed." % ", ".join(verdict.no_hit)
        if harness.no_hit_continuation():
            text += " " + harness.no_hit_continuation()
        out.tell(text)

    if verdict.not_loaded:
        for store, skills in verdict.stores_of(verdict.not_loaded, cwd):
            out.line(
                "Borrowed skills Present but not Resolvable, under %s: %s."
                % (store.label, ", ".join(skills))
            )
            if len(skills) == len(borrowed.SKILLS):
                what = "collection sits"
            elif len(skills) == 1:
                what = skills[0] + " sits"
            else:
                what = ", ".join(skills) + " sit"
            out.tell(
                "Matt Pocock's %s in %s, which %s reads, and this Session has not loaded %s."
                % (what, store.label, harness.display_name, "it" if len(skills) == 1 else "them")
            )
            for line in harness.route_present_not_resolvable(store):
                out.tell(line)

    if verdict.old_collection:
        store = verdict.store_of(borrowed.SKILLS, cwd)
        out.line("Borrowed skills: a collection from before the glossary rename (a warning, not a block).")
        out.tell(
            "Warning: your copy of Matt Pocock's collection is from before its glossary rename, too old "
            "for VDD's Roles. It does not block Setup."
            + (" It sits in %s." % store.label if store else "")
        )
        for line in harness.route_old_collection(store) or ["Update it where you installed it."]:
            out.tell(line)

    if verdict.missing:
        out.line("Borrowed skills Not Present: %s." % ", ".join(verdict.missing))
        if not verdict.old_collection:
            for line in harness.route_not_present():
                out.tell(line)

    for line in borrowed.cost_lines(set(verdict.not_loaded) | set(verdict.missing)):
        out.tell(line)
