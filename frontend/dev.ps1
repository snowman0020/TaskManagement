# frontend/dev.ps1 — install deps (first run) + start the Vite dev server
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Green
    npm install
}

Write-Host "Starting frontend on http://localhost:5173" -ForegroundColor Cyan
npm run dev
