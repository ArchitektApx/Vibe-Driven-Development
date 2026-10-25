"""VDD's 0.15 Stop entry in ~/.codex/hooks.json, and the edit that removes it.

The hook ships inline in .codex-plugin/plugin.json, so Setup registers
nothing. It removes only the handler an older VDD wrote, matched by its exact
command with any directory and its timeout, and leaves every other key, group
and handler in place and order, an emptied Stop list included.
"""

from __future__ import annotations

import difflib
import json
import re
from typing import Any

from ... import textfile

TIMEOUT = 2760
OLD_SH = re.compile(r'^sh "[^"]*/vdd-codex-stop\.sh" \|\| true$')
OLD_PS = re.compile(
    r"^\$f='(?:[^']|'')*\\vdd-codex-stop\.ps1';if\(Test-Path -LiteralPath \$f\)"
    r"\{powershell\.exe -NoProfile -ExecutionPolicy Bypass -File \$f\}$"
)


def is_old_vdd(handler: Any) -> bool:
    """A handler a released VDD wrote: one of the two 0.15 command templates
    with any directory, timeout 2760, and no other command form."""
    if not isinstance(handler, dict) or handler.get("timeout") != TIMEOUT:
        return False
    command = handler.get("command")
    if not isinstance(command, str):
        return False
    windows = handler.get("commandWindows", handler.get("command_windows"))
    if OLD_SH.match(command):
        return windows is None
    if OLD_PS.match(command):
        return windows is None or (isinstance(windows, str) and OLD_PS.match(windows) is not None)
    return False


def names_vdd(handler: Any) -> bool:
    if not isinstance(handler, dict):
        return False
    return any(
        isinstance(value, str) and "vdd-codex-stop" in value
        for value in (handler.get(k) for k in ("command", "commandWindows", "command_windows"))
    )


class Migration:
    """The planned edit of hooks.json."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.raw: bytes | None = None
        self.before = ""  # the file's text, once read
        self.after = ""  # the file's planned text, once a removal is planned
        self.error: str | None = None
        self.removed = 0
        self.shifted = False
        self.others: list[tuple[str, Any]] = []  # handlers naming vdd-codex-stop that stay
        self.plan()

    def plan(self) -> None:
        try:
            raw = textfile.read_bytes(self.path)
        except FileNotFoundError:
            return
        except OSError as error:
            self.error = "it could not be read (%s)" % textfile.reason(error)
            return
        self.raw = raw
        self.before = textfile.decode(raw)
        try:
            data = json.loads(self.before)
        except ValueError as error:
            self.error = "it does not parse as JSON (%s)" % error
            return
        hooks = data.get("hooks") if isinstance(data, dict) else None
        if not isinstance(hooks, dict):
            return
        for event, groups in hooks.items():
            if not isinstance(groups, list):
                continue
            kept_groups = []
            removed_here = False
            for group in groups:
                handlers = group.get("hooks") if isinstance(group, dict) else None
                if not isinstance(handlers, list):
                    if removed_here:
                        self.shifted = True
                    kept_groups.append(group)
                    continue
                kept = []
                for handler in handlers:
                    if event == "Stop" and is_old_vdd(handler):
                        self.removed += 1
                        removed_here = True
                        continue
                    if names_vdd(handler):
                        self.others.append((event, handler.get("command") or handler.get("commandWindows")))
                    if removed_here:
                        self.shifted = True
                    kept.append(handler)
                if kept or len(kept) == len(handlers):
                    group = dict(group)
                    group["hooks"] = kept
                    kept_groups.append(group)
            hooks[event] = kept_groups
        if not self.removed:
            return
        self.after = layout(data)

    def relaid(self) -> bool:
        """Whether the file's bytes differ from the two-space, LF, BOM-less
        UTF-8 Setup writes, so the write changes more bytes than the diff
        shows."""
        return layout(json.loads(self.before)).encode("utf-8") != self.raw

    def diff(self, label: str) -> list[str]:
        """VDD's removal alone: the file as it parses, in the layout Setup
        writes, against the result."""
        return list(
            difflib.unified_diff(
                layout(json.loads(self.before)).splitlines(),
                self.after.splitlines(),
                fromfile=label,
                tofile=label,
                lineterm="",
            )
        )


def layout(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
