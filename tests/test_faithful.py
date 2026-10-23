"""Dry runs that refuse where --write refuses, a loop a newer VDD wrote left
out of the slug-less lookup by name, and no run without a Next: line,
driven through vdd.py."""

import json
import os
import shutil
import unittest

from scenes import CC, FINDINGS, P1, P2, PLAN_OPEN_1, PLAN_REVIEW_1, SLUG, Staged

WINDOWS = os.name == "nt"
BROKEN = "{broken"
UNREADABLE = ".scratch/demo/recap.json is not a Recap records file this tool wrote"


class DryRuns(Staged):
    def refuses_like_write(self, argv, fragment, extra=None):
        dry = self.box.run(*argv, env=self.env(extra))
        written = self.box.run(*(argv + ("--write",)), env=self.env(extra))
        for result in (dry, written):
            self.assertEqual(result.code, 1, result)
            self.assertIn(fragment, result.text)
            self.assertTrue(result.last.startswith("Next: "), result)
        self.assertEqual(dry.lines, written.lines)

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
