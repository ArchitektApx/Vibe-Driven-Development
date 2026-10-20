"""The Codex Stop hook: codex-stop.

Codex runs it at every turn end of a Session whose project holds an armed
Codex wait, .scratch/<slug>/codex-armed-<session id> (the hook string's shell
guard keeps Python from starting otherwise). It reads the hook input on
standard input and finds this Session's armed file, which `doorbell wait
--harness codex` wrote, in any loop's tracker directory: the loop is that
directory. It claims the wait with an exclusive marker, deletes the file, waits
on the Doorbell file as `wait` does, and on a pending Doorbell or TIMEOUT prints Codex's block decision, so
Codex continues the Session with the reason as its prompt. It reads no Loop
file: only a Codex wait writes an armed file.

It exits 0 on every path, exceptions included: Codex reads exit 2 as a block
and repeats it without limit. Everything it needs is imported here, at start,
so a Setup swapping the Shared copy mid-wait cannot mix versions.
"""

from __future__ import annotations

import json
import os
import sys

from . import doorbells, loopfile, places, textfile
from .harness import codex as codex_harness
from .out import Output


def run(argv: list[str]) -> int:
    if "--help" in argv or "-h" in argv:
        out = Output()
        out.line("codex-stop: the Codex Stop hook. Codex runs it at a turn end, with the hook input on standard input.")
        return out.finish("Nothing to run: a Role never runs codex-stop. Run the command your skill names.")
    try:
        hook()
    except BaseException:  # noqa: B902 - exit 0 on every path
        pass
    return 0


def hook() -> None:
    cwd = os.getcwd()
    data = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else b""
    try:
        event = json.loads(textfile.decode(data))
    except ValueError:
        return
    session = event.get("session_id") if isinstance(event, dict) else None
    if not isinstance(session, str) or not doorbells.THREAD_ID.match(session):
        return
    found = armed_files(cwd, session)
    if not found:
        return
    # Two loops armed for one Session: the newer wait is the live one, and
    # the older file would keep the guard true for nothing.
    found.sort()
    for _, path, _ in found[:-1]:
        try:
            os.remove(path)
        except OSError:
            pass
    _, path, slug = found[-1]
    claimed = claim(path, os.path.join(os.path.dirname(path), loopfile.CLAIM_PREFIX + session))
    if claimed is None:
        return
    role, count = claimed
    place = doorbells.Place(cwd, slug)
    entry = places.shared_entry()
    harness = codex_harness.HARNESS
    if doorbells.watch(place, role, floor=count):
        reason = "A Doorbell for the %s is waiting. Next: run %s" % (
            role, doorbells.take_command(role, harness, slug, entry))
    else:
        reason = "TIMEOUT. Next: " + doorbells.timeout_next(role, harness, slug, entry)
    reason = "".join(c for c in reason if ord(c) >= 32 and ord(c) != 127)
    text = json.dumps({"decision": "block", "reason": reason}, ensure_ascii=True)
    sys.stdout.buffer.write((text + "\n").encode("ascii"))
    sys.stdout.buffer.flush()


def armed_files(root: str, session: str) -> list[tuple[float, str, str]]:
    """[(modification time, path, slug)] of .scratch/*/codex-armed-<session>."""
    found: list[tuple[float, str, str]] = []
    scratch = loopfile.scratch(root)
    try:
        names = os.listdir(scratch)
    except OSError:
        return found
    for name in names:
        path = os.path.join(scratch, name, loopfile.ARMED_PREFIX + session)
        try:
            if os.path.isfile(path):
                found.append((os.path.getmtime(path), path, name))
        except OSError:
            pass
    return found


def claim(path: str, marker: str) -> tuple[str, int] | None:
    """Take the armed wait: of turn ends racing for it exactly one creates the
    claim marker, so the others find it there and take nothing. The winner
    reads the armed file, then deletes it first and the marker second, so a
    later racer finds no armed file once the marker is gone. (Role, count), or
    None when another turn end has the wait, the file is gone, cannot be read
    or is not well formed (a malformed one is deleted); the claimer's own
    marker never outlives the call."""
    try:
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except OSError:
        return None
    try:
        try:
            lines = textfile.lines(path, doorbells.LOCK_RETRY_SECONDS)
        except OSError:
            return None
        claimed = well_formed(lines)
        if lines is not None:
            try:
                os.remove(path)
            except OSError:
                pass
        return claimed
    finally:
        try:
            os.remove(marker)
        except OSError:
            pass


def well_formed(lines: list[str] | None) -> tuple[str, int] | None:
    """(Role, count) of an armed file's lines, or None."""
    if lines is None or len(lines) < 2 or lines[0] != doorbells.ARMED_PREFIX + doorbells.ARMED_VERSION:
        return None
    parts = lines[1].split()
    if len(parts) != 2 or parts[0] not in doorbells.ROLES or not parts[1].isdigit():
        return None
    return parts[0], int(parts[1])
