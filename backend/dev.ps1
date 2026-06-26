# backend/dev.ps1 — one-click: create venv (Python 3.12) + install + run backend
# Usage:  .\dev.ps1     (from the backend folder, or run the root .\dev.ps1)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== TaskFlow backend setup ==" -ForegroundColor Cyan

# 1. Pick a compatible interpreter (3.12/3.11) — avoids the Python 3.14 pydantic-core build error
$pyVer = $null
foreach ($v in @("3.12", "3.11")) {
    try {
        & py "-$v" --version 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $pyVer = $v; break }
    } catch {}
}

# 2. Create the venv if missing
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    if ($pyVer) {
        Write-Host "Creating .venv with Python $pyVer ..." -ForegroundColor Green
        & py "-$pyVer" -m venv .venv
    } else {
        Write-Host "Python 3.12/3.11 not found via the 'py' launcher." -ForegroundColor Yellow
        Write-Host "Falling back to 'python' — if it is 3.13+ the install may fail." -ForegroundColor Yellow
        Write-Host "Recommended: install Python 3.12 from https://www.python.org/downloads/" -ForegroundColor Yellow
        & python -m venv .venv
    }
}

# 3. Install dependencies (call the venv's python directly — no activation needed)
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r requirements.txt

# 4. Seed a local .env on first run
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example" -ForegroundColor Green
}

# 5. Friendly MongoDB reminder
Write-Host "`nMake sure MongoDB is running (e.g. docker run -d -p 27017:27017 --name tm-mongo mongo:7)" -ForegroundColor DarkGray
Write-Host "Starting backend on http://localhost:8000  (docs: /docs)`n" -ForegroundColor Cyan

# 6. Run
& $venvPy -m uvicorn app.main:app --reload
