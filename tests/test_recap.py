"""The record step every round-recording command runs, and the Recap rendered
from its records, driven through vdd.py: a command killed at each write
converges on its rerun, and RECAP.md reads as the records say."""

import json
import os
import shutil
import stat
import time
import unittest

from scenes import CC, FINDINGS, PLAN_REVIEW_1, SLUG, Staged

ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
PLAN_RESOLUTIONS = ("Resolution: the Spec names two decimals.", "Resolution: Ticket 02 names `summary`.")
CODE_RESOLUTION = "Resolution: a.txt holds b."


class RecapTest(Staged):
    # --- the commands under test, each staged just before its run ---

    def plan_check(self):
        """Plan round 2 filled in, both findings fixed."""
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
                   "The Spec does not say how amounts are written.\n\n" + PLAN_RESOLUTIONS[0]),
                  ("Ticket 02 leaves `summary` out.", "Ticket 02 leaves `summary` out.\n\n" + PLAN_RESOLUTIONS[1]))
        return ("review", "check", "--role", "Plan-Reviewer", *SLUG, "--write")

    def code_check(self):
        """Code round 2 filled in, finding 1 fixed, after a round 1 with a
        Not carried line."""
        self.plan_rounds()
        self.code_round_one()
        self.code_review(
            ("code-review: <ran | did not resolve, the Spec reviewed by hand>", "code-review: ran"),
            ("## New findings\n", "## New findings\n\n### 1. major (open): a.txt:1\n\nThe value is wrong.\n"),
            ("- <the problem, in one line>: <why not> -->",
             "- <the problem, in one line>: <why not> -->\n- the report's style nit on a.txt: not a defect"))
        self.answered([1], "a.txt", "b\n", "fix: the value")
        self.run_ok("review", "start", "--role", "Code-Reviewer", *SLUG, "--write")
        self.fill("CODEREVIEW.md",
                  ("code-review: <ran | did not resolve, the Spec reviewed by hand | not needed, <reason>>",
                   "code-review: ran"),
                  ("### 1. major (open): a.txt:1", "### 1. major (fixed): a.txt:1"),
                  ("Coder: fixed in round 2.", "Coder: fixed in round 2.\n\n" + CODE_RESOLUTION))
        return ("review", "check", "--role", "Code-Reviewer", *SLUG, "--write")

    def coder_check(self):
        self.coder_started()
        return ("coder", "check", *SLUG, "--write")

    def add(self):
        self.folded()
        self.box.write("findings.md", FINDINGS)
        return ("review", "add", *SLUG, "--from", "findings.md", "--write")

    def fold(self):
        """Code round 2 signed off with a fix the fold absorbs, so the fold
        moves the branch."""
        self.run_ok(*self.code_check())
        return ("loop", "fold", *SLUG, *CC, "--write")

    def fold_skipped(self):
        self.code_signed()
        self.git("branch", "--set-upstream-to=main", "demo")
        return ("loop", "fold", *SLUG, *CC, "--write")

    # --- obstacles ---

    def read_only(self, name):
        path = self.box.path(self.rel(name))
        os.chmod(path, stat.S_IREAD)
        return lambda: os.chmod(path, stat.S_IWRITE | stat.S_IREAD)

    def recap_folder(self):
        """A folder at RECAP.md, with recap.json present."""
        if not self.exists("recap.json"):
            self.put("recap.json", json.dumps({"format": 1, "records": []}))
        if self.exists("RECAP.md"):
            os.remove(self.box.path(self.rel("RECAP.md")))
        os.makedirs(self.box.path(self.rel("RECAP.md")))
        return lambda: shutil.rmtree(self.box.path(self.rel("RECAP.md")))

    def killed(self, stage, obstacle):
        """Run the staged command against the obstacle, remove it, run again;
        the rerun's result."""
        argv = stage()
        undo = obstacle()
        failed = self.box.run(*argv, env=self.env())
        self.assertNotEqual(failed.code, 0, failed)
        self.assertTrue(failed.last.startswith("Next: "), failed)
        self.assertNotIn("Traceback", failed.text)
        undo()
        return self.run_ok(*argv)

    def recap(self):
        return self.read("RECAP.md")

    def lines(self, prefix):
        return [line for line in self.state().split("\n") if line.startswith(prefix)]


def check_plan(t):
    for resolution in PLAN_RESOLUTIONS:
        t.assertEqual(t.recap().count(resolution), 1, t.recap())
    t.assertEqual(len(t.lines("plan 2 reviewed ")), 1, t.state())
    t.assertNotIn("(fixed)", t.read("PLAN-REVIEW.md"))


def check_code(t):
    t.assertEqual(t.recap().count(CODE_RESOLUTION), 1, t.recap())
    t.assertEqual(t.recap().count("- Code round 1: the report's style nit"), 1, t.recap())
    t.assertEqual(len(t.lines("code 2 reviewed ")), 1, t.state())
    t.assertNotIn("(fixed)", t.read("CODEREVIEW.md"))


def check_coder(t):
    t.assertEqual(t.recap().count("### Ticket 01: 01-one.md"), 1, t.recap())
    t.assertEqual(t.recap().count("### Ticket 02: 02-two.md"), 1, t.recap())
    t.assertEqual(len(t.lines("code 1 end ")), 1, t.state())


def check_add(t):
    review = t.read("CODEREVIEW.md")
    t.assertEqual(review.count("### 1. major (open): docs/a.md:3"), 1, review)
    t.assertEqual(review.count("### 2. minor (open): src/b.py:9"), 1, review)
    t.assertNotIn("### 3.", review)
    t.assertEqual(t.lines("code 1 user "), ["code 1 user open 1,2 counts 0 1 1 next 3 new 2"])
    t.assertEqual(t.recap().count("| code | 1, user |"), 1, t.recap())


def check_fold(t):
    t.assertEqual(len(t.lines("fold folded ")), 1, t.state())
    t.assertEqual(t.recap().count("Folded demo:"), 1, t.recap())
    tip, signed = t.lines("fold folded ")[0].split()[2::2]
    t.assertNotEqual(tip, signed)
    t.assertEqual(t.sha("demo"), tip)


def check_skipped(t):
    t.assertEqual(len(t.lines("fold skipped ")), 1, t.state())
    t.assertEqual(t.recap().count("Not folded: demo stays"), 1, t.recap())


# (name, the staged command, the check after the rerun)
KILLED = [
    ("review_check_plan", RecapTest.plan_check, check_plan),
    ("review_check_code", RecapTest.code_check, check_code),
    ("coder_check", RecapTest.coder_check, check_coder),
    ("review_add", RecapTest.add, check_add),
    ("fold", RecapTest.fold, check_fold),
    ("fold_skipped", RecapTest.fold_skipped, check_skipped),
]


class KillAtEachWrite(RecapTest):
    """A command killed at each write after its records converges on the
    rerun with the obstacle removed."""


def make_killed(stage, check, which):
    def test(self):
        if which == "state" and ROOT:
            self.skipTest("root writes a read-only file")
        obstacle = (lambda: self.read_only("loop-state")) if which == "state" else self.recap_folder
        self.killed(lambda: stage(self), obstacle)
        check(self)

    test.__doc__ = ("Prevents a failure between two writes losing a Resolution, putting a Ticket in the Recap "
                    "twice, adding the user's findings twice under new numbers, or leaving a moved branch with no "
                    "fold line or Commits.")
    return test


for _name, _stage, _check in KILLED:
    for _which in ("state", "recap"):
        setattr(KillAtEachWrite, "test_%s_%s" % (_name, _which), make_killed(_stage, _check, _which))


class FoldStoppedAfterItsRef(RecapTest):
    def test_the_failed_run_says_the_ref_moved_and_the_dry_rerun_previews_the_record(self):
        """Prevents a fold killed after its update-ref hiding that the branch
        was rewritten, and a dry rerun then claiming the fold would skip
        where --write records it."""
        if ROOT:
            self.skipTest("root writes a read-only file")
        argv = self.fold()
        signed = self.sha()
        undo = self.read_only("loop-state")
        failed = self.box.run(*argv, env=self.env())
        undo()
        self.assertNotEqual(failed.code, 0, failed)
        tip = self.sha("demo")
        self.assertNotEqual(tip, signed)
        self.assertEqual(failed.lines[0], "Moved demo from the signed commit %s to the folded tip %s."
                         % (signed[:7], tip[:7]), failed)
        self.assertTrue(failed.last.startswith("Next: "), failed)
        dry = self.run_ok(*argv[:-1])
        self.assertEqual(dry.lines[0], "Would record the fold of demo: it is at the folded tip %s, which an earlier "
                         "fold moved it to before it stopped." % tip[:7], dry)
        self.assertEqual(self.lines("fold "), [])
        self.run_ok(*argv)
        check_fold(self)

    def moved_ref(self):
        """Code round 1 signed off, its fold record written and the branch
        moved to the record's tip, with no fold line: (signed, tip)."""
        self.code_signed()
        signed = self.sha()
        tip = self.commit("b.txt", "b\n", "feat: b")
        self.put("recap.json", json.dumps({"format": 1, "records": [{
            "key": "fold " + signed, "section": "Commits", "lines": ["Folded demo: 2 commits into 1.", ""],
            "data": {"tip": tip, "before": 2, "after": 1, "report": []}}]}))
        self.box.write("findings.md", FINDINGS)
        return signed, tip

    def add_refused_moved(self):
        names = ("CODEREVIEW.md", "loop-state", "recap.json")
        before = dict((name, self.read(name)) for name in names)
        result = self.box.run("review", "add", *SLUG, "--from", "findings.md", "--write", env=self.env())
        self.assertEqual(result.code, 1, result)
        self.assertEqual(result.lines[0], "Code round 1 was folded but its fold is not recorded. Nothing was "
                         "written.", result)
        self.assertEqual(dict((name, self.read(name)) for name in names), before)
        self.assertFalse(self.exists("RECAP.md"))
        return result

    def test_review_add_waits_for_the_fold_line(self):
        """Prevents review add recording the user's findings while a fold
        moved the branch and stopped before its state line: the next round
        and fold would then drop the first fold's Commits from the Recap."""
        signed, tip = self.moved_ref()
        result = self.add_refused_moved()
        self.assertNext(result, "loop fold --slug demo --harness claude-code --write, then this command again")
        self.run_ok("loop", "fold", *SLUG, *CC, "--write")
        self.assertEqual(self.lines("fold "), ["fold folded %s signed %s" % (tip, signed)])
        self.run_ok("review", "add", *SLUG, "--from", "findings.md", "--write")
        self.assertEqual(self.recap().count("Folded demo:"), 1, self.recap())

    def test_review_add_on_a_closed_loop_names_the_reopen_first(self):
        """Prevents the moved-ref refusal on a closed loop naming loop fold
        alone, which refuses a closed loop and leaves the user stuck."""
        self.moved_ref()
        self.stage("loop closed")
        result = self.add_refused_moved()
        self.assertNext(result, "loop reopen --slug demo --write, then ", "loop fold --slug demo --harness "
                        "claude-code --write, then this command again")


class StepFive(RecapTest):
    """Prevents a Working file never rewritten after its round counted: the
    rerun is already recorded and leaves the file as the first run would
    have."""

    def lost(self, stage, name):
        argv = stage(self)
        before = self.read(name)
        self.run_ok(*argv)
        after = self.read(name)
        self.assertNotEqual(before, after)
        self.put(name, before)
        again = self.run_ok(*argv)
        self.assertIn("already recorded", again.text)
        self.assertEqual(self.read(name), after)
        third = self.run_ok(*argv)
        self.assertIn("already recorded. Nothing was written.", third.text)

    def test_review_check_plan(self):
        self.lost(RecapTest.plan_check, "PLAN-REVIEW.md")

    def test_review_check_code(self):
        self.lost(RecapTest.code_check, "CODEREVIEW.md")

    def test_coder_check(self):
        self.lost(RecapTest.coder_check, "FIXES.md")


class AddAfterTheCommitPoint(RecapTest):
    def test_the_rerun_adds_nothing_and_a_later_add_joins(self):
        """Prevents the rerun of an add whose Recap failed adding the user's
        findings a second time under new numbers."""
        argv = self.add()
        undo = self.recap_folder()
        failed = self.box.run(*argv, env=self.env())
        self.assertNotEqual(failed.code, 0, failed)
        self.assertIn("Recorded in .scratch/demo/loop-state; the Recap could not be written.", failed.lines)
        undo()
        again = self.run_ok(*argv)
        self.assertIn("already added", again.text)
        self.assertEqual(len(self.lines("code 1 user ")), 1, self.state())
        self.assertIn("| code | 1, user | 2 |", self.recap())
        self.box.write("more.md", "### blocker: src/c.py:1\n\nIt crashes.\n")
        self.run_ok("review", "add", *SLUG, "--from", "more.md", "--write")
        self.assertEqual(self.lines("code 1 user ")[-1], "code 1 user open 1,2,3 counts 1 1 1 next 4 new 3")
        self.assertIn("### 3. blocker (open): src/c.py:1", self.read("CODEREVIEW.md"))


class FoldRef(RecapTest):
    def test_a_held_ref_lock_records_one_skip(self):
        """Prevents a fold whose ref move failed showing both its Commits and
        its Not folded line."""
        argv = self.fold()
        signed = self.sha()
        lock = self.box.path(".git", "refs", "heads", "demo.lock")
        with open(lock, "w") as handle:
            handle.write("")
        result = self.run_ok(*argv)
        self.assertIn("Not folded:", result.text)
        self.assertEqual(len(self.lines("fold skipped %s " % signed)), 1, self.state())
        self.assertEqual(self.lines("fold folded "), [])
        self.assertIn("Not folded: demo stays at the signed commit", self.recap())
        self.assertNotIn("Folded demo:", self.recap())
        self.assertEqual(self.sha("demo"), signed)

    @unittest.skipIf(os.name == "nt", "a git wrapper on PATH is a POSIX script")
    def test_a_refused_ref_move_leaves_no_commits_in_a_later_recap(self):
        """Prevents a fold whose update-ref a sandbox refused showing its
        Commits in every later Recap, for a fold that never happened."""
        argv = self.fold()
        signed = self.sha()
        real = shutil.which("git")
        self.box.stub("git", 'if [ "$1" = update-ref ]; then echo "fatal: Operation not permitted" >&2; exit 128; '
                             "fi\nexec '%s' \"$@\"\n" % real)
        refused = self.box.run(*argv, env=self.env({"PATH": self.box.bin + os.pathsep + os.environ.get("PATH", "")}))
        self.assertNotEqual(refused.code, 0, refused)
        self.assertIn("Nothing was folded or written", refused.text)
        self.assertIn("fold %s" % signed, self.read("recap.json"))
        os.remove(os.path.join(self.box.bin, "git"))
        self.run_ok("review", "check", "--role", "Code-Reviewer", *SLUG, "--write")
        self.assertEqual(self.lines("fold "), [])
        self.assertNotIn("Folded demo:", self.recap())
        self.assertEqual(self.sha("demo"), signed)


class Seed(RecapTest):
    def test_a_recap_from_before_the_records_is_kept_whole(self):
        """Prevents the first round recorded after the upgrade dropping what an
        earlier version's RECAP.md held, or adding its own section twice."""
        self.plan_rounds()
        self.code_round_one()
        os.remove(self.box.path(self.rel("recap.json")))
        earlier = self.recap()
        self.run_ok("review", "start", "--role", "Code-Reviewer", *SLUG, "--write")
        self.fill("CODEREVIEW.md",
                  ("code-review: <ran | did not resolve, the Spec reviewed by hand>", "code-review: ran"),
                  ("- <the problem, in one line>: <why not> -->",
                   "- <the problem, in one line>: <why not> -->\n- the report's style nit on a.txt: not a defect"))
        self.run_ok("review", "check", "--role", "Code-Reviewer", *SLUG, "--write")
        recap = self.recap()
        for section in ("## Tickets", "## Plan findings"):
            start = earlier.index(section)
            end = earlier.index("\n## ", start + 1)
            self.assertIn(earlier[start:end], recap)
        self.assertEqual(recap.count("- Code round 1: the report's style nit on a.txt: not a defect"), 1, recap)
        again = self.run_ok("review", "check", "--role", "Code-Reviewer", *SLUG, "--write")
        self.assertIn("already recorded", again.text)
        self.assertEqual(self.recap(), recap)

    def test_a_reopen_and_a_second_sign_off_show_both_folds(self):
        """Prevents the second fold's Commits replacing the first's."""
        self.whole_loop()
        self.assertEqual(self.recap().count("Folded demo:"), 2, self.recap())
        self.assertEqual(len(self.lines("fold folded ")), 2, self.state())


class Unreadable(RecapTest):
    def refused_with(self, text, fragment):
        argv = self.coder_check()
        self.put("recap.json", text)
        before = self.state()
        result = self.box.run(*argv, env=self.env())
        self.assertNotEqual(result.code, 0, result)
        self.assertIn(".scratch/demo/recap.json", result.lines[0])
        self.assertIn(fragment, result.lines[0])
        self.assertTrue(result.last.startswith("Next: "), result)
        self.assertEqual(self.read("recap.json"), text)
        self.assertEqual(self.state(), before)

    def test_not_json(self):
        """Prevents a damaged records file being overwritten, which would
        lose every finding text the Recap held."""
        self.refused_with("not json", "is not a Recap records file this tool wrote")

    def test_a_newer_format(self):
        """Prevents an older tool overwriting records a newer one wrote."""
        self.refused_with(json.dumps({"format": 2, "records": []}), "format version 2")

    def test_review_add_leaves_the_review_file_alone(self):
        """Prevents review add replacing the signed-off CODEREVIEW.md with the
        user's findings and then refusing a recap.json it cannot read."""
        argv = self.add()
        self.put("recap.json", json.dumps({"format": 2, "records": []}))
        names = ("CODEREVIEW.md", "loop-state", "recap.json")
        before = dict((name, self.read(name)) for name in names)
        result = self.box.run(*argv, env=self.env())
        self.assertEqual(result.code, 1, result)
        self.assertIn("format version 2", result.lines[0])
        self.assertTrue(result.last.startswith("Next: "), result)
        self.assertEqual(dict((name, self.read(name)) for name in names), before)


class GitTimeout(RecapTest):
    @unittest.skipIf(os.name == "nt", "a sleeping gpg.program is a POSIX script")
    def test_a_signing_call_that_hangs_skips_the_fold(self):
        """Prevents a fold waiting for ever on a signing call, as on a
        pinentry dialog a hidden Session never sees: the call ends after the
        timeout, and the fold skips naming the call and the seconds."""
        argv = self.fold()
        signed = self.sha()
        gpg = self.box.stub("gpg-sleeps", "sleep 30\n")
        self.git("config", "commit.gpgSign", "true")
        self.git("config", "gpg.program", gpg)
        started = time.monotonic()
        result = self.box.run(*argv, env=self.env({"VDD_GIT_TIMEOUT_SECONDS": "2"}))
        self.assertLess(time.monotonic() - started, 25, result)
        self.assertEqual(result.code, 0, result)
        skip = [line for line in result.lines if line.startswith("Not folded: ")]
        self.assertEqual(len(skip), 1, result)
        self.assertEqual(skip[0], "Not folded: signing a folded commit failed: git commit-tree -S timed out after 2 "
                                  "seconds.")
        self.assertEqual(self.sha("demo"), signed)

    @unittest.skipIf(os.name == "nt", "a git wrapper on PATH is a POSIX script")
    def test_a_fold_call_that_hangs_is_named_once(self):
        """Prevents the Skip reason naming a timed-out call twice, once
        before its error line and once in it."""
        argv = self.fold()
        signed = self.sha()
        real = shutil.which("git")
        self.box.stub("git", 'if [ "$1" = commit-tree ]; then exec sleep 30; fi\nexec \'%s\' "$@"\n' % real)
        result = self.box.run(*argv, env=self.env({"PATH": self.box.bin + os.pathsep + os.environ.get("PATH", ""),
                                                   "VDD_GIT_TIMEOUT_SECONDS": "1"}))
        self.assertEqual(result.code, 0, result)
        skip = [line for line in result.lines if line.startswith("Not folded: ")]
        self.assertEqual(len(skip), 1, result)
        self.assertRegex(skip[0], r"^Not folded: a git error: git commit-tree [0-9a-f]+ timed out after 1 seconds\.$")
        self.assertEqual(self.sha("demo"), signed)


if __name__ == "__main__":
    unittest.main()
