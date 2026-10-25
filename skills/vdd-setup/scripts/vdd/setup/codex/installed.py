"""The installed copy of VDD Codex runs for one marketplace: the active
version directory under <Codex home>/plugins/cache/<marketplace>/vdd/, picked
as Codex picks it."""

from __future__ import annotations

import os
import re
import stat

from .fingerprint import REPARSE_POINT

NAME = re.compile(r"[A-Za-z0-9.+_-]+")
MARKETPLACE = re.compile(r"[A-Za-z0-9._-]+")


class Installed:
    """directory, the vdd directory searched; root, the active version's
    directory, or None; candidates, the version names found there."""

    def __init__(self, directory: str, root: str | None, candidates: list[str]) -> None:
        self.directory = directory
        self.root = root
        self.candidates = candidates


def find(home: str, marketplace: str) -> Installed:
    directory = os.path.join(home, "plugins", "cache", marketplace, "vdd")
    if not MARKETPLACE.fullmatch(marketplace) or marketplace in (".", ".."):
        return Installed(directory, None, [])
    found = candidates(directory)
    active = pick(found)
    return Installed(directory, os.path.join(directory, active) if active else None, found)


def pick(names: list[str]) -> str | None:
    """The version Codex runs: local, else the one name, else the highest by
    SemVer precedence when every name is a SemVer version without a build
    part. None for no name, or for a set Codex orders by a comparison that is
    not a total order, so no port can reproduce its pick."""
    if "local" in names:
        return "local"
    if len(names) == 1:
        return names[0]
    keys = [precedence(name) for name in names]
    if not names or any(key is None for key in keys):
        return None
    return max(zip(keys, names))[1]


SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
)


def precedence(name: str) -> tuple | None:
    """A sort key in SemVer 2.0.0 precedence for a version with no build
    part, or None. A release sorts above its prereleases; numeric
    identifiers compare as numbers and below alphanumeric ones; a shorter
    run of equal identifiers sorts first."""
    match = SEMVER.fullmatch(name)
    if not match:
        return None
    core = tuple(int(part) for part in match.group(1, 2, 3))
    if match.group(4) is None:
        return core + (1, ())
    identifiers = tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in match.group(4).split("."))
    return core + (0, identifiers)


def candidates(directory: str) -> list[str]:
    """The names Codex counts as versions: directories, not symbolic links
    or junctions, named with ASCII letters, digits and .+_- only."""
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    found = []
    for name in names:
        if not NAME.fullmatch(name):
            continue
        try:
            info = os.lstat(os.path.join(directory, name))
        except OSError:
            continue
        if stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & REPARSE_POINT:
            found.append(name)
    return found
