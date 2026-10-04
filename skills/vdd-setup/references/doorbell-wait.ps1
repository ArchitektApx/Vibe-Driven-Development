# doorbell-wait.ps1: the Doorbell wait of the VDD Planner and Orchestrator,
# for native Windows.
#
# The Planner and the Orchestrator of Vibe Driven Development run this script
# on native Windows, where a Harness rings through the Doorbell file. It is
# the PowerShell form of doorbell-wait.sh and keeps its contract. It reads the
# Doorbell file and writes nothing. Run it, from any shell, as
#
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File doorbell-wait.ps1 ...
#
# It runs on Windows PowerShell 5.1 and on PowerShell 7. It ships at mode 644
# and is never made executable.
#
# It ships once, in the vdd-setup skill's references. Setup installs a copy
# into %LOCALAPPDATA%\vdd\ on native Windows, and the Roles run that copy.
#
# Two forms, chosen by the number of arguments:
#
#   doorbell-wait.ps1 <Doorbell file> <Role>
#     The count. Prints the number of lines in the Doorbell file addressed to
#     <Role> and exits 0. A missing Doorbell file counts as 0.
#
#   doorbell-wait.ps1 <Doorbell file> <Role> <armed count>
#     The wait. Reads the Doorbell file every 10 seconds. When the number of
#     lines addressed to <Role> rises above <armed count>, prints the lines
#     beyond <armed count>, oldest first, and exits 0. After 2700 seconds
#     without one, prints TIMEOUT and exits 0. Prints nothing until it exits.
#
# A line is addressed to <Role> when it starts with "HH:MM:SS to: <Role> ".
# <Role> is Planner or Orchestrator, and <armed count> is a non-negative
# integer. A wrong number of arguments or a bad value prints one usage line
# to stderr and exits 2. A Doorbell file that exists but cannot be read exits
# 1, after a message on stderr.
#
# Where it differs from doorbell-wait.sh, it does so for Windows:
# - It opens the Doorbell file shared for reading and writing, so a ring by
#   the other Session lands while this script reads.
# - A read that hits a sharing violation is retried: the count tries 5 times,
#   200 ms apart, before it treats the file as unreadable, and the wait reads
#   again at its next poll.
# - It accepts LF and CRLF lines, and prints each line with every CR removed
#   and ending in LF.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# How often the wait reads the Doorbell file, and how long it waits in all.
$pollSeconds = 10
$timeoutSeconds = 2700

# The script's arguments, taken before any function shadows $args.
$argv = @($args)

function Exit-Usage {
  [Console]::Error.WriteLine('usage: powershell.exe -NoProfile -ExecutionPolicy Bypass -File doorbell-wait.ps1 <Doorbell file> Planner|Orchestrator [<armed count>]')
  exit 2
}

if ($argv.Count -ne 2 -and $argv.Count -ne 3) { Exit-Usage }

$doorbellArg = [string]$argv[0]
$role = [string]$argv[1]

# Case-sensitive, as the sh form's case statement is.
if ($role -cne 'Planner' -and $role -cne 'Orchestrator') { Exit-Usage }

[long]$armedCount = 0
if ($argv.Count -eq 3) {
  # Digits only, 0 or no leading zero. [0-9] admits no other Unicode digit,
  # and \z anchors at the very end, where $ would allow a trailing newline.
  $armedText = [string]$argv[2]
  if ($armedText -cnotmatch '\A(0|[1-9][0-9]*)\z') { Exit-Usage }
  if (-not [long]::TryParse($armedText, [ref]$armedCount)) { Exit-Usage }
}

# The address, written once for both forms: the time, then "to: <Role> ".
$address = '\A[0-9][0-9]:[0-9][0-9]:[0-9][0-9] to: ' + $role + ' '

# The path arrives relative and with forward slashes. .NET resolves a
# relative path against the process directory, which can differ from the
# PowerShell location, so it is resolved here first.
$doorbellPath = ''
if ($doorbellArg -ne '') {
  $doorbellPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($doorbellArg)
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
$stdout = [Console]::OpenStandardOutput()

function Write-Lines($lines) {
  # UTF-8 bytes with LF endings straight to stdout, whatever the console's
  # code page.
  $text = (@($lines) -join "`n") + "`n"
  $bytes = $utf8.GetBytes($text)
  $stdout.Write($bytes, 0, $bytes.Length)
  $stdout.Flush()
}

function Exit-Unreadable($message) {
  [Console]::Error.WriteLine('doorbell-wait.ps1: ' + $doorbellArg + ': ' + $message)
  exit 1
}

# Reads the Doorbell file into $script:addressed, the lines addressed to the
# Role with every CR removed. Returns $true when it read the file or the file
# is missing, $false on a sharing violation. Exits 1 on any other read error.
function Read-Addressed {
  $script:addressed = New-Object 'System.Collections.Generic.List[string]'
  if ($doorbellPath -eq '') { return $true }
  if (-not [System.IO.File]::Exists($doorbellPath) -and -not [System.IO.Directory]::Exists($doorbellPath)) {
    return $true
  }
  $text = $null
  try {
    $stream = New-Object System.IO.FileStream($doorbellPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
      $reader = New-Object System.IO.StreamReader($stream, $utf8)
      $text = $reader.ReadToEnd()
      $reader.Dispose()
    } finally {
      $stream.Dispose()
    }
  } catch {
    $e = $_.Exception
    while ($null -ne $e.InnerException) { $e = $e.InnerException }
    if ($e -is [System.IO.FileNotFoundException] -or $e -is [System.IO.DirectoryNotFoundException]) {
      return $true
    }
    if ($e -is [System.IO.IOException]) {
      # 32 is ERROR_SHARING_VIOLATION and 33 ERROR_LOCK_VIOLATION.
      $code = $e.HResult -band 0xFFFF
      if ($code -eq 32 -or $code -eq 33) { return $false }
    }
    Exit-Unreadable $e.Message
  }
  foreach ($line in $text.Split([char]10)) {
    if ($line -cmatch $address) {
      $script:addressed.Add($line.Replace([string][char]13, ''))
    }
  }
  return $true
}

if ($argv.Count -eq 2) {
  for ($try = 1; $try -le 5; $try++) {
    if (Read-Addressed) {
      Write-Lines ([string]$script:addressed.Count)
      exit 0
    }
    if ($try -lt 5) { Start-Sleep -Milliseconds 200 }
  }
  Exit-Unreadable 'the file stays locked by another process'
}

[long]$waited = 0
while ($true) {
  # A poll that hit a sharing violation counts as unread.
  if (Read-Addressed) {
    $count = $script:addressed.Count
    if ($count -gt $armedCount) {
      Write-Lines ($script:addressed.GetRange([int]$armedCount, $count - [int]$armedCount))
      exit 0
    }
  }
  if ($waited -ge $timeoutSeconds) {
    Write-Lines 'TIMEOUT'
    exit 0
  }
  Start-Sleep -Seconds $pollSeconds
  $waited += $pollSeconds
}
