"""Golden transcripts: every command's success output in its common staged
states, pinned whole.

One table drives the module. Each row names a group, a command, a case, a
staged scene and the argv; its golden file, golden/<group>/<command>-<case>.txt,
holds the argv line, the exit code and the normalised standard output. With
VDD_UPDATE_GOLDENS=1 a row writes its file instead of comparing; without it a
missing file fails. Normalisation makes one golden hold on every OS: the
sandbox's directories, the repository and the home become placeholders, shas
become <sha>, CRLF becomes LF, a \\ between path characters becomes /, the
interpreter before the tool's path becomes <python>, and Setup's git version
becomes <version>. VDD_TODAY fixes the dates.
"""

import json
import os
import re
import stat
import subprocess
import unittest

from vddtest import PLAN_SIGNED, REPO, WINDOWS, LoopRepoTest

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")
UPDATE = os.environ.get("VDD_UPDATE_GOLDENS") == "1"
TODAY = "2026-10-20"
CC = ("--harness", "claude-code")
SLUG = ("--slug", "demo")

P1 = "VDD Planner: .scratch/demo/ ready, round 1. Read spec.md and issues/."
P2 = "VDD Planner: .scratch/demo/ ready, round 2. Read spec.md and issues/."
PLAN_OPEN_1 = "plan 1 reviewed open 1,2 counts 0 1 1 next 3 new 2 closed 0 checks writing-for-agents ran"
PLAN_SIGNED_2 = "plan 2 reviewed signed-off - counts 0 0 0 next 3 new 0 closed 2 checks writing-for-agents ran"
CODE_OPEN_1 = "code 1 reviewed open 1 counts 0 1 0 next 2 new 1 closed 0 checks code-review ran"
CODE_SIGNED_1 = "code 1 reviewed signed-off - counts 0 0 0 next 1 new 0 closed 0 checks code-review ran"
CODE_SIGNED_2 = "code 2 reviewed signed-off - counts 0 0 0 next 2 new 0 closed 1 checks code-review ran"
CODEX_ID = "019a0001-aaaa-7bbb-8ccc-0123456789ab"

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


def git_objects(box):
    """Every object name in the project's repository, for telling a sha
    from other hex: an abbreviated sha may be all digits."""
    if not os.path.isdir(os.path.join(box.proj, ".git")):
        return []
    proc = subprocess.run(["git", "cat-file", "--batch-all-objects", "--batch-check=%(objectname)"],
                          cwd=box.proj, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.stdout.decode("ascii", "replace").split()


def normalise(text, box):
    """The output as a golden holds it, the same on every OS."""
    text = text.replace("\r\n", "\n")
    places = []
    for path, name in ((box.shared, "<shared>"), (box.proj, "<project>"), (box.home, "<home>"),
                       (box.data, "<data>"), (box.root, "<sandbox>"), (REPO, "<repo>")):
        for variant in {path, os.path.realpath(path), os.path.normpath(path)}:
            places.append((variant, name))
            places.append((variant.replace("\\", "/"), name))
            places.append((variant.replace("\\", "\\\\"), name))
    for variant, name in sorted(places, key=lambda pair: -len(pair[0])):
        text = text.replace(variant, name)
    text = re.sub(r"(?<=[\w.>-])\\\\?(?=[\w.<-])", "/", text)
    text = re.sub(r'(?:py -3|python3|"?[^\s"]*python[0-9.]*(?:\.exe)?"?) (?=\\?["\']?<(?:repo|shared)>)', "<python> ", text)
    objects = git_objects(box)
    text = re.sub(r"\b[0-9a-f]{7,40}\b",
                  lambda m: "<sha>" if len(m.group(0)) == 40 or any(o.startswith(m.group(0)) for o in objects)
                  else m.group(0), text)
    text = re.sub(r"(git version: )\S+", r"\1<version>", text)
    text = re.sub(r"(git version )[0-9][^\s,]*", r"\1<version>", text)
    return text


class Golden(LoopRepoTest):
    maxDiff = None

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

    def origin(self):
        """A local bare origin with main pushed."""
        bare = os.path.join(self.box.root, "origin.git")
        self.git("init", "-q", "--bare", bare)
        self.git("remote", "add", "origin", bare)
        self.git("push", "-q", "origin", "main")

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
        self.box.write_loop("feat", harness="Codex")
        self.box.write(os.path.join(".scratch", "feat", "codex-armed-" + CODEX_ID),
                       "vdd codex-armed 1\nOrchestrator 0\n")
        with open(self.box.path(".scratch", "feat", "doorbells"), "wb") as handle:
            handle.write(("10:00:00 to: Orchestrator VDD Planner: .scratch/feat/ ready, round 1. "
                          "Read spec.md and issues/.\n").encode())

    def wayfinder_installed(self):
        self.repo()
        self.box.write(os.path.join(self.box.home, ".claude", "plugins", "cache", "x", "wayfinder", "SKILL.md"),
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

    def run_ok(self, *argv):
        result = self.box.run(*argv, env=self.env())
        self.assertEqual(result.code, 0, result)
        return result

    def check_row(self, group, command, case, scene, argv, env=None, stdin=None, code=0):
        scene(self)
        if callable(env):
            env = env(self)
        result = self.box.run(*argv, env=self.env(env), stdin=stdin)
        self.assertEqual(result.code == 0, code == 0, result)
        actual = "$ vdd %s\nexit %d\n%s" % (normalise(" ".join(argv), self.box), result.code,
                                            normalise(result.text, self.box))
        path = os.path.join(GOLDEN, group, "%s-%s.txt" % (command, case))
        if UPDATE:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(actual.encode("utf-8"))
            return
        if not os.path.exists(path):
            self.fail("%s is missing: run the suite with VDD_UPDATE_GOLDENS=1 to write it"
                      % os.path.relpath(path, REPO))
        with open(path, "rb") as handle:
            expected = handle.read().decode("utf-8")
        self.assertEqual(expected, actual, "golden %s differs" % os.path.relpath(path, REPO))


S = Golden

ROWS = [
    # group, command, case, scene, argv, env, stdin, exit (0 success, 1 refusal)
    ("loop", "new", "dry-run", S.repo, ("loop", "new", *SLUG, *CC), None, None, 0),
    ("loop", "new", "write", S.repo, ("loop", "new", *SLUG, *CC, "--minors", "fix", "--pr", "ask at sign-off",
                                       "--write"), None, None, 0),
    ("loop", "aside", "write", S.plan, ("loop", "aside", *SLUG, "--write"), None, None, 0),
    ("loop", "show", "all", S.plan, ("loop", "show", *SLUG), None, None, 0),
    ("loop", "show", "role-coder", S.signed, ("loop", "show", *SLUG, "--role", "Coder"), None, None, 0),
    ("loop", "show", "role-pr-author", S.code_signed, ("loop", "show", *SLUG, "--role", "PR-Author"), None, None, 0),
    ("loop", "set", "write", S.plan, ("loop", "set", *SLUG, "--minors", "leave", "--write"), None, None, 0),
    ("loop", "fold", "dry-run", S.code_signed, ("loop", "fold", *SLUG, *CC), None, None, 0),
    ("loop", "fold", "write", S.code_signed, ("loop", "fold", *SLUG, *CC, "--write"), None, None, 0),
    ("loop", "close", "write", S.plan, ("loop", "close", *SLUG, "--write"), None, None, 0),
    ("loop", "reopen", "write", lambda t: (t.plan(), t.stage("loop closed")), ("loop", "reopen", *SLUG, "--write"),
     None, None, 0),

    ("doorbell", "ring", "planner-dry-run", S.plan, ("doorbell", "ring", "--role", "Planner", *CC, *SLUG), None,
     None, 0),
    ("doorbell", "ring", "planner-write", S.plan, ("doorbell", "ring", "--role", "Planner", *CC, *SLUG, "--write"),
     None, None, 0),
    ("doorbell", "ring", "orchestrator-open", lambda t: (t.plan(), t.rings(P1), t.stage(PLAN_OPEN_1)),
     ("doorbell", "ring", "--role", "Orchestrator", *CC, *SLUG, "--write"), None, None, 0),
    ("doorbell", "wait", "pending", lambda t: (t.plan(), t.rings(P1)),
     ("doorbell", "wait", "--role", "Orchestrator", *CC, *SLUG), None, None, 0),
    ("doorbell", "wait", "codex-arms", S.plan, ("doorbell", "wait", "--role", "Orchestrator", "--harness", "codex",
                                                *SLUG), {"CODEX_THREAD_ID": CODEX_ID}, None, 0),
    ("doorbell", "take", "pending", lambda t: (t.plan(), t.rings(P1)),
     ("doorbell", "take", "--role", "Orchestrator", *CC, *SLUG), None, None, 0),
    ("doorbell", "take", "none-pending", S.plan, ("doorbell", "take", "--role", "Orchestrator", *CC, *SLUG), None,
     None, 0),
    ("doorbell", "take", "pasted", S.plan, ("doorbell", "take", "--role", "Orchestrator", *CC, *SLUG, "--pasted",
                                            P1), None, None, 0),

    ("coder", "start", "round-1", S.signed, ("coder", "start", *SLUG, "--write"), None, None, 0),
    ("coder", "start", "round-2", S.round_two, ("coder", "start", *SLUG, "--write"), None, None, 0),
    ("coder", "check", "dry-run", S.coder_started, ("coder", "check", *SLUG), None, None, 0),
    ("coder", "check", "write", S.coder_started, ("coder", "check", *SLUG, "--write"), None, None, 0),

    ("review", "start", "plan-round-1", lambda t: (t.plan(), t.run_ok("doorbell", "ring", "--role", "Planner", *CC,
                                                                     *SLUG, "--write")),
     ("review", "start", "--role", "Plan-Reviewer", *SLUG, "--write"), None, None, 0),
    ("review", "start", "plan-round-2", lambda t: (t.plan_review_written(),
                                                   t.run_ok("review", "check", "--role", "Plan-Reviewer", *SLUG,
                                                            "--write"),
                                                   t.run_ok("doorbell", "ring", "--role", "Planner", *CC, *SLUG,
                                                            "--write")),
     ("review", "start", "--role", "Plan-Reviewer", *SLUG, "--write"), None, None, 0),
    ("review", "start", "code-round-1", S.coding, ("review", "start", "--role", "Code-Reviewer", *SLUG, "--write"),
     None, None, 0),
    ("review", "start", "code-round-2", S.code_round_two_answered,
     ("review", "start", "--role", "Code-Reviewer", *SLUG, "--write"), None, None, 0),
    ("review", "check", "plan-dry-run", S.plan_review_written,
     ("review", "check", "--role", "Plan-Reviewer", *SLUG), None, None, 0),
    ("review", "check", "plan-write", S.plan_review_written,
     ("review", "check", "--role", "Plan-Reviewer", *SLUG, "--write"), None, None, 0),
    ("review", "check", "code-signed-off", S.code_review_written,
     ("review", "check", "--role", "Code-Reviewer", *SLUG, "--write"), None, None, 0),
    ("review", "add", "dry-run", lambda t: (t.code_signed(), t.box.write("findings.md", FINDINGS)),
     ("review", "add", *SLUG, "--from", "findings.md"), None, None, 0),
    ("review", "add", "write", lambda t: (t.code_signed(), t.stage("loop closed"),
                                          t.box.write("findings.md", FINDINGS)),
     ("review", "add", *SLUG, "--from", "findings.md", "--write"), None, None, 0),

    ("orchestrator", "start", "waiting", lambda t: t.plan(policies=("respawn Coder never",)),
     ("orchestrator", "start", *SLUG, *CC), None, None, 0),
    ("orchestrator", "start", "spawn-plan-reviewer", lambda t: (t.plan(policies=("respawn Coder never",)),
                                                                t.rings(P1)),
     ("orchestrator", "start", *SLUG, *CC), None, None, 0),
    ("orchestrator", "start", "relay-then-wait", lambda t: (t.plan(policies=("respawn Coder never",)), t.rings(P1),
                                                            t.stage(PLAN_OPEN_1)),
     ("orchestrator", "start", *SLUG, *CC), None, None, 0),
    ("orchestrator", "start", "spawn-coder", lambda t: (t.plan(policies=("respawn Coder never",)), t.rings(P1, P2),
                                                        t.stage(PLAN_OPEN_1, PLAN_SIGNED_2)),
     ("orchestrator", "start", *SLUG, *CC), None, None, 0),
    ("orchestrator", "start", "asks-respawn-policy", S.plan, ("orchestrator", "start", *SLUG, *CC), None, None, 0),
    ("orchestrator", "start", "fold", lambda t: t.code_signed(policies=("respawn Coder never",)),
     ("orchestrator", "start", *SLUG, *CC), None, None, 0),
    ("orchestrator", "start", "pr-step", lambda t: t.folded(policies=("respawn Coder never",)),
     ("orchestrator", "start", *SLUG, *CC), None, None, 0),
    ("orchestrator", "return", "plan-reviewer", lambda t: (t.plan(policies=("respawn Coder never",)), t.rings(P1),
                                                           t.stage("orchestrator session 1",
                                                                   "spawn Plan-Reviewer 1 session 1", PLAN_OPEN_1)),
     ("orchestrator", "return", "--role", "Plan-Reviewer", *SLUG, *CC), None, None, 0),
    ("orchestrator", "return", "code-reviewer-open", lambda t: (t.round_two(),
                                                                t.stage("orchestrator session 1",
                                                                        "spawn Code-Reviewer 1 session 1")),
     ("orchestrator", "return", "--role", "Code-Reviewer", *SLUG, *CC), None, None, 0),
    ("orchestrator", "return", "coder", S.coder_returned,
     ("orchestrator", "return", "--role", "Coder", *SLUG, *CC), None, None, 0),
    ("orchestrator", "return", "planner", S.planner_returned,
     ("orchestrator", "return", "--role", "Planner", *SLUG, *CC), None, None, 0),
    ("orchestrator", "respawn", "policy", S.plan,
     ("orchestrator", "respawn", "--role", "Coder", "--policy", "every round", *SLUG, "--write"), None, None, 0),
    ("orchestrator", "respawn", "once", lambda t: t.plan(policies=("respawn Coder never",)),
     ("orchestrator", "respawn", "--role", "Coder", "--once", *SLUG, "--write"), None, None, 0),
    ("orchestrator", "tokens", "coder", lambda t: (t.signed(policies=("respawn Coder over 100k",)),
                                                   t.stage("orchestrator session 1", "spawn Coder 1 session 1")),
     ("orchestrator", "tokens", "--role", "Coder", "--tokens", "52000", *SLUG), None, None, 0),

    ("pr", "check", "manual", lambda t: t.code_signed(pr="manual"), ("pr", "check", *SLUG, *CC), S.no_gh, None, 0),
    ("pr", "check", "no", lambda t: t.code_signed(pr="no"), ("pr", "check", *SLUG, *CC), S.no_gh, None, 0),
    ("pr", "check", "template-push-only", lambda t: (t.code_signed(pr="yes"), t.origin(),
                                                     t.box.write(".github/pull_request_template.md", "## What\n")),
     ("pr", "check", *SLUG, *CC), S.no_gh, None, 0),
    ("pr", "open", "push-only", lambda t: (t.folded(pr="yes"), t.origin(),
                                           t.put("pr-body.md", "feat: a\n\nThe body.\n")),
     ("pr", "open", "--path", "push-only", *SLUG, *CC, "--write"), S.no_gh, None, 0),
    ("pr", "check", "open", S.pr_check_open, ("pr", "check", *SLUG, *CC), S.gh_on_path, None, 0),
    ("pr", "check", "existing", S.pr_check_existing, ("pr", "check", *SLUG, *CC), S.gh_on_path, None, 0),
    ("pr", "check", "neither", S.pr_check_neither, ("pr", "check", *SLUG, *CC), S.gh_on_path, None, 0),
    ("pr", "open", "open", S.pr_open_open, ("pr", "open", "--path", "open", *SLUG, *CC, "--write"), S.gh_on_path,
     None, 0),
    ("pr", "open", "existing", S.pr_open_existing, ("pr", "open", "--path", "existing", *SLUG, *CC, "--write"),
     S.gh_on_path, None, 0),

    ("wayfinder", "start", "no-map", S.wayfinder_installed,
     ("wayfinder", "start", "--effort", "demo", "--skill-dir", os.path.join(REPO, "skills", "vdd-wayfinder")),
     None, None, 0),

    ("setup", "setup", "dry-run", S.repo, ("setup", *CC, "--listed", "writing-for-agents", "--glossary-named", "yes"),
     None, None, 0),
    ("setup", "setup", "write", S.repo, ("setup", *CC, "--listed", "writing-for-agents", "--glossary-named", "yes",
                                         "--write"), None, None, 0),
    ("setup", "setup", "codex", S.repo, ("setup", "--harness", "codex", "--listed", "none", "--glossary-named",
                                         "absent"), None, None, 0),

    ("brainstorm", "start", "store", S.store, ("brainstorm", "start"), None, None, 0),
    ("brainstorm", "show", "family", S.store, ("brainstorm", "show", "--idea", "main-idea"), None, None, 0),
    ("brainstorm", "find", "words", S.store, ("brainstorm", "find", "--text", "half"), None, None, 0),
    ("brainstorm", "check", "clean", S.store, ("brainstorm", "check"), None, None, 0),
    ("brainstorm", "new", "dry-run", S.store, ("brainstorm", "new", "--slug", "second-half", "--title", "Second half",
                                               "--tldr", "The second half."), None, None, 0),
    ("brainstorm", "new", "write", S.store, ("brainstorm", "new", "--slug", "second-half", "--title", "Second half",
                                             "--tldr", "The second half.", "--parent", "main-idea", "--write"),
     None, None, 0),
    ("brainstorm", "note", "next-step", S.store, ("brainstorm", "note", "--idea", "main-idea", "--section",
                                                  "Next Steps", "--text", "Count the cost.", "--write"),
     None, None, 0),
    ("brainstorm", "set", "status", S.store, ("brainstorm", "set", "--idea", "other", "--status", "shaped",
                                              "--importance", "large", "--write"), None, None, 0),
    ("brainstorm", "move", "top", S.store, ("brainstorm", "move", "--set", "part-one=top", "--write"), None, None, 0),
    ("brainstorm", "split", "parts", S.store, ("brainstorm", "split", "--idea", "other", "--part",
                                               "other-a | Other A | The first piece.", "--write"), None, None, 0),
    ("brainstorm", "merge", "into", S.store, ("brainstorm", "merge", "--idea", "other", "--into", "part-one",
                                              "--reason", "The same idea.", "--reopen-when", "They part.",
                                              "--write"), None, None, 0),
    ("brainstorm", "rename", "to", S.store, ("brainstorm", "rename", "--idea", "other", "--to", "another",
                                             "--write"), None, None, 0),
    ("brainstorm", "cleanup", "done", S.store, ("brainstorm", "cleanup", "--status", "done", "--write"), None, None,
     0),
    ("brainstorm", "migrate", "dry-run", S.legacy_store, ("brainstorm", "migrate",), None, None, 0),
    ("brainstorm", "migrate", "write", S.legacy_store, ("brainstorm", "migrate", "--write"), None, None, 0),

    ("codex-stop", "codex-stop", "armed", S.codex_armed, ("codex-stop",), None,
     json.dumps({"session_id": CODEX_ID, "turn_id": "t1", "hook_event_name": "Stop", "stop_hook_active": False,
                 "last_assistant_message": "Done."}).encode("utf-8"), 0),

    # The refusals in loopstate.header, textfile.check_header and
    # State.persist. A damaged header never reaches loopstate.header's own
    # line: every caller reads the state file through the loop finder, which
    # takes a damaged one for no loop, so its row pins what a Role sees.
    ("refusal", "loopstate-header", "damaged", S.damaged_state, ("loop", "show", *SLUG), None, None, 1),
    ("refusal", "check-header", "newer-version", S.newer_state, ("loop", "show", *SLUG), None, None, 1),
    ("refusal", "state-persist", "read-only", S.read_only_state, ("orchestrator", "start", *SLUG, *CC), None, None,
     1),
]


def make_test(row):
    group, command, case, scene, argv, env, stdin, code = row

    def test(self):
        if WINDOWS and env is Golden.gh_on_path:
            self.skipTest("the gh fake and the git stub are POSIX scripts")
        if scene is Golden.read_only_state and not WINDOWS and hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root writes a read-only file")
        self.check_row(group, command, case, scene, argv, env, stdin, code)

    test.__doc__ = "Prevents an unseen change to %s %s, %s." % (group, command, case)
    return test


for _row in ROWS:
    _name = "test_%s_%s_%s" % tuple(re.sub(r"\W", "_", part) for part in _row[:3])
    assert not hasattr(Golden, _name), _name
    setattr(Golden, _name, make_test(_row))


del S


class GoldenFileTest(unittest.TestCase):
    def test_a_row_without_its_file_fails(self):
        """Prevents a new row that passes by having no golden file."""
        if UPDATE:
            self.skipTest("VDD_UPDATE_GOLDENS writes the file instead")
        row = Golden("test_loop_show_all")
        row.setUp()
        try:
            with self.assertRaises(AssertionError) as caught:
                row.check_row("loop", "show", "no-such-golden", Golden.plan, ("loop", "show", *SLUG))
            self.assertIn("show-no-such-golden.txt is missing", str(caught.exception))
        finally:
            row.doCleanups()

    def test_every_golden_file_has_a_row(self):
        """Prevents a stale golden file left behind by a removed row."""
        named = set(os.path.join(row[0], "%s-%s.txt" % (row[1], row[2])) for row in ROWS)
        found = set()
        if os.path.isdir(GOLDEN):
            for directory, _, names in os.walk(GOLDEN):
                for name in names:
                    found.add(os.path.relpath(os.path.join(directory, name), GOLDEN))
        if UPDATE:
            for stale in found - named:
                os.remove(os.path.join(GOLDEN, stale))
            return
        self.assertEqual(sorted(found - named), [])


if __name__ == "__main__":
    unittest.main()
