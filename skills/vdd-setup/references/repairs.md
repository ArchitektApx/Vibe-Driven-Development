# Repairing a Borrowed-skills failure

## Present but not Resolvable

The install already happened, so the repair is wiring, and where you found the
file names the route:

- Found under `~/.claude/plugins/cache/`: the Claude Code plugin put it there,
  so the repair belongs on the plugin side. Tell the user to reinstall or
  re-enable `mattpocock-skills`.
- Found under an `.agents/skills/` or `.claude/skills/` store: the skills CLI
  put it there. Tell the user to re-run `npx skills@latest add
  mattpocock/skills` and to select this agent.

## Not Present

Tell the user to install it, taking the whole collection: `/plugin install
mattpocock-skills` in Claude Code's official marketplace, or
`npx skills@latest add mattpocock/skills` in other agents.

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
- Found under an `.agents/skills/` or `.claude/skills/` store:
  `npx skills update`.
