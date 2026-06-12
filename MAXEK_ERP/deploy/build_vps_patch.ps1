# Build a small ZIP for WinSCP upload to /var/www/maxek-erp-flask/
# Usage: powershell -ExecutionPolicy Bypass -File deploy/build_vps_patch.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Stamp = Get-Date -Format "yyyyMMdd_HHmm"
$OutDir = Join-Path $Root "deploy\patch_staging_$Stamp"
$ZipPath = Join-Path $Root "deploy\dist\vps-patch-maxek-erp-flask-$Stamp.zip"

$PatchFiles = @(
    "app.py",
    "workflow_service.py",
    "wsgi.py",
    "templates\accounts_book.html",
    "templates\staff.html",
    "templates\workers.html",
    "static\js\app.js",
    "deploy\migrate_production.py",
    "deploy\VPS_PATCH_maxek-erp-flask.txt"
)

New-Item -ItemType Directory -Force -Path $OutDir, (Split-Path $ZipPath) | Out-Null

foreach ($rel in $PatchFiles) {
    $src = Join-Path $Root $rel
    if (-not (Test-Path $src)) {
        Write-Error "Missing patch file: $rel"
    }
    $dest = Join-Path $OutDir $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    Copy-Item $src $dest -Force
}

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path "$OutDir\*" -DestinationPath $ZipPath -CompressionLevel Optimal
Remove-Item -Recurse -Force $OutDir -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "VPS patch ZIP ready:"
Write-Host "  $ZipPath"
Write-Host ""
Write-Host "WinSCP: extract into /var/www/maxek-erp-flask/ (merge folders)"
Write-Host "Then run SSH steps in deploy/VPS_PATCH_maxek-erp-flask.txt"
