"""Setup's checks, in the order they print, each filling the run's report."""

from __future__ import annotations

import json
import os
import re

from .. import gitcmd, loopfile, places, stores, textfile
from ..harness import Harness, codex as codex_harness
from . import borrowed_check, install
from .codex import hooks, trust, trust_check
from .report import Report

RETIRED = ("PLAN.md", "PLAN-REVIEW.md", "FIXES.md", "CODEREVIEW.md")
SCRATCH_ENTRIES = (".scratch/", "/.scratch/", ".scratch", "/.scratch")
MIGRATION_URL = "https://github.com/ArchitektApx/Vibe-Driven-Development/blob/master/CHANGELOG.md#migrating-from-014"


def run(report: Report, harness: Harness, cwd: str, listed: str, glossary_named: str,
        user_answer: str | None, hook_answer: str | None) -> None:
    borrowed_check.check(report, harness, cwd, listed, glossary_named, user_answer)
    tracker(report, harness, cwd)
    glossary_rename(report, cwd)
    git_repository(report, cwd)
    gitignore(report, cwd)
    root_loop_file(report, cwd)
    shared_copy(report)
    if harness.waits_through_stop_hook():
        codex(report, cwd, hook_answer)


# --- the tracker ---

def tracker(report: Report, harness: Harness, cwd: str) -> None:
    out = report.out
    name = "docs/agents/issue-tracker.md"
    text = report.read(os.path.join(cwd, *name.split("/")), name)
    if text is None:
        out.line("Tracker: docs/agents/issue-tracker.md is missing.")
        out.tell(
            "Invoke %s and pick Local markdown when it asks which tracker to use. Until then the "
            "Planner (to-spec, to-tickets) and the Code-Reviewer (code-review) are blocked."
            % harness.borrowed_skill("setup-matt-pocock-skills")
        )
        return
    lowered = text.lower()
    if "local markdown" in lowered or ".scratch/" in lowered:
        out.line("Tracker: docs/agents/issue-tracker.md configures local markdown. Passed.")
        return
    out.line("Tracker: docs/agents/issue-tracker.md is configured. Passed.")
    out.tell(
        "Your tracker is not local markdown. VDD works with any tracker the collection supports, "
        "but its Roles are written for local markdown under .scratch/<slug>/."
    )


# --- a repository set up before the glossary rename ---

def glossary_rename(report: Report, cwd: str) -> None:
    exists = lambda *p: os.path.isfile(os.path.join(cwd, *p))  # noqa: E731
    domain = report.read(os.path.join(cwd, "docs", "agents", "domain.md"), "docs/agents/domain.md") or ""
    old_root = exists("CONTEXT.md") or exists("CONTEXT-MAP.md")
    new_root = exists("GLOSSARY.md") or exists("GLOSSARY-MAP.md")
    fires = "CONTEXT.md" in domain or "CONTEXT-MAP.md" in domain or (old_root and not new_root)
    out = report.out
    if not fires:
        out.line("Glossary rename: nothing in this repository to migrate. Passed.")
        return
    out.line("Glossary rename: this repository was set up before it (a warning, not a block).")
    out.tell(
        "Warning: this repository was set up before Matt Pocock's glossary rename (CONTEXT.md is now "
        "GLOSSARY.md, CONTEXT-MAP.md is now GLOSSARY-MAP.md). It does not block the loop. To migrate:"
    )
    moves = [("CONTEXT.md", "GLOSSARY.md"), ("CONTEXT-MAP.md", "GLOSSARY-MAP.md")]
    context_map = report.read(os.path.join(cwd, "CONTEXT-MAP.md"), "CONTEXT-MAP.md") or ""
    for found in re.findall(r"[A-Za-z0-9_./-]*/CONTEXT\.md", context_map):
        path = found[2:] if found.startswith("./") else found
        if path.startswith("/") or ".." in path.split("/"):
            continue
        moves.append((path, path[: -len("CONTEXT.md")] + "GLOSSARY.md"))
    done = set()
    for old, new in moves:
        if old in done or not exists(*old.split("/")):
            continue
        done.add(old)
        if exists(*new.split("/")):
            out.tell("Merge the terms of %s into %s, then remove %s." % (old, new, old))
        else:
            out.tell("git mv %s %s" % (old, new))
    out.tell("Edit docs/agents/domain.md and %s so they name the new files." % setup_section_file(report, cwd))
    out.tell("The full steps: %s" % MIGRATION_URL)


def setup_section_file(report: Report, cwd: str) -> str:
    found = []
    for name in ("AGENTS.md", "CLAUDE.md"):
        text = report.read(os.path.join(cwd, name), name) or ""
        if "docs/agents/" in text or "## Agent skills" in text:
            found.append(name)
    if len(found) == 1:
        return found[0]
    return "AGENTS.md or CLAUDE.md, whichever holds the collection's setup section"


# --- the git repository ---

def git_repository(report: Report, cwd: str) -> None:
    out = report.out
    call = gitcmd.git(cwd, "rev-parse", "--is-inside-work-tree")
    inside = call.ok and call.data.strip() == b"true"
    if call.timed_out is not None:
        out.line("Git repository: %s." % call.first_error())
        out.tell("git did not answer in time: find what holds it, then rerun Setup.")
        return
    if call.code is None:
        out.line("Git repository: git is not installed or cannot run.")
        out.tell("VDD needs git: install it, then rerun Setup.")
        return
    git_version(report, cwd)
    if inside:
        out.line("Git repository: passed.")
        return
    out.line("Git repository: this directory is not one, and the workflow needs one.")
    report.questions.append("Ask the user whether to run git init here; on yes, run it with your own tools.")


def git_version(report: Report, cwd: str) -> None:
    """git 2.40 or newer: the fold at a loop's end needs git merge-tree
    --write-tree --merge-base."""
    out = report.out
    found, text, timed_out = gitcmd.version(cwd)
    if timed_out:
        out.line("git version: %s. Failed." % timed_out)
        out.tell("git did not answer in time: find what holds it, then rerun Setup.")
        return
    if found is None:
        return
    shown = gitcmd.number(text)
    if gitcmd.too_old(found):
        report.git_too_old = shown
        out.line("git version: %s, older than the 2.40 VDD needs. Failed." % shown)
        out.tell("VDD needs git 2.40 or newer, and this machine has git %s: install a newer git, then "
                 "rerun Setup." % shown)
        return
    out.line("git version: %s. Passed." % shown)


# --- .gitignore ---

def gitignore(report: Report, cwd: str) -> None:
    path = os.path.join(cwd, ".gitignore")
    try:
        after, added, removed = plan_gitignore(path)
    except OSError as error:
        report.refuse_read(".gitignore", error)
    if not added and not removed:
        report.out.line(".gitignore: covers .scratch/. Passed.")
        return

    def write() -> list[str]:
        textfile.write(path, after)
        _, again_added, again_removed = plan_gitignore(path)
        if again_added or again_removed:
            raise OSError("the file does not hold the change after the write")
        return [".gitignore: checked."]

    texts = [".gitignore adds %s" % entry for entry in added]
    texts += [".gitignore removes %s, which VDD no longer maintains" % entry for entry in removed]
    report.change(".gitignore", ".gitignore", texts, write)


def plan_gitignore(path: str) -> tuple[bytes, list[str], list[str]]:
    """(after, added, removed): the planned bytes and the entry lists. A line is
    removed only when the whole line, trimmed of surrounding whitespace,
    equals a retired entry: docs/PLAN.md and !PLAN.md are the user's own."""
    try:
        before = textfile.read_bytes(path)
    except FileNotFoundError:
        before = b""
    text = before.decode("utf-8", "surrogateescape")
    # A leading byte order mark is not part of the first line, and a rewrite
    # drops it, as textfile.decode does on every read.
    if text.startswith("\ufeff"):
        text = text[1:]
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(True)
    kept: list[str] = []
    removed: list[str] = []
    for line in lines:
        entry = line.strip()
        if entry in RETIRED:
            removed.append(entry)
            continue
        kept.append(line)
    entries = {line.strip() for line in kept}
    added: list[str] = []
    if not entries & set(SCRATCH_ENTRIES):
        added.append(".scratch/")
    after = "".join(kept)
    if added and after and not after.endswith(("\n", "\r")):
        after += newline
    after += "".join(entry + newline for entry in added)
    return after.encode("utf-8", "surrogateescape"), added, removed


# --- a Loop file from before this version ---

def root_loop_file(report: Report, cwd: str) -> None:
    """A root LOOP.md is a format-1 Loop file: reported with its fix, never
    deleted. loop new is where a loop start stops on it."""
    if not loopfile.has_root_file(cwd):
        return
    report.out.line("LOOP.md: a Loop file from before this version of VDD (format 1) is at the repository root. "
                    "No command reads it, and every loop command refuses while it is there.")
    report.out.tell(loopfile.ROOT_FIX)


# --- the Shared copy of the VDD tool ---

def shared_copy(report: Report) -> None:
    shared = places.shared_dir()
    try:
        state = install.state(shared)
    except OSError as error:
        report.refuse_read("the Shared copy of the VDD tool in %s" % shared, error)
    if state == install.CURRENT:
        report.out.line("Shared copy of the VDD tool in %s: current. Passed." % shared)
        return
    what = "install" if state == install.INSTALL else "update"

    def write() -> list[str]:
        install.swap(shared)
        if install.state(shared) != install.CURRENT:
            raise OSError("the copy differs from the shipped tool after the write")
        return ["Shared copy of the VDD tool: checked."]

    report.change("shared", "the Shared copy of the VDD tool",
                  ["%s the VDD tool (vdd.py and vdd/) in %s" % (what, shared)], write)


# --- Codex: VDD's old hooks.json entry and the hook's trust ---

def codex(report: Report, cwd: str, hook_answer: str | None) -> None:
    out = report.out
    home = codex_harness.home()
    hooks_path = os.path.join(home, "hooks.json")
    label = stores.display(hooks_path, cwd)
    migration = hooks.Migration(hooks_path)
    if migration.error:
        out.line("%s: left untouched, %s." % (label, migration.error))
        out.tell(
            "Setup left %s untouched: %s. If it holds VDD's old Stop hook entry, remove that "
            "entry by hand." % (label, migration.error)
        )
    elif not migration.removed:
        out.line("%s: no Stop entry from an older VDD. Passed." % label)
    else:
        after = migration.after

        def write() -> list[str]:
            textfile.write_text(hooks_path, after)
            json.loads(textfile.decode(textfile.read_bytes(hooks_path)))
            return ["%s: checked, it parses." % label]

        extra = list(migration.diff(label))
        if migration.relaid():
            extra.append("%s is rewritten in two-space JSON layout with LF line ends and no byte-order mark; "
                         "the diff shows only VDD's removal." % label)
        report.change("hooks.json", label,
                      ["%s removes VDD's old Stop hook entry; the hook now ships with the plugin." % label],
                      write, extra)
        if migration.shifted:
            out.tell(
                "Codex will list your own Stop hooks under 'Hooks need review' once at its next start, "
                "because removing VDD's old entry moved them: trust them again there."
            )
    for event, command in migration.others:
        out.line("%s: a %s hook naming vdd-codex-stop that Setup did not write stays: %s" % (label, event, command))
    config = os.path.join(home, "config.toml")
    config_label = stores.display(config, cwd)
    text = trust.read(config)
    if text and "vdd-codex-stop" in text:
        out.line("%s: a registration naming vdd-codex-stop stays; Setup does not edit this file." % config_label)
    trust_check.check(report, home, cwd, text, hook_answer)
