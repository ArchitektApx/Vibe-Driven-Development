"""The duplicate check: the ideas, open, closed or removed, that look like a
new one. It lists, never refuses: the model asks the user whether the new
idea is one of them."""

from __future__ import annotations

import re
from typing import Iterable, NamedTuple

from .store import Store, removed_entries, removed_reopen

# The share of one field's words a new idea must repeat to be listed as a
# likely match: the check's one knob.
SIMILARITY_THRESHOLD = 0.5
STOP = set("""a an and are as at be been but by can could did do does for from had has have how i if in into is it its
it's itself just may might more most no not of on once one only or other our out over own per same should so some such
than that the their them then there these they this those through to too under up very was we were what when where which
while who why will with would you your also new idea ideas let lets we're can't""".split())
# Scripts written without spaces between words (CJK ideographs, kana,
# Hangul): a run of them is compared as its character pairs.
UNSPACED = re.compile("[\u2e80-\u9fff\uac00-\ud7af\uf900-\ufaff]")
# The least number of shared words a field needs, or all of its words when
# it has fewer: a one-word title still matches.
FLOORS = (("reopen", 2), ("name", 2), ("tldr", 3))


class Match(NamedTuple):
    cover: float
    slug: str
    shared: list[str]
    where: str


def stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[:-len(suffix)]
    return word


def terms(text: str | None) -> list[str]:
    """The words the check compares: Unicode words of three letters or more,
    English stop words left out and English plurals and tenses cut; a run of
    an unspaced script as its character pairs."""
    out: list[str] = []
    for word in re.findall(r"\w+", (text or "").lower()):
        if UNSPACED.search(word):
            out.extend([word[i:i + 2] for i in range(len(word) - 1)] or [word])
        elif len(word) > 2 and word not in STOP:
            out.append(stem(word) if all(ord(c) < 128 for c in word) else word)
    return out


def candidates(store: Store) -> Iterable[tuple[str, dict[str, str], str]]:
    """(slug, fields, where) of every idea and removed idea: fields are the
    texts compared, where is "open", "closed" or "removed"."""
    for slug, idea in sorted(store.ideas.items()):
        fields = {"reopen": "" if idea.is_open else idea.reopen_when(),
                  "name": slug.replace("-", " ") + " " + idea.title, "tldr": idea.tldr}
        yield slug, fields, "open" if idea.is_open else "closed"
    for entry in removed_entries(store.root):
        if entry["slug"] not in store.ideas:
            fields = {"reopen": removed_reopen(entry), "name": entry["slug"].replace("-", " ") + " " + entry["title"],
                      "tldr": entry["gist"]}
            yield entry["slug"], fields, "removed"


def similar(store: Store, text: str, exclude: Iterable[str] = ()) -> list[Match]:
    """The ideas that look like text, best first. A field matches when the
    new text repeats its floor of words and SIMILARITY_THRESHOLD of them;
    cover is the best field's share."""
    words = set(terms(text))
    left_out = set(exclude)
    out: list[Match] = []
    for slug, fields, where in candidates(store):
        if slug in left_out:
            continue
        best, shared = 0.0, []
        for key, least in FLOORS:
            field = set(terms(fields[key]))
            hit = words & field
            if field and len(hit) >= min(least, len(field)):
                cover = len(hit) / float(len(field))
                if cover > best:
                    best, shared = cover, sorted(hit)
        if best >= SIMILARITY_THRESHOLD:
            out.append(Match(best, slug, shared, where))
    out.sort(key=lambda m: (-m.cover, m.slug))
    return out
