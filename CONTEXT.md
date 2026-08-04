# Vibe Driven Development

The vocabulary of an adversarial multi-session coding workflow, and of the plugin that ships it as skills.

## The workflow

**Role**:
One of the five jobs in the workflow (Planner, Plan-Reviewer, Coder, Code-Reviewer, plus Setup). Each ships as one skill file and is meant to run in its own session.
_Avoid_: agent, persona, mode

**Session**:
A single agent conversation running one Role. Separate sessions are what make the review adversarial, because a session cannot see another's reasoning.
_Avoid_: instance, window, context

**Loop**:
A Role and its reviewer exchanging a working file until sign-off. The workflow has two: Plan/Plan-Review and Coder/Code-Review.
_Avoid_: cycle, iteration, phase

**Working file**:
One of `PLAN.md`, `PLAN-REVIEW.md`, `FIXES.md`, `CODEREVIEW.md`. Scratch space for handoff between sessions, gitignored, never part of the user's project.
_Avoid_: artifact, output, deliverable

**Sign-off**:
The literal line `SIGNED OFF` at the top of a review file. The only thing that ends a Loop; hedged approval is not sign-off.
_Avoid_: approval, LGTM, done

## Skill dependencies

**Borrowed skill**:
A skill from another collection that a Role depends on but does not ship. Currently `grill-with-docs` and `improve-codebase-architecture` from Matt Pocock's collection.
_Avoid_: external skill, third-party skill, dependency

**User-invoked**:
A property of a skill whose author blocked agents from starting it, so only a human typing the slash command can. Both Borrowed skills are user-invoked. In Claude Code this is `disable-model-invocation: true` in the frontmatter; in Codex, `policy.allow_implicit_invocation: false`.
_Avoid_: manual, disabled, blocked

**Present**:
A Borrowed skill's `SKILL.md` exists in a known store on this machine. Says nothing about whether any agent can run it.
_Avoid_: installed, downloaded

**Resolvable**:
The agent running right now can actually run a Borrowed skill. Present is necessary but not sufficient: a Borrowed skill sitting in a store this agent was never wired to is Present and not Resolvable. A dangling symlink is neither, because the file it points at does not exist.
_Avoid_: available, wired, active, visible

**Sibling probe**:
Testing Resolvable by looking for one of the Borrowed skills' collection-mates that is not User-invoked, and therefore does appear in an agent's own skill list. A hit proves the collection is wired to this agent; a miss proves nothing, because collections can be installed one skill at a time.
_Avoid_: skill check, availability check
