"""The baseline file Codex keeps for an approval from before Codex 0.164, an
entry with trusted_hash and no trusted_content_hash: the content hash Codex
pinned for the plugin, in .hook-trust/ beside config.toml."""

from __future__ import annotations

import hashlib
import os

from ... import places, textfile
from ...stores import env


def config_spelling(home: str) -> str:
    """config.toml's path as Codex spells it when it names the baseline: in
    the real path of CODEX_HOME when that is set, else in ~/.codex
    unresolved."""
    if env("CODEX_HOME"):
        return os.path.join(os.path.realpath(home), "config.toml")
    return os.path.join(places.home(), ".codex", "config.toml")


def path(home: str, marketplace: str) -> str:
    """The baseline file of vdd@<marketplace>: named by the SHA-256 of the
    config path's and the plugin id's bytes, each after its length."""
    spelled = os.fsencode(config_spelling(home))
    plugin = ("vdd@%s" % marketplace).encode("utf-8")
    digest = hashlib.sha256()
    for part in (spelled, plugin):
        digest.update(len(part).to_bytes(8, "little") + part)
    return os.path.join(home, ".hook-trust", digest.hexdigest())


def read(found: str) -> bytes | None:
    """The baseline's bytes as they are, or None when there is no such file.
    Raises OSError when it cannot be read."""
    try:
        return textfile.read_bytes(found)
    except (FileNotFoundError, NotADirectoryError):
        return None
