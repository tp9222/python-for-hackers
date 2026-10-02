@echo off
REM Double-click to start the browser editor and open it.
cd /d "%~dp0"
python serve.py --open %*
