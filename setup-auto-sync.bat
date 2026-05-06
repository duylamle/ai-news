@echo off
REM Setup Windows Task Scheduler to auto-pull every hour
REM Run this ONCE as admin (or just run it — schtasks /create works without admin for user tasks)

set TASK_NAME=AI-News-Auto-Sync
set REPO_DIR=%~dp0
set SCRIPT=%REPO_DIR%sync.bat

echo Setting up Windows Task Scheduler...
echo Task name: %TASK_NAME%
echo Script: %SCRIPT%
echo Frequency: Every 1 hour
echo.

REM Delete existing task if any
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM Create new task — every hour, no need for admin (user-level task)
schtasks /create /tn "%TASK_NAME%" /tr "\"%SCRIPT%\"" /sc hourly /mo 1 /st 00:05 /f

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS: Task scheduled. Repo will auto-pull every hour at :05 minute mark.
    echo.
    echo To check: Run "schtasks /query /tn %TASK_NAME%"
    echo To remove: Run "schtasks /delete /tn %TASK_NAME% /f"
) else (
    echo.
    echo ERROR: Task creation failed. Try running this script as Administrator.
)

pause
