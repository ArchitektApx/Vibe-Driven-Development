# Repairing a Borrowed-skills failure

## Present but not Resolvable

The install already happened, so the repair is wiring, and where you found the
file names the route:

- Found under `~/.claude/plugins/cache/`: the Claude Code plugin put it there,
  so the repair belongs on the plugin side. Tell the user to reinstall or
  re-enable `mattpocock-skills`.
- Found under `~/.codex/plugins/cache/`: a Codex plugin put it there, so the
  repair belongs on the Codex plugin side. Tell the user to reinstall or
  re-enable that plugin in Codex, then start a new Codex Session.
- Found under an `.agents/skills/` or `.claude/skills/` store: the skills CLI
  put it there. Tell the user to re-run the install and to select this agent,
  in the scope of the store the files sit in, because the skills CLI's `-g`
  acts on global skills only:
  - Under `~/.agents/skills/` or `~/.claude/skills/`:
    `npx skills@latest add -g mattpocock/skills`.
  - Under `./.agents/skills/` or `./.claude/skills/`:
    `npx skills@latest add mattpocock/skills`, with no `-g`.

## Not Present

Tell the user to install it, taking the whole collection. A skills-CLI route
installs globally, with `-g`, so the collection is installed once for the user
and not into each repository. The route depends on the Harness:

- **Claude Code.** `/plugin install mattpocock-skills` from Claude Code's
  official marketplace.
- **Codex.** `npx skills@latest add -g mattpocock/skills`, selecting Codex when
  the installer asks which agents to install for, then start a new Codex
  Session: a skill added while a Session runs appears only in a new one.
- **Cursor.** `npx skills@latest add -g mattpocock/skills`, selecting Cursor
  when the installer asks which agents to install for, then open a new chat or
  a new `agent` Session before rerunning this check.
- **Copilot CLI.** `npx skills@latest add -g mattpocock/skills`, selecting
  GitHub Copilot when the installer asks which agents to install for, then run
  `/skills reload` or start a new `copilot` Session before rerunning this
  check: a skill added while a Session runs is not picked up without one of
  the two.
- **Generic.** `npx skills@latest add -g mattpocock/skills`, selecting their
  agent when the installer asks.

## A collection that predates `writing-for-agents`

`writing-for-agents` shipped after the six the Roles borrowed before it, so a
user who installed the collection earlier has those six Present and this one
absent. Say that the installed collection predates the skill, and give the
update route for the store the six were found in:

- Found under `~/.claude/plugins/cache/`: `claude plugin marketplace update
  <marketplace>` then `claude plugin update mattpocock-skills`.
  `<marketplace>` is the first directory under `~/.claude/plugins/cache/` on
  the path the six were found at, which is the marketplace name, not the plugin
  name below it. In a Claude Code session the marketplace half is
  `/plugin marketplace update <marketplace>`.
- Found under an `.agents/skills/` or `.claude/skills/` store, in the scope of
  the store the six sit in:
  - Under `~/.agents/skills/` or `~/.claude/skills/`: `npx skills update -g`.
  - Under `./.agents/skills/` or `./.claude/skills/`: `npx skills update -p`.
