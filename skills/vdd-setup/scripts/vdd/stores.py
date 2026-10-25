"""Skill stores and the Present search.

A root is a directory a Harness reads skills from: a skill store, where the
skills CLI writes, or a plugin cache, where a Harness installs plugins. The
search matches <skill>/SKILL.md at any depth, following symlinked
directories, so a skills-CLI install that links a skill into a store counts.
"""

from __future__ import annotations

import glob
import os
from typing import Iterable

from . import places

SKILL_STORE = "skill store"
PLUGIN_CACHE = "plugin cache"
USER = "user"
PROJECT = "project"

# Directories that hold no installed skill and can be large.
SKIPPED_DIRS = {".git", "node_modules"}


def env(name: str) -> str:
    """An environment variable, empty when unset."""
    return os.environ.get(name, "")


class Root:
    """One root a Harness reads skills from.

    pattern, on a plugin cache, is a glob below path that the search starts
    from, such as */mattpocock-skills for Claude Code's cache."""

    def __init__(self, path: str, kind: str, scope: str, owner: str, pattern: str | None = None) -> None:
        self.path = os.path.normpath(path)
        self.kind = kind
        self.scope = scope
        self.owner = owner
        self.pattern = pattern

    def key(self) -> tuple[str, str | None]:
        return (os.path.normcase(self.path), self.pattern)

    def label(self, cwd: str) -> str:
        return display(self.path, cwd)

    def starts(self) -> list[str]:
        """The directories the search walks."""
        if not self.pattern:
            return [self.path]
        return sorted(glob.glob(os.path.join(glob.escape(self.path), self.pattern)))


def display(path: str, cwd: str) -> str:
    """A path as the user reads it: ./ under the project, ~/ under home."""
    path = os.path.normpath(path)
    for base, prefix in ((cwd, "."), (places.home(), "~")):
        base = os.path.normpath(base)
        if path == base:
            return prefix
        if path.startswith(base + os.sep):
            return prefix + "/" + path[len(base) + 1:].replace(os.sep, "/")
    return path


class Hit:
    """One SKILL.md the search found: its root and its path."""

    def __init__(self, root: Root, path: str) -> None:
        self.root = root
        self.path = path

    def parts(self) -> list[str]:
        """The path's directories below the root's own directory."""
        rel = os.path.relpath(self.path, self.root.path)
        return rel.replace(os.sep, "/").split("/")


class Store:
    """Where a set of hits sits: a root, and on a plugin cache the
    marketplace and plugin the path names."""

    def __init__(self, hit: Hit, cwd: str) -> None:
        self.root = hit.root
        self.kind = hit.root.kind
        self.scope = hit.root.scope
        self.owner = hit.root.owner
        self.label = hit.root.label(cwd)
        parts = hit.parts()
        self.first = parts[0] if len(parts) > 1 else ""
        self.second = parts[1] if len(parts) > 2 else ""

    def key(self) -> tuple[tuple[str, str | None] | str, ...]:
        if self.kind == PLUGIN_CACHE:
            return (self.root.key(), self.first, self.second)
        return (self.root.key(),)


def search(roots: Iterable[Root], skills: Iterable[str]) -> dict[str, list[Hit]]:
    """skill -> list of Hit, for each skill with a SKILL.md under the roots."""
    wanted = set(skills)
    hits: dict[str, list[Hit]] = {}
    for root in roots:
        for start in root.starts():
            if not os.path.isdir(start):
                continue
            seen = set()
            for directory, dirs, files in os.walk(start, followlinks=True):
                real = os.path.realpath(directory)
                if real in seen:
                    dirs[:] = []
                    continue
                seen.add(real)
                dirs[:] = sorted(d for d in dirs if d not in SKIPPED_DIRS)
                name = os.path.basename(directory)
                if name in wanted and "SKILL.md" in files:
                    hits.setdefault(name, []).append(Hit(root, os.path.join(directory, "SKILL.md")))
    return hits


def union(root_lists: Iterable[Iterable[Root]]) -> list[Root]:
    """Roots from several Harnesses, each once, in order."""
    seen: set[tuple[str, str | None]] = set()
    out: list[Root] = []
    for roots in root_lists:
        for root in roots:
            if root.key() in seen:
                continue
            seen.add(root.key())
            out.append(root)
    return out


# The skills-CLI routes every Harness shares, by the scope of the store.

def cli_add(scope: str) -> str:
    if scope == PROJECT:
        return "npx skills@latest add mattpocock/skills (no -g, run in this repository)"
    return "npx skills@latest add -g mattpocock/skills"


def cli_update(scope: str) -> str:
    if scope == PROJECT:
        return "npx skills update -p"
    return "npx skills update -g"
