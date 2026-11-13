# AudienceIQ - PowerShell launcher
# Run both servers from one terminal:  .\start.ps1
# Or keep them in separate windows:  .\start.ps1 -Separate

param(
    [switch]$Separate
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  AudienceIQ - Start Application" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ---------- Prerequisites ----------
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python not found on PATH. Install Python 3.9+." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Node.js not found on PATH. Install Node.js 18+." -ForegroundColor Red
    exit 1
}

# ---------- Backend deps ----------
$venvPy = Join-Path $root "backend\venv\Scripts\python.exe"
if (Test-Path $venvPy) { $py = $venvPy } else { $py = "python" }

& $py -c "import fastapi, uvicorn, bcrypt" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[SETUP] Installing backend dependencies..." -ForegroundColor Yellow
    & $py -m pip install -r (Join-Path $root "backend\requirements.txt")
}

# ---------- Frontend deps ----------
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Write-Host "[SETUP] Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location (Join-Path $root "frontend")
    npm install
    Pop-Location
}

# ---------- Demo data ----------
Write-Host "[SEED ] Preparing demo data (skipped if already present)..." -ForegroundColor Yellow
& $py (Join-Path $root "backend\seed_demo.py")

if ($Separate) {
    Write-Host "[RUN ] Backend  -> http://127.0.0.1:8000" -ForegroundColor Green
    Start-Process cmd -ArgumentList '/k', "`"$root\scripts\run-backend.cmd`"" -Title "AudienceIQ Backend"
    Write-Host "[RUN ] Frontend -> http://localhost:3001" -ForegroundColor Green
    Start-Process cmd -ArgumentList '/k', "`"$root\scripts\run-frontend.cmd`"" -Title "AudienceIQ Frontend"
    Write-Host ""
    Write-Host "[OK  ] Open http://localhost:3001 in your browser." -ForegroundColor Cyan
    exit 0
}

# ---------- Run both in this window ----------
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

$backendJob = Start-Job -Name "AudienceIQ-Backend" -WorkingDirectory $backendDir -ScriptBlock {
    param($exe)
    if ($exe -eq "python") { & python main.py } else { & $exe main.py }
} -ArgumentList $py

$frontendJob = Start-Job -Name "AudienceIQ-Frontend" -WorkingDirectory $frontendDir -ScriptBlock {
    & npm run dev
}

Write-Host "[RUN ] Backend  -> http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "[RUN ] Frontend -> http://localhost:3001" -ForegroundColor Green
Write-Host "[RUN ] Press Ctrl+C to stop both servers." -ForegroundColor Yellow
Write-Host ""

try {
    while ($backendJob.State -eq "Running" -or $frontendJob.State -eq "Running") {
        Receive-Job -Job $backendJob -ErrorAction SilentlyContinue
        Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    Receive-Job -Job $backendJob -ErrorAction SilentlyContinue
    Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue
}
finally {
    Stop-Job -Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob, $frontendJob -Force -ErrorAction SilentlyContinue
}
