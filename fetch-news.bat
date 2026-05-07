@echo off
REM Fetch all sources scheduled for today (A + B combined)
REM Looks back since last_fetched (max 30 days, configured in fetch.py)

cd /d "%~dp0"

echo ===================================================
echo AI News Fetch - %date% %time%
echo ===================================================
echo.

echo [1/5] Pulling latest data from GitHub...
git pull --rebase origin main 2>&1
echo.

echo [2/5] Determining today's sources...
for /f "delims=" %%i in ('python -c "import datetime; print(datetime.datetime.utcnow().strftime('%%a').lower())"') do set WEEKDAY=%%i
echo Today UTC: %WEEKDAY%

REM Combine A + B sources for today
for /f "delims=" %%i in ('python -c "import json; d=json.load(open(r'sources.json',encoding='utf-8'))['schedule']; w='%WEEKDAY%'; s=set(); [s.update(d[a].get(w,{}).get(slot,[])) for a in ['A','B'] for slot in ['slot1','slot2','slot3']]; print(' '.join(sorted(s)))"') do set SOURCES=%%i

if "%SOURCES%"=="" (
    echo No sources scheduled for %WEEKDAY%. Exiting.
    pause
    exit /b 0
)
echo Sources: %SOURCES%
echo.

echo [3/5] Fetching + classifying...
python scripts\run_local.py --sources-list %SOURCES%
echo.

echo [4/5] Backfilling language + excerpt_vn...
python scripts\backfill.py
echo.

echo [5/5] Committing + pushing...
git add data/ state.json
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "feed: %date% local fetch"
    git pull --rebase origin main
    git push origin main
    echo Pushed.
) else (
    echo No new entries — nothing to commit.
)

echo.
echo ===================================================
echo DONE. Run start.bat to view feed.
echo ===================================================
pause
