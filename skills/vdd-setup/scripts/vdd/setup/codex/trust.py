"""VDD's Codex hook entries in config.toml: a narrow standard-library read of
the hooks.state table of the hook the plugin ships, once per vdd@<marketplace>.

Setup reads the file once with read() and hands its text to entries(), so a
file it could not read and a file it read but could not follow are told
apart. Values are read only from the table form Codex's own writer produces;
VDD's entry written as an inline table or with dotted keys is not
understood.
"""

from __future__ import annotations

import re

from ... import textfile

TRUST_KEY = re.compile(r"vdd@([^:]+):plugin\.json#hooks\[0\]:stop:0:0")
HASHES = ("trusted_hash", "trusted_content_hash")

ESCAPES = {'"': '"', "\\": "\\", "b": "\b", "t": "\t", "n": "\n", "f": "\f", "r": "\r"}

NOT_UNDERSTOOD = "not understood"
UNREADABLE = "unreadable"


class Entry:
    """One vdd@<marketplace> table: the hashes Codex stored when the user
    trusted the hook, and enabled, False when it is switched off in /hooks."""

    def __init__(self, marketplace: str) -> None:
        self.marketplace = marketplace
        self.trusted_hash: str | None = None
        self.trusted_content_hash: str | None = None
        self.enabled: bool | None = None


def read(path: str) -> str | None:
    """config.toml's text, "" when there is no such file, or None when it
    could not be read."""
    try:
        return textfile.decode(textfile.read_bytes(path))
    except (FileNotFoundError, NotADirectoryError):
        return ""
    except OSError:
        return None


def entries(text: str | None) -> list[Entry] | str:
    """Every VDD hook entry in config.toml, in file order, or UNREADABLE (text
    is None) or NOT_UNDERSTOOD: a table header or key the reader cannot
    follow, or VDD's entry in a form other than its own table."""
    if text is None:
        return UNREADABLE
    found: list[Entry] = []
    current: Entry | None = None
    table: list[str] = []
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
            array = stripped.startswith("[[")
            keys, rest = parse_key(stripped[2:] if array else stripped[1:])
            if keys is None or not rest.strip().startswith("]]" if array else "]"):
                return NOT_UNDERSTOOD
            table = keys
            current = None
            if has_key(table):
                if array or len(table) > 3 or any(e.marketplace == marketplace(table) for e in found):
                    return NOT_UNDERSTOOD
                current = Entry(marketplace(table))
                found.append(current)
            continue
        keys, rest = parse_key(stripped)
        if keys is None or not rest.lstrip().startswith("="):
            return NOT_UNDERSTOOD
        value = rest.lstrip()[1:].strip()
        full = table + keys
        pending = open_value(value)
        if pending == "bad":
            return NOT_UNDERSTOOD
        if current is not None:
            if len(keys) > 1 or not field(current, keys[0], value):
                return NOT_UNDERSTOOD
        elif has_key(full) or (value.startswith("{") and full in (["hooks"], ["hooks", "state"])
                               and names_vdd(value)):
            return NOT_UNDERSTOOD
    if pending:
        return NOT_UNDERSTOOD
    return found


def marketplace(path: list[str]) -> str:
    match = TRUST_KEY.fullmatch(path[2])
    return match.group(1) if match else ""


def names_vdd(value: str) -> bool:
    """Whether an inline table holds a key of VDD's hook."""
    return any(TRUST_KEY.fullmatch(key[0] or key[1])
               for key in re.findall(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'', value))


def field(entry: Entry, name: str, value: str) -> bool:
    """Set the field name of entry from its value; False when the value is
    not the type Codex writes for it. A field Setup does not read is left."""
    if name in HASHES:
        text = string_value(value)
        if text is None:
            return False
        setattr(entry, name, text)
    elif name == "enabled":
        match = re.match(r"(true|false)\s*(#.*)?$", value)
        if not match:
            return False
        entry.enabled = match.group(1) == "true"
    return True


def string_value(value: str) -> str | None:
    """A one-line TOML basic or literal string and nothing after it but a
    comment, as its text; None for any other value."""
    if value.startswith("'") and not value.startswith("'''"):
        end = value.find("'", 1)
        text, rest = (value[1:end], value[end + 1:]) if end > 0 else (None, "")
    elif value.startswith('"') and not value.startswith('"""'):
        chars: list[str] = []
        i = 1
        text = None
        while i < len(value):
            c = value[i]
            if c == "\\":
                escaped = ESCAPES.get(value[i + 1:i + 2])
                if escaped is None:
                    return None
                chars.append(escaped)
                i += 2
                continue
            if c == '"':
                text = "".join(chars)
                break
            chars.append(c)
            i += 1
        rest = value[i + 1:]
    else:
        return None
    if text is None or not re.match(r"\s*(#.*)?$", rest):
        return None
    return text



def has_key(path: list[str]) -> bool:
    return len(path) >= 3 and path[0] == "hooks" and path[1] == "state" and TRUST_KEY.fullmatch(path[2]) is not None


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
