# Removes the shortcuts install.ps1 made. Keeps your roadmap and notes (%APPDATA%\FiveMinuteAI) and your stored
# credentials unless you pass -RemoveData / -RemoveCredentials.
param([switch]$RemoveData, [switch]$RemoveCredentials)
$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Five Minute AI"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $startMenu
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path ([Environment]::GetFolderPath("Desktop")) "Five Minute AI.lnk")
if ($RemoveData) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$env:APPDATA\FiveMinuteAI", "$env:LOCALAPPDATA\FiveMinuteAI"
}
if ($RemoveCredentials) {
    foreach ($n in "github", "zoho") { cmdkey /delete:FiveMinuteAI/$n 2>$null | Out-Null }
}
Write-Host "Five Minute AI shortcuts removed."
