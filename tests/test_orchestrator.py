"""The orchestrator command group, driven from outside: the Orchestrator acting
on tool output."""

import os
import re
import subprocess
import unittest

from vddtest import PLAN_SIGNED, PLAN_SIGNED_2, CODE_SIGNED_2, REPO, LoopRepoTest, SceneTest, tool_command

P1 = "VDD Planner: .scratch/demo/ ready, round 1. Read spec.md and issues/."
P2 = "VDD Planner: .scratch/demo/ ready, round 2. Read spec.md and issues/."
PLAN_OPEN_1 = "plan 1 reviewed open 1,2 counts 0 1 1 next 3 new 2 closed 0 checks writing-for-agents ran"
CODE_OPEN_1 = "code 1 reviewed open 1 counts 0 1 0 next 2 new 1 closed 0 checks code-review ran"


class OrchestratorTest(SceneTest):
    pr = "ask at sign-off"

    def stage_scene(self):
        self.box.init_git("main")
        self.box.write_loop("demo", text=(
            "# VDD Loop\n\nFormat: 2\nFeature: demo\nBase branch: main\nFeature branch: demo\nMinors: fix\n"
            "PR: %s\nHarness: Claude Code\n" % self.pr), extra=self.policies())
        self.box.write(os.path.join(".scratch", "demo", "spec.md"), "# Spec\n")
        self.box.write(os.path.join(".scratch", "demo", "issues", "01-one.md"), "# 01\n")

    def policies(self):
        """The Coder's Respawn policy set, so start places at once."""
        return ("respawn Coder never",)

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
    Doorbell file after a crash: five states, from a rung Planner Doorbell with
    no review to a signed-off code loop."""

    def test_nothing_rung_waits_for_the_planner(self):
        result = self.start()
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("Harness: Claude Code", result.lines[0])
        self.assertIn("harness-claude-code.md", result.lines[0])
        self.assertNext(result, "doorbell wait --role Orchestrator --harness claude-code --slug demo")
        self.assertIn("orchestrator session 1", self.state())

    def test_a_stray_line_while_the_planner_is_owed_starts_the_wait_before_the_relay(self):
        """Prevents a Tell the user never reads, or a wait that never starts,
        on a start that owes the Planner's wait: the Tell about a stray line
        in the Doorbell file came before the wait, and a Next: that names the
        relay first lost the wait or the Tell."""
        relay_last = "holds every Tell the user verbatim line above, unchanged"
        for label, name in (("Claude Code", "claude-code"), ("Codex", "codex")):
            with self.subTest(harness=name):
                self.box.write_loop("demo", text=(
                    "# VDD Loop\n\nFormat: 2\nFeature: demo\nBase branch: main\nFeature branch: demo\n"
                    "Minors: fix\nPR: ask at sign-off\nHarness: %s\n" % label), extra=self.policies())
                self.rings("not a doorbell")
                result = self.orch("start", "--slug", "demo", "--harness", name)
                self.assertEqual(result.code, 0, result)
                self.assertIn("is not a Doorbell", result.text)
                self.assertFalse(result.last.startswith("Next: Relay"), result.last)
                wait = "doorbell wait --role Orchestrator --harness %s" % name
                self.assertNext(result, wait, relay_last)
                self.assertLess(result.last.index(wait), result.last.index(relay_last))

    def test_a_rung_round_with_no_review_spawns_the_plan_reviewer(self):
        """A fresh Plan-Reviewer answers the Planner's Doorbell, since one an
        earlier Session spawned is gone."""
        self.rings(P1)
        result = self.start()
        self.spawned(result, "Plan-Reviewer", 1)
        self.assertIn("Read: .scratch/demo/spec.md, .scratch/demo/issues/", result.lines)
        self.assertIn("Write: .scratch/demo/PLAN-REVIEW.md", result.lines)
        restarted = self.start()
        self.spawned(restarted, "Plan-Reviewer", 1, "after a restart")

    def test_reviewed_open_with_no_new_ring_relays_then_waits(self):
        """An Orchestrator that died after the review and before the relay
        rings it on the restart, then waits for the Planner."""
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
        """The plan is signed off: the relay is rung again so a lost SIGNED OFF
        does not leave the Planner waiting, then a Coder spawns."""
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
        """The Coder owes the answer."""
        self.signed_plan("code 1 start aaa")
        self.spawned(self.start(), "Coder", 1)

    def test_a_coder_round_ended_and_not_reviewed(self):
        """The Code-Reviewer owes the review."""
        self.signed_plan("code 1 start aaa", "code 1 end bbb")
        result = self.start()
        self.spawned(result, "Code-Reviewer", 1)
        self.assertIn("Read: .scratch/demo/spec.md, .scratch/demo/issues/, .scratch/demo/FIXES.md", result.lines)

    def test_a_code_round_reviewed_open(self):
        self.signed_plan("code 1 start aaa", "code 1 end bbb", CODE_OPEN_1)
        result = self.start()
        self.spawned(result, "Coder", 2)
        self.assertIn("Read: .scratch/demo/CODEREVIEW.md, .scratch/demo/spec.md, .scratch/demo/issues/", result.lines)

    def test_a_signed_off_code_loop_goes_to_the_fold_then_the_pr_step(self):
        """The Loop is over: the fold first, the PR step once its outcome is
        recorded."""
        self.signed_plan("code 1 start a", "code 1 end b", CODE_OPEN_1, "code 2 start b", "code 2 end c",
                         CODE_SIGNED_2)
        result = self.start()
        self.assertNext(result, "loop fold --slug demo --harness claude-code --write")
        self.assertNotIn("Spawning", result.text)
        self.stage("fold skipped c the branch moved after Sign-off")
        result = self.start()
        self.assertNext(result, "vdd-create-pr", "own Session")

    def test_a_restart_names_no_ring_once_the_planner_took_the_sign_off(self):
        """A restarted Orchestrator rang the plan Sign-off again after the
        Planner had taken it, and relayed a paste line into a Planner Session
        that had long finished."""
        self.signed_plan("code 1 start a", "code 1 end b", CODE_OPEN_1, "code 2 start b", "code 2 end c",
                         CODE_SIGNED_2, "fold skipped c the branch moved after Sign-off")
        ring = ("doorbell", "ring", "--role", "Orchestrator", "--harness", "claude-code", "--slug", "demo")
        self.box.run(*ring, "--write")
        rung = self.start()
        self.assertIn("First: ", rung.text)
        self.assertIn("doorbell ring --role Orchestrator", rung.text)
        took = self.box.run("doorbell", "take", "--role", "Planner", "--harness", "claude-code", "--slug", "demo")
        self.assertEqual(took.code, 0, took)
        result = self.start()
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertNotIn("First: ", result.text)
        self.assertNotIn("doorbell ring", result.text)
        self.assertNext(result, "vdd-create-pr", "own Session")

    def test_a_restart_in_the_code_loop_spawns_with_no_ring_once_taken(self):
        """Prevents the ring dropped while the Planner has not taken the
        Sign-off, and kept once it has."""
        self.signed_plan("code 1 start aaa")
        self.box.run("doorbell", "ring", "--role", "Orchestrator", "--harness", "claude-code", "--slug", "demo",
                     "--write")
        self.assertNext(self.start(), "doorbell ring --role Orchestrator", "spawn a fresh Coder")
        self.box.run("doorbell", "take", "--role", "Planner", "--harness", "claude-code", "--slug", "demo")
        result = self.start()
        self.spawned(result, "Coder", 1, "after a restart")
        self.assertNotIn("doorbell ring", result.text)

    def test_a_later_plan_sign_off_is_rung_after_an_earlier_one_was_taken(self):
        """Prevents a Planner left waiting on a later plan round's Sign-off
        because it had taken an earlier round's."""
        self.signed_plan()
        ring = ("doorbell", "ring", "--role", "Orchestrator", "--harness", "claude-code", "--slug", "demo")
        self.box.run(*ring, "--write")
        self.box.run("doorbell", "take", "--role", "Planner", "--harness", "claude-code", "--slug", "demo")
        self.rings("VDD Planner: .scratch/demo/ ready, round 3. Read spec.md and issues/.")
        self.stage("plan 3 reviewed signed-off - counts 0 0 0 next 3 new 0 closed 0 checks writing-for-agents ran")
        result = self.start()
        self.assertEqual(result.code, 0, result)
        self.assertIn("Plan Loop: signed off in round 3", result.text)
        self.spawned(result, "Coder", 1)
        self.assertNext(result, "doorbell ring --role Orchestrator", "spawn a fresh Coder")

    def test_start_changes_no_doorbell_working_file_or_git(self):
        """Start changes no Working file and no git ref. Of the Doorbell files
        it writes only the Orchestrator's state file, where it records the
        rung Doorbells as handled."""
        self.signed_plan("code 1 start aaa")
        before = self.files()
        before.pop("doorbell-state-orchestrator", None)
        self.start()
        after = self.files()
        after.pop("doorbell-state-orchestrator", None)
        self.assertEqual(after, before)

    def test_the_relay_after_a_placed_review_names_the_wait(self):
        """Start spawns the Plan-Reviewer for the rung round, so the relay
        after its review names the wait, not the Planner's round 1 Doorbell
        again."""
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
        """A repeat Doorbell for a round already acted on is refused."""
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
        """One fixed resume, then the user. The fixed text is the tool's, so
        the Orchestrator adds no words of its own to a recovery."""
        self.live("spawn Coder 1 session 1", "code 1 start a")
        first = self.back("Coder")
        self.assertEqual(first.code, 0, first)
        index = first.lines.index("Resume message:")
        self.assertEqual(first.lines[index + 1],
                         "Round 1 is not finished: `%s coder check --slug demo --write` has not passed. Run it, fix "
                         "what it reports until it passes, then end your turn with the line it prints."
                         % tool_command())
        second = self.back("Coder")
        self.assertEqual(second.code, 0, second)
        self.assertNotIn("Spawning", second.text)
        self.assertNotIn("Resume message:", second.lines)
        self.assertIn("Coder round 1 ended without `coder check --slug demo --write` a second time.", second.lines)
        tell = second.tells()[0]
        for word in ("resume", "respawn", "stop"):
            self.assertIn(word, tell)
        self.assertEqual(self.state().count("return Coder 1 miss"), 2)

    def test_a_review_round_with_no_check_resumes_with_the_tool_s_check(self):
        """Prevents a resume message naming review check without the tool's
        path, which a hosted Role cannot run as written."""
        self.live("spawn Coder 1 session 1", "code 1 start a", "code 1 end b", "return Coder 1 ok",
                  "spawn Code-Reviewer 1 session 1")
        result = self.back("Code-Reviewer")
        self.assertEqual(result.code, 0, result)
        index = result.lines.index("Resume message:")
        self.assertEqual(result.lines[index + 1],
                         "Round 1 is not finished: `%s review check --role Code-Reviewer --slug demo --write` has "
                         "not passed. Run it, fix what it reports until it passes, then end your turn with the line "
                         "it prints." % tool_command())
        self.assertIn("Code-Reviewer round 1 ended without `review check --role Code-Reviewer --slug demo --write`: "
                      "the round is not finished.", result.lines)

    def test_a_return_line_argument_is_refused(self):
        """The tool never reads the return's text, so return takes no --line."""
        self.live("spawn Coder 1 session 1")
        result = self.back("Coder", "--line", "DOORBELL: Doorbell: VDD Coder: FIXES.md written, round 1. Read it.")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("Unknown option: --line", result.text)

    def test_start_return_and_tokens_refuse_write(self):
        """Only respawn writes, so the other three refuse --write rather than
        ignore it."""
        self.live("spawn Coder 1 session 1", "code 1 start a", "code 1 end b")
        before = (self.files(), self.state())
        for argv in (("start", "--slug", "demo", "--write"),
                     ("return", "--role", "Coder", "--slug", "demo", "--harness", "claude-code", "--write"),
                     ("tokens", "--role", "Coder", "--tokens", "1000", "--slug", "demo", "--write")):
            with self.subTest(argv[0]):
                result = self.orch(*argv)
                self.assertNotEqual(result.code, 0, result)
                self.assertIn("Unknown option: --write", result.text)
        self.assertEqual((self.files(), self.state()), before)

    def test_a_planner_doorbell_naming_the_wrong_tracker_is_not_acted_on(self):
        """A Doorbell naming the wrong tracker: a Planner line naming
        .scratch/other/ in demo's Doorbell file is no Doorbell for demo, so
        neither take nor return acts on it."""
        self.rings("VDD Planner: .scratch/other/ ready, round 1. Read spec.md and issues/.")
        self.stage("orchestrator session 1")
        took = self.box.run("doorbell", "take", "--role", "Orchestrator", "--harness", "claude-code", "--slug", "demo")
        self.assertIn("is not a Doorbell, so it was not acted on", took.text)
        self.assertNotIn("Doorbell: VDD Planner", took.text)
        self.assertNotIn("orchestrator return --role Planner", took.text)
        before = self.state()
        result = self.back("Planner")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("there is nothing to act on", result.text)
        self.assertNotIn("Spawning", result.text)
        self.assertEqual(self.state(), before)

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


USER_2 = "code 2 user open 13,14 counts 0 1 1 next 15 new 2"
USER_REASON = "for the user's findings"


class UserFindingsTest(OrchestratorTest):
    """The loop reopened by review add: the reopened round spawns fresh, with
    no plan ring and no restart label."""

    def earlier_session(self):
        self.rings(P1, P2)
        self.stage(PLAN_OPEN_1, PLAN_SIGNED_2, "orchestrator session 1", "spawn Coder 1 session 1",
                   "code 1 start a", "code 1 end b", "return Coder 1 ok", "spawn Code-Reviewer 1 session 1",
                   CODE_OPEN_1, "return Code-Reviewer 1 ok", "resume Coder 2 session 1", "code 2 start b",
                   "code 2 end c", "return Coder 2 ok", "resume Code-Reviewer 2 session 1",
                   "code 2 reviewed signed-off - counts 0 0 0 next 13 new 0 closed 1 checks code-review ran",
                   "return Code-Reviewer 2 ok", "fold skipped c the branch moved after Sign-off", USER_2)

    def test_start_spawns_a_fresh_coder_for_the_users_findings_and_rings_nothing(self):
        """A reopen by hand sent the Orchestrator to ring the plan Loop
        first (Already rung, a stale paste for the Planner) and labelled both
        fresh spawns after a restart, though nothing restarted."""
        self.earlier_session()
        result = self.start()
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.spawned(result, "Coder", 3, USER_REASON)
        self.assertNotIn("doorbell ring", result.text)
        self.assertTrue(result.last.startswith("Next: Print the Spawning line above"), result)
        self.assertIn("Code Loop: reopened by the user's findings after round 2, 0 blocker, 1 major, 1 minor open.",
                      result.text)
        self.assertIn("Read: .scratch/demo/CODEREVIEW.md, .scratch/demo/spec.md, .scratch/demo/issues/", result.lines)
        lines = self.state().split("\n")
        self.assertEqual(lines[-3:-1], ["orchestrator session 2", "spawn Coder 3 session 2 reason " + USER_REASON])

    def test_the_code_reviewer_of_that_round_is_fresh_with_the_same_reason(self):
        self.earlier_session()
        self.start()
        self.stage("code 3 start c", "code 3 end d")
        result = self.back("Coder")
        self.assertEqual(result.code, 0, result)
        self.spawned(result, "Code-Reviewer", 3, USER_REASON)
        self.assertIn("spawn Code-Reviewer 3 session 2 reason " + USER_REASON, self.state())

    def test_from_the_round_after_each_roles_respawn_policy_applies(self):
        self.earlier_session()
        self.start()
        self.stage("code 3 start c", "code 3 end d")
        self.back("Coder")
        self.stage("code 3 reviewed open 15 counts 0 0 1 next 16 new 1 closed 2 checks code-review ran")
        result = self.back("Code-Reviewer")
        self.assertEqual(result.code, 0, result)
        self.assertIn("Resuming Coder, round 4.", result.lines)
        self.assertNotIn(USER_REASON, result.text)

    def test_a_restart_after_the_coder_started_places_as_today(self):
        self.earlier_session()
        self.start()
        self.stage("code 3 start c")
        result = self.start()
        self.assertEqual(result.code, 0, result)
        self.spawned(result, "Coder", 3, "after a restart")
        self.assertIn("doorbell ring --role Orchestrator", result.last)
        self.stage("code 3 end d")
        result = self.back("Coder")
        self.spawned(result, "Code-Reviewer", 3, "after a restart")


class FoldStepTest(OrchestratorTest):
    """The code Sign-off goes to the fold first, on every PR: value, and no
    restart skips it."""

    def signed_loop(self):
        """A real round-2 Sign-off: the commits the fold reads, and a
        Code-Reviewer out in this session."""
        self.git("checkout", "-q", "-b", "demo")
        start = self.head()
        self.commit("a.txt", "a\n", "feat: one")
        end_one = self.head()
        self.commit("a.txt", "a2\n", "fix: one")
        end_two = self.head()
        self.stage(PLAN_SIGNED, "orchestrator session 1", "code 1 start %s" % start, "code 1 end %s" % end_one, CODE_OPEN_1,
                   "code 2 start %s" % end_one, "code 2 end %s" % end_two, "spawn Code-Reviewer 2 session 1",
                   CODE_SIGNED_2)

    def test_return_after_the_sign_off_names_the_fold_on_every_pr_value(self):
        for value in ("no", "ask at sign-off", "yes", "manual"):
            with self.subTest(pr=value):
                self.setUp()
                self.set_pr(value)
                self.signed_loop()
                result = self.back("Code-Reviewer")
                self.assertEqual(result.code, 0, result)
                self.assertNext(result, "loop fold --slug demo --harness claude-code --write",
                                "Tell the user verbatim", "Next:")
                self.assertNotIn("vdd-create-pr", result.last)
                self.assertNotIn("loop close", result.last)

    def test_start_places_the_fold_until_its_outcome_is_recorded(self):
        for value, step in (("ask at sign-off", "Invoke the vdd-create-pr skill in your own Session"),
                            ("no", "loop close --slug demo --write")):
            with self.subTest(pr=value):
                self.setUp()
                self.set_pr(value)
                self.signed_loop()
                result = self.start()
                self.assertNext(result, "loop fold --slug demo --harness claude-code --write")
                self.assertNotIn("Spawning", result.text)
                env = self.box.env(GIT_COMMITTER_NAME="VDD Test", GIT_COMMITTER_EMAIL="test@example.com")
                folded = self.box.run("loop", "fold", "--slug", "demo", "--harness", "claude-code", "--write",
                                      env=env)
                self.assertEqual(folded.code, 0, folded)
                result = self.start()
                self.assertNext(result, step)
                self.assertNotIn("loop fold", result.last)


class RespawnQuestionTest(OrchestratorTest):
    """The Coder's Respawn policy, asked at Model approval only while unset."""

    def policies(self):
        return ()

    def loop_on(self, label):
        self.box.write_loop("demo", text=(
            "# VDD Loop\n\nFormat: 2\nFeature: demo\nBase branch: main\nFeature branch: demo\nMinors: fix\n"
            "PR: ask at sign-off\nHarness: %s\n" % label))

    def question(self, result):
        return [line for line in result.lines if line.startswith("Respawn question:")][0]

    def test_the_question_per_harness_and_nothing_placed(self):
        cases = {
            "Claude Code": ("claude-code", '"Every round" (recommended)', True),
            "Codex": ("codex", '"Never" (recommended)', False),
            "Cursor": ("cursor", '"Every round" (recommended)', False),
            "Copilot CLI": ("copilot-cli", '"Every round" (recommended)', False),
            "Generic": ("generic", None, False),
        }
        for label, (name, recommended, limit) in cases.items():
            with self.subTest(harness=name):
                self.loop_on(label)
                self.rings(P1)
                result = self.orch("start", "--slug", "demo", "--harness", name)
                self.assertEqual(result.code, 0, result)
                question = self.question(result)
                if recommended:
                    self.assertIn(recommended, question)
                    self.assertEqual(question.count("(recommended)"), 1)
                else:
                    self.assertNotIn("recommended", question)
                self.assertEqual("over 200k" in question, limit)
                self.assertNotIn("Spawning", result.text)
                self.assertNotIn("orchestrator session", self.state())
                self.assertNext(result, 'orchestrator respawn --role Coder --policy "<answer>" --slug demo --write')

    def test_start_then_respawn_places_the_workflow(self):
        """Starting took a second start after the respawn that answered the
        first one's question, which printed the Harness-file line and the
        plan's state again."""
        self.rings(P1, "not a doorbell")
        started = self.start()
        self.assertIn("Respawn question", started.text)
        result = self.orch("respawn", "--role", "Coder", "--policy", "every round", "--slug", "demo", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.lines[0], "Respawn policies: Coder every round, Plan-Reviewer never, Code-Reviewer "
                                          "never.")
        self.spawned(result, "Plan-Reviewer", 1)
        for line in started.lines[:-1]:
            if not line.startswith("Respawn policies:"):
                self.assertNotIn(line, result.lines)
        self.assertIn("Line 3 of the Doorbell file is not a Doorbell", result.text)
        self.assertIn("orchestrator return --role Plan-Reviewer", result.last)
        lines = self.state().splitlines()
        self.assertEqual(lines[-3:], ["respawn Coder every round", "orchestrator session 1",
                                      "spawn Plan-Reviewer 1 session 1"])
        self.assertIn("count 2", self.box.read(".scratch/demo/doorbell-state-orchestrator"))
        later = self.start()
        self.assertEqual(later.code, 0, later)
        self.assertNotIn("Respawn question", later.text)
        self.spawned(later, "Plan-Reviewer", 1, "after a restart")
        self.assertIn("orchestrator session 2", self.state().splitlines())

    def test_start_then_respawn_while_waiting_names_the_wait(self):
        """The two-call start with nothing rung ends in the Planner's wait,
        as the second start did."""
        self.start()
        result = self.orch("respawn", "--role", "Coder", "--policy", "never", "--slug", "demo", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(len(result.lines), 2, result)
        self.assertIn("doorbell wait --role Orchestrator", result.last)
        self.assertEqual(self.state().count("orchestrator session"), 1)

    def test_a_policy_set_before_start_still_names_start(self):
        """A reviewer's policy set while the Coder's is unset answers no
        question start asked, so it places nothing."""
        result = self.orch("respawn", "--role", "Code-Reviewer", "--policy", "every round", "--slug", "demo",
                           "--write")
        self.assertEqual(result.code, 0, result)
        self.assertNext(result, "orchestrator start --slug demo --harness claude-code")
        self.assertNotIn("orchestrator session", self.state())

    def test_a_policy_in_another_case_is_taken(self):
        """An Orchestrator passed its answer label "Every round" as the
        policy, was refused and asked the user a second time."""
        result = self.orch("respawn", "--role", "Coder", "--policy", "Every Round", "--slug", "demo", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertIn("respawn Coder every round", self.state())
        over = self.orch("respawn", "--role", "Code-Reviewer", "--policy", "OVER 200K", "--slug", "demo", "--write")
        self.assertEqual(over.code, 0, over)
        self.assertIn("respawn Code-Reviewer over 200k", self.state())

    def test_a_mid_loop_change_names_no_start_and_records_no_session(self):
        """A policy change after a recorded spawn placed the Workflow again and
        spawned a second Coder beside a live one."""
        self.stage("respawn Coder never", "orchestrator session 1", "spawn Coder 1 session 1")
        result = self.orch("respawn", "--role", "Code-Reviewer", "--policy", "every round", "--slug", "demo",
                           "--write")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.last, "Next: The policy applies from the Role's next round; go on with the step the "
                                      "tool printed before it.")
        self.assertNotIn("orchestrator start", result.text)
        self.assertEqual(self.state().count("orchestrator session"), 1)

    def test_generic_is_named_by_the_loop_file_s_value(self):
        """Generic's Harness module has no label, so start printed "Harness: ."
        and the refusals a blank."""
        self.loop_on("Generic")
        self.stage("respawn Coder never")
        started = self.orch("start", "--slug", "demo", "--harness", "generic")
        self.assertEqual(started.code, 0, started)
        self.assertIn("Harness: Generic. Read harness-generic.md", started.lines[0])
        over = self.orch("respawn", "--role", "Coder", "--policy", "over 200k", "--slug", "demo", "--write")
        self.assertIn("over <n> works only on Claude Code: Generic reports no subagent token count.", over.text)
        tokens = self.orch("tokens", "--role", "Coder", "--tokens", "1000", "--slug", "demo")
        self.assertIn("Generic reports no subagent token count, so there is none to record.", tokens.text)
        wrong = self.orch("start", "--slug", "demo", "--harness", "codex")
        self.assertIn("does not match the Loop file's Harness: Generic.", wrong.text)

    def test_over_is_claude_code_only_and_a_bad_policy_is_refused(self):
        for label in ("Codex", "Cursor", "Copilot CLI", "Generic"):
            with self.subTest(harness=label):
                self.loop_on(label)
                result = self.orch("respawn", "--role", "Coder", "--policy", "over 200k", "--slug", "demo", "--write")
                self.assertNotEqual(result.code, 0, result)
                self.assertIn("only on Claude Code", result.text)
        for label in ("Claude Code", "Codex"):
            for policy in ("over 2x", "sometimes"):
                with self.subTest(harness=label, policy=policy):
                    self.loop_on(label)
                    result = self.orch("respawn", "--role", "Coder", "--policy", policy, "--slug", "demo", "--write")
                    self.assertNotEqual(result.code, 0, result)
                    self.assertIn("is not a Respawn policy", result.text)
        self.assertNotIn("respawn Coder", self.state())


class PolicyTest(OrchestratorTest):
    def policies(self):
        return ()

    def after_review_one(self, policy):
        self.stage("respawn Coder %s" % policy, "orchestrator session 1", "spawn Coder 1 session 1",
                   "code 1 start a", "code 1 end b", "return Coder 1 ok", "spawn Code-Reviewer 1 session 1",
                   CODE_OPEN_1)
        return self.back("Code-Reviewer")

    def test_every_round_respawns_and_never_resumes(self):
        result = self.after_review_one("every round")
        self.spawned(result, "Coder", 2, "respawn every round")

    def test_never_resumes(self):
        result = self.after_review_one("never")
        self.assertIn("Resuming Coder, round 2.", result.lines)
        index = result.lines.index("Resume message:")
        self.assertEqual(result.lines[index + 1],
                         "VDD Code-Reviewer: CODEREVIEW.md written, round 1: 0 blocker, 1 major, 0 minor. Read it.")

    def test_over_asks_for_the_count_at_the_code_reviewer_s_return(self):
        """The count is asked when the Code-Reviewer's return decides the
        Coder's next round, when it is already in the Orchestrator's context."""
        result = self.after_review_one("over 200k")
        self.assertEqual(result.code, 0, result)
        self.assertNotIn("Spawning", result.text)
        self.assertNext(result, "orchestrator tokens --role Coder --tokens <subagent_tokens> --slug demo")
        respawned = self.orch("tokens", "--role", "Coder", "--tokens", "210000", "--slug", "demo")
        self.spawned(respawned, "Coder", 2, "respawn at 210k")

    def test_over_resumes_under_the_limit(self):
        self.after_review_one("over 200k")
        result = self.orch("tokens", "--role", "Coder", "--tokens", "150000", "--slug", "demo")
        self.assertIn("Resuming Coder, round 2.", result.lines)

    def test_tokens_is_refused_off_claude_code(self):
        self.box.write_loop("demo", text=(
            "# VDD Loop\n\nFormat: 2\nFeature: demo\nBase branch: main\nFeature branch: demo\nMinors: fix\n"
            "PR: ask at sign-off\nHarness: Codex\n"), extra=("respawn Coder never", "orchestrator session 1",
                                                              "spawn Coder 1 session 1"))
        result = self.orch("tokens", "--role", "Coder", "--tokens", "1000", "--slug", "demo")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("reports no subagent token count", result.text)

    def test_once_respawns_the_next_spawn_once(self):
        self.stage("respawn Coder never", "orchestrator session 1", "spawn Coder 1 session 1", "code 1 start a",
                   "code 1 end b", "return Coder 1 ok", "spawn Code-Reviewer 1 session 1", CODE_OPEN_1,
                   "return Code-Reviewer 1 ok", "resume Coder 2 session 1", "code 2 start b", "code 2 end c")
        once = self.orch("respawn", "--role", "Code-Reviewer", "--once", "--slug", "demo", "--write")
        self.assertEqual(once.code, 0, once)
        self.assertNext(once, "Go on with the step the tool printed before it.")
        result = self.back("Coder")
        self.spawned(result, "Code-Reviewer", 2, "respawn on request")
        self.stage("code 2 reviewed open 1 counts 0 1 0 next 2 new 0 closed 0 checks code-review ran",
                   "return Code-Reviewer 2 ok", "resume Coder 3 session 1", "code 3 start c", "code 3 end d")
        later = self.back("Coder")
        self.assertIn("Resuming Code-Reviewer, round 3.", later.lines)

    def test_once_after_a_blocked_spawns_the_unfinished_round(self):
        self.stage("respawn Coder never", "orchestrator session 1", "spawn Coder 1 session 1", "code 1 start a")
        result = self.orch("respawn", "--role", "Coder", "--once", "--slug", "demo", "--write")
        self.assertEqual(result.code, 0, result)
        self.spawned(result, "Coder", 1, "respawn on request")

    def test_once_after_a_blocked_over_a_finished_round_names_the_return(self):
        """A BLOCKED after a passed check --write leaves the round's return
        owed: --once names orchestrator return, not the step before the
        BLOCKED."""
        self.stage("respawn Coder never", "orchestrator session 1", "spawn Coder 1 session 1", "code 1 start a",
                   "code 1 end b")
        result = self.orch("respawn", "--role", "Coder", "--once", "--slug", "demo", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertNotIn("Spawning", result.text)
        self.assertNext(result, "orchestrator return --role Coder --slug demo --harness claude-code")
        self.spawned(self.back("Coder"), "Code-Reviewer", 1)

    def test_a_question_s_resume_and_the_fixed_resume_stay_resumes(self):
        """A resume after a miss stays a resume whatever the policy says."""
        self.stage("respawn Coder every round", "orchestrator session 1", "spawn Coder 1 session 1",
                   "code 1 start a")
        result = self.back("Coder")
        self.assertIn("Resuming Coder, round 1.", result.lines)


class SkillTextTest(OrchestratorTest):
    """Each hosted Role's Read and Write lists, as orchestrator return prints
    them, name only Working files that Role's SKILL.md names, since an
    Orchestrator given no list missed files."""

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

    # The Read and Write lists orchestrator return prints: (role, round) ->
    # (Read, Write), a parenthetical after a name dropped.
    TABLE = {
        ("Plan-Reviewer", 1): (["spec.md", "issues/"], ["PLAN-REVIEW.md"]),
        ("Plan-Reviewer", 2): (["PLAN-REVIEW.md", "spec.md", "issues/"], ["PLAN-REVIEW.md"]),
        ("Coder", 1): (["spec.md", "issues/"], ["FIXES.md", "issues/"]),
        ("Coder", 2): (["CODEREVIEW.md", "spec.md", "issues/"], ["FIXES.md", "issues/"]),
        ("Code-Reviewer", 1): (["spec.md", "issues/", "FIXES.md"], ["CODEREVIEW.md"]),
        ("Code-Reviewer", 2): (["CODEREVIEW.md", "spec.md", "issues/"], ["CODEREVIEW.md"]),
    }

    def test_every_listed_file_is_named_in_the_role_s_skill(self):
        """Each list also equals its row of TABLE, so a later round's file
        listed in round 1, or a missing FIXES.md, fails."""
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
