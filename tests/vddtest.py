"""Shared helpers for the VDD tool's tests.

Every test but the Harness contract test drives the tool from outside: it
runs vdd.py as a subprocess in a temporary project, with a temporary home and
Shared directory, every relocation variable cleared, so no test reads the
real machine.
"""

import atexit
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

# The origin URL a PR scene's remote keeps, and the gh stub that records its
# argv and standard input and plays the outcome a test's plan sets.
URL = "https://github.com/example/repo.git"
GH = """#!%(python)s
import json, os, sys
argv = sys.argv[1:]
data = sys.stdin.read() if "--body-file" in argv else ""
with open(%(log)r, "a") as handle:
    handle.write(json.dumps({"argv": argv, "stdin": data}) + "\\n")
with open(%(plan)r) as handle:
    plan = json.load(handle)
if argv[:2] == ["auth", "status"]:
    key = "auth"
elif argv[:2] == ["pr", "list"] and "--head" in argv:
    key = "head"
elif argv[:2] == ["pr", "list"]:
    key = "merged"
elif argv[:2] == ["pr", "create"]:
    key = "create"
else:
    key = "other"
code, out, err = plan.get(key, [0, "", ""])
sys.stdout.write(out)
sys.stderr.write(err)
sys.exit(code)
"""

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
    "PYTHONPYCACHEPREFIX",
)


# The bytecode prefix. Every tool run reads its compiled stdlib and vdd
# package from one temporary PYTHONPYCACHEPREFIX outside the repository,
# filled once per process, so no run compiles them again. The tool's own
# dont_write_bytecode stays: it stops writes, not reads. A prefix named by
# VDD_TEST_PYCACHE (the runner fills one for its workers) belongs to whoever
# set it; one this module makes is removed at exit.
SKIPPED_STDLIB = re.compile(r"[/\\](site-packages|test|tests|idlelib|tkinter|turtledemo|lib2to3|ensurepip)[/\\]")


def fill_pycache(prefix):
    """Compile the stdlib, at the path the interpreter imports it from, and
    the vdd package into prefix, serially (compileall -j0 fails in a
    sandbox)."""
    code = ("import compileall, os, re, sys\n"
            "compileall.compile_dir(os.path.dirname(os.__file__), quiet=2, rx=re.compile(sys.argv[1]))\n"
            "compileall.compile_dir(sys.argv[2], quiet=2)\n")
    env = dict(os.environ, PYTHONPYCACHEPREFIX=prefix)
    subprocess.run([sys.executable, "-B", "-c", code, SKIPPED_STDLIB.pattern, os.path.join(SCRIPTS, "vdd")],
                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def pycache_prefix():
    named = os.environ.get("VDD_TEST_PYCACHE")
    if named and os.path.isdir(named):
        return named
    prefix = os.path.realpath(tempfile.mkdtemp(prefix="vdd-pycache-"))
    atexit.register(shutil.rmtree, prefix, True)
    fill_pycache(prefix)
    return prefix


PYCACHE = pycache_prefix()

# The plan Sign-off line a loop's state file carries before its code Loop.
PLAN_SIGNED = "plan 1 reviewed signed-off - counts 0 0 0 next 1 new 0 closed 0 checks writing-for-agents ran"
PLAN_SIGNED_2 = "plan 2 reviewed signed-off - counts 0 0 0 next 3 new 0 closed 2 checks writing-for-agents ran"
CODE_SIGNED_2 = "code 2 reviewed signed-off - counts 0 0 0 next 2 new 0 closed 1 checks code-review ran"
SIGNED = PLAN_SIGNED

GIT_IDENTITY = ("-c", "commit.gpgsign=false", "-c", "user.name=VDD Test", "-c", "user.email=test@example.com")

# No git the suite starts, the tool's included, runs maintenance or gc after a
# commit: git detaches it into the background, and a scene copied while it
# runs loses a lock file mid-copy (macOS CI, 2026-10-23).
os.environ.update({
    "GIT_CONFIG_COUNT": "2",
    "GIT_CONFIG_KEY_0": "maintenance.auto",
    "GIT_CONFIG_VALUE_0": "false",
    "GIT_CONFIG_KEY_1": "gc.auto",
    "GIT_CONFIG_VALUE_1": "0",
})


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


# The Next: check. Every Next: line a test's tool run prints is read for VDD
# tool commands: an interpreter (python3, or py -3), the quoted path of a
# vdd.py, then the group, the command and its options. Each command is run
# again with --help and must exit 0: the parser refuses an unknown option
# before it honours --help, so --help is the oracle for "a Role can run this
# line verbatim". Skipped, by rule: a Next: line with no tool command, and a
# command holding a <...> placeholder, which the Role fills in. A command
# whose vdd.py does not exist fails. A command that passed is checked once per
# process. The Codex Stop hook's JSON reason and a run started with Popen
# (Sandbox.finish) are swept the same way.
FLAGS = ("--write", "--once", "--resumed", "--help")
# setup is a group with no command under it.
TOOL_COMMAND = re.compile(r'(?:python3|py -3|"[^"]*python[^"]*") "([^"]*vdd\.py)" ([^\n]*)')
NEXT_CHECKED = {}


def _report_next():
    if os.environ.get("VDD_NEXT_REPORT"):
        sys.stderr.write("Next: check ran %d distinct commands, %d failed.\n"
                         % (len(NEXT_CHECKED), len([ok for ok in NEXT_CHECKED.values() if not ok])))


atexit.register(_report_next)


def tokens(text):
    """The words of text, a double-quoted run one word with its quotes
    removed, each with whether a punctuation mark ended it."""
    out = []
    for match in re.finditer(r'"([^"]*)"([.,;:]?)|(\S+)', text):
        if match.group(3) is not None:
            word = match.group(3)
            stripped = word.rstrip(".,;:")
            out.append((stripped, stripped != word))
        else:
            out.append((match.group(1), bool(match.group(2))))
    return out


def next_commands(line):
    """The tool commands in a Next: line, each (entry, argv), and the
    placeholder-holding ones as None."""
    found = []
    for match in TOOL_COMMAND.finditer(line):
        words = tokens(match.group(2))
        argv = []
        expects = 0
        words_before_options = 1 if words[:1] and words[0][0] == "setup" else 2
        for index, (word, ended) in enumerate(words):
            if index < words_before_options and not word.startswith("--"):
                argv.append(word)
            elif word.startswith("--"):
                argv.append(word)
                expects = 0 if word in FLAGS else 1
            elif expects:
                argv.append(word)
                expects = 0
            else:
                break
            if ended:
                break
        if any("<" in word and ">" in word for word in argv):
            found.append(None)
        else:
            found.append((match.group(1), tuple(argv)))
    return found


def next_lines(result):
    """The Next: steps a result hands a Role: its last line when that is a
    Next: line, or, for the Codex Stop hook's one JSON line, each Next: step
    in its decoded reason."""
    if result.last.startswith("Next:"):
        return [result.last]
    if len(result.lines) == 1 and result.last.startswith("{"):
        try:
            reason = json.loads(result.last).get("reason")
        except (ValueError, AttributeError):
            return []
        if isinstance(reason, str) and "Next:" in reason:
            return ["Next:" + part for part in reason.split("Next:")[1:]]
    return []


def check_next(box, result, test="a test"):
    """Run each tool command result's Next: steps name with --help; raise
    AssertionError naming the command and the test when one fails. Returns
    the commands checked. Only a command that passed is cached, so every test
    that prints a broken one fails."""
    checked = []
    for command in [c for line in next_lines(result) for c in next_commands(line)]:
        if command is None:
            continue
        if not os.path.isfile(command[0]):
            raise AssertionError("The Next: line %s printed names a vdd.py that does not exist: %s"
                                 % (test, command[0]))
        checked.append(command)
        if NEXT_CHECKED.get(command):
            continue
        proc = subprocess.run([sys.executable, command[0]] + list(command[1]) + ["--help"], cwd=box.proj,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=box.env(), timeout=120)
        NEXT_CHECKED[command] = proc.returncode == 0
        if proc.returncode != 0:
            raise AssertionError("The Next: line %s printed does not parse: %s --help exited %d\n%s"
                                 % (test, " ".join(command[1]), proc.returncode, proc.stdout.decode("utf-8", "replace")))
    return checked


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
        self.test = "a test"
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
        env["PYTHONPYCACHEPREFIX"] = PYCACHE
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
        result = Result(proc.returncode, proc.stdout)
        check_next(self, result, self.test)
        return result

    def finish(self, proc, timeout=120):
        """The Result of a tool run started with subprocess.Popen, once it
        ends, its Next: steps checked as a run's are."""
        data, _ = proc.communicate(timeout=timeout)
        result = Result(proc.returncode, data)
        check_next(self, result, self.test)
        return result

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

    def bare_origin(self, name="origin", push=("main",)):
        """A local bare repository inside the sandbox as the remote name,
        each branch in push pushed to it. Returns its path."""
        bare = os.path.join(self.root, name + ".git")
        self.git("init", "-q", "--bare", bare)
        self.git("remote", "add", name, bare)
        for branch in push:
            self.git("push", "-q", name, branch)
        return bare

    def remote_ref(self, bare, ref):
        """The sha ref names in the bare repository, or "" when it has none."""
        proc = subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=bare, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        return proc.stdout.decode("utf-8").strip()

    def git_only_path(self):
        """A PATH with git on it and gh off it, or None when this machine
        keeps gh beside git. On POSIX it is the sandbox's bin directory
        holding a git launcher that runs the real git by its absolute path;
        on Windows the tool starts git through CreateProcess, which runs only
        an .exe, so it is the real git.exe's own directory."""
        real = shutil.which("git")
        if real is None:
            return None
        if WINDOWS:
            # Git for Windows' cmd directory: its git.exe sets up the PATH the
            # sh.exe a local ls-remote starts needs. A bare ucrt64\bin or
            # mingw64\bin git.exe alone crashes there (CI, 2026-10-23).
            path = os.path.dirname(real)
            root = path
            while os.path.dirname(root) != root and not os.path.isfile(os.path.join(root, "cmd", "git.exe")):
                root = os.path.dirname(root)
            if os.path.isfile(os.path.join(root, "cmd", "git.exe")):
                path = os.path.join(root, "cmd")
        else:
            os.makedirs(self.bin, exist_ok=True)
            launcher = os.path.join(self.bin, "git")
            with open(launcher, "w") as handle:
                handle.write("#!/bin/sh\nexec '%s' \"$@\"\n" % real)
            os.chmod(launcher, 0o755)
            path = self.bin
        if shutil.which("gh", path=path):
            return None
        return path

    def ls_remote_report(self, remote, env):
        """git ls-remote <remote> HEAD as the tool runs it under env, for a
        failure message: the tool keeps git's stderr to itself."""
        proc = subprocess.run(["git", "ls-remote", remote, "HEAD"], cwd=self.proj, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=env)
        return "git %s; PATH %s; ls-remote %s HEAD exited %d: %s" % (
            shutil.which("git"), env.get("PATH"), remote, proc.returncode,
            proc.stderr.decode("utf-8", "replace").strip())

    def cleanup(self):
        remove_tree(self.root)


class ToolTest(unittest.TestCase):
    """A test case with a fresh Sandbox per test."""

    def setUp(self):
        self.box = Sandbox()
        self.box.test = self.id()
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


class SceneTest(LoopRepoTest):
    """A git-backed test class that stages its scene once, in setUpClass,
    into a template sandbox, and copies the template into each test's
    sandbox. stage_scene builds the scene with self.box the template; every
    attribute it sets is carried to each test, with the template's root
    replaced by the test's, and a remote inside the template is re-pointed at
    the copy's own. after_copy writes whatever holds the sandbox
    root, a stub or a remote's path, after the copy. Each test class gets a
    template of its own, keyed by its class, so a subclass that changes a
    scene attribute stages its own scene."""

    _scenes = {}

    def stage_scene(self):
        raise NotImplementedError

    def after_copy(self):
        pass

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        stager = cls()
        stager.box = Sandbox()
        try:
            stager.stage_scene()
        except BaseException:
            stager.box.cleanup()
            raise
        attrs = dict((k, v) for k, v in vars(stager).items() if k != "box" and not k.startswith("_"))
        SceneTest._scenes[cls] = (stager.box, attrs)

    @classmethod
    def tearDownClass(cls):
        scene = SceneTest._scenes.pop(cls, None)
        if scene is not None:
            scene[0].cleanup()
        super().tearDownClass()

    def setUp(self):
        LoopRepoTest.setUp(self)
        template, attrs = SceneTest._scenes[type(self)]
        for name in os.listdir(template.root):
            source = os.path.join(template.root, name)
            target = os.path.join(self.box.root, name)
            remove_tree(target)
            if os.path.isdir(source) and not os.path.islink(source):
                shutil.copytree(source, target, symlinks=True)
            else:
                shutil.copy2(source, target)
        for key, value in attrs.items():
            if isinstance(value, str):
                value = value.replace(template.root, self.box.root)
            setattr(self, key, value)
        if os.path.isdir(os.path.join(self.box.proj, ".git")):
            subprocess.run(["git", "update-index", "--refresh", "-q"], cwd=self.box.proj,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Each copy pushes to its own copy of a remote the scene keeps
            # in the sandbox.
            urls = subprocess.run(["git", "config", "--get-regexp", r"^remote\..*\.url$"], cwd=self.box.proj,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode("utf-8")
            for line in urls.splitlines():
                key, _, url = line.partition(" ")
                if url.startswith(template.root):
                    remote = key[len("remote."):-len(".url")]
                    self.box.git("remote", "set-url", remote, self.box.root + url[len(template.root):])
        self.after_copy()
