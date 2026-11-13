@echo off
setlocal
title AudienceIQ Launcher
cd /d "%~dp0"

echo ============================================
echo   AudienceIQ - Start Application
echo ============================================
echo.

REM ---------- Check prerequisites ----------
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found on your PATH. Install Python 3.9+ and try again.
  pause
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js was not found on your PATH. Install Node.js 18+ and try again.
  pause
  exit /b 1
)

REM ---------- Backend dependency check ----------
if exist "backend\venv\Scripts\python.exe" (
  set "PYEXE=backend\venv\Scripts\python.exe"
) else (
  set "PYEXE=python"
)

"%PYEXE%" -c "import fastapi, uvicorn, bcrypt" >nul 2>nul
if errorlevel 1 (
  echo [SETUP] Installing backend dependencies...
  "%PYEXE%" -m pip install -r backend\requirements.txt
)

REM ---------- Frontend dependency check ----------
if not exist "frontend\node_modules" (
  echo [SETUP] Installing frontend dependencies...
  pushd frontend
  call npm install
  popd
)

REM ---------- Seed demo data (only when the database is empty) ----------
if not exist "backend\audienceiq.db" (
  echo [SEED ] Preparing demo data...
  "%PYEXE%" "backend\seed_demo.py"
)

REM ---------- Launch ----------
echo [RUN ] Starting backend on http://127.0.0.1:8000
start "AudienceIQ Backend" "%~dp0scripts\run-backend.cmd"

echo [RUN ] Starting frontend on http://localhost:3001
start "AudienceIQ Frontend" "%~dp0scripts\run-frontend.cmd"

echo.
echo [OK  ] Both servers are starting in separate windows.
echo [OK  ] Open your browser at: http://localhost:3001
echo.
timeout /t 6 /nobreak >nul
start "" http://localhost:3001

endlocal
