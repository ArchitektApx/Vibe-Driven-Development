"""The wayfinder command group: the Wayfinder's start, reading only.

wayfinder start reports whether the effort's map exists and where Matt
Pocock's wayfinder skill is installed, and prints the briefing with the
effort and both template paths filled in. The briefing's text lives here
alone.
"""

import os

from . import args, gitcmd, places, stores
from .out import Failure, Output

SUBCOMMANDS = ("start",)
TEMPLATES = ("overview-template.md", "handoff-template.md")
# A Feature slug, with dots allowed between words: an effort is often named
# for a release, as beta-0.16.0-work is.
EFFORT_PATTERN = "[a-z0-9]+([.-][a-z0-9]+)*"

HELP = [
    "wayfinder start --effort <slug> --skill-dir <dir>",
    "  The Wayfinder's first call. Checks the effort slug, reports whether .scratch/<effort>/map.md exists and",
    "  where Matt Pocock's wayfinder skill is installed, and prints the briefing for wayfinder with the effort",
    "  and the absolute paths of both templates filled in. --skill-dir is the Wayfinder skill's base",
    "  directory, the one your Harness reported when the skill loaded; it refuses when a template is missing",
    "  there. It writes nothing.",
    "",
    "Run every command from the repository root.",
]

SPEC = {"effort": args.VALUE, "skill-dir": args.VALUE}

# The roots Matt Pocock's wayfinder is searched under, on every Harness: (base,
# relative path), base "~" for the user's home and "." for the project.
ROOTS = (
    ("~", ".agents/skills"),
    (".", ".agents/skills"),
    ("~", ".claude/skills"),
    (".", ".claude/skills"),
    ("~", ".claude/plugins/cache"),
    ("~", ".codex/plugins/cache"),
)

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


def usage():
    return "%s wayfinder --help" % places.command()


def run(argv):
    return args.run_group(argv, "wayfinder", dict.fromkeys(SUBCOMMANDS, SPEC), HELP,
                          "Run the wayfinder command your skill names.", dispatch)


def dispatch(sub, values):
    args.require(values, ["effort", "skill-dir"], usage())
    return start(values["effort"], values["skill-dir"])


def templates(skill_dir):
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


def find_wayfinder(root):
    """The path of wayfinder/SKILL.md under the first root that holds one,
    or None."""
    for base, relative in ROOTS:
        directory = os.path.join(places.home() if base == "~" else root, *relative.split("/"))
        hits = stores.search([stores.Root(directory, stores.SKILL_STORE, stores.USER, "any")], ["wayfinder"])
        if hits.get("wayfinder"):
            return sorted(hit.path for hit in hits["wayfinder"])[0]
    return None


def briefing(effort, overview, handoff):
    return [line.replace("<effort>", effort).replace("<path to overview-template.md>", overview)
            .replace("<path to handoff-template.md>", handoff) for line in BRIEFING]


def check_effort(effort):
    args.check_slug(effort, EFFORT_PATTERN, "an effort slug", "an effort slug", "hyphens or dots")


def start(effort, skill_dir):
    check_effort(effort)
    overview, handoff = templates(skill_dir)
    root = gitcmd.project_root(os.getcwd())
    out = Output()
    out.line("Effort: %s" % effort)
    map_path = ".scratch/%s/map.md" % effort
    has_map = os.path.isfile(os.path.join(root, ".scratch", effort, "map.md"))
    out.line("Map: %s %s." % (map_path, "exists" if has_map else "does not exist"))
    found = find_wayfinder(root)
    if found is None:
        out.line("wayfinder: not installed: no wayfinder/SKILL.md under %s." % ", ".join(
            "%s/%s" % (base, relative) for base, relative in ROOTS))
        out.tell("Matt Pocock's wayfinder skill is not installed. Invoke vdd-setup, which installs it, then start "
                 "the Wayfinder again.")
    else:
        out.line("wayfinder: %s" % found)
    out.line("The briefing, to print unchanged, runs from the next line to the line before Next:.")
    for line in briefing(effort, overview, handoff):
        out.line(line)
    if found is None:
        return out.finish("Relay the Tell the user verbatim line above and stop.")
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
