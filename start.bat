@echo off
REM AI News local viewer — double-click to open feed in browser
REM Custom server có /api/star endpoint để persist star vào starred.json

set PORT=8765
cd /d "%~dp0"

echo Starting AI News local server on http://localhost:%PORT%
echo Press Ctrl+C to stop the server when done.
echo.

start "" "http://localhost:%PORT%/index.html"
python scripts\server.py --port %PORT%
