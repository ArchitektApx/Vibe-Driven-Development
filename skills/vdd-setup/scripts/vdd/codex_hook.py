"""The Codex Stop hook: codex-stop.

Codex runs it at every turn end of a Session whose project holds an armed
Codex wait, .scratch/<slug>/codex-armed-<session id> (the hook string's shell
guard keeps Python from starting otherwise). It reads the hook input on
standard input and finds this Session's armed file, which `doorbell wait
--harness codex` wrote, in any loop's tracker directory: the loop is that
directory. It claims (deletes) the file, waits on the Doorbell file as `wait`
does, and on a pending Doorbell or TIMEOUT prints Codex's block decision, so
Codex continues the Session with the reason as its prompt. It reads no Loop
file: only a Codex wait writes an armed file.

It exits 0 on every path, exceptions included: Codex reads exit 2 as a block
and repeats it without limit. Everything it needs is imported here, at start,
so a Setup swapping the Shared copy mid-wait cannot mix versions.
"""

import json
import os
import sys

from . import doorbell, loopfile, places, textfile
from .harness import codex as codex_harness
from .out import Output


def run(argv):
    if "--help" in argv or "-h" in argv:
        out = Output()
        out.line("codex-stop: the Codex Stop hook. Codex runs it at a turn end, with the hook input on standard input.")
        return out.finish("Nothing to run: a Role never runs codex-stop. Run the command your skill names.")
    try:
        hook()
    except BaseException:  # noqa: B902 - exit 0 on every path
        pass
    return 0


def hook():
    cwd = os.getcwd()
    data = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else b""
    try:
        event = json.loads(textfile.decode(data))
    except ValueError:
        return
    session = event.get("session_id") if isinstance(event, dict) else None
    if not isinstance(session, str) or not doorbell.THREAD_ID.match(session):
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
    claimed = claim(path)
    if claimed is None:
        return
    role, count = claimed
    place = doorbell.Place(cwd, slug)
    entry = places.shared_entry()
    harness = codex_harness.HARNESS
    if doorbell.watch(place, role, floor=count):
        reason = "A Doorbell for the %s is waiting. Next: run %s" % (
            role, doorbell.take_command(role, harness, slug, entry))
    else:
        reason = "TIMEOUT. Next: " + doorbell.timeout_next(role, harness, slug, entry)
    reason = "".join(c for c in reason if ord(c) >= 32 and ord(c) != 127)
    text = json.dumps({"decision": "block", "reason": reason}, ensure_ascii=True)
    sys.stdout.buffer.write((text + "\n").encode("ascii"))
    sys.stdout.buffer.flush()


def armed_files(root, session):
    """[(modification time, path, slug)] of .scratch/*/codex-armed-<session>."""
    found = []
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


def claim(path):
    """Take the armed file: rename it away, so of two turn ends racing for it
    only one gets it, then read and delete it. (Role, count), or None when it
    is not there or not well formed (it is deleted either way)."""
    if not os.path.isfile(path):
        return None
    taken = "%s.claimed-%d" % (path, os.getpid())
    try:
        os.rename(path, taken)
    except OSError:
        return None
    try:
        lines = textfile.lines(taken) or []
    finally:
        try:
            os.remove(taken)
        except OSError:
            pass
    if len(lines) < 2 or lines[0] != doorbell.ARMED_PREFIX + doorbell.ARMED_VERSION:
        return None
    parts = lines[1].split()
    if len(parts) != 2 or parts[0] not in doorbell.ROLES or not parts[1].isdigit():
        return None
    return parts[0], int(parts[1])
