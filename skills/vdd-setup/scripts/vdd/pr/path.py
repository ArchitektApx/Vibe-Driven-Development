"""The path pr check prints and pr open checks again: the preflight, the
existing-PR check and what follows from them, and the gh call they share."""

from __future__ import annotations

import json
from typing import Iterable

from .. import gitcmd, loopfile, preflight
from ..gitcmd import Refused

TIMEOUT_SECONDS = 60
OPEN = "open"
PUSH_ONLY = "push-only"
NEITHER = "neither"
EXISTING = "existing"
MANUAL = "manual"
NO_PR = "no"


def gh(root: str, *argv: str) -> gitcmd.Call:
    return gitcmd.run(root, ["gh"] + list(argv), timeout=TIMEOUT_SECONDS)


class Path:
    """The path pr check prints: its name, the checks, and the URL of an
    open PR."""

    def __init__(self, name: str, checks: Iterable[preflight.Check] = (), url: str = "", remote: str = "") -> None:
        self.name = name
        self.checks = list(checks)
        self.url = url
        self.remote = remote

    def failed(self) -> list[preflight.Check]:
        return [check for check in self.checks if not check.passed]


def existing_pr(root: str, branch: str) -> str | None:
    """The URL of an open PR for the branch, "" for none; Refused on a
    refusal; None when the check fails."""
    result = gh(root, "pr", "list", "--head", branch, "--state", "open", "--json", "url")
    if result.refused:
        raise Refused(result)
    if result.code != 0:
        return None
    try:
        data = json.loads(result.out or "[]")
    except ValueError:
        return None
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and item.get("url"):
            return str(item["url"])
    return ""


def path_of(loop: loopfile.Loop) -> Path:
    """The Path for the loop's PR: line, or Refused."""
    pr = loop.pr
    if pr == "manual":
        return Path(MANUAL)
    if pr == "no":
        return Path(NO_PR)
    base = loop.base
    branch = loop.branch
    remote, found = preflight.checks(loop.root, base)
    for check in found:
        if check.refused is not None:
            raise Refused(check.refused)
    push, can_open = found
    if not push.passed:
        return Path(NEITHER, found, remote=remote)
    if not can_open.passed:
        return Path(PUSH_ONLY, found, remote=remote)
    url = existing_pr(loop.root, branch)
    if url is None:
        found = [push, preflight.Check("can open a PR", False, "gh pr list --head %s did not exit 0" % branch)]
        return Path(PUSH_ONLY, found, remote=remote)
    if url:
        return Path(EXISTING, found, url=url, remote=remote)
    return Path(OPEN, found, remote=remote)
