"""Shared helpers for the VDD tool's tests.

Every test but the Harness contract test drives the tool from outside: it
runs vdd.py as a subprocess in a temporary project, with a temporary home and
Shared directory, every relocation variable cleared, so no test reads the
real machine.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "skills", "vdd-setup", "scripts")
ENTRY = os.path.join(SCRIPTS, "vdd.py")
WINDOWS = os.name == "nt"

# Variables that move a store, the Shared directory or the home, or that
# name a Codex thread. Each test sets the ones it needs.
CLEARED = (
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_CODE_PLUGIN_CACHE_DIR",
    "CODEX_HOME",
    "COPILOT_HOME",
    "XDG_DATA_HOME",
    "LOCALAPPDATA",
    "CODEX_THREAD_ID",
    "HOME",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "VDD_WAIT_POLL_SECONDS",
    "VDD_WAIT_TIMEOUT_SECONDS",
    "PYTHONDONTWRITEBYTECODE",
)


class Result:
    def __init__(self, code, data):
        self.code = code
        self.data = data
        self.text = data.decode("utf-8")
        self.lines = self.text.split("\n")[:-1] if self.text.endswith("\n") else self.text.split("\n")

    @property
    def last(self):
        return self.lines[-1] if self.lines else ""

    def tells(self):
        prefix = 'Tell the user verbatim: "'
        return [line[len(prefix):-1] for line in self.lines if line.startswith(prefix)]

    def __repr__(self):
        return "exit %d\n%s" % (self.code, self.text)


class Sandbox:
    """A temporary home, Shared-directory base and project."""

    def __init__(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="vdd-test-"))
        self.home = os.path.join(self.root, "home")
        self.data = os.path.join(self.root, "data")
        self.proj = os.path.join(self.root, "proj")
        for path in (self.home, self.data, self.proj):
            os.makedirs(path)

    @property
    def shared(self):
        return os.path.join(self.data, "vdd")

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items() if k not in CLEARED}
        env["HOME"] = self.home
        env["USERPROFILE"] = self.home
        if WINDOWS:
            env["LOCALAPPDATA"] = self.data
        else:
            env["XDG_DATA_HOME"] = self.data
        for key, value in extra.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return env

    def run(self, *args, cwd=None, stdin=None, env=None, entry=ENTRY, timeout=120):
        proc = subprocess.run(
            [sys.executable, entry] + list(args),
            cwd=cwd or self.proj,
            input=stdin if stdin is not None else b"",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env if env is not None else self.env(),
            timeout=timeout,
        )
        return Result(proc.returncode, proc.stdout)

    def path(self, *parts):
        return os.path.join(self.proj, *parts)

    def write(self, relative, text, base=None):
        path = os.path.join(base or self.proj, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(text.encode("utf-8") if isinstance(text, str) else text)
        return path

    def read(self, relative, base=None):
        with open(os.path.join(base or self.proj, relative), "rb") as handle:
            return handle.read().decode("utf-8")

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class ToolTest(unittest.TestCase):
    """A test case with a fresh Sandbox per test."""

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.cleanup)

    def assertNext(self, result, *fragments):
        self.assertTrue(result.last.startswith("Next: "), result)
        for fragment in fragments:
            self.assertIn(fragment, result.last, result)

    def assertContract(self, result):
        """UTF-8, LF only, and a Next: line last."""
        self.assertNotIn(b"\r", result.data)
        self.assertTrue(result.data.endswith(b"\n"), result)
        self.assertTrue(result.last.startswith("Next: "), result)
