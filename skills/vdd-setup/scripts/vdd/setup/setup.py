"""The setup command: its help, the command lines it names and the finish;
the catalog parses its options. The checks are in checks.py and fill one
report (report.py)."""

from __future__ import annotations

import os
from typing import Any

from .. import catalog, gitcmd, harness as harnesses, places
from ..harness import Harness
from ..out import Failure, escalate
from . import borrowed, checks
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
    return catalog.run("setup", argv, HELP, "Run %s setup with the options above, without --write first."
                       % places.command(), setup)


def setup(ctx: catalog.Context) -> int:
    values = ctx.values
    harness = harnesses.from_option(values, ctx.usage)
    answer = values["user-answer"]
    cwd = os.getcwd()
    require_root(harness, values, cwd)
    report = Report(values["write"])
    mode = "writing" if report.write else "dry run, nothing is changed yet"
    report.out.line("Setup, Harness %s (%s)." % (header_name(harness), mode))
    checks.run(report, harness, cwd, values["listed"], values["glossary-named"], answer)
    return finish(report, harness, values)


def command(harness: Harness, values: dict[str, Any], write: bool) -> str:
    """The setup command line this run names, with or without --write."""
    parts = [
        places.command(),
        "setup",
        "--harness",
        harness.name,
        "--listed",
        quote(values["listed"]),
        "--glossary-named",
        values["glossary-named"],
    ]
    if values["user-answer"]:
        parts += ["--user-answer", values["user-answer"]]
    if write:
        parts.append("--write")
    return " ".join(parts)


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


def finish(report: Report, harness: Harness, values: dict[str, Any]) -> int:
    out = report.out
    if report.git_too_old:
        return out.finish(
            "Relay the Tell the user verbatim line about git above, and stop: no loop can start until git is "
            "2.40 or newer.",
            1,
        )
    if report.failed:
        return out.finish(
            escalate("Otherwise tell the user which change did not land and what it was for, and stop."),
            1,
        )
    if report.user_answer_needed:
        return out.finish(
            "Ask the user to invoke %s and tell you whether it resolves. Then run: %s --user-answer "
            "resolves, or with --user-answer does-not-resolve when it does not."
            % (harness.borrowed_skill(borrowed.WRITING), command(harness, values, write=False))
        )
    if not report.write and (report.changes or report.questions):
        steps = []
        if report.questions:
            steps.append(" ".join(report.questions))
        if report.changes:
            steps.append("Show the user the planned changes above; showing them is the consent step.")
        steps.append("Then run: %s" % command(harness, values, write=True))
        return out.finish(" ".join(steps))
    if report.write and not report.changes:
        out.line("Nothing left to change.")
    return out.finish(
        "Give the user a short status report: what passed, what Setup changed, and what the user "
        "still has to do, relaying every Tell the user verbatim line above unchanged. Setup is done."
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
