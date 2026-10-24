"""The review command group for the Code-Reviewer, driven from outside: the
code review on the tool."""

import os
import unittest

from vddtest import SIGNED, LoopRepoTest, SceneTest

CODE_REVIEW_1 = "<ran | did not resolve, the Spec reviewed by hand>"
CODE_REVIEW_LATER = "<ran | did not resolve, the Spec reviewed by hand | not needed, <reason>>"
WFA = "<ran | did not resolve | not needed, <reason>>"
NOT_CARRIED_GUIDE = (
    "<!-- VDD: One line for each problem the code-review reports raise that you\n"
    "do not turn into a finding, a wrong one included. A report line that finds\n"
    "nothing wrong gets no line.\n"
    "- <the problem, in one line>: <why not> -->"
)

ROUND_1_FINDINGS = """
### 1. major (open): src/a.py:3

Wrong.

### 2. minor (open): src/b.py:9

Meh.

### 3. minor (open): README.md:40

Missing.
"""

FIXES_2 = """# Fixes, round 2

## Finding 1. major: src/a.py:3

Answer: fixed

## Finding 2. minor: src/b.py:9

Answer: fixed
Why: through the helper.

## Finding 3. minor: README.md:40

Answer: pushback
Why: the Spec keeps the README
as it is.
"""


class CodeReviewTest(SceneTest):
    minors = "fix"

    def stage_scene(self):
        self.box.init_git("main")
        self.commit("a.txt", "a\n", "base")
        self.box.git("checkout", "-q", "-b", "demo")
        self.box.write_loop("demo", text=(
            "# VDD Loop\n\nFormat: 2\nFeature: demo\nBase branch: main\nFeature branch: demo\nMinors: %s\n"
            "PR: ask at sign-off\nHarness: Claude Code\n" % self.minors), extra=(SIGNED,))
        self.box.write(os.path.join(".scratch", "demo", "spec.md"), "# Spec\n")
        self.box.write(os.path.join(".scratch", "demo", "issues", "01-one.md"), "# 01\n")

    def review(self, sub, write=True):
        return self.box.run("review", sub, "--role", "Code-Reviewer", "--slug", "demo", *(["--write"] if write else []))

    def round_one(self, findings=ROUND_1_FINDINGS, not_carried=""):
        self.coder_round(1)
        started = self.review("start")
        self.assertEqual(started.code, 0, started)
        text = self.read("CODEREVIEW.md")
        text = text.replace("code-review: <ran | did not resolve, the Spec reviewed by hand>", "code-review: ran")
        text = text.replace("## New findings\n", "## New findings\n" + findings)
        text = text.replace(NOT_CARRIED_GUIDE, NOT_CARRIED_GUIDE + "\n" + not_carried)
        self.put("CODEREVIEW.md", text)
        return started

    def round_two(self, not_carried="- `f` could take a flag: no caller needs one.\n"):
        self.round_one(not_carried=not_carried)
        checked = self.review("check")
        self.assertEqual(checked.code, 0, checked)
        self.coder_round(2)
        self.put("FIXES.md", FIXES_2)
        started = self.review("start")
        self.assertEqual(started.code, 0, started)
        return started

    def answered_round_two(self, keep_three=False):
        self.round_two()
        text = self.fill(self.read("CODEREVIEW.md"))
        text = text.replace("### 1. major (open)", "### 1. major (fixed)").replace(
            "Coder: fixed in round 2.\n", "Coder: fixed in round 2.\n\nResolution: the check now holds.\n", 1)
        text = text.replace("### 2. minor (open)", "### 2. minor (fixed)").replace(
            "Coder: fixed in round 2. through the helper.\n",
            "Coder: fixed in round 2. through the helper.\n\nResolution: the helper.\n")
        if keep_three:
            text = text.replace("the Spec keeps the README as it is.\n",
                                "the Spec keeps the README as it is.\n\nReviewer: kept open in round 2. It is needed.\n")
        else:
            text = text.replace("### 3. minor (open)", "### 3. minor (accepted)").replace(
                "the Spec keeps the README as it is.\n",
                "the Spec keeps the README as it is.\n\nResolution: accepted the pushback.\n")
        text = text.replace(NOT_CARRIED_GUIDE, NOT_CARRIED_GUIDE + "\n- one more: not needed.\n")
        self.put("CODEREVIEW.md", text)

    def fill(self, text):
        for placeholder in (CODE_REVIEW_1, CODE_REVIEW_LATER):
            text = text.replace("code-review: " + placeholder, "code-review: ran")
        return text


class StartTest(CodeReviewTest):
    def test_start_refuses_before_the_coder_end_is_recorded(self):
        result = self.review("start")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("The Coder's end of code round 1 is not recorded", result.text)
        self.assertFalse(os.path.exists(self.box.path(".scratch", "demo", "CODEREVIEW.md")))

    def test_round_one_frame(self):
        self.coder_round(1)
        result = self.review("start")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        text = self.read("CODEREVIEW.md")
        self.assertTrue(text.startswith("# Code review, round 1\n"), text)
        self.assertIn("\n## Checks\n\ncode-review: <ran | did not resolve, the Spec reviewed by hand>\n"
                      "writing-for-agents: no Agent document in this round's diff\n", text)
        self.assertIn("\n## New findings\n", text)
        self.assertIn("\n## Not carried\n\n" + NOT_CARRIED_GUIDE + "\n", text)
        self.assertIn("Base branch: main", result.lines)
        self.assertIn("Minors: fix", result.lines)
        self.assertIn("Harness file: harness-claude-code.md", result.lines)
        self.assertIn("main...demo", result.text)
        self.assertIn("Read: .scratch/demo/spec.md, .scratch/demo/issues/, .scratch/demo/FIXES.md", result.lines)

    def test_round_two_carries_each_finding_with_the_coder_s_answer(self):
        result = self.round_two()
        text = self.read("CODEREVIEW.md")
        self.assertIn("### 1. major (open): src/a.py:3\n\nWrong.\n\nCoder: fixed in round 2.\n", text)
        self.assertIn("### 2. minor (open): src/b.py:9\n\nMeh.\n\nCoder: fixed in round 2. through the helper.\n",
                      text)
        self.assertIn("### 3. minor (open): README.md:40\n\nMissing.\n\n"
                      "Coder: pushed back in round 2. the Spec keeps the README as it is.\n", text)
        self.assertIn("new findings start at 4", result.text)
        self.assertIn("Read: .scratch/demo/CODEREVIEW.md, .scratch/demo/spec.md, .scratch/demo/issues/",
                      result.lines)

    def test_a_second_start_keeps_the_file_and_reprints(self):
        """A second start in a started round writes nothing; the carried blocks
        stay in carried-code.md."""
        first = self.round_two()
        self.put("CODEREVIEW.md", self.read("CODEREVIEW.md").replace("major (open)", "major (fixed)"))
        before = (self.read("CODEREVIEW.md"), self.read("carried-code.md"), self.read("loop-state"))
        second = self.review("start")
        self.assertEqual(second.code, 0, second)
        self.assertEqual((self.read("CODEREVIEW.md"), self.read("carried-code.md"), self.read("loop-state")), before)
        self.assertEqual(second.lines[1:], first.lines[1:])
        self.assertIn("Coder: pushed back in round 2.", self.read("carried-code.md"))


class AgentDocumentTest(CodeReviewTest):
    """The Agent-document list: a changed Agent document, and a file one link
    away from an Agent document at the tip, is listed. Only changed .md files
    count, and only the link syntax is read."""

    def listed(self):
        self.coder_round(1)
        result = self.review("start")
        self.assertEqual(result.code, 0, result)
        return result

    def documents(self, result):
        line = [l for l in result.lines if l.startswith("Agent documents in the range:")][0]
        return line

    def test_a_changed_skill_file_is_listed(self):
        self.commit("skills/x/SKILL.md", "x\n", "skill")
        self.assertIn("skills/x/SKILL.md", self.documents(self.listed()))

    def test_a_file_linked_from_an_unchanged_agents_md_is_listed(self):
        self.box.git("checkout", "-q", "main")
        self.commit("AGENTS.md", "See [note](docs/agents/note.md).\n", "agents")
        self.box.git("checkout", "-q", "demo")
        self.box.git("rebase", "-q", "main")
        self.commit("docs/agents/note.md", "note\n", "note")
        line = self.documents(self.listed())
        self.assertIn("docs/agents/note.md", line)
        self.assertNotIn("AGENTS.md,", line)

    def test_a_file_at_included_from_claude_md_is_listed(self):
        self.commit("CLAUDE.md", "@docs/rules.md\n", "claude")
        self.commit("docs/rules.md", "rules\n", "rules")
        self.assertIn("docs/rules.md", self.documents(self.listed()))

    def test_code_under_references_or_scripts_never_counts(self):
        self.commit("skills/x/SKILL.md", "[t](references/tool.py) [r](scripts/run.py)\n", "skill")
        self.commit("skills/x/references/tool.py", "x = 1\n", "tool")
        self.commit("skills/x/scripts/run.py", "x = 1\n", "run")
        line = self.documents(self.listed())
        self.assertNotIn("tool.py", line)
        self.assertNotIn("run.py", line)

    def test_a_nested_link_resolves_from_the_linking_file(self):
        self.box.git("checkout", "-q", "main")
        self.commit("skills/x/SKILL.md", "See [x](../../docs/x.md#usage).\n", "skill")
        self.box.git("checkout", "-q", "demo")
        self.box.git("rebase", "-q", "main")
        self.commit("docs/x.md", "x\n", "doc")
        self.assertIn("docs/x.md", self.documents(self.listed()))

    def test_urls_placeholders_and_unlinked_files_are_skipped(self):
        """With only a URL target, a placeholder target and an unlinked .md
        changed, the frame fills the writing-for-agents line itself."""
        self.box.git("checkout", "-q", "main")
        self.commit("README.md", "[a](https://example.com/a.md) [b](<slug>/b.md)\n", "readme")
        self.box.git("checkout", "-q", "demo")
        self.box.git("rebase", "-q", "main")
        self.commit("src/app.md", "app\n", "app")
        result = self.listed()
        self.assertIn("Agent documents in the range: none", self.documents(result))
        self.assertIn("writing-for-agents: no Agent document in this round's diff", self.read("CODEREVIEW.md"))

    def test_with_an_agent_document_the_line_is_left_to_fill(self):
        self.commit("skills/x/SKILL.md", "x\n", "skill")
        self.listed()
        self.assertIn("writing-for-agents: " + WFA, self.read("CODEREVIEW.md"))


class CheckTest(CodeReviewTest):
    def test_round_one_moves_the_not_carried_lines(self):
        self.round_one(not_carried="- the helper could be\n  shorter: it reads fine.\n")
        result = self.review("check")
        self.assertEqual(result.code, 0, result)
        self.assertIn("VDD Code-Reviewer: CODEREVIEW.md written, round 1: 0 blocker, 1 major, 2 minor. Read it.",
                      result.lines)
        recap = self.read("RECAP.md")
        self.assertIn("- Code round 1: the helper could be shorter: it reads fine.", recap)
        self.assertNotIn("the helper could be", self.read("CODEREVIEW.md"))

    def test_kept_open_after_an_answer_needs_the_reviewer_line(self):
        """A carried finding the Coder answered and the reviewer keeps open
        needs the reviewer's reason: the Coder gets a reason, not just an open
        finding."""
        self.round_two()
        text = self.fill(self.read("CODEREVIEW.md"))
        text = text.replace("### 1. major (open)", "### 1. major (fixed)").replace(
            "Coder: fixed in round 2.\n", "Coder: fixed in round 2.\n\nResolution: done.\n", 1)
        text = text.replace("### 2. minor (open)", "### 2. minor (fixed)").replace(
            "Coder: fixed in round 2. through the helper.\n",
            "Coder: fixed in round 2. through the helper.\n\nResolution: done.\n")
        self.put("CODEREVIEW.md", text)
        before = self.read("CODEREVIEW.md")
        result = self.review("check")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("finding 3 keeps the Coder's round-2 answer and stays open", result.text)
        self.assertIn('"Reviewer: kept open in round 2."', result.text)
        self.assertEqual(self.read("CODEREVIEW.md"), before)

    def test_not_carried_refuses_a_line_that_is_not_a_bullet(self):
        """Not carried holds "- " lines only."""
        self.round_one(not_carried="the helper could be shorter\n")
        result = self.review("check")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn('under ## Not carried every line starts with "- ": "- <the problem, in one line>: '
                      '<why not>"', result.text)

    def test_an_axis_less_not_carried_line_passes_into_the_recap(self):
        """A Not carried line names no axis, and the Recap puts only the round
        in front of it."""
        self.round_one(not_carried="- the helper could be shorter: it reads fine.\n")
        result = self.review("check")
        self.assertEqual(result.code, 0, result)
        self.assertIn("- Code round 1: the helper could be shorter: it reads fine.", self.read("RECAP.md"))

    def test_not_carried_refuses_an_empty_line(self):
        """A "- " line with nothing after it would put an empty line into the
        Recap."""
        self.round_one(not_carried="- \n")
        before = self.read("CODEREVIEW.md")
        result = self.review("check")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn('this Not carried line is empty. Write "- <the problem, in one line>: <why not>"', result.text)
        self.assertEqual(self.read("CODEREVIEW.md"), before)
        self.assertFalse(os.path.exists(self.box.path(".scratch", "demo", "RECAP.md")))

    def test_an_empty_not_carried_and_a_wrapped_line_pass(self):
        """A wrapped "- " line is joined, never refused."""
        self.round_one()
        self.assertEqual(self.review("check", write=False).code, 0)

    def test_a_passing_round_two_moves_the_closed_findings(self):
        self.answered_round_two(keep_three=True)
        result = self.review("check")
        self.assertEqual(result.code, 0, result)
        recap = self.read("RECAP.md")
        code = recap.split("## Code findings")[1].split("## Not carried")[0]
        self.assertIn("### 1. major, fixed in round 2: src/a.py:3", code)
        self.assertIn("Problem: Wrong.", code)
        self.assertIn("Resolution: the check now holds.", code)
        self.assertIn("### 2. minor, fixed in round 2: src/b.py:9", code)
        self.assertNotIn("Coder:", code)
        notes = recap.split("## Not carried")[1]
        self.assertIn("- Code round 1: `f` could take a flag: no caller needs one.", notes)
        self.assertIn("- Code round 2: one more: not needed.", notes)
        review = self.read("CODEREVIEW.md")
        self.assertIn("\nOpen: 0 blocker, 0 major, 1 minor.\n", review)
        self.assertNotIn("### 1.", review)
        self.assertNotIn("### 2.", review)
        self.assertIn("### 3. minor (open): README.md:40", review)
        self.assertNotIn("one more", review)

    def test_round_three_carries_the_whole_thread(self):
        self.answered_round_two(keep_three=True)
        self.assertEqual(self.review("check").code, 0)
        self.coder_round(3)
        self.put("FIXES.md", "# Fixes, round 3\n\n## Finding 3. minor: README.md:40\n\nAnswer: pushback\n"
                             "Why: still so.\n")
        result = self.review("start")
        self.assertEqual(result.code, 0, result)
        text = self.read("CODEREVIEW.md")
        self.assertIn("Coder: pushed back in round 2. the Spec keeps the README as it is.", text)
        self.assertIn("Reviewer: kept open in round 2. It is needed.", text)
        self.assertIn("Coder: pushed back in round 3. still so.", text)

    def test_the_code_sign_off(self):
        self.answered_round_two()
        result = self.review("check")
        self.assertEqual(result.code, 0, result)
        self.assertIn("VDD Code-Reviewer: CODEREVIEW.md SIGNED OFF, round 2.", result.lines)
        self.assertIn("code 2 reviewed signed-off -", self.read("loop-state"))



class ChecksValuesTest(CodeReviewTest):
    """Prevents a skip recorded as ran: a round-2
    Code-Reviewer that rightly reviewed a small fix by hand was refused twice
    and settled on ran. not needed, <reason> records a skip as a skip."""

    SKIP = "code-review: not needed, round 1 reviewed the branch; this round's fix is two lines"

    def refused(self, *fragments):
        return LoopRepoTest.refused(self, ("review", "check", "--role", "Code-Reviewer", "--slug", "demo", "--write"),
                                ("CODEREVIEW.md", "loop-state", "RECAP.md"), *fragments)

    def with_code_review(self, value):
        lines = self.read("CODEREVIEW.md").split("\n")
        self.put("CODEREVIEW.md", "\n".join(value if line.startswith("code-review:") else line for line in lines))

    def test_not_needed_on_a_later_code_review_passes_into_the_recap(self):
        self.answered_round_two()
        self.with_code_review(self.SKIP)
        result = self.review("check")
        self.assertEqual(result.code, 0, result)
        row = [line for line in self.read("RECAP.md").split("\n") if line.startswith("| code | 2 |")]
        self.assertEqual(len(row), 1, self.read("RECAP.md"))
        self.assertIn(self.SKIP.replace(": ", " ", 1), row[0])

    def test_not_needed_on_round_one_s_code_review_is_refused(self):
        self.round_one()
        self.with_code_review(self.SKIP)
        self.refused("CODEREVIEW.md line ", "round 1's code-review is never skipped")

    def test_not_needed_with_no_reason_or_a_bar_is_refused(self):
        self.answered_round_two()
        self.with_code_review("code-review: not needed,")
        self.refused("CODEREVIEW.md line ", "\"code-review: not needed,\" gives no reason")
        self.with_code_review("code-review: not needed, a | b")
        self.refused("CODEREVIEW.md line ", "the reason holds a |")

    def test_writing_for_agents_not_needed_passes_in_round_two(self):
        self.answered_round_two()
        lines = self.read("CODEREVIEW.md").split("\n")
        value = "writing-for-agents: not needed, no Agent document changed this round"
        self.put("CODEREVIEW.md", "\n".join(value if line.startswith("writing-for-agents:") else line
                                            for line in lines))
        result = self.review("check")
        self.assertEqual(result.code, 0, result)
        self.assertIn(value.replace(": ", " ", 1), self.read("RECAP.md"))

    def test_a_skill_file_in_the_range_leaves_writing_for_agents_to_fill(self):
        self.coder_round(1)
        self.commit("skills/x/SKILL.md", "# x\n", "feat: a skill")
        self.stage("code 1 end %s" % self.sha())
        self.assertEqual(self.review("start").code, 0)
        self.assertIn("\nwriting-for-agents: %s\n" % WFA, self.read("CODEREVIEW.md"))

    def test_each_round_s_placeholders(self):
        """Each frame's placeholder lists exactly the values its line takes in
        that round."""
        self.coder_round(1)
        self.assertEqual(self.review("start").code, 0)
        self.assertIn("\ncode-review: %s\n" % CODE_REVIEW_1, self.read("CODEREVIEW.md"))
        self.box.cleanup()
        self.setUp()
        self.round_two()
        self.assertIn("\ncode-review: %s\n" % CODE_REVIEW_LATER, self.read("CODEREVIEW.md"))


class OwnDiffTest(CodeReviewTest):
    """Prevents a later round reviewed on the whole branch: the tool listed round
    1's Agent document again in round 2, because it read the whole branch
    while its own text says "this round's diff". A later round is reviewed
    from the previous round's recorded end."""

    def round_one_with_a_skill(self):
        start = self.sha()
        self.commit("skills/x/SKILL.md", "# x\n", "feat: a skill")
        self.stage("code 1 start %s" % start, "code 1 end %s" % self.sha())

    def test_round_one_reviews_from_the_base_branch(self):
        self.round_one_with_a_skill()
        result = self.review("start")
        self.assertEqual(result.code, 0, result)
        self.assertIn("Review range: main...demo, with main as code-review's fixed point and the diff you check "
                      "against the Tickets.", result.lines)
        self.assertIn("Agent documents in the range: skills/x/SKILL.md", result.lines)

    def test_a_later_round_reviews_from_the_previous_round_s_end(self):
        self.round_one_with_a_skill()
        end = self.sha()
        self.assertEqual(self.review("start").code, 0)
        text = self.fill(self.read("CODEREVIEW.md")).replace(
            "writing-for-agents: " + WFA, "writing-for-agents: ran").replace(
            "## New findings\n", "## New findings\n" + ROUND_1_FINDINGS)
        self.put("CODEREVIEW.md", text)
        self.assertEqual(self.review("check").code, 0)
        self.commit("src/fix.py", "x = 1\n", "fix: the check")
        self.stage("code 2 start %s" % end, "code 2 end %s" % self.sha())
        self.put("FIXES.md", FIXES_2)
        result = self.review("start")
        self.assertEqual(result.code, 0, result)
        self.assertIn("Fixed point: %s, code round 1's recorded end." % end, result.lines)
        self.assertTrue(any(line.startswith("Review range: %s...demo, this round's own diff" % end)
                            and "The verification runs on the whole branch." in line
                            for line in result.lines), result)
        self.assertIn("Agent documents in the range: none, so the writing-for-agents line is filled.", result.lines)
        self.assertIn("\nwriting-for-agents: no Agent document in this round's diff\n", self.read("CODEREVIEW.md"))
        self.assertIn("\ncode-review: %s\n" % CODE_REVIEW_LATER, self.read("CODEREVIEW.md"))

    def test_a_later_round_with_no_commits_fills_code_review(self):
        self.round_one()
        self.assertEqual(self.review("check").code, 0)
        end = self.sha()
        self.stage("code 2 start %s" % end, "code 2 end %s" % end)
        self.put("FIXES.md", FIXES_2.replace("Answer: fixed\n", "Answer: pushback\nWhy: as the Spec says.\n"))
        result = self.review("start")
        self.assertEqual(result.code, 0, result)
        self.assertIn("No commits in this round's range, so the code-review line is filled: not needed, no "
                      "commits in this round.", result.lines)
        text = self.read("CODEREVIEW.md")
        self.assertIn("\ncode-review: not needed, no commits in this round\n", text)
        text = text.replace(" (open): src/a.py:3", " (accepted): src/a.py:3").replace(
            " (open): src/b.py:9", " (accepted): src/b.py:9").replace(" (open): README.md:40", " (accepted): README.md:40")
        text = text.replace("\n\nCoder: pushed back in round 2.", "\n\nResolution: accepted.\n\nCoder: pushed back in round 2.")
        self.put("CODEREVIEW.md", text)
        checked = self.review("check")
        self.assertEqual(checked.code, 0, checked)
        self.assertIn("code-review not needed, no commits in this round", self.read("RECAP.md"))

if __name__ == "__main__":
    unittest.main()
