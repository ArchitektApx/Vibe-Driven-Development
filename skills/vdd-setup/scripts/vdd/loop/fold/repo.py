"""The fold's git adapter, every call checked and core.quotePath off, and
its committer, which makes a commit like an original one, signed when the
repository signs."""

from __future__ import annotations

import os
import re
from typing import Any

from ... import gitcmd


class GitFailed(Exception):
    """A git call that failed for any other reason."""

    def __init__(self, call: gitcmd.Call) -> None:
        Exception.__init__(self, call.first_error())
        self.call = call


def quote_path_off() -> dict[str, str]:
    """core.quotePath=false through git's environment config, after any the
    user set: every name list reads a non-ASCII path as itself, not C-quoted,
    and argv stays as the call names it."""
    try:
        count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    except ValueError:
        count = 0
    return {"GIT_CONFIG_COUNT": str(count + 1), "GIT_CONFIG_KEY_%d" % count: "core.quotePath",
            "GIT_CONFIG_VALUE_%d" % count: "false"}


QUOTE_PATH = quote_path_off()


class Repo:
    """git in the repository root, every call checked."""

    def __init__(self, root: str) -> None:
        self.root = root

    def call(self, *argv: str, **kwargs: Any) -> gitcmd.Call:
        ok = kwargs.pop("ok", (0,))
        env = dict(QUOTE_PATH)
        env.update(kwargs.pop("env", None) or {})
        result = gitcmd.git(self.root, *argv, env=env, **kwargs)
        if result.code in ok:
            return result
        if result.refused:
            raise gitcmd.Refused(result)
        raise GitFailed(result)

    def out(self, *argv: str, **kwargs: Any) -> str:
        return self.call(*argv, **kwargs).out.strip()

    def data(self, *argv: str) -> bytes:
        return self.call(*argv).data

    def tree(self, rev: str) -> str:
        return self.out("rev-parse", rev + "^{tree}")

    def parent(self, sha: str) -> str:
        return self.out("rev-parse", sha + "^")

    def names(self, *argv: str) -> list[str]:
        """A NUL-separated name list: a path with a quote or a backslash
        stays C-quoted in a line list despite core.quotePath=false."""
        return [name for name in self.call(*argv).out.split("\0") if name]

    def files(self, sha: str) -> set[str]:
        return set(self.names("diff-tree", "-z", "--no-commit-id", "--name-only", "-r", "--no-renames", sha))

    def exists(self, rev: str, path: str) -> bool:
        return self.call("cat-file", "-e", "%s:%s" % (rev, path), ok=(0, 1, 128)).code == 0

    def subject(self, sha: str) -> str:
        return self.out("log", "-1", "--format=%s", sha)

    def short(self, sha: str) -> str:
        return sha[:7]


class Committer:
    """Makes commits with an original commit's author, date and message,
    signed when the repository signs its commits."""

    def __init__(self, repo: Repo, sign: bool) -> None:
        self.repo = repo
        self.sign = sign
        self.env: dict[str, str] | None = {}
        if repo.call("var", "GIT_COMMITTER_IDENT", ok=(0, 1, 128)).code != 0:
            self.env = None  # set per commit from the original's committer

    def make(self, tree: str, parent: str, like: str, sign: bool = False) -> str:
        """A commit of tree on parent like the commit like. Unsigned, it is
        like itself when its tree and parent are already these, so an
        unchanged commit keeps its sha, committer date and signature."""
        raw = self.repo.data("cat-file", "commit", like)
        head, _, message = raw.partition(b"\n\n")
        fields = head.split(b"\n")
        parents = [line[len(b"parent "):].decode("ascii") for line in fields if line.startswith(b"parent ")]
        if not (sign and self.sign) and fields[0] == b"tree " + tree.encode("ascii") and parents == [parent]:
            return like
        env: dict[str, str] = {}
        for line in fields:
            text = line.decode("utf-8", "replace")
            for kind in ("author", "committer"):
                if text.startswith(kind + " "):
                    match = re.match(r"^\S+ (.*) <(.*)> (\S+ \S+)$", text)
                    if not match:
                        continue
                    if kind == "author":
                        env.update(GIT_AUTHOR_NAME=match.group(1), GIT_AUTHOR_EMAIL=match.group(2),
                                   GIT_AUTHOR_DATE=match.group(3))
                    elif self.env is None:
                        env.update(GIT_COMMITTER_NAME=match.group(1), GIT_COMMITTER_EMAIL=match.group(2))
        argv = ["commit-tree", tree, "-p", parent, "-F", "-"]
        if sign and self.sign:
            argv.insert(1, "-S")
        return self.repo.out(*argv, data=message, env=env)
