# backend/start.ps1 — quick start (assumes .\dev.ps1 was already run once)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "No .venv found. Run .\dev.ps1 first to set everything up." -ForegroundColor Red
    exit 1
}

Write-Host "Starting backend on http://localhost:8000  (docs: /docs)" -ForegroundColor Cyan
& $venvPy -m uvicorn app.main:app --reload
