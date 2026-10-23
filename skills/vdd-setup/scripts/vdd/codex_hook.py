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

Before the claim every failure stays silent, so an unrelated turn end is never
blocked. After it the armed file is gone and no later turn end would wait, so
a failed wait blocks once, its reason the failure and the hand-relay step;
a malformed armed file names no Role to word that step for and stays silent.

It exits 0 on every path, exceptions included: Codex reads exit 2 as a block
and repeats it without limit. Everything it needs is imported here, at start:
the hook runs the plugin's own copy, never the Shared one, and Codex deletes
an old version's directory under a running Session (ADR 0008), so a module
imported mid-wait could be gone.
"""

from __future__ import annotations

import json
import os
import sys

from . import armed, doorbells, loopfile, places, textfile
from .harness import codex as codex_harness
from .out import Failure, Output


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
    found = armed.files(loopfile.scratch(cwd), session)
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
    claimed = armed.claim(path, session, doorbells.ROLES)
    if claimed is None:
        return
    role, count = claimed
    entry = places.shared_entry()
    harness = codex_harness.HARNESS
    try:
        outcome = doorbells.wait_for(doorbells.Place(cwd, slug), role, harness, entry, floor=count)
    except Failure as failure:
        block("%s Next: %s" % (" ".join(failure.lines), doorbells.hand_relay(role, harness, slug, entry)))
        return
    except Exception as error:  # noqa: B902 - the armed file is gone, so say so once
        block("The wait stopped on an error: %s. Next: %s" % (
            textfile.reason(error).rstrip("."), doorbells.hand_relay(role, harness, slug, entry)))
        return
    if isinstance(outcome, doorbells.Found):
        block("A Doorbell for the %s is waiting. Next: run %s" % (role, outcome.take))
    else:
        block("TIMEOUT. Next: " + outcome.next_step)


def block(reason: str) -> None:
    """Print Codex's block decision: Codex continues the Session with the
    reason as its prompt."""
    reason = "".join(c for c in reason if ord(c) >= 32 and ord(c) != 127)
    text = json.dumps({"decision": "block", "reason": reason}, ensure_ascii=True)
    sys.stdout.buffer.write((text + "\n").encode("ascii"))
    sys.stdout.buffer.flush()
