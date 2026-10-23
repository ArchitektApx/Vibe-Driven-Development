"""loop new: its questions, a leftover tracker directory with the work it
holds, and the preflight warning for PR: yes."""

from __future__ import annotations

import os
from typing import Any

from .. import catalog, gitcmd, loopfile, loopstate, preflight, textfile, workfile
from ..harness import Harness
from ..out import Failure, Output
from .loop import ANSWERS, check_answers


def new(root: str, ctx: catalog.Context, harness: Harness) -> int:
    values = ctx.values
    loopfile.refuse_root(root)
    slug = values["slug"]
    loopfile.check_slug(slug)
    check_answers(values, ANSWERS)
    out = Output()
    leftover, state = loopfile.look(root, slug)
    continuing = check_leftover(slug, leftover, values["leftover"])
    if continuing and leftover == loopfile.NO_STATE:
        # look() reads a state file only beside a Loop file; one without it
        # is read here, so a newer format version refuses before anything is
        # written, and a readable one is reopened.
        state = loopfile.readable(loopfile.tracker_dir(root, slug))
    if leftover == loopstate.OPEN and continuing:
        out.line("Continuing the open loop %s: every file in .scratch/%s/ stays as it is. Nothing was written."
                 % (slug, slug))
        return out.finish(
            "This Session is the Planner: invoke vdd-planner now, and pass --slug %s on every VDD tool call."
            % slug
        )
    if leftover is not None and not continuing:
        return report_leftover(root, slug, leftover, values["write"], out)
    base = values["base"]
    if not base:
        base = gitcmd.current_branch(root)
        if not base:
            out.line("Base branch: unknown. HEAD is detached, or this is not a git repository, so the tool "
                     "does not guess it.")
            out.line("Nothing was written.")
            return out.finish(
                "Ask the user which branch the loop branches from, then run the same command again with "
                "--base <branch>.",
                1 if values["write"] else 0,
            )
        source = "the checked-out branch"
    else:
        source = "--base"
    branch = values["branch"] or slug
    if branch == base:
        raise Failure(
            "The feature branch %s equals the base branch. Every review diffs <base>...HEAD, so the two must "
            "differ. Nothing was written." % branch,
            "Ask the user for a feature branch other than %s, then run the command again with --branch "
            "<branch>." % base,
        )
    fields = {
        "Format": str(loopfile.FORMAT),
        "Feature": slug,
        "Base branch": base,
        "Feature branch": branch,
        "Harness": harness.label,
    }
    if values["write"]:
        ctx.require(*(option for option, _ in ANSWERS))
        for option, name in ANSWERS:
            fields[name] = values[option]
        return write_new(root, slug, fields, state, out, continuing)
    out.line("Slug: %s" % slug)
    out.line("Base branch: %s (from %s)." % (base, source))
    out.line("Feature branch: %s%s." % (branch, " (proposed: the slug)" if not values["branch"] else ""))
    out.line("Harness: %s." % fields["Harness"])
    asked = questions(values, branch, base)
    for number, text in enumerate(asked, 1):
        out.line("Question %d, %s" % (number, text))
    command = new_command(slug, harness, base, branch, values)
    if not asked:
        return out.finish("Nothing left to ask. Run: %s" % command)
    return out.finish(
        "Ask the user each Question line above, one at a time and in order, with its answers as written. "
        "Then run: %s" % command
    )


def questions(values: dict[str, Any], branch: str, base: str) -> list[str]:
    asked: list[str] = []
    if not values["branch"]:
        asked.append(
            "feature branch: The feature branch is %s, the slug itself. Keep it, or name another branch, "
            "which must differ from %s. (Another branch: --branch <name>.)" % (branch, base)
        )
    if values["minors"] is None:
        asked.append(
            "Minors: Does an open minor finding hold up Sign-off? Answers, in this order: "
            "\"Leave them\" (--minors leave): a reviewer signs off with the open minors listed. "
            "\"Fix them\" (--minors fix): both Loops run until no minor is open."
        )
    if values["pr"] is None:
        asked.append(
            "PR: Should VDD open the pull request at the end of the Workflow? Answers, in this order: "
            "\"Open it\" (--pr yes). \"Ask at Sign-off\" (--pr \"ask at sign-off\"). "
            "\"Manual\" (--pr manual): VDD prints the body and you open the PR. "
            "\"No PR\" (--pr no): the branch stays local and no body is printed."
        )
    return asked


def new_command(slug: str, harness: Harness, base: str, branch: str, values: dict[str, Any]) -> str:
    """The loop new command that writes this loop, every answer not given
    left as "<answer>" for the Role to fill in."""
    answers = {option: catalog.quoted(values[option]) if values[option] is not None else '"<answer>"'
               for option, _ in ANSWERS}
    return catalog.line("loop", "new", slug=slug, harness=harness.name, base=base, branch=branch,
                        leftover=values["leftover"], **answers, write=True)


def write_new(
    root: str, slug: str, fields: dict[str, str], state: loopstate.State | None, out: Output, continuing: bool = False,
) -> int:
    """Write the Loop file, and reopen state, the readable state file the
    command read, or start a missing or damaged one anew."""
    directory = loopfile.tracker_dir(root, slug)
    if fields["PR"] == "yes":
        warn_preflight(root, fields["Base branch"], out)
    try:
        loopfile.write(directory, fields)
        if state is None:
            loopstate.start_state(directory)
        else:
            loopfile.reopen(state)
    except OSError as error:
        raise textfile.write_refusal("the Loop file in %s/" % textfile.shown(directory), error,
                                     "Otherwise tell the user the Loop file could not be written, and stop.")
    out.line("Written: .scratch/%s/%s, and the loop is open.%s"
             % (slug, loopfile.NAME, " Every other file there stays." if continuing else ""))
    for name in loopfile.ORDER:
        out.line("%s: %s" % (name, fields[name]))
    out.tell("The loop's slug is %s. The Orchestrator's launch line will carry it." % slug)
    out.tell("The Harness is %s. If that is wrong, say so and it will be corrected." % fields["Harness"])
    out.tell("You can ask the Orchestrator to respawn any hosted Role at any round.")
    return out.finish(
        "Relay every Tell the user verbatim line above unchanged; only after doing that, invoke vdd-planner "
        "as your skill says. The loop's slug is %s: pass --slug %s on every VDD tool call from here on." % (slug, slug)
    )


ANSWER_CONTINUE = (
    "\"Continue the earlier Workflow\" (--leftover continue): only when it was interrupted. Every file stays "
    "where it is."
)

ANSWER_FRESH = (
    "\"Start fresh on this slug\" (loop aside, then loop new again): the directory moves to "
    ".scratch/%s-<n>/, closed, and nothing is deleted."
)

ANSWER_OTHER = "\"Use a different slug\" (loop new with the other slug): every file stays where it is."


def check_leftover(slug: str, leftover: str | None, answer: str | None) -> bool:
    """Whether the user's answer continues the leftover; refuses an answer
    its kind does not allow."""
    if answer is None:
        return False
    if leftover is None:
        raise Failure(
            "There is no .scratch/%s/ to continue. Nothing was written." % slug,
            "Run the same command without --leftover.",
        )
    if leftover == loopstate.CLOSED:
        raise Failure(
            ".scratch/%s/ holds a closed loop, and a finished loop is not continued. Nothing was written." % slug,
            "Ask the user again: start fresh on this slug, or use a different slug.",
        )
    return True


def work_left(root: str, slug: str) -> str:
    """The line naming what of a loop's work a leftover tracker directory
    holds, from what is on disk."""
    directory = loopfile.tracker_dir(root, slug)
    found = [name for name in (workfile.SPEC,) if os.path.isfile(os.path.join(directory, name))]
    issues = os.path.join(directory, workfile.ISSUES)
    tickets = [name for name in os.listdir(issues) if name.endswith(".md")] if os.path.isdir(issues) else []
    if tickets:
        found.append("%d Ticket%s in %s" % (len(tickets), "" if len(tickets) == 1 else "s", workfile.ISSUES))
    found += [name for name in workfile.own_files() if os.path.isfile(os.path.join(directory, name))]
    if not found:
        return "It holds no Spec, Tickets or review files. Nothing was written."
    return "It holds %s. Nothing was written." % ", ".join(found)


def report_leftover(root: str, slug: str, leftover: str, write: bool, out: Output) -> int:
    if leftover == loopstate.OPEN:
        out.line(".scratch/%s/ holds an open loop: an earlier Workflow on this slug that did not finish." % slug)
        answers = [ANSWER_CONTINUE, ANSWER_FRESH % slug, ANSWER_OTHER]
    elif leftover == loopstate.CLOSED:
        out.line(".scratch/%s/ holds a closed loop: an earlier Workflow on this slug that finished." % slug)
        answers = [ANSWER_FRESH % slug, ANSWER_OTHER]
    else:
        out.line(".scratch/%s/ exists and holds no loop the VDD tool started: a loop from before this version, "
                 "or a directory another tool made." % slug)
        answers = [ANSWER_CONTINUE + " The questions follow, and the Loop file is written into it.",
                   ANSWER_FRESH % slug, ANSWER_OTHER]
    out.line(work_left(root, slug))
    out.line("Question 1, leftover: Answers, in this order: " + " ".join(answers))
    aside_command = catalog.line("loop", "aside", slug=slug, write=True)
    on_continue = "" if leftover == loopstate.CLOSED else " On continue, run the same command with --leftover continue."
    return out.finish(
        "Ask the user the Question line above, with what each answer does to the files.%s On start fresh, run "
        "%s, then this command again. On a different slug, run %s with that slug."
        % (on_continue, aside_command, catalog.bare("loop", "new")),
        1 if write else 0,
    )


def warn_preflight(root: str, base: str, out: Output) -> None:
    remote, checks = preflight.checks(root, base)
    for check in checks:
        if check.passed:
            out.line("Preflight, %s, remote %s: passed." % (check.name, remote))
        else:
            out.line("Preflight, %s, remote %s: failed (%s)." % (check.name, remote, check.why))
            out.tell(
                "Warning: the %s check failed: %s. The loop goes on; fix it before Sign-off, or the "
                "PR-Author prints the body for you to open the PR." % (check.name, check.why)
            )
