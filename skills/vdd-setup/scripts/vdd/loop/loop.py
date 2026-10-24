"""The loop command group: the Loop file and the loop's state, written, read,
changed, closed and reopened only here. Each write command is a precondition
and a plan the runner prints as its dry run or applies with --write."""

from __future__ import annotations

import os
from typing import Any

from .. import catalog, gitcmd, harness as harnesses, loopfile, loopstate, prbody, runner, textfile
from ..out import TELL, Failure, Output, one_line, or_list, refused

HELP = catalog.Help({
    "new": [
        "loop new --slug <slug> --harness <h> [--base <branch>] [--branch <branch>] [--minors <a>] [--pr <a>]",
        "         [--leftover continue] [--write]",
        "  Start-Loop's first call: start a loop. Without --write it checks the slug, reads the base branch,",
        "  proposes the feature branch and prints the questions for the user, changing nothing. Ask them, then",
        "  run it again with the answers and --write: it writes .scratch/<slug>/loop.md and marks the loop open.",
        "  On PR: yes it checks that a push and gh would work, and warns without blocking. When .scratch/<slug>/",
        "  already exists it reports what is there and the answers it allows; the user's continue is",
        "  --leftover continue.",
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
        "  feature branch never change. When the user corrects the Harness after loop new: --harness-line <label>",
        "  with --harness <the corrected h>.",
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
        "  files are deleted. The PR-Author and the Orchestrator run it at the end of the Workflow. Unless PR: no,",
        "  it prints the title and body in pr-body.md for the user to open the PR from.",
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
    return catalog.run("loop", argv, HELP,
                       "Run the loop command above that your step needs, or the one the last Next: line names.", dispatch)


def dispatch(ctx: catalog.Context) -> int:
    sub, values = ctx.command, ctx.values
    if sub == "new":
        from .new import new
        harness = harnesses.from_option(values, ctx.usage)
        new_root = gitcmd.project_root(os.getcwd())
        return runner.run(ctx, lambda: new(new_root, ctx, harness))
    if values["harness"] is not None:
        harnesses.from_option(values, ctx.usage)
    root = gitcmd.project_root(os.getcwd())
    if sub == "show":
        return show(root, values)
    if sub == "aside":
        return runner.run(ctx, lambda: aside(root, values))
    if sub in ("close", "reopen"):
        return runner.run(ctx, lambda: close_or_reopen(root, values, sub))
    if sub == "fold":
        from .fold import fold
        return runner.run(ctx, lambda: fold.plan(
            loopfile.find(root, values["slug"]), harnesses.from_option(values, ctx.usage), values["write"]))
    return runner.run(ctx, lambda: set_lines(root, values, ctx.usage))


def check_answers(values: dict[str, Any], options: tuple[tuple[str, str], ...]) -> None:
    for option, name in options:
        value = values.get(option)
        if value is not None and not loopfile.accepted(name, value):
            raise catalog.not_a_choice(
                option, value, loopfile.choices(name),
                step="Ask the user again with the accepted answers, then run the command with one of them.")


def aside(root: str, values: dict[str, Any]) -> runner.Plan:
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
    closing = leftover == loopstate.OPEN

    def refuse(error: OSError) -> Failure:
        return refused(
            "Could not move .scratch/%s/ aside: %s" % (slug, textfile.reason(error)),
            "Otherwise tell the user the directory could not be moved, and stop.",
        )

    def move() -> list[str]:
        try:
            os.rename(loopfile.tracker_dir(root, slug), loopfile.tracker_dir(root, target))
        except OSError as error:
            raise refuse(error)
        return ["Moved: .scratch/%s/ is now .scratch/%s/. Nothing was deleted." % (slug, target),
                TELL % ("The earlier Workflow's files are now in .scratch/%s/." % target)]

    effects: list[runner.Effect] = []
    if closing and state is not None:
        effects += runner.close(state, done=["Closed the loop %s." % slug], refuse=refuse)
    effects.append(runner.Step(move, dry=["Would move .scratch/%s/ to .scratch/%s/%s." % (
        slug, target, ", closing its open loop first" if closing else "")], after=True))
    return runner.Plan(effects, "Run the %s command that reported the leftover again: .scratch/%s/ is free now."
                       % (catalog.bare("loop", "new"), slug))


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
    return out.finish("Pass --slug %s on every VDD tool call from here on. %s" % (loop.slug, after_show(loop, role)))


def after_show(loop: loopfile.Loop, role: str | None) -> str:
    """The step after loop show: the PR-Author's pr check, the Planner's start
    of its session, or the step that named loop show."""
    if role == "PR-Author":
        return "Then run %s" % catalog.line("pr", "check", slug=loop.slug, harness=loop.harness.name)
    if role == "Planner":
        return ("Read the Harness file above, then start the session as your skill says, on the user's problem or "
                "by asking for one.")
    return "Then go on with the step that named loop show."


def set_lines(root: str, values: dict[str, Any], usage: str) -> runner.Plan:
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
    for option, name in changes:
        lines = loopfile.replace_line(lines, name, values[option])
    written = runner.WriteFile(
        loop.file, "\n".join(lines) + "\n", "the Loop file %s" % loop.relative,
        "Otherwise tell the user the Loop file could not be changed, and stop.",
        dry=["Would set: %s: %s" % (name, values[option]) for option, name in changes],
        done=["Set: %s: %s" % (name, values[option]) for option, name in changes])
    return runner.Plan(
        [written], "Go on with the step you were on when the user asked for the change, passing --slug %s." % loop.slug)


def after_state(slug: str, target: str) -> str:
    """The Next: step once the loop is closed or open."""
    if target == loopstate.CLOSED:
        return "The loop %s is closed: run nothing more for it; finish the step you were on, then end your turn." % slug
    return "Go on as the user directs, passing --slug %s." % slug


def shown_body(loop: loopfile.Loop) -> list[runner.Effect]:
    """The PR title and body as lines for the user, unless PR: no or
    pr-body.md cannot be read as one: a loop closed without a PR leaves the
    user to open it from them."""
    if loop.pr == "no":
        return []
    found = prbody.read(loop)
    if found.problem is not None:
        return []
    tells = ["Open the PR yourself with this title and body, also in %s:" % prbody.relative(loop),
             "Title: %s" % found.title, ""] + found.body.rstrip("\n").split("\n")
    return [runner.Effect(["Would print the PR title and body in %s for the user." % prbody.relative(loop)],
                          [TELL % one_line(tell) for tell in tells])]


def close_or_reopen(root: str, values: dict[str, Any], sub: str) -> runner.Plan:
    loop = loopfile.find(root, values["slug"])
    target = loopstate.CLOSED if sub == "close" else loopstate.OPEN
    state = loop.load_state()
    if state.status == target:
        return runner.Plan([], after_state(loop.slug, target),
                           lines=["The loop %s is already %s. Nothing was written." % (loop.slug, target)])

    def refuse(error: OSError) -> Failure:
        return refused(
            "Could not change the loop state file in .scratch/%s/: %s" % (loop.slug, textfile.reason(error)),
            "Otherwise tell the user the loop could not be marked %s, and stop." % target,
        )

    dry = ["Would mark the loop %s %s." % (loop.slug, target)]
    if target == loopstate.CLOSED:
        effects = runner.close(state, dry, [runner.closed_line(loop.slug)], refuse) + shown_body(loop)
    else:
        effects = [runner.reopen(state, dry, ["Reopened: the loop %s is open again." % loop.slug], refuse)]
    return runner.Plan(effects, after_state(loop.slug, target))
