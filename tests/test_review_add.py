"""review add, driven from outside: the user's findings after a code Sign-off,
and the rounds that run on them."""

import os
import unittest

from vddtest import SIGNED, LoopRepoTest, SceneTest
NEXT_LINE = "Next: Tell the Orchestrator the loop has your findings; it carries on with orchestrator start."

FINDINGS = """### major: docs/a.md:3

Body one.

### minor: the Spec, Testing Decisions
Body two.
"""

REVIEW = """# Code review, round 2

Open: 0 blocker, 1 major, 1 minor.

Findings raised by the user after the round-2 Sign-off.

## New findings

### 13. major (open): docs/a.md:3

Body one.

### 14. minor (open): the Spec, Testing Decisions

Body two.
"""

SIGNED_REVIEW = """# Code review, round 2

SIGNED OFF. Nothing open.

## Checks

code-review: ran
writing-for-agents: ran

## New findings

## Not carried
"""

FIXES_3 = """# Fixes, round 3

## Finding 13. major: docs/a.md:3

Answer: fixed

## Finding 14. minor: the Spec, Testing Decisions

Answer: pushback
Why: the Spec says so.
"""


class AddTest(SceneTest):
    minors = "fix"

    def stage_scene(self):
        self.box.init_git("main")
        self.commit("a.txt", "a\n", "base")
        self.box.write(".gitignore", ".scratch/\n")
        self.box.git("add", ".gitignore")
        self.box.git("commit", "-q", "-m", "ignore")
        self.box.git("checkout", "-q", "-b", "demo")
        self.box.write_loop("demo", states=("open", "closed"), text=(
            "# VDD Loop\n\nFormat: 2\nFeature: demo\nBase branch: main\nFeature branch: demo\nMinors: %s\n"
            "PR: ask at sign-off\nHarness: Claude Code\n" % self.minors), extra=(SIGNED,))
        self.put("spec.md", "# Spec\n")
        self.put("issues/01-one.md", "# 01\n")

    # --- staging ---

    def coder_round(self, number, name=None):
        LoopRepoTest.coder_round(self, number, name, "x%d\n" % number)

    def signed_loop(self, minors_open="-", counts="0 0 0", review=SIGNED_REVIEW, extra=(), next_number=13):
        """Code round 1 reviewed with a finding open, round 2 signed off, the
        Loop file closed, as a Sign-off leaves a loop."""
        self.coder_round(1)
        self.stage("code 1 reviewed open 1 counts 0 1 0 next 13 new 12 closed 0 checks code-review ran")
        self.coder_round(2)
        self.stage("code 2 reviewed signed-off %s counts %s next %d new 0 closed 1 checks code-review ran"
                   % (minors_open, counts, next_number), *extra)
        self.put("CODEREVIEW.md", review)

    def findings(self, text=FINDINGS, name="findings.md"):
        self.box.write(name, text)
        return name

    def add(self, source="findings.md", write=True):
        return self.box.run("review", "add", "--slug", "demo", "--from", source, *(["--write"] if write else []))

    SNAPSHOT = ("CODEREVIEW.md", "RECAP.md", "loop-state", "FIXES.md")

    def snapshot(self):
        return LoopRepoTest.snapshot(self, self.SNAPSHOT)

    def add_refused(self, *fragments, source="findings.md"):
        return LoopRepoTest.refused(self, ("review", "add", "--slug", "demo", "--from", source, "--write"),
                                self.SNAPSHOT, *fragments)


class DryRunAndWriteTest(AddTest):
    def test_help_documents_review_add(self):
        result = self.box.run("review", "--help")
        self.assertEqual(result.code, 0, result)
        for fragment in ("review add --slug <slug> --from <file> [--write]", "### major: src/app.py:12",
                         "Severity is blocker, major or minor", "signed-off code Loop", "Without --write"):
            self.assertIn(fragment, result.text.replace("\n  ", " "))

    def test_the_dry_run_numbers_from_the_states_next_and_changes_nothing(self):
        self.signed_loop()
        self.findings()
        before = self.snapshot()
        result = self.add(write=False)
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("### 13. major (open): docs/a.md:3", result.lines)
        self.assertIn("### 14. minor (open): the Spec, Testing Decisions", result.lines)
        self.assertIn("Open: 0 blocker, 1 major, 1 minor.", result.lines)
        self.assertIn("Would reopen the closed loop demo.", result.lines)
        self.assertTrue(any("CODEREVIEW.md" in line and line.startswith("Would") for line in result.lines), result)
        self.assertNext(result, "review add --slug demo --from findings.md --write")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.read("loop-state").count("loop open"), 1)

    def test_write_rewrites_the_review_records_the_line_reopens_and_writes_the_recap(self):
        self.signed_loop()
        self.findings()
        result = self.add()
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertEqual(self.read("CODEREVIEW.md"), REVIEW)
        self.assertEqual(result.last, NEXT_LINE)
        self.assertEqual(result.tells(), [])
        state = self.state().split("\n")
        self.assertEqual(state[-3:], ["code 2 user open 13,14 counts 0 1 1 next 15 new 2", "loop open", ""])
        recap = self.read("RECAP.md")
        self.assertIn("Code Loop: 2 rounds, reopened by the user's findings after round 2.", recap)
        rows = [line for line in recap.split("\n") if line.startswith("| code |")]
        self.assertEqual(rows[1], "| code | 2 | 0 | 1 | SIGNED OFF | code-review ran |")
        self.assertEqual(rows[2], "| code | 2, user | 2 | 0 | 0 blocker, 1 major, 1 minor | none |")
        self.assertTrue(any(line.startswith("Wrote") and "CODEREVIEW.md" in line for line in result.lines), result)
        self.assertIn("Reopened the loop demo.", result.lines)
        self.assertIn("Findings 13 and 14 open: 0 blocker, 1 major, 1 minor.", result.lines)
        self.assertNotIn("Tell the user verbatim", result.text)

    def test_an_open_loop_is_not_reopened_again(self):
        self.signed_loop()
        self.stage("loop open")
        self.findings()
        result = self.add()
        self.assertEqual(result.code, 0, result)
        self.assertEqual(self.state().count("loop open"), 2)
        self.assertNotIn("Reopened", result.text)

    def test_a_fenced_heading_in_a_body_is_body_text(self):
        self.signed_loop()
        self.findings("### major: a.py:1\n\nSee:\n\n```\n### minor: not a finding\n# not a title\n```\n")
        result = self.add()
        self.assertEqual(result.code, 0, result)
        text = self.read("CODEREVIEW.md")
        self.assertIn("```\n### minor: not a finding\n# not a title\n```", text)
        self.assertIn("Open: 0 blocker, 1 major, 0 minor.", text)
        self.assertIn("code 2 user open 13 counts 0 1 0 next 14 new 1", self.state())


class LintTest(AddTest):
    def refused(self, text, *fragments):
        """A malformed file is refused with the line and the fix, and nothing
        changes (the owner's grading found a slip only rounds later, at
        review start)."""
        self.signed_loop()
        self.findings(text)
        return self.add_refused("Nothing was written.", *fragments)

    def test_text_before_the_first_finding(self):
        self.refused("My notes.\n\n### major: a.py:1\n\nBody.\n", "findings.md line 1: text before the first finding",
                     "Move this text into a finding's body")

    def test_an_unknown_severity(self):
        self.refused("### urgent: a.py:1\n\nBody.\n", "findings.md line 1:", "the severity is blocker, major or minor")

    def test_an_upper_case_severity(self):
        self.refused("### Major: a.py:1\n\nBody.\n", "findings.md line 1:", "in lower case")

    def test_a_numbered_heading(self):
        self.refused("### 3. major: a.py:1\n\nBody.\n", "findings.md line 1:", "carries a number",
                     "The tool numbers the findings")

    def test_a_heading_with_no_colon(self):
        self.refused("### major a.py\n\nBody.\n", "findings.md line 1:", "is not a finding heading")

    def test_an_empty_reference(self):
        self.refused("### major:\n\nBody.\n", "findings.md line 1:", "has no reference")

    def test_an_empty_body(self):
        self.refused("### major: a.py:1\n\n### minor: b.py:2\n\nBody.\n", "findings.md line 1: this finding has no body")

    def test_a_title_or_section_heading_in_a_body(self):
        for heading in ("# Title", "## Section"):
            with self.subTest(heading=heading):
                self.setUp()
                self.refused("### major: a.py:1\n\nBody.\n\n%s\n\nMore.\n" % heading, "findings.md line 5:",
                             "would break CODEREVIEW.md's sections")

    def test_no_finding(self):
        self.refused("", "findings.md holds no finding")

    def test_an_unclosed_fence(self):
        self.refused("### major: a.py:1\n\n```\ncode\n", "findings.md line 3:", "never closed")

    def test_an_unreadable_file(self):
        self.signed_loop()
        before = self.snapshot()
        result = self.add("missing.md")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("--from missing.md cannot be read", result.text)
        self.assertEqual(self.snapshot(), before)

    def test_every_slip_is_listed_in_one_run(self):
        result = self.refused("### urgent: a.py:1\n\nBody.\n\n### 3. major: b.py:1\n\nBody.\n",
                              "findings.md line 1:", "findings.md line 5:")
        self.assertEqual(len([l for l in result.lines if l.startswith("findings.md line")]), 2, result)


class RefusalTest(AddTest):
    def refused(self, *fragments):
        self.findings()
        return self.add_refused(*fragments)

    def test_a_version_one_state_file(self):
        self.box.write_loop("demo", version=1)
        result = self.refused("0.16.0-beta.3")
        self.assertTrue(result.tells(), result)

    def test_a_code_loop_with_no_recorded_review(self):
        self.refused("no recorded review", "review add takes findings only after a code Sign-off")

    def test_a_newest_review_with_findings_open(self):
        self.coder_round(1)
        self.stage("code 1 reviewed open 1 counts 0 1 0 next 2 new 1 closed 0 checks code-review ran")
        self.put("CODEREVIEW.md", "# Code review, round 1\n")
        self.refused("round 1's review left findings open", "review add takes findings only after a code Sign-off")

    def test_a_round_the_coder_has_started(self):
        self.signed_loop()
        self.findings()
        self.assertEqual(self.add().code, 0)
        self.stage("code 3 start %s" % self.sha())
        self.refused("The Coder has started code round 3", "review add waits for the next code Sign-off")


class JoinTest(AddTest):
    def test_a_second_add_joins_the_open_entry(self):
        self.signed_loop()
        self.assertEqual(self.add(self.findings()).code, 0)
        first = self.read("CODEREVIEW.md")
        second = self.findings("### blocker: c.py:9\n\nThird.\n", "more.md")
        result = self.add(second)
        self.assertEqual(result.code, 0, result)
        text = self.read("CODEREVIEW.md")
        self.assertIn("Open: 1 blocker, 1 major, 1 minor.", text)
        body = first.split("## New findings\n")[1]
        self.assertIn(body, text)
        self.assertTrue(text.endswith("### 15. blocker (open): c.py:9\n\nThird.\n"), text)
        lines = self.state().split("\n")
        self.assertEqual([l for l in lines if " user " in l], [
            "code 2 user open 13,14 counts 0 1 1 next 15 new 2",
            "code 2 user open 13,14,15 counts 1 1 1 next 16 new 3"])
        recap = self.read("RECAP.md")
        self.assertEqual(len([l for l in recap.split("\n") if "2, user" in l]), 1, recap)
        self.assertIn("| code | 2, user | 3 | 0 | 1 blocker, 1 major, 1 minor | none |", recap)
        started = self.box.run("coder", "start", "--slug", "demo", "--write")
        self.assertEqual(started.code, 0, started)
        fixes = self.read("FIXES.md")
        for heading in ("## Finding 13. major: docs/a.md:3", "## Finding 14. minor: the Spec, Testing Decisions",
                        "## Finding 15. blocker: c.py:9"):
            self.assertIn(heading, fixes)

    def test_a_second_add_refuses_when_the_entry_lost_a_heading(self):
        self.signed_loop()
        self.assertEqual(self.add(self.findings()).code, 0)
        text = self.read("CODEREVIEW.md").replace("### 14. minor (open)", "### minor (open)")
        self.put("CODEREVIEW.md", text)
        self.findings("### blocker: c.py:9\n\nThird.\n", "more.md")
        before = self.snapshot()
        result = self.add("more.md")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("no longer holds the heading of finding 14", result.text)
        self.assertEqual(self.snapshot(), before)


class MinorsLeaveTest(AddTest):
    minors = "leave"

    def stage_leave(self):
        self.signed_loop(minors_open="14,15", counts="0 0 2", next_number=16, review=(
            "# Code review, round 2\n\nSIGNED OFF. Open minors left, as Minors: leave allows: 2.\n\n"
            "## New findings\n\n### 14. minor (open): docs/x.md:3\n\nOne.\n\n"
            "### 15. minor (open): README.md:9\n\nTwo.\n"))

    def test_the_minors_are_named_and_not_carried(self):
        self.stage_leave()
        self.findings("### major: a.py:1\n\nBody.\n")
        note = "Not carried: the minors left open at round 2's Sign-off, 14 (docs/x.md:3) and 15 (README.md:9)."
        dry = self.add(write=False)
        self.assertIn(note, dry.lines)
        result = self.add()
        self.assertEqual(result.code, 0, result)
        self.assertIn(note, result.lines)
        text = self.read("CODEREVIEW.md")
        self.assertNotIn("docs/x.md", text)
        self.assertEqual(text.count("### "), 1)
        self.assertIn("### 16. major (open): a.py:1", text)

    def test_a_second_add_names_no_minor_and_passes(self):
        self.stage_leave()
        self.assertEqual(self.add(self.findings("### major: a.py:1\n\nBody.\n")).code, 0)
        result = self.add(self.findings("### minor: b.py:2\n\nMore.\n", "more.md"))
        self.assertEqual(result.code, 0, result)
        self.assertNotIn("Not carried", result.text)


class RecapFailureTest(AddTest):
    def test_an_unwritable_recap_leaves_the_state_alone_and_a_rerun_writes_each_finding_once(self):
        """The state line is persisted after the Recap, as review check does:
        a failed write leaves the state unchanged and the same command runs
        again."""
        self.signed_loop()
        self.findings()
        before = self.state()
        os.makedirs(self.box.path(".scratch", "demo", "RECAP.md"))
        result = self.add()
        self.assertNotEqual(result.code, 0, result)
        self.assertEqual(self.state(), before)
        os.rmdir(self.box.path(".scratch", "demo", "RECAP.md"))
        result = self.add()
        self.assertEqual(result.code, 0, result)
        self.assertEqual(self.read("CODEREVIEW.md").count("(open)"), 2)
        self.assertEqual(self.state().count(" user open "), 1)


class RoundAfterTest(AddTest):
    def test_the_next_rounds_run_on_the_findings_through_the_usual_commands(self):
        self.signed_loop()
        self.assertEqual(self.add(self.findings()).code, 0)
        started = self.box.run("coder", "start", "--slug", "demo", "--write")
        self.assertEqual(started.code, 0, started)
        self.assertIn("Entries: one per open finding, 13 and 14.", started.lines)
        self.assertIn("Read: .scratch/demo/CODEREVIEW.md, .scratch/demo/spec.md, .scratch/demo/issues/",
                      started.lines)
        self.put("FIXES.md", FIXES_3)
        self.commit("src/r3.txt", "fix\n", "fix: the findings")
        checked = self.box.run("coder", "check", "--slug", "demo", "--write")
        self.assertEqual(checked.code, 0, checked)
        review = self.box.run("review", "start", "--role", "Code-Reviewer", "--slug", "demo", "--write")
        self.assertEqual(review.code, 0, review)
        self.assertIn("Round 3: findings 13 and 14 carried open, new findings start at 15.", review.lines)
        text = self.read("CODEREVIEW.md")
        self.assertIn("## Open findings\n\n### 13. major (open): docs/a.md:3\n\nBody one.", text)
        text = text.replace("### 13. major (open)", "### 13. major (fixed)").replace(
            "Coder: fixed in round 3.\n", "Coder: fixed in round 3.\n\nResolution: done.\n", 1)
        text = text.replace("### 14. minor (open)", "### 14. minor (accepted)").replace(
            "Coder: pushed back in round 3. the Spec says so.\n",
            "Coder: pushed back in round 3. the Spec says so.\n\nResolution: accepted.\n", 1)
        text = text.replace("code-review: <ran | did not resolve, the Spec reviewed by hand | not needed, <reason>>",
                            "code-review: ran").replace(
            "writing-for-agents: <ran | did not resolve | not needed, <reason>>", "writing-for-agents: ran")
        self.put("CODEREVIEW.md", text)
        done = self.box.run("review", "check", "--role", "Code-Reviewer", "--slug", "demo", "--write")
        self.assertEqual(done.code, 0, done)
        recap = self.read("RECAP.md")
        self.assertIn("### 13. major, raised by the user after round 2, fixed in round 3: docs/a.md:3", recap)
        self.assertIn("### 14. minor, raised by the user after round 2, accepted in round 3: the Spec, Testing "
                      "Decisions", recap)
        self.assertIn("Code Loop: 3 rounds, signed off in round 3.", recap)
        # A later add numbers on from round 3's next and writes a second user row.
        again = self.add(self.findings("### minor: z.md:1\n\nLate.\n", "late.md"))
        self.assertEqual(again.code, 0, again)
        self.assertIn("### 15. minor (open): z.md:1", self.read("CODEREVIEW.md"))
        recap = self.read("RECAP.md")
        self.assertEqual([l for l in recap.split("\n") if ", user |" in l], [
            "| code | 2, user | 2 | 0 | 0 blocker, 1 major, 1 minor | none |",
            "| code | 3, user | 1 | 0 | 0 blocker, 0 major, 1 minor | none |"])

    def test_the_pr_author_refuses_while_the_users_findings_are_open(self):
        self.signed_loop()
        self.assertEqual(self.add(self.findings()).code, 0)
        result = self.box.run("loop", "show", "--slug", "demo", "--role", "PR-Author")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("the user's findings after code round 2 are open", result.text)


if __name__ == "__main__":
    unittest.main()
