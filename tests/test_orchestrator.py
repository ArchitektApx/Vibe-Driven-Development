"""The orchestrator command group, driven from outside: the Orchestrator
acting on tool output (Ticket 07)."""

import os
import re
import subprocess
import unittest

from vddtest import REPO, ToolTest

P1 = "VDD Planner: .scratch/demo/ ready, round 1. Read spec.md and issues/."
P2 = "VDD Planner: .scratch/demo/ ready, round 2. Read spec.md and issues/."
PLAN_OPEN_1 = "plan 1 reviewed open 1,2 counts 0 1 1 next 3 new 2 closed 0 checks writing-for-agents ran"
PLAN_SIGNED_2 = "plan 2 reviewed signed-off - counts 0 0 0 next 3 new 0 closed 2 checks writing-for-agents ran"
CODE_OPEN_1 = "code 1 reviewed open 1 counts 0 1 0 next 2 new 1 closed 0 checks code-review ran"
CODE_SIGNED_2 = "code 2 reviewed signed-off - counts 0 0 0 next 2 new 0 closed 1 checks code-review ran"


class OrchestratorTest(ToolTest):
    pr = "ask at sign-off"

    def setUp(self):
        ToolTest.setUp(self)
        self.box.init_git("main")
        self.box.write_loop("demo", text=(
            "# VDD Loop\n\nFormat: 2\nFeature: demo\nBase branch: main\nFeature branch: demo\nMinors: fix\n"
            "PR: %s\nHarness: Claude Code\n" % self.pr), extra=self.policies())
        self.box.write(os.path.join(".scratch", "demo", "spec.md"), "# Spec\n")
        self.box.write(os.path.join(".scratch", "demo", "issues", "01-one.md"), "# 01\n")

    def policies(self):
        """The Coder's Respawn policy set, so start places at once."""
        return ("respawn Coder never",)

    def stage(self, *lines):
        with open(self.box.path(".scratch", "demo", "loop-state"), "a") as handle:
            handle.write("".join(line + "\n" for line in lines))

    def rings(self, *lines):
        path = self.box.path(".scratch", "demo", "doorbells")
        new = not os.path.exists(path)
        with open(path, "a") as handle:
            if new:
                handle.write("# vdd doorbells 1\n")
            for line in lines:
                handle.write("10:00:00 to: Orchestrator %s\n" % line)

    def orch(self, *args):
        return self.box.run("orchestrator", *args)

    def start(self):
        return self.orch("start", "--slug", "demo", "--harness", "claude-code")

    def back(self, role, *extra):
        return self.orch("return", "--role", role, "--slug", "demo", "--harness", "claude-code", *extra)

    def state(self):
        return self.box.read(os.path.join(".scratch", "demo", "loop-state"))

    def files(self):
        """Every file under .scratch/demo/ but the state file, and git's
        HEAD and branches."""
        out = {}
        base = self.box.path(".scratch", "demo")
        for directory, _, names in os.walk(base):
            for name in names:
                path = os.path.join(directory, name)
                if name == "loop-state":
                    continue
                with open(path, "rb") as handle:
                    out[os.path.relpath(path, base)] = handle.read()
        git = subprocess.run(["git", "show-ref", "--head"], cwd=self.box.proj, stdout=subprocess.PIPE)
        out["git"] = git.stdout
        return out

    def spawned(self, result, role, number, reason=None):
        line = "Spawning %s, <model>, round %d%s." % (role, number, ", " + reason if reason else "")
        self.assertIn(line, result.lines, result)


class HelpTest(OrchestratorTest):
    def test_help_teaches_start_and_return(self):
        result = self.orch("--help")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("orchestrator start", result.text)
        self.assertIn("orchestrator return", result.text)
        self.assertIn("It takes no return line", result.text)


class PlacementTest(OrchestratorTest):
    """orchestrator start places the Workflow from the state file and the
    Doorbell file, replacing restart.md's five states and the
    parse-and-resume-once rule (ticket 72, "placement after a crash")."""

    def test_nothing_rung_waits_for_the_planner(self):
        result = self.start()
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("Harness: Claude Code", result.lines[0])
        self.assertIn("harness-claude-code.md", result.lines[0])
        self.assertNext(result, "doorbell wait --role Orchestrator --harness claude-code --slug demo")
        self.assertIn("orchestrator session 1", self.state())

    def test_a_rung_round_with_no_review_spawns_the_plan_reviewer(self):
        """restart.md's first state: a fresh Plan-Reviewer answers the
        Planner's Doorbell, since one an earlier Session spawned is gone."""
        self.rings(P1)
        result = self.start()
        self.spawned(result, "Plan-Reviewer", 1)
        self.assertIn("Read: .scratch/demo/spec.md, .scratch/demo/issues/", result.lines)
        self.assertIn("Write: .scratch/demo/PLAN-REVIEW.md", result.lines)
        restarted = self.start()
        self.spawned(restarted, "Plan-Reviewer", 1, "after a restart")

    def test_reviewed_open_with_no_new_ring_relays_then_waits(self):
        """restart.md's second state, and plan review round 1, finding 1: an
        Orchestrator that died after the review and before the relay rings
        it on the restart, then waits for the Planner."""
        self.rings(P1)
        self.stage(PLAN_OPEN_1)
        result = self.start()
        self.assertEqual(result.code, 0, result)
        self.assertNext(result, "doorbell ring --role Orchestrator --harness claude-code --slug demo --write",
                        "wait for the Planner")
        self.assertNotIn("Spawning", result.text)

    def test_reviewed_open_and_a_new_ring_spawns_for_that_round(self):
        self.rings(P1, P2)
        self.stage(PLAN_OPEN_1)
        result = self.start()
        self.spawned(result, "Plan-Reviewer", 2)
        self.assertIn("Read: .scratch/demo/PLAN-REVIEW.md, .scratch/demo/spec.md, .scratch/demo/issues/", result.lines)

    def test_a_signed_off_plan_relays_then_spawns_the_coder(self):
        """restart.md's third state, with the relay rung again so a lost
        SIGNED OFF does not leave the Planner waiting."""
        self.rings(P1, P2)
        self.stage(PLAN_OPEN_1, PLAN_SIGNED_2)
        result = self.start()
        self.spawned(result, "Coder", 1)
        self.assertIn("Write: .scratch/demo/FIXES.md, .scratch/demo/issues/ (the ticked checkboxes)", result.lines)
        self.assertNext(result, "doorbell ring --role Orchestrator", "spawn a fresh Coder")

    def signed_plan(self, *code):
        self.rings(P1, P2)
        self.stage(PLAN_OPEN_1, PLAN_SIGNED_2, *code)

    def test_a_coder_round_started_and_not_ended(self):
        """restart.md's fourth state, the Coder owing the answer."""
        self.signed_plan("code 1 start aaa")
        self.spawned(self.start(), "Coder", 1)

    def test_a_coder_round_ended_and_not_reviewed(self):
        """restart.md's fourth state, the Code-Reviewer owing the review."""
        self.signed_plan("code 1 start aaa", "code 1 end bbb")
        result = self.start()
        self.spawned(result, "Code-Reviewer", 1)
        self.assertIn("Read: .scratch/demo/spec.md, .scratch/demo/issues/, .scratch/demo/FIXES.md", result.lines)

    def test_a_code_round_reviewed_open(self):
        self.signed_plan("code 1 start aaa", "code 1 end bbb", CODE_OPEN_1)
        result = self.start()
        self.spawned(result, "Coder", 2)
        self.assertIn("Read: .scratch/demo/CODEREVIEW.md, .scratch/demo/spec.md, .scratch/demo/issues/", result.lines)

    def test_a_signed_off_code_loop_goes_to_the_pr_step(self):
        """restart.md's fifth state: the Loop is over."""
        self.signed_plan("code 1 start a", "code 1 end b", CODE_OPEN_1, "code 2 start b", "code 2 end c",
                         CODE_SIGNED_2)
        result = self.start()
        self.assertNext(result, "vdd-create-pr", "own Session")
        self.assertNotIn("Spawning", result.text)

    def test_start_changes_no_doorbell_working_file_or_git(self):
        """The Orchestrator's Doorbell state file aside, which start records
        the rung Doorbells in (code review round 4, finding 10)."""
        self.signed_plan("code 1 start aaa")
        before = self.files()
        before.pop("doorbell-state-orchestrator", None)
        self.start()
        after = self.files()
        after.pop("doorbell-state-orchestrator", None)
        self.assertEqual(after, before)

    def test_the_relay_after_a_placed_review_names_the_wait(self):
        """Code review round 4, finding 10, replacing beta's take --restart,
        which recorded the Doorbells a start acted on as handled: start
        spawns the Plan-Reviewer for the rung round, so the relay after its
        review names the wait, not the Planner's round 1 Doorbell again."""
        def db(*argv):
            return self.box.run("doorbell", *argv, "--harness", "claude-code", "--slug", "demo")
        db("ring", "--role", "Planner", "--write")
        self.spawned(self.start(), "Plan-Reviewer", 1)
        self.box.run("review", "start", "--role", "Plan-Reviewer", "--slug", "demo", "--write")
        self.box.write(os.path.join(".scratch", "demo", "PLAN-REVIEW.md"),
                       "# Plan review, round 1\n\n## Checks\n\nwriting-for-agents: ran\n\n## New findings\n\n"
                       "### 1. major (open): Implementation Decisions\n\nAmounts are unspecified.\n")
        checked = self.box.run("review", "check", "--role", "Plan-Reviewer", "--slug", "demo", "--write")
        self.assertEqual(checked.code, 0, checked)
        self.assertNext(self.back("Plan-Reviewer"), "doorbell ring --role Orchestrator")
        relay = db("ring", "--role", "Orchestrator", "--write")
        self.assertEqual(relay.code, 0, relay)
        self.assertNotIn("already waiting", relay.last)
        self.assertNext(relay, "doorbell wait --role Orchestrator")
        db("take", "--role", "Planner")
        db("ring", "--role", "Planner", "--write")
        took = db("take", "--role", "Orchestrator")
        self.assertIn("Doorbell: " + P2, took.lines)
        resumed = self.back("Planner")
        self.assertEqual(resumed.code, 0, resumed)
        self.assertIn("Resuming Plan-Reviewer, round 2.", resumed.lines)


class ReturnTest(OrchestratorTest):
    def live(self, *lines):
        self.stage("orchestrator session 1", *lines)

    def test_after_the_coder_the_code_reviewer_spawns_and_a_repeat_refuses(self):
        """Ticket 72, a repeat Doorbell for a round already acted on."""
        self.live("spawn Coder 1 session 1", "code 1 start a", "code 1 end b")
        before = self.files()
        result = self.back("Coder")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.spawned(result, "Code-Reviewer", 1)
        self.assertIn("Read: .scratch/demo/spec.md, .scratch/demo/issues/, .scratch/demo/FIXES.md", result.lines)
        self.assertIn("Write: .scratch/demo/CODEREVIEW.md", result.lines)
        self.assertNext(result, "Spawn prompt",
                        "orchestrator return --role Code-Reviewer --slug demo --harness claude-code")
        self.assertEqual(self.files(), before)
        again = self.back("Coder")
        self.assertNotEqual(again.code, 0, again)
        self.assertEqual(again.last,
                         "Next: Nothing to do for this return; go on with the step the tool printed before it.")

    def test_a_live_code_reviewer_is_resumed_with_the_coder_s_doorbell(self):
        self.live("spawn Coder 1 session 1", "code 1 start a", "code 1 end b", "return Coder 1 ok",
                  "spawn Code-Reviewer 1 session 1", CODE_OPEN_1, "return Code-Reviewer 1 ok",
                  "resume Coder 2 session 1", "code 2 start b", "code 2 end c")
        result = self.back("Coder")
        self.assertEqual(result.code, 0, result)
        self.assertIn("Resuming Code-Reviewer, round 2.", result.lines)
        index = result.lines.index("Resume message:")
        self.assertEqual(result.lines[index + 1], "VDD Coder: FIXES.md written, round 2. Read it.")
        self.assertNext(result, "as the whole message",
                        "orchestrator return --role Code-Reviewer --slug demo --harness claude-code")

    def test_a_round_with_no_check_resumes_once_then_asks_the_user(self):
        """Ticket 72 and unmatched-return.md's rule: one fixed resume, then
        the user. The fixed text is the tool's, so the Orchestrator adds no
        words of its own to a recovery."""
        self.live("spawn Coder 1 session 1", "code 1 start a")
        first = self.back("Coder")
        self.assertEqual(first.code, 0, first)
        index = first.lines.index("Resume message:")
        self.assertEqual(first.lines[index + 1],
                         "Round 1 is not finished: `coder check --slug demo --write` has not passed. Run it, fix "
                         "what it reports until it passes, then end your turn with the line it prints.")
        second = self.back("Coder")
        self.assertEqual(second.code, 0, second)
        self.assertNotIn("Spawning", second.text)
        self.assertNotIn("Resume message:", second.lines)
        tell = second.tells()[0]
        for word in ("resume", "respawn", "stop"):
            self.assertIn(word, tell)
        self.assertEqual(self.state().count("return Coder 1 miss"), 2)

    def test_a_return_line_argument_is_refused(self):
        """Ticket 61, the DOORBELL: Doorbell: return: the tool never reads
        the return's text, so it takes none."""
        self.live("spawn Coder 1 session 1")
        result = self.back("Coder", "--line", "DOORBELL: Doorbell: VDD Coder: FIXES.md written, round 1. Read it.")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("Unknown option: --line", result.text)

    def test_the_planner_s_doorbell_spawns_then_resumes_the_plan_reviewer(self):
        ring = self.box.run("doorbell", "ring", "--role", "Planner", "--harness", "claude-code", "--slug", "demo",
                            "--write")
        self.assertEqual(ring.code, 0, ring)
        self.stage("orchestrator session 1")
        took = self.box.run("doorbell", "take", "--role", "Orchestrator", "--harness", "claude-code", "--slug", "demo")
        self.assertIn("Doorbell: " + P1, took.lines)
        self.assertNext(took, "orchestrator return --role Planner --slug demo --harness claude-code")
        first = self.back("Planner")
        self.assertEqual(first.code, 0, first)
        self.spawned(first, "Plan-Reviewer", 1)
        self.assertIn("Read: .scratch/demo/spec.md, .scratch/demo/issues/", first.lines)
        self.assertIn("Write: .scratch/demo/PLAN-REVIEW.md", first.lines)
        self.assertNotEqual(self.back("Planner").code, 0)
        self.stage(PLAN_OPEN_1, "return Plan-Reviewer 1 ok")
        self.rings(P2)
        second = self.back("Planner")
        self.assertIn("Resuming Plan-Reviewer, round 2.", second.lines)
        index = second.lines.index("Resume message:")
        self.assertEqual(second.lines[index + 1], P2)

    def test_after_the_plan_reviewer_ring_then_wait_or_the_coder(self):
        self.rings(P1)
        self.live("spawn Plan-Reviewer 1 session 1", PLAN_OPEN_1)
        result = self.back("Plan-Reviewer")
        self.assertNext(result, "doorbell ring --role Orchestrator --harness claude-code --slug demo --write",
                        "wait for the Planner")
        self.rings(P2)
        self.stage("resume Plan-Reviewer 2 session 1", PLAN_SIGNED_2)
        result = self.back("Plan-Reviewer")
        self.spawned(result, "Coder", 1)
        self.assertNext(result, "doorbell ring --role Orchestrator", "spawn a fresh Coder")

    def test_no_return_changes_a_doorbell_or_working_file(self):
        self.rings(P1)
        self.live("spawn Plan-Reviewer 1 session 1", PLAN_OPEN_1)
        before = self.files()
        self.back("Plan-Reviewer")
        self.assertEqual(self.files(), before)


class PRStepTest(OrchestratorTest):
    pr = "no"

    def signed(self):
        self.stage("orchestrator session 1", "spawn Code-Reviewer 1 session 1", "code 1 start a", "code 1 end b",
                   "code 1 reviewed signed-off - counts 0 0 0")

    def test_pr_no_closes_the_loop_locally(self):
        self.signed()
        result = self.back("Code-Reviewer")
        self.assertNext(result, "loop close --slug demo --write", "stays local, nothing pushed")


class PRYesTest(PRStepTest):
    pr = "yes"

    def test_pr_no_closes_the_loop_locally(self):
        """Overridden: on PR: yes the PR step is the PR-Author."""
        self.test_any_other_pr_invokes_the_pr_author()

    def test_any_other_pr_invokes_the_pr_author(self):
        self.signed()
        result = self.back("Code-Reviewer")
        self.assertNext(result, "Invoke the vdd-create-pr skill in your own Session")
        self.assertNotIn("loop close", result.last)


class VersionOneTest(OrchestratorTest):
    def test_every_orchestrator_command_refuses_a_version_one_loop(self):
        self.box.write_loop("demo", version=1)
        for argv in (("start", "--slug", "demo"),
                     ("return", "--role", "Coder", "--slug", "demo", "--harness", "claude-code")):
            with self.subTest(argv=argv):
                result = self.orch(*argv)
                self.assertNotEqual(result.code, 0, result)
                self.assertIn("0.16.0-beta.3", result.text)


class SkillTextTest(OrchestratorTest):
    """Each hosted Role's Read and Write lists, as orchestrator return prints
    them, name only Working files that Role's SKILL.md names (Ticket 41's
    dry runs: an Orchestrator given no list missed a file in 5 of 9)."""

    CASES = (
        ("Plan-Reviewer", 1, ("orchestrator session 1",), "Planner"),
        ("Plan-Reviewer", 2, ("orchestrator session 1", PLAN_OPEN_1), "Planner"),
        ("Coder", 1, ("orchestrator session 1", "spawn Plan-Reviewer 2 session 1", PLAN_OPEN_1, PLAN_SIGNED_2),
         "Plan-Reviewer"),
        ("Coder", 2, ("orchestrator session 1", "spawn Code-Reviewer 1 session 1", CODE_OPEN_1), "Code-Reviewer"),
        ("Code-Reviewer", 1, ("orchestrator session 1", "spawn Coder 1 session 1", "code 1 start a",
                              "code 1 end b"), "Coder"),
        ("Code-Reviewer", 2, ("orchestrator session 1", "spawn Coder 2 session 1", CODE_OPEN_1, "code 2 start a",
                              "code 2 end b"), "Coder"),
    )

    # The Spec's table under Implementation Decisions, orchestrator return:
    # (role, round) -> (Read, Write), a parenthetical after a name dropped.
    TABLE = {
        ("Plan-Reviewer", 1): (["spec.md", "issues/"], ["PLAN-REVIEW.md"]),
        ("Plan-Reviewer", 2): (["PLAN-REVIEW.md", "spec.md", "issues/"], ["PLAN-REVIEW.md"]),
        ("Coder", 1): (["spec.md", "issues/"], ["FIXES.md", "issues/"]),
        ("Coder", 2): (["CODEREVIEW.md", "spec.md", "issues/"], ["FIXES.md", "issues/"]),
        ("Code-Reviewer", 1): (["spec.md", "issues/", "FIXES.md"], ["CODEREVIEW.md"]),
        ("Code-Reviewer", 2): (["CODEREVIEW.md", "spec.md", "issues/"], ["CODEREVIEW.md"]),
    }

    def test_every_listed_file_is_named_in_the_role_s_skill(self):
        """Each list also equals its row of the Spec's table, so a later
        round's file listed in round 1, or a missing FIXES.md, fails (code
        review round 4, finding 21)."""
        for role, number, lines, after in self.CASES:
            with self.subTest(role=role, round=number):
                self.box.write_loop("demo", extra=self.policies() + lines)
                if os.path.exists(self.box.path(".scratch", "demo", "doorbells")):
                    os.remove(self.box.path(".scratch", "demo", "doorbells"))
                self.rings(*([P1] if number == 1 else [P1, P2]))
                result = self.back(after)
                self.spawned(result, role, number)
                with open(os.path.join(REPO, "skills", "vdd-" + role.lower(), "SKILL.md"), encoding="utf-8") as f:
                    skill = f.read()
                for prefix, expected in zip(("Read: ", "Write: "), self.TABLE[(role, number)]):
                    listed = [l for l in result.lines if l.startswith(prefix)][0][len(prefix):]
                    names = [re.sub(r" \(.*\)$", "", item)[len(".scratch/demo/"):] for item in listed.split(", ")]
                    self.assertEqual(names, expected, "%s round %d, %s" % (role, number, prefix.strip()))
                    for name in names:
                        self.assertTrue(name in skill, "%s round %d: %s is not in its SKILL.md" % (role, number, name))


if __name__ == "__main__":
    unittest.main()
