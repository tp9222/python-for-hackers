@echo off
title PhoneDesk setup
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PhoneDesk.ps1" -Install
echo.
pause
