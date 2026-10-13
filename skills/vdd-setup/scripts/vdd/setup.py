"""The setup command: every check Setup makes, as a dry run, then with
--write the changes it plans."""

import os
import re
import subprocess

from . import args, borrowed, codex_setup, install, places, stores, textfile
from .out import Failure, Output, escalate, refused

USAGE_NAME = "setup --help"

HELP = [
    "setup --harness <h> --listed <names> --glossary-named <yes|no|absent> [--user-answer <answer>] [--write]",
    "",
    "Checks this repository and this machine for a VDD loop. Run it from the repository root.",
    "Without --write it changes nothing: it prints every check, every planned change and every line for the user.",
    "Show the user the planned changes, then run the same command with --write, which makes them and checks each.",
    "A run with nothing left to change changes nothing.",
    "",
    "--harness <h>            The Harness this Session runs in: claude-code, codex, cursor, copilot-cli,",
    "                         or generic for any other.",
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

SPEC = {
    "harness": args.VALUE,
    "listed": args.VALUE,
    "glossary-named": args.VALUE,
    "user-answer": args.VALUE,
    "write": args.FLAG,
}

RETIRED = ("PLAN.md", "PLAN-REVIEW.md", "FIXES.md", "CODEREVIEW.md")
LOOP_ENTRIES = ("LOOP.md", "/LOOP.md")
SCRATCH_ENTRIES = (".scratch/", "/.scratch/", ".scratch", "/.scratch")
MIGRATION_URL = "https://github.com/ArchitektApx/Vibe-Driven-Development/blob/master/CHANGELOG.md#migrating-from-014"


def usage():
    return "%s %s" % (places.command(), USAGE_NAME)


def run(argv):
    values = args.parse(argv, SPEC, usage())
    if values["help"]:
        out = Output()
        for line in HELP:
            out.line(line)
        return out.finish("Run %s setup with the options above, without --write first." % places.command())
    harness = args.harness_of(values, usage())
    args.require(values, ["listed", "glossary-named"], usage())
    if values["glossary-named"] not in ("yes", "no", "absent"):
        raise Failure("--glossary-named takes yes, no or absent.", "Run %s for this command's usage." % usage())
    answer = values["user-answer"]
    if answer is not None and answer not in ("resolves", "does-not-resolve"):
        raise Failure("--user-answer takes resolves or does-not-resolve.", "Run %s for this command's usage." % usage())
    return Setup(harness, values).run()


class Setup:
    def __init__(self, harness, values):
        self.harness = harness
        self.values = values
        self.write = values["write"]
        self.cwd = os.getcwd()
        self.out = Output()
        self.changes = []      # planned or made, one line each
        self.questions = []    # what the model asks the user before --write
        self.failed = []       # writes that did not land

    # --- the command lines this run names ---

    def command(self, write=None, answer=None):
        parts = [
            places.command(),
            "setup",
            "--harness",
            self.harness.name,
            "--listed",
            quote(self.values["listed"]),
            "--glossary-named",
            self.values["glossary-named"],
        ]
        answer = answer or self.values["user-answer"]
        if answer:
            parts += ["--user-answer", answer]
        if write if write is not None else self.write:
            parts.append("--write")
        return " ".join(parts)

    def require_root(self):
        """Refuse a run from below the repository root: every check and every
        write is relative to the working directory."""
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError:
            return
        root = textfile.decode(proc.stdout).strip()
        if proc.returncode != 0 or not root or same_directory(root, self.cwd):
            return
        root = os.path.realpath(root)
        raise Failure(
            [
                "Setup runs from the repository root, and this directory is below it: %s" % self.cwd,
                "The repository root: %s" % root,
                "Nothing was checked or changed.",
            ],
            "Change to the repository root, %s, and run the same command there: %s" % (root, self.command()),
        )

    # --- the run ---

    def run(self):
        self.require_root()
        out = self.out
        mode = "writing" if self.write else "dry run, nothing is changed yet"
        out.line("Setup, Harness %s (%s)." % (self.harness.label or "generic", mode))
        verdict = self.borrowed_skills()
        self.tracker()
        self.glossary_rename_repository()
        self.git_repository()
        self.gitignore()
        self.stale_loop_file()
        self.shared_copy()
        self.harness_steps()
        return self.finish(verdict)

    def finish(self, verdict):
        out = self.out
        if self.failed:
            return out.finish(
                escalate("Otherwise tell the user which change did not land and what it was for, and stop."),
                1,
            )
        if verdict.ask_user:
            return out.finish(
                "Ask the user to invoke %s and tell you whether it resolves. Then run: %s --user-answer "
                "resolves, or with --user-answer does-not-resolve when it does not."
                % (self.harness.borrowed_skill(borrowed.WRITING), self.command(write=False))
            )
        if not self.write and (self.changes or self.questions):
            steps = []
            if self.questions:
                steps.append(" ".join(self.questions))
            if self.changes:
                steps.append("Show the user the planned changes above; showing them is the consent step.")
            steps.append("Then run: %s" % self.command(write=True))
            return out.finish(" ".join(steps))
        if self.write and not self.changes:
            out.line("Nothing left to change.")
        return out.finish(
            "Give the user a short status report: what passed, what Setup changed, and what the user "
            "still has to do, relaying every Tell the user verbatim line above unchanged. Setup is done."
        )

    # --- check 1: the Borrowed skills ---

    def borrowed_skills(self):
        out = self.out
        harness = self.harness
        roots = harness.present_roots(self.cwd)
        hits = stores.search(roots, borrowed.SKILLS)
        listed = borrowed.parse_listed(self.values["listed"])
        verdict = borrowed.Verdict(hits, listed, self.values["glossary-named"], self.values["user-answer"])

        if verdict.ask_user:
            out.line(
                "Borrowed skills: %d of 13 Present in the stores this Harness reads, and your skill list "
                "shows none of the collection. Whether this Session can run them needs the user's answer."
                % len(verdict.present)
            )
            return verdict

        if len(verdict.passed) == len(borrowed.SKILLS):
            out.line("Borrowed skills: all 13 Present and Resolvable. Passed.")
        elif verdict.passed:
            out.line("Borrowed skills Present and Resolvable, passed: %s." % ", ".join(verdict.passed))

        if verdict.no_hit:
            text = "%s: Resolvable from a store Setup does not search. Passed." % ", ".join(verdict.no_hit)
            if harness.no_hit_continuation():
                text += " " + harness.no_hit_continuation()
            out.tell(text)

        if verdict.not_loaded:
            for store, skills in verdict.stores_of(verdict.not_loaded, self.cwd):
                out.line(
                    "Borrowed skills Present but not Resolvable, under %s: %s."
                    % (store.label, ", ".join(skills))
                )
                if len(skills) == len(borrowed.SKILLS):
                    what = "collection sits"
                elif len(skills) == 1:
                    what = skills[0] + " sits"
                else:
                    what = ", ".join(skills) + " sit"
                out.tell(
                    "Matt Pocock's %s in %s, which %s reads, and this Session has not loaded %s."
                    % (what, store.label, harness.label or "your agent", "it" if len(skills) == 1 else "them")
                )
                for line in harness.route_present_not_resolvable(store):
                    out.tell(line)

        old_route = None
        if verdict.old_collection:
            store = verdict.store_of(borrowed.SKILLS, self.cwd)
            old_route = harness.route_old_collection(store)
            out.line("Borrowed skills: a collection from before the glossary rename (a warning, not a block).")
            out.tell(
                "Warning: your copy of Matt Pocock's collection is from before its glossary rename, too old "
                "for VDD's Roles. It does not block Setup."
                + (" It sits in %s." % store.label if store else "")
            )
            for line in old_route or ["Update it where you installed it."]:
                out.tell(line)

        if verdict.missing:
            out.line("Borrowed skills Not Present: %s." % ", ".join(verdict.missing))
            if not verdict.old_collection:
                for line in harness.route_not_present():
                    out.tell(line)

        failed = set(verdict.not_loaded) | set(verdict.missing)
        for line in borrowed.cost_lines(failed):
            out.tell(line)
        return verdict

    # --- check 2: the tracker ---

    def tracker(self):
        text = textfile.read(os.path.join(self.cwd, "docs", "agents", "issue-tracker.md"))
        if text is None:
            self.out.line("Tracker: docs/agents/issue-tracker.md is missing.")
            self.out.tell(
                "Invoke %s and pick Local markdown when it asks which tracker to use. Until then the "
                "Planner (to-spec, to-tickets) and the Code-Reviewer (code-review) are blocked."
                % self.harness.borrowed_skill("setup-matt-pocock-skills")
            )
            return
        lowered = text.lower()
        if "local markdown" in lowered or ".scratch/" in lowered:
            self.out.line("Tracker: docs/agents/issue-tracker.md configures local markdown. Passed.")
            return
        self.out.line("Tracker: docs/agents/issue-tracker.md is configured. Passed.")
        self.out.tell(
            "Your tracker is not local markdown. VDD works with any tracker the collection supports, "
            "but its Roles are written for local markdown under .scratch/<slug>/."
        )

    # --- check 3: a repository set up before the glossary rename ---

    def glossary_rename_repository(self):
        root = self.cwd
        exists = lambda *p: os.path.isfile(os.path.join(root, *p))  # noqa: E731
        domain = textfile.read(os.path.join(root, "docs", "agents", "domain.md")) or ""
        old_root = exists("CONTEXT.md") or exists("CONTEXT-MAP.md")
        new_root = exists("GLOSSARY.md") or exists("GLOSSARY-MAP.md")
        fires = "CONTEXT.md" in domain or "CONTEXT-MAP.md" in domain or (old_root and not new_root)
        if not fires:
            self.out.line("Glossary rename: nothing in this repository to migrate. Passed.")
            return
        out = self.out
        out.line("Glossary rename: this repository was set up before it (a warning, not a block).")
        out.tell(
            "Warning: this repository was set up before Matt Pocock's glossary rename (CONTEXT.md is now "
            "GLOSSARY.md, CONTEXT-MAP.md is now GLOSSARY-MAP.md). It does not block the loop. To migrate:"
        )
        moves = [("CONTEXT.md", "GLOSSARY.md"), ("CONTEXT-MAP.md", "GLOSSARY-MAP.md")]
        context_map = textfile.read(os.path.join(root, "CONTEXT-MAP.md")) or ""
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
        holder = self.setup_section_file()
        out.tell("Edit docs/agents/domain.md and %s so they name the new files." % holder)
        out.tell("The full steps: %s" % MIGRATION_URL)

    def setup_section_file(self):
        found = []
        for name in ("AGENTS.md", "CLAUDE.md"):
            text = textfile.read(os.path.join(self.cwd, name)) or ""
            if "docs/agents/" in text or "## Agent skills" in text:
                found.append(name)
        if len(found) == 1:
            return found[0]
        return "AGENTS.md or CLAUDE.md, whichever holds the collection's setup section"

    # --- check 4: the git repository ---

    def git_repository(self):
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            inside = proc.returncode == 0 and proc.stdout.strip() == b"true"
        except OSError:
            self.out.line("Git repository: git is not installed or cannot run.")
            self.out.tell("VDD needs git: install it, then rerun Setup.")
            return
        if inside:
            self.out.line("Git repository: passed.")
            return
        self.out.line("Git repository: this directory is not one, and the workflow needs one.")
        if not self.write:
            self.questions.append(
                "Ask the user whether to run git init here; on yes, run it with your own tools."
            )

    # --- check 5: .gitignore ---

    def gitignore(self):
        path = os.path.join(self.cwd, ".gitignore")
        try:
            before, after, added, removed = plan_gitignore(path)
        except OSError as error:
            self.refuse_read(".gitignore", error)
        if not added and not removed:
            self.out.line(".gitignore: covers LOOP.md and .scratch/. Passed.")
            return
        verb = "Changed" if self.write else "Planned change"
        for entry in added:
            self.changes.append(entry)
            self.out.line("%s: .gitignore adds %s" % (verb, entry))
        for entry in removed:
            self.changes.append(entry)
            self.out.line("%s: .gitignore removes %s, which VDD no longer maintains" % (verb, entry))
        if not self.write:
            return
        try:
            textfile.write(path, after)
            _, check, again_added, again_removed = plan_gitignore(path)
            if again_added or again_removed:
                raise OSError("the file does not hold the change after the write")
            self.out.line(".gitignore: checked.")
        except OSError as error:
            self.failed.append(".gitignore")
            self.out.line("Not changed: .gitignore (%s)." % error)

    # --- check 6: a stale LOOP.md ---

    def stale_loop_file(self):
        if not os.path.exists(os.path.join(self.cwd, "LOOP.md")):
            self.out.line("LOOP.md: none from an earlier loop. Passed.")
            return
        self.out.line("LOOP.md: one from an earlier loop is here.")
        if not self.write:
            self.questions.append(
                "Ask the user whether to delete LOOP.md before a fresh loop; on yes, delete it with your own tools."
            )

    # --- check 7: the Shared copy of the VDD tool ---

    def shared_copy(self):
        shared = places.shared_dir()
        try:
            state = install.state(shared)
        except OSError as error:
            self.refuse_read("the Shared copy of the VDD tool in %s" % shared, error)
        if state == install.CURRENT:
            self.out.line("Shared copy of the VDD tool in %s: current. Passed." % shared)
            return
        verb = "Changed" if self.write else "Planned change"
        what = "install" if state == install.INSTALL else "update"
        self.changes.append("shared")
        self.out.line("%s: %s the VDD tool (vdd.py and vdd/) in %s" % (verb, what, shared))
        if not self.write:
            return
        try:
            install.swap(shared)
            if install.state(shared) != install.CURRENT:
                raise OSError("the copy differs from the shipped tool after the write")
            self.out.line("Shared copy of the VDD tool: checked.")
        except OSError as error:
            self.failed.append("shared")
            self.out.line("Not changed: the Shared copy of the VDD tool (%s)." % error)

    def refuse_read(self, what, error):
        """Stop the run on a file Setup cannot read, keeping what it printed."""
        raise refused(
            self.out.lines + ["Could not read %s: %s" % (what, error)],
            "Otherwise tell the user Setup could not read %s, and stop." % what,
        )

    # --- the Harness's own steps ---

    def harness_steps(self):
        if self.harness.codex_hook_steps():
            codex_setup.run(self)


def quote(value):
    if not value or not value.strip():
        return borrowed.NONE_LISTED
    if all(c.isalnum() or c in "-_:,." for c in value):
        return value
    return "'%s'" % value


def same_directory(one, other):
    return os.path.normcase(os.path.realpath(one)) == os.path.normcase(os.path.realpath(other))


def plan_gitignore(path):
    """(before, after, added, removed) as bytes and entry lists. A line is
    removed only when the whole line, trimmed of surrounding whitespace,
    equals a retired entry: docs/PLAN.md and !PLAN.md are the user's own."""
    try:
        with open(path, "rb") as handle:
            before = handle.read()
    except FileNotFoundError:
        before = b""
    text = before.decode("utf-8", "surrogateescape")
    # A leading byte order mark is not part of the first line, and a rewrite
    # drops it, as textfile.decode does on every read.
    if text.startswith("\ufeff"):
        text = text[1:]
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(True)
    kept = []
    removed = []
    for line in lines:
        entry = line.strip()
        if entry in RETIRED:
            removed.append(entry)
            continue
        kept.append(line)
    entries = {line.strip() for line in kept}
    added = []
    if not entries & set(LOOP_ENTRIES):
        added.append("LOOP.md")
    if not entries & set(SCRATCH_ENTRIES):
        added.append(".scratch/")
    after = "".join(kept)
    if added and after and not after.endswith(("\n", "\r")):
        after += newline
    after += "".join(entry + newline for entry in added)
    return before, after.encode("utf-8", "surrogateescape"), added, removed
