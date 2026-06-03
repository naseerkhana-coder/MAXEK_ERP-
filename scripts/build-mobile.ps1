# Build React UI and sync into Capacitor Android project
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$npm = "C:\Program Files\nodejs\npm.cmd"
if (-not (Test-Path $npm)) { $npm = "npm" }

Set-Location (Join-Path $root "frontend")
& $npm install
& $npm run build

Set-Location (Join-Path $root "mobile")
& $npm install
& $npm exec cap sync android

Write-Host ""
Write-Host "Done. Open mobile\android in Android Studio and Run."
