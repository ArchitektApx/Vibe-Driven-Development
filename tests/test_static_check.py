"""Seam 4: the static-check script against fixture trees staged in a
temporary git repository."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from vddtest import REPO

SCRIPT = os.path.join(REPO, ".github", "scripts", "check_shipped_code.py")

GOOD = {
    "README.md": "# x\n",
    "LICENSE": "MIT\n",
    ".gitignore": "LOOP.md\n",
    ".claude-plugin/plugin.json": "{}\n",
    "skills/x/SKILL.md": "---\nname: x\ndescription: x\n---\n",
    "skills/x/agents/openai.yaml": "policy:\n  allow_implicit_invocation: false\n",
    "skills/x/scripts/vdd.py": "import sys\nfrom vdd.cli import main\nsys.exit(main(sys.argv[1:]))\n",
    "skills/x/scripts/vdd/__init__.py": "",
    "skills/x/scripts/vdd/cli.py": (
        "import os\nimport subprocess\nfrom . import out\nfrom .harness import codex\n"
        "def main(argv):\n    subprocess.run(['git', 'status'], shell=False)\n    return 0\n"
    ),
    "tests/test_x.py": "import socket\nimport json\n",
}


@unittest.skipIf(sys.version_info < (3, 10), "the static check needs Python 3.10 or newer (sys.stdlib_module_names)")
class StaticCheckTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="vdd-static-")
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.git("init", "-q")
        for path, text in GOOD.items():
            self.add(path, text)

    def git(self, *args):
        subprocess.run(
            ["git", "-c", "core.autocrlf=false"] + list(args),
            cwd=self.repo,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def add(self, path, data):
        full = os.path.join(self.repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(data.encode("utf-8") if isinstance(data, str) else data)
        self.git("add", "--", path)

    def check(self):
        proc = subprocess.run(
            [sys.executable, SCRIPT, self.repo],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace")

    def assertFails(self, needle):
        code, text = self.check()
        self.assertEqual(code, 1, text)
        self.assertIn(needle, text)

    def test_the_good_tree_passes_with_relative_imports(self):
        code, text = self.check()
        self.assertEqual(code, 0, text)

    def test_310_syntax_fails(self):
        self.add("skills/x/scripts/vdd/m.py", "match x:\n    case 1:\n        pass\n")
        self.assertFails("does not parse as Python 3.9")

    def test_a_non_stdlib_import_fails(self):
        self.add("skills/x/scripts/vdd/m.py", "import requests\n")
        self.assertFails("outside the standard library: requests")

    def test_shell_true_fails(self):
        self.add("skills/x/scripts/vdd/m.py", "import subprocess\nsubprocess.run('ls', shell=True)\n")
        self.assertFails("shell=True")

    def test_os_system_fails(self):
        self.add("skills/x/scripts/vdd/m.py", "import os\nos.system('ls')\n")
        self.assertFails("os.system")

    def test_os_popen_fails(self):
        self.add("skills/x/scripts/vdd/m.py", "from os import popen\n")
        self.assertFails("os.popen")

    def test_eval_fails(self):
        self.add("skills/x/scripts/vdd/m.py", "eval('1')\n")
        self.assertFails("eval()")

    def test_exec_fails(self):
        self.add("skills/x/scripts/vdd/m.py", "exec('1')\n")
        self.assertFails("exec()")

    def test_a_socket_import_fails(self):
        self.add("skills/x/scripts/vdd/m.py", "import socket\n")
        self.assertFails("network module: socket")

    def test_a_urllib_import_fails(self):
        self.add("skills/x/scripts/vdd/m.py", "from urllib.request import urlopen\n")
        self.assertFails("network module: urllib.request")

    def test_a_non_ascii_byte_fails(self):
        """A non-ASCII character in a printed message reaches a Windows console
        in the ANSI code page as a different character, or raises before
        Python 3.15 (drafts/python-scripts-carry.md)."""
        self.add("skills/x/scripts/vdd/m.py", "x = '\u201d'\n")
        self.assertFails("byte outside printable ASCII")

    def test_an_executable_file_fails(self):
        """Mode from the git index, so the fixture works on Windows too."""
        self.git("update-index", "--chmod=+x", "skills/x/scripts/vdd/cli.py")
        self.assertFails("mode 100755")

    def test_a_shebang_fails(self):
        self.add("skills/x/scripts/vdd/m.py", "#!/usr/bin/env python3\nx = 1\n")
        self.assertFails("shebang")

    def test_a_js_file_under_skills_fails(self):
        self.add("skills/x/scripts/helper.js", "console.log(1)\n")
        self.assertFails("file kind not allowed under skills/")

    def test_a_txt_file_at_the_root_fails(self):
        self.add("notes.txt", "x\n")
        self.assertFails("file kind not allowed: notes.txt")

    def test_gitignored_files_never_count(self):
        """The script reads git ls-files, so an untracked .py breaking every
        rule is not read: this checkout holds thousands under .scratch/."""
        path = os.path.join(self.repo, "skills", "x", "scripts", "vdd", "untracked.py")
        with open(path, "w") as handle:
            handle.write("import socket\neval('1')\n")
        code, text = self.check()
        self.assertEqual(code, 0, text)


if __name__ == "__main__":
    unittest.main()
