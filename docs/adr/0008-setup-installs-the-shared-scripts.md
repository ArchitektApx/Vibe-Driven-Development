# Setup installs the shared scripts and registers the Codex hook

The plugin's install path changes with every version and differs per Harness,
so a command pointing into it breaks on the next update. Setup therefore
copies the shipped scripts into a shared directory, `$XDG_DATA_HOME/vdd/` or
`~/.local/share/vdd/` on macOS and Linux and `%LOCALAPPDATA%\vdd\` on
Windows, and on Codex registers the `Stop` hook in the user's own
`~/.codex/hooks.json`. Every Role runs the copy by its plain absolute path.

Setup does both as a standard check without an opt-in question, because it
runs at the start of every Loop and has nowhere to store a decline: it shows
the user what it will write, and the user's permission mode raises any prompt
the write needs. A registration already present is left exactly as it is.

The registration stays in `hooks.json` until the user deletes it, so it can
outlive its script, and the entry stays silent when the script is missing.
Codex reads a `Stop` hook that exits 2 as a block and repeats it without
limit, and dash exits 2 on a missing script, so an unguarded stale
registration would loop every Codex Session.

## Considered options

**A hook declared in the plugin's `hooks/hooks.json`.** Rejected: the plugin
supports Windows and macOS and Linux, so it would declare both forms of the
hook, and one of them would always fail on the other platform.
