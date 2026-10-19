"""The pr command group: the PR-Author's facts and its one publishing call.

pr check reads only: the PR template, else the repository's merged-PR
history as far as matching its shape needs, the preflight and the
existing-PR check, and the path that follows. Every git and gh call runs
from an argument list, never through a shell, and a call a sandbox refused
is told apart from any other failure.
"""

import json
import os
import re
import shutil

from . import args, gitcmd, loop as loopcommands, loopfile, loopstate, places, preflight
from .out import Failure, Output

SUBCOMMANDS = ("check",)
BODY_NAME = "pr-body.md"
TEMPLATE_DIRS = ("", ".github", "docs")
TEMPLATE_NAMES = ("PULL_REQUEST_TEMPLATE.md", "pull_request_template.md")
ISSUE_LINK = re.compile(r"(^|[^\w&])#[0-9]+\b|\b(close[sd]?|fix(e[sd])?|resolve[sd]?)\b[:\s]+\S*[0-9]+", re.I)
HEADING = re.compile(r"^#{1,6}\s+\S")
TIMEOUT_SECONDS = 60

OPEN = "open"
PUSH_ONLY = "push-only"
NEITHER = "neither"
EXISTING = "existing"
MANUAL = "manual"
NO_PR = "no"

HELP = [
    "pr check --slug <slug> --harness <h>",
    "  The PR-Author's first call after Sign-off. Reads only, and refuses until the code Loop is signed off.",
    "  Prints the PR template (the first of PULL_REQUEST_TEMPLATE.md or pull_request_template.md at the",
    "  repository root, in .github/ or in docs/) or that there is none; with none, the merged-PR history:",
    "  each title, each body's headings, whether the bodies link issues and the newest body whole, or no",
    "  history, or could not read. Unless PR: manual or no, it runs the preflight (can push, can open a PR)",
    "  and the existing-PR check, and prints the path: open, push-only, neither or existing.",
    "",
    "--slug names the loop; pass it on every call. --harness names the Harness this Session runs in.",
    "Run every command from the repository root.",
]

SPEC = {"slug": args.VALUE, "harness": args.VALUE, "path": args.VALUE, "write": args.FLAG}


def usage():
    return "%s pr --help" % places.command()


def run(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        out = Output()
        for line in HELP:
            out.line(line)
        return out.finish("Run the pr command your skill or the last Next: line names.")
    sub, rest = argv[0], argv[1:]
    if sub not in SUBCOMMANDS:
        args.unknown_command("pr " + sub, usage())
    values = args.parse(rest, SPEC, usage())
    if values["help"]:
        return run(["--help"])
    args.require(values, ["slug", "harness"], usage())
    harness = args.harness_of(values, usage())
    loop = loopfile.find(loopfile.project_root(os.getcwd()), values["slug"])
    loopstate.open_loop(loop, "pr %s" % sub)
    loopcommands.require_code_sign_off(loop)
    return check(loop, harness)


class Refused(Exception):
    def __init__(self, call):
        Exception.__init__(self, call.first_error())
        self.call = call


def gh(root, *argv):
    return gitcmd.run(root, ["gh"] + list(argv), env={"GIT_TERMINAL_PROMPT": "0"}, timeout=TIMEOUT_SECONDS)


def call_text(call):
    return " ".join(call.argv[:3])


def refusal(call, command, otherwise):
    """The Failure for a call a sandbox refused inside the tool."""
    return Failure(
        ["A sandbox refused %s inside the tool: %s" % (call_text(call), call.first_error()),
         "Nothing was pushed or written; the loop stays open."],
        "Rerun %s outside the sandbox, the way your Harness grants that; when that is refused too, %s" % (
            command, otherwise),
    )


def check_command(loop, harness):
    return "%s pr check --slug %s --harness %s" % (places.command(), loop.slug, harness.name)


# --- the template and the history ---

def template(root):
    """The repository-relative path of the first PR template, or None. Names
    are matched exactly, so a case-insensitive file system finds the name on
    disk, not the one asked for."""
    for directory in TEMPLATE_DIRS:
        full = os.path.join(root, directory) if directory else root
        try:
            names = set(os.listdir(full))
        except OSError:
            continue
        for name in TEMPLATE_NAMES:
            if name in names and os.path.isfile(os.path.join(full, name)):
                return "%s/%s" % (directory, name) if directory else name
    return None


class History:
    """The merged-PR history: outcome "history", "none" or "unread", the PRs
    (title, body) newest first, and why."""

    def __init__(self, outcome, prs=(), why=""):
        self.outcome = outcome
        self.prs = list(prs)
        self.why = why


def history(root):
    """The history, or Refused."""
    if shutil.which("gh") is None:
        return History("none", why="gh is not on PATH")
    result = gh(root, "pr", "list", "--state", "merged", "--limit", "10", "--json", "title,body")
    if result.refused:
        raise Refused(result)
    if result.code != 0:
        return History("unread", why=result.first_error())
    try:
        data = json.loads(result.out or "[]")
    except ValueError:
        return History("unread", why="gh pr list printed no JSON")
    if not isinstance(data, list):
        return History("unread", why="gh pr list printed no list")
    prs = [(str(item.get("title") or ""), str(item.get("body") or "")) for item in data if isinstance(item, dict)]
    if not prs:
        return History("none", why="no merged PR")
    return History("history", prs)


def headings(body):
    found = []
    fenced = False
    for line in body.replace("\r\n", "\n").split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if not fenced and HEADING.match(line):
            found.append(line.strip())
    return found


# Marks each line of the newest body as quoted data, so a body line such as
# "Next: ..." never reads as the tool's own.
BODY_MARK = "| "


def print_history(out, found):
    if found.outcome == "none":
        out.line("History: none (%s)." % found.why)
        return
    if found.outcome == "unread":
        out.line("History: could not read: %s" % found.why)
        return
    out.line("History: %d merged PR%s, newest first." % (len(found.prs), "" if len(found.prs) == 1 else "s"))
    for number, (title, body) in enumerate(found.prs, 1):
        out.line("PR %d title: %s" % (number, title))
        marks = headings(body)
        out.line("PR %d headings: %s" % (number, " | ".join(marks) if marks else "none"))
    links = any(ISSUE_LINK.search(body) for _, body in found.prs)
    out.line("Bodies link issues: %s." % ("yes" if links else "no"))
    out.line("The newest body, whole, each of its lines after \"%s\", up to the line \"End of the newest body.\":"
             % BODY_MARK.strip())
    for line in found.prs[0][1].replace("\r\n", "\n").split("\n"):
        out.line((BODY_MARK + line).rstrip())
    out.line("End of the newest body.")


# --- the preflight and the path ---

class Path:
    """The path pr check prints: its name, the checks, and the URL of an
    open PR."""

    def __init__(self, name, checks=(), url="", remote=""):
        self.name = name
        self.checks = list(checks)
        self.url = url
        self.remote = remote

    def failed(self):
        return [check for check in self.checks if not check.passed]


def existing_pr(root, branch):
    """The URL of an open PR for the branch, "" for none; Refused on a
    refusal; None when the check fails."""
    result = gh(root, "pr", "list", "--head", branch, "--state", "open", "--json", "url")
    if result.refused:
        raise Refused(result)
    if result.code != 0:
        return None
    try:
        data = json.loads(result.out or "[]")
    except ValueError:
        return None
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and item.get("url"):
            return str(item["url"])
    return ""


def path_of(loop):
    """The Path for the loop's PR: line, or Refused."""
    pr, _ = loop.setting("PR")
    if pr == "manual":
        return Path(MANUAL)
    if pr == "no":
        return Path(NO_PR)
    base, _ = loop.setting("Base branch")
    branch, _ = loop.setting("Feature branch")
    remote, found = preflight.checks(loop.root, base)
    for check in found:
        if check.refused is not None:
            raise Refused(check.refused)
    push, can_open = found
    if not push.passed:
        return Path(NEITHER, found, remote=remote)
    if not can_open.passed:
        return Path(PUSH_ONLY, found, remote=remote)
    url = existing_pr(loop.root, branch)
    if url is None:
        found = [push, preflight.Check("can open a PR", False, "gh pr list --head %s did not exit 0" % branch)]
        return Path(PUSH_ONLY, found, remote=remote)
    if url:
        return Path(EXISTING, found, url=url, remote=remote)
    return Path(OPEN, found, remote=remote)


def print_path(out, path):
    for check in path.checks:
        if check.passed:
            out.line("Preflight, %s, remote %s: passed." % (check.name, path.remote))
        else:
            out.line("Preflight, %s, remote %s: failed (%s)." % (check.name, path.remote, check.why))
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


# --- check ---

def check(loop, harness):
    root = loop.root
    out = Output()
    for name in ("Base branch", "Feature branch", "PR"):
        out.line("%s: %s" % (name, loop.setting(name)[0]))
    found = template(root)
    command = check_command(loop, harness)
    if found:
        out.line("Template: %s" % found)
    else:
        out.line("Template: none.")
        try:
            print_history(out, history(root))
        except Refused as error:
            raise refusal(error.call, command,
                          "tell the user the PR history could not be read, use VDD's default body, and go on as "
                          "your skill says.")
    try:
        path = path_of(loop)
    except Refused as error:
        raise refusal(error.call, command,
                      "tell the user %s was refused, and stop." % call_text(error.call))
    print_path(out, path)
    body = "%s/%s" % (loop.tracker, BODY_NAME)
    if path.name == NO_PR:
        branch, _ = loop.setting("Feature branch")
        return out.finish(
            "Run %s loop close --slug %s --write, then print \"Loop signed off. `PR: no`: `%s` stays local, nothing "
            "pushed.\" and stop." % (places.command(), loop.slug, branch)
        )
    if path.name in (OPEN, PUSH_ONLY):
        return out.finish(
            "Go on with your skill's step for this path: assemble the title and body, write them to %s (the "
            "title, a blank line, the body), show them to the user and wait for their confirmation; to push, run "
            "%s pr open --path %s --slug %s --harness %s --write." % (
                body, places.command(), path.name, loop.slug, harness.name)
        )
    named = {EXISTING: " with the PR's URL", NEITHER: " with the failed check named"}.get(path.name, "")
    return out.finish(
        "Assemble the body as your skill says, write it to %s and print it%s, then run %s loop close --slug %s "
        "--write. Push nothing." % (body, named, places.command(), loop.slug)
    )
