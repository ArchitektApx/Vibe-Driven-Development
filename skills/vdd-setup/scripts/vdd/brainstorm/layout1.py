"""The migration step from layout 1, a 0.15 idea store (one file per idea and
index.md), to layout 2, which stays flat: every idea keeps its file name.

The new layout is built in .scratch/_brainstorming.migrating/ without
touching the old store; then two renames swap it in. The old store becomes
the backup .scratch/_brainstorming.pre-0.16/, byte for byte, and the staging
becomes the store. A rerun finishes whatever an interrupted run left. The
Log in index.md is not converted: the model reads the restructures it
records from the sentences the plan prints and passes them as --event. The
step needs the user: its ask carries the events.
"""

from __future__ import annotations

import os
import re
import shutil
from typing import Dict, List, Tuple

from .. import textfile
from ..out import Failure
from .ideafile import CLOSED, Idea, fenced, real_date, split_frontmatter, today
from .lock import Lock
from .store import LAYOUT_FILE, LEDGER, STATE, STORE, layout, ledger_bytes, ledger_sha, read_once

# The layout this step reads and the one it leaves.
FROM, TO = "1", "2"
# Whether the step asks the user before it runs: its events come from them.
NEEDS_USER = True
BACKUP = STORE + ".pre-0.16"
STAGING = STORE + ".migrating"
# The migration's own lock, beside the store: the store itself is renamed
# away during a migration, its .state/lock with it.
LOCK = STORE + ".lock"
LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
FM_KINDS = (("depends-on", "depends on"), ("benefits-from", "benefits from"), ("related", "related"))
RESTRUCTURE = re.compile(r"\b(split|splits|folded|fold|folds|renamed|absorb\w*|"
                         r"merged into (?!`?(?:beta|master|main)\b))", re.I)
SLUG_RE = r"[a-z0-9]+(?:-[a-z0-9]+)*"
EVENT = re.compile(r"^(\d{4}-\d{2}-\d{2}):?\s+(%s)\s+(split into|split-into|merged into|merged-into|folded into|"
                   r"folded-into|renamed from|renamed-from)\s+(%s(?:\s*(?:,|and)\s*%s)*)\s*\.?$"
                   % (SLUG_RE, SLUG_RE, SLUG_RE))
FOLDED = re.compile(r"(?<![A-Za-z0-9-])`?(%s)`?\s+folded[- ]into\s+`?(%s)(?![A-Za-z0-9-])" % (SLUG_RE, SLUG_RE),
                    re.I)
UNDO = ("To undo the migration: delete .scratch/_brainstorming/, rename .scratch/_brainstorming.pre-0.16/ back to "
        ".scratch/_brainstorming/, and use a 0.15 VDD plugin. On 0.16 a restored store is offered the migration "
        "again.")

Event = Tuple[str, str, str, List[str]]
OldIdea = Tuple[Dict[str, str], Dict[str, List[str]], str]
# (lines, what happened, what a dry run's --write would write)
Result = Tuple[List[str], str, List[str]]


def paths(root: str) -> tuple[str, str, str]:
    return (os.path.join(root, STORE), os.path.join(root, BACKUP), os.path.join(root, STAGING))


def half(root: str) -> bool:
    """Whether a migration stopped between its two renames: no store, the
    backup complete and the staging finished beside it."""
    return state(root) == "half"


def state(root: str) -> str:
    """Where a migration stands: "old" (a 0.15 store, maybe with a leftover
    staging), "half" (backup and finished staging, no store), "done" (a
    store), or "none"."""
    store, backup, staging = paths(root)
    has_store = os.path.isdir(store)
    if has_store and layout(root) == "1":
        return "old"
    if not has_store and os.path.isdir(backup) and os.path.isfile(os.path.join(staging, LAYOUT_FILE)):
        return "half"
    return "done" if has_store else "none"


def old_slugs(store: str) -> list[str]:
    return sorted(f[:-3] for f in os.listdir(store)
                  if f.endswith(".md") and f != "index.md" and os.path.isfile(os.path.join(store, f)))


def read_old(store: str) -> dict[str, OldIdea]:
    """slug -> (fields, list fields, body) of every 0.15 idea."""
    out: dict[str, OldIdea] = {}
    for slug in old_slugs(store):
        pairs, body = split_frontmatter(textfile.read(os.path.join(store, slug + ".md")) or "")
        fields = {k: v for k, v in pairs if "\n" not in v and v != "[]"}
        lists = {k: [x.strip() for x in v.split("\n") if x.strip() and x.strip() != "[]"]
                 for k, v in pairs if k in dict(FM_KINDS)}
        out[slug] = (fields, lists, body)
    return out


def log_entries(store: str) -> list[tuple[str, str]]:
    """[(label, text)] of the index's Log, as written."""
    text = read_once(os.path.join(store, "index.md")) or ""
    if "\n## Log\n" not in text:
        return []
    out: list[tuple[str, str]] = []
    for chunk in re.split(r"\n(?=- \d{4}-\d{2}-\d{2})", "\n" + text.split("\n## Log\n", 1)[1]):
        match = re.match(r"^- (\d{4}-\d{2}-\d{2})([^:]*):\s*(.*)$", chunk.strip(), re.S)
        if match:
            out.append((match.group(1) + match.group(2), " ".join(match.group(3).split())))
    return out


def restructure_sentences(store: str) -> list[tuple[str, str, list[str]]]:
    """[(label, the entry's first sentence, the other sentences that may
    record a restructure)] of the Log."""
    out: list[tuple[str, str, list[str]]] = []
    for label, text in log_entries(store):
        sentences = re.split(r"(?<=[.;])\s+(?=[A-Z0-9`a-z])", text)
        hits = [s for s in sentences if RESTRUCTURE.search(s)]
        if not hits:
            continue
        head = sentences[0]
        if len(head) > 90:
            head = head[:90].rsplit(" ", 1)[0] + " ..."
        out.append((label, head, [h for h in hits if h != sentences[0]]))
    return out


def plan_lines(root: str) -> list[str]:
    """The migration plan a dry run and start print: the ideas, what
    changes, the backup, the Log sentences that may become events, a fold as
    its merge event, and the sentences that need the user."""
    store = paths(root)[0]
    old = read_old(store)
    open_n = sum(1 for f, _, _ in old.values() if f.get("status") not in CLOSED)
    lines = [
        "The idea store is in the 0.15 layout: index.md and %d idea files, %d open and %d closed."
        % (len(old), open_n, len(old) - open_n),
        "Migration from the 0.15 layout:",
        "- the whole store is first kept untouched as the backup %s/" % BACKUP,
        "- every idea keeps its file in the same folder, its status in its frontmatter; research/ is copied as it is",
        "- index.md and its Log stay in the backup only; each idea gets a ## History from its created date and status",
        "- relations stay where they are stated; links to idea files become slugs, Next Steps included; no idea is "
        "put under a parent",
    ]
    found = restructure_sentences(store)
    slugs = set(old)
    if not found:
        lines.append("The Log names no split, merge or rename.")
        return lines
    lines.append("Log sentences that may record a split, merge or rename (only these can become events):")
    unnamed: list[str] = []
    for label, head, shown in found:
        for sentence in [head] + shown:
            prefix = "  > %s: " % label if sentence is head else "  >   ... "
            lines.append(prefix + sentence)
            read = False
            for a, b in FOLDED.findall(sentence):
                a, b = a.lower(), b.lower()
                if a in slugs and b in slugs and a != b:
                    lines.append("    event: %s %s merged into %s" % (label[:10], a, b))
                    read = True
            if not read and re.search(r"\bfold(?:s|ed)?\b", sentence, re.I):
                unnamed.append("%s: %s" % (label, sentence))
            if re.search(r"\b(split|splits|renamed)\b", sentence, re.I):
                named = [t for t in re.findall(SLUG_RE, sentence.lower()) if t in slugs]
                if len(set(named)) < 2:
                    unnamed.append("%s: %s" % (label, sentence))
    if unnamed:
        lines.append("Needs the user: a split, rename or fold whose ideas the Log does not name:")
        lines += ["  > " + u for u in dict.fromkeys(unnamed)]
    return lines


def ask(root: str) -> str:
    asks = any(line.startswith("Needs the user") for line in plan_lines(root))
    return ("Ask the user once, in your own words, whether to migrate the idea store now: say what the lines above "
            "say will happen and where the backup goes, and list the events you take from the Log sentences above, "
            "only those a sentence states, each as '<YYYY-MM-DD> <slug> split into <slug>[, <slug>]' (or merged "
            "into, renamed from <slug>; a Log 'X folded into Y' is the event 'X merged into Y')."
            + (" For each sentence under Needs the user that records a split, merge or rename of ideas, ask the user "
               "which ideas it names before you list its event; a sentence about something else (a command, a file, "
               "a hook) you pass over, naming it in your ask as passed over." if asks else "")
            + " On their yes run brainstorm migrate with one --event per event and --write. On a no, stop: no other "
              "brainstorm command reads the 0.15 layout.")


def parse_events(values: list[str], slugs: set[str]) -> list[Event]:
    """The --event values as (date, slug, kind, [others]); a Failure naming
    every value that is malformed, has a bad date or names an idea the store
    lacks."""
    events: list[Event] = []
    bad: list[str] = []
    for value in values:
        match = EVENT.match(" ".join(value.split()))
        if not match:
            bad.append("%s: not '<YYYY-MM-DD> <slug> split into|merged into|folded into|renamed from <slug>'%s"
                       % (value, " (a part is filed after the migration, with brainstorm move)"
                          if re.search(r"\bmoved[- ]under\b", value) else ""))
            continue
        date, slug, kind, rest = match.group(1), match.group(2), match.group(3).replace("-", " "), match.group(4)
        if kind == "folded into":
            kind = "merged into"
        others = [o for o in re.split(r"\s*(?:,|\band\b)\s*", rest) if o]
        if not real_date(date):
            bad.append("%s: %s is no date" % (value, date))
        elif date > today():
            bad.append("%s: %s is after today, %s" % (value, date, today()))
        if slug in others:
            bad.append("%s: %s names %s on both sides" % (value, kind, slug))
        if slug not in slugs:
            bad.append("%s: no idea named %s" % (value, slug))
        for other in others:
            if kind != "renamed from" and other not in slugs:
                bad.append("%s: no idea named %s" % (value, other))
        if kind != "split into" and len(others) != 1:
            bad.append("%s: %s names exactly one idea" % (value, kind))
        events.append((date, slug, kind, others))
    if bad:
        raise Failure(["Events refused, nothing was written:"] + ["- " + b for b in bad],
                      "Fix the events above from the Log lines the plan printed, and run migrate again.")
    return events


def convert_links(body: str, slugs: set[str]) -> str:
    """Links to idea files become the slug, Next Steps included: bare on a
    Related Ideas line, a code span elsewhere, so rename finds it again; the
    label stays when it says more than the slug. Other links keep their
    targets."""
    lines = body.split("\n")
    inside = fenced(lines)
    section = [""]

    def fix(match: re.Match[str]) -> str:
        label, target = match.group(1), match.group(2)
        base = target.split("#", 1)[0]
        if base.startswith("./"):
            base = base[2:]
        name = base[:-3] if base.endswith(".md") and "/" not in base else None
        if name not in slugs:
            return match.group(0)
        assert name is not None
        ref = name if section[0] == "Related Ideas" else "`%s`" % name
        plain = label.strip().strip("`")
        return ref if plain in (name, name + ".md") else "%s (%s)" % (label, ref)

    out: list[str] = []
    for i, line in enumerate(lines):
        if not inside[i] and line.startswith("## "):
            section[0] = line[3:].strip()
        out.append(line if inside[i] else LINK.sub(fix, line))
    return "\n".join(out)


def pair(a: str, b: str) -> tuple[str, str]:
    """Two ideas a relation joins, in either direction."""
    return (a, b) if a < b else (b, a)


def build_ideas(old: dict[str, OldIdea], events: list[Event]) -> dict[str, Idea]:
    """slug -> Idea in layout 2, from the 0.15 files and the events."""
    slugs = set(old)
    ideas: dict[str, Idea] = {}
    for slug, (fields, _, body) in old.items():
        ideas[slug] = Idea.frame(slug, slug + ".md", [(k, fields.get(k, "")) for k in
                                                      ("tldr", "status", "importance", "size", "fog", "last-updated")],
                                 [convert_links(body, slugs)])
    # A relation named only in frontmatter becomes one line, on its side: a
    # pair a Related Ideas line already names, under any kind, on either
    # side, is not written again.
    written = {pair(s, t) for s, idea in ideas.items() for _, tokens, _, _ in idea.relation_items()
               for t in tokens if t in slugs}
    for slug, (_, lists, _) in sorted(old.items()):
        for key, kind in FM_KINDS:
            for item in lists.get(key, []):
                target = item[:-3] if item.endswith(".md") else item
                if target not in slugs or target == slug or pair(slug, target) in written:
                    continue
                written.add(pair(slug, target))
                ideas[slug].append("Related Ideas", "%s %s" % (kind, target), item="- ")
    history: dict[str, list[tuple[str, int, str]]] = {s: [] for s in slugs}
    for slug, (fields, _, _) in old.items():
        created = fields.get("created") or fields.get("last-updated") or today()
        history[slug].append((created, 0, "created"))
        status = fields.get("status", "idea")
        if status != "idea":
            history[slug].append((fields.get("last-updated") or created, 2, "status %s" % status))
    for date, slug, kind, others in events:
        if kind == "split into":
            history[slug] += [(date, 1, "split into %s" % o) for o in others]
        elif kind == "merged into":
            history[slug].append((date, 1, "merged into %s" % others[0]))
            history[others[0]].append((date, 1, "merged from %s" % slug))
        else:
            history[slug].append((date, 1, "%s %s" % (kind, others[0])))
    for slug, idea in ideas.items():
        for date, _, event in sorted(history[slug]):
            idea.add_history(event, date)
    return ideas


def build_staging(store: str, staging: str, ideas: dict[str, Idea], old: dict[str, OldIdea]) -> None:
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    os.mkdir(staging)
    for base, dirs, files in os.walk(store):
        dirs.sort()
        rel_base = os.path.relpath(base, store)
        for name in sorted(files):
            if rel_base == "." and (name == "index.md" or (name.endswith(".md") and name[:-3] in old)):
                continue
            target = os.path.join(staging, name) if rel_base == "." else os.path.join(staging, rel_base, name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(os.path.join(base, name), target)
    hashes: dict[str, str] = {}
    for slug, idea in sorted(ideas.items()):
        data = idea.render().encode("utf-8")
        textfile.write(os.path.join(staging, slug + ".md"), data)
        hashes[slug] = ledger_sha(data)
    os.makedirs(os.path.join(staging, STATE), exist_ok=True)
    textfile.write(os.path.join(staging, STATE, LEDGER), ledger_bytes(hashes))
    textfile.write(os.path.join(staging, LAYOUT_FILE), (TO + "\n").encode("ascii"))


def run(root: str, events_raw: list[str], write: bool) -> Result:
    """The step's lines and what happened: "dry", "dry-half", "finished",
    "migrated", or "moved" when another Session took the store past
    layout 1 meanwhile. A write holds the migration lock from the first look
    at the store to the last rename, so a second migration waits for it and
    then finds the store migrated (M2)."""
    if not write:
        return step(root, events_raw, False)
    os.makedirs(os.path.join(root, ".scratch"), exist_ok=True)
    with Lock(root, path=os.path.join(root, LOCK), doing="migrating the idea store") as lock:
        lines, what, would = step(root, events_raw, True)
    return lock.lines + lines, what, would


def step(root: str, events_raw: list[str], write: bool) -> Result:
    store, backup, staging = paths(root)
    where = state(root)
    if where == "half":
        if not write:
            lines = ["A migration was interrupted after the backup: %s/ is complete and %s/ waits beside it."
                     % (BACKUP, STAGING), "migrate --write renames it into place; nothing else changes."]
            return lines, "dry-half", ["%s/ (renamed from %s/)" % (STORE, STAGING)]
        os.rename(staging, store)
        return ["The interrupted migration is finished: the staging became the store."], "finished", []
    if where == "none":
        if os.path.isdir(backup):
            raise Failure("There is no .scratch/_brainstorming/, but a migration's backup is at %s/ with no finished "
                          "new layout beside it." % BACKUP,
                          "Tell the user the store is missing: to go back, rename %s/ to .scratch/_brainstorming/ and "
                          "run brainstorm start again. Stop." % BACKUP)
        raise Failure("This project has no idea store to migrate.", "Answer the user's message; there are no ideas yet.")
    if where == "done":
        return [], "moved", []
    old = read_old(store)
    events = parse_events(events_raw, set(old))
    ideas = build_ideas(old, events)
    if not write:
        lines = plan_lines(root)
        lines.append("Events to carry: %s" % ("; ".join(" ".join([d, s, k, ", ".join(o)]) for d, s, k, o in events)
                                             if events else "none"))
        return lines, "dry", ["%s/ (built, then renamed to %s/)" % (STAGING, STORE),
                              "%s/ (the 0.15 store, renamed)" % BACKUP]
    if os.path.isdir(backup):
        raise Failure("A backup %s/ already exists beside a 0.15 store; nothing was written." % BACKUP,
                      "Tell the user an earlier migration left %s/ behind, and ask them to move it away or delete it "
                      "before migrating; stop." % BACKUP)
    build_staging(store, staging, ideas, old)
    try:
        os.rename(store, backup)
    except OSError as error:
        shutil.rmtree(staging, ignore_errors=True)
        raise Failure("The old store could not be renamed to the backup (%s); it is untouched and nothing was written."
                      % textfile.reason(error),
                      "If a sandbox refused it, rerun the same command once outside the sandbox. Otherwise "
                      "tell the user a file in .scratch/_brainstorming/ is held open (an editor?), ask them "
                      "to close it, and run the command again.")
    try:
        os.rename(staging, store)
    except OSError as error:
        raise Failure("The new store could not be renamed into place (%s). The backup is complete; the staging waits "
                      "in %s/." % (textfile.reason(error), STAGING),
                      "Run brainstorm migrate --write again: it finishes the swap.")
    open_n = sum(1 for i in ideas.values() if i.is_open)
    return ["Migrated %d ideas to layout %s: %d open, %d closed, each in its own file as before; %d events from the "
            "Log carried." % (len(ideas), TO, open_n, len(ideas) - open_n, len(events))], "migrated", []

