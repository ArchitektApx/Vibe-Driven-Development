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
# lower case: real gh writes "operation not permitted".
REFUSAL_MARKERS = (
    "operation not permitted",
    "permission denied",
    "access is denied",
    "insufficient permission",
    "read-only file system",
)


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
        """The first non-empty line of stderr, else of stdout, else a line
        naming the exit."""
        for text in (self.err, self.out):
            for line in text.split("\n"):
                if line.strip():
                    return line.strip()
        if self.code is None:
            return "%s could not run" % self.argv[0]
        return "%s exited %d and printed nothing" % (" ".join(self.argv[:2]), self.code)


def is_refusal(code, stderr):
    """Whether a call that exited code with stderr was refused by a sandbox."""
    if code == 0 or code is None:
        return False
    text = (stderr or "").lower()
    return any(marker in text for marker in REFUSAL_MARKERS)


def run(root, argv, data=None, env=None, timeout=None):
    """Run argv in root and return its Call. data, bytes, goes to standard
    input; without it standard input is empty. env adds variables."""
    full = dict(os.environ)
    if env:
        full.update(env)
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
