# Running the Present search in PowerShell

Your Harness file lists the roots your Present search covers, and on Generic
check 1 lists the union. This file spells those roots for PowerShell and
holds the search that reads them. It lists no roots of its own. Everything
here runs in Windows PowerShell 5.1 and in PowerShell 7 alike.

## The substitution table

The search opens with four lines that resolve the stores a variable can move,
each falling back to its default under `$env:USERPROFILE`:

```powershell
$claude = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE '.claude' }
$claudePlugins = if ($env:CLAUDE_CODE_PLUGIN_CACHE_DIR) { $env:CLAUDE_CODE_PLUGIN_CACHE_DIR } else { Join-Path $claude 'plugins' }
$codex = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$copilot = if ($env:COPILOT_HOME) { $env:COPILOT_HOME } else { Join-Path $env:USERPROFILE '.copilot' }
```

Spell each root by replacing its prefix as below, turning every `/` after it
into `\`, and keep the double quotes. Where two prefixes match a root, the
longer one wins, so the Claude cache root always takes its own row and never
the `~/.claude` row:

| Root prefix | PowerShell spelling |
|---|---|
| `~/.claude` | `"$claude` |
| `~/.claude/plugins/cache`, the Claude cache root | `"$claudePlugins\cache` |
| `~/.codex` | `"$codex` |
| `~/.copilot` | `"$copilot` |
| any other `~` | `"$env:USERPROFILE` |
| `./` | `".\` |

The rest of the root follows, then the closing quote:
`~/.claude/plugins/cache/*/mattpocock-skills` reads
`"$claudePlugins\cache\*\mattpocock-skills"`, and `./.claude/skills` reads
`".\.claude\skills"`. `~` is `%USERPROFILE%`, never `HOME`, because the
Harnesses read their stores under `%USERPROFILE%` on Windows.

## Writing and running the search

1. Take every root your Harness file lists, or every root of the union on
   Generic.
2. Spell each one with the substitution table.
3. Write them, separated by commas, inside `$roots = @(...)` on one line.
4. On Copilot CLI, leave `~/.agents/skills` off that line and add this line
   after it, which adds the root only when `COPILOT_HOME` is empty or unset:

   ```powershell
   if (-not $env:COPILOT_HOME) { $roots += "$env:USERPROFILE\.agents\skills" }
   ```

   Generic keeps `"$env:USERPROFILE\.agents\skills"` on its `$roots` line
   whatever `COPILOT_HOME` holds.
5. Run the four lines above, your `$roots` line, the Copilot CLI line where
   it applies, and the search below as one command. A Harness may start a
   fresh PowerShell for each command, and variables set in one are gone by
   the time the next runs.

```powershell
$follow = @{}
if ($PSVersionTable.PSVersion.Major -ge 6) { $follow = @{ FollowSymlink = $true } }
$found = @(Get-Item -Path $roots -Force -ErrorAction SilentlyContinue | Where-Object { $_.PSIsContainer } | ForEach-Object { Get-ChildItem -LiteralPath $_.FullName -Recurse -Force -File -Filter SKILL.md -ErrorAction SilentlyContinue @follow })
foreach ($s in 'setup-matt-pocock-skills', 'grill-with-docs', 'improve-codebase-architecture', 'to-spec', 'to-tickets', 'wayfinder', 'code-review', 'writing-for-agents', 'grilling') {
  $found | Where-Object { $_.Directory.Name -eq $s } | ForEach-Object { $_.FullName }
}
```

On Claude Code the whole command reads:

```powershell
$claude = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE '.claude' }
$claudePlugins = if ($env:CLAUDE_CODE_PLUGIN_CACHE_DIR) { $env:CLAUDE_CODE_PLUGIN_CACHE_DIR } else { Join-Path $claude 'plugins' }
$codex = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$copilot = if ($env:COPILOT_HOME) { $env:COPILOT_HOME } else { Join-Path $env:USERPROFILE '.copilot' }
$roots = @("$claude\skills", ".\.claude\skills", "$claudePlugins\cache\*\mattpocock-skills")
$follow = @{}
if ($PSVersionTable.PSVersion.Major -ge 6) { $follow = @{ FollowSymlink = $true } }
$found = @(Get-Item -Path $roots -Force -ErrorAction SilentlyContinue | Where-Object { $_.PSIsContainer } | ForEach-Object { Get-ChildItem -LiteralPath $_.FullName -Recurse -Force -File -Filter SKILL.md -ErrorAction SilentlyContinue @follow })
foreach ($s in 'setup-matt-pocock-skills', 'grill-with-docs', 'improve-codebase-architecture', 'to-spec', 'to-tickets', 'wayfinder', 'code-review', 'writing-for-agents', 'grilling') {
  $found | Where-Object { $_.Directory.Name -eq $s } | ForEach-Object { $_.FullName }
}
```

Each line the search prints is the full path of one hit, and the path names
the store it sits in. Missing roots and access errors are normal here, so
both are silenced.

## The roots

`Get-Item` expands the `*` in the Claude cache root to the directories it
matches, one per marketplace, and the search starts below each
`mattpocock-skills`. A `temp_git_*` staging clone that Claude Code leaves
directly under the cache is laid out as the collection's own repository, so
it holds no `mattpocock-skills` directory and never matches. The Claude
plugin route nests skills by category (`engineering/`, `productivity/`),
which is why the search recurses rather than looking at a fixed depth.

Claude Code, Codex and Copilot CLI each move some of their stores when the
user sets one of the variables in the four lines, and the lines move the
search with them, so the search reads the stores the Harness reads in that
state. Each line carries a default, so an unset variable leaves the plain
path.

## Why the parent directory name

Windows paths carry backslashes, so the search matches a hit on the name of
the directory that holds the `SKILL.md`, not on a trailing path pattern with
`/`. That is the POSIX loop's `<skill>/SKILL.md` at any depth.

## Why `-FollowSymlink`, and why the files and not the directories

A skills-CLI install can link a skill directory into a store rather than
copy it. Windows PowerShell 5.1 follows a linked directory when it recurses,
and PowerShell 6 and later do so only with `-FollowSymlink`, which 5.1 does
not have, so the search passes it where `$PSVersionTable` says 6 or later.
Without it, a working link install reads as Not Present on PowerShell 7.

The search matches `SKILL.md` files rather than skill directories, so a
dangling link named like a Borrowed skill lists no file and reads as absent,
which is the answer you want: the skill is not there for the user to run.
