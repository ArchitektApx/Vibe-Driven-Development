"""Static checks on the `.py` files this plugin ships.

Run from the repository root, or with the repository as the one argument. It
reads the tracked files from `git ls-files`, so gitignored scratch files never
count. The repository's other Invariants are check_repository.py's. The
shipped code is checked against Python 3.9.

Prints one line per problem and exits 1 when there is any, 0 otherwise.
"""

import ast
import os
import subprocess
import sys

# Every module the shipped code may import, any submodule included: the
# standard library modules it imports today and its own package. A new import
# is a visible edit here, in the same PR as the code that needs it.
ALLOWED_MODULES = {
    "__future__", "abc", "base64", "binascii", "datetime", "difflib", "errno",
    "fcntl", "glob", "hashlib", "json", "msvcrt", "os", "posixpath", "re",
    "shutil", "signal", "subprocess", "sys", "textwrap", "time", "types",
    "typing",
    "vdd",
}

# Modules allowed in the named files alone: subprocess runs a program, so it
# lives in the git module. A submodule counts as its top-level module unless a
# restriction names the submodule.
RESTRICTED_MODULES = {
    "subprocess": ("skills/vdd-setup/scripts/vdd/gitcmd.py",),
}

# Modules that open a network connection, or serve or fetch over one, and
# the C modules under socket and ssl.
NETWORK_MODULES = {
    "_socket", "_ssl", "asyncio", "ftplib", "http", "imaplib", "nntplib",
    "poplib", "smtpd", "smtplib", "socket", "socketserver", "ssl", "telnetlib",
    "urllib", "webbrowser", "wsgiref", "xmlrpc",
}

# Modules refused outright, any submodule included: importlib and runpy load
# or run code by a computed name or path, and posix and nt hold system and
# popen under the names os re-exports.
REFUSED_MODULES = {
    "importlib": "importlib imports by a computed name",
    "runpy": "runpy runs a module or a file by a computed name",
    "posix": "posix holds system and popen, which run a shell",
    "nt": "nt holds system and popen, which run a shell",
}

# What runs a shell, evaluates text or imports by a computed name, by its
# qualified name, however the file reaches it: called, referenced, imported
# by name, or under an alias.
BANNED = {
    "os.system": "os.system runs a shell",
    "os.popen": "os.popen runs a shell",
    "subprocess.getoutput": "subprocess.getoutput runs a shell",
    "subprocess.getstatusoutput": "subprocess.getstatusoutput runs a shell",
    "builtins.eval": "eval()",
    "builtins.exec": "exec()",
    "builtins.__import__": "__import__ imports by a computed name",
}
BANNED_NAMES = {
    "eval": "eval()",
    "exec": "exec()",
    "__import__": "__import__ imports by a computed name",
    "__builtins__": "__builtins__ reaches eval, exec and __import__ by name",
}
# Modules whose attributes getattr() or a star import could reach a banned
# name through.
GUARDED_MODULES = {"os", "subprocess", "builtins"}

ALLOWED_BYTES = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D}


def tracked(repo):
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=repo, check=True, capture_output=True
    ).stdout
    for entry in out.split(b"\0"):
        if entry:
            yield entry.decode("utf-8", "surrogateescape")


def bound_names(tree):
    """Each name an absolute import binds, mapped to what it names: `import
    os as o` binds o to os, `from subprocess import run` binds run to
    subprocess.run."""
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    names[alias.asname] = alias.name
                else:
                    top = alias.name.split(".")[0]
                    names[top] = top
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            for alias in node.names:
                if alias.name != "*":
                    names[alias.asname or alias.name] = node.module + "." + alias.name
    # A plain assignment of a guarded module or a banned attribute binds its
    # target the same way: `o = os` binds o to os, `x = os.system` binds x to
    # os.system. Repeated until nothing changes, so `p = o` follows `o = os`.
    assignments = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            assignments.append((targets, node.value))
        elif isinstance(node, ast.AnnAssign) and node.value is not None and isinstance(node.target, ast.Name):
            assignments.append(([node.target.id], node.value))
    changed = True
    while changed:
        changed = False
        for targets, value in assignments:
            name = dotted(value, names)
            if name in GUARDED_MODULES or name in BANNED:
                for target in targets:
                    if target not in names:
                        names[target] = name
                        changed = True
    return names


def attribute_of(node):
    """The (base, name) an attribute access reads: `a.b`, and `getattr(a,
    "b")` with a constant name, which reads the same attribute. None for
    anything else."""
    if isinstance(node, ast.Attribute):
        return node.value, node.attr
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr"
            and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)):
        return node.args[0], node.args[1].value
    return None


def dotted(node, names):
    """The dotted name an expression stands for through the bound names, or
    None. A guarded module reached as an attribute of anything is that
    module: shutil.os, posixpath.os, subprocess.os and getattr(shutil, "os")
    are all os."""
    if isinstance(node, ast.Name):
        name = names.get(node.id)
    else:
        attribute = attribute_of(node)
        if attribute is None:
            return None
        value, attr = attribute
        if attr in GUARDED_MODULES:
            return attr
        base = dotted(value, names)
        name = base + "." + attr if base else None
    if name and "." in name and name.rsplit(".", 1)[1] in GUARDED_MODULES:
        return name.rsplit(".", 1)[1]
    return name


class Calls(ast.NodeVisitor):
    """Finds a shell, an evaluator, a computed import or a network module in
    one file."""

    def __init__(self, path, problems, names):
        self.path = path
        self.problems = problems
        self.names = names
        self.bases = set()
        self.getattr_targets = set()

    def visit(self, node):
        # Note each node that is the base of an attribute access, or the
        # first argument of getattr, which reports it itself, or of vars,
        # an escape ADR 0011 accepts, before its children.
        if isinstance(node, ast.Attribute):
            self.bases.add(id(node.value))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id in ("getattr", "vars") and node.args):
            self.getattr_targets.add(id(node.args[0]))
        return ast.NodeVisitor.visit(self, node)

    def guarded_value(self, node):
        """A guarded module used as a value, anywhere but as the base of an
        attribute access: bound under another name by an assignment, a
        tuple, a walrus, a for loop, a default argument or a class
        attribute, or held in a container, it reaches a banned name the
        check cannot follow."""
        if not isinstance(node, ast.Call) and not isinstance(getattr(node, "ctx", None), ast.Load):
            return
        if id(node) in self.bases or id(node) in self.getattr_targets:
            return
        name = self.qualified(node)
        if name in GUARDED_MODULES:
            self.problem(node, "%s used as a value can reach a banned name under another name" % name)

    def problem(self, node, text):
        self.problems.append("%s:%d: %s" % (self.path, getattr(node, "lineno", 0), text))

    def qualified(self, node):
        return dotted(node, self.names)

    def check_module(self, node, name, level):
        if level:
            return
        top = name.split(".")[0]
        if top in REFUSED_MODULES:
            self.problem(node, "%s: %s" % (REFUSED_MODULES[top], name))
        elif top in NETWORK_MODULES:
            self.problem(node, "network module: " + name)
        elif top not in ALLOWED_MODULES:
            self.problem(node, (
                "import of %s in %s, a module outside the allowlist: add %s to ALLOWED_MODULES in"
                " .github/scripts/check_shipped_code.py in the same PR" % (name, self.path, top)
            ))
        else:
            parts = name.split(".")
            restricted = next(
                (".".join(parts[:n]) for n in range(len(parts), 0, -1) if ".".join(parts[:n]) in RESTRICTED_MODULES),
                None,
            )
            if restricted and self.path not in RESTRICTED_MODULES[restricted]:
                self.problem(node, "import of %s in %s: %s is allowed only in %s" % (
                    name, self.path, restricted, ", ".join(RESTRICTED_MODULES[restricted])))

    def visit_Import(self, node):
        for alias in node.names:
            self.check_module(node, alias.name, 0)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        self.check_module(node, node.module or "", node.level)
        if not node.level and node.module:
            for alias in node.names:
                if alias.name == "*" and node.module in GUARDED_MODULES:
                    self.problem(node, "from %s import * brings in names the check cannot see" % node.module)
                if node.module + "." + alias.name in BANNED:
                    self.problem(node, BANNED[node.module + "." + alias.name])
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in BANNED_NAMES and node.id not in self.names:
            self.problem(node, BANNED_NAMES[node.id])
        if isinstance(node.ctx, ast.Load) and self.names.get(node.id) in BANNED:
            self.problem(node, BANNED[self.names[node.id]])
        self.guarded_value(node)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        name = self.qualified(node)
        if name in BANNED:
            self.problem(node, BANNED[name])
        self.guarded_value(node)
        self.generic_visit(node)

    def visit_Call(self, node):
        func = self.qualified(node.func) or ""
        if isinstance(node.func, ast.Name) and node.func.id == "getattr" and node.args:
            target = self.qualified(node.args[0])
            if target in GUARDED_MODULES:
                self.problem(node, "getattr on %s can reach a banned name" % target)
            if attribute_of(node) is not None:
                name = self.qualified(node)
                if name in BANNED:
                    self.problem(node, BANNED[name])
                self.guarded_value(node)
        if func.startswith("subprocess."):
            if any(keyword.arg is None for keyword in node.keywords):
                self.problem(node, "** arguments to %s can carry shell=True" % func)
            if len(node.args) > 1 or any(isinstance(arg, ast.Starred) for arg in node.args):
                self.problem(node, "positional arguments after the first to %s can carry shell=True" % func)
        for keyword in node.keywords:
            if keyword.arg == "shell" and not (
                isinstance(keyword.value, ast.Constant) and keyword.value.value in (False, None)
            ):
                self.problem(node, "shell=True")
        self.generic_visit(node)


def check_python(path, data, problems):
    """Checks one shipped .py file. The Invariants hold for the code a user
    runs: a byte outside printable ASCII reaches a Windows console as another
    character, a shebang marks a file to execute, syntax past 3.9 breaks the
    oldest Python the tool supports, and a shell, an evaluator, a computed
    import or a network module would let the tool do what ADR 0011 says it
    never does."""
    for number, line in enumerate(data.split(b"\n"), 1):
        bad = [b for b in line if b not in ALLOWED_BYTES]
        if bad:
            problems.append("%s:%d: byte outside printable ASCII: 0x%02x" % (path, number, bad[0]))
            break
    if data.startswith(b"#!"):
        problems.append("%s:1: shebang" % path)
    try:
        tree = ast.parse(data, filename=path, feature_version=(3, 9))
    except SyntaxError as error:
        problems.append("%s:%s: does not parse as Python 3.9: %s" % (path, error.lineno, error.msg))
        return
    Calls(path, problems, bound_names(tree)).visit(tree)


def main(argv):
    repo = argv[0] if argv else "."
    problems = []
    count = 0
    for path in tracked(repo):
        count += 1
        full = os.path.join(repo, path)
        if path.startswith("skills/") and path.endswith(".py") and os.path.isfile(full):
            with open(full, "rb") as handle:
                check_python(path, handle.read(), problems)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("Shipped code passes: %d tracked files checked." % count)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
