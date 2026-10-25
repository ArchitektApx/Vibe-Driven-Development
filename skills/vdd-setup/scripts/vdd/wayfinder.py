"""The wayfinder command group: the Wayfinder's start, reading only.

wayfinder start reports whether the effort's map exists and where Matt
Pocock's wayfinder skill is installed, and prints the briefing with the
effort and both template paths filled in. The briefing's text lives here
alone.
"""

from __future__ import annotations

import os

from . import catalog, gitcmd, harness as harnesses, stores
from .out import Failure, Output

TEMPLATES = ("overview-template.md", "handoff-template.md")
# A Feature slug, with dots allowed between words: an effort is often named
# for a release, as release-2.1-work is.
EFFORT_PATTERN = "[a-z0-9]+([.-][a-z0-9]+)*"

HELP = catalog.Help({
    "start": [
        "wayfinder start --effort <slug> --skill-dir <dir>",
        "  The Wayfinder's first call. Checks the effort slug, reports whether .scratch/<effort>/map.md exists and",
        "  where Matt Pocock's wayfinder skill is installed, and prints the briefing for wayfinder with the effort",
        "  and the absolute paths of both templates filled in. --skill-dir is the Wayfinder skill's base",
        "  directory, the one your Harness reported when the skill loaded; it refuses when a template is missing",
        "  there. It writes nothing.",
    ],
})

BRIEFING = [
    "Briefing for the wayfinding of <effort>:",
    "",
    "- This project uses Vibe Driven Development (VDD). Each loop is one coherent",
    "  change: a Planner grills the user and writes a Spec and Tickets, a",
    "  Plan-Reviewer reviews the plan in rounds, a Coder implements, a",
    "  Code-Reviewer reviews the code in rounds, each in its own context. Every",
    "  loop does its own grilling and planning. The wayfinding settles the big",
    "  picture and nothing about a loop's inner workings.",
    "- Destination: the handoffs under .scratch/<effort>/handoffs/, one",
    "  00-overview.md from <path to overview-template.md> and one NN-<slug>.md per",
    "  loop from <path to handoff-template.md>. The map is done when those files",
    "  exist and nothing is left to decide before loop 01 starts.",
    "- Loops are cut by coherence, the way to-tickets cuts tickets: what belongs",
    "  together lands together. Size is not the cut; a loop that turns out too",
    "  large is caught by its Planner, who asks the user to split it.",
    "- Carry these three points into the map's Notes section, so every later",
    "  wayfinding session reads them.",
]


def run(argv: list[str]) -> int:
    return catalog.run("wayfinder", argv, HELP, "Run wayfinder start with the effort slug and this skill's base directory.",
                       dispatch)


def dispatch(ctx: catalog.Context) -> int:
    return start(ctx.values["effort"], ctx.values["skill-dir"])


def templates(skill_dir: str) -> list[str]:
    """The absolute paths of both templates, or a Failure naming the one
    missing."""
    found = []
    for name in TEMPLATES:
        path = os.path.join(os.path.abspath(skill_dir), "references", name)
        if not os.path.isfile(path):
            raise Failure(
                "--skill-dir %s has no references/%s. Nothing was printed." % (skill_dir, name),
                "Check that --skill-dir is this skill's base directory, the one your Harness reported when the "
                "skill loaded, and run the command again. When it is, tell the user VDD's install is incomplete: "
                "invoke vdd-setup, then start the Wayfinder again. Stop.",
            )
        found.append(path)
    return found


def wayfinder_roots(root: str) -> list[stores.Root]:
    """The roots Matt Pocock's wayfinder is searched under: every Harness's
    skill stores, the ones Setup searches under Generic, whichever Harness
    this Session runs in."""
    return stores.union(found.present_roots(root) for found in harnesses.every())


def find_wayfinder(roots: list[stores.Root]) -> str | None:
    """The path of wayfinder/SKILL.md under the first root that holds one,
    or None."""
    for store in roots:
        hits = stores.search([store], ["wayfinder"])
        if hits.get("wayfinder"):
            return sorted(hit.path for hit in hits["wayfinder"])[0]
    return None


def shown(store: stores.Root, root: str) -> str:
    """A root as the refusal names it, with the pattern a plugin cache is
    searched below."""
    label = store.label(root)
    return "%s/%s" % (label, store.pattern) if store.pattern else label


def briefing(effort: str, overview: str, handoff: str) -> list[str]:
    return [line.replace("<effort>", effort).replace("<path to overview-template.md>", overview)
            .replace("<path to handoff-template.md>", handoff) for line in BRIEFING]


def check_effort(effort: str) -> None:
    catalog.check_slug(effort, EFFORT_PATTERN, "an effort slug", "an effort slug", "hyphens or dots")


def start(effort: str, skill_dir: str) -> int:
    check_effort(effort)
    overview, handoff = templates(skill_dir)
    root = gitcmd.project_root(os.getcwd())
    out = Output()
    out.line("Effort: %s" % effort)
    map_path = ".scratch/%s/map.md" % effort
    has_map = os.path.isfile(os.path.join(root, ".scratch", effort, "map.md"))
    out.line("Map: %s %s." % (map_path, "exists" if has_map else "does not exist"))
    roots = wayfinder_roots(root)
    found = find_wayfinder(roots)
    if found is None:
        out.line("wayfinder: not installed: no wayfinder/SKILL.md under %s." % ", ".join(
            shown(store, root) for store in roots))
        out.tell("Matt Pocock's wayfinder skill is not installed. Invoke vdd-setup, which installs it, then start "
                 "the Wayfinder again.")
    else:
        out.line("wayfinder: %s" % found)
    out.line("The briefing, to print unchanged, runs from the next line to the line before Next:.")
    for line in briefing(effort, overview, handoff):
        out.line(line)
    if found is None:
        return out.finish("Stop.")
    if has_map:
        return out.finish(
            "Read the ## Notes of %s. If any of the three points in the briefing above is missing there, print the "
            "briefing unchanged. Then tell the user to invoke wayfinder with the path %s. You are done." % (
                map_path, map_path)
        )
    return out.finish(
        "Ask the user what the effort is: a loose idea in text, a goals file, or a decided idea file from the "
        "Brainstormer. Read what they name, print the briefing above unchanged, then tell the user to invoke "
        "wayfinder with the idea or file you read. You are done."
    )
