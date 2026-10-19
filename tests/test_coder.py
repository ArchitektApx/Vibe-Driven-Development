"""The coder command group, driven from outside: the Coder on the tool."""

import os
import subprocess
import unittest

from vddtest import ToolTest

SIGNED = "plan 1 reviewed signed-off - counts 0 0 0 next 1 new 0 closed 0 checks writing-for-agents ran"

CODEREVIEW = """# Code review, round 1

Open: 0 blocker, 1 major, 2 minor.

## Checks

code-review: ran
writing-for-agents: no Agent document in this round's diff

## New findings

### 1. major (open): src/a.py:3

Wrong.

### 2. minor (open): src/b.py:9

Meh.

### 3. minor (open): README.md:40

Missing.

## Not carried
"""


def filled_round_one(text):
    return text.replace("Files:\nChange:\nVerified:", "Files: `a.txt`\nChange: wrote a.\nVerified: the test passed.")


class CoderTest(ToolTest):
    def setUp(self):
        ToolTest.setUp(self)
        self.box.init_git("main")
        self.box.write("a.txt", "a\n")
        self.box.write(".gitignore", ".scratch/\n")
        self.box.git("add", "a.txt", ".gitignore")
        self.box.git("commit", "-q", "-m", "base")
        self.box.write_loop("demo", extra=(SIGNED,))
        self.box.write(os.path.join(".scratch", "demo", "spec.md"), "# Spec\n")
        self.box.write(os.path.join(".scratch", "demo", "issues", "01-one.md"), "# 01\n")
        self.box.write(os.path.join(".scratch", "demo", "issues", "02-two.md"), "# 02\n")

    def coder(self, sub, write=True):
        return self.box.run("coder", sub, "--slug", "demo", *(["--write"] if write else []))

    def rel(self, name):
        return os.path.join(".scratch", "demo", name)

    def read(self, name):
        return self.box.read(self.rel(name))

    def exists(self, name):
        return os.path.exists(self.box.path(".scratch", "demo", name))

    def put(self, name, text):
        self.box.write(self.rel(name), text)

    def out(self, *argv):
        proc = subprocess.run(["git"] + list(argv), cwd=self.box.proj, stdout=subprocess.PIPE, check=True)
        return proc.stdout.decode().strip()

    def sha(self, ref="HEAD"):
        return self.out("rev-parse", ref)

    def branch(self):
        return self.out("branch", "--show-current")

    def commit(self, name, text, message):
        self.box.write(name, text)
        self.box.git("add", name)
        self.box.git("commit", "-q", "-m", message)

    def state(self):
        return self.read("loop-state")

    def stage_round_two(self):
        """Round 1 started, ended and reviewed with findings 1 to 3 open."""
        self.box.git("checkout", "-q", "-b", "demo")
        start = self.sha()
        self.commit("a.txt", "a1\n", "feat: one")
        end = self.sha()
        with open(self.box.path(".scratch", "demo", "loop-state"), "a") as handle:
            handle.write("code 1 start %s\ncode 1 end %s\n" % (start, end))
            handle.write("code 1 reviewed open 1,2,3 counts 0 1 2 next 4 new 3 closed 0 checks code-review ran\n")
        self.put("CODEREVIEW.md", CODEREVIEW)
        self.put("FIXES.md", "# Fixes, round 1\n\n## Ticket 01: 01-one.md\n\nFiles: x\nChange: y\nVerified: z\n")


class HelpTest(CoderTest):
    def test_help_teaches_start_and_check(self):
        result = self.box.run("coder", "--help")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("coder start", result.text)
        self.assertIn("coder check", result.text)


class StartTest(CoderTest):
    def test_the_plan_loop_not_signed_off_refuses_and_changes_nothing(self):
        """Replaces the Coder's Precondition (1e59e46): PLAN-REVIEW.md had to
        start SIGNED OFF, since an unreviewed Spec is not a contract."""
        self.box.write_loop("demo", extra=("plan 1 reviewed open 1 counts 0 1 0",))
        before = self.state()
        result = self.coder("start")
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("The plan Loop is not finished", result.text)
        self.assertEqual(self.branch(), "main")
        self.assertNotIn("demo", self.out("branch", "--list"))
        self.assertFalse(self.exists("FIXES.md"))
        self.assertEqual(self.state(), before)

    def test_on_the_base_with_no_feature_branch_it_creates_it(self):
        main = self.sha()
        result = self.coder("start")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertEqual(self.branch(), "demo")
        self.assertEqual(self.sha("demo"), main)
        self.assertIn("Round 1 starts at %s." % main, result.lines)
        self.assertIn("code 1 start %s" % main, self.state())

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "a read-only .git refuses only a non-root user on macOS and Linux")
    def test_a_sandbox_refusing_git_asks_for_a_rerun_outside_it(self):
        """Codex keeps .git read-only in its sandbox. The switch failed inside
        the tool, whose Next: said stop, so the Coder never asked to rerun it
        outside the sandbox as it would for its own git command."""
        dirs = [self.box.path(".git")]
        for directory, names, _ in os.walk(self.box.path(".git")):
            dirs += [os.path.join(directory, name) for name in names]
        for path in dirs:
            os.chmod(path, 0o555)
        self.addCleanup(lambda: [os.chmod(path, 0o755) for path in dirs])
        result = self.coder("start")
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertNext(result, "Rerun", "coder start --slug demo --write", "outside the sandbox")
        self.assertEqual(self.branch(), "main")

    def test_any_other_git_failure_still_stops(self):
        """Only a permission refusal asks for the rerun; a branch name git
        rejects goes to the user."""
        self.box.write_loop("demo", branch="bad..name", extra=(SIGNED,))
        result = self.coder("start")
        self.assertNotEqual(result.code, 0, result)
        self.assertNext(result, "Tell the user git could not check out the feature branch bad..name, and stop.")

    def test_on_the_base_with_the_feature_branch_it_switches(self):
        self.box.git("branch", "demo")
        result = self.coder("start")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(self.branch(), "demo")
        self.assertIn("Switched to the feature branch demo.", result.lines)

    def test_on_the_feature_branch_it_stays(self):
        self.box.git("checkout", "-q", "-b", "demo")
        result = self.coder("start")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(self.branch(), "demo")
        self.assertIn("On the feature branch demo.", result.lines)

    def test_on_any_other_branch_it_refuses_with_the_question(self):
        """The Spawn prompt's QUESTION case 1: a Coder on neither branch asks
        the user; the tool tells it to."""
        self.box.git("checkout", "-q", "-b", "other")
        before = self.state()
        result = self.coder("start")
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertNext(result, "Return QUESTION:", "main", "demo")
        self.assertEqual(self.branch(), "other")
        self.assertFalse(self.exists("FIXES.md"))
        self.assertEqual(self.state(), before)

    def test_round_one_frame(self):
        result = self.coder("start")
        text = self.read("FIXES.md")
        self.assertTrue(text.startswith("# Fixes, round 1\n\n<!-- VDD: "), text)
        self.assertIn("\n## Ticket 01: 01-one.md\n\nFiles:\nChange:\nVerified:\n", text)
        self.assertIn("\n## Ticket 02: 02-two.md\n\nFiles:\nChange:\nVerified:\n", text)
        self.assertIn("Read: .scratch/demo/spec.md, .scratch/demo/issues/", result.lines)
        self.assertNext(result, "coder check --slug demo --write")

    def test_a_second_start_writes_nothing_and_prints_the_recorded_start(self):
        """A respawned Coder's first call is start again; it keeps the round's
        partial FIXES.md and its recorded start, so the fold's reset still
        collapses the whole round."""
        self.stage_round_two()
        first = self.coder("start")
        self.assertEqual(first.code, 0, first)
        start = self.sha()
        self.assertIn("Round 2 starts at %s." % start, first.lines)
        text = self.read("FIXES.md").replace("Answer: <fixed | pushback>", "Answer: fixed", 1)
        self.put("FIXES.md", text)
        self.commit("a.txt", "a2\n", "fixup! %s" % start)
        before = (self.read("FIXES.md"), self.state())
        second = self.coder("start")
        self.assertEqual(second.code, 0, second)
        self.assertEqual((self.read("FIXES.md"), self.state()), before)
        self.assertIn("Round 2 starts at %s." % start, second.lines)
        self.assertTrue(any("Nothing was written" in line for line in second.lines), second)
        self.assertEqual(self.state().count("code 2 start"), 1)

    def test_no_start_prints_the_base_branch(self):
        """The Base branch: line's only reader was the fold commands in the
        Coder's skill, which the tool's fold after Sign-off replaced."""
        cases = {
            "create": lambda: None,
            "switch": lambda: self.box.git("branch", "demo"),
            "stay": lambda: self.box.git("checkout", "-q", "-b", "demo"),
        }
        for name, stage in cases.items():
            with self.subTest(case=name):
                self.setUp()
                stage()
                first = self.coder("start")
                self.assertEqual(first.code, 0, first)
                self.assertFalse([line for line in first.lines if line.startswith("Base branch:")], first)
                again = self.coder("start")
                self.assertEqual(again.code, 0, again)
                self.assertFalse([line for line in again.lines if line.startswith("Base branch:")], again)

    def test_a_repeated_start_switches_only_with_write(self):
        """A repeated start without --write checked out the feature branch
        while saying nothing was written, and with --write it dropped the
        switch line."""
        self.assertEqual(self.coder("start").code, 0)
        self.box.git("checkout", "-q", "main")
        dry = self.coder("start", write=False)
        self.assertEqual(dry.code, 0, dry)
        self.assertEqual(self.branch(), "main")
        self.assertIn("Would switch to the feature branch demo.", dry.lines)
        self.assertNext(dry, "Run the same command with --write.")
        done = self.coder("start")
        self.assertEqual(done.code, 0, done)
        self.assertEqual(self.branch(), "demo")
        self.assertIn("Switched to the feature branch demo.", done.lines)

    def test_a_later_round_frame_names_each_open_finding(self):
        self.stage_round_two()
        result = self.coder("start")
        self.assertEqual(result.code, 0, result)
        text = self.read("FIXES.md")
        self.assertTrue(text.startswith("# Fixes, round 2\n"), text)
        for heading in ("## Finding 1. major: src/a.py:3", "## Finding 2. minor: src/b.py:9",
                        "## Finding 3. minor: README.md:40"):
            self.assertIn(heading + "\n\nAnswer: <fixed | pushback>\nWhy:\n", text + "\n")
        self.assertNotIn("Ticket 01", text)
        self.assertIn("Read: .scratch/demo/CODEREVIEW.md, .scratch/demo/spec.md, .scratch/demo/issues/", result.lines)

    def test_a_round_ended_and_not_reviewed_has_no_next_round(self):
        """A round that ended and has no recorded review has no next round:
        start refuses and says the Coder waits for the review."""
        self.stage_round_two()
        lines = [l for l in self.state().split("\n") if "reviewed open 1,2,3" not in l]
        self.put("loop-state", "\n".join(lines))
        result = self.coder("start")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("waits for its review", result.text)


class CheckTest(CoderTest):
    def started(self):
        result = self.coder("start")
        self.assertEqual(result.code, 0, result)
        return result

    def refused(self, *fragments):
        before = (self.read("FIXES.md"), self.state(), self.exists("RECAP.md"))
        result = self.coder("check")
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        for fragment in fragments:
            self.assertIn(fragment, result.text)
        self.assertEqual((self.read("FIXES.md"), self.state(), self.exists("RECAP.md")), before)
        self.assertNext(result, "coder check --slug demo --write", "again")
        return result

    def test_an_empty_verified_is_refused(self):
        """Verified is the result of each check, never its output."""
        self.started()
        text = filled_round_one(self.read("FIXES.md")).replace("Verified: the test passed.", "Verified:", 1)
        self.put("FIXES.md", text)
        self.refused("Ticket 01's Verified: is empty", "the result of each check you ran, not its output",
                     "FIXES.md line ")

    def test_a_missing_ticket_entry_is_refused(self):
        """A FIXES.md that skips a Ticket is refused, so no Ticket goes
        unreported."""
        self.started()
        text = filled_round_one(self.read("FIXES.md"))
        text = text.split("## Ticket 02")[0]
        self.put("FIXES.md", text)
        self.refused("Ticket 02's entry \"## Ticket 02: 02-two.md\" is missing")

    def test_an_unclosed_fence_is_refused_at_its_line(self):
        """A fence left open turned every later line into prose, so the entries
        after it went unread."""
        self.started()
        text = filled_round_one(self.read("FIXES.md")).replace("Change: wrote a.", "Change: wrote a.\n\n~~~\nx", 1)
        self.put("FIXES.md", text)
        number = text.split("\n").index("~~~") + 1
        self.refused("FIXES.md line %d: the code fence that opens here is never closed" % number,
                     "Close it with a line holding ~~~.")

    def test_a_modified_tracked_file_is_refused_by_name(self):
        """Replaces the Coder skill's "Uncommitted work at hand-off time is a
        defect" (1e59e46): both reviews diff committed work only."""
        self.started()
        self.put("FIXES.md", filled_round_one(self.read("FIXES.md")))
        self.box.write("a.txt", "changed\n")
        self.refused("uncommitted changes to tracked files: a.txt")

    def test_a_passing_round_one(self):
        self.started()
        self.commit("a.txt", "one\n", "feat: one")
        self.commit("b.txt", "two\n", "feat: two")
        self.put("FIXES.md", filled_round_one(self.read("FIXES.md")))
        result = self.coder("check")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        tip = self.sha()
        self.assertIn("code 1 end %s" % tip, self.state())
        self.assertIn("Round 1 ends at %s." % tip, result.lines)
        self.assertIn("VDD Coder: FIXES.md written, round 1. Read it.", result.lines)
        self.assertEqual(result.last, "Next: End your turn with the Doorbell line above as your whole reply.")
        self.assertNotIn("<!--", self.read("FIXES.md"))
        tickets = self.read("RECAP.md").split("## Tickets")[1].split("## Plan findings")[0]
        self.assertIn("### Ticket 01: 01-one.md", tickets)
        self.assertIn("### Ticket 02: 02-two.md", tickets)
        self.assertIn("Verified: the test passed.", tickets)

    def test_the_recap_header_names_a_coder_round_not_reviewed(self):
        """The header counted reviews only, so after the Coder's round 1 it
        still read "Code Loop: not started"."""
        self.started()
        self.commit("a.txt", "one\n", "feat: one")
        self.put("FIXES.md", filled_round_one(self.read("FIXES.md")))
        result = self.coder("check")
        self.assertEqual(result.code, 0, result)
        self.assertIn("Code Loop: round 1, not reviewed yet.", self.read("RECAP.md"))
        self.assertNotIn("Code Loop: not started.", self.read("RECAP.md"))

    def later(self):
        self.stage_round_two()
        result = self.coder("start")
        self.assertEqual(result.code, 0, result)

    def answer(self, one, two, three):
        text = self.read("FIXES.md")
        for answer in (one, two, three):
            text = text.replace("Answer: <fixed | pushback>\nWhy:", answer, 1)
        self.put("FIXES.md", text)

    def test_a_later_round_refuses_a_bad_answer_and_a_pushback_without_why(self):
        """The answer is fixed or pushback, and a pushback needs its reason."""
        self.later()
        self.answer("Answer: done\nWhy:", "Answer: pushback\nWhy:", "Answer: fixed\nWhy:")
        self.refused("finding 1: \"Answer: done\": the answer is fixed or pushback",
                     "finding 2 answers pushback with no Why:")

    def test_a_missing_finding_entry_prints_its_whole_heading(self):
        """The refusal printed "## Finding 2. ...", not the heading the tool
        wrote."""
        self.later()
        self.answer("Answer: fixed\nWhy:", "Answer: fixed\nWhy:", "Answer: fixed\nWhy:")
        text = self.read("FIXES.md")
        self.put("FIXES.md", text.replace("## Finding 2. minor: src/b.py:9\n\nAnswer: fixed\nWhy:\n", ""))
        self.refused('finding 2\'s entry is missing. Put back "## Finding 2. minor: src/b.py:9" as the tool wrote it')

    def test_a_later_round_accepts_fixed_with_no_why(self):
        self.later()
        self.answer("Answer: fixed\nWhy:", "Answer: fixed", "Answer: pushback\nWhy: the Spec says so,\nin its words.")
        result = self.coder("check")
        self.assertEqual(result.code, 0, result)
        self.assertIn("VDD Coder: FIXES.md written, round 2. Read it.", result.lines)
        self.assertNotIn("Ticket", self.read("FIXES.md"))

    def test_an_amended_earlier_round_is_refused_until_it_is_a_new_commit(self):
        """Ticket 71 (case c10): a round that amends, rebases or resets an
        earlier round's commit loses the recorded end the fold and the next
        review read. check refuses it, writes no round end, and passes once
        the change is a new commit."""
        self.later()
        start = self.sha()
        self.box.write("a.txt", "fix\n")
        self.box.git("commit", "-q", "--amend", "--no-edit", "-a")
        self.answer("Answer: fixed", "Answer: fixed", "Answer: fixed")
        result = self.refused("Round 2 started at %s" % start, "no longer in demo's history",
                              "amended, rebased or reset", "git reset --soft %s" % start,
                              "commit the change as a new commit")
        self.assertNotIn("code 2 end", self.state())
        self.box.git("reset", "-q", "--soft", start)
        self.box.git("commit", "-q", "-m", "fix: a")
        result = self.coder("check")
        self.assertEqual(result.code, 0, result)
        self.assertIn("code 2 end %s" % self.sha(), self.state())

    def test_a_round_with_new_commits_on_its_start_passes(self):
        """Commits of the round's own, in any number, keep the start in the
        branch's history."""
        self.later()
        self.commit("a.txt", "fix\n", "fix: a")
        self.commit("a.txt", "fix 2\n", "fix: a again")
        self.answer("Answer: fixed", "Answer: fixed", "Answer: fixed")
        result = self.coder("check")
        self.assertEqual(result.code, 0, result)

    def test_a_check_after_the_end_reprints_the_doorbell(self):
        self.started()
        self.put("FIXES.md", filled_round_one(self.read("FIXES.md")))
        self.coder("check")
        before = self.state()
        again = self.coder("check")
        self.assertEqual(again.code, 0, again)
        self.assertIn("VDD Coder: FIXES.md written, round 1. Read it.", again.lines)
        self.assertEqual(self.state(), before)


class VersionOneTest(CoderTest):
    def test_every_coder_command_refuses_a_version_one_loop(self):
        self.box.write_loop("demo", version=1)
        for sub in ("start", "check"):
            with self.subTest(sub=sub):
                result = self.coder(sub)
                self.assertNotEqual(result.code, 0, result)
                self.assertIn("0.16.0-beta.3", result.text)
                self.assertTrue(result.tells(), result)
        self.assertEqual(self.branch(), "main")


if __name__ == "__main__":
    unittest.main()
