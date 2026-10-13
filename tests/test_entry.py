"""The entry, --help, the unknown command and the output contract."""

import os
import shutil
import subprocess
import sys
import unittest

from vddtest import ENTRY, SCRIPTS, Sandbox, ToolTest


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

    def test_output_is_utf8_with_lf_whatever_the_console(self):
        """Printed through sys.stdout.buffer as UTF-8 with LF, every CR
        removed: a Windows console's code page mangled a non-ASCII line in the
        first attempt at this tool (drafts/python-scripts-carry.md)."""
        result = self.box.run("café\r\nx", env=self.box.env(PYTHONIOENCODING="cp1252"))
        self.assertIn("Unknown command: café x".encode("utf-8"), result.data)
        self.assertContract(result)

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
        __pycache__ lands beside the tool in the Shared directory or the
        plugin root (spec, "What the tool writes")."""
        copy = os.path.join(self.box.root, "copy")
        shutil.copytree(SCRIPTS, copy, ignore=shutil.ignore_patterns("__pycache__"))
        result = self.box.run("--help", entry=os.path.join(copy, "vdd.py"))
        self.assertEqual(result.code, 0, result)
        found = [d for d, dirs, files in os.walk(copy) if "__pycache__" in dirs]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
