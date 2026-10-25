"""Codex's content hash of an installed plugin copy, ported from Codex 0.164's
plugin_fingerprint.rs: what Codex compares with the trusted_content_hash it
stored when the user trusted the plugin's hook.

The walk is depth-first pre-order, each directory's children sorted by their
own name as bytes. Each entry feeds its path relative to the root, joined
with the separator, then "directory", or "file" with its size and bytes.
"""

from __future__ import annotations

import hashlib
import os
import stat

PRIMER = b"codex-plugin-bundle-v1"
SKIPPED_NAMES = ("__pycache__", ".venv")
SKIPPED_ENDINGS = (".pyc", ".egg-info")
REPARSE_POINT = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT: a junction or a symbolic link on Windows

SPECIAL = "special"      # not a plain file or directory: a symbolic link, a junction, a device
UNREADABLE = "unreadable"
RESIZED = "resized"      # a file whose size changed while it was read


class Unhashable(Exception):
    """The copy holds an entry the hash cannot take, so Codex cannot either.
    relative is its path under the root, joined with /; kind, SPECIAL,
    UNREADABLE or RESIZED; error, the OSError behind UNREADABLE."""

    def __init__(self, relative: str, kind: str, error: OSError | None = None) -> None:
        Exception.__init__(self, relative)
        self.relative = relative
        self.kind = kind
        self.error = error


def skipped(name: str) -> bool:
    return name in SKIPPED_NAMES or name.endswith(SKIPPED_ENDINGS)


def content_hash(root: str, sep: str = os.sep) -> str:
    """sha256:<hex> of the tree at root, as Codex hashes it with sep between
    path parts. Raises Unhashable."""
    digest = hashlib.sha256(PRIMER)
    pending: list[tuple[str, ...]] = [()]
    while pending:
        parts = pending.pop()
        if parts and skipped(parts[-1]):
            continue
        relative = "/".join(parts)
        raw = os.fsencode(sep.join(parts)) if parts else b""
        digest.update(len(raw).to_bytes(8, "little") + raw)
        path = os.path.join(root, *parts)
        try:
            found = os.lstat(path)
            if getattr(found, "st_file_attributes", 0) & REPARSE_POINT:
                raise Unhashable(relative, SPECIAL)
            if stat.S_ISDIR(found.st_mode):
                digest.update(b"directory")
                names = sorted(os.listdir(path), key=os.fsencode)
                pending.extend(parts + (name,) for name in reversed(names))
            elif stat.S_ISREG(found.st_mode):
                with open(path, "rb") as handle:
                    data = handle.read()
                if len(data) != found.st_size:
                    raise Unhashable(relative, RESIZED)
                digest.update(b"file" + found.st_size.to_bytes(8, "little") + data)
            else:
                raise Unhashable(relative, SPECIAL)
        except OSError as error:
            raise Unhashable(relative, UNREADABLE, error)
    return "sha256:" + digest.hexdigest()
