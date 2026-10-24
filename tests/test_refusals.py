"""Refusal tables: one table per command group, one row per refusal.

A row names a case, a staged scene, the argv, a fragment of the refusal's
first line (or a tuple of fragments, one per line from the first) and a
fragment of its Next: line. Every row asserts a non-zero exit, the tool's
contract (UTF-8, LF, a Next: line last), the line fragments and the Next:
fragment. A row marked POSIX stubs git or gh with an
sh script, or leans on a POSIX permission, and skips on native Windows.

Unreachable from vdd.py, so no row: orchestrator.py's four RuntimeError
guards (the Harness harness_slug names, the code review a Coder return
relays, and the code and plan reviews done reads), each behind a lookup an
earlier step has passed; coder's "git could not run", since the branch check
before it reads a git that cannot start as a detached HEAD and refuses
first."""

import json
import os
import re
import shutil
import stat
import subprocess
import unittest

from scenes import CC, CODEX_ID, FINDINGS, SLUG, Staged
from vddtest import PLAN_SIGNED, WINDOWS

V1 = "has state file version 1, which this VDD no longer reads."
NEXT_V1 = "Relay the Tell the user verbatim line above unchanged, and stop."
GH_REFUSED = "failed to read configuration: open ~/.config/gh/hosts.yml: operation not permitted"


class Refusals(Staged):
    """Each row a test of its own, named after its group and case."""

    def version_one(self):
        self.plan()
        self.box.write_loop("demo", version=1)

    def no_commit(self):
        self.box.git("init", "-q")
        self.box.git("symbolic-ref", "HEAD", "refs/heads/main")
        self.box.write_loop("demo", extra=(PLAN_SIGNED,))
        self.put("spec.md", "# Spec\n")
        self.put("issues/01-one.md", "# 01\n")

    def no_tickets(self):
        self.signed()
        shutil.rmtree(self.box.path(self.rel("issues")))

    def lost_open_finding(self):
        self.round_two()
        self.put("CODEREVIEW.md", re.sub(r"### 1\. major \(open\): a.txt:1\n", "", self.read("CODEREVIEW.md")))

    def off_the_feature_branch(self):
        self.coder_started()
        self.git("checkout", "-q", "main")

    def backup_blocked(self):
        """A 0.15 store with a file where the migration's backup goes, so
        the old store's rename fails as a held store's does on Windows."""
        self.legacy_store()
        self.box.write(".scratch/_brainstorming.pre-0.16", "in the way\n")

    def fixes_deleted(self):
        self.coder_started()
        os.remove(self.box.path(self.rel("FIXES.md")))

    def git_fails(self, verb):
        """A git on PATH that fails the verb and runs the real git
        otherwise."""
        real = shutil.which("git")
        self.box.stub("git", 'for a in "$@"; do if [ "$a" = %s ]; then echo "fatal: %s broke" >&2; exit 128; fi; '
                             "done\nexec '%s' \"$@\"\n" % (verb, verb, real))
        return {"PATH": self.box.bin + os.pathsep + os.environ.get("PATH", "")}

    def git_hangs(self, verb):
        """A git on PATH that sleeps on the verb, past a one-second timeout,
        and runs the real git otherwise."""
        real = shutil.which("git")
        self.box.stub("git", 'for a in "$@"; do if [ "$a" = %s ]; then exec sleep 30; fi; '
                             "done\nexec '%s' \"$@\"\n" % (verb, real))
        return {"PATH": self.box.bin + os.pathsep + os.environ.get("PATH", ""), "VDD_GIT_TIMEOUT_SECONDS": "1"}

    def coder_out(self):
        self.signed(policies=("respawn Coder never",))
        self.stage("orchestrator session 1")

    def gh_refuses_head(self):
        """PR: yes with a template, origin on GitHub with ls-remote stubbed, and a gh
        that passes auth and refuses the existing-PR check."""
        self.folded(pr="yes")
        self.git("remote", "add", "origin", "https://github.com/example/repo.git")
        real = shutil.which("git")
        self.box.stub("git", "if [ \"$1\" = ls-remote ]; then exit 0; fi\nexec '%s' \"$@\"\n" % real)
        self.box.write(".github/pull_request_template.md", "## What\n")
        self.box.stub("gh", 'case "$*" in *--head*) echo "%s" >&2; exit 1;; esac\nexit 0\n' % GH_REFUSED)
        return {"PATH": self.box.bin + os.pathsep + os.environ.get("PATH", "")}

    def ls_remote_refused(self):
        self.folded(pr="yes")
        self.origin()
        self.put("pr-body.md", "feat: a\n\nThe body.\n")
        real = shutil.which("git")
        self.box.stub("git", 'if [ "$1" = ls-remote ]; then echo "fatal: unable to access: Operation not '
                             "permitted\" >&2; exit 128; fi\nexec '%s' \"$@\"\n" % real)
        return {"PATH": self.box.bin + os.pathsep + os.environ.get("PATH", "")}

    def close_fails(self):
        """A push-only PR whose loop cannot be closed: its state file is
        read-only."""
        self.folded(pr="yes")
        self.origin()
        self.put("pr-body.md", "feat: a\n\nThe body.\n")
        path = self.box.path(self.rel("loop-state"))
        os.chmod(path, stat.S_IREAD)
        self.addCleanup(os.chmod, path, stat.S_IWRITE | stat.S_IREAD)
        return self.no_gh()

    def bad_review_range(self):
        """Code round 1 whose base branch is gone, so main...demo cannot be
        read."""
        self.coding()
        self.git("branch", "-q", "-D", "main")

    def plan_lost_finding(self):
        self.plan_review_written()
        self.run_ok("review", "check", "--role", "Plan-Reviewer", *SLUG, "--write")
        self.run_ok("doorbell", "ring", "--role", "Planner", *CC, *SLUG, "--write")
        self.put("PLAN-REVIEW.md", self.read("PLAN-REVIEW.md").replace("### 2. minor (open): Ticket 02", "### 2."))

    def plan_review_deleted(self):
        self.plan()
        self.run_ok("doorbell", "ring", "--role", "Planner", *CC, *SLUG, "--write")
        self.run_ok("review", "start", "--role", "Plan-Reviewer", *SLUG, "--write")
        os.remove(self.box.path(self.rel("PLAN-REVIEW.md")))

    def findings_after(self, scene):
        scene(self)
        self.box.write("findings.md", FINDINGS)

    def findings_open(self):
        self.coding()
        self.stage("code 1 reviewed open 1 counts 0 1 0 next 2 new 1 closed 0 checks code-review ran")
        self.put("CODEREVIEW.md", "# Code review, round 1\n")
        self.box.write("findings.md", FINDINGS)

    def moved_ref_closed(self):
        """Code round 1 signed off, a fold that moved the branch and stopped
        before its state line, then the loop closed."""
        self.code_signed()
        signed = self.sha()
        tip = self.commit("b.txt", "b\n", "feat: b")
        self.put("recap.json", json.dumps({"format": 1, "records": [{
            "key": "fold " + signed, "section": "Commits", "lines": ["Folded demo: 2 commits into 1.", ""],
            "data": {"tip": tip, "before": 2, "after": 1, "report": []}}]}))
        self.stage("loop closed")
        self.box.write("findings.md", FINDINGS)

    def snapshot(self):
        """The staged project as a refusal must leave it: every file and
        directory outside .git, with its bytes, and the checked-out branch
        and HEAD when the project is a repository. The idea store's lock
        file is left out: every brainstorm write that takes the lock writes
        its pid there, a refused one included."""
        tree = {}
        for directory, dirs, files in os.walk(self.box.proj):
            dirs[:] = sorted(d for d in dirs if not (directory == self.box.proj and d == ".git"))
            rel = os.path.relpath(directory, self.box.proj)
            tree[rel] = None
            for name in files:
                if rel == ".scratch" and name == "_brainstorming.lock":
                    continue
                with open(os.path.join(directory, name), "rb") as handle:
                    tree[os.path.join(rel, name)] = handle.read()
        if os.path.isdir(self.box.path(".git")):
            tree[".git HEAD"] = self.box.read(os.path.join(".git", "HEAD"))
            try:
                tree[".git rev"] = self.box.git("rev-parse", "--verify", "-q", "HEAD")
            except subprocess.CalledProcessError:
                tree[".git rev"] = None
        return tree

    def newer_state_alone(self):
        """A tracker directory holding a newer VDD's loop-state and no
        loop.md."""
        self.repo()
        self.put("loop-state", "vdd loop-state 9\nloop open\n")

    def test_aside_offers_the_move_for_a_newer_state_without_a_loop_file(self):
        """Prevents loop aside, the way out for a leftover directory,
        refusing one whose newer state file has no Loop file beside it."""
        self.newer_state_alone()
        result = self.box.run("loop", "aside", *SLUG, env=self.env())
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.lines[0], "Would move .scratch/demo/ to .scratch/demo-2/.", result)

    def test_new_refuses_a_newer_state_without_a_loop_file_before_writing(self):
        """Prevents loop new writing a Loop file into a directory whose
        state file a newer VDD wrote, and its dry run promising a run that
        --write then refuses."""
        self.newer_state_alone()
        before = self.snapshot()
        for write in ([], ["--write"]):
            with self.subTest(write=bool(write)):
                result = self.box.run("loop", "new", *SLUG, *CC, "--leftover", "continue", "--minors", "fix",
                                      "--pr", "ask at sign-off", *write, env=self.env())
                self.assertEqual(result.code, 1, result)
                self.assertIn("format version 9", result.lines[0], result)
                self.assertEqual(self.snapshot(), before, result)

    def check(self, row):
        _, case, scene, argv, first, following, env, posix = row
        if posix and WINDOWS:
            self.skipTest("stubs a POSIX sh script or a POSIX permission")
        if posix and hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root passes a POSIX permission check")
        extra = scene(self)
        if callable(env):
            extra = env(self)
        values = dict(extra) if isinstance(extra, dict) else {}
        values.update(env if isinstance(env, dict) else {})
        before = self.snapshot()
        result = self.box.run(*argv, env=self.env(values))
        label = "row %s %s" % (row[0], case)
        self.assertEqual(self.snapshot(), before, "%s: the refusal left a trace\n%r" % (label, result))
        if case.startswith("version-1"):
            tells = result.tells()
            self.assertTrue(tells and "loop aside --slug demo --write" in tells[0] and "vdd-start-loop" in tells[0],
                            "%s: no loop aside or vdd-start-loop in the Tell line\n%r" % (label, result))
            self.assertNotIn("reinstall", tells[0], label)
            self.assertIn(V1, result.lines[0], label)
            self.assertNotIn("review file", result.text, label)
        self.assertNotEqual(result.code, 0, "%s: exit 0\n%r" % (label, result))
        self.assertNotIn(b"\r", result.data, label)
        self.assertTrue(result.last.startswith("Next: "), "%s: the last line is no Next: line\n%r" % (label, result))
        for number, fragment in enumerate(first if isinstance(first, tuple) else (first,)):
            self.assertIn(fragment, result.lines[number], "%s: line %d\n%r" % (label, number + 1, result))
        self.assertIn(following, result.last, "%s: Next: line\n%r" % (label, result))


R = Refusals
CHECK = ("coder", "check", *SLUG, "--write")
START = ("coder", "start", *SLUG, "--write")
USAGE = "--help for this command's usage."
AGAIN = "Run the command again"


def unknown(option, takes):
    """The first two lines of the refusal of an option the command does not
    take: the option, and the command's own options."""
    return ("Unknown option: --%s" % option, "This command takes: %s." % ", ".join("--" + o for o in takes))


# (group, case, scene, argv, first-line fragment, Next: fragment, env, POSIX only). A scene may return the
# environment it needs; env adds to it.
TABLES = {
    "loop": [
        ("pr-author-before-sign-off", R.signed, ("loop", "show", *SLUG, "--role", "PR-Author"),
         "The code Loop is not signed off", "the Loop is not finished", None, False),
        ("bad-slug", R.repo, ("loop", "new", "--slug", "Not A Slug", *CC), "Not a Feature slug", "Ask the user for a slug",
         None, False),
        ("set-nothing", R.plan, ("loop", "set", *SLUG, "--write"), "Nothing to set", "loop set --help", None,
         False),
        ("newer-state-version", R.newer_state, ("loop", "show", *SLUG), "format version 9", "rerun Setup", None,
         False),
        ("show-option-of-new", R.plan, ("loop", "show", *SLUG, *CC, "--minors", "leave"),
         unknown("minors", ("harness", "role", "slug")), AGAIN, None, False),
        ("close-option-of-set", R.plan, ("loop", "close", *SLUG, "--feature", "y"),
         unknown("feature", ("harness", "slug", "write")), AGAIN, None, False),
        ("new-option-of-set", R.repo, ("loop", "new", *SLUG, *CC, "--minors", "fix", "--pr", "no", "--harness-line",
                                       "Codex"),
         unknown("harness-line", ("base", "branch", "harness", "leftover", "minors", "pr", "slug", "write")), AGAIN,
         None, False),
        ("new-missing", R.repo, ("loop", "new", *CC), "Missing: --slug", "loop new " + USAGE, None, False),
        ("new-write-missing-answers", R.repo, ("loop", "new", *SLUG, *CC, "--write"), "Missing: --minors, --pr",
         "loop new " + USAGE, None, False),
        ("show-role-not-a-choice", R.plan, ("loop", "show", *SLUG, "--role", "Nobody"),
         "--role takes Planner, Plan-Reviewer, Coder, Code-Reviewer, Orchestrator or PR-Author, not Nobody.",
         "loop show " + USAGE, None, False),
        ("new-leftover-not-a-choice", R.repo, ("loop", "new", *SLUG, *CC, "--leftover", "keep"),
         "--leftover takes continue, not keep.", "loop new " + USAGE, None, False),
        ("new-minors-not-a-choice", R.repo, ("loop", "new", *SLUG, *CC, "--minors", "bogus"),
         "--minors takes fix or leave, not bogus.", "Ask the user again with the accepted answers", None, False),
        ("set-pr-not-a-choice", R.plan, ("loop", "set", *SLUG, "--pr", "bogus"),
         '--pr takes yes, "ask at sign-off", manual or no, not bogus.', "Ask the user again with the accepted answers",
         None, False),
    ],
    "doorbell": [
        ("version-1-ring", R.version_one, ("doorbell", "ring", "--role", "Planner", *CC, *SLUG, "--write"),
         "doorbell ring does not run on it.", NEXT_V1, None,
         False),
        ("closed-loop-ring", lambda t: (t.plan(), t.stage("loop closed")),
         ("doorbell", "ring", "--role", "Planner", *CC, *SLUG, "--write"), "is closed", "ask the Orchestrator to reopen it", None,
         False),
        ("ring-option-of-take", R.plan, ("doorbell", "ring", "--role", "Planner", *CC, *SLUG, "--pasted", "z"),
         unknown("pasted", ("harness", "role", "slug", "write")), AGAIN, None, False),
        ("take-option-of-ring", R.plan, ("doorbell", "take", "--role", "Planner", *CC, *SLUG, "--write"),
         unknown("write", ("harness", "pasted", "resumed", "role", "slug")), AGAIN, None, False),
        ("wait-option-of-ring", R.plan, ("doorbell", "wait", "--role", "Planner", *CC, *SLUG, "--write"),
         unknown("write", ("harness", "role", "slug")), AGAIN, None, False),
        ("ring-missing", R.plan, ("doorbell", "ring", *SLUG, "--write"), "Missing: --role, --harness",
         "doorbell ring " + USAGE, None, False),
        ("ring-role-not-a-choice", R.plan, ("doorbell", "ring", "--role", "Coder", *CC, *SLUG, "--write"),
         "--role takes Planner or Orchestrator, not Coder.", "doorbell ring " + USAGE, None, False),
    ],
    "coder": [
        ("version-1-start", R.version_one, START, V1, NEXT_V1, None, False),
        ("version-1-check", R.version_one, CHECK, V1, NEXT_V1, None, False),
        ("no-commit", R.no_commit, START, "has no commit", "first commit", None, False),
        ("git-diff-fails", R.coder_started, CHECK, "git diff failed", "git diff fails",
         lambda t: t.git_fails("diff"), True),
        ("git-diff-times-out", R.coder_started, CHECK, "git diff timed out after 1 seconds.",
         "git diff did not finish", lambda t: t.git_hangs("diff"), True),
        ("git-ls-files-fails", R.coder_started, CHECK, "git ls-files failed", "git ls-files fails",
         lambda t: t.git_fails("ls-files"), True),
        ("git-branch-times-out", R.signed, START, "git branch timed out after 1 seconds.",
         "git branch did not finish", lambda t: t.git_hangs("branch"), True),
        ("start-after-code-sign-off", R.code_signed, START, "The code Loop signed off in round 1",
         "BLOCKED: the code Loop is already signed off", None, False),
        ("lost-open-finding", R.lost_open_finding, START, "CODEREVIEW.md has no heading for finding 1",
         "lost a finding the loop still has open", None, False),
        ("no-ticket-files", R.no_tickets, START, "holds no Ticket file", "BLOCKED: the loop has no Tickets", None, False),
        ("check-before-start", R.signed, CHECK, "Code round 1 has not been started", "coder start", None, False),
        ("check-off-the-feature-branch", R.off_the_feature_branch, CHECK, "The checked-out branch is main",
         "coder check --slug demo --write again", None, False),
        ("check-fixes-deleted", R.fixes_deleted, CHECK, "FIXES.md does not exist", "FIXES.md is gone", None, False),
        ("start-option-of-review", R.signed, START + ("--role", "Coder"), unknown("role", ("slug", "write")), AGAIN,
         None, False),
    ],
    "review": [
        ("version-1-plan-start", R.version_one, ("review", "start", "--role", "Plan-Reviewer", *SLUG, "--write"), V1,
         NEXT_V1, None, False),
        ("version-1-plan-check", R.version_one, ("review", "check", "--role", "Plan-Reviewer", *SLUG, "--write"),
         V1, NEXT_V1, None, False),
        ("version-1-add", lambda t: (t.version_one(), t.box.write("findings.md", FINDINGS)),
         ("review", "add", *SLUG, "--from", "findings.md", "--write"), V1, NEXT_V1, None, False),
        ("bad-review-range", R.bad_review_range, ("review", "start", "--role", "Code-Reviewer", *SLUG, "--write"),
         "git cannot read the review range", "git cannot diff", None, False),
        ("git-diff-times-out", R.coding, ("review", "start", "--role", "Code-Reviewer", *SLUG, "--write"),
         "git diff timed out after 1 seconds.", "git diff did not finish",
         lambda t: t.git_hangs("diff"), True),
        ("start-after-sign-off", R.code_signed, ("review", "start", "--role", "Code-Reviewer", *SLUG, "--write"),
         "The code Loop signed off in round 1", "BLOCKED: the code Loop is already signed off", None, False),
        ("lost-finding", R.plan_lost_finding, ("review", "start", "--role", "Plan-Reviewer", *SLUG, "--write"),
         "no longer holds finding 2", "lost a finding the loop still has open", None, False),
        ("check-before-start", R.plan, ("review", "check", "--role", "Plan-Reviewer", *SLUG, "--write"),
         "Round 1 of the plan review has not been started", "review start", None, False),
        ("check-file-deleted", R.plan_review_deleted, ("review", "check", "--role", "Plan-Reviewer", *SLUG,
                                                       "--write"),
         "PLAN-REVIEW.md does not exist", "writes the frame again", None, False),
        ("add-no-recorded-review", lambda t: t.findings_after(Refusals.coding),
         ("review", "add", *SLUG, "--from", "findings.md", "--write"), "no recorded review",
         "review add takes findings only after a code Sign-off", None, False),
        ("add-findings-open", R.findings_open, ("review", "add", *SLUG, "--from", "findings.md", "--write"),
         "round 1's review left findings open", "review add takes findings only after a code Sign-off", None,
         False),
        ("add-moved-ref-closed", R.moved_ref_closed, ("review", "add", *SLUG, "--from", "findings.md", "--write"),
         "Code round 1 was folded but its fold is not recorded", "loop reopen --slug demo --write, then ", None,
         False),
        ("add-option-of-start", R.code_signed, ("review", "add", *SLUG, "--from", "findings.md", "--role", "Coder"),
         unknown("role", ("from", "slug", "write")), AGAIN, None, False),
        ("start-missing", R.plan, ("review", "start", *SLUG, "--write"), "Missing: --role",
         "review start " + USAGE, None, False),
        ("add-missing", R.code_signed, ("review", "add", *SLUG, "--write"), "Missing: --from", "review add " + USAGE,
         None, False),
        ("start-role-not-a-choice", R.plan, ("review", "start", "--role", "Coder", *SLUG, "--write"),
         "--role takes Plan-Reviewer or Code-Reviewer, not Coder.", "review start " + USAGE, None, False),
    ],
    "orchestrator": [
        ("version-1-start", R.version_one, ("orchestrator", "start", *SLUG, *CC), V1, NEXT_V1, None, False),
        ("version-1-return", R.version_one, ("orchestrator", "return", "--role", "Coder", *SLUG, *CC), V1, NEXT_V1,
         None, False),
        ("return-with-no-role-out", R.coder_out, ("orchestrator", "return", "--role", "Coder", *SLUG, *CC),
         "No Coder is out in this Orchestrator session", "orchestrator start", None, False),
        ("respawn-both", R.plan, ("orchestrator", "respawn", "--role", "Coder", "--policy", "never", "--once",
                                  *SLUG, "--write"), "Give --policy or --once", "usage", None, False),
        ("respawn-neither", R.plan, ("orchestrator", "respawn", "--role", "Coder", *SLUG, "--write"),
         "Missing: --policy or --once", "orchestrator respawn " + USAGE, None, False),
        ("start-option-of-return", R.plan, ("orchestrator", "start", *SLUG, *CC, "--role", "Coder"),
         unknown("role", ("harness", "slug")), AGAIN, None, False),
        ("tokens-missing", R.coder_out, ("orchestrator", "tokens", "--role", "Coder", *SLUG), "Missing: --tokens",
         "orchestrator tokens " + USAGE, None, False),
        ("return-role-not-a-choice", R.plan, ("orchestrator", "return", "--role", "PR-Author", *SLUG, *CC),
         "--role takes Planner, Plan-Reviewer, Coder or Code-Reviewer, not PR-Author.", "orchestrator return " + USAGE,
         None, False),
        ("tokens-not-a-number", R.coder_out, ("orchestrator", "tokens", "--role", "Coder", "--tokens", "52k",
                                              *SLUG), "--tokens takes a whole number", "again with the number",
         None, False),
        ("tokens-with-no-role-out", R.coder_out, ("orchestrator", "tokens", "--role", "Coder", "--tokens", "52000",
                                                  *SLUG), "No Coder is out", "step the tool printed", None, False),
    ],
    "pr": [
        ("version-1-check", R.version_one, ("pr", "check", *SLUG, *CC), V1, NEXT_V1, None, False),
        ("gh-refuses-the-existing-pr-check", R.gh_refuses_head, ("pr", "check", *SLUG, *CC), "A sandbox refused",
         "outside the sandbox", None, True),
        # The push is done, so it prints first.
        ("close-fails", R.close_fails, ("pr", "open", "--path", "push-only", *SLUG, *CC, "--write"),
         "Pushed demo to origin.", "could not be closed", None, True),
        ("bad-path", R.folded, ("pr", "open", "--path", "pushed", *SLUG, *CC, "--write"),
         "--path takes open, push-only or existing, not pushed.", "pr open " + USAGE, None, False),
        ("check-fold-owed", R.code_signed, ("pr", "check", *SLUG, *CC), "The fold's outcome is not recorded",
         "loop fold --slug demo --harness claude-code --write, then run ", None, False),
        ("check-option-of-open", R.code_signed, ("pr", "check", *SLUG, *CC, "--path", "open"),
         unknown("path", ("harness", "slug")), AGAIN, None, False),
        ("open-missing", R.folded, ("pr", "open", *SLUG, "--write"), "Missing: --harness, --path", "pr open " + USAGE,
         None, False),
        ("preflight-refused-at-open", R.ls_remote_refused, ("pr", "open", "--path", "push-only", *SLUG, *CC,
                                                            "--write"),
         "A sandbox refused", "outside the sandbox", None, True),
    ],
    "wayfinder": [
        ("no-templates", R.repo, ("wayfinder", "start", "--effort", "demo", "--skill-dir", "nowhere"),
         "has no references/overview-template.md", "invoke vdd-setup", None, False),
        ("start-missing", R.repo, ("wayfinder", "start", "--effort", "demo"), "Missing: --skill-dir",
         "wayfinder start " + USAGE, None, False),
        ("start-option-of-loop", R.repo, ("wayfinder", "start", "--effort", "demo", "--skill-dir", "x", *SLUG),
         unknown("slug", ("effort", "skill-dir")), AGAIN, None, False),
    ],
    "setup": [
        ("unknown-harness", R.repo, ("setup", "--harness", "emacs", "--listed", "none", "--glossary-named", "yes"),
         "Unknown Harness: emacs", "Run again with --harness set to one of", None, False),
        ("missing", R.repo, ("setup", *CC), "Missing: --listed, --glossary-named", "setup " + USAGE, None, False),
        ("glossary-named-not-a-choice", R.repo, ("setup", *CC, "--listed", "none", "--glossary-named", "maybe"),
         "--glossary-named takes yes, no or absent, not maybe.", "setup " + USAGE, None, False),
        ("option-of-loop", R.repo, ("setup", *CC, "--listed", "none", "--glossary-named", "yes", *SLUG),
         unknown("slug", ("glossary-named", "harness", "listed", "user-answer", "write")), AGAIN, None, False),
    ],
    "brainstorm": [
        ("unknown-idea", R.store, ("brainstorm", "show", "--idea", "main-ide"), "No idea named main-ide",
         "with the slug as the user meant it", None, False),
        ("show-missing", R.store, ("brainstorm", "show"), "Missing: --idea", "brainstorm show " + USAGE, None, False),
        ("migrate-rename-held", R.backup_blocked, ("brainstorm", "migrate", "--write"),
         ("could not be renamed to the backup", "an editor, or a shell whose working directory is inside it"),
         "if your own shell's working directory is inside .scratch/_brainstorming/, change to the repository root "
         "and run the command again; if not, tell the user what holds it open and wait for their word", None, False),
        ("set-option-of-new", R.store, ("brainstorm", "set", "--idea", "x", "--parent", "y", "--write"),
         unknown("parent", ("decision", "fog", "idea", "importance", "reopen-when", "size", "status", "title", "tldr",
                            "write")), AGAIN, None, False),
    ],
}


def make_test(group, row):
    def test(self):
        self.check((group,) + row)

    test.__doc__ = "Prevents an unseen change to the %s refusal %s." % (group, row[0])
    return test


for _group, _rows in TABLES.items():
    for _row in _rows:
        _name = "test_%s_%s" % (_group, re.sub(r"\W", "_", _row[0]))
        assert not hasattr(Refusals, _name), _name
        setattr(Refusals, _name, make_test(_group, _row))

del R


class RefusalPathTest(Staged):
    """The refusals in loopstate.header, textfile.check_header and
    State.persist print the state file's path as the rest of the tool does."""

    def refusal(self, scene, *argv):
        scene(self)
        result = self.box.run(*argv, env=self.env())
        self.assertNotEqual(result.code, 0, result)
        self.assertNotIn(self.box.root, result.text)
        self.assertNotIn(self.box.root.replace("\\", "\\\\"), result.text)
        return result.lines[0]

    def test_a_newer_header_names_the_scratch_path(self):
        """Prevents a refusal that prints the absolute path of the user's
        project where every other line prints .scratch/<slug>/."""
        first = self.refusal(Staged.newer_state, "loop", "show", *SLUG)
        self.assertTrue(first.startswith(".scratch/demo/loop-state has format version 9"), first)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root writes a read-only file")
    def test_a_refused_state_write_names_the_scratch_path_and_the_reason(self):
        """Prevents a write refusal that repeats the absolute path in the
        error, repr-escaped on Windows."""
        first = self.refusal(Staged.read_only_state, "orchestrator", "start", *SLUG, *CC)
        self.assertTrue(first.startswith("Could not write the loop state file .scratch/demo/loop-state: "), first)

    def test_a_damaged_header_names_the_scratch_path(self):
        """loopstate.header's own line is caught by every caller, which takes
        a damaged state file for no loop; the refusal a Role sees names the
        tracker directory the same way."""
        first = self.refusal(Staged.damaged_state, "loop", "show", *SLUG)
        self.assertTrue(first.startswith(".scratch/demo/ "), first)

    def read_only(self, *parts):
        """The project path parts made read-only for the rest of the test."""
        path = self.box.path(*parts)
        mode = stat.S_IMODE(os.stat(path).st_mode)
        os.chmod(path, stat.S_IRUSR | stat.S_IXUSR if os.path.isdir(path) else stat.S_IRUSR)
        self.addCleanup(os.chmod, path, mode)

    def immutable(self, *parts):
        """The project path parts flagged immutable, so replacing it fails
        while reading it works."""
        path = self.box.path(*parts)
        os.chflags(path, stat.UF_IMMUTABLE)
        self.addCleanup(os.chflags, path, 0)

    def assertNoError(self, first):
        """No whole OSError: its [Errno n] and repr-quoted path."""
        self.assertNotIn("[Errno", first)

    @unittest.skipIf(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0), "needs a POSIX permission bit")
    def test_a_refused_loop_new_names_the_scratch_path(self):
        """Prevents loop new's write refusal printing the tracker directory's
        absolute path and the whole OSError."""
        self.repo()
        os.makedirs(self.box.path(".scratch"))
        self.read_only(".scratch")
        first = self.refusal(lambda t: None, "loop", "new", *SLUG, *CC, "--minors", "fix", "--pr", "ask at sign-off",
                             "--write")
        self.assertTrue(first.startswith("Could not write the Loop file in .scratch/demo/: "), first)
        self.assertNoError(first)

    @unittest.skipUnless(hasattr(os, "chflags") and not WINDOWS, "replacing a readable file fails only with chflags")
    def test_a_refused_recap_write_names_the_scratch_path(self):
        """Prevents the Recap's write refusal printing RECAP.md's absolute
        path."""
        self.coder_started()
        self.put("RECAP.md", "")
        self.immutable(".scratch", "demo", "RECAP.md")
        first = self.refusal(lambda t: None, "coder", "check", *SLUG, "--write")
        self.assertTrue(first.startswith("Could not write .scratch/demo/RECAP.md: "), first)
        self.assertNoError(first)

    @unittest.skipIf(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0), "needs a POSIX permission bit")
    def test_a_refused_ring_names_the_scratch_path(self):
        """Prevents doorbell ring's refusal printing the Doorbell file's
        absolute path."""
        self.plan()
        self.rings("VDD Planner: .scratch/demo/ ready, round 9. Read spec.md and issues/.")
        self.read_only(".scratch", "demo", "doorbells")
        first = self.refusal(lambda t: None, "doorbell", "ring", "--role", "Planner", *CC, *SLUG, "--write")
        self.assertTrue(first.startswith("Could not write the Doorbell file .scratch/demo/doorbells: "), first)
        self.assertNoError(first)

    @unittest.skipIf(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0), "needs a POSIX permission bit")
    def test_a_refused_doorbell_state_write_names_the_scratch_path(self):
        """Prevents doorbell take's refusal printing the Doorbell state
        file's absolute path."""
        self.planner_returned()
        self.read_only(".scratch", "demo")
        first = self.refusal(lambda t: None, "doorbell", "take", "--role", "Orchestrator", *CC, *SLUG)
        self.assertTrue(first.startswith("Could not write the Doorbell state file "
                                         ".scratch/demo/doorbell-state-orchestrator: "), first)
        self.assertNoError(first)

    @unittest.skipIf(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0), "needs a POSIX permission bit")
    def test_a_wait_that_cannot_read_names_the_scratch_path(self):
        """Prevents the wait's read refusal printing the whole OSError, on
        the Codex arm and on the watch every other Harness runs."""
        self.planner_returned()
        self.read_only(".scratch", "demo", "doorbells")
        os.chmod(self.box.path(".scratch", "demo", "doorbells"), 0)
        env = self.box.env(VDD_WAIT_POLL_SECONDS="0.05", VDD_WAIT_TIMEOUT_SECONDS="0.2", CODEX_THREAD_ID=CODEX_ID)
        for harness in ("claude-code", "codex"):
            with self.subTest(harness=harness):
                result = self.box.run("doorbell", "wait", "--role", "Orchestrator", "--harness", harness, *SLUG,
                                      env=env)
                self.assertNotEqual(result.code, 0, result)
                self.assertNotIn(self.box.root, result.text)
                self.assertIn("The wait could not read its files: .scratch/demo/doorbells: ", result.text)
                self.assertNoError(result.text)

    @unittest.skipIf(WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0), "needs a POSIX permission bit")
    def test_a_refused_armed_write_names_the_scratch_path(self):
        """Prevents the Codex arm's write refusal printing the whole
        OSError."""
        self.planner_returned()
        self.read_only(".scratch", "demo")
        env = self.box.env(CODEX_THREAD_ID=CODEX_ID)
        result = self.box.run("doorbell", "wait", "--role", "Planner", "--harness", "codex", *SLUG, env=env)
        self.assertNotEqual(result.code, 0, result)
        self.assertNotIn(self.box.root, result.text)
        self.assertIn("Cannot write the armed file: .scratch/demo/", result.text)
        self.assertNoError(result.text)

    @unittest.skipIf(WINDOWS, "a directory read as a file fails differently on Windows")
    def test_an_unexpected_file_error_names_the_scratch_path(self):
        """Prevents the catch-all refusal printing the whole OSError with
        its absolute path: it names the file by its .scratch path."""
        self.coder_started()
        os.makedirs(self.box.path(".scratch", "demo", "RECAP.md"))
        first = self.refusal(lambda t: None, "coder", "check", *SLUG, "--write")
        self.assertTrue(first.startswith("A file could not be read or written: .scratch/demo/RECAP.md: "), first)
        self.assertNoError(first)


if __name__ == "__main__":
    unittest.main()
