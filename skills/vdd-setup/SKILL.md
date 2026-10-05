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

   **Present.** Search the roots your Harness file writes out, and only
   those: a skill found in a store your Harness does not read is not there
   for this Harness. On Generic, nobody knows which stores the Harness reads,
   so search the union of every Harness's roots, which the search file below
   writes out.

   Setup runs from the repository root, and `./` is that root as it stands.
   Run the search on every Harness, in place of any search tool your Harness
   gives you: [the find loop](references/present-search-posix.md) in a POSIX
   shell, Git Bash on native Windows included, and
   [the PowerShell search](references/present-search-windows.md) in
   PowerShell. Each applies the relocation variables and follows symlinked
   skill directories the same way everywhere, and a Harness's own search tool
   may do neither.

   **Resolvable.** Present means the file sits in a store this Harness reads;
   it does not mean this Session has loaded it. Answer this one from your own
   skill list alone, leaving symlink targets and other Harnesses' directories
   where they are. Only your own resolution matters, because the user will be
   running the loop in this Harness.

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
   - **Present but not Resolvable.** The skill sits in a store this Harness
     reads, and this Session has not loaded it.
   - **Not Present.** Tell the user to install the whole collection, with the
     commands the repairs below name for your Harness.

   A fourth case passes too: **Resolvable with no search hit.** This Session
   can run the collection, and the search found some of the nine in no store
   it searched, so they resolve from a store Setup does not search. Do not
   report those skills as Not Present, and give no repair for them. Report
   them in one line that names whichever of the nine had no hit:

   ```
   <skills>: Resolvable from a store Setup does not search. Passed.
   ```

   Where your Harness file gives a continuation for this line, add it to the
   line.

   Not Present for `writing-for-agents` alone, with the other eight Present, is
   an old collection rather than a missing one, and telling that user to
   install a collection they already have is the wrong advice.

   In either failing state, and on that old-collection shape, read
   [the repairs](references/repairs.md) before you report: what the failure
   costs each Role, and your Harness's section, the Generic section on
   Generic. Take the route for the store the files came from, and give the
   user the commands it names.

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
4. **Gitignore.** Ensure `.gitignore` covers `LOOP.md` and `.scratch/`, the
   loop's scratch space, which also holds the review files; add either one
   that is missing.

   Then remove the four entries VDD no longer maintains: `PLAN.md`,
   `PLAN-REVIEW.md`, `FIXES.md` and `CODEREVIEW.md`. Name in your report which
   of the four you removed, because this edits a file the user tracks.

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
6. **Shared scripts.** Where your Harness file says this check applies, read
   how to install the shared scripts and follow it: on native Windows, when
   your Harness reports the platform as Windows,
   [`script-install-windows.md`](references/script-install-windows.md), which
   copies [`doorbell-wait.ps1`](references/doorbell-wait.ps1) and
   [`vdd-codex-stop.ps1`](references/vdd-codex-stop.ps1); on macOS and Linux,
   WSL included, [`script-install-unix.md`](references/script-install-unix.md),
   which copies [`doorbell-wait.sh`](references/doorbell-wait.sh) and
   [`vdd-codex-stop.sh`](references/vdd-codex-stop.sh). A command your
   Harness refuses is no reason to skip this check: the file says how to
   escalate it. Where your Harness file says nothing about this check, and on
   Generic, skip it silently: a Generic loop relays every Doorbell by hand and
   runs no script.
7. **The Codex `Stop` hook.** On Codex, once the shared scripts check has run,
   register the hook that wakes a waiting Codex Planner or Orchestrator: on
   native Windows
   [`codex-stop-hook-windows.md`](references/codex-stop-hook-windows.md), on
   macOS and Linux [`codex-stop-hook-unix.md`](references/codex-stop-hook-unix.md).

Finish with a short status report: what passed, what you fixed, what the user still has to do.

## Harnesses

- Claude Code: [`references/harness-claude-code.md`](references/harness-claude-code.md)
- Codex: [`references/harness-codex.md`](references/harness-codex.md)
- Cursor: [`references/harness-cursor.md`](references/harness-cursor.md)
- Copilot CLI: [`references/harness-copilot-cli.md`](references/harness-copilot-cli.md)
