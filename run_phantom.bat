@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ================================================
echo   PHANTOM LAB - AUTOMATIC LOCAL TEST RUNNER
echo ================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    echo Install Python or add it to PATH, then run again.
    goto finish_error
)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo ERROR: This folder is not a Git clone.
    echo Clone https://github.com/zrajibj/phantom and run this file there.
    goto finish_error
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo ERROR: No GitHub origin is configured.
    goto finish_error
)

if not exist "config.local.json" (
    copy /Y "config.example.json" "config.local.json" >nul
    if errorlevel 1 (
        echo ERROR: Could not create config.local.json.
        goto finish_error
    )
    echo Created local config from config.example.json.
)

rem The published summary is generated output and will be regenerated below.
rem Restore only that tracked output if it was left modified by a failed run.
git diff --quiet -- "public_reports/latest.md"
if errorlevel 1 (
    echo Cleaning up the previous generated summary so Git can update safely...
)
git restore --source=HEAD --staged --worktree -- "public_reports/latest.md"
if errorlevel 1 (
    echo ERROR: Could not restore the generated summary file.
    goto finish_error
)

set "STATUS_FILE=%TEMP%\phantom-status-%RANDOM%.txt"
git status --porcelain --untracked-files=normal > "%STATUS_FILE%"
findstr /v /c:"public_reports/latest.md" "%STATUS_FILE%" | findstr /r /c:"." >nul
if not errorlevel 1 (
    echo ERROR: Other local Git changes or untracked files need attention.
    echo No files were discarded. Review:
    git status --short
    del "%STATUS_FILE%" >nul 2>&1
    goto finish_error
)
del "%STATUS_FILE%" >nul 2>&1

echo Fetching latest PHANTOM code and benchmarks...
git fetch origin
if errorlevel 1 (
    echo ERROR: Could not fetch from GitHub. Check internet and sign-in.
    goto finish_error
)

set "LOCAL_AHEAD=0"
for /f %%A in ('git rev-list --count origin/main..HEAD') do set "LOCAL_AHEAD=%%A"

if not "!LOCAL_AHEAD!"=="0" (
    set "COMMIT_FILE=%TEMP%\phantom-local-commits-%RANDOM%.txt"
    git log --format=%%s origin/main..HEAD > "!COMMIT_FILE!"
    findstr /v /x /c:"Update PHANTOM safe benchmark summary" "!COMMIT_FILE!" | findstr /r /c:"." >nul
    if not errorlevel 1 (
        echo ERROR: Local commits include changes other than generated report updates.
        echo No commits were discarded. Please review: git log --oneline origin/main..HEAD
        del "!COMMIT_FILE!" >nul 2>&1
        goto finish_error
    )
    del "!COMMIT_FILE!" >nul 2>&1
    echo Found an unpublished generated-report commit from an earlier run.
    echo Re-aligning to GitHub; the summary will be regenerated after testing.
    git reset --hard origin/main
    if errorlevel 1 (
        echo ERROR: Could not align the local copy with origin/main.
        goto finish_error
    )
) else (
    git merge --ff-only origin/main
    if errorlevel 1 (
        echo ERROR: Could not fast-forward to GitHub main.
        echo No tests were run against stale code.
        goto finish_error
    )
)

echo.
echo Running automated PHANTOM tests against local LM Studio...
python phantom_lab.py --config config.local.json
set "PHANTOM_EXIT=!ERRORLEVEL!"

if not "!PHANTOM_EXIT!"=="0" (
    echo.
    echo ERROR: Test run did not complete successfully.
    echo The old GitHub summary will not be republished as a new result.
    goto finish
)

if not exist "public_reports\latest.md" (
    echo ERROR: No summary was generated. Skipping publish.
    goto finish
)

echo.
echo Publishing the safe summary only...
git add -- "public_reports/latest.md"
if errorlevel 1 (
    echo ERROR: Could not stage the safe summary. Full reports remain local.
    goto finish
)

git diff --cached --quiet
if not errorlevel 1 (
    echo The summary is unchanged; nothing to publish.
    goto finish
)

git commit -m "Update PHANTOM safe benchmark summary"
if errorlevel 1 (
    echo ERROR: Could not commit the safe summary.
    goto finish
)

git push origin main
if errorlevel 1 (
    echo WARNING: GitHub push failed. The local report is still saved.
    echo Check GitHub sign-in/network. The next run can recover safely.
    goto finish
)

echo.
echo SUCCESS: Latest summary published:
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
