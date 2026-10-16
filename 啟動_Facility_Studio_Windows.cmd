@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul 2>nul
title Facility Studio V5.6.0 (win.4)
cd /d "%~dp0"
if exist "Facility_Studio_V5_6_0_Windows_Offline.exe" (
    start "" "%~dp0Facility_Studio_V5_6_0_Windows_Offline.exe"
    exit /b 0
)
if not exist "windows\Facility_Studio_V5_5.py" goto missing
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0windows\Facility_Studio_V5_5.py"
    if errorlevel 1 goto failed
    exit /b 0
)
where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0windows\Facility_Studio_V5_5.py"
    if errorlevel 1 goto failed
    exit /b 0
)
echo Preparing Python and packages through the online installer...
call "%~dp0windows\installer\START.cmd"
exit /b %errorlevel%
:missing
echo Extract the complete source package, or download the tested Windows Offline EXE from GitHub Releases.
:failed
pause
exit /b 1
