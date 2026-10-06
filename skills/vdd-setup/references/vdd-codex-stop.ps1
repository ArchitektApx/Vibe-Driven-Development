# vdd-codex-stop.ps1: the Codex Stop hook of Vibe Driven Development, for
# native Windows.
#
# It waits on the Doorbell file for a Codex Planner or Orchestrator, so the
# Session spends no model turn while it waits. It is the PowerShell form of
# vdd-codex-stop.sh and mirrors it. Setup installs it into %LOCALAPPDATA%\vdd\,
# beside doorbell-wait.ps1, and the user's ~\.codex\hooks.json runs it at
# every turn end of a root Codex Session, through
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File vdd-codex-stop.ps1
# It runs on Windows PowerShell 5.1 and on PowerShell 7. It ships once, in
# the vdd-setup skill's references, at mode 644, and is never made
# executable. It needs no jq.
#
# Reads: LOOP.md in the current directory, which Codex sets to the Session's
#   cwd; the hook input on stdin, for its session_id; and the armed file
#   <tracker>/armed-<session_id>, one line "<Role> <armed count>", which the
#   Role writes before its turn ends when it expects a Doorbell.
# Deletes: that armed file, and no other, before it waits.
# Runs: powershell.exe -NoProfile -ExecutionPolicy Bypass -File
#   doorbell-wait.ps1 <tracker>/doorbells <Role> <armed count>, from this
#   script's own directory.
# Prints: {"decision":"block","reason":"<line>"}, the newest line the wait
#   printed or TIMEOUT, so Codex continues the Session with that line as its
#   prompt. Prints nothing when the cwd holds no Codex loop, when nothing is
#   armed for this Session, when the armed line is not a Role and a count, or
#   when the wait exits non-zero.
# Exits 0 on every path.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

try {
  # The fast path: most turn ends on a machine are in a project that holds
  # no Codex loop.
  if (-not (Test-Path -LiteralPath 'LOOP.md' -PathType Leaf)) { exit 0 }

  $utf8 = New-Object System.Text.UTF8Encoding($false)
  $here = (Get-Location).Path

  $codex = $false
  $tracker = ''
  $loopText = [System.IO.File]::ReadAllText((Join-Path $here 'LOOP.md'), $utf8)
  foreach ($line in $loopText.Split([char]10)) {
    # A CR left by a CRLF line is outside the class, as in the sh form.
    if ($line -cmatch '\AHarness: Codex([^A-Za-z0-9_-]|\z)') { $codex = $true }
    if ($line.StartsWith('Tracker: ', [System.StringComparison]::Ordinal)) {
      $tracker = $line.Substring(9)
    }
  }
  if (-not $codex) { exit 0 }

  # The tracker path, trailing blanks and one trailing slash dropped.
  $tracker = $tracker.TrimEnd([char]32, [char]9, [char]13)
  if ($tracker.EndsWith('/')) { $tracker = $tracker.Substring(0, $tracker.Length - 1) }
  if ($tracker -eq '') { exit 0 }

  # The session_id from the hook input, read as UTF-8 bytes. The character
  # set keeps the id a plain file name, and an empty or missing id exits
  # here, so no file named armed- is ever claimed. CODEX_THREAD_ID is not in
  # the hook's environment.
  $stdinReader = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), $utf8)
  $hookInput = $stdinReader.ReadToEnd()
  $ids = [regex]::Matches($hookInput, '"session_id": *"([0-9A-Za-z_-]*)"')
  if ($ids.Count -eq 0) { exit 0 }
  $sessionId = $ids[$ids.Count - 1].Groups[1].Value
  if ($sessionId -cnotmatch '\A[0-9A-Za-z_-]+\z') { exit 0 }

  $trackerPath = [System.IO.Path]::Combine($here, $tracker)
  $armed = [System.IO.Path]::Combine($trackerPath, 'armed-' + $sessionId)
  if (-not [System.IO.File]::Exists($armed)) { exit 0 }

  $armedLine = ([System.IO.File]::ReadAllText($armed, $utf8).Split([char]10))[0].TrimEnd([char]13)
  [System.IO.File]::Delete($armed)

  $fields = @($armedLine.Trim([char]32, [char]9) -split '[ \t]+')
  $role = ''
  $count = ''
  if ($fields.Count -ge 1) { $role = $fields[0] }
  if ($fields.Count -ge 2) { $count = $fields[1] }

  # Checked here, because Windows PowerShell 5.1 drops an empty-string
  # argument to a native program: an empty count would reach the wait as a
  # two-argument call and run its count form.
  if ($role -cne 'Planner' -and $role -cne 'Orchestrator') { exit 0 }
  if ($count -cnotmatch '\A(0|[1-9][0-9]*)\z') { exit 0 }

  $wait = Join-Path $PSScriptRoot 'doorbell-wait.ps1'
  $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $wait, ($tracker + '/doorbells'), $role, $count)
  $quoted = @()
  foreach ($a in $arguments) {
    if ($a -match '[\s"]') {
      # No argument here holds a double quote or ends in a backslash: the
      # path comes from the script's own directory, and the rest is checked
      # above.
      $quoted += ('"' + $a + '"')
    } else {
      $quoted += $a
    }
  }
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = 'powershell.exe'
  $psi.Arguments = $quoted -join ' '
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.StandardOutputEncoding = $utf8
  $psi.WorkingDirectory = $here
  $process = [System.Diagnostics.Process]::Start($psi)
  $out = $process.StandardOutput.ReadToEnd()
  $process.WaitForExit()
  if ($process.ExitCode -ne 0) { exit 0 }

  # The Role acts on the newest line only.
  $lines = @($out.Replace([string][char]13, '').Split([char]10) | Where-Object { $_ -ne '' })
  if ($lines.Count -eq 0) { exit 0 }
  $newest = $lines[$lines.Count - 1]

  # Control characters dropped, then \ and " escaped, so the reason is a valid
  # JSON string.
  $reason = ($newest -replace '[\x00-\x1F\x7F]', '').Replace('\', '\\').Replace('"', '\"')
  if ($reason -eq '') { exit 0 }

  $bytes = $utf8.GetBytes('{"decision":"block","reason":"' + $reason + '"}' + "`n")
  $stdout = [Console]::OpenStandardOutput()
  $stdout.Write($bytes, 0, $bytes.Length)
  $stdout.Flush()
} catch {
  exit 0
}
exit 0
