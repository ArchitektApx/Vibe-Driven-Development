"""The loop command group: the Loop file and the loop's state, written, read,
changed, closed and reopened only here."""

import os

from . import args, loopfile, places, preflight, textfile
from .out import Failure, Output, refused

SUBCOMMANDS = ("new", "aside", "show", "set", "close", "reopen")

HELP = [
    "loop new --slug <slug> --harness <h> [--base <branch>] [--branch <branch>] [--minors <a>] [--pr <a>]",
    "         [--leftover continue] [--write]",
    "  Start a loop. Without --write it checks the slug, reads the base branch, proposes the feature branch",
    "  and prints the questions for the user, changing nothing. Ask them, then run it again with the answers",
    "  and --write: it writes .scratch/<slug>/loop.md and marks the loop open. On PR: yes it checks that a",
    "  push and gh would work, and warns without blocking. When .scratch/<slug>/ already exists it reports",
    "  what is there and the answers it allows; the user's continue is --leftover continue.",
    "",
    "loop aside --slug <slug> --write",
    "  Move .scratch/<slug>/ to .scratch/<slug>-<n>/, the lowest free n from 2, closing an open loop first.",
    "  It deletes nothing. The user's start fresh on a leftover tracker directory.",
    "",
    "loop show [--slug <slug>] [--role <Role>]",
    "  Print the Loop file's lines as every Role acts on them: a missing or malformed line as its default,",
    "  whether the loop is open or closed, and the Harness file to read. --role prints only the lines that",
    "  Role acts on: Planner, Plan-Reviewer, Coder, Code-Reviewer, Orchestrator or PR-Author.",
    "",
    "loop set [--slug <slug>] [--minors <a>] [--pr <a>] [--harness-line <label>] --write",
    "  Change the Minors:, PR: or Harness: line on the user's word. The feature, the base branch and the",
    "  feature branch never change.",
    "",
    "loop close [--slug <slug>] --write",
    "  Close the loop: it stays on disk as the record, a ring or a wait on it is refused, and its Codex armed",
    "  files are deleted. The PR-Author and the Orchestrator run it at the end of the Workflow.",
    "",
    "loop reopen [--slug <slug>] --write",
    "  Reopen a closed loop, on the user's request.",
    "",
    "Accepted values: --minors fix or leave; --pr yes, \"ask at sign-off\", manual or no; --harness-line",
    "Claude Code, Codex, Cursor, Copilot CLI or Generic.",
    "",
    "--slug names the loop. Without it the tool takes the loop whose feature branch is checked out, else the",
    "only open loop, else it refuses. A Role passes --slug on every call. --harness names the Harness this",
    "Session runs in (claude-code, codex, cursor, copilot-cli or generic) and never changes the Loop file.",
    "Run every command from the repository root.",
]

SPEC = {
    "slug": args.VALUE,
    "harness": args.VALUE,
    "base": args.VALUE,
    "branch": args.VALUE,
    "minors": args.VALUE,
    "pr": args.VALUE,
    "harness-line": args.VALUE,
    "role": args.VALUE,
    "leftover": args.VALUE,
    "write": args.FLAG,
    # Named only to refuse them: a running loop's identity never changes.
    "feature": args.VALUE,
    "base-branch": args.VALUE,
    "feature-branch": args.VALUE,
}

# Option -> Loop file line, for the answers new writes and set changes.
ANSWERS = (("minors", "Minors"), ("pr", "PR"))
SETTABLE = ANSWERS + (("harness-line", "Harness"),)


def usage():
    return "%s loop --help" % places.command()


def run(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        out = Output()
        for line in HELP:
            out.line(line)
        return out.finish("Run the loop command your skill or the last Next: line names.")
    sub, rest = argv[0], argv[1:]
    if sub not in SUBCOMMANDS:
        args.unknown_command("loop " + sub, usage())
    values = args.parse(rest, SPEC, usage())
    if values["help"]:
        return run(["--help"])
    harness = args.harness_of(values, usage()) if values["harness"] is not None or sub == "new" else None
    root = loopfile.project_root(os.getcwd())
    if sub == "new":
        return new(root, values, harness)
    if sub == "aside":
        return aside(root, values)
    if sub == "show":
        return show(root, values)
    if sub in ("close", "reopen"):
        return close_or_reopen(root, values, sub)
    return set_lines(root, values)


def check_answers(values, options):
    for option, name in options:
        value = values.get(option)
        if value is not None and not loopfile.accepted(name, value):
            raise Failure(
                "--%s %s is not a value the %s: line accepts. It takes %s."
                % (option, value, name, loopfile.accepted_text(name)),
                "Ask the user again with the accepted answers, then run the command with one of them.",
            )


def quoted(value):
    return '"%s"' % value if " " in value else value


# --- new ---

def new(root, values, harness):
    loopfile.refuse_root(root)
    slug = values["slug"]
    args.require(values, ["slug"], usage())
    loopfile.check_slug(slug)
    check_answers(values, ANSWERS)
    out = Output()
    leftover = loopfile.kind(root, slug)
    continuing = check_leftover(slug, leftover, values["leftover"])
    if leftover == loopfile.OPEN and continuing:
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
        base = loopfile.current_branch(root)
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
        "Harness": loopfile.LABELS[harness.name],
    }
    if values["write"]:
        args.require(values, [option for option, _ in ANSWERS], usage())
        for option, name in ANSWERS:
            fields[name] = values[option]
        return write_new(root, slug, fields, out, continuing)
    out.line("Slug: %s" % slug)
    out.line("Base branch: %s (from %s)." % (base, source))
    out.line("Feature branch: %s%s." % (branch, " (proposed: the slug)" if not values["branch"] else ""))
    out.line("Harness: %s." % fields["Harness"])
    asked = questions(values, branch, base)
    for number, text in enumerate(asked, 1):
        out.line("Question %d, %s" % (number, text))
    command = new_command(slug, harness, base, branch, values)
    if not asked:
        return out.finish("Nothing left to ask. Run: %s --write" % command)
    return out.finish(
        "Ask the user each Question line above, one at a time and in order, with its answers as written. "
        "Then run: %s --write" % command
    )


def questions(values, branch, base):
    asked = []
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


def new_command(slug, harness, base, branch, values):
    parts = [places.command(), "loop new", "--slug", slug, "--harness", harness.name, "--base", base,
             "--branch", branch]
    if values["leftover"]:
        parts += ["--leftover", values["leftover"]]
    for option, _ in ANSWERS:
        value = values[option]
        parts += ["--" + option, quoted(value) if value is not None else '"<answer>"']
    return " ".join(parts)


def write_new(root, slug, fields, out, continuing=False):
    directory = loopfile.tracker_dir(root, slug)
    new_state = loopfile.needs_new_state(directory)
    if fields["PR"] == "yes":
        warn_preflight(root, fields["Base branch"], out)
    try:
        loopfile.write(directory, fields)
        if new_state:
            loopfile.start_state(directory)
        else:
            loopfile.append_state(directory, loopfile.OPEN)
    except OSError as error:
        raise refused(
            "Could not write the Loop file in %s: %s" % (directory, error),
            "Otherwise tell the user the Loop file could not be written, and stop.",
        )
    out.line("Written: .scratch/%s/%s, and the loop is open.%s"
             % (slug, loopfile.NAME, " Every other file there stays." if continuing else ""))
    for name in loopfile.ORDER:
        out.line("%s: %s" % (name, fields[name]))
    return out.finish(
        "Give the user the closing summary your skill names. The loop's slug is %s: pass --slug %s on every "
        "VDD tool call from here on." % (slug, slug)
    )


# --- a leftover tracker directory ---

ANSWER_CONTINUE = (
    "\"Continue the earlier Workflow\" (--leftover continue): only when it was interrupted. Every file stays "
    "where it is."
)
ANSWER_FRESH = (
    "\"Start fresh on this slug\" (loop aside, then loop new again): the directory moves to "
    ".scratch/%s-<n>/, closed, and nothing is deleted."
)
ANSWER_OTHER = "\"Use a different slug\" (loop new with the other slug): every file stays where it is."


def check_leftover(slug, leftover, answer):
    """Whether the user's answer continues the leftover; refuses an answer
    its kind does not allow."""
    if answer is None:
        return False
    if answer != "continue":
        raise Failure("--leftover takes continue.", "Run %s for this command's usage." % usage())
    if leftover is None:
        raise Failure(
            "There is no .scratch/%s/ to continue. Nothing was written." % slug,
            "Run the same command without --leftover.",
        )
    if leftover == loopfile.CLOSED:
        raise Failure(
            ".scratch/%s/ holds a closed loop, and a finished loop is not continued. Nothing was written." % slug,
            "Ask the user again: start fresh on this slug, or use a different slug.",
        )
    return True


def work_left(root, slug):
    """The line naming what of a loop's work a leftover tracker directory
    holds, from what is on disk."""
    directory = loopfile.tracker_dir(root, slug)
    found = [name for name in ("spec.md",) if os.path.isfile(os.path.join(directory, name))]
    issues = os.path.join(directory, "issues")
    tickets = [name for name in os.listdir(issues) if name.endswith(".md")] if os.path.isdir(issues) else []
    if tickets:
        found.append("%d Ticket%s in issues/" % (len(tickets), "" if len(tickets) == 1 else "s"))
    found += [name for name in ("PLAN-REVIEW.md", "FIXES.md", "CODEREVIEW.md")
              if os.path.isfile(os.path.join(directory, name))]
    if not found:
        return "It holds no Spec, Tickets or review files. Nothing was written."
    return "It holds %s. Nothing was written." % ", ".join(found)


def report_leftover(root, slug, leftover, write, out):
    if leftover == loopfile.OPEN:
        out.line(".scratch/%s/ holds an open loop: an earlier Workflow on this slug that did not finish." % slug)
        answers = [ANSWER_CONTINUE, ANSWER_FRESH % slug, ANSWER_OTHER]
    elif leftover == loopfile.CLOSED:
        out.line(".scratch/%s/ holds a closed loop: an earlier Workflow on this slug that finished." % slug)
        answers = [ANSWER_FRESH % slug, ANSWER_OTHER]
    else:
        out.line(".scratch/%s/ exists and holds no loop the VDD tool started: a loop from before this version, "
                 "or a directory another tool made." % slug)
        answers = [ANSWER_CONTINUE + " The questions follow, and the Loop file is written into it.",
                   ANSWER_FRESH % slug, ANSWER_OTHER]
    out.line(work_left(root, slug))
    out.line("Question 1, leftover: Answers, in this order: " + " ".join(answers))
    aside_command = "%s loop aside --slug %s --write" % (places.command(), slug)
    on_continue = "" if leftover == loopfile.CLOSED else " On continue, run the same command with --leftover continue."
    return out.finish(
        "Ask the user the Question line above, with what each answer does to the files.%s On start fresh, run "
        "%s, then this command again. On a different slug, run loop new with that slug."
        % (on_continue, aside_command),
        1 if write else 0,
    )


def warn_preflight(root, base, out):
    remote, checks = preflight.run(root, base)
    for name, passed, why in checks:
        if passed:
            out.line("Preflight, %s, remote %s: passed." % (name, remote))
        else:
            out.line("Preflight, %s, remote %s: failed (%s)." % (name, remote, why))
            out.tell(
                "Warning: the %s check failed: %s. The loop goes on; fix it before Sign-off, or the "
                "PR-Author prints the body for you to open the PR." % (name, why)
            )


# --- aside ---

def aside(root, values):
    loopfile.refuse_root(root)
    args.require(values, ["slug"], usage())
    slug = values["slug"]
    loopfile.check_slug(slug)
    leftover = loopfile.kind(root, slug)
    if leftover is None:
        raise Failure(
            ".scratch/%s/ does not exist: nothing to move aside." % slug,
            "Run loop new for the slug instead.",
        )
    number = 2
    while os.path.lexists(loopfile.tracker_dir(root, "%s-%d" % (slug, number))):
        number += 1
    target = "%s-%d" % (slug, number)
    out = Output()
    closing = leftover == loopfile.OPEN
    if not values["write"]:
        out.line("Would move .scratch/%s/ to .scratch/%s/%s." % (
            slug, target, ", closing its open loop first" if closing else ""))
        return out.finish("Run the same command with --write.")
    directory = loopfile.tracker_dir(root, slug)
    try:
        if closing:
            loopfile.append_state(directory, loopfile.CLOSED)
            for name in loopfile.delete_armed(directory):
                out.line("Deleted the Codex armed file %s." % name)
            out.line("Closed the loop %s." % slug)
        os.rename(directory, loopfile.tracker_dir(root, target))
    except OSError as error:
        raise refused(
            "Could not move .scratch/%s/ aside: %s" % (slug, error),
            "Otherwise tell the user the directory could not be moved, and stop.",
        )
    out.line("Moved: .scratch/%s/ is now .scratch/%s/. Nothing was deleted." % (slug, target))
    out.tell("The earlier Workflow's files are now in .scratch/%s/." % target)
    return out.finish("Run loop new for %s again, as your skill says." % slug)


# --- show ---

def show(root, values):
    loop = loopfile.find(root, values["slug"])
    role = values["role"]
    if role is not None and role not in loopfile.ROLES:
        raise Failure(
            "--role takes one of: %s." % ", ".join(loopfile.ROLES),
            "Run the command again with your Role's name.",
        )
    names = loopfile.ROLES[role] if role else loopfile.IDENTITY + loopfile.SETTINGS
    out = Output()
    out.line("Slug: %s" % loop.slug)
    out.line("State: %s" % loop.state())
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


# --- set ---

def set_lines(root, values):
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
            "Run %s for this command's usage." % usage(),
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
    try:
        textfile.write(loop.file, ("\n".join(lines) + "\n").encode("utf-8"))
    except OSError as error:
        raise refused(
            "Could not write the Loop file %s: %s" % (loop.relative, error),
            "Otherwise tell the user the Loop file could not be changed, and stop.",
        )
    return out.finish("Go on as your skill says, passing --slug %s." % loop.slug)


# --- close and reopen ---

def close_or_reopen(root, values, sub):
    loop = loopfile.find(root, values["slug"])
    target = loopfile.CLOSED if sub == "close" else loopfile.OPEN
    out = Output()
    if loop.state() == target:
        out.line("The loop %s is already %s. Nothing was written." % (loop.slug, target))
        return out.finish("Go on as your skill says, passing --slug %s." % loop.slug)
    if not values["write"]:
        out.line("Would mark the loop %s %s." % (loop.slug, target))
        return out.finish("Run the same command with --write.")
    try:
        loopfile.append_state(loop.dir, target)
        if target == loopfile.CLOSED:
            for name in loopfile.delete_armed(loop.dir):
                out.line("Deleted the Codex armed file %s." % name)
    except OSError as error:
        raise refused(
            "Could not change the loop state file in .scratch/%s/: %s" % (loop.slug, error),
            "Otherwise tell the user the loop could not be marked %s, and stop." % target,
        )
    if target == loopfile.CLOSED:
        out.line("Closed: the loop %s. Its files stay in .scratch/%s/ as the record." % (loop.slug, loop.slug))
    else:
        out.line("Reopened: the loop %s is open again." % loop.slug)
    return out.finish("Go on as your skill says, passing --slug %s." % loop.slug)
