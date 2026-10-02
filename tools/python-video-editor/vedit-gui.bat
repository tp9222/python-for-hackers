@echo off
REM Double-click to open the editor.
cd /d "%~dp0"
start "" pythonw vedit.py gui %*
