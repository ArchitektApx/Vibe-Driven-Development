"""The entry, --help, the unknown command and the output contract."""

import os
import shutil
import subprocess
import sys
import unittest

from vddtest import ENTRY, SCRIPTS, Sandbox, ToolTest

# Every command and the options it takes, as its unknown-option refusal lists
# them. An option another command of the group reads is refused here.
TAKES = {
    ("loop", "new"): "base branch harness leftover minors pr slug write",
    ("loop", "aside"): "harness slug write",
    ("loop", "show"): "harness role slug",
    ("loop", "set"): "base base-branch branch feature feature-branch harness harness-line minors pr slug write",
    ("loop", "fold"): "harness slug write",
    ("loop", "close"): "harness slug write",
    ("loop", "reopen"): "harness slug write",
    ("doorbell", "ring"): "harness role slug write",
    ("doorbell", "wait"): "harness role slug",
    ("doorbell", "take"): "harness pasted resumed role slug",
    ("pr", "check"): "harness slug",
    ("pr", "open"): "harness path slug write",
    ("coder", "start"): "slug write",
    ("coder", "check"): "slug write",
    ("review", "start"): "role slug write",
    ("review", "check"): "role slug write",
    ("review", "add"): "from slug write",
    ("wayfinder", "start"): "effort skill-dir",
    ("orchestrator", "start"): "harness slug",
    ("orchestrator", "return"): "harness role slug",
    ("orchestrator", "respawn"): "harness once policy role slug write",
    ("orchestrator", "tokens"): "harness role slug tokens",
    ("brainstorm", "start"): "page",
    ("brainstorm", "show"): "idea",
    ("brainstorm", "find"): "text",
    ("brainstorm", "check"): "",
    ("brainstorm", "new"): "despite fog importance parent relate size slug summary title tldr write",
    ("brainstorm", "note"): "idea section text tick write",
    ("brainstorm", "set"): "decision fog idea importance reopen-when size status title tldr write",
    ("brainstorm", "move"): "set write",
    ("brainstorm", "split"): "idea part write",
    ("brainstorm", "merge"): "idea into reason reopen-when write",
    ("brainstorm", "rename"): "idea to write",
    ("brainstorm", "cleanup"): "idea older status write",
    ("brainstorm", "migrate"): "event write",
    ("setup",): "glossary-named harness listed user-answer write",
}


class EntryTest(ToolTest):
    def test_help_ends_with_next_and_exits_zero(self):
        result = self.box.run("--help")
        self.assertEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("VDD tool", result.text)

    def test_no_arguments_prints_the_help(self):
        self.assertEqual(self.box.run().text, self.box.run("--help").text)

    def test_unknown_command_names_rerun_setup(self):
        result = self.box.run("no-such-command")
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("rerun Setup", result.text)

    def test_an_option_before_its_command_names_the_order_not_setup(self):
        """A model that read "pass --slug on every call" as a global option
        ran `vdd.py --slug <slug> loop show`; told its copy was out of date,
        it ran Setup before retrying in the right order."""
        for argv in (["--slug", "demo", "loop", "show"], ["loop", "--slug", "demo", "show"],
                     ["doorbell", "--slug", "demo", "take"]):
            with self.subTest(argv=argv):
                result = self.box.run(*argv)
                self.assertNotEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertIn("Option before its command: --slug", result.text)
                self.assertIn("loop show --role <Role> --slug <slug>", result.last)
                self.assertNotIn("Setup", result.text)

    def test_a_value_that_swallowed_the_next_option_is_refused_with_the_reason(self):
        """Windows PowerShell 5.1 joins `--slug "C:\\dir\\" --role Coder` into
        one value `C:\\dir" --role Coder`; the Role then ran on a mangled
        value and read the wrong failure. The refusal names the shell and says
        to drop the trailing backslash."""
        result = self.box.run("loop", "show", "--slug", 'demo" --role Coder')
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("--slug's value holds '\" --role': demo\" --role Coder.", result.text)
        self.assertIn("Windows PowerShell 5.1", result.text)
        self.assertNext(result, "no value ending in a backslash")

    def test_a_value_that_only_mentions_a_word_that_is_no_option_is_text(self):
        """A value quoting a command, such as `git log" --oneline`, holds
        `" --word` for a word the command does not take; refusing it as
        PowerShell's mangling would reject text a Role means."""
        result = self.box.run("loop", "show", "--slug", 'demo" --oneline')
        self.assertNotIn("PowerShell", result.text)
        self.assertNotIn("Unknown option", result.text)

    def test_a_value_option_given_twice_is_refused_and_writes_nothing(self):
        """Red team F10, D12: a value option given twice kept the last value,
        so a command meant for one slug ran on the other without a word."""
        self.box.init_git()
        result = self.box.run("loop", "new", "--slug", "a", "--slug", "b", "--harness", "claude-code", "--write")
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("--slug is given twice (a, then b); this command takes it once.", result.text)
        self.assertFalse(os.path.exists(self.box.path(".scratch")))

    def test_an_unknown_option_lists_what_the_command_takes_and_the_closest(self):
        """A mistyped option sent the Role to --help for the spelling; the
        refusal lists the options and names the closest one."""
        result = self.box.run("loop", "show", "--rol", "Coder")
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("Unknown option: --rol", result.lines)
        self.assertIn("This command takes: --harness, --role, --slug.", result.lines)
        self.assertIn("Closest: --role.", result.lines)
        self.assertNext(result, "again with --role")
        self.assertNotIn("rerun Setup", result.text)

    def test_an_unknown_option_with_none_close_says_to_rerun_setup(self):
        """An option this copy lacks, written by a newer skill, has no close
        spelling: the refusal tells the Role to have the user rerun Setup."""
        result = self.box.run("loop", "show", "--fresh-coder")
        self.assertNotEqual(result.code, 0, result)
        self.assertIn("Unknown option: --fresh-coder", result.lines)
        self.assertIn("This command takes: --harness, --role, --slug.", result.lines)
        self.assertNotIn("Closest", result.text)
        self.assertNext(result, "tell the user to rerun Setup")

    def test_each_command_takes_only_its_own_options(self):
        """Every command of a group took every option of the group and
        dropped the ones it does not read without a word: `loop new
        --harness-line Codex` wrote the Loop file's Harness: line from
        --harness. Each command now lists exactly its own options."""
        for command, takes in TAKES.items():
            with self.subTest(command=" ".join(command)):
                result = self.box.run(*command, "--no-such-option-here")
                self.assertNotEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertEqual(result.lines[0], "Unknown option: --no-such-option-here", result)
                expected = ("This command takes: %s." % ", ".join("--" + o for o in takes.split()) if takes
                            else "This command takes no options.")
                self.assertEqual(result.lines[1], expected, result)

    def groups(self):
        """The groups the top-level help lists."""
        lines = self.box.run("--help").lines
        listed = lines[lines.index("Command groups:") + 1:-1]
        return [line.split()[0] for line in listed if line.startswith("  ")]

    def test_every_group_in_the_list_reaches_its_own_help(self):
        """cli.load ended in an else that ran Setup, so a group added to the
        list without its import branch printed Setup's help as its own."""
        groups = self.groups()
        self.assertIn("setup", groups)
        self.assertIn("codex-stop", groups)
        for group in groups:
            with self.subTest(group=group):
                result = self.box.run(group, "--help")
                self.assertEqual(result.code, 0, result)
                self.assertContract(result)
                self.assertTrue(any(line.startswith((group + " ", group + ":")) for line in result.lines[:-1]),
                                result)

    def test_a_group_without_an_import_branch_is_a_named_error(self):
        """A group in the list that cli.load has no branch for fails at its
        first run, naming the group, instead of running another group."""
        copy = os.path.join(self.box.root, "copy")
        shutil.copytree(SCRIPTS, copy, ignore=shutil.ignore_patterns("__pycache__"))
        specs = os.path.join(copy, "vdd", "catalog", "specs.py")
        with open(specs, encoding="utf-8") as handle:
            text = handle.read()
        anchor = "GROUPS = {\n"
        self.assertIn(anchor, text)
        with open(specs, "w", encoding="utf-8") as handle:
            handle.write(text.replace(anchor, anchor + '    "zz-new": "A group with no branch.",\n', 1))
        result = self.box.run("zz-new", "--help", entry=os.path.join(copy, "vdd.py"))
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        self.assertIn("NoGroupBranch: cli.load has no branch for the group zz-new", result.lines[0])

    def test_output_is_utf8_with_lf_whatever_the_console(self):
        """Printed through sys.stdout.buffer as UTF-8 with LF, every CR
        removed: printed through sys.stdout, a non-ASCII line reaches a
        Windows console in its code page as different characters, or raises."""
        result = self.box.run("café\r\nx", env=self.box.env(PYTHONIOENCODING="cp1252"))
        self.assertIn("Unknown command: café x".encode("utf-8"), result.data)
        self.assertContract(result)

    def test_a_closed_output_pipe_ends_quietly(self):
        """`vdd.py loop --help | true` printed a traceback: the BrokenPipeError
        was caught as a file error, whose refusal wrote to the closed pipe
        again, and the interpreter's flush at exit printed "Exception
        ignored". On Windows the write fails as EINVAL instead, with the same
        tracebacks. The pipe here is closed before the tool's first line."""
        read_end, write_end = os.pipe()
        os.close(read_end)
        try:
            proc = subprocess.run(
                [sys.executable, ENTRY, "loop", "--help"],
                cwd=self.box.proj,
                stdin=subprocess.DEVNULL,
                stdout=write_end,
                stderr=subprocess.PIPE,
                env=self.box.env(),
                timeout=120,
            )
        finally:
            os.close(write_end)
        self.assertEqual(proc.stderr, b"")
        self.assertNotEqual(proc.returncode, 0)

    def test_below_python_39_prints_one_line_and_exits_non_zero(self):
        """The entry parses on any Python 3 and checks the version before any
        other import. The matrix has no Python below 3.9, so the entry runs
        with sys.version_info replaced before its check."""
        code = (
            "import runpy, sys\n"
            "sys.version_info = (3, 8, 18, 'final', 0)\n"
            "runpy.run_path(sys.argv[1], run_name='__main__')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code, ENTRY, "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.box.env(),
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.replace(b"\r", b""), b"VDD needs Python 3.9 or newer.\n")

    def test_the_entry_writes_no_bytecode(self):
        """The entry turns bytecode off before it imports the package, so no
        __pycache__ lands beside the tool in the Shared directory or the plugin
        root. The run clears PYTHONPYCACHEPREFIX: with the suite's prefix set,
        Python would write any bytecode there, and a tool that turned
        bytecode back on would still leave the copy clean."""
        copy = os.path.join(self.box.root, "copy")
        shutil.copytree(SCRIPTS, copy, ignore=shutil.ignore_patterns("__pycache__"))
        result = self.box.run("--help", entry=os.path.join(copy, "vdd.py"),
                              env=self.box.env(PYTHONPYCACHEPREFIX=None))
        self.assertEqual(result.code, 0, result)
        found = [d for d, dirs, files in os.walk(copy) if "__pycache__" in dirs]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
