"""The PR preflight behind PR: yes: can push, and can open a PR.

Exit codes alone decide; stderr is ignored. git ls-remote has been observed
printing "fatal: failed to store" on a call that exited 0 (9e820de). The
tool's own code opens no connection; the git and gh it starts may.
"""

import os
import re
import shutil
import subprocess

from . import textfile

TIMEOUT_SECONDS = 60


def call(root, argv):
    """(exit code, stdout text); exit code None when the command cannot run."""
    env = dict(os.environ)
    # A credential prompt would hang the check; git fails instead.
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        proc = subprocess.run(
            argv,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None, ""
    return proc.returncode, textfile.decode(proc.stdout)


def remotes(root):
    code, text = call(root, ["git", "remote"])
    if code != 0:
        return []
    return [line.strip() for line in text.split("\n") if line.strip()]


def remote_of(root, base):
    """The remote the base branch tracks, else the single configured remote,
    else origin."""
    code, text = call(root, ["git", "config", "--get", "branch.%s.remote" % base])
    tracked = text.strip()
    if code == 0 and tracked and tracked != ".":
        return tracked
    configured = remotes(root)
    if len(configured) == 1:
        return configured[0]
    return "origin"


def host_of(url):
    """The host a remote URL names: https://host/..., ssh://user@host:port/...,
    or the scp form user@host:path."""
    url = url.strip()
    match = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://(?:[^@/]*@)?([^/:]+)", url)
    if match:
        return match.group(1).lower()
    match = re.match(r"^(?:[^@/]+@)?([^/:]+):", url)
    if match:
        return match.group(1).lower()
    return ""


def can_push(root, remote):
    if remote not in remotes(root):
        return False, "no remote %s is configured" % remote
    code, _ = call(root, ["git", "ls-remote", remote, "HEAD"])
    if code != 0:
        return False, "git ls-remote %s HEAD did not exit 0" % remote
    return True, ""


def can_open(root, remote):
    if shutil.which("gh") is None:
        return False, "gh is not on PATH"
    code, url = call(root, ["git", "remote", "get-url", remote])
    host = host_of(url) if code == 0 else ""
    if not host or "github" not in host:
        return False, "the remote %s is not on a GitHub host" % remote
    code, _ = call(root, ["gh", "auth", "status", "--hostname", host])
    if code != 0:
        return False, "gh auth status --hostname %s did not exit 0" % host
    return True, ""


def run(root, base):
    """(remote, [(check name, passed, why)]) for both checks."""
    remote = remote_of(root, base)
    push = can_push(root, remote)
    pr = can_open(root, remote)
    return remote, [("can push", push[0], push[1]), ("can open a PR", pr[0], pr[1])]
