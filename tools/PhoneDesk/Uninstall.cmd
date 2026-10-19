@echo off
title PhoneDesk uninstall
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PhoneDesk.ps1" -Uninstall
echo.
pause
