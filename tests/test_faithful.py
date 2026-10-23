"""Dry runs that refuse where --write refuses and name exactly what it
writes, a loop a newer VDD wrote left out of the slug-less lookup by name,
and no run without a Next: line, driven through vdd.py."""

import json
import os
import re
import shutil
import unittest

from scenes import CC, CODEX_ID, FINDINGS, P1, P2, PLAN_OPEN_1, PLAN_REVIEW_1, SLUG, Staged

WINDOWS = os.name == "nt"
BROKEN = "{broken"
UNREADABLE = ".scratch/demo/recap.json is not a Recap records file this tool wrote"
ARMED = "codex-armed-" + CODEX_ID


class Faithful(Staged):
    def refuses_like_write(self, argv, fragment, extra=None):
        dry = self.box.run(*argv, env=self.env(extra))
        written = self.box.run(*(argv + ("--write",)), env=self.env(extra))
        for result in (dry, written):
            self.assertEqual(result.code, 1, result)
            self.assertIn(fragment, result.text)
            self.assertTrue(result.last.startswith("Next: "), result)
        self.assertEqual(dry.lines, written.lines)


class DryRuns(Faithful):
    def test_coder_start_on_a_third_branch(self):
        """Prevents a dry run of coder start passing where --write refuses
        on a branch that is neither the base nor the feature branch."""
        self.signed()
        self.git("checkout", "-q", "-b", "elsewhere")
        self.refuses_like_write(("coder", "start", *SLUG), "neither the base branch main nor the feature branch demo")

    def test_review_start_with_a_finding_heading_gone(self):
        """Prevents a dry run of review start passing while CODEREVIEW.md has
        lost a finding the loop still has open."""
        self.code_round_two_answered()
        self.put("CODEREVIEW.md", self.read("CODEREVIEW.md").replace("### 1. major (open): a.txt:1\n", ""))
        self.refuses_like_write(("review", "start", "--role", "Code-Reviewer", *SLUG), "no longer holds finding 1")

    def test_review_start_with_a_carried_finding_gone(self):
        """Prevents a dry run of review start passing while PLAN-REVIEW.md has
        lost a finding round 1 left open."""
        self.plan()
        self.rings(P1, P2)
        self.stage("plan 1 review-started", PLAN_OPEN_1)
        self.put("PLAN-REVIEW.md", PLAN_REVIEW_1.replace("### 2. minor (open): Ticket 02\n", ""))
        self.refuses_like_write(("review", "start", "--role", "Plan-Reviewer", *SLUG), "no longer holds finding 2")


    # --- the Recap's records, loaded before a dry run returns ---

    def test_review_check_with_a_damaged_records_file(self):
        """Prevents a dry run of review check passing while --write refuses a
        recap.json it cannot read."""
        self.plan_review_written()
        self.put("recap.json", BROKEN)
        self.refuses_like_write(("review", "check", "--role", "Plan-Reviewer", *SLUG), UNREADABLE)

    def test_coder_check_with_a_damaged_records_file(self):
        """Prevents a dry run of coder check passing while --write refuses a
        recap.json it cannot read."""
        self.coder_started()
        self.put("recap.json", BROKEN)
        self.refuses_like_write(("coder", "check", *SLUG), UNREADABLE)

    def test_review_add_with_a_damaged_records_file(self):
        """Prevents a dry run of review add passing while --write refuses a
        recap.json it cannot read."""
        self.folded()
        self.box.write("findings.md", FINDINGS)
        self.put("recap.json", BROKEN)
        self.refuses_like_write(("review", "add", *SLUG, "--from", "findings.md"), UNREADABLE)

    def test_loop_fold_with_a_newer_records_file(self):
        """Prevents a dry run of loop fold printing Would fold while --write
        refuses a recap.json a newer VDD wrote."""
        self.code_signed()
        self.put("recap.json", json.dumps({"format": 2, "records": []}))
        self.refuses_like_write(("loop", "fold", *SLUG, *CC), "has format version 2")

    @unittest.skipIf(WINDOWS, "a git wrapper on PATH is a POSIX script")
    def test_coder_start_with_ls_files_failing(self):
        """Prevents a dry run of coder start passing while --write fails on
        git ls-files after it switched the branch and wrote FIXES.md."""
        self.signed()
        real = shutil.which("git")
        self.box.stub("git", 'for a in "$@"; do if [ "$a" = ls-files ]; then echo "fatal: ls-files broke" >&2; '
                             "exit 128; fi; done\nexec '%s' \"$@\"\n" % real)
        path = {"PATH": self.box.bin + os.pathsep + os.environ.get("PATH", "")}
        self.refuses_like_write(("coder", "start", *SLUG), "git ls-files failed", path)
        self.assertEqual(self.git("branch", "--show-current"), "main")
        self.assertFalse(self.exists("FIXES.md"))


class MovedRef(Staged):
    def test_dry_run_and_write_agree_on_a_fold_that_moved_the_ref(self):
        """Prevents a dry run that says the fold would skip, because the
        branch moved, where --write records the fold an earlier run moved
        the branch for and stopped before its state line."""
        self.code_signed()
        signed = self.sha()
        tip = self.commit("b.txt", "b\n", "feat: b")
        self.put("recap.json", json.dumps({"format": 1, "records": [{
            "key": "fold " + signed, "section": "Commits", "lines": ["Folded demo: 2 commits into 1.", ""],
            "data": {"tip": tip, "before": 2, "after": 1, "report": []}}]}))
        dry = self.run_ok("loop", "fold", *SLUG, *CC)
        self.assertEqual(dry.lines[0], "Would record the fold of demo: it is at the folded tip %s, which an earlier "
                         "fold moved it to before it stopped." % tip[:7], dry)
        self.assertNotIn("skip", dry.text)
        written = self.run_ok("loop", "fold", *SLUG, *CC, "--write")
        self.assertEqual(written.lines[0], "Folded demo: 2 commits into 1.", written)
        self.assertIn("fold folded %s signed %s" % (tip, signed), self.state())
        self.assertEqual(self.sha("demo"), tip)



NEW = ("loop", "new", *SLUG, *CC, "--minors", "fix", "--pr", "no")


class LoopRefusals(Faithful):
    """Every loop write command's dry run refuses where its --write does."""

    def test_new_with_the_base_as_the_feature_branch(self):
        """Prevents a dry run of loop new passing a feature branch --write
        refuses as the base branch."""
        self.repo()
        self.refuses_like_write(NEW + ("--branch", "main"), "equals the base branch")

    def test_new_continuing_no_directory(self):
        """Prevents a dry run of loop new continuing a tracker directory that
        is not there."""
        self.repo()
        self.refuses_like_write(NEW + ("--leftover", "continue"), "There is no .scratch/demo/ to continue")

    def test_new_continuing_a_closed_loop(self):
        """Prevents a dry run of loop new continuing a finished loop."""
        self.plan()
        self.stage("loop closed")
        self.refuses_like_write(NEW + ("--leftover", "continue"), "a finished loop is not continued")

    def test_new_beside_a_root_loop_file(self):
        """Prevents a dry run of loop new passing beside a format-1 LOOP.md."""
        self.repo()
        self.box.write("LOOP.md", "# old\n")
        self.refuses_like_write(NEW, "LOOP.md at the repository root")

    def test_new_on_a_leftover_asks_what_the_write_refuses(self):
        """Prevents a dry run of loop new on a leftover directory printing
        other lines than the --write that cannot run without the user's
        answer: the dry run asks, the write refuses with the same lines."""
        self.plan()
        dry = self.box.run(*NEW, env=self.env())
        written = self.box.run(*(NEW + ("--write",)), env=self.env())
        self.assertEqual((dry.code, written.code), (0, 1), (dry, written))
        self.assertEqual(dry.lines, written.lines)
        self.assertIn("Question 1, leftover", dry.text)

    def test_set_a_fixed_line(self):
        """Prevents a dry run of loop set passing a line that never changes."""
        self.plan()
        self.refuses_like_write(("loop", "set", *SLUG, "--feature", "other"), "loop set never changes the Feature:")

    def test_set_nothing(self):
        """Prevents a dry run of loop set passing with nothing to set."""
        self.plan()
        self.refuses_like_write(("loop", "set", *SLUG), "Nothing to set")

    def test_set_on_no_loop(self):
        """Prevents a dry run of loop set passing on a slug with no loop."""
        self.plan()
        self.refuses_like_write(("loop", "set", "--slug", "other", "--minors", "fix"), "No loop other")

    def test_aside_with_no_directory(self):
        """Prevents a dry run of loop aside passing with nothing to move."""
        self.repo()
        self.refuses_like_write(("loop", "aside", *SLUG), "nothing to move aside")

    def test_close_and_reopen_on_no_loop(self):
        """Prevents a dry run of loop close or reopen passing on a slug with
        no loop."""
        self.plan()
        for command in ("close", "reopen"):
            self.refuses_like_write(("loop", command, "--slug", "other"), "No loop other")

    def test_fold_before_the_code_sign_off(self):
        """Prevents a dry run of loop fold passing before the code Sign-off."""
        self.coding()
        self.refuses_like_write(("loop", "fold", *SLUG, *CC), "The code Loop is not signed off")

    def test_fold_on_a_closed_loop(self):
        """Prevents a dry run of loop fold passing on a closed loop."""
        self.code_signed()
        self.stage("loop closed")
        self.refuses_like_write(("loop", "fold", *SLUG, *CC), "The loop demo is closed")


SHORT = re.compile(r"\b[0-9a-f]{7}\b")


class Plans(Staged):
    """Runs a write command as a dry run and with --write, and names what
    each changed."""

    def tree(self):
        """Every file of the project outside .git, and every git ref."""
        found = {}
        for top, dirs, files in os.walk(self.box.proj):
            dirs[:] = [name for name in dirs if name != ".git"]
            for name in files:
                path = os.path.join(top, name)
                with open(path, "rb") as handle:
                    found[os.path.relpath(path, self.box.proj).replace(os.sep, "/")] = handle.read()
        for line in self.git("for-each-ref", "--format=%(refname) %(objectname)").splitlines():
            ref, sha = line.split(" ")
            found["ref:" + ref] = sha
        return found

    def plan_and_write(self, *argv):
        """(dry run, --write run, the paths the write changed)."""
        before = self.tree()
        dry = self.run_ok(*argv)
        self.assertEqual(self.tree(), before, "the dry run wrote something")
        written = self.run_ok(*(argv + ("--write",)))
        after = self.tree()
        changed = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        return dry, written, changed

    def body(self, result):
        return result.lines[:-1]


class LoopPlans(Plans):
    """A loop write command's dry run writes nothing, and its lines name
    exactly the change its --write makes."""

    def test_set(self):
        """Prevents loop set's dry run naming other lines than --write sets."""
        self.plan()
        dry, written, changed = self.plan_and_write("loop", "set", *SLUG, "--minors", "leave", "--pr", "no")
        self.assertEqual(self.body(dry), ["Would set: Minors: leave", "Would set: PR: no"])
        self.assertEqual(self.body(written), ["Set: Minors: leave", "Set: PR: no"])
        self.assertEqual(changed, [".scratch/demo/loop.md"])
        for line in ("Minors: leave", "PR: no"):
            self.assertIn(line, self.read("loop.md").splitlines())

    def test_close(self):
        """Prevents loop close's dry run hiding a change --write makes."""
        self.plan()
        self.put(ARMED, "vdd codex-armed 1\nOrchestrator 0\n")
        dry, written, changed = self.plan_and_write("loop", "close", *SLUG)
        self.assertEqual(self.body(dry), ["Would mark the loop demo closed."])
        self.assertEqual(changed, [".scratch/demo/" + ARMED, ".scratch/demo/loop-state"])
        self.assertEqual(self.state().splitlines()[-1], "loop closed")
        self.assertEqual(self.body(written), ["Deleted the Codex armed file %s." % ARMED,
                                              "Closed: the loop demo. Its files stay in .scratch/demo/ as the record."])

    def test_reopen(self):
        """Prevents loop reopen's dry run hiding a change --write makes."""
        self.plan()
        self.stage("loop closed")
        dry, written, changed = self.plan_and_write("loop", "reopen", *SLUG)
        self.assertEqual(self.body(dry), ["Would mark the loop demo open."])
        self.assertEqual(self.body(written), ["Reopened: the loop demo is open again."])
        self.assertEqual(changed, [".scratch/demo/loop-state"])
        self.assertEqual(self.state().splitlines()[-1], "loop open")

    def test_aside(self):
        """Prevents loop aside's dry run naming another target, or hiding
        that it closes the loop, where --write moves and closes it."""
        self.plan()
        before = self.tree()
        dry, written, changed = self.plan_and_write("loop", "aside", *SLUG)
        self.assertEqual(self.body(dry), ["Would move .scratch/demo/ to .scratch/demo-2/, closing its open loop "
                                          "first."])
        moved = dict((path.replace(".scratch/demo/", ".scratch/demo-2/"), data) for path, data in before.items()
                     if path.startswith(".scratch/demo/"))
        self.assertEqual(changed, sorted(set(moved) | set(path for path in before if path.startswith(".scratch/"))))
        self.assertFalse(os.path.exists(self.box.path(".scratch", "demo")))
        state = self.box.read(".scratch/demo-2/loop-state")
        self.assertEqual(state, moved[".scratch/demo-2/loop-state"].decode() + "loop closed\n")
        self.assertEqual(self.body(written)[:2], ["Closed the loop demo.",
                                                  "Moved: .scratch/demo/ is now .scratch/demo-2/. Nothing was "
                                                  "deleted."])

    def test_new(self):
        """Prevents loop new's dry run naming another base, feature branch or
        Harness than the Loop file --write writes."""
        self.repo()
        dry, written, changed = self.plan_and_write(*NEW)
        self.assertEqual(self.body(dry), ["Slug: demo", "Base branch: main (from the checked-out branch).",
                                          "Feature branch: demo (proposed: the slug).", "Harness: Claude Code.",
                                          dry.lines[4]])
        self.assertEqual(changed, [".scratch/demo/loop-state", ".scratch/demo/loop.md"])
        lines = self.read("loop.md").splitlines()
        for line in ("Base branch: main", "Feature branch: demo", "Harness: Claude Code", "Minors: fix", "PR: no"):
            self.assertIn(line, lines)
            self.assertIn(line, written.lines)
        self.assertEqual(self.state().splitlines()[-1], "loop open")

    def test_fold(self):
        """Prevents loop fold's dry run naming other commits than --write
        folds the branch into."""
        self.code_signed()
        dry, written, changed = self.plan_and_write("loop", "fold", *SLUG, *CC)
        head, report = self.body(dry)[0], self.body(dry)[1:]
        self.assertEqual(head, "Would fold demo: 1 commits into 1.")
        self.assertEqual(self.body(written)[0], "Folded demo: 1 commits into 1.")
        self.assertEqual([SHORT.sub("<sha>", line) for line in self.body(written)[1:1 + len(report)]],
                         [SHORT.sub("<sha>", line) for line in report])
        self.assertEqual(changed, [".scratch/demo/RECAP.md", ".scratch/demo/loop-state", ".scratch/demo/recap.json"])
        self.assertIn("fold folded ", self.state())

    def test_fold_skipped(self):
        """Prevents loop fold's dry run giving another reason to skip than
        --write records, or moving the branch."""
        self.code_signed()
        self.commit("b.txt", "b\n", "feat: after the Sign-off")
        dry, written, changed = self.plan_and_write("loop", "fold", *SLUG, *CC)
        reason = self.body(dry)[0]
        self.assertTrue(reason.startswith("Would skip the fold: the branch moved after Sign-off"), dry)
        self.assertEqual(self.body(written)[0], "Not folded: %s." % reason[len("Would skip the fold: "):].split(
            ". demo would stay")[0])
        self.assertEqual(changed, [".scratch/demo/RECAP.md", ".scratch/demo/loop-state", ".scratch/demo/recap.json"])
        self.assertIn("fold skipped ", self.state())


class RoundPlans(Plans):
    """A Coder's or a reviewer's round command: its dry run writes nothing,
    and its lines name the change its --write makes."""

    def test_coder_start(self):
        """Prevents coder start's dry run naming another branch or frame than
        --write creates and writes."""
        self.signed()
        dry, written, changed = self.plan_and_write("coder", "start", *SLUG)
        self.assertEqual(self.body(dry), ["Would start code round 1 on demo and write the frame of "
                                          ".scratch/demo/FIXES.md."])
        self.assertEqual(self.body(written)[:2], ["Created the feature branch demo from main and switched to it.",
                                                  "Wrote the frame of .scratch/demo/FIXES.md."])
        self.assertEqual(changed, [".scratch/demo/FIXES.md", ".scratch/demo/coder-untracked-1",
                                   ".scratch/demo/loop-state", "ref:refs/heads/demo"])
        self.assertEqual(self.git("branch", "--show-current"), "demo")

    def test_coder_check(self):
        """Prevents coder check's dry run passing a round --write records
        differently, or hiding a file it writes."""
        self.coder_started()
        dry, written, changed = self.plan_and_write("coder", "check", *SLUG)
        self.assertEqual(self.body(dry), ["FIXES.md passes: round 1."])
        self.assertEqual(self.body(written)[0], "FIXES.md: round 1 checked and written.")
        self.assertIn("VDD Coder: FIXES.md written, round 1. Read it.", written.lines)
        self.assertEqual(changed, [".scratch/demo/FIXES.md", ".scratch/demo/RECAP.md", ".scratch/demo/loop-state",
                                   ".scratch/demo/recap.json"])
        self.assertIn("code 1 end ", self.state())

    def test_review_start(self):
        """Prevents review start's dry run naming another frame than --write
        writes."""
        self.plan()
        self.run_ok("doorbell", "ring", "--role", "Planner", *CC, *SLUG, "--write")
        dry, written, changed = self.plan_and_write("review", "start", "--role", "Plan-Reviewer", *SLUG)
        self.assertEqual(self.body(dry), ["Would write the frame of .scratch/demo/PLAN-REVIEW.md for round 1."])
        self.assertEqual(self.body(written)[0], "Wrote the frame of .scratch/demo/PLAN-REVIEW.md.")
        self.assertEqual(changed, [".scratch/demo/PLAN-REVIEW.md", ".scratch/demo/carried-plan.md",
                                   ".scratch/demo/loop-state"])

    def test_review_check(self):
        """Prevents review check's dry run giving another outcome than --write
        records, or hiding a file it writes."""
        self.plan_review_written()
        dry, written, changed = self.plan_and_write("review", "check", "--role", "Plan-Reviewer", *SLUG)
        self.assertEqual(self.body(dry), ["PLAN-REVIEW.md passes: round 1, 2 new findings, 0 closed.",
                                          "Open: 0 blocker, 1 major, 1 minor."])
        self.assertEqual(self.body(written)[:2], ["PLAN-REVIEW.md: round 1 checked and written.",
                                                  "Open: 0 blocker, 1 major, 1 minor."])
        self.assertEqual(changed, [".scratch/demo/PLAN-REVIEW.md", ".scratch/demo/RECAP.md",
                                   ".scratch/demo/loop-state", ".scratch/demo/recap.json"])
        self.assertIn("plan 1 reviewed open 1,2 ", self.state())

    def test_review_add(self):
        """Prevents review add's dry run naming other findings or files than
        --write adds and writes."""
        self.folded()
        self.box.write("findings.md", FINDINGS)
        dry, written, changed = self.plan_and_write("review", "add", *SLUG, "--from", "findings.md")
        self.assertEqual(self.body(dry)[:3], ["Would add 2 findings after round 1's Sign-off:",
                                              "### 1. major (open): docs/a.md:3", "### 2. minor (open): src/b.py:9"])
        self.assertEqual(self.body(dry)[-1], "Would rewrite .scratch/demo/CODEREVIEW.md, record the findings in "
                                             ".scratch/demo/loop-state and write .scratch/demo/RECAP.md.")
        self.assertEqual(self.body(written)[:2], ["Wrote .scratch/demo/CODEREVIEW.md.",
                                                  "Wrote .scratch/demo/RECAP.md."])
        self.assertEqual(changed, [".scratch/demo/CODEREVIEW.md", ".scratch/demo/RECAP.md",
                                   ".scratch/demo/loop-state", ".scratch/demo/recap.json"])
        self.assertIn("code 1 user open 1,2 ", self.state())


class LeftOut(Staged):
    def newer(self):
        self.box.write_loop("newer", branch="newer")
        self.box.write(".scratch/newer/loop-state", "vdd loop-state 3\nloop open\n")

    LINE = ("Left out the loop newer: .scratch/newer/loop-state has format version 3, which this copy of the VDD "
            "tool does not know.")

    def test_beside_a_current_loop(self):
        """Prevents a loop a newer VDD wrote vanishing from the slug-less
        lookup without a word, and blocking the user's own loop."""
        self.plan()
        self.newer()
        result = self.run_ok("loop", "show")
        self.assertEqual(result.lines[0], self.LINE)
        self.assertIn("Slug: demo", result.lines)

    def test_alone(self):
        """Prevents "No open loop" with no word of the loop it left out."""
        self.repo()
        self.newer()
        result = self.box.run("loop", "show", env=self.env())
        self.assertEqual(result.code, 1, result)
        self.assertEqual(result.lines[0], self.LINE)
        self.assertIn("No open loop under .scratch/", result.lines[1])
        self.assertTrue(result.last.startswith("Next: "), result)


class NoTraceback(Staged):
    def refused(self, argv, fragment):
        result = self.box.run(*argv, env=self.env())
        self.assertEqual(result.code, 1, result)
        self.assertIn(fragment, result.text)
        self.assertTrue(result.last.startswith("Next: "), result)
        self.assertNotIn("Traceback", result.text)
        return result

    def test_a_page_that_is_not_ascii_digits(self):
        """Prevents --page ² passing a digit check and crashing int()."""
        self.store()
        self.refused(("brainstorm", "start", "--page", "²"), "is not a number")

    def test_tokens_that_are_not_ascii_digits(self):
        """Prevents --tokens ² passing a digit check and crashing int()."""
        self.plan()
        self.stage("respawn Coder never", "orchestrator session 1", "spawn Coder 1 session 1")
        self.refused(("orchestrator", "tokens", "--role", "Coder", "--tokens", "²", *SLUG),
                     "--tokens takes a whole number")

    def test_an_internal_error_ends_in_a_next_line(self):
        """Prevents an unexpected exception ending the run in a traceback with
        no Next: line: the Role always learns what to do."""
        self.plan()
        self.put("loop.md", self.read("loop.md").replace("Format: 2", "Format: ²"))
        result = self.refused(("loop", "show", *SLUG), "The VDD tool hit an internal error: ValueError")
        self.assertNext(result, "internal error")


if __name__ == "__main__":
    unittest.main()
