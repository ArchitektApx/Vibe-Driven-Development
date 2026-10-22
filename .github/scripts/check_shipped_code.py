"""Static checks on the `.py` files this plugin ships.

Run from the repository root, or with the repository as the one argument. It
reads the tracked files from `git ls-files`, so gitignored scratch files never
count. The repository's other Invariants are check_repository.py's. Needs Python
3.10 or newer for sys.stdlib_module_names; the shipped code itself is checked
against Python 3.9.

Prints one line per problem and exits 1 when there is any, 0 otherwise.
"""

import ast
import os
import subprocess
import sys

if sys.version_info < (3, 10):
    print("check_shipped_code.py needs Python 3.10 or newer (sys.stdlib_module_names).")
    sys.exit(2)

# Modules that open a network connection, or serve or fetch over one, and
# the C modules under socket and ssl.
NETWORK_MODULES = {
    "_socket", "_ssl", "asyncio", "ftplib", "http", "imaplib", "nntplib",
    "poplib", "smtpd", "smtplib", "socket", "socketserver", "ssl", "telnetlib",
    "urllib", "webbrowser", "wsgiref", "xmlrpc",
}

# The tool's own package, imported by name from its entry.
OWN_PACKAGES = {"vdd"}

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
    return names


class Calls(ast.NodeVisitor):
    """Finds a shell, an evaluator, a computed import or a network module in
    one file."""

    def __init__(self, path, problems, names):
        self.path = path
        self.problems = problems
        self.names = names

    def problem(self, node, text):
        self.problems.append("%s:%d: %s" % (self.path, getattr(node, "lineno", 0), text))

    def qualified(self, node):
        """The dotted name an expression stands for through the imports, or
        None."""
        if isinstance(node, ast.Name):
            return self.names.get(node.id)
        if isinstance(node, ast.Attribute):
            base = self.qualified(node.value)
            return base + "." + node.attr if base else None
        return None

    def check_module(self, node, name, level):
        if level:
            return
        top = name.split(".")[0]
        if top in REFUSED_MODULES:
            self.problem(node, "%s: %s" % (REFUSED_MODULES[top], name))
        elif top in NETWORK_MODULES:
            self.problem(node, "network module: " + name)
        elif top not in sys.stdlib_module_names and top not in OWN_PACKAGES:
            self.problem(node, "import outside the standard library: " + name)

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
        self.generic_visit(node)

    def visit_Attribute(self, node):
        name = self.qualified(node)
        if name in BANNED:
            self.problem(node, BANNED[name])
        self.generic_visit(node)

    def visit_Call(self, node):
        func = self.qualified(node.func) or ""
        if isinstance(node.func, ast.Name) and node.func.id == "getattr" and node.args:
            target = self.qualified(node.args[0])
            if target in GUARDED_MODULES:
                self.problem(node, "getattr on %s can reach a banned name" % target)
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
