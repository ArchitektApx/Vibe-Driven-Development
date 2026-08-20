---
name: vdd-setup
description: Environment check for the Vibe Driven Development workflow.
---

# VDD Setup

Verify this repository and session are ready for a Vibe Driven Development loop, fix what you can, and report the rest.

This check is machine-level and repository-level. It knows nothing about a
particular feature; `/vdd:vdd-start-loop` handles per-loop state and writes
`LOOP.md`.

Check, in order:

1. **Borrowed skills.** The Roles depend on seven skills from Matt Pocock's
   collection:

   | Borrowed skill | Invoked by | Needed by |
   |----------------|-----------|-----------|
   | `setup-matt-pocock-skills` | the user | check 2 below |
   | `grill-with-docs` | the user | Planner |
   | `improve-codebase-architecture` | the user | Planner |
   | `to-spec` | the user | Planner |
   | `to-tickets` | the user | Planner |
   | `code-review` | an agent | Code-Reviewer |
   | `writing-for-agents` | an agent | Planner, Plan-Reviewer, Code-Reviewer |

   The five user-invoked ones have `disable-model-invocation: true` in their
   frontmatter, so they never appear in your own skill list even when correctly
   installed. Your skill list is silent about those five by design, so answer
   for them on the two separate conditions below.

   **Present.** Search for the files, not the directories, so that a dangling
   symlink reads as absent:

   ```
   ~/.agents/skills/*/SKILL.md
   ./.agents/skills/*/SKILL.md
   ~/.claude/skills/*/SKILL.md
   ./.claude/skills/*/SKILL.md
   ~/.claude/plugins/cache/*/mattpocock-skills/*/skills/**/SKILL.md
   ```

   You want `setup-matt-pocock-skills/SKILL.md`, `grill-with-docs/SKILL.md`,
   `improve-codebase-architecture/SKILL.md`, `to-spec/SKILL.md`,
   `to-tickets/SKILL.md`, `code-review/SKILL.md` and
   `writing-for-agents/SKILL.md`. Match on the trailing path rather than a
   fixed depth.

   Use your file-search tool if you have one; otherwise:

   ```bash
   for s in setup-matt-pocock-skills grill-with-docs improve-codebase-architecture to-spec to-tickets code-review writing-for-agents; do
     find ~/.agents/skills ./.agents/skills ~/.claude/skills ./.claude/skills ~/.claude/plugins/cache \
       -name SKILL.md 2>/dev/null | grep "/$s/SKILL.md$"
   done
   ```

   Filter with `grep`, not with `-path`, and search one skill per invocation.
   Missing search roots are normal here, so their errors go to `/dev/null` and
   a non-zero exit means nothing. When your `find` rejects a predicate, or
   prints everything under the roots, or returns nothing for a skill you have
   reason to think is there, read
   [why the search is shaped this way](references/present-search.md).

   **Resolvable.** Present only means the file exists somewhere; it does not
   mean this agent can run it. Answer this one from your own skill list alone,
   leaving symlink targets and other agents' directories where they are. Only
   your own resolution matters, because the user will be running the loop in
   this agent.

   Probe your own skill list for `writing-for-agents`. It is Borrowed in its
   own right and agent-invocable, so a wired collection puts it in your skill
   list, and Claude Code bundles nothing of that name, so a hit needs no
   reading. A hit answers Resolvable for the five user-invoked skills, for
   `code-review` and for `writing-for-agents` itself.

   A miss proves nothing, because these collections can be installed one skill
   at a time. `code-review` is agent-invocable too, so it looks like a second
   probe; it is not, because Claude Code ships an unrelated bundled
   `code-review` skill of the same bare name, and a bare hit proves nothing
   until you have read its description. When `writing-for-agents` misses, read
   [the rest of the probe list](references/resolvable-probes.md) before you
   answer Resolvable for anything.

   Report the result as one of three states:

   - **Present and Resolvable.** Passed, say nothing further.
   - **Present but not Resolvable.** Installed, but not wired to this agent.
     The install already happened, so the repair is wiring, and where you found
     the file decides which repair. Keep each repair on the store its files
     came from: the npx route offered for a plugin-route install creates a
     second, parallel copy of the collection.
   - **Not Present.** Tell the user to install the whole collection.

   Not Present for `writing-for-agents` alone, with the other six Present, is
   an old collection rather than a missing one, and telling that user to
   install a collection they already have is the wrong advice.

   In either failing state, and on that old-collection shape, read
   [the repair for the store the files came from](references/repairs.md) and
   give the user the commands it names.

   Name what a failure costs each Role, in these words. A missing or
   unresolvable `grill-with-docs`, `improve-codebase-architecture`, `to-spec` or
   `to-tickets` blocks the Planner. A missing or unresolvable `code-review`
   blocks the Code-Reviewer. A missing or unresolvable `writing-for-agents`
   degrades the Planner, the Plan-Reviewer and the Code-Reviewer instead of
   blocking them: each drops its writing pass, records that in the file it
   writes, and carries on. The Coder is the only Role that borrows nothing,
   and a user resuming mid-workflow is stopped by the `code-review` finding
   alone.

2. **Tracker configured.** `to-spec`, `to-tickets` and `code-review` all read
   `docs/agents/issue-tracker.md` to learn where specs and tickets live, and
   point at `/setup-matt-pocock-skills` when it is missing. Check that the file
   exists at the repository root.

   If it is missing, tell the user to type `/setup-matt-pocock-skills` and to
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
   `.scratch/<slug>/`, and `/vdd:vdd-start-loop` asks about that directory once
   the user has named the slug, because from here you cannot know which feature
   is stale.

Finish with a short status report: what passed, what you fixed, what the user still has to do.

## Reference files

- [`references/present-search.md`](references/present-search.md): the search
  roots, and why the Present search filters with `grep` and takes one skill per
  invocation.
- [`references/resolvable-probes.md`](references/resolvable-probes.md): the
  sibling names to probe after `writing-for-agents` misses, how to read a bare
  `code-review` hit, and the question to put to the user when nothing hits.
- [`references/repairs.md`](references/repairs.md): the repair for each failing
  state, keyed on the store the files were found in, and the update route for a
  collection that predates `writing-for-agents`.
