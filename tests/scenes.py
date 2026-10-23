"""The staged scenes the goldens and the refusal tables run on: a loop in
each state a Role meets it in, built with the shared helpers."""

import json
import os
import shutil
import stat
import subprocess
import sys

from vddtest import GH, PLAN_SIGNED, SCRIPTS, URL, LoopRepoTest

TODAY = "2026-10-20"
CC = ("--harness", "claude-code")
SLUG = ("--slug", "demo")

P1 = "VDD Planner: .scratch/demo/ ready, round 1. Read spec.md and issues/."
P2 = "VDD Planner: .scratch/demo/ ready, round 2. Read spec.md and issues/."
PLAN_OPEN_1 = "plan 1 reviewed open 1,2 counts 0 1 1 next 3 new 2 closed 0 checks writing-for-agents ran"
CODE_OPEN_1 = "code 1 reviewed open 1 counts 0 1 0 next 2 new 1 closed 0 checks code-review ran"
CODE_SIGNED_1 = "code 1 reviewed signed-off - counts 0 0 0 next 1 new 0 closed 0 checks code-review ran"
CODEX_ID = "019a0001-aaaa-7bbb-8ccc-0123456789ab"
PR_URL = "https://github.com/example/repo/pull/7"

PLAN_REVIEW_1 = """# Plan review, round 1

## Checks

writing-for-agents: ran

## New findings

### 1. major (open): Implementation Decisions

The Spec does not say how amounts are written.

### 2. minor (open): Ticket 02

Ticket 02 leaves `summary` out.
"""

FINDINGS = """### major: docs/a.md:3

The heading names the wrong command.

### minor: src/b.py:9

The helper's name says less than it does.
"""

LEGACY_INDEX = """# Brainstorming Index

## Ideas

| Idea | Importance | Size | Fog | Status | TL;DR |
|---|---|---|---|---|---|
| [old-idea.md](old-idea.md) | large | small | small | shaped | An old idea. |

## Log

- 2026-10-01: old-idea captured.
"""

LEGACY_IDEA = "# Old idea\n\n## Summary\n\nAn old idea.\n\n## Next Steps\n\n- [ ] Look again.\n"


class Staged(LoopRepoTest):
    """A test that stages one of the scenes below, then runs the tool."""

    # --- scenes ---

    def repo(self):
        """main with a .gitignore for .scratch/."""
        self.box.init_git("main")
        self.box.write(".gitignore", ".scratch/\n")
        self.git("add", ".gitignore")
        self.git("commit", "-q", "-m", "chore: ignore the tracker")

    def plan(self, *extra, pr="ask at sign-off", policies=()):
        """An open loop in planning, its Spec and two Tickets."""
        self.repo()
        self.box.write_loop("demo", extra=tuple(policies) + extra)
        if pr != "ask at sign-off":
            self.set_pr(pr)
        self.put("spec.md", "# Spec\n")
        self.put("issues/01-one.md", "# 01\n")
        self.put("issues/02-two.md", "# 02\n")

    def rings(self, *lines, to="Orchestrator"):
        path = self.box.path(self.rel("doorbells"))
        new = not os.path.exists(path)
        with open(path, "a") as handle:
            if new:
                handle.write("# vdd doorbells 1\n")
            for line in lines:
                handle.write("10:00:00 to: %s %s\n" % (to, line))

    def signed(self, **kw):
        self.plan(PLAN_SIGNED, **kw)

    def coding(self, **kw):
        """The plan signed off, round 1 of the code on the feature branch."""
        self.signed(**kw)
        self.git("checkout", "-q", "-b", "demo")
        self.coder_round(1)

    def coder_started(self):
        self.signed()
        self.run_ok("coder", "start", *SLUG, "--write")
        self.put("FIXES.md", self.read("FIXES.md").replace(
            "Files:\nChange:\nVerified:", "Files: `a.txt`\nChange: wrote a.\nVerified: the test passed."))
        self.commit("a.txt", "a\n", "feat: a")

    def round_two(self):
        """Code round 1 reviewed with finding 1 open."""
        self.coding()
        self.stage(CODE_OPEN_1)
        self.put("CODEREVIEW.md", "# Code review, round 1\n\nOPEN: 0 blocker, 1 major, 0 minor.\n\n## Checks\n\n"
                 "code-review: ran\n\n## Open findings\n\n## New findings\n\n### 1. major (open): a.txt:1\n\n"
                 "The value is wrong.\n\n## Not carried\n")

    def coder_returned(self):
        """Code round 1 written and the Coder's Doorbell in, the Coder
        spawned in this session."""
        self.coding(policies=("respawn Coder never",))
        self.stage("orchestrator session 1", "spawn Coder 1 session 1")
        self.rings("VDD Coder: FIXES.md written, round 1. Read it.")

    def planner_returned(self):
        """The plan written and the Planner's Doorbell in, no Plan-Reviewer
        yet."""
        self.plan(policies=("respawn Coder never",))
        self.rings(P1)
        self.stage("orchestrator session 1")

    def code_round_two_answered(self):
        """Code round 1 reviewed with finding 1 open, and the Coder's round 2
        answering it."""
        self.round_two()
        self.run_ok("coder", "start", *SLUG, "--write")
        self.put("FIXES.md", self.read("FIXES.md").replace("Answer: <fixed | pushback>", "Answer: fixed"))
        self.commit("a.txt", "b\n", "fix: the value")
        self.run_ok("coder", "check", *SLUG, "--write")

    def code_signed(self, **kw):
        """Code round 1 signed off."""
        self.coding(**kw)
        self.stage(CODE_SIGNED_1)
        self.put("CODEREVIEW.md", "# Code review, round 1\n\nSIGNED OFF. Nothing open.\n\n## New findings\n")

    def folded(self, **kw):
        self.code_signed(**kw)
        self.stage("fold folded %s signed %s" % (self.sha(), self.sha()))

    def plan_review_written(self):
        self.plan()
        self.run_ok("doorbell", "ring", "--role", "Planner", *CC, *SLUG, "--write")
        self.run_ok("review", "start", "--role", "Plan-Reviewer", *SLUG, "--write")
        self.put("PLAN-REVIEW.md", PLAN_REVIEW_1)

    def code_review_written(self):
        self.coding()
        self.run_ok("review", "start", "--role", "Code-Reviewer", *SLUG, "--write")
        text = self.read("CODEREVIEW.md")
        text = text.replace("code-review: <ran | did not resolve, the Spec reviewed by hand>", "code-review: ran")
        self.put("CODEREVIEW.md", text)

    # --- a whole loop, every Recap section written by the tool ---

    def fill(self, name, *pairs):
        """Replace the first old of each (old, new) in a Working file,
        failing when old is missing, so a changed frame shows here first."""
        text = self.read(name)
        for old, new in pairs:
            self.assertIn(old, text, name)
            text = text.replace(old, new, 1)
        self.put(name, text)

    def plan_rounds(self):
        """Plan round 1 with two findings open, round 2 signing off with both
        fixed."""
        self.plan()
        self.run_ok("doorbell", "ring", "--role", "Planner", *CC, *SLUG, "--write")
        self.run_ok("review", "start", "--role", "Plan-Reviewer", *SLUG, "--write")
        self.put("PLAN-REVIEW.md", PLAN_REVIEW_1)
        self.run_ok("review", "check", "--role", "Plan-Reviewer", *SLUG, "--write")
        self.run_ok("doorbell", "ring", "--role", "Planner", *CC, *SLUG, "--write")
        self.run_ok("review", "start", "--role", "Plan-Reviewer", *SLUG, "--write")
        self.fill("PLAN-REVIEW.md",
                  ("writing-for-agents: <ran | did not resolve | not needed, <reason>>", "writing-for-agents: ran"),
                  ("### 1. major (open)", "### 1. major (fixed)"),
                  ("### 2. minor (open)", "### 2. minor (fixed)"),
                  ("The Spec does not say how amounts are written.",
                   "The Spec does not say how amounts are written.\n\nResolution: the Spec names two decimals."),
                  ("Ticket 02 leaves `summary` out.",
                   "Ticket 02 leaves `summary` out.\n\nResolution: Ticket 02 names `summary`."))
        self.run_ok("review", "check", "--role", "Plan-Reviewer", *SLUG, "--write")

    def code_round_one(self):
        """The Coder's round 1, both Tickets, on the feature branch."""
        self.run_ok("coder", "start", *SLUG, "--write")
        self.put("FIXES.md", self.read("FIXES.md").replace(
            "Files:\nChange:\nVerified:", "Files: `a.txt`\nChange: wrote a.\nVerified: the test passed."))
        self.commit("a.txt", "a\n", "feat: a")
        self.run_ok("coder", "check", *SLUG, "--write")

    def code_review(self, *pairs):
        """A code review round, its frame filled with pairs."""
        self.run_ok("review", "start", "--role", "Code-Reviewer", *SLUG, "--write")
        self.fill("CODEREVIEW.md", *pairs)
        self.run_ok("review", "check", "--role", "Code-Reviewer", *SLUG, "--write")

    def answered(self, numbers, name, text, message):
        """A later Coder round fixing each open finding in numbers."""
        self.run_ok("coder", "start", *SLUG, "--write")
        self.fill("FIXES.md", *[("Answer: <fixed | pushback>", "Answer: fixed")] * len(numbers))
        self.commit(name, text, message)
        self.run_ok("coder", "check", *SLUG, "--write")

    def code_two_signed(self):
        """Plan rounds with closed findings, round 1's Tickets, a code
        finding closed in round 2 with a Not carried line in round 1, and
        round 2 signed off: the fold absorbs the fix and moves the branch."""
        self.plan_rounds()
        self.code_round_one()
        self.code_review(
            ("code-review: <ran | did not resolve, the Spec reviewed by hand>", "code-review: ran"),
            ("## New findings\n", "## New findings\n\n### 1. major (open): a.txt:1\n\nThe value is wrong.\n"),
            ("- <the problem, in one line>: <why not> -->",
             "- <the problem, in one line>: <why not> -->\n- the report's style nit on a.txt: not a defect"))
        self.answered([1], "a.txt", "b\n", "fix: the value")
        self.code_review(
            ("code-review: <ran | did not resolve, the Spec reviewed by hand | not needed, <reason>>",
             "code-review: ran"),
            ("### 1. major (open): a.txt:1", "### 1. major (fixed): a.txt:1"),
            ("Coder: fixed in round 2.", "Coder: fixed in round 2.\n\nResolution: a.txt holds b."))

    def whole_loop(self):
        """A loop through every Recap section: code_two_signed, the fold, the
        user's findings closed in round 3, and a second fold."""
        self.code_two_signed()
        self.run_ok("loop", "fold", *SLUG, *CC, "--write")
        self.box.write("findings.md", FINDINGS)
        self.run_ok("review", "add", *SLUG, "--from", "findings.md", "--write")
        self.answered([2, 3], "b.txt", "b\n", "fix: the user's findings")
        self.code_review(
            ("code-review: <ran | did not resolve, the Spec reviewed by hand | not needed, <reason>>",
             "code-review: ran"),
            ("### 2. major (open): docs/a.md:3", "### 2. major (fixed): docs/a.md:3"),
            ("### 3. minor (open): src/b.py:9", "### 3. minor (accepted): src/b.py:9"),
            ("Coder: fixed in round 3.", "Coder: fixed in round 3.\n\nResolution: the heading names it."),
            ("Coder: fixed in round 3.\n\n## New", "Coder: fixed in round 3.\n\nResolution: the name stays.\n\n## New"))
        self.run_ok("loop", "fold", *SLUG, *CC, "--write")

    def origin(self):
        """A local bare origin with main pushed."""
        bare = os.path.join(self.box.root, "origin.git")
        self.git("init", "-q", "--bare", bare)
        self.git("remote", "add", "origin", bare)
        self.git("push", "-q", "origin", "main")

    def github(self, remote=True, **plan):
        """The gh fake of test_pr.py on the sandbox's bin directory, playing
        plan, and git ls-remote stubbed to pass; with remote, origin at a
        GitHub URL whose push goes to a local bare repository. The stubs are
        POSIX scripts, so a row on this scene skips on native Windows."""
        log = os.path.join(self.box.root, "gh.log")
        plan_file = os.path.join(self.box.root, "gh-plan.json")
        with open(plan_file, "w") as handle:
            json.dump(plan, handle)
        self.box.stub("git", "if [ \"$1\" = ls-remote ]; then exit 0; fi\nexec '%s' \"$@\"\n" % shutil.which("git"))
        self.box.stub("gh", GH % {"python": sys.executable, "log": log, "plan": plan_file})
        if remote:
            bare = os.path.join(self.box.root, "bare.git")
            subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
            self.git("remote", "add", "origin", URL)
            self.git("config", "url.%s.pushInsteadOf" % bare, URL)

    def pr_check_open(self):
        self.code_signed(pr="yes")
        self.github(merged=[0, "[]", ""], head=[0, "[]", ""])

    def pr_check_existing(self):
        self.code_signed(pr="yes")
        self.github(merged=[0, "[]", ""], head=[0, json.dumps([{"url": PR_URL}]), ""])

    def pr_check_neither(self):
        self.code_signed(pr="yes")
        self.github(remote=False, merged=[0, "[]", ""])

    def pr_open_open(self):
        self.folded(pr="yes")
        self.github(auth=[0, "", ""], head=[0, "[]", ""], create=[0, PR_URL + "\n", ""])
        self.put("pr-body.md", "feat: a\n\nThe body.\n")

    def pr_open_existing(self):
        self.folded(pr="yes")
        self.github(auth=[0, "", ""], head=[0, json.dumps([{"url": PR_URL}]), ""])
        self.put("pr-body.md", "feat: a\n\nThe body.\n")

    def store(self):
        """An idea store with a family and a closed idea."""
        self.repo()
        for argv in (("--slug", "main-idea", "--title", "Main idea", "--tldr", "The whole thing."),
                     ("--slug", "part-one", "--title", "Part one", "--tldr", "The first half.", "--parent",
                      "main-idea"),
                     ("--slug", "other", "--title", "Other", "--tldr", "Needs part one.", "--relate",
                      "depends on part-one: builds on it"),
                     ("--slug", "old", "--title", "Old", "--tldr", "Done long ago.")):
            self.run_ok("brainstorm", "new", *argv, "--write")
        self.run_ok("brainstorm", "set", "--idea", "old", "--status", "done", "--decision", "Shipped.", "--write")

    def legacy_store(self):
        self.repo()
        self.box.write(".scratch/_brainstorming/index.md", LEGACY_INDEX)
        self.box.write(".scratch/_brainstorming/old-idea.md", LEGACY_IDEA)

    def codex_armed(self):
        """An armed Codex Orchestrator with a Doorbell waiting, and the
        Shared copy the hook's reason names, so the Next: sweep can run it."""
        shutil.copytree(SCRIPTS, self.box.shared, ignore=shutil.ignore_patterns("__pycache__"))
        self.box.write_loop("feat", harness="Codex")
        self.box.write(os.path.join(".scratch", "feat", "codex-armed-" + CODEX_ID),
                       "vdd codex-armed 1\nOrchestrator 0\n")
        with open(self.box.path(".scratch", "feat", "doorbells"), "wb") as handle:
            handle.write(("10:00:00 to: Orchestrator VDD Planner: .scratch/feat/ ready, round 1. "
                          "Read spec.md and issues/.\n").encode())

    def codex_armed_newer_doorbells(self):
        """An armed Codex Orchestrator whose Doorbell file has a format
        version this copy does not know: the wait fails after the claim."""
        self.codex_armed()
        with open(self.box.path(".scratch", "feat", "doorbells"), "wb") as handle:
            handle.write(b"# vdd doorbells 99\n")

    def wayfinder_installed(self):
        self.repo()
        self.box.write(os.path.join(self.box.home, ".claude", "plugins", "cache", "mattpocock", "mattpocock-skills",
                                    "1.0.0", "skills", "wayfinder", "SKILL.md"),
                       "---\nname: wayfinder\n---\n", base=self.box.root)

    def read_only_state(self):
        self.plan("respawn Coder never")
        path = self.box.path(self.rel("loop-state"))
        os.chmod(path, stat.S_IREAD)
        self.addCleanup(os.chmod, path, stat.S_IWRITE | stat.S_IREAD)

    def damaged_state(self):
        self.plan()
        self.put("loop-state", "not a state file\nloop open\n")

    def newer_state(self):
        self.plan()
        self.put("loop-state", "vdd loop-state 9\nloop open\n")

    # --- running ---

    def env(self, extra=None):
        values = {"VDD_TODAY": TODAY}
        values.update(extra or {})
        return self.box.env(**values)

    def no_gh(self):
        """The environment with git on PATH and gh off it."""
        path = self.box.git_only_path()
        if path is None:
            self.skipTest("gh sits beside git on this machine")
        return {"PATH": path}

    def gh_on_path(self):
        """The environment with the sandbox's bin directory, which holds the
        gh fake, first on PATH."""
        return {"PATH": self.box.bin + os.pathsep + os.environ.get("PATH", "")}

    def run_ok(self, *argv):
        result = self.box.run(*argv, env=self.env())
        self.assertEqual(result.code, 0, result)
        return result
