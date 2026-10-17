@echo off
rem 启动本地服务并打开摘要页（Windows 双击即可）。需要 PATH 里有 Python 3.9+。
rem 端口与下载目录取自 config.json；首次运行会自动按 config.example.json 生成。
chcp 65001 >nul
cd /d "%~dp0"

set "PY=python"
where python >nul 2>nul || set "PY=py -3"
%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" 2>nul
if errorlevel 1 (
  echo 未找到 Python 3.9+，请先安装 Python 并确保 python 或 py 在 PATH 中。
  pause
  exit /b 1
)

set "PORT=8765"
for /f "usebackq delims=" %%p in (`%PY% -c "import json,os;p='config.json';print(json.load(open(p,encoding='utf-8')).get('port',8765) if os.path.exists(p) else 8765)" 2^>nul`) do set "PORT=%%p"

echo Starting local paper server on http://127.0.0.1:%PORT% ...
start "" http://127.0.0.1:%PORT%
%PY% server.py --no-open
pause
