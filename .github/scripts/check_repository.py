"""The repository Invariants in AGENTS.md that are not about a shipped `.py`.

Run from the repository root, or with the repository as the one argument. It
reads the tracked files and their modes from `git ls-files -s`, so gitignored
scratch files never count and a mode reads the same on every OS. Each check
is one function; its docstring carries the reason the Invariant holds, and a
deliberate exception edits the function in the same PR so the reviewer sees
both. The workflow checks are text checks on the lines that are not comments:
the runner has no YAML parser.

Prints one line per problem and exits 1 when there is any, 0 otherwise.
"""

import json
import os
import posixpath
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote

ORCHESTRATOR = "skills/vdd-orchestrator/SKILL.md"
HOSTED = (
    "skills/vdd-plan-reviewer/SKILL.md",
    "skills/vdd-coder/SKILL.md",
    "skills/vdd-code-reviewer/SKILL.md",
)
START_SENTENCE = "An Orchestrator hosts this Workflow."

CODEX_HOOK = {
    "hooks": {
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": (
                            "[ ! -d .scratch ] || [ -z \"$(find .scratch -mindepth 2 -maxdepth 2"
                            " -name 'codex-armed-*' 2>/dev/null)\" ] || python3"
                            " \"${PLUGIN_ROOT}/skills/vdd-setup/scripts/vdd.py\" codex-stop || true"
                        ),
                        "commandWindows": (
                            "if (Test-Path .scratch\\*\\codex-armed-*) { py -3"
                            " \"${PLUGIN_ROOT}\\skills\\vdd-setup\\scripts\\vdd.py\" codex-stop }; exit 0"
                        ),
                        "timeout": 2760,
                    }
                ]
            }
        ]
    }
}

# The fields Codex repeats from .claude-plugin/plugin.json.
REPEATED_FIELDS = ("name", "version", "description", "author", "homepage", "repository", "license", "keywords")

# Outside these directories every tracked file is one of the kinds below.
UNSHIPPED_DIRS = ("skills/", ".github/", "tests/", "docs/")
ROOT_FILES = (".gitignore", ".gitattributes", "LICENSE", "pyrightconfig.json")
MANIFEST_DIRS = (".claude-plugin/", ".codex-plugin/")

HARNESS_NONE = "none: the inline text is complete"
REFERENCE_LIMIT = 8192

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)")
HARNESS_LINK = re.compile(r"\]\(([^)\s]+)\)")
HARNESS_ENTRY = re.compile(r"^\s*-\s+([^:`]+):\s*(.*?)\s*$")
EXTERNAL = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)
PLACEHOLDER = re.compile(r"<[^>]*>")
# A hooks key at any indentation, quoted or not.
HOOKS_KEY = re.compile(r"""^\s*["']?hooks["']?\s*:""")
TOP_KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*$")
LINE_END = re.compile(r"\r\n|\r|\n")
# A `: write` grant, quoted or not, of any scope, block or flow style.
WRITE_GRANT = re.compile(r""":\s*["']?write["']?(?=\s*(?:[,}#]|$))""")
TRAILING_COMMENT = re.compile(r"\s+#.*$")
# A `permissions:` key at any indentation, quoted or not, and the one form a
# scope under it may take: `scope: value` on one line, each plain or quoted.
PERMISSIONS_KEY = re.compile(r"""^(\s*)(["']?)permissions\2\s*:\s*(.*?)\s*$""")
SCOPE_LINE = re.compile(r"""^\s*(["']?)[\w-]+\1\s*:\s*(["']?)[\w-]+\2\s*$""")
MATRIX_LEG = re.compile(r"""\bos\s*:\s*([\w.-]+)\s*,\s*python\s*:\s*(["']?)([\w.]+)\2""")
# The test job's runner and Python, each taken from its matrix leg.
RUNS_ON = re.compile(r"^\s*runs-on\s*:\s*(.*?)\s*$")
PYTHON_VERSION = re.compile(r"^\s*python-version\s*:\s*(.*?)\s*$")
MATRIX_OS = re.compile(r"""^(["']?)\$\{\{\s*matrix\.os\s*\}\}\1$""")
MATRIX_PYTHON = re.compile(r"""^(["']?)\$\{\{\s*matrix\.python\s*\}\}\1$""")
TEST_OSES = ("ubuntu", "windows", "macos")
TEST_PYTHONS = ("3.9", "3.x")

RELEASE = ".github/workflows/release.yml"
VERIFY = ".github/workflows/verify.yml"
TAG_VERSION = r"'^[0-9]+\.[0-9]+\.[0-9]+$'"
DISPATCH_VERSION = r"'^[0-9]+\.[0-9]+\.[0-9]+(-beta\.[0-9]+)?$'"


class Repo:
    """The repository as git tracks it: one `git ls-files -s` listing."""

    def __init__(self, root: str):
        self.root = root
        out = subprocess.run(
            ["git", "ls-files", "-s", "-z"], cwd=root, check=True, stdout=subprocess.PIPE
        ).stdout
        self.files: List[Tuple[str, str]] = []
        for entry in out.split(b"\0"):
            if not entry:
                continue
            meta, _, path = entry.partition(b"\t")
            mode = meta.split(b" ")[0].decode("ascii")
            self.files.append((mode, path.decode("utf-8", "surrogateescape")))
        self.paths = [path for _, path in self.files]
        self.tracked = set(self.paths)
        self.dirs = set()
        for path in self.paths:
            parent = posixpath.dirname(path)
            while parent:
                self.dirs.add(parent)
                parent = posixpath.dirname(parent)

    def under(self, prefix: str) -> List[str]:
        return [path for path in self.paths if path.startswith(prefix)]

    def data(self, path: str) -> Optional[bytes]:
        try:
            with open(os.path.join(self.root, path), "rb") as handle:
                return handle.read()
        except OSError:
            return None

    def text(self, path: str) -> Optional[str]:
        data = self.data(path)
        if data is None:
            return None
        return data.decode("utf-8", "replace").lstrip("\ufeff")

    def lines(self, path: str) -> Optional[List[str]]:
        text = self.text(path)
        return None if text is None else LINE_END.split(text)

    def skill_files(self) -> List[str]:
        """Each skills/<name>/SKILL.md."""
        return [p for p in self.paths if p.startswith("skills/") and p.count("/") == 2 and p.endswith("/SKILL.md")]


def frontmatter(text: Optional[str]) -> Optional[List[str]]:
    """The lines between a file's opening `---` and the next, or None when it
    has none. Reads past a byte order mark and splits on any line end; a fence
    is `---` exactly, since a Harness reads no indented or padded fence as
    frontmatter."""
    if text is None:
        return None
    lines = LINE_END.split(text.lstrip("\ufeff"))
    if not lines or lines[0] != "---":
        return None
    for number in range(1, len(lines)):
        if lines[number] == "---":
            return lines[1:number]
    return None


def frontmatter_keys(lines: List[str]) -> Dict[str, str]:
    keys = {}
    for line in lines:
        match = TOP_KEY.match(line)
        if match:
            keys.setdefault(match.group(1), match.group(2).strip("\"'"))
    return keys


def link_targets(text: str, pattern=LINK) -> List[str]:
    """Each relative link target in a Markdown text, without its anchor. A
    target with <angle brackets> is a placeholder the reader fills in."""
    targets = []
    for match in pattern.finditer(text):
        target = unquote(re.split(r"[#?]", match.group(1).strip())[0])
        if not target or EXTERNAL.match(target) or target.startswith(("/", "#")) or PLACEHOLDER.search(target):
            continue
        targets.append(target)
    return targets


def code_lines(repo: Repo, path: str) -> List[Tuple[int, str]]:
    """A workflow's lines that are not comments, by number."""
    return [
        (number, line)
        for number, line in enumerate(repo.lines(path) or [], 1)
        if line.strip() and not line.lstrip().startswith("#")
    ]


def block(lines: List[Tuple[int, str]], key: str) -> Optional[List[str]]:
    """The lines under a top-level `key:`, trailing comments cut, or None when
    the key is missing. An inline value is the block's one line."""
    found = None
    for _, line in lines:
        line = TRAILING_COMMENT.sub("", line)
        if found is None:
            if re.match(r"^%s\s*:" % re.escape(key), line):
                found = []
                rest = line.split(":", 1)[1].strip()
                if rest:
                    found.append(rest)
            continue
        if not line.startswith((" ", "\t")):
            break
        found.append(line)
    return found


def check_manifests(repo: Repo) -> List[str]:
    """A broken manifest breaks install for every user. Codex ignores
    .claude-plugin/plugin.json once its own exists, so a field changed in one
    drifts silently, and version drift is always a mistake."""
    manifests = {}
    for path in (".claude-plugin/marketplace.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        try:
            manifests[path] = json.loads(repo.text(path) or "")
        except ValueError as error:
            return ["missing or invalid JSON: %s: %s" % (path, error)]
    market = manifests[".claude-plugin/marketplace.json"]
    claude = manifests[".claude-plugin/plugin.json"]
    codex = manifests[".codex-plugin/plugin.json"]
    entry = next((e for e in market.get("plugins") or [] if e.get("name") == claude.get("name")), None)
    if entry is None:
        return ["marketplace.json has no plugin named %s" % claude.get("name")]
    problems = []
    if entry.get("version") != claude.get("version"):
        problems.append("version drift: marketplace %s vs plugin.json %s" % (entry.get("version"), claude.get("version")))
    if entry.get("source") != "./":
        problems.append('plugin %s sources from %s, expected "./" (this repo)' % (claude.get("name"), json.dumps(entry.get("source"))))
    for key in REPEATED_FIELDS:
        if key not in claude or key not in codex:
            problems.append("%s is missing from %s/plugin.json" % (key, ".codex-plugin" if key in claude else ".claude-plugin"))
    for key in claude:
        if key in codex and key != "hooks" and claude[key] != codex[key]:
            problems.append(".codex-plugin/plugin.json %s differs from .claude-plugin/plugin.json" % key)
    return problems


def check_frontmatter(repo: Repo) -> List[str]:
    """A Harness finds a skill by the name and description in its
    frontmatter."""
    problems = []
    for path in repo.under("skills/"):
        if path.split("/")[-1] != "SKILL.md":
            continue
        lines = frontmatter(repo.text(path))
        if lines is None:
            problems.append("missing frontmatter: " + path)
            continue
        keys = frontmatter_keys(lines)
        for key in ("name", "description"):
            if not keys.get(key):
                problems.append("missing %s in the frontmatter: %s" % (key, path))
    return problems


def check_unique_names(repo: Repo) -> List[str]:
    """`npx skills add` installs by frontmatter name, so a duplicate silently
    clobbers the other skill."""
    owners: Dict[str, List[str]] = {}
    for path in repo.skill_files():
        name = frontmatter_keys(frontmatter(repo.text(path)) or []).get("name")
        if name:
            owners.setdefault(name, []).append(path)
    return [
        "duplicate skill name %s: %s" % (name, ", ".join(paths))
        for name, paths in sorted(owners.items())
        if len(paths) > 1
    ]


def check_relative_links(repo: Repo) -> List[str]:
    """A link to a file that does not ship strands its reader, in a Reference
    file as in a skill file. A link resolves to a tracked file or directory."""
    problems = []
    for path in repo.under("skills/"):
        if not path.endswith(".md"):
            continue
        for target in link_targets(repo.text(path) or ""):
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
            if resolved not in repo.tracked and resolved not in repo.dirs:
                problems.append("%s: link resolves to nothing: %s" % (path, target))
    return problems


def check_reference_links(repo: Repo) -> List[str]:
    """A Reference file its skill file does not link is one no reader is sent
    to. A direct link is enough: each is linked from the step that reads it, a
    Harness file from ## Harnesses."""
    problems = []
    roots = sorted({"/".join(p.split("/")[:2]) for p in repo.under("skills/") if p.count("/") >= 2})
    for root in roots:
        skill = root + "/SKILL.md"
        if skill not in repo.tracked:
            problems.append("%s: no SKILL.md" % root)
            continue
        linked = {
            posixpath.normpath(posixpath.join(root, target)) for target in link_targets(repo.text(skill) or "")
        }
        for path in repo.under(root + "/references/"):
            if path not in linked:
                problems.append("%s: no direct link from %s" % (path, skill))
    return problems


def check_reference_size(repo: Repo) -> List[str]:
    """Some Harnesses truncate a long file, so a Role can miss the end of a
    Reference file it reads in one call."""
    problems = []
    for path in repo.under("skills/"):
        if "/references/" not in path:
            continue
        size = len(repo.data(path) or b"")
        if size > REFERENCE_LIMIT:
            problems.append("%s: %d bytes, over 8 KB" % (path, size))
    return problems


def check_harness_index(repo: Repo) -> List[str]:
    """A skill that ships a Harness file and leaves a Harness out of
    ## Harnesses sends that reader nowhere."""
    shipped: Dict[str, List[str]] = {}
    for skill in repo.skill_files():
        root = posixpath.dirname(skill)
        for path in repo.under(root + "/"):
            match = re.match(r"^harness-(.+)\.md$", posixpath.basename(path))
            if match:
                shipped.setdefault(skill, []).append(match.group(1))
    every = sorted({slug for slugs in shipped.values() for slug in slugs})
    problems = []
    for skill in sorted(shipped):
        lines = repo.lines(skill) or []
        start = next((i for i, line in enumerate(lines) if line.strip() == "## Harnesses"), None)
        if start is None:
            problems.append("%s: ships a Harness file and has no ## Harnesses section" % skill)
            continue
        end = next((i for i in range(start + 1, len(lines)) if re.match(r"^#{1,2} ", lines[i])), len(lines))
        linked = set()
        none = set()
        for line in lines[start + 1:end]:
            for match in HARNESS_LINK.finditer(line):
                linked.add(posixpath.normpath(re.split(r"[#?]", match.group(1))[0]))
            entry = HARNESS_ENTRY.match(line)
            if entry and entry.group(2) == HARNESS_NONE:
                none.add(re.sub(r"\s+", "-", entry.group(1).strip().lower()))
        for slug in every:
            own = "references/harness-%s.md" % slug
            if own not in linked and slug not in none:
                problems.append('%s: ## Harnesses has no entry for %s (a link to %s, or "%s")' % (skill, slug, own, HARNESS_NONE))
    return problems


def implicit_off(lines: List[str]) -> bool:
    top = None
    for line in lines:
        key = re.match(r"^([A-Za-z_][\w-]*)\s*:", line)
        if key:
            top = key.group(1)
            continue
        value = re.match(r"^\s+allow_implicit_invocation\s*:\s*(\S+)\s*$", line)
        if value and top == "policy" and value.group(1) == "false":
            return True
    return False


def check_user_invoked_pairs(repo: Repo) -> List[str]:
    """Each half of the pair is ignored by the Harnesses the other covers, so
    one half alone leaves the skill model-invocable on those Harnesses."""
    problems = []
    policies = {p for p in repo.under("skills/") if p.endswith("/agents/openai.yaml")}
    for policy in sorted(policies):
        if posixpath.dirname(posixpath.dirname(policy)) + "/SKILL.md" not in repo.tracked:
            problems.append("%s: no SKILL.md beside its agents directory" % policy)
    for skill in repo.skill_files():
        root = posixpath.dirname(skill)
        lines = frontmatter(repo.text(skill)) or []
        blocked = any(re.match(r"^disable-model-invocation:\s*true\s*$", line) for line in lines)
        policy = root + "/agents/openai.yaml"
        off = policy in policies and implicit_off(repo.lines(policy) or [])
        if blocked and policy not in policies:
            problems.append("%s: disable-model-invocation: true and no agents/openai.yaml" % root)
        elif blocked and not off:
            problems.append("%s: disable-model-invocation: true but %s does not set policy.allow_implicit_invocation: false" % (root, policy))
        elif not blocked and off:
            problems.append("%s: %s sets policy.allow_implicit_invocation: false but the frontmatter lacks disable-model-invocation: true" % (root, policy))
    return problems


def check_start_sentence(repo: Repo) -> List[str]:
    """The hosted skills refuse to run unless their prompt says the start
    sentence, and the Spawn prompt is the one that says it (ticket 76): an
    edit to either side makes every spawn refuse."""
    problems = []
    if "You are the <Role> in a Vibe Driven Development loop. " + START_SENTENCE not in (repo.text(ORCHESTRATOR) or ""):
        problems.append("%s: the Spawn prompt lacks: %s" % (ORCHESTRATOR, START_SENTENCE))
    for path in HOSTED:
        if 'If the prompt that started you does not say "%s"' % START_SENTENCE not in (repo.text(path) or ""):
            problems.append("%s: the start check lacks: %s" % (path, START_SENTENCE))
    return problems


def check_claude_md(repo: Repo) -> List[str]:
    """Claude Code reads CLAUDE.md first, so a house rule added only to
    AGENTS.md never reaches it, and one added to both is read twice. The
    bytes are compared, trailing newlines removed and nothing else, so a byte
    order mark or a CRLF line end is refused."""
    if (repo.data("CLAUDE.md") or b"").rstrip(b"\n") != b"@AGENTS.md":
        return ["CLAUDE.md must contain exactly the line: @AGENTS.md"]
    return []


def check_executable_surface(repo: Repo) -> List[str]:
    """No symlinks, executable files, MCP servers or hook but one: each would
    end up on every installer's machine. The one hook is the Codex Stop hook,
    which check_codex_hook holds to its form. The Claude Code manifests
    declare no hook or MCP server, and no hook or MCP config file is
    tracked."""
    problems = []
    for mode, path in repo.files:
        if mode == "120000":
            problems.append("symlink in distributed content: " + path)
        elif mode == "100755":
            problems.append("executable in distributed content: " + path)
        if posixpath.basename(path) in ("hooks.json", ".mcp.json", "mcp.json"):
            problems.append("unexpected hook or MCP config: " + path)
    for path in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
        if re.search(r'"(hooks|mcpServers)"', repo.text(path) or ""):
            problems.append("%s declares hooks or MCP servers; only .codex-plugin/plugin.json carries the one hook" % path)
    return problems


def check_skill_modes(repo: Repo) -> List[str]:
    """Every tracked file under skills/ is at mode 644: a shipped file runs
    through a named interpreter, never as a program of its own. The mode is
    the index's, so it reads the same on every OS."""
    return [
        "mode %s, not 100644, under skills/: %s" % (mode, path)
        for mode, path in repo.files
        if path.startswith("skills/") and mode != "100644"
    ]


def check_codex_hook(repo: Repo) -> List[str]:
    """The one hook is the Codex Stop hook inline in .codex-plugin/plugin.json,
    in its fixed form, because Codex's trust covers its command string and a
    changed string is a hook every user trusts again. The guard uses find, not
    a bare glob: zsh aborts on an unmatched glob, which Codex shows as "Hook
    failed" at every turn end."""
    try:
        codex = json.loads(repo.text(".codex-plugin/plugin.json") or "")
    except ValueError:
        return [".codex-plugin/plugin.json: missing or invalid JSON"]
    problems = []
    if codex.get("hooks") != CODEX_HOOK:
        problems.append(".codex-plugin/plugin.json: hooks is not exactly the one Codex Stop hook in its fixed form")
    if "mcpServers" in codex:
        problems.append(".codex-plugin/plugin.json declares MCP servers")
    return problems


def check_skill_hooks(repo: Repo) -> List[str]:
    """A hooks key in a SKILL.md frontmatter is a hook: Claude Code registers
    it when the skill runs, plugin skills included. The one hook is the Codex
    Stop hook in .codex-plugin/plugin.json."""
    problems = []
    for path in repo.under("skills/"):
        if path.split("/")[-1] != "SKILL.md":
            continue
        for number, line in enumerate(frontmatter(repo.text(path)) or [], 2):
            if HOOKS_KEY.match(line):
                problems.append("%s:%d: hooks key in the frontmatter: a second hook" % (path, number))
    return problems


def check_policy_keys(repo: Repo) -> List[str]:
    """A `dependencies` key in agents/openai.yaml can declare tools and MCP
    servers, so `interface` and `policy` are the only top-level keys."""
    problems = []
    for path in repo.under("skills/"):
        if not path.endswith("/agents/openai.yaml"):
            continue
        lines = repo.lines(path) or []
        content = [l for l in lines if l.strip() and not l.lstrip().startswith("#") and l.rstrip() != "---"]
        if content and content[0][0] in " \t":
            problems.append("%s: top-level keys must start at column 0" % path)
        for line in content:
            if line[0] in " \t#" or line.rstrip() == "...":
                continue
            if not re.match(r"^(interface|policy)\s*:", line):
                problems.append("%s: top-level key other than interface and policy: %s" % (path, line.strip()))
    return problems


def check_file_kinds(repo: Repo) -> List[str]:
    """Under skills/ every tracked file is .md, agents/openai.yaml or .py, so
    nothing else ships to an installer's machine. Outside skills/, .github/,
    tests/ and docs/ every tracked file is .md, a manifest under
    .claude-plugin/ or .codex-plugin/, or one of the root files."""
    problems = []
    for path in repo.paths:
        if path.startswith("skills/"):
            parts = path.split("/")
            if path.endswith((".md", ".py")) or (len(parts) == 4 and parts[2:] == ["agents", "openai.yaml"]):
                continue
            problems.append("file kind not allowed under skills/ (only .md, agents/openai.yaml and .py): " + path)
        elif path.startswith(UNSHIPPED_DIRS) or path.endswith(".md") or path in ROOT_FILES:
            continue
        elif path.endswith(".json") and path.startswith(MANIFEST_DIRS) and path.count("/") == 1:
            continue
        else:
            problems.append("file kind not allowed: " + path)
    return problems


def job_of(lines: List[Tuple[int, str]]) -> Dict[int, Optional[str]]:
    """Each line's job under `jobs:` by number, None outside jobs."""
    jobs: Dict[int, Optional[str]] = {}
    inside = False
    job = None
    for number, line in lines:
        if not line.startswith((" ", "\t")):
            inside = bool(re.match(r"^jobs\s*:", line))
            job = None
        elif inside:
            match = re.match(r"^  ([A-Za-z_][\w-]*)\s*:", line)
            if match:
                job = match.group(1)
        jobs[number] = job if inside else None
    return jobs


def trigger_keys(on: List[str]) -> List[str]:
    return sorted(re.sub(r"\s*:.*$", "", line.strip()) for line in on if re.match(r"^  \S", line))


def split_permissions(path: str, lines: List[Tuple[int, str]]) -> List[str]:
    """Each line under a block `permissions:` key, quoted or not, that is not
    `scope: value` on one line, each such key whose own value is a block
    scalar, anchor, alias or tag, and each flow mapping under it that does
    not close on its own line. YAML joins a value on the next line or in a
    block scalar to its scope, so `contents:` then `write` grants write, and
    the one-line check in check_write_access would not see it."""
    problems = []
    for index, (number, line) in enumerate(lines):
        line = TRAILING_COMMENT.sub("", line)
        match = PERMISSIONS_KEY.match(line)
        if not match:
            continue
        indent, rest = len(match.group(1)), match.group(3)
        if rest:
            if rest[0] in "|>&*!" or (rest[0] == "{" and not rest.endswith("}")):
                problems.append("%s:%d: permissions is not a plain value; write it on one line: %s" % (path, number, line.strip()))
            continue
        for child_number, child in lines[index + 1:]:
            child = TRAILING_COMMENT.sub("", child)
            if len(child) - len(child.lstrip()) <= indent:
                break
            if not SCOPE_LINE.match(child):
                problems.append("%s:%d: a permission not written as `scope: value` on one line; write the scope and its value on one line: %s"
                                % (path, child_number, child.strip()))
    return problems


def check_write_access(repo: Repo) -> List[str]:
    """release.yml alone may write to the repository, and only from a version
    tag push or a workflow_dispatch; a pull_request trigger there would run
    PR-head content with write access. verify.yml runs PR-head content too, on
    pull_request and never pull_request_target, so it gets no write access or
    secrets, and a push to any branch runs it, so a branch shows its check
    before a PR exists. Any `: write`, quoted or not, of any scope, outside
    release.yml's release job is refused, and so is a scope whose value is
    not on its own line, which YAML reads as the same grant."""
    problems = []
    workflows = [p for p in repo.under(".github/workflows/") if p.endswith((".yml", ".yaml"))]
    if RELEASE not in workflows:
        problems.append("missing " + RELEASE)
    if VERIFY not in workflows:
        problems.append("missing " + VERIFY)
    for path in workflows:
        lines = code_lines(repo, path)
        jobs = job_of(lines)
        problems.extend(split_permissions(path, lines))
        grants = []
        for number, line in lines:
            if "write-all" in line:
                problems.append("%s:%d: grants every permission at once" % (path, number))
            if WRITE_GRANT.search(line):
                grants.append((number, line))
        for number, line in grants:
            if path != RELEASE or jobs.get(number) != "release":
                problems.append("%s:%d: grants write access, which only release.yml's release job may: %s" % (path, number, line.strip()))
        in_release_job = [line.strip() for number, line in grants if path == RELEASE and jobs.get(number) == "release"]
        if path == RELEASE and in_release_job != ["contents: write"]:
            problems.append("%s: the release job grants %s, expected contents: write alone" % (path, in_release_job or "nothing"))
        permissions = block(lines, "permissions")
        if permissions != ["  contents: read"]:
            problems.append("%s: workflow-level permissions are %s, expected contents: read alone" % (path, permissions))
        if "pull_request_target" in "\n".join(line for _, line in lines):
            problems.append("%s: names pull_request_target" % path)
    if RELEASE in workflows:
        lines = code_lines(repo, RELEASE)
        on = block(lines, "on") or []
        if trigger_keys(on) != ["push", "workflow_dispatch"]:
            problems.append("%s: triggers are %s, expected push and workflow_dispatch" % (RELEASE, trigger_keys(on)))
        push_filters = trigger_filters(on, "push")
        if [re.sub(r"\s*:.*$", "", f.strip()) for f in push_filters] != ["tags"]:
            problems.append("%s: push filters are %s, expected tags only" % (RELEASE, push_filters))
        if any("pull_request" in line for _, line in lines):
            problems.append("%s: names a pull_request trigger" % RELEASE)
    if VERIFY in workflows:
        on = block(code_lines(repo, VERIFY), "on") or []
        if trigger_keys(on) != ["pull_request", "push"]:
            problems.append("%s: triggers are %s, expected push and pull_request" % (VERIFY, trigger_keys(on)))
        push_filters = [f.strip() for f in trigger_filters(on, "push")]
        if len(push_filters) != 1 or not re.match(r"""^branches\s*:\s*\[\s*(['"])\*\*\1\s*\]$""", push_filters[0]):
            problems.append("%s: push filters are %s, expected branches: ['**'] alone" % (VERIFY, push_filters))
        if trigger_filters(on, "pull_request"):
            problems.append("%s: pull_request has filters, expected none" % VERIFY)
    return problems


def trigger_filters(on: List[str], trigger: str) -> List[str]:
    """The lines under one trigger in an `on:` block."""
    found: List[str] = []
    inside = False
    for line in on:
        if re.match(r"^  \S", line):
            inside = bool(re.match(r"^  %s\s*:" % re.escape(trigger), line))
            rest = line.split(":", 1)[1].strip() if inside and ":" in line else ""
            if rest:
                found.append(rest)
            continue
        if inside:
            found.append(line)
    return found


CHECKS = (
    check_manifests,
    check_frontmatter,
    check_unique_names,
    check_relative_links,
    check_reference_links,
    check_reference_size,
    check_harness_index,
    check_user_invoked_pairs,
    check_start_sentence,
    check_claude_md,
    check_executable_surface,
    check_skill_modes,
    check_codex_hook,
    check_skill_hooks,
    check_policy_keys,
    check_file_kinds,
    check_write_access,
)


def main(argv: List[str]) -> int:
    repo = Repo(argv[0] if argv else ".")
    problems = []
    for check in CHECKS:
        problems.extend(check(repo))
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("Repository passes: %d checks on %d tracked files." % (len(CHECKS), len(repo.paths)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
