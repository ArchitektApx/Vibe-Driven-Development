"""Whether the user trusted VDD's Codex hook: a narrow standard-library read
of ~/.codex/config.toml for the hooks.state key of the hook the plugin ships.

Setup reads the file once with read() and hands its text to state(), so a
file it could not read and a file it read but could not follow are told
apart.
"""

from __future__ import annotations

import re

from ... import textfile

TRUST_KEY = re.compile(r"^vdd@[^:]+:plugin\.json#hooks\[0\]:stop:0:0$")
DISABLED = re.compile(r"\benabled\s*=\s*false\b")

PRESENT = "present"
DISABLED_STATE = "disabled"
ABSENT = "absent"
NOT_UNDERSTOOD = "not understood"
UNREADABLE = "unreadable"


def read(path: str) -> str | None:
    """config.toml's text, "" when there is no such file, or None when it
    could not be read."""
    try:
        return textfile.decode(textfile.read_bytes(path))
    except (FileNotFoundError, NotADirectoryError):
        return ""
    except OSError:
        return None


def state(text: str | None) -> str:
    """PRESENT, DISABLED_STATE, ABSENT, NOT_UNDERSTOOD or UNREADABLE (text is
    None): whether config.toml holds the hooks.state key of VDD's hook, and
    whether that key says enabled = false (a hook switched off in /hooks
    keeps its key). A table header or dotted key the reader cannot follow is
    NOT_UNDERSTOOD."""
    if text is None:
        return UNREADABLE
    table: list[str] = []
    found = disabled = False
    pending: str | tuple[str, int] | None = None  # an open multi-line string or array
    for line in text.split("\n"):
        if pending:
            pending = continue_value(line, pending)
            if pending == "bad":
                return NOT_UNDERSTOOD
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            inner = stripped[2:] if stripped.startswith("[[") else stripped[1:]
            keys, rest = parse_key(inner)
            if keys is None:
                return NOT_UNDERSTOOD
            close = "]]" if stripped.startswith("[[") else "]"
            if not rest.strip().startswith(close):
                return NOT_UNDERSTOOD
            table = keys
            found = found or has_key(table)
            continue
        keys, rest = parse_key(stripped)
        if keys is None or not rest.lstrip().startswith("="):
            return NOT_UNDERSTOOD
        value = rest.lstrip()[1:].strip()
        full = table + keys
        pending = open_value(value)
        if pending == "bad":
            return NOT_UNDERSTOOD
        if has_key(full):
            found = True
            if full[3:] == ["enabled"] and value.startswith("false"):
                disabled = True
            elif len(full) == 3 and value.startswith("{") and DISABLED.search(value):
                disabled = True
        elif value.startswith("{") and full in (["hooks"], ["hooks", "state"]):
            for key in re.findall(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'', value):
                if TRUST_KEY.match(key[0] or key[1]):
                    found = True
    if pending:
        return NOT_UNDERSTOOD
    if disabled:
        return DISABLED_STATE
    return PRESENT if found else ABSENT


def has_key(path: list[str]) -> bool:
    return len(path) >= 3 and path[0] == "hooks" and path[1] == "state" and TRUST_KEY.match(path[2]) is not None


def parse_key(text: str) -> tuple[list[str] | None, str]:
    """A dotted TOML key at the start of text: (segments, the rest), or
    (None, text) when it is not one."""
    segments: list[str] = []
    i = 0
    n = len(text)
    while True:
        while i < n and text[i] in " \t":
            i += 1
        if i < n and text[i] == '"':
            j = i + 1
            value: list[str] = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    value.append(text[j + 1])
                    j += 2
                    continue
                value.append(text[j])
                j += 1
            if j >= n:
                return None, text
            segments.append("".join(value))
            i = j + 1
        elif i < n and text[i] == "'":
            j = text.find("'", i + 1)
            if j < 0:
                return None, text
            segments.append(text[i + 1:j])
            i = j + 1
        else:
            match = re.match(r"[A-Za-z0-9_-]+", text[i:])
            if not match:
                return None, text
            segments.append(match.group(0))
            i += match.end()
        while i < n and text[i] in " \t":
            i += 1
        if i < n and text[i] == ".":
            i += 1
            continue
        return segments, text[i:]


def open_value(value: str) -> str | tuple[str, int] | None:
    """None when the value ends on its line, or what it leaves open."""
    if value.startswith('"""') and value.count('"""') == 1:
        return '"""'
    if value.startswith("'''") and value.count("'''") == 1:
        return "'''"
    if value.startswith("["):
        depth = bracket_depth(value)
        if depth < 0:
            return "bad"
        return ("[", depth) if depth else None
    return None


def continue_value(line: str, pending: str | tuple[str, int]) -> str | tuple[str, int] | None:
    if isinstance(pending, str):
        return None if pending in line else pending
    depth = pending[1] + bracket_depth(line)
    if depth < 0:
        return "bad"
    return ("[", depth) if depth else None


def bracket_depth(text: str) -> int:
    depth = 0
    quote = None
    i = 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "#":
            break
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        i += 1
    return depth
