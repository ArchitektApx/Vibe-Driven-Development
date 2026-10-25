# Changelog

All notable changes to Vibe Driven Development are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

**TL;DR:** VDD's routine work, such as Setup, the Doorbells and the review
files, now runs in the VDD tool, a Python program that ships with the plugin
and does the same thing on every run. Shaped by 2,700 past sessions and
hundreds of test runs across every supported agent and several models on
each, 0.16 cuts what the Roles read by up to 80%, and by about 45% over a
whole loop, all while working better than ever, even on low-tier models.
Every loop now ends with a recap and a tidy branch with one commit per
ticket, and you can send your own findings back after Sign-off. The
Brainstormer keeps one file per idea. VDD now needs Python 3.9 and git 2.40
or newer.

### Migrating from 0.15

1. **Install Python 3.9 or newer and git 2.40 or newer** if your machine
   lacks them. Setup checks both and tells you what is missing. On a Mac,
   the Command Line Tools bring both, though an older Xcode brings an older
   git. On Windows, VDD runs Python as `py -3`, which every python.org
   install provides.
2. **On Codex, trust VDD's hook in `/hooks` when Setup asks.** The hook now
   ships with the plugin, and Setup moves you off the 0.15 one. Codex asks
   again after every update, because the plugin you trusted has changed.
3. **Finish or restart a loop in flight.** VDD no longer reads `LOOP.md` at
   the repository root, and every Role stops while it is there. Delete it,
   then run `/vdd:vdd-start-loop` with the loop's slug and answer continue.
4. **Say yes when the Brainstormer offers to convert your idea store.** It
   explains the change before writing anything and first keeps your whole
   store as a backup in `.scratch/_brainstorming.pre-0.16/`. To undo it,
   delete the new `.scratch/_brainstorming/`, rename the backup back, and
   use a 0.15 plugin. Until you say yes, the Brainstormer cannot work on the
   old store.
5. **Optionally, delete the old scripts** `doorbell-wait.*` and
   `vdd-codex-stop.*` in `~/.local/share/vdd/` (`%LOCALAPPDATA%\vdd\` on
   Windows) once no loop on an older VDD is running.

### Added

- **A recap of every loop.** `.scratch/<slug>/RECAP.md` lists the rounds,
  the tickets, every closed finding with how it was fixed, and the final
  commits.
- **A tidy branch at every Sign-off.** VDD folds each later fix into the
  commit it fixes, so the branch reads as one commit per ticket. A branch
  that was already pushed stays as it is, and VDD tells you why.
- **Your own findings after Sign-off.** Write them in a file and run
  `review add`: the loop opens again, a fresh Coder fixes them and the
  Code-Reviewer checks the fixes. [The workflow page](docs/VDD-WORKFLOW.md)
  shows how.
- **Ideas with parts.** Split, nest, merge or rename ideas, up to three
  levels deep. Before a new idea is written, the Brainstormer shows you
  similar ones.
- **Clean up old ideas.** The Brainstormer removes done or dropped ideas on
  your yes and keeps a one-line record of each.
- **From idea to loop.** When you agree on an idea, the Brainstormer gives
  you the line to start a loop or the Wayfinder with it.
- **Setup checks Codex's trust in VDD's hook.** After an update Codex stops
  running the hook until you trust it again, and Setup asks you to.
- **The Coder cannot forget a new file.** VDD refuses a round that leaves a
  new file uncommitted, and names it.

### Changed

- **Setup and the Doorbells run in the VDD tool.** Setup shows what it will
  change before it changes anything, and a Doorbell is acted on once, even
  after a restart.
- **Roles stay on track.** The skills are shorter, and after every step the
  VDD tool tells the Role its exact next step and what to tell you.
- **The Brainstormer keeps one file per idea,** each with a history of what
  happened to it, and no index. It now needs `/vdd:vdd-setup` once per
  machine.
- **The Coder's restarts suit your agent.** The Orchestrator asks once per
  loop whether the Coder starts fresh each round, and recommends the
  cheapest choice for your agent. Start-Loop no longer asks.
- **Review files list only what is still open,** and a later code round is
  reviewed on its own fixes.
- **A restarted Orchestrator picks up where the loop stood.** Say "pause"
  between rounds and it stops before the next step.
- **Each loop keeps its settings in its own folder,** `.scratch/<slug>/`, so
  two loops never mix them up and nothing is left to delete afterwards.
- **Every loop starts with `/vdd:vdd-start-loop`.** The other Roles stop when
  started by hand, except the PR-Author after Sign-off.
- **The Planner asks for the problem** when you bring none.
  `improve-codebase-architecture` and `codebase-design` are no longer
  required.
- **Commits follow your repository's style** and no longer carry
  `Ticket NN`.
- **The plan is fixed once it signs off.** A later change goes in with
  `review add`.
- **VDD opens the PR itself** after you confirm the title and body, and asks
  only what your `PR:` answer left open.
- **The Wayfinder finds Matt Pocock's `wayfinder` for you** on every agent.

### Fixed

- **Roles on Codex carried their parent's conversation.** Codex starts a
  subagent with a copy of its parent's whole conversation unless told
  otherwise, so every Role the Orchestrator started saw context that was not
  its own: reviews were less independent and cost more
  ([mattpocock/skills#1257](https://github.com/mattpocock/skills/issues/1257)).
  Each Role now starts from its own instructions alone.
- **Late or polled code reviews on Claude Code.** The Code-Reviewer's two
  review passes sometimes reported late, or it spent tokens checking on them.
- **PR titles with quotes.** A title with a double quote or an apostrophe now
  reaches GitHub exactly as you confirmed it, on Windows too.
- **A blocked PR history.** A sandbox that kept VDD from reading your past
  PRs no longer looks like a repository without any.

### If you used a 0.16 beta

Skip this when you update from 0.15.

- **A loop started on 0.16.0-beta.3** cannot continue. Move it aside with the
  command the Role prints and start it again.
- **A loop started on an earlier beta** finishes without the tidy branch.
- **An idea store an earlier beta wrote** is updated in your next
  Brainstormer session.
- **Many fixes to the betas' new parts:** the idea store, the fold,
  `review add`, the PR step, Setup and the Codex wait. An unexpected error
  now ends with what to do instead of a Python traceback.

## [0.15.0] - 2026-10-07

**TL;DR:** Automatic Doorbells on every supported agent, native Windows
support, fewer tokens per session, and bug fixes for Claude Code, Codex and
Copilot CLI. Needs Matt Pocock's skills v1.3.1 or later; see the migration
steps below.

### Migrating from 0.14

VDD 0.15 needs Matt Pocock's skills
[v1.3.1](https://github.com/mattpocock/skills/releases/tag/v1.3.1) or later,
which rename the glossary `CONTEXT.md` to `GLOSSARY.md`
([#1120](https://github.com/mattpocock/skills/pull/1120)) but do not migrate
a repository set up on an earlier version
([#1176](https://github.com/mattpocock/skills/issues/1176)).

1. **Update Matt Pocock's skills.** In Claude Code, move from the official
   marketplace, which still ships an older version, to Matt Pocock's own, and
   turn on auto-update for `mattpocock` under `/plugin` > Marketplaces:

   ```
   claude plugin uninstall mattpocock-skills@claude-plugins-official
   claude plugin marketplace add mattpocock/skills
   claude plugin install mattpocock-skills@mattpocock
   ```

   On other agents, run `npx skills update -g`, or `-p` for a project install.
2. **Run `/vdd:vdd-setup` in each repository, or just start your next loop**,
   which runs it for you. Setup checks whether your installed skills are
   older than v1.3.1 and whether the repository still uses `CONTEXT.md` or
   `CONTEXT-MAP.md`, and tells you exactly what to change: the `git mv`
   commands for your glossary files and the two files that name them. Neither
   check stops the loop, so you can migrate when it suits you.

### Added

- **Native Windows.** Every Role runs on Windows, in Windows PowerShell 5.1
  and PowerShell 7.
- **Automatic Doorbells on every supported agent.** In Claude Code, Codex,
  Cursor and GitHub Copilot CLI the Planner and the Orchestrator wait for each
  other's Doorbell and react to it on their own.
- **A Doorbell hook for Codex.** Codex cannot wake a session when a background
  command finishes, so a Role waiting for a Doorbell would have to check again
  and again, and every check costs tokens. Setup installs a hook that holds
  the waiting session until the Doorbell arrives, at no token cost. Trust it
  in `/hooks` when Setup asks; the README says how to remove it.
- **Setup helps you migrate.** It notices skills older than v1.3.1 or a
  repository still on `CONTEXT.md`, and tells you what to change.
- **This changelog, and a GitHub release for every version.**

### Changed

- **Starting Codex.** VDD recommends starting Codex with `codex --no-daemon`,
  and resuming with `codex resume --no-daemon`. Plain `codex` keeps a session
  running in a background server after you quit, so a quit Orchestrator would
  keep its Roles working and spending tokens you do not see. Apps that run
  Codex on their own server, such as T3 Code, stop the session when you close
  it and need no flag.
- **Matt Pocock's marketplace in Claude Code.** Install his skills from his
  own marketplace with auto-update on; the official marketplace still ships
  an older version.
- **Setup checks every skill VDD relies on.** Besides the skills the Roles call
  themselves, it now checks the four those skills call in turn:
  `domain-modeling`, `codebase-design`, `research` and `prototype`. A missing
  one shows up in Setup instead of halfway through planning.
- **Two small scripts outside your repository.** Setup copies the Doorbell
  wait ([`doorbell-wait.sh`](https://github.com/ArchitektApx/Vibe-Driven-Development/blob/master/skills/vdd-setup/references/doorbell-wait.sh),
  [`doorbell-wait.ps1`](https://github.com/ArchitektApx/Vibe-Driven-Development/blob/master/skills/vdd-setup/references/doorbell-wait.ps1)) and the Codex hook
  ([`vdd-codex-stop.sh`](https://github.com/ArchitektApx/Vibe-Driven-Development/blob/master/skills/vdd-setup/references/vdd-codex-stop.sh),
  [`vdd-codex-stop.ps1`](https://github.com/ArchitektApx/Vibe-Driven-Development/blob/master/skills/vdd-setup/references/vdd-codex-stop.ps1)) to `~/.local/share/vdd/`
  (`%LOCALAPPDATA%\vdd\` on Windows).
- **Sessions read only what they need.** The skills are split more finely, so
  each Role reads only the instructions for its own step and platform, when
  it gets there. The skills now have more files and more lines in total,
  because 0.15 adds native Windows and automatic Doorbells, but a session
  reads around 20% fewer tokens.

#### Internal

- The ADRs are cut to the decisions that still hold and renumbered.
- The repository's glossary is `GLOSSARY.md`.
- CI runs on every pushed branch and checks that every shipped script parses
  on macOS, Linux and Windows; the Codex hook has fixture tests.

### Removed

- **Session names.** Start-Loop no longer asks for a short repository name,
  and you no longer rename sessions. Open the Orchestrator with plain
  `claude`, `codex --no-daemon`, `agent` or `copilot`.

### Fixed

- **Skills reported as installed when they were not usable.** Setup counted
  Matt Pocock's skills as installed on Cursor or Copilot CLI when they sat in
  a folder only Claude Code reads.
- **Lost reports on Claude Code.** On Claude Code 2.1.289 and newer, the
  Orchestrator never received a Role's report in later review rounds and
  waited or stopped as `BLOCKED`.
- **Early reviews on Claude Code.** The Code-Reviewer wrote its review before
  its own review passes had finished.
- **Missing messages from the Orchestrator.** Lines meant for you, such as
  the paste line when the plan was signed off, never showed up.
- **A stalled Orchestrator on Codex.** It stopped after starting a Role.
- **Repeated plan reviews on Copilot CLI.** A restarted Orchestrator reviewed
  an already approved plan again.
- **Unapproved models on Copilot CLI.** Roles could run on a model you had not
  approved.
