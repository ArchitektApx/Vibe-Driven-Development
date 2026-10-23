"""The Codex armed file, .scratch/<slug>/codex-armed-<thread id>, and its
claim marker, .scratch/<slug>/codex-claim-<thread id>: their names, the
armed file's header, arming, claiming, reading and deleting.

A Codex wait (`doorbell wait` on Codex) arms the file; the Codex Stop hook
(`codex-stop`) claims and deletes it; closing a loop deletes every armed file
and claim marker in it. The file name is coupled to the two shell guards of
the Stop hook in .codex-plugin/plugin.json, which start the hook only while a
.scratch/*/codex-armed-* file exists: renaming FILE_PREFIX breaks the hook
until both guards change with it. A claim marker's name must not start with
FILE_PREFIX, or the guards would see it as an armed wait.
"""

from __future__ import annotations

import os

from . import textfile

FILE_PREFIX = "codex-armed-"
CLAIM_PREFIX = "codex-claim-"
HEADER = "vdd codex-armed "
VERSION = "1"


def path(directory: str, thread: str) -> str:
    return os.path.join(directory, FILE_PREFIX + thread)


def claim_path(directory: str, thread: str) -> str:
    return os.path.join(directory, CLAIM_PREFIX + thread)


def arm(directory: str, thread: str, role: str, count: int) -> None:
    """Write the thread's armed file for role, which has seen count Doorbell
    lines. Raises OSError."""
    os.makedirs(directory, exist_ok=True)
    # A claim marker a killed hook left would block this wait.
    try:
        os.remove(claim_path(directory, thread))
    except FileNotFoundError:
        pass
    textfile.write_text(path(directory, thread), "%s%s\n%s %d\n" % (HEADER, VERSION, role, count))


def files(scratch: str, thread: str) -> list[tuple[float, str, str]]:
    """[(modification time, path, slug)] of <scratch>/*/codex-armed-<thread>."""
    found: list[tuple[float, str, str]] = []
    try:
        names = os.listdir(scratch)
    except OSError:
        return found
    for name in names:
        armed = path(os.path.join(scratch, name), thread)
        try:
            if os.path.isfile(armed):
                found.append((os.path.getmtime(armed), armed, name))
        except OSError:
            pass
    return found


def claim(armed: str, thread: str, roles: tuple[str, ...]) -> tuple[str, int] | None:
    """Take the armed wait: of turn ends racing for it exactly one creates the
    claim marker, so the others find it there and take nothing. The winner
    reads the armed file, then deletes it first and the marker second, so a
    later racer finds no armed file once the marker is gone. (Role, count), or
    None when another turn end has the wait, the file is gone, cannot be read
    or is not well formed (a malformed one is deleted). The claimer's own
    marker outlives the call only when the armed file cannot be deleted, so no
    later turn end takes the wait again; the next arm clears it."""
    marker = claim_path(os.path.dirname(armed), thread)
    try:
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except OSError:
        return None
    keep = False
    try:
        try:
            lines = textfile.lines(armed)
        except OSError:
            return None
        claimed = well_formed(lines, roles)
        if lines is not None:
            keep = not removed(armed)
        return claimed
    finally:
        if not keep:
            try:
                os.remove(marker)
            except OSError:
                pass


def removed(name: str) -> bool:
    """Delete name, retried as textfile.retried says: on Windows a program
    holding the file open refuses the delete for a moment. True once the
    file is gone."""
    try:
        textfile.retried(lambda: os.remove(name))
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def well_formed(lines: list[str] | None, roles: tuple[str, ...]) -> tuple[str, int] | None:
    """(Role, count) of an armed file's lines, or None."""
    if lines is None or len(lines) < 2 or lines[0] != HEADER + VERSION:
        return None
    parts = lines[1].split()
    if len(parts) != 2 or parts[0] not in roles or not parts[1].isdigit():
        return None
    return parts[0], int(parts[1])


def delete(directory: str) -> list[str]:
    """Delete every armed file in directory, and every claim marker; the
    names of the armed files deleted."""
    gone: list[str] = []
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return gone
    for name in names:
        if name.startswith((FILE_PREFIX, CLAIM_PREFIX)):
            try:
                os.remove(os.path.join(directory, name))
                if name.startswith(FILE_PREFIX):
                    gone.append(name)
            except OSError:
                pass
    return gone
