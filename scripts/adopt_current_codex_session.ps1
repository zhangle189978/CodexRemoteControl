param(
    [string]$ConfigPath = "config/local.toml",
    [string]$CodexHome = "$env:USERPROFILE\.codex",
    [int]$Index = 1,
    [string]$UserId = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$argsList = @(
    "-m", "codex_remote_control.adopt_session",
    "--config", $ConfigPath,
    "--codex-home", $CodexHome,
    "--index", "$Index"
)

if ($UserId) {
    $argsList += @("--user-id", $UserId)
}

& .\.venv\Scripts\python.exe @argsList
