# MAXEK ERP — Build deployment ZIP for WinSCP upload
# Usage: powershell -ExecutionPolicy Bypass -File deploy/build_deploy_package.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Stamp = Get-Date -Format "yyyyMMdd_HHmm"
$ShortHash = (Get-FileHash "app.py" -Algorithm SHA256).Hash.Substring(0, 7).ToLower()
$OutDir = Join-Path $Root "deploy\package_$Stamp"
$ZipName = "maxek-erp-deploy-$ShortHash.zip"
$ZipPath = Join-Path $Root "deploy\dist\$ZipName"
$ManifestPath = Join-Path $Root "deploy\dist\MANIFEST_$ShortHash.txt"

New-Item -ItemType Directory -Force -Path $OutDir, (Split-Path $ZipPath) | Out-Null

$IncludeFiles = @(
    "app.py", "workflow_service.py", "wsgi.py", "requirements.txt"
)

$IncludeDirs = @("templates", "static", "deploy", "tests")

foreach ($f in $IncludeFiles) {
    Copy-Item $f (Join-Path $OutDir $f) -Force
}

foreach ($d in $IncludeDirs) {
    $dest = Join-Path $OutDir $d
    robocopy $d $dest /E /XD __pycache__ .venv venv dist package /XF *.pyc *.pyo *.tmp *.bak *.old | Out-Null
}

# Empty folders for server structure
New-Item -ItemType Directory -Force -Path (Join-Path $OutDir "database"), (Join-Path $OutDir "reports") | Out-Null
"" | Out-File (Join-Path $OutDir "database\.gitkeep") -Encoding ascii -NoNewline
"" | Out-File (Join-Path $OutDir "reports\.gitkeep") -Encoding ascii -NoNewline

# Remove old zip if exists
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path "$OutDir\*" -DestinationPath $ZipPath -CompressionLevel Optimal

# Manifest
$files = Get-ChildItem -Recurse -File $OutDir | Sort-Object FullName
$lines = @(
    "MAXEK ERP Deployment Package",
    "Generated: $(Get-Date -Format o)",
    "Package: $ZipName",
    "App hash (app.py SHA256 prefix): $ShortHash",
    "",
    "UI VERIFICATION MARKERS (must exist on VPS after deploy):",
    "  templates/login.html       -> class maxek-login-v2",
    "  static/css/maxek-login.css -> Login v2 stylesheet (NEW FILE)",
    "  templates/forgot_password.html -> forgot password page (NEW FILE)",
    "  templates/dashboard.html   -> Approval Summary section",
    "  templates/users.html       -> User Settings page",
    "  app.py                     -> APP_VERSION, user_settings route",
    "",
    "FILE LIST ($($files.Count) files):",
    "----------------------------------------"
)
foreach ($f in $files) {
    $rel = $f.FullName.Substring($OutDir.Length + 1).Replace("\", "/")
    $lines += "{0,-55} {1,8}  {2}" -f $rel, $f.Length, $f.LastWriteTime.ToString("yyyy-MM-dd HH:mm")
}
$lines | Out-File $ManifestPath -Encoding utf8

Write-Host ""
Write-Host "=============================================="
Write-Host " DEPLOYMENT PACKAGE READY"
Write-Host " ZIP:      $ZipPath"
Write-Host " Manifest: $ManifestPath"
Write-Host " Files:    $($files.Count)"
Write-Host "=============================================="

# Remove staging dir (best effort)
Remove-Item -Recurse -Force $OutDir -ErrorAction SilentlyContinue
