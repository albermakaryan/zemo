@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ─── Versioning ────────────────────────────────────────────────────────────────
REM Usage:
REM   build_exe.bat                 -> bump PATCH (e.g. 0.1.3 -> 0.1.4)
REM   build_exe.bat patch           -> same as above
REM   build_exe.bat minor           -> bump MINOR, reset patch (0.1.3 -> 0.2.0)
REM   build_exe.bat major           -> bump MAJOR, reset minor/patch (0.1.3 -> 1.0.0)
REM   build_exe.bat 1.2.3           -> set explicit version 1.2.3 (no auto-bump)
REM   build_exe.bat --test          -> test build: do NOT bump VERSION, do NOT overwrite
REM                                    version_info.txt if it already exists; output
REM                                    dist\Recorder_test.exe
REM
REM VERSION is the single source of truth. This script:
REM   1) reads VERSION (or 0.0.0 if missing)
REM   2) bumps it according to the mode (major/minor/patch) or uses explicit value
REM   3) writes the new VERSION back to disk (skipped for --test)
REM   4) passes that version to build_version_info.py and names the output exe.

set "TEST_BUILD=0"
if /I "%~1"=="--test" set "TEST_BUILD=1"
if /I "%~1"=="test" set "TEST_BUILD=1"

if "!TEST_BUILD!"=="1" (
    set VER=
    if exist "VERSION" (
        set /p VER=<VERSION
        set VER=!VER: =!
    ) else (
        set VER=0.0.0
    )
    echo [Test build] Version !VER! from VERSION; not bumping; not rewriting VERSION; keeping version_info.txt if present.
    echo.
    goto :have_ver
)

set MODE=%~1
if "%MODE%"=="" set MODE=patch

set VER=
if exist "VERSION" (
    set /p VER=<VERSION
    set VER=!VER: =!
) else (
    set VER=0.0.0
)

REM If MODE looks like an explicit version (contains a dot and starts with a digit),
REM use it directly instead of bumping.
echo %MODE% | findstr /R "^[0-9][0-9.]*$" >nul
if not errorlevel 1 (
    set VER=%MODE%
    goto have_ver
)

REM Parse current semantic version VER = MAJOR.MINOR.PATCH
for /f "tokens=1-3 delims=." %%A in ("%VER%") do (
    set MAJOR=%%A
    set MINOR=%%B
    set PATCH=%%C
)
if "!MINOR!"=="" set MINOR=0
if "!PATCH!"=="" set PATCH=0

if /I "%MODE%"=="major" (
    set /a MAJOR+=1
    set MINOR=0
    set PATCH=0
) else if /I "%MODE%"=="minor" (
    set /a MINOR+=1
    set PATCH=0
) else (
    REM default / "patch"
    set /a PATCH+=1
)

set VER=!MAJOR!.!MINOR!.!PATCH!

:have_ver
if not "!TEST_BUILD!"=="1" (
    echo !VER!>VERSION
)

echo Building Recorder.exe, version !VER! ...
echo.

if not exist "env\Scripts\python.exe" (
    set PY=python
) else (
    set PY=env\Scripts\python.exe
)

if "!TEST_BUILD!"=="1" (
    if exist "version_info.txt" (
        echo Skipping build_version_info.py; using existing version_info.txt for Windows resource.
    ) else (
        echo version_info.txt not found; generating from VERSION - one-time ...
        "%PY%" build_version_info.py !VER!
        if errorlevel 1 (
            echo Failed to generate version_info.txt.
            pause
            exit /b 1
        )
    )
) else (
    "%PY%" build_version_info.py !VER!
    if errorlevel 1 (
        echo Failed to generate version_info.txt.
        pause
        exit /b 1
    )
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

if "!TEST_BUILD!"=="1" (
    copy /y "dist\Recorder.exe" "dist\Recorder_test.exe" >nul
    echo.
    echo Done. Test build: dist\Recorder_test.exe
    echo  VERSION, version_info.txt, and dist\Recorder_*.exe left unchanged for release.
) else (
    copy /y "dist\Recorder.exe" "dist\Recorder_!VER!.exe" >nul
    echo.
    echo Done. Executable: dist\Recorder_!VER!.exe
)
echo.
pause
