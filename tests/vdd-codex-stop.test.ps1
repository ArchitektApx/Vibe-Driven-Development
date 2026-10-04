# vdd-codex-stop.test.ps1: the fixture test for the PowerShell Doorbell wait
# and the PowerShell Codex Stop hook.
#
# Run from anywhere, with pwsh on macOS or Linux and with powershell.exe on
# Windows, as
#   pwsh -NoProfile -File tests/vdd-codex-stop.test.ps1 [-WaitScript <path>] [-HookScript <path>]
# It tests skills/vdd-setup/references/doorbell-wait.ps1 and
# skills/vdd-setup/references/vdd-codex-stop.ps1, or the scripts named by the
# two parameters (scratch copies for a mutation check). It is the PowerShell
# counterpart of tests/vdd-codex-stop.test.sh. Every file it reads or writes
# is built under the temp directory, and it touches no real Session. It runs
# every script with the PowerShell that runs this test.
#
# It prints one PASS or FAIL line per case, and SKIP for a case this machine
# cannot run, and exits 1 when any case fails, 0 when all pass. Written for
# Windows PowerShell 5.1 and PowerShell 7 alike.

param(
  [string]$WaitScript = '',
  [string]$HookScript = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$repo = Split-Path -Parent $PSScriptRoot
$references = Join-Path (Join-Path (Join-Path $repo 'skills') 'vdd-setup') 'references'
if ($WaitScript -eq '') { $WaitScript = Join-Path $references 'doorbell-wait.ps1' }
if ($HookScript -eq '') { $HookScript = Join-Path $references 'vdd-codex-stop.ps1' }
$waitSh = Join-Path $references 'doorbell-wait.sh'

$onWindows = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
$hostExe = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Say([string]$text) { [Console]::Out.WriteLine($text) }

Say ('wait: ' + $WaitScript)
Say ('hook: ' + $HookScript)
Say ('host: ' + $hostExe + ', PowerShell ' + $PSVersionTable.PSVersion)

if (-not (Test-Path -LiteralPath $WaitScript -PathType Leaf)) {
  Say ('FAIL  no wait script at ' + $WaitScript)
  exit 1
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('vdd-codex-stop-test.' + [guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $root)

# --- Running a script -------------------------------------------------------

# Quotes one argument for a Windows command line, which .NET also parses on
# macOS and Linux. An empty argument becomes "", so it still arrives.
function Format-Argument([string]$a) {
  if ($a.Length -gt 0 -and $a -notmatch '[\s"]') { return $a }
  $sb = New-Object System.Text.StringBuilder
  [void]$sb.Append('"')
  $slashes = 0
  foreach ($c in $a.ToCharArray()) {
    if ($c -eq [char]'\') { $slashes++; continue }
    if ($c -eq [char]'"') {
      [void]$sb.Append([char]'\', 2 * $slashes + 1)
    } else {
      [void]$sb.Append([char]'\', $slashes)
    }
    [void]$sb.Append($c)
    $slashes = 0
  }
  [void]$sb.Append([char]'\', 2 * $slashes)
  [void]$sb.Append('"')
  return $sb.ToString()
}

# Runs a program and sets $script:out, $script:err and $script:status. stdin
# is written as UTF-8 bytes. A run longer than two minutes is killed and
# reads as status -1, since a real wait would run for 45 minutes.
function Invoke-Child([string]$exe, [string[]]$arguments, [string]$stdin, [string]$cwd) {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $exe
  $quoted = @()
  foreach ($a in $arguments) { $quoted += (Format-Argument $a) }
  $psi.Arguments = $quoted -join ' '
  $psi.UseShellExecute = $false
  $psi.RedirectStandardInput = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.StandardOutputEncoding = $utf8
  $psi.StandardErrorEncoding = $utf8
  if ($cwd -ne '') { $psi.WorkingDirectory = $cwd }
  $p = [System.Diagnostics.Process]::Start($psi)
  $outTask = $p.StandardOutput.ReadToEndAsync()
  $errTask = $p.StandardError.ReadToEndAsync()
  if ($stdin -ne '') {
    $bytes = $utf8.GetBytes($stdin)
    $p.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
    $p.StandardInput.BaseStream.Flush()
  }
  $p.StandardInput.Close()
  if ($p.WaitForExit(120000)) {
    $p.WaitForExit()
    $script:status = $p.ExitCode
  } else {
    $p.Kill()
    $p.WaitForExit()
    $script:status = -1
  }
  $script:out = $outTask.Result
  $script:err = $errTask.Result
}

function Invoke-Wait([string[]]$arguments) {
  Invoke-Child $hostExe (@('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script:waitUnderTest) + $arguments) '' $script:waitDir
}

# --- Verdicts ---------------------------------------------------------------

$script:failed = $false

function Show([string]$text) {
  # A printed value on one line, with CR and LF visible.
  return $text.Replace("`r", '\r').Replace("`n", '\n')
}

function Verdict([string]$label, [bool]$ok) {
  if ($ok) { $result = 'PASS' } else { $result = 'FAIL'; $script:failed = $true }
  Say ('{0}  {1,-62} exit {2}, printed "{3}"' -f $result, $label, $script:status, (Show $script:out))
  if (-not $ok -and $script:err -ne '') { Say ('      stderr: ' + (Show $script:err)) }
}

function Skip([string]$label, [string]$reason) {
  Say ('SKIP  {0,-62} {1}' -f $label, $reason)
}

function Write-Text([string]$path, [string]$text) {
  [System.IO.File]::WriteAllText($path, $text, $utf8)
}

# One usage line on stderr, nothing on stdout, exit 2.
function Test-Usage {
  $lines = @($script:err.Split("`n") | Where-Object { $_ -ne '' })
  return ($script:status -eq 2 -and $script:out -eq '' -and $lines.Count -eq 1 -and $lines[0] -clike 'usage: *')
}

try {

# --- The Doorbell wait ------------------------------------------------------

$script:waitDir = Join-Path $root 'wait'
[void](New-Item -ItemType Directory -Path $script:waitDir)
$script:waitUnderTest = $WaitScript

$both = "10:00:00 to: Orchestrator VDD Planner: .scratch/feat/ ready, round 1. Read spec.md and issues/.`n" +
  "10:01:00 to: Planner VDD Plan-Reviewer: PLAN-REVIEW.md written, round 1: 0 blocker, 1 major, 0 minor. Read it.`n" +
  "10:02:00 to: Orchestrator VDD Planner: .scratch/feat/ revised, round 2. Read spec.md and issues/.`n" +
  "10:03:00 to: Orchestrator VDD Planner: .scratch/feat/ revised, round 3. Read spec.md and issues/.`n" +
  "not a ring to: Orchestrator x`n" +
  "10:04:00 to: Coder VDD Planner: nothing.`n" +
  "10:05:00 to: planner VDD Plan-Reviewer: lower case Role.`n" +
  "10:06:00 TO: Planner VDD Plan-Reviewer: upper case address.`n" +
  "10:07:00 to: ORCHESTRATOR VDD Planner: upper case Role.`n"
Write-Text (Join-Path $script:waitDir 'doorbells') $both

Invoke-Wait @('missing', 'Planner')
Verdict 'W1 count, missing file: 0' ($script:status -eq 0 -and $script:out -eq "0`n" -and $script:err -eq '')

Invoke-Wait @('doorbells', 'Orchestrator')
Verdict 'W2 count, both Roles in the file: Orchestrator lines only' ($script:status -eq 0 -and $script:out -eq "3`n")

Invoke-Wait @('doorbells', 'Planner')
Verdict 'W3 count, both Roles in the file: Planner lines only' ($script:status -eq 0 -and $script:out -eq "1`n")

$usageCases = @(
  @('W4 usage: one argument', @('doorbells')),
  @('W5 usage: four arguments', @('doorbells', 'Planner', '0', '0')),
  @('W6 usage: Role Coder', @('doorbells', 'Coder')),
  @('W7 usage: Role planner, lower case', @('doorbells', 'planner')),
  @('W8 usage: armed count empty', @('doorbells', 'Planner', '')),
  @('W9 usage: armed count 00', @('doorbells', 'Planner', '00')),
  @('W10 usage: armed count 01', @('doorbells', 'Planner', '01')),
  @('W11 usage: armed count -1', @('doorbells', 'Planner', '-1')),
  @('W12 usage: armed count 1a', @('doorbells', 'Planner', '1a'))
)
foreach ($case in $usageCases) {
  Invoke-Wait $case[1]
  Verdict $case[0] (Test-Usage)
}

$expected = "10:02:00 to: Orchestrator VDD Planner: .scratch/feat/ revised, round 2. Read spec.md and issues/.`n" +
  "10:03:00 to: Orchestrator VDD Planner: .scratch/feat/ revised, round 3. Read spec.md and issues/.`n"
Invoke-Wait @('doorbells', 'Orchestrator', '1')
Verdict 'W13 wait, lines beyond the count: printed oldest first' ($script:status -eq 0 -and $script:out -ceq $expected)

Write-Text (Join-Path $script:waitDir 'crlf') ("10:00:00 to: Planner first`r`n10:01:00 to: Planner second`r`n")
Invoke-Wait @('crlf', 'Planner', '0')
Verdict 'W14 wait, CRLF lines: printed with no CR' ($script:status -eq 0 -and $script:out -ceq "10:00:00 to: Planner first`n10:01:00 to: Planner second`n")

# The real timeout is 45 minutes, so this case runs a scratch copy whose
# timeout is 0: it reads once and times out.
$shortWait = Join-Path $script:waitDir 'doorbell-wait-short.ps1'
$waitText = [System.IO.File]::ReadAllText($script:waitUnderTest)
$shortText = $waitText.Replace('$timeoutSeconds = 2700', '$timeoutSeconds = 0')
Write-Text $shortWait $shortText
$script:waitUnderTest = $shortWait
Invoke-Wait @('doorbells', 'Planner', '1')
$script:waitUnderTest = $WaitScript
Verdict 'W15 wait, nothing beyond the count at timeout 0: TIMEOUT' ($shortText -cne $waitText -and $script:status -eq 0 -and $script:out -ceq "TIMEOUT`n")

# A file that exists and cannot be read.
$denied = Join-Path $script:waitDir 'denied'
Write-Text $denied $both
if ($onWindows) {
  $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  [void](& icacls.exe $denied /deny ($user + ':(R)'))
} else {
  & chmod 000 $denied
}
$readable = $true
try { [void][System.IO.File]::ReadAllText($denied) } catch { $readable = $false }
if ($readable) {
  Skip 'W16 count, file denied: exit 1' 'this user can read a denied file'
  Skip 'W17 wait, file denied: exit 1' 'this user can read a denied file'
} else {
  Invoke-Wait @('denied', 'Planner')
  Verdict 'W16 count, file denied: exit 1, message on stderr' ($script:status -eq 1 -and $script:out -eq '' -and $script:err -ne '')
  Invoke-Wait @('denied', 'Planner', '0')
  Verdict 'W17 wait, file denied: exit 1, message on stderr' ($script:status -eq 1 -and $script:out -eq '' -and $script:err -ne '')
}
if ($onWindows) {
  [void](& icacls.exe $denied /remove:d $user)
} else {
  & chmod 644 $denied
}

# --- Parity with doorbell-wait.sh -------------------------------------------

$sh = Get-Command sh -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$mixed = "10:00:00 to: Orchestrator one`n" +
  "10:01:00 to: Planner two`r`n" +
  "10:02:00 to: Orchestrator three`r`n" +
  "10:03:00 to: Planner four`n" +
  "10:04:00 to: Orchestrator five`n" +
  "10:05:00 to: Planner six`r`n" +
  "10:06:00 to: planner seven`n" +
  "10:07:00 to: orchestrator eight`r`n"
Write-Text (Join-Path $script:waitDir 'mixed') $mixed
$parityCases = @(
  @('P1 parity, count Planner', @('mixed', 'Planner')),
  @('P2 parity, count Orchestrator', @('mixed', 'Orchestrator')),
  @('P3 parity, wait Planner armed at 1', @('mixed', 'Planner', '1')),
  @('P4 parity, wait Orchestrator armed at 0', @('mixed', 'Orchestrator', '0'))
)
foreach ($case in $parityCases) {
  if ($onWindows -or $null -eq $sh) {
    # A Windows checkout carries the .sh with CRLF, which sh cannot run.
    Skip $case[0] 'needs sh and an LF checkout of doorbell-wait.sh'
    continue
  }
  Invoke-Child $sh.Source (@($waitSh) + $case[1]) '' $script:waitDir
  $shStatus = $script:status
  $shOut = $script:out
  Invoke-Wait $case[1]
  $ok = $shStatus -eq $script:status -and $shOut.Replace("`r", '') -ceq $script:out.Replace("`r", '') -and -not $script:out.Contains("`r") -and $script:out -ne ''
  Verdict $case[0] $ok
}

} finally {
  Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

if ($script:failed) { exit 1 }
exit 0
