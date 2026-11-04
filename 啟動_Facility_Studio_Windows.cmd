@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul 2>nul
title Facility Studio 5.7.3 - Historical launcher retired
echo This historical 5.6 launcher is retired. No files were installed or changed.
echo For packaged software, open the verified Facility Studio 5.7.3 EXE from its complete portable folder,
echo or install the verified 5.7.3 Setup into a new empty directory.
echo Source build instructions: docs\development.md
echo Release status and verified downloads: https://github.com/azx4121/facility-studio/releases
exit /b 1
