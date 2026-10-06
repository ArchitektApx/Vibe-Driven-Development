# Running the Present search in a POSIX shell

Your Harness file writes out the roots your Present search covers, as a
`set --` line and, on Copilot CLI, a second line. On Generic, use the union of
every Harness's roots instead:

```sh
set -- "$HOME/.agents/skills" ./.agents/skills "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills" ./.claude/skills "${CLAUDE_CODE_PLUGIN_CACHE_DIR:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins}/cache"/*/mattpocock-skills "${CODEX_HOME:-$HOME/.codex}/skills" ./.codex/skills "${CODEX_HOME:-$HOME/.codex}/plugins/cache" "$HOME/.cursor/skills" ./.cursor/skills "$HOME/.cursor/plugins/cache" "${COPILOT_HOME:-$HOME/.copilot}/skills" ./.github/skills "${COPILOT_HOME:-$HOME/.copilot}/installed-plugins"
```

Run those lines and the loop below as one command. A Harness may start a
fresh shell for each command, and a `set --` run on its own is gone by the
time the loop runs.

```sh
for s in setup-matt-pocock-skills grill-with-docs improve-codebase-architecture to-spec to-tickets wayfinder code-review writing-for-agents grilling domain-modeling codebase-design research prototype; do
  find -L "$@" -name SKILL.md 2>/dev/null | grep "/$s/SKILL.md$"
done
```

Each line the loop prints is the path of one hit, and the path names the
store it sits in. Filter with `grep`, not with `-path`, and search one skill
per invocation. Missing roots are normal here, so their errors go to
`/dev/null` and a non-zero exit means nothing. A glob root that matches
nothing reaches `find` as a literal path, and its error is discarded the same
way. The sections below say why the loop has this shape, for when your `find`
rejects a predicate, prints everything under the roots, or returns nothing for
a skill you have reason to think is there.

## The roots

The Claude plugin route nests skills by category (`engineering/`,
`productivity/`), which is why the search matches on the trailing path
`<skill>/SKILL.md` rather than a fixed depth.

The Claude cache root stops at `*/mattpocock-skills`, the plugin's directory
under each marketplace. Claude Code stages a marketplace clone as a
`temp_git_*` directory directly under the cache, laid out as the collection's
own repository, and a root at the cache itself would report that transient
copy as Present. `~/.codex/plugins/cache/` is where Codex installs a plugin,
one directory per marketplace, plugin and version.

Claude Code, Codex and Copilot CLI each move some of their stores when the
user sets one of their variables, and the roots move the search with them,
so the search reads the stores the Harness reads in that state. Each root
carries a default, so an unset variable leaves the plain path. In Git Bash
on native Windows the loop reads `$HOME`, which differs from `%USERPROFILE%`
only when the user set `HOME` themselves, and that gap is accepted.

## Why `grep` and not `-path`

Harnesses commonly replace `find` with a shell function around a
bundled `bfs`, or route it through a command-rewriting proxy, and several of
those answer `-path` with `unknown flag '-path', ignored` and then print
everything under the roots, or nothing at all. `-name` survives both.

## Why one skill per invocation

A single `find` with compound predicates is correct POSIX and works in a plain
shell, but the same proxies reject compound predicates outright. The loop is
immune and costs nothing.

## Why `-L`, and why the files and not the directories

Without `-L`, `find` descends into no symlinked directory, whether its target
exists or not. Measured on macOS with `/usr/bin/find`, with `find` under
`sh -c` and with Claude Code's `bfs` function, all three behave this way. A
skills-CLI install for Claude Code writes the files to
`./.claude/skills/<name>/` at project scope. At global scope it writes the
real copy to `~/.agents/skills/<name>/` and a symlink at
`~/.claude/skills/<name>`, and Claude Code does not search
`~/.agents/skills`, so without `-L` that working install reads as Not
Present.

With `-L`, `find` follows a live symlink and lists nothing under a dangling
one. The search matches `SKILL.md` files rather than skill directories, so a
dangling symlink named like a Borrowed skill lists no file and reads as
absent, which is the answer you want: the skill is not there for the user to
run.
