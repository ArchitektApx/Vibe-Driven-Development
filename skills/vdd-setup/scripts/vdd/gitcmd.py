"""git and gh as the tool runs them: always from an argument list, never
through a shell.

version() reads the leading "git version X.Y" of git --version, a vendor
suffix such as "(Apple Git-157)" or ".windows.2" ignored: Setup and the fold
read it the same way. is_refusal() tells a sandbox refusal from any other
failure, by a marker on stderr after a non-zero exit only (a call that exits
0 is judged by its exit code alone, 9e820de).
"""

import os
import re
import subprocess

from . import textfile

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


def environment(extra=None):
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

    def __init__(self, argv, code, data, error):
        self.argv = argv
        self.code = code
        self.data = data
        self.out = textfile.decode(data)
        self.err = textfile.decode(error)

    @property
    def ok(self):
        return self.code == 0

    @property
    def refused(self):
        return is_refusal(self.code, self.err)

    def first_error(self):
        """The line of stderr, else of stdout, that names the cause, else a
        line naming the exit."""
        for text in (self.err, self.out):
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if lines:
                return reason(lines)
        if self.code is None:
            return "%s could not run" % self.argv[0]
        return "%s exited %d and printed nothing" % (" ".join(self.argv[:2]), self.code)


def reason(lines):
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

    def __init__(self, call):
        Exception.__init__(self, call.first_error())
        self.call = call


def is_refusal(code, stderr):
    """Whether a call that exited code with stderr was refused by a sandbox."""
    if code == 0 or code is None:
        return False
    text = (stderr or "").lower()
    return any(marker in text for marker in REFUSAL_MARKERS)


def run(root, argv, data=None, env=None, timeout=None):
    """Run argv in root and return its Call. data, bytes, goes to standard
    input; without it standard input is empty. env adds variables."""
    full = environment(env)
    try:
        proc = subprocess.run(
            argv,
            cwd=root,
            input=data if data is not None else b"",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=full,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return Call(argv, None, b"", str(error).encode("utf-8", "replace"))
    return Call(argv, proc.returncode, proc.stdout, proc.stderr)


def git(root, *argv, **kwargs):
    return run(root, ["git"] + list(argv), **kwargs)


def project_root(cwd):
    """The directory the loops live under: the repository's top level, so a
    command run from a subdirectory, the tracker directory included, finds
    them; the working directory outside git."""
    call = git(cwd, "rev-parse", "--show-toplevel")
    top = call.out.strip()
    if call.code != 0 or not top:
        return cwd
    return os.path.normpath(top)


def current_branch(root):
    """The checked-out branch, or "" on a detached HEAD or outside git."""
    call = git(root, "branch", "--show-current")
    if call.code != 0:
        return ""
    return call.out.strip()


def version(root=None):
    """((major, minor) or None, the text git --version printed). None for
    the tuple when git cannot run or prints no version."""
    call = git(root or os.getcwd(), "--version")
    text = call.out.strip()
    if call.code is None:
        return None, ""
    match = VERSION.match(text)
    if not match:
        return None, text
    return (int(match.group(1)), int(match.group(2))), text


def number(text):
    """The version number in git --version's text: "2.39.5" from
    "git version 2.39.5"."""
    return text[len("git version "):].strip() if text.startswith("git version ") else text


def too_old(found):
    return found is not None and found < MINIMUM
