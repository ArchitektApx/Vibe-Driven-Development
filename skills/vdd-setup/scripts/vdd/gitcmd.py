"""git and gh as the tool runs them: always from an argument list, never
through a shell.

version() reads the leading "git version X.Y" of git --version, a vendor
suffix such as "(Apple Git-157)" or ".windows.2" ignored: Setup and the fold
read it the same way. is_refusal() tells a sandbox refusal from any other
failure, by a marker on stderr after a non-zero exit only (a call that exits
0 is judged by its exit code alone: git ls-remote has printed "fatal: failed
to store" on a call that succeeded).
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
from typing import Any, Iterable

from . import seams, textfile
from .out import Failure

MINIMUM = (2, 40)
VERSION = re.compile(r"^git version ([0-9]+)\.([0-9]+)")
# What a refused call prints: macOS and Linux, Windows, and gh. Matched in
# lower case: real gh writes "operation not permitted". The last four are a
# network a sandbox blocks, as gh and git's connection layer word it; neither
# translates them, and every git call runs in English (ENGLISH).
REFUSAL_MARKERS = (
    "operation not permitted",
    "permission denied",
    "access is denied",
    "insufficient permission",
    "read-only file system",
    "error connecting to",
    "proxyconnect",
    "failed to connect to",
    "could not resolve host",
)
# git translates its messages into the system's language, and the markers
# above are English.
ENGLISH = {"LC_ALL": "C"}
# git fails instead of prompting: GIT_TERMINAL_PROMPT for git's own prompt,
# GCM_INTERACTIVE for Git Credential Manager, which ignores the first and
# opens a sign-in window that a hidden Session never closes.
NO_PROMPT = {"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
# Every call ends after this many seconds unless its caller passes its own:
# a signing call waiting on a pinentry dialog a hidden Session never sees
# would otherwise wait for ever, and a user typing a passphrase gets minutes.
TIMEOUT_SECONDS = 300.0
# The words of a program's subcommand, as a line names a call: gh's is a
# group and a command, git's one word.
SUBCOMMAND_WORDS = {"gh": 2}
WINDOWS = os.name == "nt"


def environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment for a git or gh call: this one plus extra, in English
    and never prompting; extra cannot change either."""
    full = dict(os.environ)
    full.update(extra or {})
    full.update(ENGLISH)
    full.update(NO_PROMPT)
    return full


class Call:
    """One finished call: its exit code (None when it could not start),
    stdout and stderr as text, and stdout as bytes."""

    def __init__(
        self, argv: list[str], code: int | None, data: bytes, error: bytes, timed_out: float | None = None,
    ) -> None:
        self.argv = argv
        self.code = code
        self.data = data
        self.out = textfile.decode(data)
        self.err = textfile.decode(error)
        # The seconds after which the call was ended, or None; error then
        # holds the line that says so.
        self.timed_out = timed_out

    @property
    def ok(self) -> bool:
        return self.code == 0

    @property
    def refused(self) -> bool:
        return is_refusal(self.code, self.err)

    def first_error(self) -> str:
        """The line of stderr, else of stdout, that names the cause, else a
        line naming the exit."""
        for text in (self.err, self.out):
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if lines:
                return reason(lines)
        if self.code is None:
            return "%s could not run" % self.argv[0]
        return "%s exited %d and printed nothing" % (name_of(self.argv), self.code)


def reason(lines: list[str]) -> str:
    """The line that names the cause among a failed call's lines: the first
    one left once git push's "To <url>" header, gh's and git's "warning:"
    lines in any case, ssh's "** " notices, git's "hint:" lines and bare
    "remote:" lines are dropped. A signing failure
    puts gpg's reason on the lines after "gpg failed to sign the data:"."""
    for i, line in enumerate(lines):
        if line.endswith("failed to sign the data:"):
            after = [other for other in lines[i + 1:] if not other.startswith("[GNUPG:]")]
            gpg = [other for other in after if other.lower().startswith("gpg:")]
            found = gpg[-1] if gpg else (after[0] if after else "")
            return "%s %s" % (line, found) if found else line
    kept = [line for line in lines
            if not line.startswith(("To ", "hint:", "** ")) and not line.lower().startswith("warning:")
            and line != "remote:"]
    return kept[0] if kept else lines[0]


class Refused(Exception):
    """A git or gh call a sandbox refused."""

    def __init__(self, call: Call) -> None:
        Exception.__init__(self, call.first_error())
        self.call = call


def is_refusal(code: int | None, stderr: str | None) -> bool:
    """Whether a call that exited code with stderr was refused by a sandbox."""
    if code == 0 or code is None:
        return False
    text = (stderr or "").lower()
    return any(marker in text for marker in REFUSAL_MARKERS)


def run(
    root: str,
    argv: list[str],
    data: bytes | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> Call:
    """Run argv in root and return its Call. data, bytes, goes to standard
    input; without it standard input is empty. env adds variables. The call
    ends after timeout seconds, by default TIMEOUT_SECONDS or the
    VDD_GIT_TIMEOUT_SECONDS seam; on POSIX with every process it started, so
    a gpg it left behind cannot hold its output open."""
    full = environment(env)
    seconds = timeout if timeout is not None else seams.seconds("VDD_GIT_TIMEOUT_SECONDS", TIMEOUT_SECONDS)
    try:
        proc = subprocess.Popen(argv, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=full, start_new_session=not WINDOWS)
    except (OSError, subprocess.SubprocessError) as error:
        return Call(argv, None, b"", str(error).encode("utf-8", "replace"))
    try:
        out, err = proc.communicate(data if data is not None else b"", timeout=seconds)
    except subprocess.TimeoutExpired:
        end(proc)
        line = "%s timed out after %g seconds" % (name_of(argv), seconds)
        return Call(argv, None, b"", line.encode("utf-8"), timed_out=seconds)
    except BaseException:
        end(proc)
        raise
    return Call(argv, proc.returncode, out, err)


def end(proc: subprocess.Popen[bytes]) -> None:
    """Kill the call and, on POSIX, every process in its session."""
    try:
        if WINDOWS:
            proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        proc.communicate(timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def name_of(argv: list[str]) -> str:
    """A call as a line names it: the program and its subcommand."""
    return " ".join(argv[:1 + SUBCOMMAND_WORDS.get(argv[0], 1)] if argv else [])


def call_text(call: Call) -> str:
    """The call as a line names it: the program and its subcommand."""
    return name_of(call.argv)


def sandbox_refusal(
    call: Call, command: str, otherwise: str, done: Iterable[str] = (), name: str | None = None,
) -> Failure:
    """The Failure for a git or gh call a sandbox refused inside the tool:
    the call, by name when given, else by call_text, and its error, the
    lines done says about what happened before it, and the rerun of command
    outside the sandbox, otherwise after it."""
    return Failure(
        ["A sandbox refused %s inside the tool: %s" % (name or call_text(call), call.first_error())] + list(done),
        "Rerun %s outside the sandbox, the way your Harness grants that; when that is refused too, %s" % (
            command, otherwise),
    )


def git(root: str, *argv: str, **kwargs: Any) -> Call:
    return run(root, ["git"] + list(argv), **kwargs)


def answered(call: Call) -> Call:
    """call, or the one Failure for a call that timed out, naming the call
    and the seconds: a caller never reads a timeout as a state of the
    repository."""
    if call.timed_out is not None:
        raise Failure(call.first_error() + ".", "Tell the user %s did not finish, and stop." % call_text(call))
    return call


def project_root(cwd: str) -> str:
    """The directory the loops live under: the repository's top level, so a
    command run from a subdirectory, the tracker directory included, finds
    them; the working directory outside git."""
    call = git(cwd, "rev-parse", "--show-toplevel")
    top = call.out.strip()
    if call.code != 0 or not top:
        return cwd
    return os.path.normpath(top)


def current_branch(root: str) -> str:
    """The checked-out branch, or "" on a detached HEAD or outside git.
    Refuses a call that timed out."""
    call = answered(git(root, "branch", "--show-current"))
    if call.code != 0:
        return ""
    return call.out.strip()


def version(root: str | None = None) -> tuple[tuple[int, int] | None, str, str]:
    """((major, minor) or None, the text git --version printed, the line
    that says it timed out or ""). None for the tuple when git cannot run,
    times out or prints no version."""
    call = git(root or os.getcwd(), "--version")
    text = call.out.strip()
    if call.code is None:
        return None, "", call.err.strip() if call.timed_out is not None else ""
    match = VERSION.match(text)
    if not match:
        return None, text, ""
    return (int(match.group(1)), int(match.group(2))), text, ""


def number(text: str) -> str:
    """The version number in git --version's text: "2.39.5" from
    "git version 2.39.5"."""
    return text[len("git version "):].strip() if text.startswith("git version ") else text


def too_old(found: tuple[int, int] | None) -> bool:
    return found is not None and found < MINIMUM
