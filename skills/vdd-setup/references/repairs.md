# Repairing a Borrowed-skills failure

Read the section for your Harness, or the Generic section on Generic, and in
it the route for the store the files were found in. The path the search
printed names the store. A store that a variable relocated takes the route of
the store it replaces. On native Windows a `~/` path below reads as
`%USERPROFILE%\` and each `/` as `\`, so match a path the PowerShell search
printed to its store that way.

Each section covers three cases:

- **Present but not Resolvable.** The files sit in a store this Harness
  reads, and this Session has not loaded them. The install already happened,
  so the repair gets this Session to load them.
- **Not Present.** Tell the user to install it, taking the whole collection.
  A skills-CLI route installs globally, with `-g`, so the collection is
  installed once for the user and not into each repository.
- **A collection that predates `writing-for-agents`.** `writing-for-agents`
  shipped after the six the Roles borrowed before it, so a user who installed
  the collection earlier has those six Present and this one absent. Say that
  the installed collection predates the skill, and give the update route for
  the store the six were found in.

A store is one of two kinds. A plugin cache is a root a Harness installs
plugins into: `~/.claude/plugins/cache`, `~/.codex/plugins/cache`,
`~/.cursor/plugins/cache` or `~/.copilot/installed-plugins`. Every other root
is a skill store, where the skills CLI writes. A skills-CLI command acts in
the scope of the store the files sit in, because the skills CLI's `-g` acts on
global skills only: with `-g` for a store under `~`, and with no `-g` for a
store under `./`.

## Claude Code

### Present but not Resolvable

- Under `~/.claude/plugins/cache/`: the Claude Code plugin put it there, so
  the repair belongs on the plugin side. Tell the user to run
  `claude plugin enable mattpocock-skills@<marketplace>` from the repository
  root, then start a new Claude Code Session. It finds the scope that holds
  the disable, a project's `.claude/settings.local.json` included.
  `<marketplace>` is read off the path as in the update route below. If the
  plugin is enabled and still not loaded, tell the user to reinstall it.
- Under `~/.claude/skills/` or `./.claude/skills/`: the skills CLI put it
  there. Tell the user to re-run the install and to select Claude Code, in the
  scope of the store the files sit in:
  - Under `~/.claude/skills/`: `npx skills@latest add -g mattpocock/skills`.
  - Under `./.claude/skills/`: `npx skills@latest add mattpocock/skills`,
    with no `-g`.

### Not Present

`/plugin install mattpocock-skills` from Claude Code's official marketplace.

### A collection that predates `writing-for-agents`

- Under `~/.claude/plugins/cache/`: `claude plugin marketplace update
  <marketplace>` then `claude plugin update mattpocock-skills`.
  `<marketplace>` is the first directory under `~/.claude/plugins/cache/` on
  the path the six were found at, which is the marketplace name, not the
  plugin name below it. In a Claude Code session the marketplace half is
  `/plugin marketplace update <marketplace>`.
- Under `~/.claude/skills/`: `npx skills update -g`.
- Under `./.claude/skills/`: `npx skills update -p`.

## Codex

### Present but not Resolvable

- Under `~/.agents/skills/`, `./.agents/skills/`, `~/.codex/skills/` or
  `./.codex/skills/`: first tell the user to start a new Codex Session, because
  a skill added while a Session runs appears only in a new one. If the new
  Session still cannot run it, tell the user to re-run the install, select
  Codex, and start a new Codex Session after it:
  - Under `~`: `npx skills@latest add -g mattpocock/skills`.
  - Under `./`: `npx skills@latest add mattpocock/skills`, with no `-g`.
- Under `~/.codex/plugins/cache/`: a Codex plugin put it there. Tell the user
  to run `codex plugin add <plugin>@<marketplace>`, then start a new Codex
  Session. On the path the files were found at, `<marketplace>` is the first
  directory under `~/.codex/plugins/cache/` and `<plugin>` the second.

### Not Present

`npx skills@latest add -g mattpocock/skills`, selecting Codex when the
installer asks which agents to install for, then start a new Codex Session: a
skill added while a Session runs appears only in a new one.

### A collection that predates `writing-for-agents`

- Under `~/.codex/plugins/cache/`: `codex plugin marketplace upgrade
  <marketplace>`, then `codex plugin add <plugin>@<marketplace>` and a new
  Codex Session, with both names read off the path as above.
- Under a skill store in `~`: `npx skills update -g`.
- Under a skill store in `./`: `npx skills update -p`.

## Cursor

### Present but not Resolvable

- Under `~/.agents/skills/`, `./.agents/skills/`, `~/.cursor/skills/` or
  `./.cursor/skills/`: first tell the user to open a new chat or a new `agent`
  Session. If that still cannot run it, tell the user to re-run the install,
  select Cursor, and open a new chat or `agent` Session after it:
  - Under `~`: `npx skills@latest add -g mattpocock/skills`.
  - Under `./`: `npx skills@latest add mattpocock/skills`, with no `-g`.
- Under `~/.cursor/plugins/cache/`: a Cursor plugin put it there. Tell the
  user to reinstall the plugin in the Cursor IDE's plugin UI, then open a new
  chat or `agent` Session. Cursor has no command-line route for this.

### Not Present

`npx skills@latest add -g mattpocock/skills`, selecting Cursor when the
installer asks which agents to install for, then open a new chat or a new
`agent` Session before rerunning this check.

### A collection that predates `writing-for-agents`

- Under `~/.cursor/plugins/cache/`: refresh the plugin in the Cursor IDE's
  plugin UI.
- Under a skill store in `~`: `npx skills update -g`.
- Under a skill store in `./`: `npx skills update -p`.

## Copilot CLI

### Present but not Resolvable

- Under `~/.agents/skills/`, `./.agents/skills/`, `~/.copilot/skills/`,
  `./.github/skills/` or `./.claude/skills/`: first tell the user to run
  `/skills reload` or start a new `copilot` Session. If that still cannot run
  it, tell the user to re-run the install, select GitHub Copilot, and reload
  after it the same way:
  - Under `~`: `npx skills@latest add -g mattpocock/skills`.
  - Under `./`: `npx skills@latest add mattpocock/skills`, with no `-g`.

  With `COPILOT_HOME` set, the `-g` re-run writes `~/.agents/skills`, which
  Copilot CLI does not read while `COPILOT_HOME` is set. Follow it with
  `copilot skill add ~/.agents/skills`, in PowerShell
  `copilot skill add "$env:USERPROFILE\.agents\skills"`, then
  `/skills reload` or a new `copilot` Session. PowerShell does not expand `~`
  for a program it runs, so the path goes in expanded.
- Under `~/.copilot/installed-plugins/`: a Copilot CLI plugin put it there.
  Tell the user to re-enable it, then start a new `copilot` Session:
  - Under `~/.copilot/installed-plugins/<marketplace>/<plugin>/`, a
    marketplace install: `copilot plugin enable <plugin>@<marketplace>`.
  - Under `~/.copilot/installed-plugins/_direct/<source-id>/`, a direct
    install: `copilot plugin enable <source-id>`.

  Read `<marketplace>`, `<plugin>` and `<source-id>` off the path the files
  were found at, in the positions shown.

### Not Present

`npx skills@latest add -g mattpocock/skills`, selecting GitHub Copilot when
the installer asks which agents to install for. With `COPILOT_HOME` set, then
run `copilot skill add ~/.agents/skills`, in PowerShell
`copilot skill add "$env:USERPROFILE\.agents\skills"`, because Copilot CLI
does not read that store while `COPILOT_HOME` is set. Then run `/skills reload` or start a
new `copilot` Session before rerunning this check: a skill added while a
Session runs is not picked up without one of the two.

### A collection that predates `writing-for-agents`

- Under `~/.copilot/installed-plugins/<marketplace>/<plugin>/`:
  `copilot plugin update <plugin>@<marketplace>`.
- Under `~/.copilot/installed-plugins/_direct/<source-id>/`:
  `copilot plugin update <plugin>`, where `<plugin>` is the bare plugin name
  `copilot plugin list` shows, not the source id on the path.
- Under a skill store in `~`: `npx skills update -g`.
- Under a skill store in `./`: `npx skills update -p`.

## Generic

### Present but not Resolvable

- Under a plugin cache: give the re-enable route from the section of the
  Harness that owns that cache.
- Under a skill store: the skills CLI put it there. Tell the user to re-run
  the install and to select their agent, in the scope of the store the files
  sit in:
  - Under `~`: `npx skills@latest add -g mattpocock/skills`.
  - Under `./`: `npx skills@latest add mattpocock/skills`, with no `-g`.

### Not Present

`npx skills@latest add -g mattpocock/skills`, selecting their agent when the
installer asks.

### A collection that predates `writing-for-agents`

- Under a plugin cache: give the update route from the section of the
  Harness that owns that cache.
- Under a skill store in `~`: `npx skills update -g`.
- Under a skill store in `./`: `npx skills update -p`.
