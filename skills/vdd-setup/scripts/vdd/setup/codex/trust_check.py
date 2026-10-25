"""Whether Codex trusts VDD's hook: each vdd@<marketplace> entry in
config.toml checked against the installed copy, hashed as Codex hashes it,
and the report lines and Tell lines Setup prints for it."""

from __future__ import annotations

import os

from ... import stores, textfile
from ..report import Report
from . import baseline, fingerprint, installed, trust

NOT_TRUSTED_WAIT = "Trust VDD's hook in /hooks, then say so here, or say skip."
CHANGED_WAIT = "VDD changed since you trusted its hook. Trust it again in /hooks, then say so here, or say skip."
COULD_NOT_VERIFY = ("Setup could not verify that Codex trusts VDD's hook. If /hooks lists it for review, "
                    "trust it there.")
SKIPPED = "VDD's hook is not trusted: every Doorbell waits for you to paste it."
SWITCHED_OFF = "VDD's hook is switched off in Codex: turn it on in /hooks, or every Doorbell waits for a paste."

TRUSTED = "trusted"
CHANGED = "changed"
NOT_TRUSTED = "not trusted"
OFF = "switched off"
UNVERIFIED = "could not verify"


class Check:
    """One run's trust check: the Codex home, config.toml, how the report
    shows paths, and answer, the user's --hook-answer: trusted or skip after
    Setup asked them to trust the hook, or None."""

    def __init__(self, report: Report, home: str, cwd: str, answer: str | None) -> None:
        self.report = report
        self.answer = answer
        self.home = home
        self.cwd = cwd
        self.config = os.path.join(home, "config.toml")
        self.config_label = self.shown(self.config)
        self.states: list[str] = []

    def shown(self, path: str) -> str:
        return stores.display(path, self.cwd)

    def run(self, text: str | None) -> None:
        found = trust.entries(text)
        if isinstance(found, str):
            why = "could not be read" if found == trust.UNREADABLE else "was read but not understood"
            self.unverified("VDD's Codex hook", "%s %s" % (self.config_label, why))
        elif not found:
            self.waiting(NOT_TRUSTED, "VDD's Codex hook", "not trusted, %s has no entry for it" % self.config_label,
                         "%s still has no entry for it" % self.config_label)
        else:
            for entry in found:
                label = "VDD's Codex hook" if len(found) == 1 else "VDD's Codex hook for vdd@%s" % entry.marketplace
                self.entry(entry, label)
        self.tells()

    def entry(self, entry: trust.Entry, label: str) -> None:
        if entry.enabled is False:
            self.line(OFF, "%s: switched off, %s says enabled = false for it." % (label, self.config_label))
            return
        if entry.trusted_hash is None:
            self.waiting(NOT_TRUSTED, label, "not trusted, %s holds no approval for it" % self.config_label,
                         "%s still holds no approval for it" % self.config_label)
            return
        trusted = entry.trusted_content_hash
        if trusted is None:
            legacy = baseline.path(self.home, entry.marketplace)
            try:
                pinned = baseline.read(legacy)
            except OSError as error:
                self.unverified(label, "the baseline of an approval from before Codex 0.164, %s, could not be read "
                                "(%s)" % (self.shown(legacy), textfile.reason(error)))
                return
            if pinned is None:
                self.unverified(label, "%s holds an approval from before Codex 0.164 and its baseline %s is missing"
                                % (self.config_label, self.shown(legacy)))
                return
            trusted = pinned.decode("utf-8", "surrogateescape")
        copy = installed.find(self.home, entry.marketplace)
        if copy.root is None and copy.candidates:
            self.unverified(label, "%s holds versions whose order Codex does not fix: %s"
                            % (self.shown(copy.directory), ", ".join(copy.candidates)))
            return
        if copy.root is None:
            self.unverified(label, "no installed copy at %s" % self.shown(copy.directory))
            return
        root = self.shown(copy.root)
        try:
            current = fingerprint.content_hash(copy.root)
        except fingerprint.Unhashable as error:
            self.unverified(label, unhashable(root, error))
            return
        if current == trusted:
            self.line(TRUSTED, "%s: trusted, the installed copy at %s is the one you trusted. Passed." % (label, root))
        else:
            self.waiting(CHANGED, label, "changed, the installed copy at %s differs from the one you trusted" % root,
                         "the installed copy at %s still differs from the one you trusted" % root)

    def line(self, state: str, text: str) -> None:
        """A run with the user's answer is the recheck, so its verdict prints
        even when the Role kept --write."""
        self.states.append(state)
        self.report.out.line(text, on_write=self.answer is not None)

    def waiting(self, state: str, label: str, verdict: str, still: str) -> None:
        """A verdict that asks the user to trust the hook in /hooks; after they
        said they did, one Setup could not verify."""
        if self.answer == "trusted":
            self.unverified(label, still)
        else:
            self.line(state, "%s: %s." % (label, verdict))

    def unverified(self, label: str, cause: str) -> None:
        self.line(UNVERIFIED, "%s: could not verify, %s." % (label, cause))

    def tells(self) -> None:
        out = self.report.out
        if OFF in self.states:
            out.tell(SWITCHED_OFF)
        if UNVERIFIED in self.states:
            out.tell(COULD_NOT_VERIFY)
        if CHANGED not in self.states and NOT_TRUSTED not in self.states:
            return
        if self.answer == "skip":
            out.tell(SKIPPED)
        else:
            self.report.hook_wait = CHANGED_WAIT if CHANGED in self.states else NOT_TRUSTED_WAIT


def unhashable(root: str, error: fingerprint.Unhashable) -> str:
    if error.kind == fingerprint.UNREADABLE:
        why = "it could not be read (%s)" % textfile.reason(error.error or OSError())
    elif error.kind == fingerprint.RESIZED:
        why = "it changed size while Setup read it"
    else:
        why = "it is not a plain file or directory"
    return "the installed copy at %s holds an entry Setup cannot hash, %s: %s" % (root, error.relative, why)


def check(report: Report, home: str, cwd: str, text: str | None, answer: str | None) -> None:
    """Report the trust of every VDD hook entry in config.toml, whose text
    trust.read() gave, and set the report's hook_wait when the user has to
    trust the hook in /hooks; Setup's finish asks them."""
    Check(report, home, cwd, answer).run(text)
