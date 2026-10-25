"""The test sandbox itself: what every other test stands on."""

import os
import stat
import json
import subprocess
import sys
import unittest
import warnings

from vddtest import ENTRY, PLAN_SIGNED, REPO, Result, Sandbox, SceneTest, ToolTest, check_next


class CleanupTest(unittest.TestCase):
    def test_a_sandbox_with_read_only_git_objects_is_removed(self):
        """Prevents the Windows %TEMP% leak: git marks its objects read-only,
        Windows refuses to delete a read-only file, and every git-backed
        sandbox stayed behind. The removal raises no DeprecationWarning on
        Python 3.12 and later either."""
        box = Sandbox()
        try:
            box.init_git("main")
            box.commit("a.txt", "a\n", "feat: a")
            marked = box.write("read-only.txt", "x\n")
            os.chmod(marked, stat.S_IREAD)
            objects = [root for root, _, names in os.walk(os.path.join(box.proj, ".git", "objects")) if names]
            self.assertTrue(objects)
            # A read-only directory makes POSIX refuse the delete as well, so
            # the retry runs on every OS.
            os.chmod(objects[0], stat.S_IREAD | stat.S_IEXEC)
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                box.cleanup()
            self.assertFalse(os.path.exists(box.root))
        finally:
            if os.path.exists(box.root):
                for root, dirs, _ in os.walk(box.root):
                    for name in dirs:
                        os.chmod(os.path.join(root, name), stat.S_IRWXU)
                box.cleanup()


class CopiedSceneTest(SceneTest):
    """A scene staged once and copied per test, as the git-backed classes
    stage theirs."""

    def stage_scene(self):
        self.box.init_git("main")
        self.box.write(".gitignore", ".scratch/\n")
        self.box.git("add", ".gitignore")
        self.box.git("commit", "-q", "-m", "ignore")
        self.git("checkout", "-q", "-b", "demo")
        self.box.write_loop("demo", extra=(PLAN_SIGNED,))
        self.start = self.commit("a.txt", "a\n", "feat: a")
        self.where = self.box.root
        self.staged_by = type(self).__name__

    def test_the_copy_is_clean(self):
        """Prevents a copied scene whose index still holds the template's file
        stats: git would list every file as modified."""
        self.assertEqual(self.out("status", "--porcelain"), "")
        self.assertEqual(self.sha(), self.start)

    def test_nothing_in_the_copy_points_into_the_template(self):
        """Prevents a test that reads or writes another test's files through a
        path the template left behind."""
        template = SceneTest._scenes[type(self)][0].root
        self.assertNotEqual(template, self.box.root)
        self.assertEqual(self.where, self.box.root)
        for directory, _, names in os.walk(self.box.root):
            for name in names:
                with open(os.path.join(directory, name), "rb") as handle:
                    self.assertNotIn(template.encode("utf-8"), handle.read(), os.path.join(directory, name))

    def test_each_test_gets_its_own_copy(self):
        self.commit("b.txt", "b\n", "feat: b")
        self.assertNotEqual(self.sha(), self.start)


class OtherSceneTest(CopiedSceneTest):
    """A subclass stages a template of its own, keyed by its class."""

    def test_the_template_is_its_own(self):
        self.assertEqual(self.staged_by, "OtherSceneTest")


class PycacheTest(ToolTest):
    def test_a_sandbox_run_reads_bytecode_from_outside_the_repository(self):
        """Prevents a tool run that compiles its modules again on every call,
        or one that writes bytecode into the repository."""
        prefix = self.box.env()["PYTHONPYCACHEPREFIX"]
        self.assertTrue(os.path.isdir(prefix))
        self.assertFalse(os.path.realpath(prefix).startswith(os.path.realpath(REPO) + os.sep))
        self.assertTrue(any(name.endswith(".pyc") for _, _, names in os.walk(prefix) for name in names))


class NextCheckTest(ToolTest):
    def result(self, next_line):
        return Result(1, ("A line.\nNext: %s\n" % next_line).encode("utf-8"))

    def test_a_next_line_with_an_unknown_option_fails_naming_the_command(self):
        """Prevents a Next: line a Role cannot run: a printed command with an
        option its command does not take."""
        line = 'Run python3 "%s" loop show --slug demo --bogus x, then go on.' % ENTRY
        with self.assertRaises(AssertionError) as caught:
            check_next(self.box, self.result(line), "test_x")
        self.assertIn("loop show --slug demo --bogus x", str(caught.exception))
        self.assertIn("test_x", str(caught.exception))

    def test_a_command_that_parses_passes(self):
        line = 'Run python3 "%s" loop show --slug demo --role Coder in the foreground.' % ENTRY
        self.assertEqual(check_next(self.box, self.result(line)), [(ENTRY, ("loop", "show", "--slug", "demo",
                                                                             "--role", "Coder"))])

    def test_a_command_naming_a_missing_vdd_py_fails_naming_it(self):
        """Prevents a Next: line a Role cannot run: a command whose vdd.py
        path does not exist."""
        missing = os.path.join(self.box.root, "nowhere", "vdd.py")
        line = 'Run python3 "%s" loop show --slug demo, then go on.' % missing
        with self.assertRaises(AssertionError) as caught:
            check_next(self.box, self.result(line), "test_x")
        self.assertIn(missing, str(caught.exception))
        self.assertIn("test_x", str(caught.exception))

    def test_a_hook_reason_with_an_unknown_option_fails(self):
        """Prevents an unchecked Next: step in the Codex Stop hook's JSON
        reason, which the Role runs verbatim."""
        line = 'Run python3 "%s" doorbell take --role Orchestrator --bogus x' % ENTRY
        hook = Result(0, (json.dumps({"decision": "block", "reason": "A Doorbell is waiting. Next: " + line})
                          + "\n").encode("utf-8"))
        with self.assertRaises(AssertionError) as caught:
            check_next(self.box, hook, "test_x")
        self.assertIn("doorbell take --role Orchestrator --bogus x", str(caught.exception))

    def test_a_failed_command_fails_every_test_that_prints_it(self):
        """Prevents a broken command cached after its first failure, so only
        the first test that prints it fails."""
        line = 'Run python3 "%s" loop show --slug demo --bogus y, then go on.' % ENTRY
        for test in ("test_one", "test_two"):
            with self.assertRaises(AssertionError) as caught:
                check_next(self.box, self.result(line), test)
            self.assertIn(test, str(caught.exception))

    def test_a_popen_run_is_checked(self):
        """Prevents an unchecked Next: line from a run a test starts with
        Popen, as a background doorbell wait is."""
        line = 'Next: Run python3 "%s" loop show --slug demo --bogus z.' % ENTRY
        proc = subprocess.Popen([sys.executable, "-c", "print(%r)" % line], stdout=subprocess.PIPE)
        with self.assertRaises(AssertionError):
            self.box.finish(proc)

    def test_a_placeholder_value_is_checked_with_a_dummy_value(self):
        line = ('Ask the user, then run python3 "%s" orchestrator respawn --role Coder --policy "<answer>" '
                '--slug demo --write' % ENTRY)
        self.assertEqual(check_next(self.box, self.result(line)),
                         [(ENTRY, ("orchestrator", "respawn", "--role", "Coder", "--policy", "x", "--slug", "demo",
                                   "--write"))])

    def test_a_wrong_option_beside_a_placeholder_fails(self):
        """Prevents a printed command that holds a placeholder from going
        unchecked, so a misspelt option beside it reaches a Role."""
        line = ('Ask the user, then run python3 "%s" orchestrator respawn --role Coder --polcy "<answer>" '
                '--slug demo --write' % ENTRY)
        with self.assertRaises(AssertionError) as caught:
            check_next(self.box, self.result(line), "test_x")
        self.assertIn("orchestrator respawn --role Coder --polcy x", str(caught.exception))

    def test_a_wrong_option_on_a_plain_command_fails(self):
        """Prevents a printed command with an option its own command does not
        take, though another command of the group takes it."""
        line = 'Run python3 "%s" pr check --slug demo --harness claude-code --write.' % ENTRY
        with self.assertRaises(AssertionError) as caught:
            check_next(self.box, self.result(line), "test_x")
        self.assertIn("pr check --slug demo --harness claude-code --write", str(caught.exception))

    def test_every_command_of_a_line_is_checked(self):
        """Prevents a second command in one line going unchecked behind the
        first."""
        line = ('Run python3 "%s" loop show --slug demo, then run python3 "%s" loop fold --slug demo --harness '
                'claude-code --bogus.' % (ENTRY, ENTRY))
        with self.assertRaises(AssertionError) as caught:
            check_next(self.box, self.result(line), "test_x")
        self.assertIn("loop fold --slug demo --harness claude-code --bogus", str(caught.exception))

    def test_a_bare_brainstorm_command_is_checked(self):
        """Prevents a brainstorm line a Role cannot run: the group names its
        own commands without the tool's path."""
        self.assertEqual(check_next(self.box, self.result("Run brainstorm migrate --write, then brainstorm start.")),
                         [(ENTRY, ("brainstorm", "migrate", "--write")), (ENTRY, ("brainstorm", "start"))])
        with self.assertRaises(AssertionError) as caught:
            check_next(self.box, self.result("Run brainstorm migrate --wirte."), "test_x")
        self.assertIn("brainstorm migrate --wirte", str(caught.exception))

    def test_an_option_named_without_its_value_is_checked(self):
        self.assertEqual(check_next(self.box, self.result("For a decision use brainstorm set --decision; go on.")),
                         [(ENTRY, ("brainstorm", "set", "--decision", "x"))])

    def test_a_tell_line_and_the_resume_message_are_checked(self):
        """Prevents a command a Role relays or a hosted Role runs from the
        resume message going unchecked, as only the Next: line was."""
        tell = 'Tell the user verbatim: "Run brainstorm show --idaa a."'
        resume = 'Resume message:\nRun `python3 "%s" coder check --slug demo --wirte` first.' % ENTRY
        for text, fragment in ((tell, "brainstorm show --idaa a"), (resume, "coder check --slug demo --wirte")):
            with self.assertRaises(AssertionError) as caught:
                check_next(self.box, Result(0, (text + "\nNext: Go on.\n").encode("utf-8")), "test_x")
            self.assertIn(fragment, str(caught.exception))

    def test_a_placeholder_command_prose_and_a_line_with_no_command_are_skipped(self):
        group = 'Run python3 "%s" <group> --help for the group your skill names.' % ENTRY
        self.assertEqual(check_next(self.box, self.result(group)), [])
        self.assertEqual(check_next(self.box, self.result("Tell the user the brainstorm command reads it.")), [])
        self.assertEqual(check_next(self.box, self.result("Tell the user in one line.")), [])


if __name__ == "__main__":
    unittest.main()
