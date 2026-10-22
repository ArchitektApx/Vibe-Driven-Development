"""Shared helpers for the VDD tool's tests.

Every test but the Harness contract test drives the tool from outside: it
runs vdd.py as a subprocess in a temporary project, with a temporary home and
Shared directory, every relocation variable cleared, so no test reads the
real machine.
"""

import base64
import json
import os
import re
import shutil
import stat
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
    "VDD_TODAY",
    "VDD_SAVE_PAUSE_SECONDS",
    "PYTHONDONTWRITEBYTECODE",
)


# The plan Sign-off line a loop's state file carries before its code Loop.
PLAN_SIGNED = "plan 1 reviewed signed-off - counts 0 0 0 next 1 new 0 closed 0 checks writing-for-agents ran"
PLAN_SIGNED_2 = "plan 2 reviewed signed-off - counts 0 0 0 next 3 new 0 closed 2 checks writing-for-agents ran"
CODE_SIGNED_2 = "code 2 reviewed signed-off - counts 0 0 0 next 2 new 0 closed 1 checks code-review ran"
SIGNED = PLAN_SIGNED

GIT_IDENTITY = ("-c", "commit.gpgsign=false", "-c", "user.name=VDD Test", "-c", "user.email=test@example.com")


def b64(data):
    return None if data is None else base64.b64encode(data).decode("ascii")


def _writable_retry(function, path, _):
    """Clear the read-only bit on the path and its directory, then retry:
    Windows refuses to delete a read-only file, POSIX a file in a read-only
    directory."""
    parent = os.path.dirname(path)
    os.chmod(parent, stat.S_IRWXU)
    if not os.path.isdir(path) or os.path.islink(path):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    else:
        os.chmod(path, stat.S_IRWXU)
    function(path)


def remove_tree(path):
    """Remove a test's temporary tree, read-only files included. Windows
    refuses to delete git's read-only objects, which left every git-backed
    sandbox behind in %TEMP%."""
    if not os.path.lexists(path):
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_writable_retry)  # pyright: ignore[reportCallIssue]
    else:
        shutil.rmtree(path, onerror=lambda function, failed, info: _writable_retry(function, failed, info))


LOOP_TEXT = (
    "# VDD Loop\n\nFormat: 2\nFeature: %s\nBase branch: %s\nFeature branch: %s\nMinors: fix\n"
    "PR: ask at sign-off\nHarness: %s\n"
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

    def git(self, *args, cwd=None, env=None):
        """Run git in the project, unsigned and with a fixed identity, and
        return its stripped standard output."""
        proc = subprocess.run(
            ["git"] + list(GIT_IDENTITY) + list(args),
            cwd=cwd or self.proj,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        return proc.stdout.decode("utf-8").strip()

    def sha(self, ref="HEAD", cwd=None):
        return self.git("rev-parse", ref, cwd=cwd)

    def commit(self, name, text, message):
        """Write one file, commit it, and return the new HEAD."""
        self.write(name, text)
        self.git("add", name)
        self.git("commit", "-q", "-m", message)
        return self.sha()

    def init_git(self, branch="main"):
        """A repository on branch with one commit."""
        self.git("init", "-q")
        self.git("symbolic-ref", "HEAD", "refs/heads/" + branch)
        self.git("commit", "-q", "--allow-empty", "-m", "init")

    def write_loop(self, slug, branch=None, harness="Claude Code", states=("open",), base="main", text=None,
                   version=2, extra=()):
        """A loop as loop new writes it: .scratch/<slug>/loop.md and its
        state file, each state in states appended, then each line in
        extra. version 1 stages a loop 0.16.0-beta.3 started."""
        if text is None:
            text = LOOP_TEXT % (slug, base, branch or slug, harness)
        self.write(os.path.join(".scratch", slug, "loop.md"), text)
        state = "vdd loop-state %d\n" % version + "".join("loop %s\n" % s for s in states)
        state += "".join(line + "\n" for line in extra)
        self.write(os.path.join(".scratch", slug, "loop-state"), state)

    @property
    def bin(self):
        return os.path.join(self.root, "bin")

    def stub(self, name, body):
        """A POSIX sh script named name in the sandbox's bin directory, which
        stub_env puts first on PATH. body follows a #!/bin/sh line, unless it
        starts with its own #! line."""
        os.makedirs(self.bin, exist_ok=True)
        path = os.path.join(self.bin, name)
        with open(path, "w") as handle:
            handle.write(body if body.startswith("#!") else "#!/bin/sh\n" + body)
        os.chmod(path, 0o755)
        return path

    def stub_env(self, **extra):
        """The environment with the sandbox's bin directory first on PATH."""
        os.makedirs(self.bin, exist_ok=True)
        return self.env(PATH=self.bin + os.pathsep + os.environ.get("PATH", ""), **extra)

    def cleanup(self):
        remove_tree(self.root)


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


class LoopRepoTest(ToolTest):
    """A test on one loop, .scratch/<slug>/, in a git repository the
    subclass stages."""

    slug = "demo"

    # --- files under .scratch/<slug>/ ---

    def rel(self, name):
        return os.path.join(".scratch", self.slug, name)

    def read(self, name):
        return self.box.read(self.rel(name))

    def exists(self, name):
        return os.path.exists(self.box.path(self.rel(name)))

    def put(self, name, text):
        self.box.write(self.rel(name), text)

    def state(self):
        return self.read("loop-state")

    def stage(self, *lines):
        """Append lines to the loop's state file."""
        with open(self.box.path(self.rel("loop-state")), "ab") as handle:
            handle.write("".join(line + "\n" for line in lines).encode("utf-8"))

    def snapshot(self, names):
        """Each named file's text, None when it is missing."""
        return dict((name, self.read(name) if self.exists(name) else None) for name in names)

    def set_pr(self, value):
        text = self.read("loop.md")
        self.put("loop.md", re.sub(r"(?m)^PR: .*$", "PR: %s" % value, text))

    # --- git ---

    def git(self, *argv, cwd=None, env=None):
        return self.box.git(*argv, cwd=cwd, env=env)

    def out(self, *argv):
        return self.box.git(*argv)

    def sha(self, ref="HEAD", cwd=None):
        return self.box.sha(ref, cwd=cwd)

    def head(self):
        return self.box.sha()

    def commit(self, name, text, message):
        return self.box.commit(name, text, message)

    def coder_round(self, number, name=None, text="x\n"):
        """A code round's commit and its recorded start and end."""
        start = self.sha()
        self.commit(name or "src/r%d.txt" % number, text, "feat: round %d" % number)
        self.stage("code %d start %s" % (number, start), "code %d end %s" % (number, self.sha()))

    # --- refusals ---

    def refused(self, argv, names, *fragments):
        """Run argv, assert the tool refused it under its contract with every
        fragment printed, and that none of the named files changed."""
        before = LoopRepoTest.snapshot(self, names)
        result = self.box.run(*argv)
        self.assertNotEqual(result.code, 0, result)
        self.assertContract(result)
        for fragment in fragments:
            self.assertIn(fragment, result.text, result)
        self.assertEqual(LoopRepoTest.snapshot(self, names), before)
        return result
