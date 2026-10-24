"""A plan: the effects a write command would apply, each with the lines its
group words for it, and the Next: steps around them.

An effect belongs to one phase of the record step, and the runner applies
the phases in this order: the Recap's records, the effects before the commit
point, the state lines in one write (the commit point), RECAP.md rendered
from the records, the effects after the commit point. Within a phase the
effects apply in plan order, and every effect's lines print in plan order.
"""

from __future__ import annotations

from typing import Callable, Sequence, Union

RECORDS = "records"
BEFORE = "before"
STATE = "state"
RECAP = "recap"
AFTER = "after"
PHASES = (RECORDS, BEFORE, STATE, RECAP, AFTER)

WRITE_NEXT = "Run the same command with --write."

# A Next: step, or a function that words it from what the effects wrote.
Next = Union[str, Callable[[], str]]


class Effect:
    """One change: dry, the lines a dry run prints for it; done, the lines
    --write prints once it applied. With keep, its done lines also print
    before the lines of a failure in a later effect."""

    phase = BEFORE

    def __init__(self, dry: Sequence[str] = (), done: Sequence[str] = (), keep: bool = False) -> None:
        self.dry = list(dry)
        self.done = list(done)
        self.keep = keep

    def apply(self) -> list[str]:
        """Make the change; its done lines. Raises a Failure the effect
        words, or Instead."""
        return list(self.done)


class Plan:
    """What a command does: its effects; next, the Next: step once they
    applied, or a function the runner calls for it then, when the step
    reads what the effects wrote; dry_next, the dry run's. A plan that writes nothing has no
    effects and prints lines, what the command found, and next, with or
    without --write. requires names the options a --write needs that a dry
    run asks the user for. An always plan applies without --write. code is
    the exit code, or a function the runner calls for it once the effects
    applied or printed, when a write that did not land fails the command."""

    def __init__(
        self,
        effects: Sequence[Effect],
        next_step: Next,
        dry_next: str = WRITE_NEXT,
        lines: Sequence[str] = (),
        requires: Sequence[str] = (),
        always: bool = False,
        code: Union[int, Callable[[], int]] = 0,
    ) -> None:
        self.effects = list(effects)
        self.next = next_step
        self.dry_next = dry_next
        self.lines = list(lines)
        self.requires = tuple(requires)
        self.always = always
        self.code = code

    def next_line(self) -> str:
        """The Next: step once the effects applied."""
        return self.next if isinstance(self.next, str) else self.next()

    def exit_code(self) -> int:
        return self.code if isinstance(self.code, int) else self.code()


class Instead(Exception):
    """Raised by an effect that could not apply and leaves the command to
    another plan: the runner applies plan from its first phase in place of
    the effects not yet applied. kept is the done lines to print first."""

    def __init__(self, plan: Plan) -> None:
        Exception.__init__(self, "instead")
        self.plan = plan
        self.kept: list[str] = []
