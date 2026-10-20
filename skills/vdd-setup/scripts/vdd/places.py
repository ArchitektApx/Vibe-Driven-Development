"""Where things are: the user's home, the Shared directory, this copy of the
tool, and the command form that runs it."""

from __future__ import annotations

import os


def is_windows() -> bool:
    return os.name == "nt"


def home() -> str:
    """The home the Harnesses read their stores under: HOME on macOS and
    Linux, USERPROFILE on native Windows."""
    return os.path.expanduser("~")


def shared_dir() -> str:
    """vdd/ under XDG_DATA_HOME, or ~/.local/share when that is unset, on
    macOS and Linux; %LOCALAPPDATA%\\vdd on native Windows."""
    if is_windows():
        base = os.environ.get("LOCALAPPDATA") or os.path.join(home(), "AppData", "Local")
        return os.path.join(base, "vdd")
    xdg = os.environ.get("XDG_DATA_HOME", "")
    if xdg and os.path.isabs(xdg):
        return os.path.join(xdg, "vdd")
    return os.path.join(home(), ".local", "share", "vdd")


def package_dir() -> str:
    """The vdd/ package directory of the running copy."""
    return os.path.dirname(os.path.abspath(__file__))


def running_entry() -> str:
    """The vdd.py of the running copy."""
    return os.path.join(os.path.dirname(package_dir()), "vdd.py")


def shared_entry() -> str:
    return os.path.join(shared_dir(), "vdd.py")


def command(entry: str | None = None) -> str:
    """The command that runs the tool at entry, the running copy by default:
    python3 on macOS and Linux, py -3 on native Windows."""
    path = entry or running_entry()
    if is_windows():
        return 'py -3 "%s"' % path
    return 'python3 "%s"' % path
