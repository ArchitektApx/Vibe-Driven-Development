"""The journal: every write of the idea store as one move, so that
a killed run cannot leave half done.

A save writes the journal whole first (every file's before and after bytes
in base64, and the folder moves), then the folder moves and the files, and
deletes the journal last. The next command that holds the lock
finds a journal left behind and rolls it forward when every file still holds
the journal's before or after bytes, or back otherwise, leaving a file
changed since as it is. A journal not in this tool's form, or naming a path
outside the store, is set aside and never followed. Nothing is synced to
disk: a power loss mid-write is not covered.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import time
from typing import Any, List, Optional, Tuple

from .. import textfile
from ..out import TELL
from .ideafile import SLUG_PATTERN, is_idea_name
from .lock import Lock
from .removed import REMOVED
from .store import Store, read_once, rel, state_dir, store_dir

# "pid" is read, never written: an earlier 0.16 beta wrote it. The pid is in
# the journal's file name.
KEYS = ("label", "pid", "ops", "dirs")
RESEARCH_DIR = re.compile("^research/" + SLUG_PATTERN + "$")
TEMP = re.compile(r"\.vdd-new-\d+$")

Op = Tuple[str, Optional[bytes], Optional[bytes]]
Ops = List[Op]
Dirs = List[Tuple[str, str]]


def journal_dir(root: str) -> str:
    return os.path.join(state_dir(root), "journal")


def b64(data: bytes | None) -> str | None:
    return None if data is None else base64.b64encode(data).decode("ascii")


def unb64(text: Any) -> bytes | None:
    """The bytes of a journal's base64 field; ValueError when it is not one."""
    if text is None:
        return None
    if not isinstance(text, str):
        raise ValueError("a file's bytes are not base64 text")
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error):
        raise ValueError("a file's bytes are not base64 text")


def write_journal(root: str, label: str, ops: Ops, dirs: Dirs) -> str:
    folder = journal_dir(root)
    os.makedirs(folder, exist_ok=True)
    now = time.time()
    name = "%s-%d-%06d.json" % (time.strftime("%Y%m%dT%H%M%S", time.localtime(now)), os.getpid(),
                                int((now % 1) * 1e6))
    path = os.path.join(folder, name)
    data = {"label": label,
            "ops": [{"path": n, "before": b64(b), "after": b64(a)} for n, b, a in ops],
            "dirs": [list(m) for m in dirs]}
    textfile.write(path, json.dumps(data).encode("ascii"))
    return path


def current(path: str) -> bytes | None:
    return textfile.read_bytes(path) if os.path.isfile(path) else None


def apply(root: str, ops: Ops, dirs: Dirs, side: str) -> None:
    """Bring every file and folder of a journaled move to one side, "after"
    or "before". Folders move first going forward (research moves before the
    files that link it) and last going back. A file that already holds the
    side's bytes is not touched."""
    base = store_dir(root)

    def move_dirs() -> None:
        for old, new in (dirs if side == "after" else list(reversed(dirs))):
            src, dst = (old, new) if side == "after" else (new, old)
            src, dst = os.path.join(base, *src.split("/")), os.path.join(base, *dst.split("/"))
            if os.path.isdir(src) and not os.path.exists(dst):
                os.rename(src, dst)

    if side == "after":
        move_dirs()
    for name, before, after in ops:
        want = after if side == "after" else before
        path = os.path.join(base, name)
        if current(path) == want:
            continue
        if want is None:
            if os.path.lexists(path):
                os.remove(path)
        else:
            textfile.write(path, want)
    if side == "before":
        move_dirs()


def sweep_temp(root: str) -> None:
    """Remove the temp files a killed write left (*.vdd-new-<pid>)."""
    base = store_dir(root)
    for folder in (base, state_dir(root), journal_dir(root)):
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            if TEMP.search(name):
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    pass


def save(store: Store, label: str) -> list[str]:
    """Write every change of one command as one move: the journal, the
    folder moves, the files, then the journal goes. A write
    refused partway rolls back its own changes and removes its journal.
    Returns the names written."""
    ops = store.ops()
    if not ops and not store.dir_moves:
        return []
    dirs = list(store.dir_moves)
    sweep_temp(store.root)
    path = write_journal(store.root, label, ops, dirs)
    try:
        apply(store.root, ops, dirs, "after")
    except BaseException:
        try:
            apply(store.root, ops, dirs, "before")
            os.remove(path)
        except OSError:
            pass
        raise
    store.written(ops)
    os.remove(path)
    return [name for name, _, _ in ops]


def inside_store(base: str, name: Any, kind: str) -> bool:
    """Whether a path read from a journal names what this tool journals, an
    idea file or removed.md at the store's top ("file") or a research folder
    ("dir"), and resolves inside the store: no absolute path, no "..", no
    symlinked folder leading out."""
    if not isinstance(name, str):
        return False
    if kind == "file" and not (is_idea_name(name) or name == REMOVED):
        return False
    if kind == "dir" and not RESEARCH_DIR.match(name):
        return False
    real = os.path.realpath(base)
    full = os.path.join(base, *name.split("/"))
    for path in (os.path.dirname(full), full):
        resolved = os.path.realpath(path)
        if resolved != real and not resolved.startswith(real + os.sep):
            return False
    return True


def read_journal(base: str, path: str) -> tuple[str, Ops, Dirs]:
    """(label, ops, dirs) of a journal in the form this tool writes, every
    path checked before anything is touched; ValueError naming what is wrong
    otherwise."""
    try:
        data = json.loads(read_once(path) or "")
    except ValueError:
        raise ValueError("it is not JSON")
    if not isinstance(data, dict) or not isinstance(data.get("ops"), list) or not isinstance(data.get("dirs", []),
                                                                                            list):
        raise ValueError("it is not in the form this tool writes")
    extra = sorted(str(k) for k in data if k not in KEYS)
    if extra:
        raise ValueError("it holds fields this tool does not write (%s)" % ", ".join(extra))
    ops: Ops = []
    for entry in data["ops"]:
        if not isinstance(entry, dict) or sorted(entry) != ["after", "before", "path"]:
            raise ValueError("a file entry is not in the form this tool writes")
        if not inside_store(base, entry["path"], "file"):
            raise ValueError("it names %r, which is no idea file inside the store" % (entry["path"],))
        ops.append((entry["path"], unb64(entry["before"]), unb64(entry["after"])))
    dirs: Dirs = []
    for move in data.get("dirs", []):
        if not isinstance(move, list) or len(move) != 2:
            raise ValueError("a folder move is not in the form this tool writes")
        for name in move:
            if not inside_store(base, name, "dir"):
                raise ValueError("it names %r, which is no research folder inside the store" % (name,))
        dirs.append((move[0], move[1]))
    label = data.get("label")
    return (label if isinstance(label, str) else "?"), ops, dirs


def journal_files(base: str, path: str) -> list[str]:
    """The idea files a journal names, as far as they pass inside_store."""
    try:
        data = json.loads(read_once(path) or "")
        return sorted({e["path"] for e in data["ops"] if isinstance(e, dict) and inside_store(base, e.get("path"),
                                                                                               "file")})
    except (ValueError, KeyError, TypeError, AttributeError):
        return []


def file_side(path: str, before: bytes | None, after: bytes | None) -> str:
    cur = current(path)
    if cur == after:
        return "after"
    if cur == before:
        return "before"
    return "other"


def pending(root: str) -> bool:
    try:
        return any(n.endswith(".json") for n in os.listdir(journal_dir(root)))
    except OSError:
        return False


def recover(lock: Lock) -> list[str]:
    """Finish or roll back the writes a killed run left in the journal, and
    sweep its temp files; the lines to print. Runs only while this run holds
    the lock, so a journal here is never a running writer's, or where the
    lock is not supported."""
    root = lock.root
    sweep_temp(root)
    try:
        names = sorted(n for n in os.listdir(journal_dir(root)) if n.endswith(".json"))
    except OSError:
        return []
    base = store_dir(root)
    lines: list[str] = []
    for name in names:
        path = os.path.join(journal_dir(root), name)
        try:
            label, ops, dirs = read_journal(base, path)
        except ValueError as why:
            named = journal_files(base, path)
            aside = path + ".unreadable"
            os.replace(path, aside)
            lines.append("A journal of an interrupted write was not used, because %s; nothing it names was touched, "
                         "and it was set aside as %s.%s" % (why, rel(root, aside), (
                             " It names %s, which may be half written: brainstorm check shows what is wrong."
                             % ", ".join(named)) if named else ""))
            continue
        lines += settle(root, label, ops, dirs)
        os.remove(path)
    return lines


def settle(root: str, label: str, ops: Ops, dirs: Dirs) -> list[str]:
    """Roll one journal forward, or back when a file changed since: the lines
    to print."""
    base = store_dir(root)
    sides = [file_side(os.path.join(base, n), b, a) for n, b, a in ops]
    dir_sides: list[str] = []
    for old, new in dirs:
        has_old = os.path.isdir(os.path.join(base, *old.split("/")))
        has_new = os.path.isdir(os.path.join(base, *new.split("/")))
        dir_sides.append("after" if has_new and not has_old else "before" if has_old and not has_new else "other")
    others = [op[0] for op, side in zip(ops, sides) if side == "other"]
    others += ["research folder %s" % d[0] for d, side in zip(dirs, dir_sides) if side == "other"]
    if not others:
        apply(root, ops, dirs, "after")
        return ["An interrupted write (%s) was finished." % label]
    apply(root, [op for op, side in zip(ops, sides) if side != "other"],
          [d for d, side in zip(dirs, dir_sides) if side != "other"], "before")
    lines = ["An interrupted write (%s) was rolled back: %s changed since and %s left as it is."
             % (label, ", ".join(others), "was" if len(others) == 1 else "were")]
    created = [op[0] for op, side in zip(ops, sides) if side == "other" and op[1] is None]
    restored = [op[0] for op, side in zip(ops, sides) if side != "other" and op[2] is None and op[1] is not None]
    if created:
        lines.append(TELL % (
            "An interrupted write (%s) was undone, but %s, which it had created, was edited since and is kept as it "
            "is%s. Check whether %s the same idea twice and keep one." % (
                label, " and ".join(created),
                ("; the undo brought back %s" % " and ".join(restored)) if restored else "",
                "they hold" if restored or len(created) > 1 else "it holds")))
    return lines
