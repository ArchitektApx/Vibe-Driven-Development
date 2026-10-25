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
    if len(found) == 1:
        return Installed(directory, os.path.join(directory, found[0]), found)
    return Installed(directory, None, found)


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
