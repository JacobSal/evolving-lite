<#
.SYNOPSIS
  Evolving Lite - post-clone setup for Windows (PowerShell).

.DESCRIPTION
  Cross-platform companion to setup.sh for users who do not run Git Bash.
  hooks/hooks.json ships with ${CLAUDE_PLUGIN_ROOT} placeholders that Claude Code
  substitutes itself, so this script only VALIDATES the file (it never rewrites
  paths). Optionally provisions the Windows venv + kairn-ai, then runs the Doctor.

.PARAMETER SetupVenv
  Also create ./venv (at the repo root, two levels up from the plugin) and
  pip install kairn-ai into it. The kairn MCP server expects ./venv/Scripts/kairn.exe.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\setup.ps1
  powershell -ExecutionPolicy Bypass -File .\setup.ps1 -SetupVenv
#>
[CmdletBinding()]
param(
    [switch]$SetupVenv
)

$ErrorActionPreference = 'Stop'
$PluginRoot = $PSScriptRoot
$HooksFile  = Join-Path $PluginRoot 'hooks\hooks.json'

Write-Host "Evolving Lite setup (PowerShell)"
Write-Host "Plugin root: $PluginRoot"

if (-not (Test-Path $HooksFile)) {
    Write-Error "hooks.json not found at $HooksFile"
    exit 1
}

# Resolve a Python interpreter (python, then py launcher, then python3).
$Py = $null
foreach ($cand in @('python', 'py', 'python3')) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($cmd) { $Py = $cmd.Source; break }
}
if (-not $Py) {
    Write-Error "No Python interpreter on PATH (need 3.10+)."
    exit 1
}

# Validate hooks.json: parseable JSON, no merge markers, placeholder present.
$raw = Get-Content -Raw -Encoding UTF8 $HooksFile
if ($raw -match '<<<<<<<' -or $raw -match '>>>>>>>') {
    Write-Error "hooks.json contains unresolved merge-conflict markers."
    exit 1
}
try {
    $null = $raw | ConvertFrom-Json
} catch {
    Write-Error "hooks.json is not valid JSON: $_"
    exit 1
}
if ($raw -notmatch '\$\{CLAUDE_PLUGIN_ROOT\}') {
    Write-Warning "hooks.json has no `${CLAUDE_PLUGIN_ROOT}` placeholder; paths may be hardcoded."
} else {
    Write-Host "hooks.json: valid JSON, portable placeholders present."
}

# Optional: provision the Windows venv + kairn-ai at the repo root.
$RepoRoot = (Resolve-Path (Join-Path $PluginRoot '..\..\..')).Path
$VenvDir  = Join-Path $RepoRoot 'venv'
if ($SetupVenv) {
    if (-not (Test-Path (Join-Path $VenvDir 'Scripts\python.exe'))) {
        Write-Host "Creating venv at $VenvDir ..."
        & $Py -m venv $VenvDir
    }
    $VenvPy = Join-Path $VenvDir 'Scripts\python.exe'
    Write-Host "Installing kairn-ai into venv ..."
    & $VenvPy -m pip install --quiet --upgrade pip
    & $VenvPy -m pip install --quiet kairn-ai
    & (Join-Path $VenvDir 'Scripts\kairn.exe') --version
} else {
    Write-Host ""
    Write-Host "Kairn (memory-layer prerequisite) not provisioned. To set it up:"
    Write-Host "  .\setup.ps1 -SetupVenv"
    Write-Host "The kairn MCP server is configured to use .\venv\Scripts\kairn.exe."
}

# Run the Self-Star Doctor (re-runnable any time via /health). -X utf8 so the
# cp1252 console codec never breaks UTF-8 file reads or the board glyphs.
Write-Host ""
Write-Host "Running the Self-Star Doctor..."
$env:CLAUDE_PLUGIN_ROOT = $PluginRoot
& $Py -X utf8 (Join-Path $PluginRoot 'scripts\doctor.py')
