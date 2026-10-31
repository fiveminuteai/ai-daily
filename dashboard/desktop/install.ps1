# Installs the Five Minute AI desktop app for this Windows user: a Start-menu entry and a desktop shortcut that start
# the app from THIS folder (no admin rights, nothing downloaded). Run again after moving the folder.
#   powershell -ExecutionPolicy Bypass -File dashboard\desktop\install.ps1
# Remove with uninstall.ps1. Needs Node.js 18+ on PATH (https://nodejs.org).
param([switch]$NoDesktop)
$ErrorActionPreference = "Stop"
$dir = $PSScriptRoot
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js is needed: install the LTS from https://nodejs.org, then run this again." }
$major = [int]((node --version).TrimStart("v").Split(".")[0])
if ($major -lt 18) { throw "Node.js 18 or newer is needed (found $(node --version))." }

$shell = New-Object -ComObject WScript.Shell
$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Five Minute AI"
New-Item -ItemType Directory -Force $startMenu | Out-Null

function New-Shortcut($path, $launchArgs, $desc) {
    $s = $shell.CreateShortcut($path)
    $s.TargetPath = "$env:WINDIR\System32\wscript.exe"
    $s.Arguments = "`"$dir\launch.vbs`" $launchArgs".Trim()
    $s.WorkingDirectory = $dir
    $s.IconLocation = "$dir\fiveminuteai.ico,0"
    $s.Description = $desc
    $s.Save()
}

New-Shortcut (Join-Path $startMenu "Five Minute AI.lnk") "" "Five Minute AI control app (dry run: buttons show what they would do)"
New-Shortcut (Join-Path $startMenu "Five Minute AI (live).lnk") "--live" "Five Minute AI control app: buttons really commit and start workflows"
if (-not $NoDesktop) {
    New-Shortcut (Join-Path ([Environment]::GetFolderPath("Desktop")) "Five Minute AI.lnk") "" "Five Minute AI control app"
}
Write-Host "Installed. Start it from the Start menu: Five Minute AI." -ForegroundColor Green
Write-Host "App data (roadmap, notes): $env:APPDATA\FiveMinuteAI   Secrets: Windows Credential Manager (FiveMinuteAI/*)"
