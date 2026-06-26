# dev.ps1 — one-click local dev: starts MongoDB (Docker), backend and frontend
# Opens the backend and frontend each in their own PowerShell window.
# Usage:  .\dev.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "== TaskFlow — local dev ==" -ForegroundColor Cyan

# 1. Ensure MongoDB is up (via Docker, if available)
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    $running = docker ps --filter "name=tm-mongo" --format "{{.Names}}" 2>$null
    if ($running -ne "tm-mongo") {
        Write-Host "Starting MongoDB container 'tm-mongo'..." -ForegroundColor Green
        docker start tm-mongo 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            docker run -d -p 27017:27017 --name tm-mongo mongo:7 | Out-Null
        }
    } else {
        Write-Host "MongoDB container already running." -ForegroundColor DarkGray
    }
} else {
    Write-Host "Docker not found — make sure MongoDB is running on localhost:27017." -ForegroundColor Yellow
}

# 2. Launch backend and frontend in separate windows
Write-Host "Opening backend window (http://localhost:8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$root\backend\dev.ps1"

Write-Host "Opening frontend window (http://localhost:5173)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "$root\frontend\dev.ps1"

Write-Host "`nDone. Open http://localhost:5173 and log in with admin / admin1234" -ForegroundColor Cyan
Write-Host "(Tip: 'docker compose up --build' runs the whole stack in containers instead.)" -ForegroundColor DarkGray
