@echo off
setlocal
cd /d "%~dp0"

echo.
echo ================================================
echo   PHANTOM ASSISTANT - LOCAL QWEN RUNTIME
echo ================================================
echo.
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    echo Install Python 3.12 or add Python to PATH.
    goto failed
)

if not exist "phantom_assistant.py" (
    echo ERROR: phantom_assistant.py is missing.
    echo First run run_phantom.bat to sync the latest repository.
    goto failed
)

echo Starting local assistant. Make sure LM Studio is running Qwen3-8B
echo and the local API server is enabled at 127.0.0.1:1234.
echo.
python phantom_assistant.py
if errorlevel 1 goto failed
goto end

:failed
echo.
echo PHANTOM assistant stopped with an error.
pause
exit /b 1

:end
exit /b 0
