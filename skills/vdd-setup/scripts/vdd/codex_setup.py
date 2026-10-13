"""Setup's Codex steps: remove VDD's 0.15 Stop entry from ~/.codex/hooks.json,
and check whether the user trusted the hook the plugin now ships.

The hook ships inline in .codex-plugin/plugin.json, so Setup registers
nothing. It removes only the handler an older VDD wrote, matched by its exact
command with any directory and its timeout, and leaves every other key, group
and handler in place and order, an emptied Stop list included.
"""

import difflib
import json
import os
import re

from . import places, stores, textfile

TIMEOUT = 2760
OLD_SH = re.compile(r'^sh "[^"]*/vdd-codex-stop\.sh" \|\| true$')
OLD_PS = re.compile(
    r"^\$f='(?:[^']|'')*\\vdd-codex-stop\.ps1';if\(Test-Path -LiteralPath \$f\)"
    r"\{powershell\.exe -NoProfile -ExecutionPolicy Bypass -File \$f\}$"
)
TRUST_KEY = re.compile(r"^vdd@[^:]+:plugin\.json#hooks\[0\]:stop:0:0$")


def codex_home():
    return os.environ.get("CODEX_HOME") or os.path.join(places.home(), ".codex")


def is_old_vdd(handler):
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


def names_vdd(handler):
    if not isinstance(handler, dict):
        return False
    return any(
        isinstance(handler.get(k), str) and "vdd-codex-stop" in handler.get(k)
        for k in ("command", "commandWindows", "command_windows")
    )


class Migration:
    """The planned edit of hooks.json."""

    def __init__(self, path):
        self.path = path
        self.raw = None
        self.before = None
        self.after = None
        self.error = None
        self.removed = 0
        self.shifted = False
        self.others = []  # handlers naming vdd-codex-stop that stay
        self.plan()

    def plan(self):
        try:
            with open(self.path, "rb") as handle:
                raw = handle.read()
        except FileNotFoundError:
            return
        except OSError as error:
            self.error = str(error)
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

    def relaid(self):
        """Whether the file's bytes differ from the two-space, LF, BOM-less
        UTF-8 Setup writes, so the write changes more bytes than the diff
        shows."""
        return layout(json.loads(self.before)).encode("utf-8") != self.raw

    def diff(self, label):
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


def layout(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def trust_state(path):
    """present, absent or unknown: whether ~/.codex/config.toml holds the
    hooks.state key of VDD's hook. A narrow standard-library read of TOML
    table headers and dotted keys; anything it cannot follow is unknown."""
    try:
        with open(path, "rb") as handle:
            text = textfile.decode(handle.read())
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unknown"
    table = []
    pending = None  # an open multi-line string or array
    for line in text.split("\n"):
        if pending:
            pending = continue_value(line, pending)
            if pending == "bad":
                return "unknown"
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            inner = stripped[2:] if stripped.startswith("[[") else stripped[1:]
            path, rest = parse_key(inner)
            if path is None:
                return "unknown"
            close = "]]" if stripped.startswith("[[") else "]"
            if not rest.strip().startswith(close):
                return "unknown"
            table = path
            if has_key(table):
                return "present"
            continue
        path, rest = parse_key(stripped)
        if path is None or not rest.lstrip().startswith("="):
            return "unknown"
        if has_key(table + path):
            return "present"
        value = rest.lstrip()[1:].strip()
        pending = open_value(value)
        if pending == "bad":
            return "unknown"
        if value.startswith("{") and table + path in (["hooks"], ["hooks", "state"]):
            for key in re.findall(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'', value):
                if TRUST_KEY.match(key[0] or key[1]):
                    return "present"
    if pending:
        return "unknown"
    return "absent"


def has_key(path):
    return len(path) >= 3 and path[0] == "hooks" and path[1] == "state" and TRUST_KEY.match(path[2]) is not None


def parse_key(text):
    """A dotted TOML key at the start of text: (segments, the rest), or
    (None, text) when it is not one."""
    segments = []
    i = 0
    n = len(text)
    while True:
        while i < n and text[i] in " \t":
            i += 1
        if i < n and text[i] == '"':
            j = i + 1
            value = []
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


def open_value(value):
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


def continue_value(line, pending):
    if pending in ('"""', "'''"):
        return None if pending in line else pending
    depth = pending[1] + bracket_depth(line)
    if depth < 0:
        return "bad"
    return ("[", depth) if depth else None


def bracket_depth(text):
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


def run(setup):
    """Setup's Codex steps, reporting into setup.out and setup.changes."""
    out = setup.out
    home = codex_home()
    hooks_path = os.path.join(home, "hooks.json")
    label = stores.display(hooks_path, setup.cwd)
    migration = Migration(hooks_path)
    if migration.error:
        out.line("%s: left untouched, %s." % (label, migration.error))
        out.tell(
            "Setup left %s untouched because %s. If it holds VDD's old Stop hook entry, remove that "
            "entry by hand." % (label, migration.error)
        )
    elif not migration.removed:
        out.line("%s: no Stop entry from an older VDD. Passed." % label)
    else:
        verb = "Changed" if setup.write else "Planned change"
        setup.changes.append("hooks.json")
        out.line("%s: %s removes VDD's old Stop hook entry; the hook now ships with the plugin." % (verb, label))
        if not setup.write:
            for line in migration.diff(label):
                out.line(line)
            if migration.relaid():
                out.line("%s is rewritten in two-space JSON layout with LF line ends and no byte-order mark; "
                    "the diff shows only VDD's removal." % label)
        if migration.shifted:
            out.tell(
                "Codex will list your own Stop hooks under 'Hooks need review' once at its next start, "
                "because removing VDD's old entry moved them: trust them again there."
            )
        if setup.write:
            try:
                textfile.write(hooks_path, migration.after.encode("utf-8"))
                json.loads(textfile.read(hooks_path))
                out.line("%s: checked, it parses." % label)
            except (OSError, ValueError) as error:
                setup.failed.append("hooks.json")
                out.line("Not changed: %s (%s)." % (label, error))
    for event, command in migration.others:
        out.line("%s: a %s hook naming vdd-codex-stop that Setup did not write stays: %s" % (label, event, command))
    config = os.path.join(home, "config.toml")
    config_label = stores.display(config, setup.cwd)
    text = textfile.read(config) or ""
    if "vdd-codex-stop" in text:
        out.line("%s: a registration naming vdd-codex-stop stays; Setup does not edit this file." % config_label)
    state = trust_state(config)
    if state == "present":
        out.line("VDD's Codex hook: a trust entry is in %s." % config_label)
    elif state == "absent":
        out.tell("Trust VDD's hook in /hooks.")
    else:
        out.line("VDD's Codex hook: whether it is trusted is unknown, %s could not be read." % config_label)
        out.tell(
            "Setup could not tell whether VDD's hook is trusted. Open /hooks and trust VDD's hook if it "
            "is listed for review."
        )
