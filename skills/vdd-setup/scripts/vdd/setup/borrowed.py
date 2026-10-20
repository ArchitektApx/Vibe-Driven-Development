"""The Borrowed skills: Present, Resolvable, and what a failure costs.

Present: the search found the skill in a store this Harness reads.
Resolvable: this Session can run it, which only the model's own skill list
shows; the model passes what it found there, and the user's answer when the
list cannot tell.
"""

from __future__ import annotations

from typing import Iterable

from .. import stores

# The 11 skills from Matt Pocock's collection the Roles depend on.
SKILLS: tuple[str, ...] = (
    "setup-matt-pocock-skills",
    "grill-with-docs",
    "to-spec",
    "to-tickets",
    "wayfinder",
    "code-review",
    "writing-for-agents",
    "grilling",
    "domain-modeling",
    "research",
    "prototype",
)

WRITING = "writing-for-agents"

# Agent-invocable skills of the collection whose hit in the model's skill
# list proves the collection is wired, after writing-for-agents misses.
SIBLINGS: tuple[str, ...] = (
    "grilling",
    "codebase-design",
    "domain-modeling",
    "tdd",
    "research",
    "prototype",
    "diagnosing-bugs",
    "code-review",
)

# What a missing or unresolvable skill costs each Role.
COSTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("grill-with-docs", "to-spec", "to-tickets"), "blocks the Planner."),
    (("domain-modeling",), "blocks the Planner and the Wayfinder, because grill-with-docs and wayfinder call it."),
    (
        ("grilling",),
        "blocks the Planner and the Wayfinder, because grill-with-docs and wayfinder call it, and the "
        "Brainstormer talks the idea through without grilling.",
    ),
    (("code-review",), "blocks the Code-Reviewer."),
    (("wayfinder",), "blocks the Wayfinder."),
    (("research", "prototype"), "degrades the Wayfinder: its research and prototype tickets cannot run."),
    (
        ("writing-for-agents",),
        "degrades the Planner, the Plan-Reviewer and the Code-Reviewer: each drops its writing pass, "
        "records that in the file it writes, and carries on.",
    ),
    (("setup-matt-pocock-skills",), "blocks the tracker setup, so the Planner and the Code-Reviewer wait on it."),
)


def bare(name: str) -> str:
    """A skill name as the list shows it, compared by the part after the last
    colon: mattpocock-skills:writing-for-agents is writing-for-agents."""
    return name.strip().rsplit(":", 1)[-1]


# --listed none: no skill of the collection listed. Windows PowerShell 5.1
# drops an empty argument, so '' cannot carry it there.
NONE_LISTED = "none"


def parse_listed(value: str | None) -> set[str]:
    if not value or value.strip() == NONE_LISTED:
        return set()
    names = value.replace(",", " ").split()
    return {bare(name) for name in names if bare(name)}


def ordered(skills: set[str]) -> list[str]:
    return [s for s in SKILLS if s in skills]


def cost_lines(failed: Iterable[str]) -> list[str]:
    lines: list[str] = []
    for group, cost in COSTS:
        hit = [s for s in group if s in failed]
        if hit:
            lines.append("%s: missing or not loaded, which %s" % (", ".join(hit), cost))
    return lines


class Verdict:
    """The Borrowed skills' state, from the search and the model's facts."""

    def __init__(
        self,
        hits: dict[str, list[stores.Hit]],
        listed: set[str],
        glossary_named: str | None,
        user_answer: str | None,
    ) -> None:
        self.hits = hits
        self.present = {s for s in SKILLS if hits.get(s)}
        self.ask_user = False
        self.resolvable: set[str]
        if WRITING in listed or user_answer == "resolves":
            self.resolvable = set(SKILLS)
        elif listed & set(SIBLINGS):
            self.resolvable = set(SKILLS) - {WRITING}
        else:
            self.resolvable = set()
            # A miss on the whole list proves nothing when the files are
            # there: the user's one answer on writing-for-agents settles it.
            self.ask_user = bool(self.present) and user_answer is None
        self.passed = ordered(self.present & self.resolvable)
        self.no_hit = ordered(self.resolvable - self.present)
        self.not_loaded = ordered(self.present - self.resolvable)
        self.missing = ordered(set(SKILLS) - self.present - self.resolvable)
        others = set(SKILLS) - {WRITING}
        self.old_collection = glossary_named == "no" or (
            WRITING not in self.present and others <= self.present
        )

    def store_of(self, skills: Iterable[str], cwd: str) -> stores.Store | None:
        """The store most of these skills were found in, first root first."""
        counts = {}
        first = {}
        for skill in skills:
            for hit in self.hits.get(skill, [])[:1]:
                store = stores.Store(hit, cwd)
                counts[store.key()] = counts.get(store.key(), 0) + 1
                first.setdefault(store.key(), store)
        if not counts:
            return None
        best = max(counts.values())
        for key, store in first.items():
            if counts[key] == best:
                return store
        return None

    def stores_of(self, skills: Iterable[str], cwd: str) -> list[tuple[stores.Store, list[str]]]:
        """Each store these skills were found in, with its skills."""
        found = {}
        order = []
        for skill in skills:
            hit = self.hits[skill][0]
            store = stores.Store(hit, cwd)
            if store.key() not in found:
                found[store.key()] = (store, [])
                order.append(store.key())
            found[store.key()][1].append(skill)
        return [found[key] for key in order]
