param(
    [string]$venvName = ".venv"
)

$here = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
Set-Location $here

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found on PATH. Ensure Python 3.8+ is installed." -ForegroundColor Yellow
}

if (-Not (Test-Path $venvName)) {
    python -m venv $venvName
}

$pip = Join-Path $venvName 'Scripts\pip.exe'
& $pip install --upgrade pip
if (Test-Path 'requirements.txt') {
    & $pip install -r requirements.txt
} else {
    & $pip install openpyxl
}

Write-Host "Virtual environment created/updated. Activate with:`" -NoNewline
Write-Host " .\$venvName\Scripts\Activate.ps1`" -ForegroundColor Cyan
