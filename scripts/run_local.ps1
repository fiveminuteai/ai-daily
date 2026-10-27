# Laptop fallback: write today's post with local Ollama (qwen2.5:14b), then push it so GitHub deploys it.
# Use this on a day the cloud run skipped, or if you'd rather not use a hosted model at all.
#
#   powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1            # generate + push
#   powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1 -NoPush    # generate only, look first
#
# Needs: Ollama running (ollama serve) with qwen2.5:14b pulled. On a CPU-only laptop a post takes
# roughly 20-60 minutes.
param([switch]$NoPush, [string]$Date = "")

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
New-Item -ItemType Directory -Force logs | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$args_ = @("-m", "fma", "daily", "--provider", "ollama")
if ($Date) { $args_ += @("--date", $Date) }

git pull --ff-only
python @args_ 2>&1 | Tee-Object -FilePath "logs\local-$stamp.log"
$last = Get-Content "logs\local-$stamp.log" -Tail 1
if ($last -notmatch "^PUBLISHED") { Write-Host "No post today: $last"; exit 0 }

python -m fma build --base-url "http://localhost:8000/" | Out-Null
Write-Host "Built a local preview in public\ (python -m http.server 8000 -d public)."
if ($NoPush) { Write-Host "Not pushing (-NoPush). Commit and push content\ and data\ when you're happy."; exit 0 }

git add content data
git commit -m "Post for $(Get-Date -Format yyyy-MM-dd) (local Ollama)"
git push
Write-Host "Pushed. The Deploy site workflow will publish it in about a minute."
