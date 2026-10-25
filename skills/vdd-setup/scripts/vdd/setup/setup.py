"""The setup command: its help, the command lines it names and the finish;
the catalog parses its options. The checks are in checks.py and fill one
report (report.py)."""

from __future__ import annotations

import os
from typing import Any

from .. import catalog, gitcmd, harness as harnesses, places, runner
from ..harness import Harness
from ..out import Failure, escalate
from . import borrowed, checks, install
from .report import Report

HELP = [
    "setup --harness <h> --listed <names> --glossary-named <yes|no|absent> [--user-answer <answer>] [--write]",
    "",
    "Checks this repository and this machine for a VDD loop. Run it from the repository root.",
    "Without --write it changes nothing: it prints every check, every planned change and every line for the user.",
    "Show the user the planned changes, then run the same command with --write, which makes them and checks each.",
    "A run with nothing left to change changes nothing.",
    "",
    "--harness <h>            The Harness this Session runs in: %s,"
    % ", ".join(found.name for found in harnesses.every()[:-1]),
    "                         or %s for any other." % harnesses.every()[-1].name,
    "--listed <names>         The skills from Matt Pocock's collection your own skill list shows, named as",
    "                         it shows them (bare, or with a plugin prefix such as",
    "                         mattpocock-skills:writing-for-agents), separated by commas; none for none.",
    "                         Look for: writing-for-agents, grilling, codebase-design, domain-modeling, tdd,",
    "                         research, prototype, diagnosing-bugs, code-review. Pass code-review only when",
    "                         its description names the two axes Standards and Spec, or when it carries",
    "                         the mattpocock-skills: prefix.",
    "--glossary-named <v>     yes when domain-modeling's description in your skill list names GLOSSARY.md,",
    "                         no when it does not, absent when domain-modeling is not in your skill list.",
    "--user-answer <answer>   Only when a run's Next: line asks for it: resolves or does-not-resolve, the",
    "                         user's answer on whether writing-for-agents ran when they invoked it.",
    "--write                  Make the planned changes.",
]


def run(argv: list[str]) -> int:
    return catalog.run("setup", argv, catalog.Help({"": HELP}), "Run %s with the options above, without --write first."
                       % catalog.line("setup"), setup)


def setup(ctx: catalog.Context) -> int:
    values = ctx.values
    harness = harnesses.from_option(values, ctx.usage)
    cwd = os.getcwd()
    require_shipped(harness, values)
    require_root(harness, values, cwd)
    mode = "writing" if values["write"] else "dry run, nothing is changed yet"
    report = Report("Setup, Harness %s (%s)." % (header_name(harness), mode))
    return runner.run(ctx, lambda: plan(report, harness, values, cwd))


def plan(report: Report, harness: Harness, values: dict[str, Any], cwd: str) -> runner.Plan:
    """Setup as a plan: every check's lines and planned changes in the order
    they print, the dry run's Next: and the write's."""
    checks.run(report, harness, cwd, values["listed"], values["glossary-named"], values["user-answer"])
    effects = list(report.effects)
    if not report.changes:
        effects.append(runner.Effect(done=["Nothing left to change."]))
    return runner.Plan(effects, lambda: finish(report, harness, values, write=True),
                       dry_next=finish(report, harness, values, write=False), lines=[report.header],
                       code=lambda: 1 if report.git_too_old or report.failed else 0)


def command(harness: Harness, values: dict[str, Any], write: bool, entry: str | None = None) -> str:
    """The setup command line this run names, with or without --write, on
    the copy of the tool at entry (the running one by default)."""
    return catalog.line("setup", entry=entry, harness=harness.name, listed=quote(values["listed"]),
                        glossary_named=values["glossary-named"], user_answer=values["user-answer"] or None,
                        write=write)


def require_shipped(harness: Harness, values: dict[str, Any]) -> None:
    """Refuse a run from the Shared copy: it would compare the Shared copy
    with itself and call it current whatever the plugin ships."""
    shared = places.shared_dir()
    if not same_directory(install.shipped_dir(), shared):
        return
    entry = os.path.join("<vdd-setup skill directory>", "scripts", "vdd.py")
    raise Failure(
        [
            "Setup ran from the Shared copy of the VDD tool, %s, which it installs and checks; from there it cannot "
            "see the copy the plugin ships." % os.path.join(shared, "vdd.py"),
            "Nothing was checked or changed.",
        ],
        "Setup runs from the copy beside the vdd-setup skill you loaded: run scripts/vdd.py in the directory its "
        "SKILL.md sits in, with the same options: %s" % command(harness, values, values["write"], entry),
    )


def require_root(harness: Harness, values: dict[str, Any], cwd: str) -> None:
    """Refuse a run from below the repository root: every check and every
    write is relative to the working directory."""
    call = gitcmd.git(cwd, "rev-parse", "--show-toplevel")
    if call.code is None:
        return
    root = call.out.strip()
    if not call.ok or not root or same_directory(root, cwd):
        return
    root = os.path.realpath(root)
    raise Failure(
        [
            "Setup runs from the repository root, and this directory is below it: %s" % cwd,
            "The repository root: %s" % root,
            "Nothing was checked or changed.",
        ],
        "Change to the repository root, %s, and run the same command there: %s"
        % (root, command(harness, values, values["write"])),
    )


def finish(report: Report, harness: Harness, values: dict[str, Any], write: bool) -> str:
    """The Next: step, from what the checks found and, on a write, what
    landed."""
    if report.git_too_old:
        return "Stop: no loop can start until git is 2.40 or newer."
    if report.failed:
        return escalate("Otherwise tell the user which change did not land and what it was for, and stop.")
    if report.user_answer_needed:
        return (
            "Ask the user to invoke %s and tell you whether it resolves. Then run: %s --user-answer "
            "resolves, or with --user-answer does-not-resolve when it does not."
            % (harness.borrowed_skill(borrowed.WRITING), command(harness, values, write=False))
        )
    if not write and (report.changes or report.questions):
        steps = []
        if report.questions:
            steps.append(" ".join(report.questions))
        if report.changes:
            steps.append("Show the user the planned changes above; showing them is the consent step.")
        steps.append("Then run: %s" % command(harness, values, write=True))
        return " ".join(steps)
    return (
        "Give the user a short status report: what passed, what Setup changed, and what the user "
        "still has to do. Setup is done. If another "
        "skill invoked Setup, go on with that skill's next step in this same turn; otherwise end your turn with "
        "the report."
    )


def header_name(harness: Harness) -> str:
    """The Harness as Setup's first line names it: by its label, or by its
    --harness value when the user-facing name is no name of its own
    (Generic's "your agent")."""
    return harness.label if harness.display_name == harness.label else harness.name


def quote(value: str) -> str:
    if not value or not value.strip():
        return borrowed.NONE_LISTED
    if all(c.isalnum() or c in "-_:,." for c in value):
        return value
    return "'%s'" % value


def same_directory(one: str, other: str) -> bool:
    return os.path.normcase(os.path.realpath(one)) == os.path.normcase(os.path.realpath(other))
