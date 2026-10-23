"""The kinds of effect a plan holds, and the effects closing and reopening a
loop and recording a round are made of."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable, Optional, Sequence

from .. import armed, loopstate, textfile
from ..loopstate import recap
from ..out import Failure
from .plan import AFTER, BEFORE, RECAP, RECORDS, STATE, Effect

if TYPE_CHECKING:
    from ..loopstate.records import Record, Records

# Words the refusal of a write that failed: the OSError -> the Failure.
Refusal = Optional[Callable[[OSError], Failure]]


class WriteFile(Effect):
    """A file with its new text, its directory made first. what and
    otherwise word the refusal, as textfile.write_refusal takes them. after
    puts it after the commit point."""

    def __init__(
        self, path: str, text: str, what: str, otherwise: str, dry: Sequence[str] = (), done: Sequence[str] = (),
        after: bool = False,
    ) -> None:
        Effect.__init__(self, dry, done)
        self.phase = AFTER if after else BEFORE
        self.path = path
        self.text = text
        self.what = what
        self.otherwise = otherwise

    def apply(self) -> list[str]:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            textfile.write_text(self.path, self.text)
        except OSError as error:
            raise textfile.write_refusal(self.what, error, self.otherwise)
        return list(self.done)


class StateLines(Effect):
    """Lines appended to the loop's state file. The runner appends the
    lines of every StateLines in a plan in one write, the commit point;
    refuse, of the first one that has it, words its refusal."""

    phase = STATE

    def __init__(
        self, state: loopstate.State, lines: Sequence[str], dry: Sequence[str] = (), done: Sequence[str] = (),
        refuse: Refusal = None,
    ) -> None:
        Effect.__init__(self, dry, done)
        self.state = state
        self.lines = list(lines)
        self.refuse = refuse


class SaveRecords(Effect):
    """The Recap's records, each put under its key, saved in one write."""

    phase = RECORDS

    def __init__(self, store: Records, records: Sequence[Record], dry: Sequence[str] = (),
                 done: Sequence[str] = ()) -> None:
        Effect.__init__(self, dry, done)
        self.store = store
        self.records = list(records)

    def apply(self) -> list[str]:
        for record in self.records:
            self.store.put(record)
        self.store.save()
        return list(self.done)


class RenderRecap(Effect):
    """RECAP.md rendered from the state and store when its text changed.
    done prints when it wrote, unchanged when the file already held it
    (done again when not given)."""

    phase = RECAP

    def __init__(
        self, store: Records, state: loopstate.State, dry: Sequence[str] = (), done: Sequence[str] = (),
        unchanged: Sequence[str] | None = None,
    ) -> None:
        Effect.__init__(self, dry, done)
        self.store = store
        self.state = state
        self.unchanged = list(done if unchanged is None else unchanged)

    def apply(self) -> list[str]:
        wrote = recap.render_recap(self.store.loop, self.state, self.store)
        return list(self.done if wrote else self.unchanged)


class DeleteArmed(Effect):
    """The loop's Codex armed files and claim markers deleted, after the
    commit point: a done line names each armed file deleted."""

    phase = AFTER

    def __init__(self, directory: str) -> None:
        Effect.__init__(self)
        self.directory = directory

    def apply(self) -> list[str]:
        return ["Deleted the Codex armed file %s." % name for name in armed.delete(self.directory)]


class Step(Effect):
    """A compound effect its module owns, such as moving a branch: run()
    makes the change and returns its done lines, or raises the Failure it
    words, or Instead. after puts it after the commit point."""

    def __init__(self, run: Callable[[], list[str]], dry: Sequence[str] = (), after: bool = False,
                 keep: bool = False) -> None:
        Effect.__init__(self, dry, (), keep)
        self.phase = AFTER if after else BEFORE
        self.run = run

    def apply(self) -> list[str]:
        return self.run()


# --- the loop's open and closed lines, and the record step ---

def close(state: loopstate.State, dry: Sequence[str] = (), done: Sequence[str] = (),
          refuse: Refusal = None) -> list[Effect]:
    """Closing the loop: "loop closed" appended, then its Codex armed files
    deleted. done prints after the deleted files' lines."""
    return [DeleteArmed(state.dir), StateLines(state, [loopstate.loop_line(loopstate.CLOSED)], dry, done, refuse)]


def reopen(state: loopstate.State, dry: Sequence[str] = (), done: Sequence[str] = (),
           refuse: Refusal = None) -> StateLines:
    """Reopening the loop: "loop open", in the same write as the plan's
    other state lines and after them."""
    return StateLines(state, [loopstate.loop_line(loopstate.OPEN)], dry, done, refuse)


def closed_line(slug: str) -> str:
    """The line loop close and pr open print once a loop is closed."""
    return "Closed: the loop %s. Its files stay in .scratch/%s/ as the record." % (slug, slug)


def record_step(
    store: Records, state: loopstate.State, records: Sequence[Record], lines: Sequence[str], reopen_loop: bool = False,
    dry: Sequence[str] = (), done: Sequence[str] = (),
) -> list[Effect]:
    """A round recorded: the records saved, the state lines appended in one
    write, with "loop open" after them on reopen_loop, then RECAP.md
    rendered. store is the records the command loaded before its dry run,
    so a records file it cannot read refuses the dry run too."""
    effects: list[Effect] = [SaveRecords(store, records, dry, done), StateLines(state, lines)]
    if reopen_loop:
        effects.append(reopen(state))
    effects.append(RenderRecap(store, state))
    return effects
