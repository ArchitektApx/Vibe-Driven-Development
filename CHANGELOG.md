# Changelog

All notable changes to Vibe Driven Development are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

**TL;DR:** VDD now needs Python 3.9 or newer: Setup and the Doorbell run in
the VDD tool, a small program VDD ships, which makes both faster and more
reliable. The Codex hook ships with the plugin, the Orchestrator recommends
how the Coder restarts for the least cost on your agent, and code reviews on
Claude Code and Codex are fixed. Each loop keeps its settings in its own
directory, every loop starts with Start-Loop, and a finished loop leaves a
`RECAP.md` that says how it went. VDD also needs git 2.40 or newer: it folds
each loop's fixes into the commits they fix, at every Sign-off. The
Brainstormer keeps one file per idea with no index, so it needs Setup too,
and it offers to hand a decided idea to the next Role.

### Migrating from 0.15

1. **Install Python 3.9 or newer** if your machine has none. On a Mac, the
   Command Line Tools that bring git bring one. On Windows, VDD runs it as
   `py -3`, which every python.org install provides. Without it, a Role says
   so and stops.
2. **On Codex, trust VDD's hook once in `/hooks`.** It now ships with the
   plugin, and Setup migrates the 0.15 hook. If you trusted it on an earlier
   0.16 beta, Codex asks once more, because the hook changed.
3. **Optionally, delete the old scripts** `doorbell-wait.*` and
   `vdd-codex-stop.*` in `~/.local/share/vdd/` (`%LOCALAPPDATA%\vdd\` on
   Windows) once no loop on an older VDD is running.
4. **Finish or restart a loop in flight.** A loop now keeps its settings in
   its own directory, and VDD no longer reads `LOOP.md` at the repository
   root: every Role stops while it is there, and Setup tells you so. Delete
   `LOOP.md`. To carry on the loop it belonged to, run `/vdd:vdd-start-loop`
   with its slug and answer continue.
5. **On a 0.16 beta, finish a loop you started on 0.16.0-beta.3 with that
   version.** The Planner, the reviewers, the Coder and the PR-Author
   refuse it on this one and say so.
   Reinstall 0.16.0-beta.3 to finish it, or move it aside with the command
   they print and start the loop again.
6. **Install git 2.40 or newer** if yours is older. Setup checks it and
   stops until it is. On a Mac, git comes with the Command Line Tools, and
   older Xcode releases bring an older one.
7. **A loop started on an earlier 0.16 beta finishes with its branch
   unfolded.** Its commits stay as its Coder made them, and the Orchestrator
   tells you so before the PR.
8. **Your first Brainstormer session converts a 0.15 idea store on your
   yes.** It says what the migration does before anything is written, and
   first keeps your whole store as a backup in
   `.scratch/_brainstorming.pre-0.16/`. To undo it, delete the migrated
   `.scratch/_brainstorming/`, rename the backup back to
   `.scratch/_brainstorming/`, and use a 0.15 plugin. On 0.16 a restored
   store is offered the migration again. Until you say yes, the Brainstormer
   cannot work on the old store.

### Changed

- **The Brainstormer keeps one file per idea, with no index or Log.** Every
  idea, open or closed, stays in one folder, and each file ends with a
  History of what happened to it. The Brainstormer's first look shows every
  open idea, so it answers your first message at once. Each move you ask for
  is one command of the VDD tool, so the files stay consistent and a session
  costs far fewer calls. The Brainstormer now needs `/vdd:vdd-setup` once
  per machine.
- **Ideas have parts.** Split an idea into parts, file one idea under
  another, merge two ideas into one, or rename one; a family goes three
  levels deep. Before a new idea is written, the Brainstormer shows you the
  ideas it looks like, closed ones included.
- **Clean up closed ideas.** Ask the Brainstormer to remove done or dropped
  ideas, by status, age or name. It lists them first and removes them on your
  yes, keeping a one-line record of each, so "didn't we talk about this"
  still finds it. Research folders stay.
- **The Brainstormer offers the next Role.** When a grilling ends in
  agreement, it asks whether to keep brainstorming or take the idea on, with
  `/vdd:vdd-start-loop` for one loop or `/vdd:vdd-wayfinder` for more, and
  gives you the line to start it.
- **Setup runs in the VDD tool.** It is faster and more precise: it shows
  the exact changes before it makes them, and its repair advice is the exact
  commands for your agent.
- **Doorbells run in the VDD tool.** It keeps track of what each Role has
  handled, so a Doorbell is acted on once, even when it arrives twice or a
  session restarts, and a mistyped one is refused before the other session
  sees it.
- **Coder restarts tuned to your agent.** With Model approval, the
  Orchestrator asks once per loop how the Coder continues between rounds,
  and recommends what costs least with your agent's cache: a fresh Coder
  every round on Claude Code, Cursor and Copilot CLI, one Coder for all
  rounds on Codex. On Claude Code you can also restart it once its token
  count passes a limit. Start-Loop no longer asks. At any round you can ask
  the Orchestrator to restart any Role every round, or once.
- **Review files hold what is still open.** `PLAN-REVIEW.md` and
  `CODEREVIEW.md` list only the open findings, each code finding with the
  Coder's answer under it, and `FIXES.md` holds the current round only. A
  miscounted or skipped finding is caught in the Role's own turn. The
  Code-Reviewer no longer pastes the `code-review` reports; each problem
  they raise becomes a finding or one line saying why not.
- **`RECAP.md` after the loop.** `.scratch/<slug>/RECAP.md` records how the
  loop went: the rounds, each ticket, every closed finding with what was
  wrong and how it was resolved, and the review notes the Code-Reviewer did
  not carry. The PR-Author reads it only for a testing or review section
  your PR template or your past PRs ask for.
- **A restarted Orchestrator picks up where the loop stood.** It starts or
  resumes the right Role with the right files, and a Role that ends a round
  without finishing it is sent back once before you are asked. Say "pause"
  between rounds and it stops before the next step.
- **Each loop keeps its settings in its own directory.** VDD writes and reads
  them in `.scratch/<slug>/` for you, so two loops in one repository never
  share them, and there is no `LOOP.md` to delete after a loop. A finished
  loop is closed and its files stay as its record. To fix something before
  you merge, send it back with `review add`.
- **Start-Loop asks less.** It no longer asks whether to delete an old
  `LOOP.md`. When an earlier loop used your slug, it offers only what fits:
  continue an interrupted loop, start fresh with the old files moved aside
  and nothing deleted, or pick another slug.
- **Every loop starts with `/vdd:vdd-start-loop`.** The Planner, the
  Plan-Reviewer, the Coder and the Code-Reviewer stop with one line when you
  start them by hand, and Claude Code and Copilot CLI no longer list them in
  the `/` menu. You can still start the PR-Author by hand after Sign-off.
- **The Planner asks for the problem.** Started with nothing described, it
  asks what problem the loop solves. `improve-codebase-architecture` is yours
  to run before a loop or the Wayfinder, and Setup no longer requires it or
  `codebase-design`.
- **Commits no longer carry `Ticket NN`.** The Coder commits in your
  repository's own style: one commit per ticket, then its fixes as plain
  commits in later rounds.
- **The branch is folded at each Sign-off, by VDD.** After the code review
  signs off, each later round's fix moves into the commit that wrote the
  lines it changes, so the branch reads as one commit per ticket plus any
  commit no ticket owned. A fix that would clash stays as its own commit.
  The branch moves only when it holds exactly what was reviewed, and never
  once it was pushed; otherwise it stays as reviewed and you are told
  why. When your findings reopen the loop, the next Sign-off folds again.
  `RECAP.md` lists each final commit and what it was built from.
- **Findings you add after Sign-off reopen the loop.** Put them in a file and
  run `review add`: it numbers them, you set each one's severity, and a
  fresh Coder takes them in the next round. The Code-Reviewer reviews only
  that round's fixes, and `RECAP.md` shows your findings in a row of their
  own, apart from the reviewers' rounds. Minors that a `Minors: leave`
  Sign-off left open do not come back unless you list them. When the PR is
  already open, the PR-Author pushes the fixes to it as new commits. The
  workflow page shows the call.
- **Start-Loop shows you its warnings and summary.** The slug, the Harness
  and how to correct it, and the warnings about a push or a PR that will fail
  are printed by VDD and relayed to you before the Planner starts. They were
  dropped in every Claude Code Start-Loop since 2026-10-17.
- **The Coder cannot leave a new file out of the commits.** When a round ends
  with a file the Coder created and never added, VDD refuses it and names the
  file. A file that was already untracked when the round started, and an
  ignored one, pass.
- **A later round is reviewed on its own diff.** The Code-Reviewer reviews
  the fixes since its last round instead of the whole branch again, and
  still reruns the verification on the whole branch. A reviewer who skips a
  check now says so, with the reason, and `RECAP.md` shows it.
- **VDD opens the PR itself, so a title keeps its quotes.** The PR-Author
  shows you the title and body, and after your confirmation one VDD command
  pushes the branch, opens the PR and closes the loop. A title with a double
  quote or an apostrophe reaches GitHub as you confirmed it, on Windows too,
  and the body stays in `.scratch/<slug>/pr-body.md`. A sandbox that blocks
  reading your PR history no longer passes for a repository without one.
- **The Wayfinder finds Matt Pocock's `wayfinder` for you** and fills in its
  briefing, on every agent.
- **The Codex hook starts Python only for a wait.** Outside a Codex
  session's wait for a Doorbell it ends at once, under zsh too.
- **A mistyped option names its fix.** When a VDD command gets an option it
  does not take, it lists the options the command takes and names the
  closest one. When none is close and the skill itself writes that option,
  your copy of the VDD tool is older than the skill, and the Role asks you to
  rerun Setup.
- **A value Windows PowerShell 5.1 mangled is refused.** When a
  value ends in a backslash, PowerShell 5.1 pulls the options after it into
  that value. VDD now refuses such a value and says why, and the Role runs
  the command again without the backslash.

#### Internal

- CI runs the VDD tool's tests on macOS, Linux and Windows against Python
  3.9 and the newest 3.x, and checks the shipped code for shell calls,
  network modules and computed imports.

### Fixed

- **VDD calls refused on Codex for Windows.** On an earlier 0.16 beta,
  Codex's Windows sandbox could not read the copy of the VDD tool Setup
  installs, so every call was refused once and rerun outside the sandbox.
  The next Setup replaces the copy.
- **Sandbox refusals on a git set to another language.** git translates its
  messages, so on a system in another language a sandbox that refused git
  read as a plain failure instead of asking to rerun outside the sandbox.
  VDD now runs git in English.
- **Late or polled code reviews on Claude Code.** The Code-Reviewer's two
  review passes sometimes reported late, or the Code-Reviewer spent tokens
  polling for them. Both are fixed.
- **Roles on Codex started as forks of their parent.** Codex starts a
  subagent as a fork carrying its parent's whole conversation by default, so
  every Role the Orchestrator started, and the Code-Reviewer's review
  passes, carried context that was not theirs: the reviews were less
  independent and cost more
  ([mattpocock/skills#1257](https://github.com/mattpocock/skills/issues/1257)).
  VDD now starts each from its own instructions alone.

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
