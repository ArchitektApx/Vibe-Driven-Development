# Changelog

All notable changes to Vibe Driven Development are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
