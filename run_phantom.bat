@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo ================================================
echo   PHANTOM LAB - LOCAL EXPERIMENT RUNNER
echo ================================================
echo.

if not exist "config.local.json" (
    copy /Y "config.example.json" "config.local.json" >nul
    if errorlevel 1 (
        echo ERROR: Could not create config.local.json
        goto finish_error
    )
    echo Created local config from config.example.json
)

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    echo Install Python or add it to PATH, then try again.
    goto finish_error
)

python phantom_lab.py --config config.local.json
set "PHANTOM_EXIT=%ERRORLEVEL%"

echo.
echo Checking whether the safe summary can be synced to GitHub...

if not exist "public_reports\latest.md" (
    echo No summary file was generated. Skipping publish.
    goto finish
)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo This folder is not a Git clone. Reports remain local.
    echo Clone https://github.com/zrajibj/phantom to use automatic sync.
    goto finish
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo No Git origin is configured. Reports remain local.
    goto finish
)

git add -- "public_reports/latest.md"
if errorlevel 1 (
    echo Could not stage the safe summary. Local reports are preserved.
    goto finish
)

git diff --cached --quiet
if not errorlevel 1 (
    echo The safe summary has not changed; nothing to publish.
    goto finish
)

git commit -m "Update PHANTOM safe benchmark summary"
if errorlevel 1 (
    echo Git commit failed. Local reports are preserved.
    goto finish
)

git push origin
if errorlevel 1 (
    echo Git push failed. Your full report is still saved locally.
    echo Check your GitHub sign-in and internet connection, then run again.
    goto finish
)

echo.
echo Published safe summary:
echo https://github.com/zrajibj/phantom/blob/main/public_reports/latest.md
echo Full prompts and model responses remain local.

:finish
echo.
if not defined PHANTOM_NO_PAUSE pause
exit /b %PHANTOM_EXIT%

:finish_error
echo.
if not defined PHANTOM_NO_PAUSE pause
exit /b 1
