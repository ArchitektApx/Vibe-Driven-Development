"""The Shared copy of the VDD tool: vdd.py and vdd/ in the Shared directory.

Setup compares the shipped tree with the Shared copy and, on a difference,
copies the shipped tree into a sibling directory and swaps it in. Every other
file in the Shared directory stays.
"""

import os
import shutil

from . import places, textfile

CURRENT = "current"
INSTALL = "install"
UPDATE = "update"


def tree(entry_dir):
    """relative path -> bytes for vdd.py and every file under vdd/, bytecode
    excluded. Paths use / on every OS."""
    files = {}
    entry = os.path.join(entry_dir, "vdd.py")
    if os.path.isfile(entry):
        files["vdd.py"] = textfile.read_bytes(entry)
    package = os.path.join(entry_dir, "vdd")
    for directory, dirs, names in os.walk(package):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(names):
            if name.endswith((".pyc", ".pyo")):
                continue
            path = os.path.join(directory, name)
            rel = os.path.relpath(path, entry_dir).replace(os.sep, "/")
            files[rel] = textfile.read_bytes(path)
    return files


def shipped_dir():
    return os.path.dirname(places.package_dir())


def state(shared):
    ours = tree(shipped_dir())
    theirs = tree(shared)
    if ours == theirs:
        return CURRENT
    if not theirs:
        return INSTALL
    return UPDATE


def unique_dir(parent, prefix):
    """A new, empty directory under parent with a unique name that starts
    with prefix, made with a plain os.mkdir so it inherits parent's ACL. On
    Windows the tempfile module's directory gets a protected ACL that the
    files copied into it keep, and Codex's sandbox cannot read them."""
    while True:
        path = os.path.join(parent, "%s%d-%s" % (prefix, os.getpid(), os.urandom(4).hex()))
        try:
            os.mkdir(path)
            return path
        except FileExistsError:
            continue


def swap(shared):
    """Copy the shipped tree into a sibling directory of the Shared copy, then
    swap it in. Raises OSError when a write fails."""
    source = shipped_dir()
    os.makedirs(shared, exist_ok=True)
    stage = unique_dir(shared, ".vdd-new-")
    old = None
    try:
        for rel in tree(source):
            dest = os.path.join(stage, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(os.path.join(source, *rel.split("/")), dest)
        package = os.path.join(shared, "vdd")
        if os.path.lexists(package):
            old = unique_dir(shared, ".vdd-old-")
            os.rmdir(old)
            os.rename(package, old)
        try:
            os.rename(os.path.join(stage, "vdd"), package)
        except OSError:
            if old:
                os.rename(old, package)
                old = None
            raise
        os.replace(os.path.join(stage, "vdd.py"), os.path.join(shared, "vdd.py"))
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        if old:
            shutil.rmtree(old, ignore_errors=True)
