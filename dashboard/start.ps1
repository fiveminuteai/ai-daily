# Starts the control dashboard on this laptop and opens it: http://127.0.0.1:8788/
#
#   powershell -ExecutionPolicy Bypass -File dashboard\start.ps1          (dry run: buttons only show their request)
#   powershell -ExecutionPolicy Bypass -File dashboard\start.ps1 -Live    (buttons really commit / start workflows)
#
# The GitHub token is taken from $env:GITHUB_TOKEN, else from the GitHub CLI's login (gh auth token), else asked for.
# It lives only in this window's memory: never written to a file. Close the window to stop the dashboard.
param([switch]$Live, [int]$Port = 8788)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js is needed: https://nodejs.org (LTS)" }
if (-not $env:GITHUB_TOKEN) {
    if (Get-Command gh -ErrorAction SilentlyContinue) { $env:GITHUB_TOKEN = (gh auth token 2>$null) }
    if (-not $env:GITHUB_TOKEN) {
        $s = Read-Host -AsSecureString "GitHub token (fine-grained, fiveminuteai/ai-daily only)"
        $env:GITHUB_TOKEN = [System.Net.NetworkCredential]::new("", $s).Password
    }
}
$env:DRY_RUN = if ($Live) { "0" } else { "1" }
$env:PORT = "$Port"
$env:LOCAL_FILES = ".."          # files not on main yet (this branch's data/) come from this checkout

Start-Job -ScriptBlock { param($p) Start-Sleep 2; Start-Process "http://127.0.0.1:$p/" } -ArgumentList $Port | Out-Null
node dev-server.mjs
