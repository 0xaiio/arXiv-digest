@echo off
rem 启动本地服务，并用默认浏览器打开一份已生成的 arXiv digest HTML（Windows 双击即可）。
rem 端口与下载目录取自 config.json；端口被占用时 server.py 自动顺延并写 output/server.json，
rem 因此本脚本不自己拼 URL（否则会开到被占用的旧端口）。
rem
rem 参数（全部可选，与顺序无关）：
rem   [日期]   YYYY-MM-DD，打开「期次日期 <= 该日期 且最接近」的一期（含指定当天）。
rem            --date 2026-11-11 / --date=2026-11-11 是等价的显式写法。
rem   [包名]   兼容旧用法：第 1 个非日期参数 = 要导入的数据包名（如 hengxin）。
rem   force    兼容旧用法：允许数据包覆盖本机已有的 config.json / interests.json。
rem
rem 默认行为：不带日期 → 打开当前已生成的最新一期；不带包名 → 干净启动、不导入任何数据。
rem 边界处理：
rem   - 日期严格按 YYYY-MM-DD 且必须是真实日历日期（2026-02-30 / 2026-11-1 都拒绝）；
rem   - 参数非法或找不到符合条件的 HTML：只打印提示，绝不打开任何文件，服务照常启动；
rem   - 同一期次日期有多份 HTML：按生成时间(mtime)取最新，同秒优先根目录的正式文件；
rem   - 只打开这一份：用 --no-open 关掉 server.py 自带的开页，避免冒出两个标签页；
rem     打开的 HTML 是静态文件，页内 APIPORT 是生成当时的端口，端口顺延时刷新页面即可；
rem   - config.json 的 open_browser=false 仍然生效（此时不开浏览器，服务照常启动）。
rem
rem 用法：
rem   start_digest.bat                          最新一期（兼容旧的无参数调用）
rem   start_digest.bat 2026-11-11               看 11-11 当期；没有则找最接近的更早一期
rem   start_digest.bat --date 2026-11-11       显式指定日期
rem   start_digest.bat hengxin                 导入数据包（旧用法，行为不变）
rem   start_digest.bat hengxin force           同上，且允许覆盖本机配置
rem   start_digest.bat hengxin 2026-11-11      导入数据包 + 指定期次
chcp 65001 >nul
cd /d "%~dp0"
setlocal EnableDelayedExpansion
rem 帮助块与提示含中文，统一按 UTF-8 输出，避免 GBK 控制台把回传值/提示打歪。
set "PYTHONIOENCODING=utf-8"

set "PY=python"
where python >nul 2>nul || set "PY=py -3"
%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" 2>nul
if errorlevel 1 (
  echo 未找到 Python 3.9+，请先安装 Python 并确保 python 或 py 在 PATH 中。
  pause
  exit /b 1
)

rem 文件末尾的内嵌 Python 帮助块负责：解析参数、校验日期、按「期次日期 <= 目标 且
rem 最接近」挑 HTML，并回传四行 KEY=VALUE。用 Python 而非 cmd 字符串运算，是因为
rem 闰年/大小月校验与 mtime 排序用批处理写既脆弱又难以测试。
set "DP_DIGEST="
set "DP_PRESETFLAGS="
set "DP_OPEN=1"
set "DP_ERR="
for /f "usebackq tokens=1,* delims==" %%K in (`%PY% -c "import sys; a=sys.argv; s=open(a[1],encoding='utf-8').read(); m='# ==PY-'; b=s.split(m+'BEGIN==')[1].split(m+'END==')[0]; sys.argv=[a[1],a[2]]+a[3:]; exec(b)" "%~f0" "%~dp0output" %*`) do set "DP_%%K=%%L"

if defined DP_DIGEST (
  if "!DP_OPEN!"=="0" (
    echo [start_digest] config.json 里 open_browser=false，按配置不打开浏览器。
  ) else (
    echo [start_digest] 打开日报：!DP_DIGEST!
    start "" "!DP_DIGEST!"
  )
) else (
  if defined DP_ERR (echo [start_digest] !DP_ERR!) else (echo [start_digest] 帮助块未返回可打开的日报（执行失败）。)
  echo [start_digest] 本次不打开任何 HTML；服务照常启动。
)

rem 服务启动逻辑保持原样：同一条 server.py 命令 + 数据包参数；只把「开浏览器」交给本脚本。
echo Starting local paper server (port from config.json; auto-increment if busy) ...
%PY% server.py !DP_PRESETFLAGS! --no-open
pause
exit /b 0

rem ============================================================================
rem 以下为内嵌 Python 帮助块：cmd 不会执行（exit /b 已结束批处理），
rem 由上面的 python -c 从本文件抽出后 exec。改这里请同步 tests/unit/test_start_digest_bat.py。
# ==PY-BEGIN==
"""start_digest.bat 的内嵌帮助块：只解析参数并挑一份日报 HTML，不启动服务、不开浏览器。

输出约定（stdout 的 KEY=VALUE 行，由 bat 的 for /f 读回）：
    PRESETFLAGS=<传给 server.py 的数据包参数，可为空>
    DIGEST=<要打开的 HTML 绝对路径；出错时必为空>
    OPEN=<1 允许打开浏览器 / 0 配置里关掉了自动打开>
    ERR=<人类可读的错误说明，仅出错时输出>
"""
import datetime
import json
import os
import re
import sys

DATE_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 明显在写日期但格式不对的形态也归入日期分支，避免被当成数据包名给出误导性提示
DATE_LIKE = re.compile(r"^(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{8})$")
ROOT_ISSUE = re.compile(r"^arxiv_digest_(\d{8})(?:[_-].*)?\.html$", re.I)
ARCHIVE_ISSUE = re.compile(r"^(\d{8})\.html$", re.I)
CANONICAL = re.compile(r"^arxiv_digest_\d{8}\.html$", re.I)
_TRUTHY = {"1", "true", "yes", "on", "y", "t"}


def parse_date(text):
    """严格 YYYY-MM-DD + 真实日历日期；返回 (date 或 None, 错误说明 或 None)。"""
    if not DATE_SHAPE.match(text or ""):
        return None, "日期参数不合法：'%s'；应为 YYYY-MM-DD（例如 2026-11-11）" % text
    try:
        return datetime.date(int(text[:4]), int(text[5:7]), int(text[8:10])), None
    except ValueError:
        return None, "日期不存在：%s（月/日超出范围，例如 2026-02-30）" % text


def parse_args(args):
    """兼容旧用法；返回 (date_text, preset, force, error)。

    日期：位置参数（形似日期即归入此分支）、--date <值> 或 --date=<值>；
    包名：第一个其它位置参数（旧用法的第 1 个参数）；force / --preset-force：允许覆盖。
    """
    date_text, preset, force = "", "", False
    i = 0
    while i < len(args):
        a = args[i]
        low = a.lower()
        if low == "--date":
            if i + 1 >= len(args):
                return "", "", False, "--date 后缺少日期（YYYY-MM-DD）"
            date_text, i = args[i + 1], i + 2
            continue
        if low.startswith("--date="):
            date_text, i = a.split("=", 1)[1], i + 1
            continue
        if low == "--preset":
            if i + 1 >= len(args):
                return "", "", False, "--preset 后缺少数据包名"
            preset, i = args[i + 1], i + 2
            continue
        if low.startswith("--preset="):
            preset, i = a.split("=", 1)[1], i + 1
            continue
        if low in ("force", "--preset-force"):
            force, i = True, i + 1
            continue
        if DATE_LIKE.match(a):
            if date_text:
                return "", "", False, "日期参数只能给一次（收到第二个：%s）" % a
            date_text, i = a, i + 1
            continue
        if a.startswith("-"):
            return "", "", False, "无法识别的参数：%s" % a
        if not preset:
            preset, i = a, i + 1
            continue
        return "", "", False, "无法识别的多余参数：%s（只接受一个数据包名）" % a
    return date_text, preset, force, None


def browser_allowed(config_path):
    """沿用 serveport.browser_enabled 的默认值语义：缺省 true，显式 false 才关。"""
    try:
        with open(config_path, encoding="utf-8") as fh:
            value = json.load(fh).get("open_browser", True)
    except Exception:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY
    return bool(value)


def scan_issues(out_dir):
    """收集已生成的日报 HTML：output/arxiv_digest_<YYYYMMDD>[_后缀].html 与
    output/archive/<YYYYMMDD>.html。返回 [(期次日期, mtime, 绝对路径, 排序优先级)]。

    只认文件名里 8 位且真实存在的日期；favorites.html / archive.html / _preview.html
    等非期次页面一律不计入 —— 这是「绝不打开错误文件」的第一道闸门。
    """
    rows = []
    for folder, is_archive in ((out_dir, False), (os.path.join(out_dir, "archive"), True)):
        if not os.path.isdir(folder):
            continue
        rx = ARCHIVE_ISSUE if is_archive else ROOT_ISSUE
        for name in os.listdir(folder):
            m = rx.match(name)
            if not m:
                continue
            stamp = m.group(1)
            try:
                issue = datetime.date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))
            except ValueError:
                continue
            path = os.path.abspath(os.path.join(folder, name))
            try:
                mt = os.path.getmtime(path)
            except OSError:
                continue
            rank = 0 if (not is_archive and CANONICAL.match(name)) else 1
            rows.append((issue, mt, path, rank))
    return rows


def choose_issue(rows, target):
    """target=None 取期次日期最新的一期；否则取 <= target 且最接近的一期（含相等）。
    同一期次有多份时按生成时间 mtime 取最新；mtime 相同按「正式文件优先 / 路径」兜底。
    """
    if not rows:
        return None
    pool = rows if target is None else [r for r in rows if r[0] <= target]
    if not pool:
        return None
    best = max(r[0] for r in pool)
    same = [r for r in pool if r[0] == best]
    return sorted(same, key=lambda r: (r[1], -r[3], r[2]))[-1][2]


def resolve(out_dir, args):
    """返回 (digest_path, preset_flags, error)。出错时 digest_path 必为空字符串。"""
    date_text, preset, force, err = parse_args(args)
    flags = ""
    if preset:
        flags = "--preset %s" % preset
        if force:
            flags += " --preset-force"
    if err:
        return "", flags, err
    target, derr = (None, None)
    if date_text:
        target, derr = parse_date(date_text)
    if derr:
        return "", flags, derr
    rows = scan_issues(out_dir)
    path = choose_issue(rows, target)
    if not path:
        if target is None:
            return "", flags, "未在 %s 找到任何已生成的 arxiv_digest_<YYYYMMDD>.html" % out_dir
        earliest = min((r[0] for r in rows), default=None)
        hint = "，现存最早一期是 %s" % earliest.isoformat() if earliest else "（当前一期也没有）"
        return "", flags, "找不到期次日期不晚于 %s 的日报 HTML%s" % (target.isoformat(), hint)
    return path, flags, ""


def main():
    out_dir, args = sys.argv[1], sys.argv[2:]
    path, flags, err = resolve(out_dir, args)
    allowed = browser_allowed(os.path.join(os.path.dirname(os.path.abspath(out_dir)), "config.json"))
    print("PRESETFLAGS=%s" % flags)
    print("DIGEST=%s" % path)
    print("OPEN=%d" % (1 if allowed else 0))
    if err:
        print("ERR=%s" % err)
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
# ==PY-END==
