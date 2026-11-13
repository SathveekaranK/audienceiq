@echo off
REM Runs the AudienceIQ frontend (Vite dev server) in its own window.
cd /d "%~dp0..\frontend"

npm run dev

echo.
echo Frontend stopped. Press any key to close this window.
pause >nul
