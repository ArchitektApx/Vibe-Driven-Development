"""The review command group, driven from outside: the plan Loop on the tool."""

import os
import unittest

from vddtest import LoopRepoTest, SceneTest

WFA = "<ran | did not resolve | not needed, <reason>>"
P1 = "VDD Planner: .scratch/demo/ ready, round 1. Read spec.md and issues/."

ROUND_1 = """# Plan review, round 1

<!-- VDD: left as the tool wrote it. -->

## Checks

writing-for-agents: ran

## New findings

### 1. major (open): Implementation Decisions

The Spec does not say how amounts are written.

### 2. minor (open): Ticket 02

Ticket 02 leaves `summary` out.
"""


class ReviewTest(SceneTest):
    def stage_scene(self):
        self.box.init_git("main")
        self.box.write_loop("demo", text=(
            "# VDD Loop\n\nFormat: 2\nFeature: demo\nBase branch: main\nFeature branch: demo\nMinors: %s\n"
            "PR: ask at sign-off\nHarness: Claude Code\n" % self.minors))
        self.box.write(os.path.join(".scratch", "demo", "spec.md"), "# Spec\n")
        self.box.write(os.path.join(".scratch", "demo", "issues", "01-one.md"), "# 01\n")
        self.box.write(os.path.join(".scratch", "demo", "issues", "02-two.md"), "# 02\n")

    minors = "fix"

    def tool(self, *args):
        return self.box.run(*args)

    def ring(self, role="Planner"):
        return self.tool("doorbell", "ring", "--role", role, "--harness", "claude-code", "--slug", "demo", "--write")

    def start(self, write=True):
        return self.tool("review", "start", "--role", "Plan-Reviewer", "--slug", "demo", *(["--write"] if write else []))

    def check(self, write=True):
        return self.tool("review", "check", "--role", "Plan-Reviewer", "--slug", "demo", *(["--write"] if write else []))

    def round_one(self, text=ROUND_1):
        self.ring()
        started = self.start()
        self.assertEqual(started.code, 0, started)
        self.put("PLAN-REVIEW.md", text)
        return started

    def round_two(self):
        self.round_one()
        checked = self.check()
        self.assertEqual(checked.code, 0, checked)
        self.ring()
        started = self.start()
        self.assertEqual(started.code, 0, started)
        return started

    def snapshot(self):
        return LoopRepoTest.snapshot(self, ("PLAN-REVIEW.md", "RECAP.md", "loop-state"))


class HelpTest(ReviewTest):
    def test_help_teaches_start_and_check(self):
        result = self.tool("review", "--help")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("review start", result.text)
        self.assertIn("review check", result.text)

    def test_the_top_level_help_lists_the_group(self):
        self.assertIn("  review ", self.tool("--help").text)


class StartTest(ReviewTest):
    def test_the_planner_rings_round_one_composed_from_the_state(self):
        result = self.ring()
        self.assertEqual(result.code, 0, result)
        self.assertIn("to: Orchestrator " + P1, self.read("doorbells"))
        refused = self.tool("doorbell", "ring", "--role", "Planner", "--line", P1, "--harness", "claude-code",
                            "--slug", "demo", "--write")
        self.assertNotEqual(refused.code, 0, refused)
        self.assertIn("Unknown option: --line", refused.text)

    def test_start_refuses_before_the_planner_rings(self):
        result = self.start()
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("The Planner has rung no round", result.text)
        self.assertFalse(self.exists("PLAN-REVIEW.md"))

    def test_round_one_frame(self):
        self.ring()
        result = self.start()
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        text = self.read("PLAN-REVIEW.md")
        lines = text.split("\n")
        self.assertEqual(lines[0], "# Plan review, round 1")
        self.assertIn("<!-- VDD: ", text)
        self.assertIn("## Checks\n\nwriting-for-agents: " + WFA + "\n", text)
        self.assertIn("\n## New findings\n", text)
        self.assertNotIn("## Open findings", text)
        self.assertIn("Read: .scratch/demo/spec.md, .scratch/demo/issues/", result.lines)
        self.assertIn("Minors: fix", result.lines)
        self.assertIn("new findings start at 1", result.text)
        self.assertNext(result, "review check --role Plan-Reviewer --slug demo --write")
        self.assertIn("plan 1 review-started", self.read("loop-state"))

    def test_a_second_start_writes_nothing_and_prints_the_same(self):
        """A respawned Plan-Reviewer's first call is start again: it must not
        wipe the round's work."""
        self.ring()
        first = self.start()
        self.put("PLAN-REVIEW.md", ROUND_1)
        before = self.snapshot()
        second = self.start()
        self.assertEqual(second.code, 0, second)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("Nothing was written", second.lines[0])
        self.assertEqual(second.lines[1:], first.lines[1:])

    def test_round_two_carries_both_findings_whole(self):
        result = self.round_two()
        text = self.read("PLAN-REVIEW.md")
        self.assertTrue(text.startswith("# Plan review, round 2\n"), text)
        open_part = text.split("## Open findings")[1].split("## New findings")[0]
        self.assertIn("### 1. major (open): Implementation Decisions\n\nThe Spec does not say how amounts are written.",
                      open_part)
        self.assertIn("### 2. minor (open): Ticket 02\n\nTicket 02 leaves `summary` out.", open_part)
        self.assertIn("Resolution:", text)
        self.assertIn("new findings start at 3", result.text)
        self.assertIn("findings 1 and 2 carried open", result.text)
        self.assertIn("Read: .scratch/demo/PLAN-REVIEW.md, .scratch/demo/spec.md, .scratch/demo/issues/", result.lines)
        carried = self.read("carried-plan.md")
        self.assertIn("### 1. major (open): Implementation Decisions", carried)
        self.assertIn("### 2. minor (open): Ticket 02", carried)

    def test_a_second_start_in_round_two_keeps_the_file_and_the_carried_blocks(self):
        """The carried blocks live in the tool-owned carried-plan.md, and a
        second start leaves both files."""
        first = self.round_two()
        self.put("PLAN-REVIEW.md", self.read("PLAN-REVIEW.md").replace("(open): Ticket 02", "(fixed): Ticket 02"))
        before = (self.snapshot(), self.read("carried-plan.md"))
        second = self.start()
        self.assertEqual(second.code, 0, second)
        self.assertEqual((self.snapshot(), self.read("carried-plan.md")), before)
        self.assertEqual(second.lines[1:], first.lines[1:])


class LintTest(ReviewTest):
    """Every refusal of review check names the file, the line and the fix,
    exits non-zero, writes nothing and reruns the check."""

    def refused(self, text, *fragments):
        self.round_one(text)
        result = LoopRepoTest.refused(self, ("review", "check", "--role", "Plan-Reviewer", "--slug", "demo", "--write"),
                                  ("PLAN-REVIEW.md", "RECAP.md", "loop-state"), *fragments)
        self.assertFalse(self.exists("RECAP.md"))
        self.assertNext(result, "review check --role Plan-Reviewer --slug demo --write", "again")
        return result

    def test_a_severity_outside_the_three(self):
        """The severity is blocker, major or minor, in lower case."""
        self.refused(ROUND_1.replace("### 2. minor", "### 2. Minor"),
                     "PLAN-REVIEW.md line 15:", "the severity is blocker, major or minor, in lower case")

    def test_a_state_outside_the_three(self):
        """The state is open, fixed or accepted."""
        self.refused(ROUND_1.replace("minor (open)", "minor (rejected)"),
                     "PLAN-REVIEW.md line 15:", "the state is open, fixed or accepted")

    def test_a_closed_finding_without_a_resolution(self):
        """A fixed or accepted finding needs its Resolution: line."""
        self.round_two()
        text = self.read("PLAN-REVIEW.md").replace("major (open)", "major (fixed)")
        self.put("PLAN-REVIEW.md", text)
        before = self.snapshot()
        result = self.check()
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("finding 1 is fixed but has no Resolution: line", result.text)
        self.assertRegex(result.text, r"PLAN-REVIEW\.md line [0-9]+:")
        self.assertEqual(self.snapshot(), before)
        self.assertNext(result, "review check", "again")

    def test_a_missing_carried_finding_prints_its_block(self):
        """A carried finding the reviewer dropped is refused with its block,
        word for word, from carried-plan.md."""
        self.round_two()
        text = self.read("PLAN-REVIEW.md")
        head, tail = text.split("### 2. minor (open): Ticket 02")
        self.put("PLAN-REVIEW.md", head + "## New findings\n")
        self.put("PLAN-REVIEW.md", head.rstrip() + "\n\n## New findings\n")
        before = self.snapshot()
        result = self.check()
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("finding 2 was open at the start of round 2 and is missing", result.text)
        self.assertIn("### 2. minor (open): Ticket 02", result.lines)
        self.assertIn("Ticket 02 leaves `summary` out.", result.lines)
        self.assertEqual(self.snapshot(), before)

    def test_new_findings_that_skip_a_number(self):
        """New findings start at the printed number and run without gaps."""
        self.refused(ROUND_1.replace("### 2. minor", "### 3. minor"),
                     "PLAN-REVIEW.md line 15:", "finding 2 is numbered 3; new findings this round start at 1")

    def test_a_new_finding_under_open_findings(self):
        """A finding under ## Open findings must have been carried by the tool."""
        self.round_two()
        text = self.read("PLAN-REVIEW.md").replace(
            "## New findings", "### 3. minor (open): Ticket 01\n\nNew.\n\n## New findings")
        self.put("PLAN-REVIEW.md", text)
        result = self.check()
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("a finding under ## Open findings must have been carried by the tool", result.text)
        self.assertNext(result, "again")

    def test_an_unclosed_fence_or_comment_is_refused(self):
        """A fence left open turned every later line into prose, so a blocker
        after it was dropped from the counts, the state and the Doorbell."""
        tail = "\n### 3. blocker (open): Ticket 01\n\nTicket 01 deletes the database.\n"
        fenced = ROUND_1.replace("leaves `summary` out.", "leaves `summary` out:\n\n```python\nx = 1\n") + tail
        self.refused(fenced, "PLAN-REVIEW.md line 19:", "the code fence that opens here is never closed",
                     "Close it with a line holding ```.")
        self.box.cleanup()
        self.setUp()
        commented = ROUND_1.replace("leaves `summary` out.", "leaves `summary` out.\n\n<!-- a note") + tail
        self.refused(commented, "PLAN-REVIEW.md line 19:", "the comment that opens here is never closed")

    def test_a_round_one_finding_outside_new_findings_names_that_heading(self):
        """Round 1 has no ## Open findings, so the refusal names ## New
        findings alone."""
        result = self.refused(ROUND_1.replace("writing-for-agents: ran\n",
                                              "writing-for-agents: ran\n\n### 3. minor (open): Ticket 01\n\nX.\n"),
                              "a finding heading belongs under ## New findings.")
        self.assertNotIn("## Open findings", result.text)

    def test_an_unfilled_checks_line(self):
        """An unfilled Checks line is refused."""
        self.refused(ROUND_1.replace("writing-for-agents: ran", "writing-for-agents: " + WFA),
                     "PLAN-REVIEW.md line 7:", "is not filled in")


class NotNeededTest(ReviewTest):
    def test_writing_for_agents_not_needed_passes_in_round_one(self):
        """Prevents a skip recorded as ran: a reviewer with
        nothing for writing-for-agents to check could record only ran or did
        not resolve, and settled on ran. not needed, <reason> records the skip
        as a skip, its reason in the Recap."""
        value = "writing-for-agents: not needed, no Agent document changed this round"
        self.round_one(ROUND_1.replace("writing-for-agents: ran", value))
        result = self.check()
        self.assertEqual(result.code, 0, result)
        self.assertIn("| writing-for-agents not needed, no Agent document changed this round |", self.read("RECAP.md"))

    def test_not_needed_without_a_reason_is_refused(self):
        """Prevents a 'not needed' skip without a reason: the user sees why
        each check was skipped."""
        self.round_one(ROUND_1.replace("writing-for-agents: ran", "writing-for-agents: not needed,"))
        before = self.snapshot()
        result = self.check()
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("PLAN-REVIEW.md line 7:", result.text)
        self.assertIn("gives no reason", result.text)
        self.assertEqual(self.snapshot(), before)


class CheckTest(ReviewTest):
    def test_a_passing_round_one(self):
        """Replaces the Plan-Reviewer's hand-written "Round <n>" line and
        Doorbell and its counts of open findings, which could disagree with
        the findings file: the check writes the status line, the Doorbell and
        the state."""
        self.round_one()
        dry = self.check(write=False)
        self.assertEqual(dry.code, 0, dry)
        self.assertNext(dry, "--write")
        result = self.check()
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        text = self.read("PLAN-REVIEW.md")
        self.assertNotIn("<!--", text)
        self.assertTrue(text.startswith("# Plan review, round 1\n\nOpen: 0 blocker, 1 major, 1 minor.\n"), text)
        self.assertIn("VDD Plan-Reviewer: PLAN-REVIEW.md written, round 1: 0 blocker, 1 major, 1 minor. Read it.",
                      result.lines)
        self.assertEqual(result.last, "Next: End your turn with the Doorbell line above as your whole reply.")
        self.assertIn("plan 1 reviewed open 1,2 counts 0 1 1", self.read("loop-state"))

    def test_the_orchestrator_relays_round_one(self):
        """Replaces the Plan-Reviewer's Doorbell line, composed by hand, which
        could differ from what the check recorded: the relay rings the line
        the check recorded."""
        self.round_one()
        self.check()
        result = self.ring("Orchestrator")
        self.assertEqual(result.code, 0, result)
        self.assertIn("to: Planner VDD Plan-Reviewer: PLAN-REVIEW.md written, round 1: 0 blocker, 1 major, 1 minor. "
                      "Read it.", self.read("doorbells"))

    def test_round_two_signs_off_and_moves_both_findings_to_the_recap(self):
        """Replaces the literal "SIGNED OFF" first line the Plan-Reviewer
        wrote and its sign-off Doorbell, which could disagree with the
        findings file: the check writes both."""
        self.round_two()
        text = self.read("PLAN-REVIEW.md")
        text = text.replace("### 1. major (open)", "### 1. major (fixed)").replace(
            "amounts are written.", "amounts are written.\n\nResolution: Implementation Decisions now say two decimals.")
        text = text.replace("### 2. minor (open)", "### 2. minor (accepted)").replace(
            "leaves `summary` out.", "leaves `summary` out.\n\nResolution: accepted the Planner's pushback.")
        text = text.replace("writing-for-agents: " + WFA, "writing-for-agents: ran")
        self.put("PLAN-REVIEW.md", text)
        result = self.check()
        self.assertEqual(result.code, 0, result)
        self.assertIn("VDD Plan-Reviewer: PLAN-REVIEW.md SIGNED OFF, round 2.", result.lines)
        review = self.read("PLAN-REVIEW.md")
        self.assertIn("\nSIGNED OFF. Nothing open.\n", review)
        self.assertNotIn("###", review)
        recap = self.read("RECAP.md")
        findings = recap.split("## Plan findings")[1].split("## Code findings")[0]
        self.assertIn("### 1. major, fixed in round 2: Implementation Decisions", findings)
        self.assertIn("Problem: The Spec does not say how amounts are written.", findings)
        self.assertIn("Resolution: Implementation Decisions now say two decimals.", findings)
        self.assertIn("### 2. minor, accepted in round 2: Ticket 02", findings)
        self.assertIn("Resolution: accepted the Planner's pushback.", findings)
        self.assertIn("| plan | 1 | 2 | 0 | 0 blocker, 1 major, 1 minor | writing-for-agents ran |", recap)
        self.assertIn("| plan | 2 | 0 | 2 | SIGNED OFF | writing-for-agents ran |", recap)
        self.assertIn("Plan Loop: 2 rounds, signed off in round 2.", recap)
        self.assertIn("plan 2 reviewed signed-off -", self.read("loop-state"))

    def test_a_second_check_after_the_write_reprints_the_doorbell(self):
        self.round_one()
        self.check()
        before = self.snapshot()
        again = self.check()
        self.assertEqual(again.code, 0, again)
        self.assertIn("already recorded", again.text)
        self.assertIn("VDD Plan-Reviewer: PLAN-REVIEW.md written, round 1: 0 blocker, 1 major, 1 minor. Read it.",
                      again.lines)
        self.assertEqual(self.snapshot(), before)

    def test_a_finding_line_that_reads_like_a_status_line_stays(self):
        """The write dropped every line starting "Open: " or "SIGNED OFF."
        anywhere in the file, a finding's prose included."""
        self.round_one(ROUND_1.replace("amounts are written.",
                                       "amounts are written.\nOpen: question whether locale matters."))
        result = self.check()
        self.assertEqual(result.code, 0, result)
        text = self.read("PLAN-REVIEW.md")
        self.assertIn("amounts are written.\nOpen: question whether locale matters.\n", text)
        self.assertEqual(text.count("Open: 0 blocker"), 1)

    def test_a_round_one_preamble_line_under_the_title_stays(self):
        """In round 1 no status line sits under the title yet, so the write
        dropped a preamble line there that started "Open: "."""
        preamble = "Open: the owner asked me to look at locale."
        self.round_one(ROUND_1.replace("round 1\n\n", "round 1\n\n%s\n\n" % preamble, 1))
        result = self.check()
        self.assertEqual(result.code, 0, result)
        text = self.read("PLAN-REVIEW.md")
        self.assertIn(preamble + "\n", text)
        self.assertEqual(text.count("Open: 1 blocker"), 0)
        self.assertEqual(text.count("Open: 0 blocker, 1 major, 1 minor."), 1)

    def test_a_fenced_heading_in_a_finding_is_prose(self):
        """A finding that quotes Markdown is never read as frame."""
        text = ROUND_1.replace("Ticket 02 leaves `summary` out.",
                               "Ticket 02 leaves `summary` out:\n\n```\n### 9. Bad (x): y\n## Notes\n```")
        self.round_one(text)
        result = self.check()
        self.assertEqual(result.code, 0, result)

    def fenced_finding(self, quoted):
        """Round 1 with quoted lines in finding 2 and a blocker after them,
        checked: the blocker counts only if the quote closed where Markdown
        closes it."""
        tail = "\n### 3. blocker (open): Ticket 01\n\nTicket 01 deletes the database.\n"
        self.round_one(ROUND_1.replace("leaves `summary` out.", "leaves `summary` out:\n\n" + quoted) + tail)
        result = self.check()
        self.assertEqual(result.code, 0, result)
        self.assertIn("VDD Plan-Reviewer: PLAN-REVIEW.md written, round 1: 1 blocker, 1 major, 1 minor. Read it.",
                      result.lines)

    def test_a_tilde_fence_quoting_a_backtick_line_closes_on_its_tildes(self):
        """Any backtick or tilde line closed a fence, so a ~~~ fence quoting
        ``` was refused as unclosed at its closing ~~~."""
        self.fenced_finding("~~~md\n```\n~~~")

    def test_a_four_backtick_fence_holds_a_three_backtick_block(self):
        """The inner ``` closed a ```` fence, so the quoted ### line inside it
        was read as a finding."""
        self.fenced_finding("````md\n```sh\n### 9. x (open): y\n```\n````")

    def test_a_four_space_indented_backtick_line_opens_no_fence(self):
        """An indented ``` line, an indented code block in Markdown, was
        refused as an unclosed fence."""
        self.fenced_finding("    ```")


class FencedRecapTest(ReviewTest):
    def test_a_fenced_heading_in_the_recap_survives_the_next_write(self):
        """The Recap's reader took a "##" line inside a closed finding's fence
        for a section heading, so the next write put finding 2 inside finding
        1's fence and finding 1's Resolution under ## Not carried."""
        quoted = "The Recap template should read:\n\n```markdown\n## Tickets\n\n## Not carried\n```"
        self.round_two()
        text = self.read("PLAN-REVIEW.md").replace("writing-for-agents: " + WFA,
                                                   "writing-for-agents: ran")
        text = text.replace("The Spec does not say how amounts are written.", quoted)
        text = text.replace("### 1. major (open)", "### 1. major (fixed)").replace(
            "## Not carried\n```", "## Not carried\n```\n\nResolution: the Spec names both headings.")
        self.put("PLAN-REVIEW.md", text)
        self.assertEqual(self.check().code, 0)
        self.ring()
        self.assertEqual(self.start().code, 0)
        text = self.read("PLAN-REVIEW.md").replace("writing-for-agents: " + WFA,
                                                   "writing-for-agents: ran")
        text = text.replace("### 2. minor (open)", "### 2. minor (fixed)").replace(
            "leaves `summary` out.", "leaves `summary` out.\n\nResolution: added.")
        self.put("PLAN-REVIEW.md", text)
        result = self.check()
        self.assertEqual(result.code, 0, result)
        recap = self.read("RECAP.md")
        findings = recap.split("\n## Plan findings\n")[1].split("\n## Code findings\n")[0]
        self.assertIn("```\n\nResolution: the Spec names both headings.\n\n### 2. minor, fixed in round 3", findings)
        self.assertEqual(recap.split("\n## Not carried\n")[-1].strip(), "")


class LeaveTest(ReviewTest):
    minors = "leave"

    def test_open_minors_sign_off_on_leave_and_stay(self):
        """Prevents open minors blocking a sign-off or dropped from the file:
        the check signs off and keeps the minors in the file."""
        self.round_one(ROUND_1.replace("### 1. major", "### 1. minor"))
        result = self.check()
        self.assertEqual(result.code, 0, result)
        review = self.read("PLAN-REVIEW.md")
        self.assertIn("\nSIGNED OFF. Open minors left, as Minors: leave allows: 2.\n", review)
        self.assertIn("### 1. minor (open)", review)
        self.assertIn("### 2. minor (open)", review)
        self.assertIn("VDD Plan-Reviewer: PLAN-REVIEW.md SIGNED OFF, round 1.", result.lines)


if __name__ == "__main__":
    unittest.main()
