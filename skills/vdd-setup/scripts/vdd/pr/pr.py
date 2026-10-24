"""The pr command group: the PR-Author's facts, the one ending that applies,
and its one publishing call.

pr check reads only: the PR template, else the repository's merged-PR
history as far as matching its shape needs, the preflight and the
existing-PR check, the path that follows, and as its Next: line the one
ending that applies to the loop's PR: line and the path. pr open is a plan:
the push, the PR's creation and the loop's close. Every git and gh call runs
from an argument list, never through a shell, and a call a sandbox refused
is told apart from any other failure.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .. import catalog, doorbells, gitcmd, harness as harnesses, loopfile, loopstate, prbody, runner, textfile
from ..gitcmd import Refused
from ..out import TELL, Failure, Output, one_line, refused
from . import conventions
from .path import EXISTING, MANUAL, NEITHER, NO_PR, OPEN, PUSH_ONLY, TIMEOUT_SECONDS, Path, path_of

if TYPE_CHECKING:
    from ..harness import Harness

PUSH_TIMEOUT_SECONDS = 600

# pr open's refusal for each reason pr-body.md cannot be read, after its path.
BODY_PROBLEMS = {
    prbody.MISSING: "does not exist",
    prbody.NO_TITLE: "has no title on its first line",
    prbody.NO_BLANK_LINE: "has no blank second line between the title and the body",
    prbody.NO_BODY: "has no body after the blank line",
}

HELP = catalog.Help({
    "check": [
        "pr check --slug <slug> --harness <h>",
        "  The PR-Author's first call after Sign-off. Reads only, and refuses until the code Loop is signed off",
        "  and while a fold is owed. Prints the PR template (the first of PULL_REQUEST_TEMPLATE.md or",
        "  pull_request_template.md at the repository root, in .github/ or in docs/) or that there is none; with",
        "  none and unless PR: no, the merged-PR history: each title, each body's headings, whether the bodies",
        "  link issues and the newest body whole, or no history, or could not read. On PR: yes or ask at",
        "  sign-off it runs the preflight (can push, can open a PR) and the existing-PR check, and prints the",
        "  path: open, push-only, neither or existing. Its Next: line is the one ending for the PR: line and the",
        "  path.",
    ],
    "open": [
        "pr open --path <open|push-only|existing> --slug <slug> --harness <h> --write",
        "  After the user confirmed the title and body in .scratch/<slug>/pr-body.md (the title, a blank line, the",
        "  body). --path is the path pr check printed. Refuses before the fold's outcome is recorded and on a",
        "  malformed pr-body.md. Runs the preflight and the existing-PR check again and pushes nothing when they",
        "  give another path. Pushes with git push -u <remote> <feature branch>; on the open path runs gh pr",
        "  create with the title as an argument and the body on standard input, and on the existing path only",
        "  pushes; closes the loop. A failed push leaves the loop open; a refused call asks for a rerun outside",
        "  the sandbox.",
    ]},
    [
        "--slug names the loop; pass it on every call. --harness names the Harness this Session runs in.",
    ])


def run(argv: list[str]) -> int:
    return catalog.run("pr", argv, HELP, "Run the pr command above that your step needs, or the one the last Next: "
                       "line names.", dispatch)


def dispatch(ctx: catalog.Context) -> int:
    sub, values = ctx.command, ctx.values
    harness = harnesses.from_option(values, ctx.usage)
    loop = loopfile.find(gitcmd.project_root(os.getcwd()), values["slug"])
    state = runner.open_loop(loop, "pr %s" % sub)
    loopstate.require_code_sign_off(state)
    if sub == "open":
        return runner.run(ctx, lambda: open_plan(loop, state, harness, values["path"]))
    return check(loop, state, harness)


def refusal(
    call: gitcmd.Call, command: str, otherwise: str, what: str = "Nothing was pushed or written; the loop stays open.",
) -> Failure:
    """The Failure for a call a sandbox refused inside the tool; what says
    what happened before it."""
    return gitcmd.sandbox_refusal(call, command, otherwise, [what])


def check_command(loop: loopfile.Loop, harness: Harness) -> str:
    return catalog.line("pr", "check", slug=loop.slug, harness=harness.name)


def open_command(loop: loopfile.Loop, harness: Harness, path: str) -> str:
    return catalog.line("pr", "open", path=path, slug=loop.slug, harness=harness.name, write=True)


def fold_owed(loop: loopfile.Loop, state: loopstate.State) -> bool:
    return doorbells.Place(loop.root, loop.slug, loop, state).position().fold_owed


def paths(loop: loopfile.Loop, command: str) -> Path:
    """The path, a sandbox's refusal of a call inside it worded for command."""
    try:
        return path_of(loop)
    except Refused as error:
        raise refusal(error.call, command, "tell the user %s was refused, and stop." % gitcmd.call_text(error.call))


# --- check ---

# Marks each line of the newest body as quoted data, so a body line such as
# "Next: ..." never reads as the tool's own.
BODY_MARK = "| "


def print_history(out: Output, found: conventions.History) -> None:
    if found.outcome == "none":
        out.line("History: none (%s)." % found.why)
        return
    if found.outcome == "unread":
        out.line("History: could not read: %s" % found.why)
        return
    out.line("History: %d merged PR%s, newest first." % (len(found.prs), "" if len(found.prs) == 1 else "s"))
    for number, (title, text) in enumerate(found.prs, 1):
        out.line("PR %d title: %s" % (number, title))
        marks = conventions.headings(text)
        out.line("PR %d headings: %s" % (number, " | ".join(marks) if marks else "none"))
    links = any(conventions.ISSUE_LINK.search(text) for _, text in found.prs)
    out.line("Bodies link issues: %s." % ("yes" if links else "no"))
    out.line("The newest body, whole, each of its lines after \"%s\", up to the line \"End of the newest body.\":"
             % BODY_MARK.strip())
    for line in found.prs[0][1].replace("\r\n", "\n").split("\n"):
        out.line((BODY_MARK + line).rstrip())
    out.line("End of the newest body.")


def print_path(out: Output, path: Path) -> None:
    for check_ in path.checks:
        if check_.passed:
            out.line("Preflight, %s, remote %s: passed." % (check_.name, path.remote))
        else:
            out.line("Preflight, %s, remote %s: failed (%s)." % (check_.name, path.remote, check_.why))
    if path.name == EXISTING:
        out.line("Existing PR: %s" % path.url)
        out.line("Path: existing %s" % path.url)
    elif path.name == MANUAL:
        out.line("Path: manual (PR: manual, no preflight)")
    elif path.name == NO_PR:
        out.line("Path: none (PR: no, no preflight)")
    else:
        if path.name == OPEN:
            out.line("Existing PR: none.")
        out.line("Path: %s" % path.name)


def check(loop: loopfile.Loop, state: loopstate.State, harness: Harness) -> int:
    command = check_command(loop, harness)
    if fold_owed(loop, state):
        raise Failure(
            "The fold's outcome is not recorded for the code Sign-off: the PR is assembled and pushed only from the "
            "folded branch. Nothing was read.",
            "Run %s, then run %s again." % (loopstate.fold_command(loop, harness), command),
        )
    root = loop.root
    out = Output()
    for name, value in (("Base branch", loop.base), ("Feature branch", loop.branch), ("PR", loop.pr)):
        out.line("%s: %s" % (name, value))
    found = conventions.template(root)
    if found:
        out.line("Template: %s" % found)
    else:
        out.line("Template: none.")
        if loop.pr != NO_PR:
            try:
                print_history(out, conventions.history(root))
            except Refused as error:
                raise refusal(error.call, command,
                              "tell the user %s was refused, and stop." % gitcmd.call_text(error.call))
    path = paths(loop, command)
    print_path(out, path)
    return out.finish(ending(loop, harness, path))


def ending(loop: loopfile.Loop, harness: Harness, path: Path) -> str:
    """The one PR-Author ending for the loop's PR: line and the path."""
    if path.name == NO_PR:
        return loopstate.pr_step(loop)
    pr_body = prbody.relative(loop)
    assemble = "Write the title and body to %s as your skill says" % pr_body
    leave = ("run %s and stop; push nothing"
             % catalog.line("loop", "close", slug=loop.slug, write=True))
    if path.name == MANUAL:
        return "%s, then %s." % (assemble, leave)
    if path.name == NEITHER:
        failed = "; ".join("%s: %s" % (found.name, found.why) for found in path.failed())
        return ("%s. No PR can be opened from here, so ask nothing: tell the user the check that failed (%s), then %s."
                % (assemble, failed, leave))
    if path.name == PUSH_ONLY:
        failed = path.failed()
        why = failed[0].why if failed else "the open-a-PR check failed"
        return ("%s, then show the user the title and body and ask one question: push the branch so they can open "
                "the PR themselves (gh cannot open it here: %s), or leave it to them. On push, write any amendment "
                "back to %s, run %s and do what its Next: line says; on leave, %s."
                % (assemble, why, pr_body, open_command(loop, harness, PUSH_ONLY), leave))
    confirm = ("show the user the title and body and wait for one confirmation before any push, writing an "
               "amendment back to %s; then run %s and do what its Next: line says"
               % (pr_body, open_command(loop, harness, path.name)))
    if path.name == EXISTING:
        confirm = ("tell the user a PR is already open for the branch, %s, and the push adds the new commits to it; "
                   "%s" % (path.url, confirm))
    if loop.pr == "ask at sign-off":
        return ("%s, then ask the user whether to open the PR or leave it to them. On leave, %s. On open, %s."
                % (assemble, leave, confirm))
    return "%s, then %s." % (assemble, confirm)


# --- open ---

def changed(path: Path, wanted: str) -> str:
    """What the re-check found, for a path other than the one confirmed."""
    if path.name == EXISTING:
        return "a PR is now open for the branch: %s" % path.url
    failed = dict((found.name, found.why) for found in path.failed())
    if "can push" in failed:
        return "the push check now fails: %s" % failed["can push"]
    if path.name == PUSH_ONLY:
        return "the open-a-PR check now fails: %s" % failed.get("can open a PR", "")
    if path.name == OPEN and wanted == PUSH_ONLY:
        return "the open-a-PR check now passes, so the path is open"
    return "the path is now %s" % path.name


def told(text: str) -> str:
    return TELL % one_line(text)


def open_plan(loop: loopfile.Loop, state: loopstate.State, harness: Harness, wanted: str) -> runner.Plan:
    """pr open as a plan: the push, on the open path the PR's creation, then
    the loop's close. The fold, pr-body.md and the path are its
    precondition, checked alike by the dry run and the write."""
    if fold_owed(loop, state):
        raise Failure(
            "The fold's outcome is not recorded for the code Sign-off: the branch is pushed only after the Sign-off "
            "and the fold. Nothing was pushed.",
            "Stop, and tell the user the fold has not run; the Orchestrator runs %s at the code Sign-off."
            % loopstate.fold_command(loop, harness),
        )
    found = prbody.read(loop)
    if found.problem is not None:
        raise Failure(
            "%s %s. Nothing was pushed." % (prbody.relative(loop), BODY_PROBLEMS[found.problem]),
            "Write %s with your file tool: the title as the first line, a blank line, then the body, as the user "
            "confirmed them. Then run the same command again." % prbody.relative(loop),
        )
    title, text = found.title, found.body
    command = open_command(loop, harness, wanted)
    path = paths(loop, command)
    if path.name != wanted:
        raise Failure(["The path is no longer %s: %s. Nothing was pushed." % (wanted, changed(path, wanted)),
                       told("Nothing was pushed: %s." % changed(path, wanted))],
                      "Relay the line above, then run %s and go on with the path it prints."
                      % check_command(loop, harness))
    branch, base, remote = loop.branch, loop.base, path.remote
    pr_body = prbody.relative(loop)

    def push() -> list[str]:
        pushed = gitcmd.run(loop.root, ["git", "push", "-u", remote, branch], timeout=PUSH_TIMEOUT_SECONDS)
        if pushed.refused:
            raise refusal(pushed, command, "tell the user git push was refused, and stop.")
        if pushed.code != 0:
            raise Failure(["git push -u %s %s failed: %s" % (remote, branch, pushed.first_error()),
                           "No PR was opened; the loop stays open, and %s stays." % pr_body,
                           told("The push of %s failed: %s" % (branch, pushed.first_error()))],
                          "Relay the line above and wait for the user to fix it; when they say it is fixed, run %s"
                          % command)
        return ["Pushed %s to %s." % (branch, remote)]

    def create() -> list[str]:
        created = gitcmd.run(loop.root, ["gh", "pr", "create", "--head", branch, "--base", base, "--title", title,
                                         "--body-file", "-"], data=text.encode("utf-8"), timeout=TIMEOUT_SECONDS)
        if created.refused:
            raise refusal(created, command, "tell the user gh pr create was refused, and stop.",
                          "%s is pushed; no PR was opened, and the loop stays open." % branch)
        if created.code != 0:
            return ["gh pr create failed after the push: %s" % created.first_error(),
                    told("The branch %s is pushed, but gh pr create failed: %s. Open the PR with the title and body "
                         "in %s." % (branch, created.first_error(), pr_body))]
        found = [line.strip() for line in created.out.split("\n") if line.strip()]
        return [told("Opened the PR: %s" % (found[-1] if found else "(gh printed no URL)"))]

    if wanted == EXISTING:
        after = told("Pushed %s to %s: the PR %s has the new commits." % (branch, remote, path.url))
    elif wanted == PUSH_ONLY:
        failed = path.failed()
        after = told("Pushed %s to %s. gh cannot open the PR here (%s): open it in the web UI with the title and "
                     "body in %s." % (branch, remote, failed[0].why if failed else "the open-a-PR check failed",
                                      pr_body))
    what = {OPEN: " and open the PR into %s" % base, EXISTING: ", to the PR %s" % path.url}.get(wanted, "")
    effects: list[runner.Effect] = [
        runner.Step(push, dry=["Would push %s to %s%s, then close the loop." % (branch, remote, what)], keep=True),
        runner.Step(create, keep=True) if wanted == OPEN else runner.Effect(done=[after], keep=True),
    ]

    def refuse(error: OSError) -> Failure:
        return refused("Could not close the loop %s: %s" % (loop.slug, textfile.reason(error)),
                       "Otherwise tell the user the loop could not be closed, and stop.")

    effects += runner.close(state, done=[runner.closed_line(loop.slug)], refuse=refuse)
    return runner.Plan(effects, "Relay the line above and stop.", dry_next="Run %s" % command)
