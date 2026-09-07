# Where the Borrowed skills sit, and why the search is shaped this way

## The find loop

```bash
for s in setup-matt-pocock-skills grill-with-docs improve-codebase-architecture to-spec to-tickets wayfinder code-review writing-for-agents grilling; do
  find ~/.agents/skills ./.agents/skills ~/.claude/skills ./.claude/skills ~/.claude/plugins/cache \
    -name SKILL.md 2>/dev/null | grep "/$s/SKILL.md$"
done
```

Filter with `grep`, not with `-path`, and search one skill per invocation.
Missing search roots are normal here, so their errors go to `/dev/null` and a
non-zero exit means nothing. The sections below say why the loop has this shape,
for when your `find` rejects a predicate, prints everything under the roots, or
returns nothing for a skill you have reason to think is there.

## The roots

The Claude plugin route nests skills by category (`engineering/`,
`productivity/`), which is why the search matches on the trailing path rather
than a fixed depth. The two `.claude/skills` roots are where the skills CLI
writes when it installs for Claude Code: project scope lands in
`./.claude/skills/<name>/`, global scope stores the files in
`~/.agents/skills/<name>/` and symlinks `~/.claude/skills/<name>` at them.

## Why `grep` and not `-path`

Agent environments commonly replace `find` with a shell function around a
bundled `bfs`, or route it through a command-rewriting proxy, and several of
those answer `-path` with `unknown flag '-path', ignored` and then print
everything under the roots, or nothing at all. `-name` survives both.

## Why one skill per invocation

A single `find` with compound predicates is correct POSIX and works in a plain
shell, but the same proxies reject compound predicates outright. The loop is
immune and costs nothing.

## Why the files and not the directories

Without `-L`, `find` does not descend into a symlinked directory whose target
is gone, so no `SKILL.md` is ever listed under it. A dangling symlink reads as
absent, which is the answer you want: the skill is not there for the user to
run.
