"""The loop command group, driven from outside: new, show and set, and
finding the loop."""

import os
import unittest

from vddtest import ToolTest

ANSWERS = ["--minors", "fix", "--pr", "ask at sign-off"]
SUMMARY = [
    "The loop's slug is demo. The Orchestrator's launch line will carry it.",
    "The Harness is Claude Code. If that is wrong, say so now, before the Planner starts.",
    "You can ask the Orchestrator to respawn any hosted Role at any round.",
]
NEXT_AFTER_NEW = (
    "Next: Relay every Tell the user verbatim line above unchanged, then invoke vdd-planner as your skill says. "
    "The loop's slug is demo: pass --slug demo on every VDD tool call from here on."
)
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
                         ["Question 1, feature branch", "Question 2, Minors", "Question 3, PR"])
        self.assertNotIn("Fresh Coder", result.text)
        self.assertNotIn("--fresh-coder", result.last)
        self.assertNext(result, "loop new --slug demo", "--write")

    def test_write_writes_the_loop_file_and_the_state_file(self):
        result = self.new("demo", *ANSWERS, write=True)
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertEqual(
            self.file(),
            "# VDD Loop\n\nFormat: 2\nFeature: demo\nBase branch: main\nFeature branch: demo\nMinors: fix\n"
            "PR: ask at sign-off\nHarness: Claude Code\n",
        )
        self.assertEqual(self.file(name="loop-state"), "vdd loop-state 2\nloop open\n")
        self.assertNext(result, "--slug demo")

    def test_write_prints_the_summary_as_tell_lines_and_relays_them_in_next(self):
        """A7: in all 7 Claude Code Start-Loops since 2026-10-17 the model
        wrote the closing summary into its thinking and never showed the user
        the Tell lines. The tool now prints the summary's facts itself, and
        the Next: line names relaying them."""
        result = self.new("demo", "--minors", "fix", "--pr", "manual", write=True)
        self.assertEqual(result.tells(), SUMMARY)
        self.assertEqual(result.last, NEXT_AFTER_NEW)
        for tell in SUMMARY:
            self.assertIn('Tell the user verbatim: "%s"' % tell, result.lines)
        self.assertLess(result.lines.index("Harness: Claude Code"), result.lines.index(
            'Tell the user verbatim: "%s"' % SUMMARY[0]))

    def test_the_summary_names_the_harness_label(self):
        result = self.new("demo", *ANSWERS, harness="codex", write=True)
        self.assertEqual(result.tells()[1],
                         "The Harness is Codex. If that is wrong, say so now, before the Planner starts.")

    def test_write_needs_every_answer(self):
        result = self.new("demo", "--minors", "fix", write=True)
        self.assertNotEqual(result.code, 0, result)
        self.assertFalse(os.path.exists(self.box.path(".scratch", "demo")))

    def test_the_respawn_question_left_loop_new(self):
        """The Respawn policy moved into the state file, asked at Model
        approval: loop new takes no --fresh-coder, in a dry run or with
        --write."""
        for extra in ((), ("--write",)):
            with self.subTest(extra=extra):
                result = self.new("demo", *(ANSWERS + ["--fresh-coder", "never"] + list(extra)))
                self.assertNotEqual(result.code, 0, result)
                self.assertIn("Unknown option: --fresh-coder", result.text)
        self.assertFalse(os.path.exists(self.box.path(".scratch", "demo")))

    def test_answers_given_are_not_asked(self):
        result = self.new("demo", "--branch", "feat/demo", "--minors", "leave")
        names = [line.split(":")[0] for line in result.lines if line.startswith("Question ")]
        self.assertEqual(names, ["Question 1, PR"])

    def test_the_harness_line_is_the_display_name(self):
        for harness, label in (("codex", "Codex"), ("copilot-cli", "Copilot CLI"), ("generic", "Generic")):
            with self.subTest(harness=harness):
                slug = "h-" + harness
                self.new(slug, *ANSWERS, harness=harness, write=True)
                self.assertIn("Harness: %s\n" % label, self.file(slug))

    def test_a_slug_outside_the_pattern_is_refused_with_the_pattern(self):
        """The slug check moved from Start-Loop's prose into the tool: the
        refusal names the pattern so the user fixes the slug in one try."""
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
        result = self.new("demo", "--minors", "Fix", "--pr", "yes", write=True)
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
            "Orchestrator": ["Feature", "Base branch", "Feature branch", "Minors", "PR", "Harness"],
            "PR-Author": ["Base branch", "Feature branch", "PR", "Harness"],
        }
        with open(self.box.path(".scratch", "demo", "loop-state"), "a") as handle:
            handle.write("code 1 reviewed signed-off - counts 0 0 0\n")
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
        """A missing line was reported as malformed. Each line reads as its
        default, with the right word, and the user is told."""
        defaults = {"Minors": "leave", "PR": "ask at sign-off", "Harness": "Generic"}
        bad = {"Minors": "maybe", "PR": "sometimes", "Harness": "Vim"}
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
        """An older tool never misreads a Loop file of a newer format, and a
        loop.md without Format: 2 is refused the same way."""
        original = self.file()
        for replacement in ("Format: 3", "Format: 1", None):
            with self.subTest(format=replacement):
                text = original.replace("Format: 2\n", (replacement + "\n") if replacement else "")
                self.box.write(os.path.join(".scratch", "demo", "loop.md"), text)
                result = self.loop("show", "--slug", "demo")
                self.assertNotEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertIn("rerun Setup", result.text)


class PRAuthorTest(LoopTest):
    def setUp(self):
        LoopTest.setUp(self)
        self.new("demo", *ANSWERS, write=True)

    def test_the_pr_author_waits_for_the_recorded_code_sign_off(self):
        """The PR-Author used to check that CODEREVIEW.md's first line was
        SIGNED OFF. The status line replaced it, so the tool checks the state
        file's code Sign-off."""
        for staged in ((), ("code 1 reviewed open 1 counts 0 1 0",)):
            with self.subTest(staged=staged):
                with open(self.box.path(".scratch", "demo", "loop-state"), "a") as handle:
                    handle.write("".join(line + "\n" for line in staged))
                result = self.loop("show", "--slug", "demo", "--role", "PR-Author")
                self.assertNotEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertIn("The code Loop is not signed off", result.text)
        with open(self.box.path(".scratch", "demo", "loop-state"), "a") as handle:
            handle.write("code 2 reviewed signed-off - counts 0 0 0\n")
        result = self.loop("show", "--slug", "demo", "--role", "PR-Author")
        self.assertEqual(result.code, 0, result)
        for line in ("Base branch: main", "Feature branch: demo", "PR: ask at sign-off", "Harness: Claude Code"):
            self.assertIn(line, result.lines)

    def test_every_other_role_and_no_role_work_before_the_sign_off(self):
        for role in (None, "Planner", "Plan-Reviewer", "Coder", "Code-Reviewer", "Orchestrator"):
            with self.subTest(role=role):
                extra = ["--role", role] if role else []
                result = self.loop("show", "--slug", "demo", *extra)
                self.assertEqual(result.code, 0, result)


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

    def test_set_refuses_fresh_coder(self):
        """The Coder's respawn line left the Loop file: loop set refuses it as
        an unknown option and writes nothing."""
        before = self.file()
        result = self.loop("set", "--slug", "demo", "--fresh-coder", "never", "--write")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("Unknown option: --fresh-coder", result.text)
        self.assertEqual(self.file(), before)

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
        for option, value in (("--minors", "Fix"), ("--pr", "maybe"), ("--harness-line", "claude-code")):
            with self.subTest(option=option):
                result = self.loop("set", "--slug", "demo", option, value, "--write")
                self.assertNotEqual(result.code, 0, result)
        self.assertEqual(self.file(), before)


class VersionOneTest(LoopTest):
    """A loop 0.16.0-beta.3 started: state file version 1 and a Loop file with
    the Coder's respawn line. Every loop command still reads it."""

    def setUp(self):
        LoopTest.setUp(self)
        text = (
            "# VDD Loop\n\nFormat: 2\nFeature: demo\nBase branch: main\nFeature branch: demo\nMinors: fix\n"
            "PR: ask at sign-off\nFresh Coder: over 300k\nHarness: Claude Code\n"
        )
        self.box.write_loop("demo", text=text, version=1)

    def test_show_reads_it_and_ignores_the_respawn_line(self):
        result = self.loop("show", "--slug", "demo")
        self.assertEqual(result.code, 0, result)
        self.assertIn("State: open", result.lines)
        self.assertFalse([line for line in result.lines if line.startswith("Fresh Coder")], result)
        self.assertEqual(result.tells(), [])

    def test_close_then_reopen_work(self):
        closed = self.loop("close", "--slug", "demo", "--write")
        self.assertEqual(closed.code, 0, closed)
        self.assertIn("State: closed", self.loop("show", "--slug", "demo").lines)
        reopened = self.loop("reopen", "--slug", "demo", "--write")
        self.assertEqual(reopened.code, 0, reopened)
        self.assertIn("State: open", self.loop("show", "--slug", "demo").lines)
        self.assertEqual(self.file(name="loop-state"), "vdd loop-state 1\nloop open\nloop closed\nloop open\n")

    def test_a_newer_state_version_is_refused_as_out_of_date(self):
        self.box.write(os.path.join(".scratch", "demo", "loop-state"), "vdd loop-state 3\nloop open\n")
        result = self.loop("show", "--slug", "demo")
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("out of date", result.text)
        self.assertIn("rerun Setup", result.text)


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

    def test_a_command_run_below_the_repository_root_acts_on_the_loop(self):
        """A Role's shell can be left in a subdirectory after a cd, the
        tracker directory included. There a check for LOOP.md by path also
        matched the loop's own loop.md on a case-insensitive file system, so
        loop close refused and told the user to delete LOOP.md."""
        self.box.write_loop("demo")
        os.makedirs(self.box.path("src"))
        for where in (self.box.path(".scratch", "demo"), self.box.path("src")):
            with self.subTest(where=os.path.relpath(where, self.box.proj)):
                shown = self.box.run("loop", "show", "--slug", "demo", cwd=where)
                self.assertEqual(shown.code, 0, shown)
                self.assertEqual(shown.lines[0], "Slug: demo")
                self.assertEqual(self.box.run("loop", "show", cwd=where).lines[0], "Slug: demo")
                closed = self.box.run("loop", "close", "--slug", "demo", "--write", cwd=where)
                self.assertEqual(closed.code, 0, closed)
                self.assertEqual(closed.tells(), [])
                self.assertTrue(self.file(name="loop-state").endswith("loop closed\n"))
                reopened = self.box.run("loop", "reopen", "--slug", "demo", "--write", cwd=where)
                self.assertEqual(reopened.code, 0, reopened)
        self.assertEqual(sorted(os.listdir(self.box.path(".scratch"))), ["demo"])
        self.assertFalse(os.path.exists(self.box.path("src", ".scratch")))

    def test_only_a_file_named_exactly_loop_md_in_capitals_refuses(self):
        """A case-insensitive file system answers a path test for LOOP.md
        with any spelling of it, so the check reads the directory listing."""
        self.box.write_loop("demo")
        self.box.write("Loop.md", "notes\n")
        result = self.loop("show", "--slug", "demo")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.tells(), [])



class LeftoverTest(LoopTest):
    def question(self, result):
        return [line for line in result.lines if line.startswith("Question 1, leftover")][0]

    def test_an_open_loop_offers_three_answers_and_continue_writes_nothing(self):
        self.box.write_loop("demo")
        self.box.write(os.path.join(".scratch", "demo", "spec.md"), "spec\n")
        before = self.tree()
        result = self.new()
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("open loop", result.text)
        question = self.question(result)
        for answer in ("Continue the earlier Workflow", "Start fresh on this slug", "Use a different slug"):
            self.assertIn(answer, question)
        self.assertNext(result, "--leftover continue", "loop aside --slug demo --write")
        state = self.file(name="loop-state")
        result = self.new("demo", "--leftover", "continue")
        self.assertEqual(result.code, 0, result)
        self.assertNext(result, "vdd-planner", "--slug demo")
        self.assertEqual(self.tree(), before)
        self.assertEqual(self.file(name="loop-state"), state)

    def test_the_report_names_only_the_work_the_directory_holds(self):
        """The report said "Its Spec, Tickets and review files are still in
        there" of a directory holding only the Loop file, so the user chose
        between continue and start fresh on files that were not there."""
        self.box.write_loop("empty")
        self.assertIn("It holds no Spec, Tickets or review files.", self.new("empty").text)
        self.box.write_loop("demo")
        for name in ("spec.md", "issues/01-a.md", "issues/02-b.md", "PLAN-REVIEW.md"):
            self.box.write(os.path.join(".scratch", "demo", name), "x\n")
        result = self.new()
        self.assertIn("It holds spec.md, 2 Tickets in issues/, PLAN-REVIEW.md.", result.text)
        self.assertNotIn("FIXES.md", result.text)

    def test_write_without_continue_refuses_on_any_existing_directory(self):
        for setup in ("open", "closed", "files"):
            with self.subTest(setup=setup):
                slug = "d-" + setup
                if setup == "files":
                    self.box.write(os.path.join(".scratch", slug, "spec.md"), "spec\n")
                else:
                    self.box.write_loop(slug, states=("open",) if setup == "open" else ("open", "closed"))
                before = {name: self.box.read(name) for name in self.tree()}
                result = self.new(slug, *ANSWERS, write=True)
                self.assertNotEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertEqual({name: self.box.read(name) for name in self.tree()}, before)

    def test_a_closed_loop_offers_start_fresh_or_a_different_slug_only(self):
        self.box.write_loop("demo", states=("open", "closed"))
        result = self.new()
        self.assertEqual(result.code, 0, result)
        question = self.question(result)
        self.assertNotIn("Continue", question)
        self.assertIn("Start fresh on this slug", question)
        self.assertIn("Use a different slug", question)
        self.assertNotIn("--leftover continue", result.last)
        self.assertNext(result, "loop aside --slug demo --write")
        refused = self.new("demo", "--leftover", "continue", *ANSWERS, write=True)
        self.assertNotEqual(refused.code, 0, refused)
        self.assertIn("closed loop", refused.text)

    def test_a_directory_with_no_state_file_continues_keeping_every_file(self):
        self.box.write(os.path.join(".scratch", "demo", "spec.md"), "spec\n")
        self.box.write(os.path.join(".scratch", "demo", "issues", "01-x.md"), "ticket\n")
        result = self.new()
        self.assertEqual(result.code, 0, result)
        question = self.question(result)
        for answer in ("Continue the earlier Workflow", "Start fresh on this slug", "Use a different slug"):
            self.assertIn(answer, question)
        asked = self.new("demo", "--leftover", "continue")
        self.assertEqual(asked.code, 0, asked)
        self.assertTrue(any(line.startswith("Question 3, PR") for line in asked.lines), asked)
        self.assertNext(asked, "--leftover continue", "--write")
        written = self.new("demo", "--leftover", "continue", *ANSWERS, write=True)
        self.assertEqual(written.code, 0, written)
        self.assertEqual(self.box.read(os.path.join(".scratch", "demo", "spec.md")), "spec\n")
        self.assertEqual(self.box.read(os.path.join(".scratch", "demo", "issues", "01-x.md")), "ticket\n")
        self.assertIn("Format: 2\n", self.file())
        self.assertEqual(self.file(name="loop-state"), "vdd loop-state 2\nloop open\n")
        self.assertEqual(written.tells(), SUMMARY)
        self.assertEqual(written.last, NEXT_AFTER_NEW)

    def test_a_damaged_state_file_reads_as_a_directory_with_no_state_file(self):
        """A damaged loop-state stopped loop new and loop aside alike, leaving
        the slug no way out."""
        self.box.write_loop("demo")
        self.box.write(os.path.join(".scratch", "demo", "loop-state"), "junk\n")
        result = self.new()
        self.assertEqual(result.code, 0, result)
        question = self.question(result)
        for answer in ("Continue the earlier Workflow", "Start fresh on this slug", "Use a different slug"):
            self.assertIn(answer, question)
        written = self.new("demo", "--leftover", "continue", *ANSWERS, write=True)
        self.assertEqual(written.code, 0, written)
        self.assertEqual(self.file(name="loop-state"), "vdd loop-state 2\nloop open\n")
        self.box.write(os.path.join(".scratch", "demo", "loop-state"), "junk\n")
        moved = self.loop("aside", "--slug", "demo", "--write")
        self.assertEqual(moved.code, 0, moved)
        self.assertIn(".scratch/demo-2/", moved.text)
        self.assertFalse(os.path.exists(self.box.path(".scratch", "demo")))

    def test_continue_appends_to_a_readable_state_file_and_refuses_a_newer_one(self):
        """Continue rewrote a readable loop-state whole, losing its history,
        and overwrote a newer tool's."""
        self.box.write(os.path.join(".scratch", "demo", "loop-state"), "vdd loop-state 2\nloop open\nloop closed\n")
        written = self.new("demo", "--leftover", "continue", *ANSWERS, write=True)
        self.assertEqual(written.code, 0, written)
        self.assertEqual(self.file(name="loop-state"), "vdd loop-state 2\nloop open\nloop closed\nloop open\n")
        newer = "vdd loop-state 3\nloop closed\nrounds 3\n"
        self.box.write(os.path.join(".scratch", "later", "loop-state"), newer)
        refused = self.new("later", "--leftover", "continue", *ANSWERS, write=True)
        self.assertNotEqual(refused.code, 0, refused)
        self.assertEqual(self.box.read(os.path.join(".scratch", "later", "loop-state")), newer)
        self.assertFalse(os.path.exists(self.box.path(".scratch", "later", "loop.md")))

    def test_continue_with_no_directory_is_refused(self):
        result = self.new("demo", "--leftover", "continue", *ANSWERS, write=True)
        self.assertNotEqual(result.code, 0, result)
        self.assertFalse(os.path.exists(self.box.path(".scratch", "demo")))


class AsideTest(LoopTest):
    def test_aside_takes_the_lowest_free_n_and_deletes_nothing(self):
        """The leftover-tracker reference: "Delete nothing on any of the
        three answers", and the move takes the lowest n from 2 that is free."""
        self.box.write(os.path.join(".scratch", "demo", "spec.md"), "first\n")
        result = self.loop("aside", "--slug", "demo", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn(".scratch/demo-2/", result.text)
        self.assertEqual(self.box.read(os.path.join(".scratch", "demo-2", "spec.md")), "first\n")
        self.assertFalse(os.path.exists(self.box.path(".scratch", "demo")))
        self.box.write(os.path.join(".scratch", "demo", "spec.md"), "second\n")
        result = self.loop("aside", "--slug", "demo", "--write")
        self.assertIn(".scratch/demo-3/", result.text)
        self.assertEqual(self.box.read(os.path.join(".scratch", "demo-2", "spec.md")), "first\n")
        self.assertEqual(self.box.read(os.path.join(".scratch", "demo-3", "spec.md")), "second\n")
        self.assertEqual(self.tree(), [os.path.join(".scratch", "demo-2", "spec.md"),
                                       os.path.join(".scratch", "demo-3", "spec.md")])

    def test_aside_without_write_moves_nothing(self):
        self.box.write_loop("demo")
        before = self.tree()
        result = self.loop("aside", "--slug", "demo")
        self.assertEqual(result.code, 0, result)
        self.assertNext(result, "--write")
        self.assertEqual(self.tree(), before)

    def test_aside_closes_an_open_loop_and_deletes_its_armed_files(self):
        self.box.write_loop("demo")
        self.box.write(os.path.join(".scratch", "demo", "codex-armed-T1"), "vdd codex-armed 1\nPlanner 0\n")
        self.box.write(os.path.join(".scratch", "demo", "doorbells"), "# vdd doorbells 1\n")
        result = self.loop("aside", "--slug", "demo", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertFalse(os.path.exists(self.box.path(".scratch", "demo-2", "codex-armed-T1")))
        self.assertTrue(os.path.exists(self.box.path(".scratch", "demo-2", "doorbells")))
        self.assertIn("State: closed", self.loop("show", "--slug", "demo-2").lines)
        self.assertNotEqual(self.loop("show").code, 0)

    def test_the_new_loop_wins_on_its_branch_and_two_closed_ones_refuse(self):
        self.box.write_loop("demo")
        self.loop("aside", "--slug", "demo", "--write")
        self.box.git("checkout", "-q", "-b", "demo")
        result = self.new("demo", "--base", "main", *ANSWERS, write=True)
        self.assertEqual(result.code, 0, result)
        self.assertEqual(self.loop("show").lines[0], "Slug: demo")
        self.loop("aside", "--slug", "demo", "--write")
        refused = self.loop("show")
        self.assertNotEqual(refused.code, 0, refused)
        self.assertIn("demo-2", refused.text)
        self.assertIn("demo-3", refused.text)


class CloseTest(LoopTest):
    def setUp(self):
        LoopTest.setUp(self)
        self.new("demo", *ANSWERS, write=True)

    def test_help_lists_close_reopen_and_aside(self):
        text = self.loop("--help").text
        for command in ("loop close", "loop reopen", "loop aside"):
            self.assertIn(command, text)
        self.assertIn("--slug", self.box.run("doorbell", "--help").text)

    def test_close_and_reopen_append_to_the_state_file(self):
        result = self.loop("close", "--slug", "demo", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertEqual(self.file(name="loop-state"), "vdd loop-state 2\nloop open\nloop closed\n")
        self.assertIn("State: closed", self.loop("show", "--slug", "demo").lines)
        result = self.loop("reopen", "--slug", "demo", "--write")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(self.file(name="loop-state"), "vdd loop-state 2\nloop open\nloop closed\nloop open\n")
        self.assertIn("State: open", self.loop("show", "--slug", "demo").lines)

    def test_close_without_write_and_twice_change_nothing(self):
        before = self.file(name="loop-state")
        self.assertNext(self.loop("close", "--slug", "demo"), "--write")
        self.assertEqual(self.file(name="loop-state"), before)
        self.loop("close", "--slug", "demo", "--write")
        closed = self.file(name="loop-state")
        result = self.loop("close", "--slug", "demo", "--write")
        self.assertIn("already closed", result.text)
        self.assertEqual(self.file(name="loop-state"), closed)

    def test_a_closed_loop_is_not_the_only_open_loop_and_slug_still_reaches_it(self):
        self.loop("close", "--slug", "demo", "--write")
        self.assertNotEqual(self.loop("show").code, 0)
        self.assertEqual(self.loop("show", "--slug", "demo").code, 0)

    def test_close_deletes_the_codex_armed_files(self):
        for name in ("codex-armed-T1", "codex-armed-T2"):
            self.box.write(os.path.join(".scratch", "demo", name), "vdd codex-armed 1\nPlanner 0\n")
        self.box.write(os.path.join(".scratch", "demo", "doorbells"), "# vdd doorbells 1\n")
        self.loop("close", "--slug", "demo", "--write")
        left = sorted(os.listdir(self.box.path(".scratch", "demo")))
        self.assertEqual(left, ["doorbells", "loop-state", "loop.md"])

    def test_close_deletes_a_claim_marker_with_the_armed_files(self):
        """A claim marker a killed Codex hook left would block the Session's
        waits of a reopened loop; closing the loop removes it with the armed
        file, printing only the armed file."""
        self.box.write(os.path.join(".scratch", "demo", "codex-armed-T1"), "vdd codex-armed 1\nPlanner 0\n")
        self.box.write(os.path.join(".scratch", "demo", "codex-claim-T1"), "")
        result = self.loop("close", "--slug", "demo", "--write")
        self.assertIn("Deleted the Codex armed file codex-armed-T1.", result.lines)
        self.assertNotIn("codex-claim", result.text)
        self.assertEqual(sorted(os.listdir(self.box.path(".scratch", "demo"))), ["loop-state", "loop.md"])


@unittest.skipIf(os.name == "nt", "a POSIX shell script stands in for git")
class PreflightTest(LoopTest):
    def stub(self, ls_remote_code=0):
        """A git on PATH that runs the real one, except for ls-remote, which
        prints fatal: failed to store and exits with ls_remote_code; and a gh
        that passes auth status."""
        import shutil
        real = shutil.which("git")
        bin_dir = os.path.join(self.box.root, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        git = os.path.join(bin_dir, "git")
        with open(git, "w") as handle:
            handle.write(
                "#!/bin/sh\n"
                "if [ \"$1\" = ls-remote ]; then echo 'fatal: failed to store' >&2; exit %d; fi\n"
                "exec '%s' \"$@\"\n" % (ls_remote_code, real)
            )
        os.chmod(git, 0o755)
        gh = os.path.join(bin_dir, "gh")
        with open(gh, "w") as handle:
            handle.write("#!/bin/sh\nexit 0\n")
        os.chmod(gh, 0o755)
        return self.box.env(PATH=bin_dir + os.pathsep + os.environ.get("PATH", ""))

    def write_yes(self, env, slug="demo"):
        return self.box.run("loop", "new", "--slug", slug, "--harness", "claude-code", "--minors", "fix",
                            "--pr", "yes", "--write", env=env)

    def test_the_push_check_judges_the_exit_code_only(self):
        """9e820de: git ls-remote printed fatal: failed to store on a call
        that exited 0, and a check that read stderr reported a working remote
        as broken."""
        self.box.git("remote", "add", "origin", "https://github.com/example/repo.git")
        result = self.write_yes(self.stub(0))
        self.assertEqual(result.code, 0, result)
        self.assertIn("Preflight, can push, remote origin: passed.", result.lines)
        self.assertIn("Preflight, can open a PR, remote origin: passed.", result.lines)
        self.assertEqual(result.tells(), SUMMARY)

    def test_a_failed_check_warns_and_still_writes(self):
        self.box.git("remote", "add", "origin", "https://example.com/repo.git")
        result = self.write_yes(self.stub(2))
        self.assertEqual(result.code, 0, result)
        tells = result.tells()
        self.assertEqual(len(tells), 5, result)
        self.assertIn("can push", tells[0])
        self.assertIn("can open a PR", tells[1])
        self.assertEqual(tells[2:], SUMMARY)
        self.assertEqual(result.last, NEXT_AFTER_NEW)
        self.assertIn("PR: yes\n", self.file())

    def test_no_preflight_unless_pr_yes(self):
        result = self.new("demo", *ANSWERS, write=True)
        self.assertNotIn("Preflight", result.text)

    def test_the_remote_the_base_branch_tracks_else_the_single_else_origin(self):
        env = self.stub(0)
        self.box.git("remote", "add", "upstream", "https://github.com/example/up.git")
        result = self.write_yes(env, "one")
        self.assertIn("Preflight, can push, remote upstream: passed.", result.lines)
        self.box.git("remote", "add", "fork", "https://github.com/example/fork.git")
        result = self.write_yes(env, "two")
        self.assertIn("Preflight, can push, remote origin: failed (no remote origin is configured).", result.lines)
        self.box.git("config", "branch.main.remote", "fork")
        result = self.write_yes(env, "three")
        self.assertIn("Preflight, can push, remote fork: passed.", result.lines)


if __name__ == "__main__":
    unittest.main()
