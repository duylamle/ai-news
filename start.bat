@echo off
REM AI News local viewer — double-click to open feed in browser
REM Auto pulls latest data from GitHub on startup

set PORT=8765
cd /d "%~dp0"

echo [1/3] Pulling latest data from GitHub...
git pull --rebase origin main 2>&1
echo.

echo [2/3] Starting local server on http://localhost:%PORT%
echo Press Ctrl+C to stop when done.
echo.

REM Background auto-pull every 30 minutes while server runs
start /b "" cmd /c "for /l %%i in (1,1,9999) do (timeout /t 1800 /nobreak >nul && git pull --rebase origin main >nul 2>&1)"

echo [3/3] Opening browser...
start "" "http://localhost:%PORT%/index.html"
python scripts\server.py --port %PORT%
