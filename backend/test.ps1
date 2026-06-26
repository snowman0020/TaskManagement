# backend/test.ps1 — run the in-process smoke + HTTP integration tests (no MongoDB needed)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "No .venv found. Run .\dev.ps1 first." -ForegroundColor Red
    exit 1
}

& $venvPy -m pip install -q -r requirements-dev.txt
Write-Host "`n== smoke_test ==" -ForegroundColor Cyan
& $venvPy tests\smoke_test.py
Write-Host "`n== http_test ==" -ForegroundColor Cyan
& $venvPy tests\http_test.py
