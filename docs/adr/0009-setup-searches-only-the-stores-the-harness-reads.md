# Setup searches only the stores the Harness reads

Setup counts a Borrowed skill as Present only when it sits in a store the
current Harness reads, because a skill in another Harness's store is one this
Harness never loads. A collection in `~/.claude/skills` is therefore Not
Present on Copilot CLI, and one in `~/.agents/skills` with no link in a
Claude Code store is Not Present on Claude Code, where a search across every
store would report both installs as healthy. Generic searches the union of
every Harness's stores, since nobody knows which ones it reads.

Cursor searches no `.claude` or `.codex` store. The Cursor IDE reads them only
through its third-party import, which the user can turn off, and Setup cannot
read that setting: no shell tells the IDE's Agent from the Cursor CLI, and the
CLI ignores it.

A skill the Session can run still passes when the search finds it nowhere,
with a line saying so, because a Harness also reads stores the search leaves
out, such as Claude Code's enterprise store, and a skill the user can run is
not a failure.
