"""The PR preflight behind PR: yes: can push, and can open a PR.

A call a sandbox refused is told apart first, by its stderr after a non-zero
exit; after that, exit codes alone decide and stderr is ignored. git ls-remote
has been observed printing "fatal: failed to store" on a call that exited 0
(9e820de). The tool's own code opens no connection; the git and gh it starts
may.
"""

import re
import shutil

from . import gitcmd

TIMEOUT_SECONDS = 60


def call(root, argv):
    """The finished gitcmd.Call; its code is None when the command cannot
    run or times out."""
    return gitcmd.run(root, argv, timeout=TIMEOUT_SECONDS)


def remotes(root):
    result = call(root, ["git", "remote"])
    if result.code != 0:
        return []
    return [line.strip() for line in result.out.split("\n") if line.strip()]


def remote_of(root, base):
    """The remote the base branch tracks, else the single configured remote,
    else origin."""
    result = call(root, ["git", "config", "--get", "branch.%s.remote" % base])
    tracked = result.out.strip()
    if result.code == 0 and tracked and tracked != ".":
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


class Check:
    """One capability: passed, why it failed, and the call a sandbox refused
    (None when none was)."""

    def __init__(self, name, passed, why="", refused=None):
        self.name = name
        self.passed = passed
        self.why = why
        self.refused = refused


def can_push(root, remote):
    name = "can push"
    if remote not in remotes(root):
        return Check(name, False, "no remote %s is configured" % remote)
    result = call(root, ["git", "ls-remote", remote, "HEAD"])
    if result.refused:
        return Check(name, False, "git ls-remote %s HEAD was refused" % remote, result)
    if result.code != 0:
        return Check(name, False, "git ls-remote %s HEAD did not exit 0" % remote)
    return Check(name, True)


def can_open(root, remote):
    name = "can open a PR"
    if shutil.which("gh") is None:
        return Check(name, False, "gh is not on PATH")
    result = call(root, ["git", "remote", "get-url", remote])
    host = host_of(result.out) if result.code == 0 else ""
    if not host or "github" not in host:
        return Check(name, False, "the remote %s is not on a GitHub host" % remote)
    result = call(root, ["gh", "auth", "status", "--hostname", host])
    if result.refused:
        return Check(name, False, "gh auth status --hostname %s was refused" % host, result)
    if result.code != 0:
        return Check(name, False, "gh auth status --hostname %s did not exit 0" % host)
    return Check(name, True)


def checks(root, base):
    """(remote, [Check]) for both capabilities. After the refusal check, exit
    codes alone decide."""
    remote = remote_of(root, base)
    return remote, [can_push(root, remote), can_open(root, remote)]


def run(root, base):
    """(remote, [(check name, passed, why)]) for both checks."""
    remote, found = checks(root, base)
    return remote, [(check.name, check.passed, check.why) for check in found]
