"""The fold's history rewrite: each later commit split by the commit of
the folded history that wrote its lines, the hunks absorbed into their
owners and the rest replayed on top, the folded commits signed again, and
the report of what each final commit was built from. It moves no ref."""

from __future__ import annotations

import os
import re

from ...out import and_list
from .repo import Committer, GitFailed, Repo

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
BLAME = re.compile(r"^([0-9a-f]{40}) \d+ \d+")
LINES = re.compile(rb"[^\n]*\n|[^\n]+$")
ROUND_ONE = "round 1"
NO_OWNER = "no commit of the loop wrote its lines"
CONFLICT = "folding it would conflict"


def split_lines(data: bytes) -> list[bytes]:
    return LINES.findall(data)


class Split:
    """A later-round commit's change, split by the commit of the folded
    history that wrote the lines it changes.

    tip is the folded history's last commit, whose tree equals the commit's
    parent's tree; chain is that history, oldest first. An owner is an index
    into chain, or None: no commit of the loop wrote the lines."""

    def __init__(self, repo: Repo, chain: list[str], tip: str, commit: str, index_path: str) -> None:
        self.repo = repo
        self.chain = chain
        self.tip = tip
        self.commit = commit
        self.index_path = index_path
        self.positions = dict((sha, i) for i, sha in enumerate(chain))
        self.touched_cache: dict[int, set[str]] = {}
        self.hunks: dict[str, list[tuple[int, int, int, int, int | None]]] = {}
        self.whole: dict[str, int | None] = {}
        self.text: dict[str, tuple[list[bytes], bytes | None]] = {}
        self.mode: dict[str, str] = {}
        added: set[str] = set()
        for name in repo.names("diff", "-z", "--name-only", "--no-renames", tip, commit):
            has_old = repo.exists(tip, name)
            has_new = repo.exists(commit, name)
            old = repo.data("show", "%s:%s" % (tip, name)) if has_old else b""
            new = repo.data("show", "%s:%s" % (commit, name)) if has_new else None
            listed = repo.out("ls-tree", commit if has_new else tip, "--", name)
            self.mode[name] = listed.split(" ")[0] if listed else "100644"
            old_lines = split_lines(old)
            self.text[name] = (old_lines, new)
            if not has_old:
                self.whole[name] = None
                added.add(name)
                continue
            if not has_new:
                # A deleted file goes to the owner of its last lines.
                owner = self.latest(self.blame(name, 1, len(old_lines))) if old_lines else None
                self.whole[name] = owner if owner is not None else self.file_owner(name)
                continue
            hunks = []
            # The fold's own settings: a diff.interHunkContext would merge two
            # owners' hunks, and a textconv would change the line numbers.
            diff = repo.out("diff", "-U0", "--inter-hunk-context=0", "--no-textconv", "--no-color", "--no-ext-diff",
                            "--no-renames", tip, commit, "--", name)
            for line in diff.split("\n"):
                match = HUNK.match(line)
                if not match:
                    continue
                a = int(match.group(1))
                b = int(match.group(2)) if match.group(2) is not None else 1
                c = int(match.group(3))
                d = int(match.group(4)) if match.group(4) is not None else 1
                if b:
                    owner = self.latest(self.blame(name, a, a + b - 1))
                else:
                    # An insertion after line a: the lines around it decide.
                    near = [x for x in (a, a + 1) if 1 <= x <= len(old_lines)]
                    owner = self.latest(self.blame(name, min(near), max(near))) if near else None
                hunks.append((a, b, c, d, owner if owner is not None else self.file_owner(name)))
            if hunks:
                self.hunks[name] = hunks
            else:
                # A mode change or a binary file: the whole file.
                self.whole[name] = self.file_owner(name)
        owners = set(h[4] for hs in self.hunks.values() for h in hs) | set(self.whole.values())
        real = sorted(o for o in owners if o is not None)
        if len(real) == 1:
            # A new file joins the commit's single target.
            for name in added:
                self.whole[name] = real[0]

    def touched(self, i: int) -> set[str]:
        if i not in self.touched_cache:
            self.touched_cache[i] = self.repo.files(self.chain[i])
        return self.touched_cache[i]

    def file_owner(self, name: str) -> int | None:
        """Lines no loop commit wrote: the latest loop commit that changed the
        file, else None."""
        found = [i for i in range(len(self.chain)) if name in self.touched(i)]
        return found[-1] if found else None

    def blame(self, name: str, start: int, end: int) -> list[int | None]:
        owners: list[int | None] = []
        # An empty --ignore-revs-file clears the revisions any
        # blame.ignoreRevsFile names, which would move lines to other commits.
        argv = ("blame", "--no-textconv", "--ignore-revs-file=", "--porcelain", "-L", "%d,%d" % (start, end),
                self.tip, "--", name)
        try:
            text = self.repo.out(*argv)
        except GitFailed as error:
            # A blame.ignoreRevsFile naming a missing file fails every blame,
            # and no setting clears it. Set where it usually is, in the global
            # or system config, it is left out.
            if "could not open object name list" not in error.call.err:
                raise
            text = self.repo.out(*argv, env={"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull})
        for line in text.split("\n"):
            match = BLAME.match(line)
            if match:
                owners.append(self.positions.get(match.group(1)))
        return owners

    @staticmethod
    def latest(owners: list[int | None]) -> int | None:
        known = [o for o in owners if o is not None]
        return max(known) if known else None

    def owners(self) -> dict[int | None, list[str]]:
        """owner -> sorted files, owner an index into chain or None."""
        found: dict[int | None, set[str]] = {}
        for name, hunks in self.hunks.items():
            for hunk in hunks:
                found.setdefault(hunk[4], set()).add(name)
        for name, owner in self.whole.items():
            found.setdefault(owner, set()).add(name)
        return dict((owner, sorted(names)) for owner, names in found.items())

    def tree_with(self, included: set[int]) -> str:
        """The tip's tree with the changes of the owners in included
        applied, written through a temporary index."""
        env = {"GIT_INDEX_FILE": self.index_path}
        try:
            self.repo.call("read-tree", self.tip, env=env)
            for name, hunks in self.hunks.items():
                if not any(h[4] in included for h in hunks):
                    continue
                old, new_data = self.text[name]
                if new_data is None:
                    continue
                new = split_lines(new_data)
                parts = []
                position = 0
                for a, b, c, d, owner in hunks:
                    start = a - 1 if b else a
                    parts += old[position:start]
                    parts += new[c - 1:c - 1 + d] if owner in included else old[start:start + b]
                    position = start + b
                parts += old[position:]
                self.put(name, b"".join(parts), env)
            for name, owner in self.whole.items():
                if owner not in included:
                    continue
                data = self.text[name][1]
                if data is None:
                    self.repo.call("update-index", "--force-remove", "--", name, env=env)
                else:
                    self.put(name, data, env)
            return self.repo.out("write-tree", env=env)
        finally:
            remove(self.index_path)

    def put(self, name: str, data: bytes, env: dict[str, str]) -> None:
        blob = self.repo.out("hash-object", "-w", "--stdin", data=data)
        self.repo.call("update-index", "--add", "--cacheinfo", "%s,%s,%s" % (self.mode[name], blob, name), env=env)


def remove(path: str) -> None:
    for candidate in (path, path + ".lock"):
        if os.path.lexists(candidate):
            try:
                os.remove(candidate)
            except OSError:
                pass


def merge_tree(repo: Repo, base: str, ours: str, theirs: str) -> str | None:
    """The tree of theirs' change (base to theirs) applied to ours, or None on
    a conflict."""
    result = repo.call("merge-tree", "--write-tree", "--no-messages", "--merge-base=" + base, ours, theirs,
                       ok=(0, 1))
    if result.code == 1:
        return None
    return result.out.split("\n")[0].strip()


def replay(repo: Repo, committer: Committer, chain: list[str], start: int, parent: str) -> list[str] | None:
    """chain[start:] replayed onto parent: the new commits, or None on a
    conflict."""
    made: list[str] = []
    for sha in chain[start:]:
        tree = merge_tree(repo, repo.parent(sha), parent, sha)
        if tree is None:
            return None
        parent = committer.make(tree, parent, sha)
        made.append(parent)
    return made


def absorb(
    repo: Repo, committer: Committer, base: str, chain_end: str, signed: str, index_path: str,
) -> tuple[list[str], list[list[tuple[str, list[str] | None, str | None]]]]:
    """(chain, sources): the folded history oldest first, and for each of its
    commits the (original sha, files or None for the whole commit, why it
    stayed) it was built from."""
    chain = [s for s in repo.out("rev-list", "--reverse", "%s..%s" % (base, chain_end)).split("\n") if s]
    sources: list[list[tuple[str, list[str] | None, str | None]]] = [[(sha, None, ROUND_ONE)] for sha in chain]
    later = [s for s in repo.out("rev-list", "--reverse", "%s..%s" % (chain_end, signed)).split("\n") if s]
    for commit in later:
        tip = chain[-1] if chain else base
        split = Split(repo, chain, tip, commit, index_path)
        owners = split.owners()
        done: set[int] = set()
        for i in sorted(o for o in owners if o is not None):
            want = split.tree_with(done | {i})
            fix = committer.make(want, chain[-1], commit)
            tree = merge_tree(repo, chain[-1], chain[i], fix)
            folded: list[str] | None = None
            if tree is not None:
                head = committer.make(tree, repo.parent(chain[i]), chain[i])
                rest = replay(repo, committer, chain, i + 1, head)
                if rest is not None and repo.tree((rest or [head])[-1]) == want:
                    folded = chain[:i] + [head] + rest
            if folded is None:
                continue  # it would conflict: these lines stay on top
            chain = folded
            done.add(i)
            sources[i].append((commit, owners[i], None))
        if repo.tree(chain[-1] if chain else base) != repo.tree(commit):
            left = set(owners) - done
            stay = sorted(set(name for owner in left for name in owners[owner]))
            why = NO_OWNER if left == {None} else CONFLICT
            chain.append(committer.make(repo.tree(commit), chain[-1] if chain else base, commit))
            sources.append([(commit, stay if done else None, why)])
    return chain, sources


def resign(repo: Repo, committer: Committer, base: str, chain: list[str], originals: list[str]) -> list[str]:
    """The chain with every commit the absorb made made again, signed: the
    absorb's own commits are unsigned. A leading commit the fold kept as it
    was stays."""
    kept = 0
    while kept < len(chain) and kept < len(originals) and chain[kept] == originals[kept]:
        kept += 1
    result = chain[:kept]
    parent = chain[kept - 1] if kept else base
    for sha in chain[kept:]:
        parent = committer.make(repo.tree(sha), parent, sha, sign=True)
        result.append(parent)
    return result


def report(
    repo: Repo, chain: list[str], sources: list[list[tuple[str, list[str] | None, str | None]]], earlier: str,
) -> list[str]:
    """The report lines; earlier names the history the chain began as:
    "round 1", or "folded after round 2"."""
    lines: list[str] = []
    for sha, source in zip(chain, sources):
        lines.append("  %s %s" % (repo.short(sha), repo.subject(sha)))
        for original, files, why in source:
            what = "%s %s" % (repo.short(original), repo.subject(original))
            if why == ROUND_ONE:
                lines.append("      %s (%s)" % (what, earlier))
            elif why:
                part = "" if files is None else ": %s" % and_list(files)
                lines.append("      %s%s, its own commit: %s" % (what, part, why))
            elif files is not None:
                lines.append("    + %s: %s" % (what, and_list(files)))
    return lines


class Result:
    """What a fold built: how many commits the loop had, the final chain oldest
    first, its tip, and the report lines."""

    def __init__(self, before: int, chain: list[str], tip: str, lines: list[str]) -> None:
        self.before = before
        self.chain = chain
        self.tip = tip
        self.lines = lines
