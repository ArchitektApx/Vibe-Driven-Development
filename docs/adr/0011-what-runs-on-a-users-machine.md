# What runs on a user's machine

Nothing the plugin ships runs on an installer's machine unless a Role calls
it through a named interpreter or the user trusted it hook by hook, so
everything that runs is something the user can see in an approval prompt or
a hook list. The one hook is Codex's `Stop` hook. The plugin ships no MCP
server, no symlink and no executable file, and its code opens no network
connection, starts no shell and evaluates no text. CI checks these on every
pull request; Python can hide a call in more ways than a static check
follows, so review covers the rest.

## Considered options

**No hooks at all.** Rejected: a background shell cannot wake a Codex
Session, so every Codex Doorbell would need a paste.

**Hooks on the other Harnesses.** Rejected: they run a plugin's hooks without
asking per hook, and a background shell wakes them anyway.
