@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hfwei\.workbuddy\binaries\python\versions\3.13.12\python.exe
if not exist "%PY%" set PY=python
echo Starting local paper server...
start "" http://127.0.0.1:8765
"%PY%" server.py --no-open
pause
