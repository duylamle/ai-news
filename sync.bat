@echo off
REM Pull latest data from GitHub silently
cd /d "%~dp0"
git pull --rebase origin main >nul 2>&1
exit /b 0
