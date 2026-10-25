"""Every state-line kind, written by the command that writes it and read back
by another command, through vdd.py. Each test prevents a builder and its
parser drifting apart: the documented "[once]" token of a spawn line was
parsed for versions, yet no version ever wrote it."""

import unittest

from scenes import CC, FINDINGS, SLUG, Staged


class StateLines(Staged):
    def lines(self, prefix):
        return [line for line in self.state().split("\n") if line.startswith(prefix)]

    def orch(self, *argv):
        return self.box.run("orchestrator", *argv, *SLUG, *CC, env=self.env())

    def start(self):
        return self.orch("start")

    def back(self, role):
        return self.orch("return", "--role", role)

    # --- the loop lines ---

    def test_loop_closed_and_open(self):
        """loop close and loop reopen write "loop closed" and "loop open";
        loop show reads them back, so the two never disagree on the word."""
        self.plan()
        self.run_ok("loop", "close", *SLUG, "--write")
        self.assertEqual(self.lines("loop "), ["loop open", "loop closed"])
        self.assertIn("State: closed", self.run_ok("loop", "show", *SLUG).lines)
        self.run_ok("loop", "reopen", *SLUG, "--write")
        self.assertIn("State: open", self.run_ok("loop", "show", *SLUG).lines)

    # --- the review lines ---

    def test_review_started(self):
        """review start writes "<kind> <r> review-started"; review check,
        its one reader, finds it and does not refuse the round as not
        started."""
        self.plan_review_written()
        self.assertEqual(self.lines("plan 1 review-started"), ["plan 1 review-started"])
        result = self.box.run("review", "check", "--role", "Plan-Reviewer", *SLUG, env=self.env())
        self.assertNotIn("has not been started", result.text)
        self.assertEqual(result.code, 0, result)

    def test_reviewed(self):
        """review check --write writes the reviewed line; orchestrator start
        reads its round, outcome and counts."""
        self.plan_review_written()
        self.run_ok("review", "check", "--role", "Plan-Reviewer", *SLUG, "--write")
        self.assertEqual(len(self.lines("plan 1 reviewed open 1,2 ")), 1, self.state())
        result = self.start()
        self.assertIn("Plan Loop: round 1 reviewed, 0 blocker, 1 major, 1 minor open; the Planner owns the next "
                      "move.", result.text)

    def test_user(self):
        """review add writes the user line; orchestrator start reads it as
        the user's entry after round 1, with its counts."""
        self.folded()
        self.box.write("findings.md", FINDINGS)
        self.run_ok("review", "add", *SLUG, "--from", "findings.md", "--write")
        self.assertEqual(len(self.lines("code 1 user open ")), 1, self.state())
        result = self.start()
        self.assertIn("Code Loop: reopened by the user's findings after round 1, 0 blocker, 1 major, 1 minor open.",
                      result.text)

    # --- the code round lines ---

    def test_code_start(self):
        """coder start --write writes "code <r> start <sha>"; orchestrator
        start reads the round as started."""
        self.signed()
        self.run_ok("coder", "start", *SLUG, "--write")
        self.assertEqual(self.lines("code 1 start "), ["code 1 start %s" % self.sha("main")])
        self.assertIn("Code Loop: Coder round 1 started, not finished.", self.start().text)

    def test_code_end(self):
        """coder check --write writes "code <r> end <sha>"; orchestrator start
        reads the round as done."""
        self.coder_started()
        self.run_ok("coder", "check", *SLUG, "--write")
        self.assertEqual(self.lines("code 1 end "), ["code 1 end %s" % self.sha()])
        self.assertIn("Code Loop: Coder round 1 done, not reviewed.", self.start().text)

    # --- the Orchestrator's ledger ---

    def test_respawn(self):
        """orchestrator respawn --policy writes the respawn line; orchestrator
        start reads the policy."""
        self.plan()
        self.run_ok("orchestrator", "respawn", "--role", "Coder", "--policy", "every round", *SLUG, "--write")
        self.assertEqual(self.lines("respawn "), ["respawn Coder every round"])
        self.assertIn("Respawn policies: Coder every round, Plan-Reviewer never, Code-Reviewer never.",
                      self.start().lines)

    def test_session_and_spawn(self):
        """orchestrator start writes the session and the spawn lines; the
        next orchestrator start reads both, so its spawn is one after a
        restart."""
        self.planner_returned()
        first = self.start()
        self.assertIn("Spawning Plan-Reviewer, <model>, round 1, after a restart.", first.lines)
        self.assertEqual(self.lines("orchestrator session "), ["orchestrator session 1", "orchestrator session 2"])
        self.assertEqual(self.lines("spawn "), ["spawn Plan-Reviewer 1 session 2 reason after a restart"])
        second = self.start()
        self.assertEqual(self.lines("orchestrator session ")[-1], "orchestrator session 3")
        self.assertIn("Spawning Plan-Reviewer, <model>, round 1, after a restart.", second.lines)

    def test_spawn_without_a_reason(self):
        """A spawn line with no reason reads back as a live Role:
        orchestrator return acts on its round."""
        self.plan(policies=("respawn Coder never",))
        self.rings("VDD Planner: .scratch/demo/ ready, round 1. Read spec.md and issues/.")
        self.start()
        self.assertEqual(self.lines("spawn "), ["spawn Plan-Reviewer 1 session 1"])
        result = self.back("Plan-Reviewer")
        self.assertIn("Plan-Reviewer round 1 ended without", result.text)

    def test_return_ok_and_miss(self):
        """orchestrator return writes "return <Role> <r> miss" and "ok"; the
        next return reads them: a second miss asks the user, and a return
        after ok is already acted on."""
        self.plan(policies=("respawn Coder never",))
        self.rings("VDD Planner: .scratch/demo/ ready, round 1. Read spec.md and issues/.")
        self.start()
        self.back("Plan-Reviewer")
        self.assertEqual(self.lines("return "), ["return Plan-Reviewer 1 miss"])
        self.assertIn("a second time", self.back("Plan-Reviewer").text)
        self.run_ok("review", "start", "--role", "Plan-Reviewer", *SLUG, "--write")
        self.put("PLAN-REVIEW.md", self.read("PLAN-REVIEW.md").replace(
            "writing-for-agents: <ran | did not resolve | not needed, <reason>>", "writing-for-agents: ran"))
        self.run_ok("review", "check", "--role", "Plan-Reviewer", *SLUG, "--write")
        self.back("Plan-Reviewer")
        self.assertEqual(self.lines("return ")[-1], "return Plan-Reviewer 1 ok")
        self.assertIn("already acted on", self.back("Plan-Reviewer").text)

    def test_resume(self):
        """orchestrator return writes the resume line; the next return reads
        the resumed Role as live for its new round."""
        self.plan(policies=("respawn Coder never",))
        self.rings("VDD Planner: .scratch/demo/ ready, round 1. Read spec.md and issues/.")
        self.start()
        self.stage("plan 1 reviewed open 1 counts 0 1 0 next 2 new 1 closed 0 checks writing-for-agents ran",
                   "return Plan-Reviewer 1 ok")
        self.rings("VDD Planner: .scratch/demo/ ready, round 2. Read spec.md and issues/.")
        self.assertIn("Resuming Plan-Reviewer, round 2.", self.back("Planner").lines)
        self.assertEqual(self.lines("resume "), ["resume Plan-Reviewer 2 session 1"])
        self.assertIn("Plan-Reviewer round 2 ended without", self.back("Plan-Reviewer").text)

    def test_respawn_once(self):
        """orchestrator respawn --once writes the respawn-once line; the next
        return reads it and spawns the Role fresh."""
        self.plan(policies=("respawn Coder never",))
        self.stage("orchestrator session 1", "spawn Coder 1 session 1", "code 1 start a", "code 1 end b",
                   "return Coder 1 ok", "spawn Code-Reviewer 1 session 1",
                   "code 1 reviewed open 1 counts 0 1 0 next 2 new 1 closed 0 checks code-review ran",
                   "return Code-Reviewer 1 ok", "resume Coder 2 session 1", "code 2 start b", "code 2 end c")
        self.run_ok("orchestrator", "respawn", "--role", "Code-Reviewer", "--once", *SLUG, "--write")
        self.assertEqual(self.lines("respawn-once "), ["respawn-once Code-Reviewer"])
        self.assertIn("Spawning Code-Reviewer, <model>, round 2, respawn on request.", self.back("Coder").lines)

    def test_tokens(self):
        """orchestrator tokens writes the tokens line; a later return reads
        the count against the Coder's policy."""
        self.plan(policies=("respawn Coder over 200k",))
        self.stage("orchestrator session 1", "spawn Coder 1 session 1", "code 1 start a", "code 1 end b",
                   "return Coder 1 ok", "spawn Code-Reviewer 1 session 1")
        self.run_ok("orchestrator", "tokens", "--role", "Coder", "--tokens", "210000", *SLUG)
        self.assertEqual(self.lines("tokens "), ["tokens Coder 1 210000"])
        self.stage("code 1 reviewed open 1 counts 0 1 0 next 2 new 1 closed 0 checks code-review ran")
        self.assertIn("Spawning Coder, <model>, round 2, respawn at 210k.", self.back("Code-Reviewer").lines)

    # --- the fold lines ---

    def test_fold_folded(self):
        """loop fold --write writes "fold folded <tip> signed <sha>";
        orchestrator start reads it and goes on to the PR step."""
        self.code_signed(policies=("respawn Coder never",))
        self.run_ok("loop", "fold", *SLUG, *CC, "--write")
        self.assertEqual(len(self.lines("fold folded ")), 1, self.state())
        self.assertIn("Fold: folded.", self.start().lines)

    def test_fold_skipped(self):
        """loop fold --write on a branch with an upstream writes "fold
        skipped <sha> <reason>"; orchestrator start reads it."""
        self.code_signed(policies=("respawn Coder never",))
        self.git("branch", "--set-upstream-to=main", "demo")
        self.run_ok("loop", "fold", *SLUG, *CC, "--write")
        self.assertEqual(len(self.lines("fold skipped %s " % self.sha())), 1, self.state())
        self.assertIn("Fold: skipped.", self.start().lines)


if __name__ == "__main__":
    unittest.main()
