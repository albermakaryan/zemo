@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Version: from first argument, or VERSION file, or date-based (e.g. 0.0.20250219)
set VER=
if not "%~1"=="" (
    set VER=%~1
) else if exist "VERSION" (
    set /p VER=<VERSION
    set VER=!VER: =!
)
if "!VER!"=="" (
    for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set DT=%%I
    if defined DT (set VER=0.0.!DT:~0,8!) else (set VER=0.0.0)
)

echo Building Recorder.exe (version !VER!) ...
echo.

if not exist "env\Scripts\python.exe" (
    set PY=python
) else (
    set PY=env\Scripts\python.exe
)

"%PY%" -m pip install pyinstaller pyinstaller-hooks-contrib --quiet
if errorlevel 1 (
    echo Failed to install PyInstaller.
    pause
    exit /b 1
)

REM Remove previous build folders to avoid "Access is denied" on localpycs (close Recorder.exe first)
if exist "build" (
    echo Cleaning build folder...
    rd /s /q build 2>nul
    if exist "build" (
        echo.
        echo ERROR: Could not delete "build" folder. Close Recorder.exe and any terminals using this folder, then try again.
        pause
        exit /b 1
    )
)

REM Build (spec defines name=Recorder; --name not allowed with .spec)
"%PY%" -m PyInstaller --clean Recorder.spec

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

REM Copy to versioned name so we keep dist\Recorder_1.0.0.exe etc.
copy /y "dist\Recorder.exe" "dist\Recorder_!VER!.exe" >nul

echo.
echo Done. Executable: dist\Recorder_!VER!.exe
echo.
pause
