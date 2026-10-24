"""The runner: one command's plan printed as its dry run, or applied
through the record step with its done lines printed."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Sequence

from .. import textfile
from ..out import Failure, Output
from .effects import StateLines
from .plan import PHASES, STATE, Effect, Instead, Plan
from .preconditions import Ask

if TYPE_CHECKING:
    from ..catalog import Context


def run(ctx: Context, build: Callable[[], Plan]) -> int:
    """Run the command whose precondition and plan build() checks and
    returns. Without --write it prints each effect's dry lines and the
    plan's dry Next:; with --write, or for an always plan, it applies the
    effects and prints their done lines and the plan's Next:. A refusal
    refuses both alike; an Ask prints its question, exiting 1 on --write."""
    write = bool(ctx.values.get("write"))
    out = Output()
    try:
        plan = build()
    except Ask as ask:
        for line in ask.lines:
            out.line(line)
        return out.finish(ask.next_step, 1 if write else 0)
    if not plan.effects:
        lines, next_step = plan.lines, plan.next_line()
    elif not (write or plan.always):
        lines = plan.lines + [line for effect in plan.effects for line in effect.dry]
        next_step = plan.dry_next
    else:
        if write:
            ctx.require(*plan.requires)
        lines = list(plan.lines)
        while True:
            try:
                lines += apply(plan.effects)
                break
            except Instead as instead:
                lines += instead.kept
                plan = instead.plan
        next_step = plan.next_line()
    for line in lines:
        out.line(line)
    return out.finish(next_step, plan.exit_code())


def apply(effects: Sequence[Effect]) -> list[str]:
    """Apply effects in the record step's order: the records, the effects
    before the commit point, the state lines in one write, RECAP.md, the
    effects after it. Their done lines, in plan order. A failure raised
    by an effect prints after the done lines of the applied effects that
    keep theirs."""
    done: dict[int, list[str]] = {}

    def kept() -> list[str]:
        return [line for index, effect in enumerate(effects) if effect.keep and index in done
                for line in done[index]]

    try:
        for phase in PHASES:
            if phase == STATE:
                commit([(index, effect) for index, effect in enumerate(effects) if isinstance(effect, StateLines)],
                       done)
                continue
            for index, effect in enumerate(effects):
                if effect.phase == phase:
                    done[index] = effect.apply()
    except Instead as instead:
        instead.kept = kept()
        raise
    except Failure as failure:
        failure.lines = kept() + failure.lines
        raise
    return [line for index in range(len(effects)) for line in done.get(index, [])]


def commit(found: list[tuple[int, StateLines]], done: dict[int, list[str]]) -> None:
    """Append every StateLines' lines in one write: the commit point."""
    if not found:
        return
    state = found[0][1].state
    lines = [line for _, effect in found for line in effect.lines]
    try:
        if lines:
            state.add(*lines)
    except OSError as error:
        refuse = next((effect.refuse for _, effect in found if effect.refuse is not None), None)
        if refuse is not None:
            raise refuse(error)
        raise textfile.write_refusal("the loop state file %s" % textfile.shown(state.path), error,
                                     "Otherwise tell the user the loop state file cannot be written, and stop.")
    for index, effect in found:
        done[index] = list(effect.done)
