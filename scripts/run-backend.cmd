@echo off
REM Runs the AudienceIQ backend in its own window.
cd /d "%~dp0..\backend"

if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
)

python main.py

echo.
echo Backend stopped. Press any key to close this window.
pause >nul
