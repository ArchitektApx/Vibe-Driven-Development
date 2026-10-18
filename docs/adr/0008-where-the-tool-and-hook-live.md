# Where the VDD tool and the Codex hook live

The plugin's install path changes with every version and differs per
Harness, so Setup copies the VDD tool into a Shared directory outside it, and
Roles run that copy. Setup does this at every loop start without asking,
after showing what it writes, because it has nowhere to keep a decline.

The Codex `Stop` hook ships inline in `.codex-plugin/plugin.json`, a manifest
only Codex reads. Codex asks the user to trust it once and keeps that trust
across updates, and the hook leaves with the plugin. It exits 0 on every
path, because Codex reads exit 2, Python's code for a missing script, as a
block it repeats. Setup removes the entry an older VDD wrote into
`~/.codex/hooks.json`, so two hooks never race for one wake.

## Considered options

**Setup registering the hook in `~/.codex/hooks.json`.** Rejected: the entry
outlived its script, a second one raced the first, and the model built the
entry itself instead of copying it.

**A hook in `hooks/hooks.json` or a root `plugin.json`.** Rejected: the other
Harnesses read those too and run their hooks without asking.

**Roles running the tool from the plugin root.** Rejected: only Claude Code
substitutes the root into skill text, and Codex deletes an old version's
directory under a running Session.

**A copy in the project.** Rejected: a relative allow rule for it would run
whatever file a cloned repository ships at that path, and an absolute one is
a rule per project.
