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

from . import args, fold, gitcmd, loop as loopcommands, loopfile, loopstate, places, preflight, textfile
from .gitcmd import Refused
from .out import Failure, Output, refused

SUBCOMMANDS = ("check", "open")
BODY_NAME = "pr-body.md"
TEMPLATE_DIRS = ("", ".github", "docs")
TEMPLATE_NAMES = ("PULL_REQUEST_TEMPLATE.md", "pull_request_template.md")
ISSUE_LINK = re.compile(r"(^|[^\w&])#[0-9]+\b|\b(close[sd]?|fix(e[sd])?|resolve[sd]?)\b[:\s]+\S*[0-9]+", re.I)
HEADING = re.compile(r"^#{1,6}\s+\S")
TIMEOUT_SECONDS = 60
# A push uploads the branch's objects, so it gets longer than a gh call.
PUSH_TIMEOUT_SECONDS = 600

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
    "pr open --path <open|push-only> --slug <slug> --harness <h> --write",
    "  After the user confirmed the title and body in .scratch/<slug>/pr-body.md (the title, a blank line, the",
    "  body). --path is the path pr check printed. Refuses before the fold's outcome is recorded and on a",
    "  malformed pr-body.md. Runs the preflight and the existing-PR check again and pushes nothing when they",
    "  give another path. Pushes with git push -u <remote> <feature branch>; on the open path runs gh pr",
    "  create with the title as an argument and the body on standard input; closes the loop. A failed push",
    "  leaves the loop open; a refused call asks for a rerun outside the sandbox.",
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
    loop = loopfile.find(gitcmd.project_root(os.getcwd()), values["slug"])
    loopstate.open_loop(loop, "pr %s" % sub)
    loopcommands.require_code_sign_off(loop)
    if sub == "open":
        return open_pr(loop, harness, values["path"], values["write"])
    return check(loop, harness)


def gh(root, *argv):
    return gitcmd.run(root, ["gh"] + list(argv), timeout=TIMEOUT_SECONDS)


def call_text(call):
    return " ".join(call.argv[:3])


def refusal(call, command, otherwise, what="Nothing was pushed or written; the loop stays open."):
    """The Failure for a call a sandbox refused inside the tool; what says
    what happened before it."""
    return Failure(
        ["A sandbox refused %s inside the tool: %s" % (call_text(call), call.first_error()), what],
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
            raise refusal(error.call, command, "tell the user %s was refused, and stop." % call_text(error.call))
    try:
        path = path_of(loop)
    except Refused as error:
        raise refusal(error.call, command,
                      "tell the user %s was refused, and stop." % call_text(error.call))
    print_path(out, path)
    if path.name == NO_PR:
        return out.finish(fold.pr_step(loop))
    return out.finish(
        "Assemble the title and body as your skill's step 3 says and write them to %s/%s, then go on from its "
        "step 4 (the PR: line)." % (loop.tracker, BODY_NAME)
    )


# --- open ---

def open_command(loop, harness, path):
    return "%s pr open --path %s --slug %s --harness %s --write" % (places.command(), path, loop.slug, harness.name)


def read_body(loop):
    """(title, body) from pr-body.md, or a Failure naming what is wrong."""
    relative = "%s/%s" % (loop.tracker, BODY_NAME)
    text = textfile.read(os.path.join(loop.dir, BODY_NAME))
    problem = None
    if text is None:
        problem = "%s does not exist" % relative
    else:
        lines = text.split("\n")
        if not title_of(lines[0]):
            problem = "%s has no title on its first line" % relative
        elif len(lines) < 2 or lines[1].strip():
            problem = "%s has no blank second line between the title and the body" % relative
        elif not "\n".join(lines[2:]).strip():
            problem = "%s has no body after the blank line" % relative
    if problem:
        raise Failure(
            "%s. Nothing was pushed." % problem,
            "Write %s with your file tool: the title as the first line, a blank line, then the body, as the user "
            "confirmed them. Then run the same command again." % relative,
        )
    lines = text.split("\n")
    body = "\n".join(lines[2:]).strip("\n") + "\n"
    return title_of(lines[0]), body


def title_of(line):
    """The title line as plain text: a Markdown heading's "# " is not part of
    the title."""
    return re.sub(r"^#{1,6}\s+", "", line.strip()).strip()


def changed(path, wanted):
    """What the re-check found, for a path other than the one confirmed."""
    if path.name == EXISTING:
        return "a PR is now open for the branch: %s" % path.url
    failed = dict((check.name, check.why) for check in path.failed())
    if "can push" in failed:
        return "the push check now fails: %s" % failed["can push"]
    if path.name == PUSH_ONLY:
        return "the open-a-PR check now fails: %s" % failed.get("can open a PR", "")
    if path.name == OPEN and wanted == PUSH_ONLY:
        return "the open-a-PR check now passes, so the path is open"
    return "the path is now %s" % path.name


def close(loop, out):
    try:
        loopstate.append_state(loop.dir, loopstate.CLOSED)
        for name in loopfile.delete_armed(loop.dir):
            out.line("Deleted the Codex armed file %s." % name)
    except OSError as error:
        raise refused(
            "Could not close the loop %s: %s" % (loop.slug, error),
            "Otherwise tell the user the loop could not be closed, and stop.",
        )
    out.line("Closed: the loop %s. Its files stay in %s/ as the record." % (loop.slug, loop.tracker))


def open_pr(loop, harness, wanted, write):
    if wanted not in (OPEN, PUSH_ONLY):
        raise Failure(
            "--path takes open or push-only: the path pr check printed.",
            "Run %s pr check --slug %s --harness %s, and copy the path from its Path: line." % (
                places.command(), loop.slug, harness.name),
        )
    state = loopstate.State(loop.dir)
    if state.fold_outcome() is None:
        raise Failure(
            "The fold's outcome is not recorded: the branch is pushed only after the code Sign-off and the fold. "
            "Nothing was pushed.",
            "Stop, and tell the user the fold has not run; the Orchestrator runs %s loop fold --slug %s --harness "
            "%s --write at the code Sign-off." % (places.command(), loop.slug, harness.name),
        )
    title, body = read_body(loop)
    command = open_command(loop, harness, wanted)
    try:
        path = path_of(loop)
    except Refused as error:
        raise refusal(error.call, command, "tell the user %s was refused, and stop." % call_text(error.call))
    out = Output()
    if path.name != wanted:
        out.line("The path is no longer %s: %s. Nothing was pushed." % (wanted, changed(path, wanted)))
        out.tell("Nothing was pushed: %s." % changed(path, wanted))
        return out.finish(
            "Relay the line above, then run %s pr check --slug %s --harness %s and go on with the path it prints."
            % (places.command(), loop.slug, harness.name), 1)
    branch, _ = loop.setting("Feature branch")
    base, _ = loop.setting("Base branch")
    if not write:
        out.line("Would push %s to %s%s, then close the loop." % (
            branch, path.remote, " and open the PR into %s" % base if wanted == OPEN else ""))
        return out.finish("Run %s" % command)
    push = gitcmd.run(loop.root, ["git", "push", "-u", path.remote, branch],
                      timeout=PUSH_TIMEOUT_SECONDS)
    if push.refused:
        raise refusal(push, command, "tell the user git push was refused, and stop.")
    if push.code != 0:
        out.line("git push -u %s %s failed: %s" % (path.remote, branch, push.first_error()))
        out.line("No PR was opened; the loop stays open, and %s/%s stays." % (loop.tracker, BODY_NAME))
        out.tell("The push of %s failed: %s" % (branch, push.first_error()))
        return out.finish(
            "Relay the line above and wait for the user to fix it; when they say it is fixed, run %s" % command, 1)
    out.line("Pushed %s to %s." % (branch, path.remote))
    if wanted == PUSH_ONLY:
        failed = path.failed()
        close(loop, out)
        out.tell("Pushed %s to %s. gh cannot open the PR here (%s): open it in the web UI with the title and body "
                 "in %s/%s." % (branch, path.remote, failed[0].why if failed else "the open-a-PR check failed",
                                loop.tracker, BODY_NAME))
        return out.finish("Relay the line above and stop.")
    created = gitcmd.run(loop.root, ["gh", "pr", "create", "--head", branch, "--base", base, "--title", title,
                                     "--body-file", "-"], data=body.encode("utf-8"),
                         timeout=TIMEOUT_SECONDS)
    if created.refused:
        raise refusal(created, command, "tell the user gh pr create was refused, and stop.",
                      "%s is pushed; no PR was opened, and the loop stays open." % branch)
    if created.code != 0:
        out.line("gh pr create failed after the push: %s" % created.first_error())
        close(loop, out)
        out.tell("The branch %s is pushed, but gh pr create failed: %s. Open the PR with the title and body in "
                 "%s/%s." % (branch, created.first_error(), loop.tracker, BODY_NAME))
        return out.finish("Relay the line above and stop.")
    url = [line.strip() for line in created.out.split("\n") if line.strip()]
    url = url[-1] if url else "(gh printed no URL)"
    close(loop, out)
    out.tell("Opened the PR: %s" % url)
    return out.finish("Relay the line above and stop.")
