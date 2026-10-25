"""The position table: one staged state file and Doorbell file per position,
and each Role command run against it through vdd.py. At most one Role
command passes in a row, the one whose Role owes the next move, so the
Orchestrator never spawns a Role that refuses on its precondition."""

import unittest

from scenes import CC, CODE_OPEN_1, P1, P2, PLAN_OPEN_1, SLUG, Staged

USER_1 = "code 1 user open 1 counts 0 1 0 next 2 new 1"
NEVER = ("respawn Coder never",)

# The Role commands of a row, each a dry run that checks its precondition.
COMMANDS = {
    "coder": ("coder", "start", *SLUG),
    "plan": ("review", "start", "--role", "Plan-Reviewer", *SLUG),
    "code": ("review", "start", "--role", "Code-Reviewer", *SLUG),
    "pr": ("pr", "check", *SLUG, *CC),
}


class Scenes(Staged):
    """The rows' scenes."""

    def nothing_rung(self):
        self.plan(policies=NEVER)

    def plan_rung(self):
        self.plan(policies=NEVER)
        self.rings(P1)

    def plan_open(self):
        self.plan(policies=NEVER)
        self.rings(P1)
        self.stage(PLAN_OPEN_1)

    def plan_signed(self):
        self.signed(policies=NEVER)

    def ring_before_code(self):
        """A Planner ring after the plan Sign-off, before code 1 start."""
        self.signed(policies=NEVER)
        self.rings(P1, P2)

    def ring_after_code(self):
        """A Planner ring after the plan Sign-off, once code 1 started."""
        self.signed(policies=NEVER)
        self.git("checkout", "-q", "-b", "demo")
        self.stage("code 1 start %s" % self.sha())
        self.rings(P1, P2)

    def code_ended(self):
        self.coding(policies=NEVER)

    def review_file(self, reference):
        """CODEREVIEW.md holding finding 1 open, as the round's check left it."""
        self.put("CODEREVIEW.md", "# Code review, round 1\n\nOpen: 0 blocker, 1 major, 0 minor.\n\n## Open findings\n\n"
                 "### 1. major (open): %s\n\nThe value is wrong.\n" % reference)

    def code_open(self):
        self.coding(policies=NEVER)
        self.stage(CODE_OPEN_1)
        self.review_file("a.txt:1")

    def user_findings(self):
        """The user's findings after the round-1 Sign-off."""
        self.code_signed(policies=NEVER)
        self.stage(USER_1)
        self.review_file("docs/a.md:3")

    def fold_owed(self):
        self.code_signed(policies=NEVER)

    def folded_scene(self):
        self.folded(policies=NEVER)

    def reopened(self):
        """The user's findings after round 1, and the Coder's round 2 done."""
        self.code_signed(policies=NEVER)
        self.stage(USER_1)
        self.review_file("docs/a.md:3")
        self.coder_round(2)


class Positions(Scenes):
    def row(self, scene, passes, placed):
        scene(self)
        env = self.env(self.no_gh())
        passed = []
        for name, argv in COMMANDS.items():
            result = self.box.run(*argv, env=env)
            self.assertTrue(result.last.startswith("Next: "), result)
            if result.code == 0:
                passed.append(name)
        self.assertEqual(passed, [passes] if passes else [], "the Role commands that passed")
        start = self.box.run("orchestrator", "start", *SLUG, *CC, env=env)
        self.assertEqual(start.code, 0, start)
        for line in placed:
            self.assertIn(line, start.text)
        return start

    def test_nothing_rung(self):
        self.row(Scenes.nothing_rung, None, ["Plan Loop: the Planner has rung no round yet."])

    def test_plan_round_rung(self):
        self.row(Scenes.plan_rung, "plan", ["Spawning Plan-Reviewer, <model>, round 1."])

    def test_plan_round_open(self):
        self.row(Scenes.plan_open, None, ["the Planner owns the next move"])

    def test_plan_signed_off(self):
        self.row(Scenes.plan_signed, "coder", ["Spawning Coder, <model>, round 1."])

    def test_a_ring_after_the_plan_sign_off_before_code_1_start(self):
        """Prevents the Plan-Reviewer spawned for a changed Spec refusing on
        a signed-off plan Loop and ending in BLOCKED."""
        self.row(Scenes.ring_before_code, "plan", [
            "Plan Loop: signed off in round 1; the Planner rang round 2 after it, not reviewed yet.",
            "Spawning Plan-Reviewer, <model>, round 2."])

    def test_a_ring_after_the_plan_sign_off_after_code_1_start(self):
        self.row(Scenes.ring_after_code, "coder", ["Spawning Coder, <model>, round 1."])

    def test_code_round_ended(self):
        self.row(Scenes.code_ended, "code", ["Spawning Code-Reviewer, <model>, round 1."])

    def test_code_round_open(self):
        self.row(Scenes.code_open, "coder", ["Spawning Coder, <model>, round 2."])

    def test_the_user_s_findings(self):
        """Prevents review check answering the user's counts as the
        Code-Reviewer's own Doorbell."""
        self.row(Scenes.user_findings, "coder", ["Spawning Coder, <model>, round 2, for the user's findings."])
        check = self.box.run("review", "check", "--role", "Code-Reviewer", *SLUG, "--write", env=self.env())
        self.assertNotEqual(check.code, 0, check)
        self.assertNotIn("VDD Code-Reviewer:", check.text)
        self.assertNotIn("already recorded", check.text)

    def test_the_owed_fold(self):
        """Prevents a PR assembled or pushed from a branch the fold has not
        put in its reviewed shape: pr check and pr open both refuse, and pr
        check names the loop fold call."""
        self.row(Scenes.fold_owed, None, ["Fold: not run yet."])
        checked = self.box.run("pr", "check", *SLUG, *CC, env=self.env(self.no_gh()))
        self.assertIn("loop fold --slug demo --harness claude-code --write, then run ", checked.last)
        opened = self.box.run("pr", "open", "--path", "open", *SLUG, *CC, "--write", env=self.env(self.no_gh()))
        self.assertNotEqual(opened.code, 0, opened)
        self.assertIn("The fold's outcome is not recorded", opened.text)

    def test_folded(self):
        self.row(Scenes.folded_scene, "pr", ["Fold: folded."])

    def test_a_reopened_code_loop(self):
        self.row(Scenes.reopened, "code", ["Spawning Code-Reviewer, <model>, round 2"])


class PlanRing(Scenes):
    def test_the_refusal_once_the_code_loop_runs(self):
        """Pins the plan-ring refusal: once the code Loop has started, a
        Planner ring after the plan Sign-off spawns no Plan-Reviewer, which
        would only end in BLOCKED."""
        self.ring_after_code()
        result = self.box.run("orchestrator", "return", "--role", "Planner", *SLUG, *CC, env=self.env())
        self.assertEqual(result.code, 1, result)
        self.assertEqual(result.lines, [
            "The Planner rang plan round 2 after the plan Sign-off in round 1, and the code Loop has started: no "
            "Plan-Reviewer reviews it.",
            'Tell the user verbatim: "The plan Loop is signed off and the code Loop is running, so the Planner\'s '
            'plan round 2 is not reviewed. The code Loop goes on with the Spec as it was signed off."',
            "Next: Relay every Tell the user verbatim line above unchanged; only after doing that, go on with the "
            "step you were on before the Planner's Doorbell. Spawn no Plan-Reviewer.",
        ])
        self.assertNotIn("spawn Plan-Reviewer", self.state())

    def test_before_the_code_loop_the_ring_opens_the_next_plan_round(self):
        """Prevents a changed Spec after the plan Sign-off going unreviewed."""
        self.ring_before_code()
        self.stage("orchestrator session 1")
        result = self.box.run("orchestrator", "return", "--role", "Planner", *SLUG, *CC, env=self.env())
        self.assertEqual(result.code, 0, result)
        self.assertIn("Spawning Plan-Reviewer, <model>, round 2.", result.lines)
        started = self.box.run("review", "start", "--role", "Plan-Reviewer", *SLUG, "--write", env=self.env())
        self.assertEqual(started.code, 0, started)


if __name__ == "__main__":
    unittest.main()
