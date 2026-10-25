"""One builder per state-line kind: no caller formats a state line. The
Orchestrator's parsers of its ledger lines live in its group (flow), and
state reads the round lines."""

from __future__ import annotations

from typing import Iterable, Literal, Sequence

STATE_PREFIX = "vdd loop-state "
STATE_VERSION = "2"


def header_line() -> str:
    return STATE_PREFIX + STATE_VERSION


def loop_line(status: str) -> str:
    """"loop open" or "loop closed"."""
    return "loop %s" % status


def review_started_line(kind: str, round_number: int) -> str:
    return "%s %d review-started" % (kind, round_number)


def reviewed_line(
    kind: str, round_number: int, signed_off: bool, open_numbers: Iterable[int], counts: Sequence[int],
    next_number: int, new: int, closed: int, checks: str,
) -> str:
    numbers = ",".join(str(n) for n in open_numbers) or "-"
    return "%s %d reviewed %s %s counts %d %d %d next %d new %d closed %d checks %s" % (
        kind, round_number, "signed-off" if signed_off else "open", numbers, counts[0], counts[1], counts[2],
        next_number, new, closed, checks)


def user_line(
    round_number: int, open_numbers: Iterable[int], counts: Sequence[int], next_number: int, new: int,
) -> str:
    numbers = ",".join(str(n) for n in open_numbers)
    return "code %d user open %s counts %d %d %d next %d new %d" % (
        round_number, numbers, counts[0], counts[1], counts[2], next_number, new)


def code_mark_line(which: Literal["start", "end"], round_number: int, sha: str) -> str:
    """"code <r> start <sha>" or "code <r> end <sha>"."""
    return "code %d %s %s" % (round_number, which, sha)


def respawn_line(role: str, policy: str) -> str:
    return "respawn %s %s" % (role, policy)


def respawn_once_line(role: str) -> str:
    return "respawn-once %s" % role


def session_line(number: int) -> str:
    return "orchestrator session %d" % number


def spawn_line(role: str, round_number: int, session: int, reason: str | None = None) -> str:
    return "spawn %s %d session %d%s" % (role, round_number, session, " reason " + reason if reason else "")


def resume_line(role: str, round_number: int, session: int) -> str:
    return "resume %s %d session %d" % (role, round_number, session)


def return_line(role: str, round_number: int, ok: bool) -> str:
    return "return %s %d %s" % (role, round_number, "ok" if ok else "miss")


def tokens_line(role: str, round_number: int, count: int) -> str:
    return "tokens %s %d %d" % (role, round_number, count)


def folded_line(tip: str, signed: str) -> str:
    return "fold folded %s signed %s" % (tip, signed)


def skipped_line(signed: str, reason: str) -> str:
    return "fold skipped %s %s" % (signed, " ".join(reason.split()))
