param([string]$Distribution = 'Ubuntu')

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeDirectory = Join-Path $projectRoot '.deployment'
$pidFile = Join-Path $runtimeDirectory 'wsl-keeper.pid'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null

if (Test-Path -LiteralPath $pidFile) {
    $keeperId = 0
    if ([int]::TryParse((Get-Content -LiteralPath $pidFile -Raw).Trim(), [ref]$keeperId)) {
        $existing = Get-CimInstance Win32_Process -Filter "ProcessId = $keeperId"
        if ($existing -and $existing.Name -eq 'wsl.exe' -and
            $existing.CommandLine -like "* $Distribution --exec /bin/sleep infinity*") {
            Write-Output "WSL runtime is already held by process $keeperId."
            exit 0
        }
    }
}

if ($Distribution -notmatch '^[a-zA-Z0-9_.-]+$') {
    throw 'Distribution must be a simple WSL distribution name.'
}
$keeper = Start-Process -FilePath wsl.exe -ArgumentList @(
    '-d', $Distribution, '--exec', '/bin/sleep', 'infinity'
) -WindowStyle Hidden -PassThru
$keeper.Id | Set-Content -LiteralPath $pidFile
Write-Output "WSL runtime is held by hidden process $($keeper.Id). Run this script again after Windows restarts."
