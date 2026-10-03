---
name: vdd-setup
description: Environment check for the Vibe Driven Development workflow.
---

# VDD Setup

Verify this repository and session are ready for a Vibe Driven Development loop, fix what you can, and report the rest.

This check is machine-level and repository-level. It knows nothing about a
particular feature; `vdd-start-loop` handles per-loop state and writes
`LOOP.md`.

Name the Harness this Session runs in. If the user named one, use theirs. If
this skill's Harnesses index links a file for it, read it now, once. Any other
Harness is Generic, and the inline text is complete.

Check, in order:

1. **Borrowed skills.** The Roles depend on nine skills from Matt Pocock's
   collection:

   | Borrowed skill | Invoked by | Needed by |
   |----------------|-----------|-----------|
   | `setup-matt-pocock-skills` | the user | check 2 below |
   | `grill-with-docs` | the user | Planner |
   | `improve-codebase-architecture` | the user | Planner |
   | `to-spec` | the user | Planner |
   | `to-tickets` | the user | Planner |
   | `wayfinder` | the user | Wayfinder |
   | `code-review` | an agent | Code-Reviewer |
   | `writing-for-agents` | an agent | Planner, Plan-Reviewer, Code-Reviewer |
   | `grilling` | an agent | Brainstormer |

   The six user-invoked ones were blocked from model invocation by their
   author, so they never appear in your own skill list even when correctly
   installed. Answer for them on the two separate conditions below.

   **Present.** Search for the files, not the directories, so that a dangling
   symlink reads as absent:

   ```
   ~/.agents/skills/*/SKILL.md
   ./.agents/skills/*/SKILL.md
   ~/.claude/skills/*/SKILL.md
   ./.claude/skills/*/SKILL.md
   ~/.claude/plugins/cache/*/mattpocock-skills/*/skills/**/SKILL.md
   ~/.codex/plugins/cache/**/SKILL.md
   ```

   Search every root on every Harness, and match on the trailing path
   `<skill>/SKILL.md` rather than a fixed depth.

   Use your file-search tool if you have one; otherwise run
   [the find loop](references/present-search.md).

   **Resolvable.** Present only means the file exists somewhere; it does not
   mean this Harness can run it. Answer this one from your own skill list
   alone, leaving symlink targets and other Harnesses' directories where they
   are. Only your own resolution matters, because the user will be running the
   loop in this Harness.

   Probe your own skill list for `writing-for-agents`. It is Borrowed in its
   own right and agent-invocable, so a wired collection puts it in your skill
   list, and the name is the collection's alone, so a hit needs no reading. A
   hit answers Resolvable for all nine.

   A miss proves nothing, because these collections can be installed one skill
   at a time. `code-review` is agent-invocable too, but a hit on it counts only
   when its description names the two axes "Standards" and "Spec": another
   skill can carry the same bare name. When `writing-for-agents` misses, read
   [the rest of the probe list](references/resolvable-probes.md) before you
   answer Resolvable for anything.

   Report the result as one of three states:

   - **Present and Resolvable.** Passed, say nothing further.
   - **Present but not Resolvable.** Installed, not wired to this Harness.
   - **Not Present.** Tell the user to install the whole collection.

   Not Present for `writing-for-agents` alone, with the other eight Present, is
   an old collection rather than a missing one, and telling that user to
   install a collection they already have is the wrong advice.

   In either failing state, and on that old-collection shape, read
   [the repair for the store the files came from](references/repairs.md),
   in the section for your Harness where the route differs, and give the user
   the commands it names.

   Name what a failure costs each Role, in these words. A missing or
   unresolvable `grill-with-docs`, `improve-codebase-architecture`, `to-spec` or
   `to-tickets` blocks the Planner. A missing or unresolvable `code-review`
   blocks the Code-Reviewer. A missing or unresolvable `wayfinder` blocks the Wayfinder. A
   missing or unresolvable `writing-for-agents` degrades the Planner, the
   Plan-Reviewer and the Code-Reviewer instead of blocking them: each drops
   its writing pass, records that in the file it writes, and carries on. A
   missing or unresolvable `grilling` degrades the Brainstormer the same way:
   it talks the idea through without grilling. The Brainstormer and the
   Wayfinder check their own Borrowed skill when they start, so each of those
   two failures surfaces again at the Role. The Coder is the only Role that
   borrows nothing, and a user resuming mid-workflow is stopped by the
   `code-review` finding alone.

2. **Tracker configured.** `to-spec`, `to-tickets` and `code-review` all read
   `docs/agents/issue-tracker.md` to learn where specs and tickets live, and
   point at `setup-matt-pocock-skills` when it is missing. Check that the file
   exists at the repository root.

   If it is missing, tell the user to invoke `setup-matt-pocock-skills` and to
   recommend Local markdown when it asks which tracker to use. You cannot run
   it yourself: it is user-invoked, like the rest of the collection. Say that
   this blocks the Planner (`to-spec`, `to-tickets`) and the Code-Reviewer
   (`code-review`).

   If it exists but describes something other than the local-markdown tracker,
   note it and continue. VDD works with any tracker the collection supports,
   but the Roles are written for local markdown under `.scratch/<slug>/`.

3. **Git repository.** The workflow needs one. If this directory is not a repository, ask before running `git init`.
4. **Gitignore.** The loop's working files are scratch space, and `.gitignore`
   is what keeps them out of the user's history. Ensure `.gitignore` covers
   `LOOP.md` and `.scratch/`; add either one that is missing. `.scratch/` is
   the Borrowed tracker directory, and VDD is what invokes it here, so it is
   scratch space like the rest. It is also where the three review files are
   written, so its entry covers them.

   Then remove the four entries VDD no longer maintains: `PLAN.md`,
   `PLAN-REVIEW.md`, `FIXES.md` and `CODEREVIEW.md`. A user upgrading from an
   earlier release has them, and no file can appear at any of those paths in
   this release. Name in your report which of the four you removed, because
   this edits a file the user tracks.

   Remove a line only when the whole line, trimmed of surrounding whitespace,
   equals one of those four names. A line that merely contains one of them,
   `docs/PLAN.md` or `!PLAN.md` or `PLAN.md.bak`, is the user's own and stays:
   `PLAN.md` is a name anyone may ignore for reasons of their own.
5. **Stale working files.** If `LOOP.md` already exists from a previous loop,
   ask whether to delete it before starting fresh. Delete only between loops.
   It is the one working file you can find from here: the rest live under
   `.scratch/<slug>/`, and `vdd-start-loop` asks about that directory once
   the user has named the slug, because from here you cannot know which feature
   is stale.
6. **Session-name hook.** Where your Harness file says this check applies,
   read [the Session-name hook Reference](references/session-name-hook.md)
   and follow it, and where it says to skip the check, do what it says.
   Where your Harness file says nothing about it, and on Generic, skip it
   silently.
7. **Shared scripts.** Where your Harness file says this check applies, read
   [how to install the shared scripts](references/script-install.md) and
   follow it. Where your Harness file says nothing about it, and on Generic,
   skip it silently: a Generic loop relays every Doorbell by hand and runs no
   script.

Finish with a short status report: what passed, what you fixed, what the user still has to do.

## Harnesses

- Claude Code: [`references/harness-claude-code.md`](references/harness-claude-code.md)
- Codex: [`references/harness-codex.md`](references/harness-codex.md)
- Cursor: [`references/harness-cursor.md`](references/harness-cursor.md)
- Copilot CLI: [`references/harness-copilot-cli.md`](references/harness-copilot-cli.md)

## Reference files

- [`references/present-search.md`](references/present-search.md): the search
  roots, and why the Present search filters with `grep` and takes one skill per
  invocation.
- [`references/resolvable-probes.md`](references/resolvable-probes.md): the
  sibling names to probe after `writing-for-agents` misses, how to read a bare
  `code-review` hit, and the question to put to the user when nothing hits.
- [`references/repairs.md`](references/repairs.md): the repair for each failing
  state, keyed on the store the files were found in and on the Harness, and the
  update route for a collection that predates `writing-for-agents`.
- [`references/harness-claude-code.md`](references/harness-claude-code.md),
  [`references/harness-codex.md`](references/harness-codex.md),
  [`references/harness-cursor.md`](references/harness-cursor.md) and
  [`references/harness-copilot-cli.md`](references/harness-copilot-cli.md): the
  typed skill names, what each Harness lists under the name `code-review`, on
  Codex the restart a new skill needs and the `Stop` hook registration, on
  Claude Code where the Session-name hook check applies, and that the shared
  scripts check applies.
- [`references/script-install.md`](references/script-install.md): the shared
  directory and its `XDG_DATA_HOME` default, the scripts installed there, the
  `cmp` check, the install or update and its consent step, a denied write,
  native Windows, and its line in the status report.
- [`references/codex-stop-hook.md`](references/codex-stop-hook.md), read only
  where the Codex Harness file sends you: what the Codex `Stop` hook does, the
  registration check across `~/.codex/hooks.json` and `~/.codex/config.toml`,
  the exact entry and why it is exact, the edit and its consent step, the
  trust step, and its line in the status report.
- [`references/doorbell-wait.sh`](references/doorbell-wait.sh) and
  [`references/vdd-codex-stop.sh`](references/vdd-codex-stop.sh): the Doorbell
  wait and the Codex `Stop` hook, which that check copies into the shared
  directory with `cp`, never read and written out with a file tool.
- [`references/session-name-hook.md`](references/session-name-hook.md): what
  the Session-name hook does, its `jq` requirement and minimum Claude Code
  version, the check, the install or update and its consent step, a denied
  write, whether it names this Session, removal, and its line in the status
  report.
- [`references/vdd-session-name.sh`](references/vdd-session-name.sh): the
  Session-name hook script that check copies to `~/.claude/hooks/` with `cp`,
  never read and written out with a file tool.
