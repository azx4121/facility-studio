@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul 2>nul
title Facility Studio V5.6.0 (win.4) - Build Offline EXE
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto missing
py -3.13 -m venv ".build-venv"
if errorlevel 1 goto failed
".build-venv\Scripts\python.exe" -m pip install --require-hashes --only-binary=:all: -r "windows\winrelease\requirements.lock.txt"
if errorlevel 1 goto failed
pushd windows
"..\.build-venv\Scripts\python.exe" -m winrelease.build --output "..\dist\windows-offline"
if errorlevel 1 goto build_failed
popd
echo Built files: %CD%\dist\windows-offline
echo Run windows\winrelease\Verify_on_Windows.cmd or the native CI before distribution.
pause
exit /b 0
:build_failed
popd
:failed
echo Build failed. No successful standalone EXE is being claimed.
pause
exit /b 1
:missing
echo Install the supported Python 3.13 x64 with Tcl/Tk to build from source.
echo For normal use, download the tested Windows Offline EXE from GitHub Releases.
pause
exit /b 1
