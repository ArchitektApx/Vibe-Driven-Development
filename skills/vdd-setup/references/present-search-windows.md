# Running the Present search in PowerShell

Your Harness file writes out the roots your Present search covers, as a
`$roots` block. Everything here runs in Windows PowerShell 5.1 and in
PowerShell 7 alike. `~` is `%USERPROFILE%`, never `HOME`, because the
Harnesses read their stores under `%USERPROFILE%` on Windows. On Generic, use
the union of every Harness's roots instead:

```powershell
$claude = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE '.claude' }
$claudePlugins = if ($env:CLAUDE_CODE_PLUGIN_CACHE_DIR) { $env:CLAUDE_CODE_PLUGIN_CACHE_DIR } else { Join-Path $claude 'plugins' }
$codex = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$copilot = if ($env:COPILOT_HOME) { $env:COPILOT_HOME } else { Join-Path $env:USERPROFILE '.copilot' }
$roots = @("$env:USERPROFILE\.agents\skills", ".\.agents\skills", "$claude\skills", ".\.claude\skills", "$claudePlugins\cache\*\mattpocock-skills", "$codex\skills", ".\.codex\skills", "$codex\plugins\cache", "$env:USERPROFILE\.cursor\skills", ".\.cursor\skills", "$env:USERPROFILE\.cursor\plugins\cache", "$copilot\skills", ".\.github\skills", "$copilot\installed-plugins")
```

Run that block and the search below as one command. A Harness may start a
fresh PowerShell for each command, and variables set in one are gone by the
time the next runs.

```powershell
$follow = @{}
if ($PSVersionTable.PSVersion.Major -ge 6) { $follow = @{ FollowSymlink = $true } }
$found = @(Get-Item -Path $roots -Force -ErrorAction SilentlyContinue | Where-Object { $_.PSIsContainer } | ForEach-Object { Get-ChildItem -LiteralPath $_.FullName -Recurse -Force -File -Filter SKILL.md -ErrorAction SilentlyContinue @follow })
foreach ($s in 'setup-matt-pocock-skills', 'grill-with-docs', 'improve-codebase-architecture', 'to-spec', 'to-tickets', 'wayfinder', 'code-review', 'writing-for-agents', 'grilling', 'domain-modeling', 'codebase-design', 'research', 'prototype') {
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
user sets one of their variables, and the roots move the search with
them, so the search reads the stores the Harness reads in that
state. Each root carries a default, so an unset variable leaves the plain
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
