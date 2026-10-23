"""The loop command group: the Loop file and the loop's state, written, read,
changed, closed and reopened only here."""

from __future__ import annotations

import os
from typing import Any

from .. import catalog, gitcmd, harness as harnesses, loopfile, loopstate, textfile
from ..harness import Harness
from ..out import Failure, Output, or_list, refused

HELP = catalog.Help({
    "new": [
        "loop new --slug <slug> --harness <h> [--base <branch>] [--branch <branch>] [--minors <a>] [--pr <a>]",
        "         [--leftover continue] [--write]",
        "  Start a loop. Without --write it checks the slug, reads the base branch, proposes the feature branch",
        "  and prints the questions for the user, changing nothing. Ask them, then run it again with the answers",
        "  and --write: it writes .scratch/<slug>/loop.md and marks the loop open. On PR: yes it checks that a",
        "  push and gh would work, and warns without blocking. When .scratch/<slug>/ already exists it reports",
        "  what is there and the answers it allows; the user's continue is --leftover continue.",
    ],
    "aside": [
        "loop aside --slug <slug> --write",
        "  Move .scratch/<slug>/ to .scratch/<slug>-<n>/, the lowest free n from 2, closing an open loop first.",
        "  It deletes nothing. The user's start fresh on a leftover tracker directory.",
    ],
    "show": [
        "loop show [--slug <slug>] [--role <Role>]",
        "  Print the Loop file's lines as every Role acts on them: a missing or malformed line as its default,",
        "  whether the loop is open or closed, and the Harness file to read. --role prints only the lines that",
        "  Role acts on: Planner, Plan-Reviewer, Coder, Code-Reviewer, Orchestrator or PR-Author. --role",
        "  PR-Author refuses until the state file records the code Sign-off.",
    ],
    "set": [
        "loop set [--slug <slug>] [--minors <a>] [--pr <a>] [--harness-line <label>] --write",
        "  Change the Minors:, PR: or Harness: line on the user's word. The feature, the base branch and the",
        "  feature branch never change.",
    ],
    "fold": [
        "loop fold --slug <slug> --harness <h> [--write]",
        "  Run at each code Sign-off, on every PR: value, without asking the user. Moves each later round's fix",
        "  into the commit that wrote its lines; when it cannot, the branch stays as signed and it says why.",
        "  Without --write it prints what it would do.",
    ],
    "close": [
        "loop close [--slug <slug>] --write",
        "  Close the loop: it stays on disk as the record, a ring or a wait on it is refused, and its Codex armed",
        "  files are deleted. The PR-Author and the Orchestrator run it at the end of the Workflow.",
    ],
    "reopen": [
        "loop reopen [--slug <slug>] --write",
        "  Reopen a closed loop, on the user's request.",
    ]},
    [
        catalog.Only(("set",),
                     "Accepted values: --minors fix or leave; --pr yes, \"ask at sign-off\", manual or no; "
                     "--harness-line",
                     "%s." % or_list(found.label for found in harnesses.every())),
        catalog.Only(("new",),
                     "Accepted values: --minors fix or leave; --pr yes, \"ask at sign-off\", manual or no.",
                     group=False),
        "",
        "--slug names the loop. Without it the tool takes the loop whose feature branch is checked out, else the",
        "only open loop, else it refuses. A Role passes --slug on every call. --harness names the Harness this",
        "Session runs in (%s) and never changes the Loop file."
        % or_list(found.name for found in harnesses.every()),
    ])

# Option -> Loop file line, for the answers new writes and set changes.
ANSWERS = (("minors", "Minors"), ("pr", "PR"))
SETTABLE = ANSWERS + (("harness-line", "Harness"),)


def run(argv: list[str]) -> int:
    return catalog.run("loop", argv, HELP, "Run the loop command your skill or the last Next: line names.", dispatch)


def dispatch(ctx: catalog.Context) -> int:
    sub, values = ctx.command, ctx.values
    if sub == "new":
        from .new import new
        harness = harnesses.from_option(values, ctx.usage)
        return new(gitcmd.project_root(os.getcwd()), ctx, harness)
    if values["harness"] is not None:
        harnesses.from_option(values, ctx.usage)
    root = gitcmd.project_root(os.getcwd())
    if sub == "aside":
        return aside(root, values)
    if sub == "show":
        return show(root, values)
    if sub in ("close", "reopen"):
        return close_or_reopen(root, values, sub)
    if sub == "fold":
        from .fold import fold
        return fold.run(loopfile.find(root, values["slug"]), harnesses.from_option(values, ctx.usage), values["write"])
    return set_lines(root, values, ctx.usage)


def check_answers(values: dict[str, Any], options: tuple[tuple[str, str], ...]) -> None:
    for option, name in options:
        value = values.get(option)
        if value is not None and not loopfile.accepted(name, value):
            raise Failure(
                "--%s %s is not a value the %s: line accepts. It takes %s."
                % (option, value, name, loopfile.accepted_text(name)),
                "Ask the user again with the accepted answers, then run the command with one of them.",
            )


def aside(root: str, values: dict[str, Any]) -> int:
    loopfile.refuse_root(root)
    slug = values["slug"]
    loopfile.check_slug(slug)
    leftover, state = loopfile.look(root, slug)
    if leftover is None:
        raise Failure(
            ".scratch/%s/ does not exist: nothing to move aside." % slug,
            "Run %s for the slug instead." % catalog.bare("loop", "new"),
        )
    number = 2
    while os.path.lexists(loopfile.tracker_dir(root, "%s-%d" % (slug, number))):
        number += 1
    target = "%s-%d" % (slug, number)
    out = Output()
    closing = leftover == loopstate.OPEN
    if not values["write"]:
        out.line("Would move .scratch/%s/ to .scratch/%s/%s." % (
            slug, target, ", closing its open loop first" if closing else ""))
        return out.finish("Run the same command with --write.")
    directory = loopfile.tracker_dir(root, slug)
    try:
        if closing and state is not None:
            for name in loopfile.close(state):
                out.line("Deleted the Codex armed file %s." % name)
            out.line("Closed the loop %s." % slug)
        os.rename(directory, loopfile.tracker_dir(root, target))
    except OSError as error:
        raise refused(
            "Could not move .scratch/%s/ aside: %s" % (slug, textfile.reason(error)),
            "Otherwise tell the user the directory could not be moved, and stop.",
        )
    out.line("Moved: .scratch/%s/ is now .scratch/%s/. Nothing was deleted." % (slug, target))
    out.tell("The earlier Workflow's files are now in .scratch/%s/." % target)
    return out.finish("Run %s for %s again, as your skill says." % (catalog.bare("loop", "new"), slug))


def show(root: str, values: dict[str, Any]) -> int:
    loop = loopfile.find(root, values["slug"])
    role = values["role"]
    state = loop.load_state()
    if role == "PR-Author":
        state.refuse_v1(loop.slug, "loop show --role PR-Author")
        loopstate.require_code_sign_off(state)
    names = loopfile.ROLES[role] if role else loopfile.IDENTITY + loopfile.SETTINGS
    out = Output()
    out.line("Slug: %s" % loop.slug)
    out.line("State: %s" % state.status)
    faults = []
    for name in names:
        value, fault = loop.setting(name)
        if fault:
            raw = loop.fields.get(name)
            what = "malformed: %s" % raw if fault == "malformed" else "missing"
            out.line("%s: %s (%s; read as the default)" % (name, value, what))
            faults.append((name, value, fault))
        else:
            out.line("%s: %s" % (name, value))
    out.line("Harness file: %s" % loop.harness_file())
    for name, value, fault in faults:
        out.tell(
            "The Loop file's %s: line is %s, so it reads as %s: %s." % (name, fault, name, value)
        )
    return out.finish(
        "Pass --slug %s on every VDD tool call from here on, and go on as your skill says." % loop.slug
    )


def set_lines(root: str, values: dict[str, Any], usage: str) -> int:
    if any(values[option] is not None for option in ("feature", "base-branch", "feature-branch", "base", "branch")):
        raise Failure(
            "loop set never changes the Feature:, Base branch: or Feature branch: line: they name the loop and "
            "its review range. Nothing was written.",
            "Tell the user these lines are fixed for the loop's life; to change them, start a new loop.",
        )
    changes = [(option, name) for option, name in SETTABLE if values[option] is not None]
    if not changes:
        raise Failure(
            "Nothing to set: name --minors, --pr or --harness-line.",
            "Run %s for this command's usage." % usage,
        )
    check_answers(values, SETTABLE)
    loop = loopfile.find(root, values["slug"])
    lines = list(loop.lines)
    out = Output()
    for option, name in changes:
        lines = loopfile.replace_line(lines, name, values[option])
        out.line("%s %s: %s" % ("Set:" if values["write"] else "Would set:", name, values[option]))
    if not values["write"]:
        return out.finish("Run the same command with --write.")
    textfile.write_or_refuse(loop.file, "\n".join(lines) + "\n", "the Loop file %s" % loop.relative,
                             "Otherwise tell the user the Loop file could not be changed, and stop.")
    return out.finish("Go on as your skill says, passing --slug %s." % loop.slug)


def close_or_reopen(root: str, values: dict[str, Any], sub: str) -> int:
    loop = loopfile.find(root, values["slug"])
    target = loopstate.CLOSED if sub == "close" else loopstate.OPEN
    out = Output()
    state = loop.load_state()
    if state.status == target:
        out.line("The loop %s is already %s. Nothing was written." % (loop.slug, target))
        return out.finish("Go on as your skill says, passing --slug %s." % loop.slug)
    if not values["write"]:
        out.line("Would mark the loop %s %s." % (loop.slug, target))
        return out.finish("Run the same command with --write.")
    try:
        if target == loopstate.CLOSED:
            for name in loopfile.close(state):
                out.line("Deleted the Codex armed file %s." % name)
        else:
            loopfile.reopen(state)
    except OSError as error:
        raise refused(
            "Could not change the loop state file in .scratch/%s/: %s" % (loop.slug, textfile.reason(error)),
            "Otherwise tell the user the loop could not be marked %s, and stop." % target,
        )
    if target == loopstate.CLOSED:
        out.line(loopfile.closed_line(loop.slug))
    else:
        out.line("Reopened: the loop %s is open again." % loop.slug)
    return out.finish("Go on as your skill says, passing --slug %s." % loop.slug)
