@echo off
setlocal DisableDelayedExpansion
title Facility Studio V5.5.4 - One Click Setup
cd /d "%~dp0"
echo Facility Studio V5.5.4 - Windows x64
 echo This prepares Python, builds the EXE and creates a desktop shortcut.
echo Internet access is required on first setup. Keep this window open.
echo.
set "HVAC_ARCH=%PROCESSOR_ARCHITECTURE%"
if defined PROCESSOR_ARCHITEW6432 set "HVAC_ARCH=%PROCESSOR_ARCHITEW6432%"
if /i not "%HVAC_ARCH%"=="AMD64" goto unsupported
if not defined LOCALAPPDATA goto failed
if not exist "%~dp0payload\Facility_Studio_V5_5.py" goto missing
set "HVAC_PY="
set "HVAC_BOOT=%LOCALAPPDATA%\Facility_Studio_V5_5\bootstrap"
if not exist "%HVAC_BOOT%" mkdir "%HVAC_BOOT%"
if not exist "%HVAC_BOOT%" goto failed
if not exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" goto find_launcher
"%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%~dp0probe_python.py" >nul 2>nul
if errorlevel 1 goto find_launcher
set "HVAC_PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
goto build
:find_launcher
where py >nul 2>nul
if errorlevel 1 goto download
for /f "delims=" %%P in ('py -3.13 "%~dp0probe_python.py" 2^>nul') do set "HVAC_PY=%%P"
if defined HVAC_PY goto build
:download
echo Preparing official Python 3.13.15 x64 from python.org...
echo Details: %HVAC_BOOT%\Python_Setup.log
powershell.exe -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; try { [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $f=Join-Path $env:HVAC_BOOT 'python-3.13.15-amd64.exe'; Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.13.15/python-3.13.15-amd64.exe' -OutFile $f -TimeoutSec 300; $h=(Get-FileHash -Algorithm SHA256 -LiteralPath $f).Hash; if ($h -ne 'EDEC09C4853AEAE9AC36EFB8C9F95B6B8E2FEE65EEE56D9767A8B7C69C574403') { throw 'Python installer SHA256 mismatch.' }; $s=Get-AuthenticodeSignature -LiteralPath $f; if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'CN=Python Software Foundation') { throw 'Python installer publisher signature is not valid.' }; $p=Start-Process -FilePath $f -ArgumentList '/passive','InstallAllUsers=0','Include_launcher=0','Include_pip=1','Include_tcltk=1','Include_test=0','Include_doc=0','Shortcuts=0','AssociateFiles=0','PrependPath=0','Include_freethreaded=0' -Wait -PassThru; if ($p.ExitCode -notin @(0,3010)) { throw ('Python installer exit: '+$p.ExitCode) }; exit 0 } catch { $_ | Out-File -LiteralPath (Join-Path $env:HVAC_BOOT 'Python_Setup.log'); Write-Host $_; exit 1 }"
if errorlevel 1 goto failed
set "HVAC_PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not exist "%HVAC_PY%" goto python_missing
"%HVAC_PY%" "%~dp0probe_python.py" >nul 2>nul
if errorlevel 1 goto python_missing
:build
"%HVAC_PY%" "%~dp0oneclick_setup.py"
if errorlevel 1 goto failed
echo.
echo Ready. Next time, use the Facility Studio V5.5 desktop shortcut.
if /i not "%~1"=="/installer" pause
exit /b 0
:missing
echo Please extract the ENTIRE ZIP first, then run START.cmd again.
goto failed
:unsupported
echo This package requires Windows 10/11 with an Intel/AMD 64-bit processor.
goto failed
:python_missing
echo Python 3.13 x64 with Tcl/Tk was not found after setup.
echo An existing custom Python installation may need repair by your IT team.
:failed
echo.
echo Setup did not finish. No successful EXE installation is being claimed.
echo Please send a screenshot of this window and the available setup logs.
echo Logs: %LOCALAPPDATA%\Facility_Studio_V5_5\Setup.log
 echo       %LOCALAPPDATA%\Facility_Studio_V5_5\bootstrap\Python_Setup.log
if /i not "%~1"=="/installer" pause
exit /b 1
