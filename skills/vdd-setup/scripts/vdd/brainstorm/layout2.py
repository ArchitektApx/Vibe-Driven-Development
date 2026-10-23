"""The migration step from layout 2 to layout 3: the dates move from the
ledger into the files.

Layout 2 kept .state/ledger.json, each idea file's hash as the tool last
wrote it. Under the store lock the step sets the modification time of every
idea whose text still matches its ledger entry to its last-updated day, at
noon local time, leaves a hand-edited idea's as it is, deletes the ledger and
writes .layout 3, in that order: a run killed after the delete reruns as a
layout 2 store without a ledger and only writes the marker. No idea's text
changes, so it needs no journal, and nothing from the user.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import List, Tuple

from .. import textfile
from ..out import TELL
from . import journal
from .ideafile import Idea, is_idea_name, real_date
from .lock import Lock
from .store import LAYOUT_FILE, read_once, set_file_day, state_dir, store_dir

FROM, TO = "2", "3"
NEEDS_USER = False
LEDGER = "ledger.json"
PLAN = "The dates move from the ledger into the files; no idea's text changes."
DONE = ("The idea store was updated to layout 3: each idea's date now comes from its file; no idea's text "
        "changed.")

Result = Tuple[List[str], str, List[str]]


def ledger_path(root: str) -> str:
    return os.path.join(state_dir(root), LEDGER)


def ledger_sha(data: bytes) -> str:
    """The ledger's hash of an idea file: of its text as read (UTF-8, LF, no
    byte order mark)."""
    return hashlib.sha256(textfile.decode(data).encode("utf-8")).hexdigest()


def read_ledger(root: str) -> dict[str, str]:
    try:
        data = json.loads(read_once(ledger_path(root)) or "{}")
    except ValueError:
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def plan_lines(root: str) -> list[str]:
    return [PLAN]


def run(root: str, events_raw: list[str], write: bool) -> Result:
    """The step's lines and what happened: "dry" or "updated"."""
    if not write:
        return plan_lines(root), "dry", [LAYOUT_FILE + " (3)"] + ([".state/" + LEDGER + " (removed)"]
                                                     if os.path.isfile(ledger_path(root)) else [])
    with Lock(root, on_take=journal.recover) as lock:
        ledger = read_ledger(root)
        base = store_dir(root)
        for name in sorted(os.listdir(base)):
            path = os.path.join(base, name)
            if not is_idea_name(name) or name[:-3] not in ledger or not os.path.isfile(path):
                continue
            data = textfile.read_bytes(path)
            day = Idea.read(name[:-3], path, data).get("last-updated")
            if ledger[name[:-3]] == ledger_sha(data) and real_date(day):
                set_file_day(path, day)
        if os.path.isfile(ledger_path(root)):
            os.remove(ledger_path(root))
        textfile.write(os.path.join(base, LAYOUT_FILE), (TO + "\n").encode("ascii"))
    return lock.lines + [TELL % DONE], "updated", []
