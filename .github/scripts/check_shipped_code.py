"""Static checks on the code this plugin ships.

Run from the repository root, or with the repository as the one argument. It
reads the tracked files and their modes from `git ls-files -s`, so gitignored
scratch files never count and a mode reads the same on every OS. Needs Python
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

# Kept until the 0.15 scripts are deleted with the Codex hook's move.
LEGACY_SCRIPT_KINDS = (".sh", ".ps1")

# Outside these directories every tracked file is one of the kinds below.
UNSHIPPED_DIRS = ("skills/", ".github/", "tests/", "docs/")
ROOT_FILES = (".gitignore", ".gitattributes", "LICENSE")
MANIFEST_DIRS = (".claude-plugin/", ".codex-plugin/")

# Modules that open a network connection, or serve or fetch over one.
NETWORK_MODULES = {
    "asyncio", "ftplib", "http", "imaplib", "nntplib", "poplib", "smtpd",
    "smtplib", "socket", "socketserver", "ssl", "telnetlib", "urllib",
    "webbrowser", "wsgiref", "xmlrpc",
}

# The tool's own package, imported by name from its entry.
OWN_PACKAGES = {"vdd"}

ALLOWED_BYTES = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D}


def tracked(repo):
    out = subprocess.run(
        ["git", "ls-files", "-s", "-z"], cwd=repo, check=True, capture_output=True
    ).stdout
    for entry in out.split(b"\0"):
        if not entry:
            continue
        meta, _, path = entry.partition(b"\t")
        mode = meta.split(b" ")[0].decode("ascii")
        yield mode, path.decode("utf-8", "surrogateescape")


def kind_problem(path):
    if path.startswith("skills/"):
        parts = path.split("/")
        if path.endswith(".md") or path.endswith(".py"):
            return None
        if len(parts) == 4 and parts[2:] == ["agents", "openai.yaml"]:
            return None
        if path.endswith(LEGACY_SCRIPT_KINDS):
            return None
        return "file kind not allowed under skills/ (only .md, agents/openai.yaml and .py): " + path
    if path.startswith(UNSHIPPED_DIRS):
        return None
    if path.endswith(".md"):
        return None
    if path.endswith(".json") and path.startswith(MANIFEST_DIRS) and path.count("/") == 1:
        return None
    if path in ROOT_FILES:
        return None
    return "file kind not allowed: " + path


class Calls(ast.NodeVisitor):
    """Finds a shell, an evaluator or a network module in one file."""

    def __init__(self, path, problems):
        self.path = path
        self.problems = problems

    def problem(self, node, text):
        self.problems.append("%s:%d: %s" % (self.path, getattr(node, "lineno", 0), text))

    def check_module(self, node, name, level):
        if level:
            return
        top = name.split(".")[0]
        if top in NETWORK_MODULES:
            self.problem(node, "network module: " + name)
        elif top not in sys.stdlib_module_names and top not in OWN_PACKAGES:
            self.problem(node, "import outside the standard library: " + name)

    def visit_Import(self, node):
        for alias in node.names:
            self.check_module(node, alias.name, 0)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        self.check_module(node, node.module or "", node.level)
        if not node.level and node.module == "os":
            for alias in node.names:
                if alias.name in ("system", "popen"):
                    self.problem(node, "os." + alias.name)
        self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
            self.problem(node, func.id + "()")
        if isinstance(func, ast.Attribute):
            base = func.value
            if isinstance(base, ast.Name) and base.id == "os" and func.attr in ("system", "popen"):
                self.problem(node, "os." + func.attr)
            if isinstance(base, ast.Name) and base.id == "subprocess" and func.attr in ("getoutput", "getstatusoutput"):
                self.problem(node, "subprocess." + func.attr + " runs a shell")
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
    Calls(path, problems).visit(tree)


def main(argv):
    repo = argv[0] if argv else "."
    problems = []
    count = 0
    for mode, path in tracked(repo):
        count += 1
        problem = kind_problem(path)
        if problem:
            problems.append(problem)
        if path.startswith("skills/") and mode != "100644":
            problems.append("mode %s, not 100644, under skills/: %s" % (mode, path))
        if path.startswith("skills/") and path.endswith(".py"):
            full = os.path.join(repo, path)
            if not os.path.isfile(full):
                continue
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
