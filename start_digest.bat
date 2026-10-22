@echo off
rem 启动本地服务并打开摘要页（Windows 双击即可）。需要 PATH 里有 Python 3.9+。
rem 端口与下载目录取自 config.json；首次运行会自动按 config.example.json 生成。
rem 端口被占用时 server.py 会自动向后顺延（8765 -> 8766 -> ...），实际地址由它
rem 打印并自动在浏览器打开，所以这里不再自己拼 URL（否则会开到被占用的旧端口）。
rem
rem 用法：
rem   start_digest.bat                 干净启动（不加载任何人的画像）
rem   start_digest.bat hengxin         启动前先导入 presets\hengxin\ 这份数据包
rem   start_digest.bat hengxin force   同上，但允许覆盖本机已有的 config.json / interests.json
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

rem 可选的第 1 个参数 = 数据包名；第 2 个参数写 force 则允许覆盖本机配置
set "PRESET="
if not "%~1"=="" set "PRESET=--preset %~1"
if /I "%~2"=="force" set "PRESET=%PRESET% --preset-force"

rem 端口取 config.json（默认 8765）；被占用自动顺延，浏览器由 server.py 打开。
echo Starting local paper server (port from config.json; auto-increment if busy) ...
%PY% server.py %PRESET%
pause
