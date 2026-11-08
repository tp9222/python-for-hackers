@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
start "" http://127.0.0.1:5070
python app.py %*
