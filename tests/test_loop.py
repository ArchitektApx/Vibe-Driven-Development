"""The loop command group, driven from outside: new, show and set, and
finding the loop."""

import os
import unittest

from vddtest import ToolTest

ANSWERS = ["--minors", "fix", "--pr", "ask at sign-off", "--fresh-coder", "every round"]
ROOT_FIX = (
    "Delete `LOOP.md`. To carry on the loop it belongs to, run `vdd-start-loop` with its slug and answer continue."
)


class LoopTest(ToolTest):
    def setUp(self):
        ToolTest.setUp(self)
        self.box.init_git("main")

    def loop(self, *args):
        return self.box.run("loop", *args)

    def new(self, slug="demo", *extra, harness="claude-code", write=False):
        tail = ["--write"] if write else []
        return self.loop("new", "--slug", slug, "--harness", harness, *(list(extra) + tail))

    def tree(self):
        out = []
        for directory, _, files in os.walk(self.box.proj):
            if ".git" in os.path.relpath(directory, self.box.proj).split(os.sep):
                continue
            for name in files:
                out.append(os.path.relpath(os.path.join(directory, name), self.box.proj))
        return sorted(out)

    def file(self, slug="demo", name="loop.md"):
        return self.box.read(os.path.join(".scratch", slug, name))

    def field(self, result, name):
        for line in result.lines:
            if line.startswith(name + ": "):
                return line[len(name) + 2:]
        return None


class HelpTest(LoopTest):
    def test_help_lists_the_commands(self):
        result = self.loop("--help")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        for command in ("loop new", "loop show", "loop set"):
            self.assertIn(command, result.text)

    def test_the_top_level_help_lists_the_group(self):
        self.assertIn("  loop ", self.box.run("--help").text)


class NewTest(LoopTest):
    def test_a_dry_run_changes_nothing_and_prints_the_questions(self):
        before = self.tree()
        result = self.new()
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertEqual(self.tree(), before)
        self.assertIn("Feature branch: demo (proposed: the slug).", result.lines)
        self.assertIn("Base branch: main (from the checked-out branch).", result.lines)
        questions = [line for line in result.lines if line.startswith("Question ")]
        self.assertEqual([q.split(":")[0] for q in questions],
                         ["Question 1, feature branch", "Question 2, Minors", "Question 3, PR",
                          "Question 4, Fresh Coder"])
        fresh = questions[3]
        self.assertIn('"Every round" (recommended)', fresh)
        self.assertIn("over 200k", fresh)
        self.assertNext(result, "loop new --slug demo", "--write")

    def test_write_writes_the_loop_file_and_the_state_file(self):
        result = self.new("demo", *ANSWERS, write=True)
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertEqual(
            self.file(),
            "# VDD Loop\n\nFormat: 2\nFeature: demo\nBase branch: main\nFeature branch: demo\nMinors: fix\n"
            "PR: ask at sign-off\nFresh Coder: every round\nHarness: Claude Code\n",
        )
        self.assertEqual(self.file(name="loop-state"), "vdd loop-state 1\nloop open\n")
        self.assertNext(result, "--slug demo")

    def test_write_needs_every_answer(self):
        result = self.new("demo", "--minors", "fix", write=True)
        self.assertNotEqual(result.code, 0, result)
        self.assertFalse(os.path.exists(self.box.path(".scratch", "demo")))

    def test_the_fresh_coder_question_per_harness(self):
        cases = {
            "codex": ('"Never" (recommended)', False),
            "cursor": ('"Every round" (recommended)', False),
            "copilot-cli": ('"Every round" (recommended)', False),
            "generic": (None, False),
        }
        for harness, (recommended, limit) in cases.items():
            with self.subTest(harness=harness):
                result = self.new(harness=harness)
                fresh = [line for line in result.lines if line.startswith("Question 4, Fresh Coder")][0]
                if recommended:
                    self.assertIn(recommended, fresh)
                    self.assertEqual(fresh.count("(recommended)"), 1)
                else:
                    self.assertNotIn("recommended", fresh)
                self.assertNotIn("over ", fresh)

    def test_answers_given_are_not_asked(self):
        result = self.new("demo", "--branch", "feat/demo", "--minors", "leave")
        names = [line.split(":")[0] for line in result.lines if line.startswith("Question ")]
        self.assertEqual(names, ["Question 1, PR", "Question 2, Fresh Coder"])

    def test_the_harness_line_is_the_display_name(self):
        for harness, label in (("codex", "Codex"), ("copilot-cli", "Copilot CLI"), ("generic", "Generic")):
            with self.subTest(harness=harness):
                slug = "h-" + harness
                self.new(slug, *ANSWERS, harness=harness, write=True)
                self.assertIn("Harness: %s\n" % label, self.file(slug))

    def test_a_slug_outside_the_pattern_is_refused_with_the_pattern(self):
        """The slug check moved from Start-Loop's prose into the tool
        (ticket 18 L02): the refusal names the pattern so the user fixes the
        slug in one try."""
        for slug in ("Demo", "demo_x", "-demo", "demo-", "de--mo", "", "a/b"):
            with self.subTest(slug=slug):
                result = self.new(slug, *ANSWERS, write=True)
                self.assertNotEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertIn("[a-z0-9]+(-[a-z0-9]+)*", result.text)
        self.assertFalse(os.path.exists(self.box.path(".scratch")))

    def test_a_feature_branch_equal_to_the_base_branch_is_refused(self):
        """Start-Loop step 5: every review diffs <base>...HEAD, so the
        feature branch must differ from the base branch."""
        for extra in (("--branch", "main"), ("--base", "demo")):
            with self.subTest(extra=extra):
                result = self.new("demo", *(list(extra) + ANSWERS), write=True)
                self.assertNotEqual(result.code, 0, result)
                self.assertIn("equals the base branch", result.text)
                self.assertFalse(os.path.exists(self.box.path(".scratch", "demo")))

    def test_a_detached_head_asks_for_the_base_branch(self):
        """Start-Loop step 5: on a detached HEAD the tool asks for the base
        branch and never guesses it."""
        self.box.git("checkout", "-q", "--detach")
        result = self.new()
        self.assertEqual(result.code, 0, result)
        self.assertNext(result, "--base <branch>")
        self.assertFalse(any(line.startswith("Question") for line in result.lines))
        written = self.new("demo", *ANSWERS, write=True)
        self.assertNotEqual(written.code, 0, written)
        self.assertNext(written, "--base <branch>")
        self.assertFalse(os.path.exists(self.box.path(".scratch", "demo")))
        ok = self.new("demo", "--base", "main", *ANSWERS, write=True)
        self.assertEqual(ok.code, 0, ok)
        self.assertIn("Base branch: main\n", self.file())

    def test_an_answer_outside_the_accepted_values_is_refused(self):
        result = self.new("demo", "--minors", "Fix", "--pr", "yes", "--fresh-coder", "never", write=True)
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("fix or leave", result.text)


class ShowTest(LoopTest):
    def setUp(self):
        LoopTest.setUp(self)
        self.new("demo", *ANSWERS, write=True)

    def test_show_prints_every_line_the_state_and_the_harness_file(self):
        result = self.loop("show", "--slug", "demo")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertEqual(result.lines[:-1], [
            "Slug: demo",
            "State: open",
            "Feature: demo",
            "Base branch: main",
            "Feature branch: demo",
            "Minors: fix",
            "PR: ask at sign-off",
            "Fresh Coder: every round",
            "Harness: Claude Code",
            "Harness file: harness-claude-code.md",
        ])
        self.assertNext(result, "--slug demo")

    def test_role_prints_only_its_lines(self):
        roles = {
            "Planner": ["Feature", "Harness"],
            "Plan-Reviewer": ["Minors", "Harness"],
            "Coder": ["Base branch", "Feature branch", "Harness"],
            "Code-Reviewer": ["Base branch", "Minors", "Harness"],
            "Orchestrator": ["Feature", "Base branch", "Feature branch", "Minors", "PR", "Fresh Coder", "Harness"],
            "PR-Author": ["Base branch", "Feature branch", "PR", "Harness"],
        }
        for role, names in roles.items():
            with self.subTest(role=role):
                result = self.loop("show", "--slug", "demo", "--role", role)
                self.assertEqual(result.code, 0, result)
                shown = [line.split(":")[0] for line in result.lines[2:-2]]
                self.assertEqual(shown, names)
                self.assertEqual(result.lines[:2], ["Slug: demo", "State: open"])
                self.assertEqual(result.lines[-2], "Harness file: harness-claude-code.md")

    def test_an_unknown_role_is_refused(self):
        result = self.loop("show", "--slug", "demo", "--role", "Wayfinder")
        self.assertNotEqual(result.code, 0, result)

    def rewrite(self, name, value):
        lines = self.file().split("\n")
        lines = [line for line in lines if not line.startswith(name + ":")]
        if value is not None:
            lines.insert(3, "%s: %s" % (name, value))
        self.box.write(os.path.join(".scratch", "demo", "loop.md"), "\n".join(lines))

    def test_a_missing_line_and_a_malformed_line_each_name_their_fault(self):
        """Respawn finding 1: a missing line was reported as malformed. Each
        line reads as its default, with the right word, and the user is told."""
        defaults = {"Minors": "leave", "PR": "ask at sign-off", "Fresh Coder": "never", "Harness": "Generic"}
        bad = {"Minors": "maybe", "PR": "sometimes", "Fresh Coder": "Every Round", "Harness": "Vim"}
        original = self.file()
        for name, default in defaults.items():
            for fault, value in (("missing", None), ("malformed", bad[name])):
                with self.subTest(name=name, fault=fault):
                    self.box.write(os.path.join(".scratch", "demo", "loop.md"), original)
                    self.rewrite(name, value)
                    result = self.loop("show", "--slug", "demo")
                    self.assertEqual(result.code, 0, result)
                    line = [l for l in result.lines if l.startswith(name + ": ")][0]
                    self.assertTrue(line.startswith("%s: %s (" % (name, default)), line)
                    self.assertIn(fault, line)
                    other = "malformed" if fault == "missing" else "missing"
                    self.assertNotIn(other, line)
                    self.assertEqual(
                        result.tells(),
                        ["The Loop file's %s: line is %s, so it reads as %s: %s." % (name, fault, name, default)],
                    )
                    if name == "Harness":
                        self.assertIn("Harness file: harness-generic.md", result.lines)

    def test_the_accepted_values(self):
        cases = {
            ("Fresh Coder", "over 300k"): True,
            ("Fresh Coder", "over 1k"): True,
            ("Fresh Coder", "every round"): True,
            ("Fresh Coder", "never"): True,
            ("Fresh Coder", "over 0k"): False,
            ("Fresh Coder", "over 200000"): False,
            ("Fresh Coder", "Every Round"): False,
            ("Minors", "Fix"): False,
            ("Minors", "leave"): True,
            ("PR", "Ask at sign-off"): False,
            ("PR", "manual"): True,
            ("Harness", "claude code"): False,
            ("Harness", "Copilot CLI"): True,
        }
        original = self.file()
        for (name, value), ok in cases.items():
            with self.subTest(name=name, value=value):
                self.box.write(os.path.join(".scratch", "demo", "loop.md"), original)
                self.rewrite(name, value)
                result = self.loop("show", "--slug", "demo")
                line = [l for l in result.lines if l.startswith(name + ": ")][0]
                if ok:
                    self.assertEqual(line, "%s: %s" % (name, value))
                else:
                    self.assertIn("malformed", line)

    def test_an_unknown_higher_format_is_refused_with_rerun_setup(self):
        """The paused grilling of 2026-10-14: an older tool never misreads a
        Loop file of a newer format, and a loop.md without Format: 2 is
        refused the same way."""
        original = self.file()
        for replacement in ("Format: 3", "Format: 1", None):
            with self.subTest(format=replacement):
                text = original.replace("Format: 2\n", (replacement + "\n") if replacement else "")
                self.box.write(os.path.join(".scratch", "demo", "loop.md"), text)
                result = self.loop("show", "--slug", "demo")
                self.assertNotEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertIn("rerun Setup", result.text)


class SetTest(LoopTest):
    def setUp(self):
        LoopTest.setUp(self)
        self.new("demo", *ANSWERS, write=True)

    def test_set_changes_only_its_line_and_harness_never_writes(self):
        before = self.file()
        result = self.loop("set", "--slug", "demo", "--pr", "yes", "--harness", "codex", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertEqual(self.file(), before.replace("PR: ask at sign-off", "PR: yes"))
        self.assertIn("Harness: Claude Code\n", self.file())

    def test_harness_line_changes_the_harness(self):
        result = self.loop("set", "--slug", "demo", "--harness-line", "Codex", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertIn("Harness: Codex\n", self.file())
        self.assertIn("Harness file: harness-codex.md", self.loop("show", "--slug", "demo").lines)

    def test_a_harness_correction_asks_the_fresh_coder_question_again(self):
        """Start-Loop's Harness correction: the corrected Harness's Fresh Coder
        recommendation and limit, asked once more before the write."""
        before = self.file()
        result = self.loop("set", "--slug", "demo", "--harness-line", "Codex")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(self.file(), before)
        question = [line for line in result.lines if line.startswith("Question 1, Fresh Coder")][0]
        self.assertIn('"Never" (recommended)', question)
        self.assertNext(result, "--harness-line Codex", '--fresh-coder "<answer>"', "--write")

    def test_set_without_write_changes_nothing(self):
        before = self.file()
        result = self.loop("set", "--slug", "demo", "--minors", "leave")
        self.assertEqual(result.code, 0, result)
        self.assertNext(result, "--write")
        self.assertEqual(self.file(), before)

    def test_set_writes_a_missing_line_in_its_place(self):
        self.box.write(os.path.join(".scratch", "demo", "loop.md"), self.file().replace("Minors: fix\n", ""))
        self.loop("set", "--slug", "demo", "--minors", "leave", "--write")
        lines = self.file().split("\n")
        self.assertEqual(lines[lines.index("Feature branch: demo") + 1], "Minors: leave")

    def test_set_refuses_the_identity_lines(self):
        before = self.file()
        for option in ("--feature", "--base-branch", "--feature-branch", "--base", "--branch"):
            with self.subTest(option=option):
                result = self.loop("set", "--slug", "demo", option, "other", "--write")
                self.assertNotEqual(result.code, 0, result)
                self.assertContract(result)
        self.assertEqual(self.file(), before)

    def test_set_refuses_a_value_outside_the_accepted_values(self):
        before = self.file()
        for option, value in (("--minors", "Fix"), ("--pr", "maybe"), ("--fresh-coder", "over 0k"),
                              ("--harness-line", "claude-code")):
            with self.subTest(option=option):
                result = self.loop("set", "--slug", "demo", option, value, "--write")
                self.assertNotEqual(result.code, 0, result)
        self.assertEqual(self.file(), before)


class FindTest(LoopTest):
    def test_the_loop_of_the_checked_out_branch(self):
        self.box.write_loop("one", branch="feat-one")
        self.box.write_loop("two", branch="feat-two")
        self.box.git("checkout", "-q", "-b", "feat-two")
        result = self.loop("show")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.lines[0], "Slug: two")

    def test_the_only_open_loop(self):
        self.box.write_loop("one")
        self.box.write_loop("old", states=("open", "closed"))
        result = self.loop("show")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.lines[0], "Slug: one")

    def test_two_open_loops_and_neither_branch_checked_out_refuse(self):
        self.box.write_loop("one")
        self.box.write_loop("two")
        for args in (("show",), ("set", "--pr", "no", "--write")):
            with self.subTest(args=args):
                result = self.loop(*args)
                self.assertNotEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertIn("one", result.text)
                self.assertIn("two", result.text)
                self.assertNext(result, "--slug")

    def test_no_loop_refuses(self):
        result = self.loop("show")
        self.assertNotEqual(result.code, 0, result)
        self.assertNext(result, "--slug")

    def test_slug_names_a_loop_that_is_not_there(self):
        self.box.write_loop("one")
        result = self.loop("show", "--slug", "two")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn(".scratch/two/ does not exist", result.text)

    def test_a_root_loop_file_refuses_every_command(self):
        self.box.write_loop("demo")
        self.box.write("LOOP.md", "# VDD Loop\n\nFeature: demo\nTracker: .scratch/demo/\n")
        for args in (["new", "--slug", "other", "--harness", "claude-code"],
                     ["show", "--slug", "demo"], ["show"],
                     ["set", "--slug", "demo", "--pr", "no", "--write"]):
            with self.subTest(args=args):
                result = self.loop(*args)
                self.assertNotEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertEqual(result.tells(), [ROOT_FIX])
        self.assertIn("PR: ask at sign-off", self.file())


if __name__ == "__main__":
    unittest.main()
