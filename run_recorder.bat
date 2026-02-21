@echo off
cd /d "%~dp0"

if exist "env\Scripts\python.exe" (
    set "PY=env\Scripts\python.exe"
) else (
    set "PY=python"
)

"%PY%" --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Python is not installed or not on PATH.
    echo.
    echo   Install Python from:  https://www.python.org/downloads/
    echo   During setup, check "Add Python to PATH".
    echo.
    echo   Then run this script again.
    echo.
    start "" "https://www.python.org/downloads/"
    pause
    exit /b 1
)

"%PY%" main.py
if errorlevel 1 (
    echo.
    echo Something went wrong. Check the message above.
    pause
)
