"""The loop command group: the Loop file and the loop's state, written, read,
changed, closed and reopened only here."""

import os

from . import args, loopfile, places, textfile
from .out import Failure, Output, refused

SUBCOMMANDS = ("new", "show", "set")

HELP = [
    "loop new --slug <slug> --harness <h> [--base <branch>] [--branch <branch>] [--minors <a>] [--pr <a>]",
    "         [--fresh-coder <a>] [--write]",
    "  Start a loop. Without --write it checks the slug, reads the base branch, proposes the feature branch",
    "  and prints the questions for the user, changing nothing. Ask them, then run it again with the answers",
    "  and --write: it writes .scratch/<slug>/loop.md and marks the loop open.",
    "",
    "loop show [--slug <slug>] [--role <Role>]",
    "  Print the Loop file's lines as every Role acts on them: a missing or malformed line as its default,",
    "  whether the loop is open or closed, and the Harness file to read. --role prints only the lines that",
    "  Role acts on: Planner, Plan-Reviewer, Coder, Code-Reviewer, Orchestrator or PR-Author.",
    "",
    "loop set [--slug <slug>] [--minors <a>] [--pr <a>] [--fresh-coder <a>] [--harness-line <label>] --write",
    "  Change the Minors:, PR:, Fresh Coder: or Harness: line on the user's word. The feature, the base",
    "  branch and the feature branch never change.",
    "",
    "Accepted values: --minors fix or leave; --pr yes, \"ask at sign-off\", manual or no; --fresh-coder",
    "\"every round\", never or \"over <n>k\"; --harness-line Claude Code, Codex, Cursor, Copilot CLI or Generic.",
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
    "fresh-coder": args.VALUE,
    "harness-line": args.VALUE,
    "role": args.VALUE,
    "write": args.FLAG,
    # Named only to refuse them: a running loop's identity never changes.
    "feature": args.VALUE,
    "base-branch": args.VALUE,
    "feature-branch": args.VALUE,
}

# Option -> Loop file line, for the answers new writes and set changes.
ANSWERS = (("minors", "Minors"), ("pr", "PR"), ("fresh-coder", "Fresh Coder"))
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
        raise Failure(
            [
                "Unknown command: loop %s" % sub,
                "This copy of the VDD tool may be older than the skill that called it: rerun Setup.",
            ],
            "Tell the user this copy of the VDD tool is out of date and to rerun Setup, then retry.",
        )
    values = args.parse(rest, SPEC, usage())
    if values["help"]:
        return run(["--help"])
    harness = args.harness_of(values, usage()) if values["harness"] is not None or sub == "new" else None
    root = os.getcwd()
    if sub == "new":
        return new(root, values, harness)
    if sub == "show":
        return show(root, values)
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
    if loopfile.kind(root, slug) is not None:
        raise Failure(
            ".scratch/%s/ already exists. Nothing was written." % slug,
            "Ask the user for a different slug, then run the command again with it.",
        )
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
        return write_new(root, slug, fields, out)
    out.line("Slug: %s" % slug)
    out.line("Base branch: %s (from %s)." % (base, source))
    out.line("Feature branch: %s%s." % (branch, " (proposed: the slug)" if not values["branch"] else ""))
    out.line("Harness: %s." % fields["Harness"])
    asked = questions(values, harness, branch, base)
    for number, text in enumerate(asked, 1):
        out.line("Question %d, %s" % (number, text))
    command = new_command(slug, harness, base, branch, values)
    if not asked:
        return out.finish("Nothing left to ask. Run: %s --write" % command)
    return out.finish(
        "Ask the user each Question line above, one at a time and in order, with its answers as written. "
        "Then run: %s --write" % command
    )


def questions(values, harness, branch, base):
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
    if values["fresh-coder"] is None:
        asked.append(fresh_coder_question(harness))
    return asked


def fresh_coder_question(harness):
    recommended, limit = harness.fresh_coder()
    answers = [("Every round", "every round"), ("Never", "never")]
    if limit:
        answers.append(("Over a limit, the Coder's context size; the user may name another number", limit))
    parts = []
    for label, value in answers:
        mark = " (recommended)" if value == recommended else ""
        parts.append("\"%s\"%s (--fresh-coder %s)." % (label, mark, quoted(value)))
    return (
        "Fresh Coder: When should the Orchestrator respawn the Coder, spawning it anew for a round in "
        "place of resuming the one before? Answers, in this order: " + " ".join(parts)
    )


def new_command(slug, harness, base, branch, values):
    parts = [places.command(), "loop new", "--slug", slug, "--harness", harness.name, "--base", base,
             "--branch", branch]
    for option, _ in ANSWERS:
        value = values[option]
        parts += ["--" + option, quoted(value) if value is not None else '"<answer>"']
    return " ".join(parts)


def write_new(root, slug, fields, out):
    directory = loopfile.tracker_dir(root, slug)
    try:
        loopfile.write(directory, fields)
        loopfile.append_state(directory, loopfile.OPEN)
    except OSError as error:
        raise refused(
            "Could not write the Loop file in %s: %s" % (directory, error),
            "Otherwise tell the user the Loop file could not be written, and stop.",
        )
    out.line("Written: .scratch/%s/%s, and the loop is open." % (slug, loopfile.NAME))
    for name in loopfile.ORDER:
        out.line("%s: %s" % (name, fields[name]))
    return out.finish(
        "Give the user the closing summary your skill names. The loop's slug is %s: pass --slug %s on every "
        "VDD tool call from here on." % (slug, slug)
    )


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
            "Nothing to set: name --minors, --pr, --fresh-coder or --harness-line.",
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
        if values["harness-line"] is not None and values["fresh-coder"] is None:
            # A changed Harness changes the Fresh Coder question's
            # recommendation and limit, so the question is asked again.
            corrected = args.harness_of({"harness": values["harness-line"]}, usage())
            out.line("Question 1, %s" % fresh_coder_question(corrected))
            parts = [places.command(), "loop set", "--slug", loop.slug]
            for option, _ in changes:
                parts += ["--" + option, quoted(values[option])]
            parts += ["--fresh-coder", '"<answer>"', "--write"]
            return out.finish(
                "Ask the user the Question line above, with its answers as written. Then run: %s" % " ".join(parts)
            )
        return out.finish("Run the same command with --write.")
    try:
        textfile.write(loop.file, ("\n".join(lines) + "\n").encode("utf-8"))
    except OSError as error:
        raise refused(
            "Could not write the Loop file %s: %s" % (loop.relative, error),
            "Otherwise tell the user the Loop file could not be changed, and stop.",
        )
    return out.finish("Go on as your skill says, passing --slug %s." % loop.slug)
