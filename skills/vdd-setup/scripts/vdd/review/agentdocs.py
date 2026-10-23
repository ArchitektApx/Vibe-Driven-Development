"""The Agent documents in a review range: the changed Markdown files an
agent reads as instructions.

A changed .md file counts when it is a SKILL.md or under a skill's
references/, an AGENTS.md or a CLAUDE.md, a GLOSSARY.md or GLOSSARY-MAP.md,
or under a docs/adr/ directory; or when one of those documents, as it stands
at the range's tip and whether it changed or not, links to it with a
Markdown link target "](<path>)" or @-includes it on a line starting with
"@". One hop only. A target resolves from the linking file's directory with
its #fragment stripped; a URL, an absolute path and a <placeholder> target
are skipped. Only that link syntax is read, never the text around it.
"""

from __future__ import annotations

import posixpath
import re
from typing import Container

from .. import gitcmd, textfile

LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def direct(path: str, tree: Container[str]) -> bool:
    """Whether path is an Agent document by its own name and place."""
    if not path.endswith(".md"):
        return False
    parts = path.split("/")
    name = parts[-1]
    if name in ("SKILL.md", "AGENTS.md", "CLAUDE.md", "GLOSSARY.md", "GLOSSARY-MAP.md"):
        return True
    for index in range(len(parts) - 1):
        if parts[index] == "references" and "/".join(parts[:index] + ["SKILL.md"]) in tree:
            return True
        if parts[index] == "docs" and index + 1 < len(parts) - 1 and parts[index + 1] == "adr":
            return True
    return False


def targets(path: str, text: str) -> list[str]:
    """The repository paths a document links to or @-includes."""
    found: list[str] = []
    raw: list[str] = LINK.findall(text)
    for line in text.split("\n"):
        if line.startswith("@"):
            word = line[1:].strip().split()
            if word:
                raw.append(word[0])
    base = posixpath.dirname(path)
    for target in raw:
        if "<" in target or ">" in target or SCHEME.match(target) or target.startswith("/"):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        resolved = posixpath.normpath(posixpath.join(base, target))
        if resolved.startswith("../") or resolved == "..":
            continue
        found.append(resolved)
    return found


def listed(root: str, base: str, tip: str) -> list[str] | None:
    """The Agent documents in base...tip, sorted, or None when git cannot
    read the range. Refuses a call that timed out."""
    call = gitcmd.answered(gitcmd.git(root, "diff", "--name-only", "%s...%s" % (base, tip)))
    if not call.ok:
        return None
    changed = set(line.strip() for line in call.out.split("\n") if line.strip())
    call = gitcmd.answered(gitcmd.git(root, "ls-tree", "-r", "--name-only", tip))
    if not call.ok:
        return None
    tree = set(line.strip() for line in call.out.split("\n") if line.strip())
    found = set(path for path in changed if direct(path, tree))
    for path, text in read_all(root, tip, [path for path in sorted(tree) if direct(path, tree)]).items():
        for target in targets(path, text):
            if target in changed and target.endswith(".md"):
                found.add(target)
    return sorted(found)


def read_all(root: str, tip: str, paths: list[str]) -> dict[str, str]:
    """path -> its text at tip, for every path git can read, in one batch
    call however many there are. A missing one is left out."""
    if not paths:
        return {}
    request = "".join("%s:%s\n" % (tip, path) for path in paths).encode("utf-8")
    call = gitcmd.answered(gitcmd.git(root, "cat-file", "--batch", data=request))
    if not call.ok:
        return {}
    texts: dict[str, str] = {}
    data = call.data
    at = 0
    for path in paths:
        end = data.find(b"\n", at)
        if end < 0:
            break
        header = data[at:end].split(b" ")
        at = end + 1
        if len(header) != 3 or not header[2].isdigit():
            continue  # "<name> missing" or "ambiguous": nothing follows
        size = int(header[2])
        texts[path] = textfile.decode(data[at:at + size])
        at += size + 1
    return texts
