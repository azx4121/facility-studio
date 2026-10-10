@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if not defined LOCALAPPDATA goto failed
if not exist "%~dp0Facility_Studio_V5_5_7_Windows_Offline.exe" goto missing
set "FACILITY_CHECK_LOGS=%LOCALAPPDATA%\Facility_Studio_V5_5\Logs"
if not exist "%FACILITY_CHECK_LOGS%" mkdir "%FACILITY_CHECK_LOGS%"
echo Checking the bundled Windows EXE. No Python installation or internet is needed.
start "" /wait "%~dp0Facility_Studio_V5_5_7_Windows_Offline.exe" --self-test --self-test-result "%FACILITY_CHECK_LOGS%\Windows_Acceptance.json"
if errorlevel 1 goto failed
echo PASS. Report: %FACILITY_CHECK_LOGS%\Windows_Acceptance.json
pause
exit /b 0
:missing
echo Please fully extract the ZIP; keep this script alongside the EXE.
:failed
echo Acceptance did not finish successfully.
echo Logs: %LOCALAPPDATA%\Facility_Studio_V5_5\Logs
pause
exit /b 1
