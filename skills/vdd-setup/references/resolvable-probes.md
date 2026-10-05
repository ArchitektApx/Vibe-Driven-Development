# Probing for the collection after `writing-for-agents` misses

## The rest of the probe list

Probe your own skill list for another of the collection's skills that is not
user-invoked: `grilling`, `codebase-design`, `domain-modeling`, `tdd`,
`research`, `prototype`, `diagnosing-bugs`. A hit
means the collection is wired to this Harness, which answers Resolvable for all
nine. A miss on `writing-for-agents`
followed by a hit further down the list means the collection is Resolvable and
`writing-for-agents` is not.

## Reading a `code-review` hit

- A `code-review` whose description names the two axes "Standards" and "Spec"
  is Matt Pocock's. It proves the collection is Resolvable.
- A `code-review` with any other description is a different skill of the same
  name. It proves nothing. Ignore it and fall through to the sibling names
  above.

### On Claude Code

- A hit on `mattpocock-skills:code-review` is the Claude Code plugin install.
  It proves the collection is Resolvable.
- A bare `code-review` whose description names "Standards" and "Spec" is a
  skills-CLI install, where the collection is the only source of that name, and
  a project or personal skill of that name replaces Claude Code's bundled one.
  It proves the collection is Resolvable too.
- A bare `code-review` with any other description is Claude Code's bundled
  `code-review` skill.

## On a miss across the whole list, or a skill list you cannot inspect

Ask the user to invoke `writing-for-agents` and tell you whether it resolves.
That one question answers the collection and the seventh skill together, and a
miss on it followed by a `grill-with-docs` hit is the collection that predates
the skill.
