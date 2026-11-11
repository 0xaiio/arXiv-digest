# -*- coding: utf-8 -*-
"""``start_digest.bat`` 的回归测试。

脚本把日期校验与选文件逻辑写在**自身内嵌的 Python 帮助块**里（没有独立 .py 源文件），
因此测试直接抽取该块并 exec —— 测的就是交付出去的那份代码，不是复制品。

三层覆盖：
  1. 帮助块的纯函数（日期校验、参数解析、扫描、选择、错误文案）；
  2. 脚本里 `python -c` 引导串的真实子进程（验证标记抽取 + KEY=VALUE 契约）；
  3. Windows cmd 层的干跑副本（把「开浏览器 / 起服务」两行换成 echo，
     验证 for /f、延迟展开、参数透传与「出错绝不打开」）。

不启动真实服务、不打开浏览器；临时目录按项目约定放在 tmp_pytest/ 且从不删除。
"""
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BAT = ROOT / "start_digest.bat"
TMP = ROOT / "tmp_pytest"
BEGIN = "# ==PY-BEGIN=="
END = "# ==PY-END=="

pytestmark = pytest.mark.unit

# 真实 cmd 干跑会起嵌套 cmd/python 子进程；本机还常驻本地服务与浏览器自动化，
# Windows 下偶发出现 stdio 句柄继承导致的 communicate() 不返回。与项目里 ui 用例
# 同样的做法：默认跳过，需要验 cmd 层时设 RUN_BAT_CMD_E2E=1 显式开启。
RUN_BAT_CMD = os.environ.get("RUN_BAT_CMD_E2E") == "1"
batcmd = pytest.mark.skipif(not RUN_BAT_CMD, reason="设 RUN_BAT_CMD_E2E=1 才跑真实 cmd 干跑")


@pytest.fixture(scope="module")
def bat_text():
    return BAT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def helper(bat_text):
    """抽取帮助块并以非 __main__ 名字 exec（避免自动调用 main）。"""
    block = bat_text.split(BEGIN)[1].split(END)[0]
    ns = {"__name__": "start_digest_helper"}
    exec(compile(block, str(BAT), "exec"), ns)
    return ns


def _make_out(tag, files):
    """files = {相对路径: mtime 秒}；返回临时 output 目录。"""
    TMP.mkdir(exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="bat-%s-" % tag, dir=str(TMP)))
    (d / "archive").mkdir()
    for rel, ts in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("<html>digest</html>", encoding="utf-8")
        os.utime(str(p), (ts, ts))
    return d


@pytest.fixture()
def out():
    """三期日报 + 归档快照 + 一堆不应被当成期次的页面。

    mtime 刻意错开：20261105 的归档副本比正式文件新，20261109 反过来。
    """
    return _make_out("issues", {
        "arxiv_digest_20261101.html": 1000,
        "arxiv_digest_20261105.html": 1100,
        "arxiv_digest_20261109.html": 1200,
        "archive/20261105.html": 1300,
        "archive/20261109.html": 1150,
        "favorites.html": 9999,
        "archive.html": 9999,
        "_preview.html": 9999,
        "arxiv_digest_20261345.html": 9999,     # 8 位但不是真实日期
        "arxiv_digest_20261110.html.old": 9999,  # 不是 .html 后缀
        "notes.md": 9999,
    })


def _base(rel):
    return Path(rel).name


# ------------------------------------------------------------------ 一、脚本结构
def test_bat_keeps_original_service_startup(bat_text):
    """服务仍是前台那条 server.py 命令，没有被改成后台拉起或换入口。"""
    assert "%PY% server.py !DP_PRESETFLAGS! --no-open" in bat_text
    assert "chcp 65001 >nul" in bat_text
    assert 'where python >nul 2>nul || set "PY=py -3"' in bat_text
    assert 'set "PY=python"' in bat_text
    assert "pause" in bat_text
    assert "start \"\" \"!DP_DIGEST!\"" in bat_text
    assert "--preset-force" in bat_text          # 旧参数仍由帮助块产出


def test_bat_comments_cover_args_default_and_edge_cases(bat_text):
    head = bat_text.split("chcp 65001")[0]
    for kw in ("YYYY-MM-DD", "参数", "默认行为", "边界处理", "不打开任何文件"):
        assert kw in head, "脚本注释缺少：%s" % kw


def test_helper_markers_are_unique_and_block_compiles(bat_text):
    """标记若重复出现在引导串里，抽取会拿到错误片段（实测踩过）。"""
    assert bat_text.count(BEGIN) == 1
    assert bat_text.count(END) == 1
    assert bat_text.index(BEGIN) > bat_text.index("exit /b 0")
    block = bat_text.split(BEGIN)[1].split(END)[0]
    compile(block, str(BAT), "exec")


# ------------------------------------------------------------------ 二、日期校验
@pytest.mark.parametrize("text,expected", [
    ("2026-11-11", datetime.date(2026, 11, 11)),
    ("2024-02-29", datetime.date(2024, 2, 29)),   # 闰年
    ("2000-02-29", datetime.date(2000, 2, 29)),
    ("1999-12-31", datetime.date(1999, 12, 31)),
])
def test_parse_date_accepts_real_calendar_dates(helper, text, expected):
    got, err = helper["parse_date"](text)
    assert got == expected and err is None


@pytest.mark.parametrize("text", [
    "", "2026-11-11 ", " 2026-11-11", "2026-1-1", "20261111", "2026/11/11",
    "2026.11.11", "2026-02-30", "2025-02-29", "2026-13-01", "2026-00-10",
    "2026-11-32", "abcd-ef-gh", "2026-11-11T00:00",
])
def test_parse_date_rejects_bad_format_or_nonexistent_date(helper, text):
    got, err = helper["parse_date"](text)
    assert got is None and isinstance(err, str) and err


# ------------------------------------------------------------------ 三、参数解析
@pytest.mark.parametrize("args,expected", [
    ([], ("", "", False, None)),
    (["hengxin"], ("", "hengxin", False, None)),
    (["hengxin", "force"], ("", "hengxin", True, None)),
    (["hengxin", "FORCE"], ("", "hengxin", True, None)),
    (["2026-11-11"], ("2026-11-11", "", False, None)),
    (["--date", "2026-11-11"], ("2026-11-11", "", False, None)),
    (["--date=2026-11-11"], ("2026-11-11", "", False, None)),
    (["hengxin", "2026-11-11"], ("2026-11-11", "hengxin", False, None)),
    (["hengxin", "force", "2026-11-11"], ("2026-11-11", "hengxin", True, None)),
    (["--preset", "hengxin", "--date", "2026-11-11"], ("2026-11-11", "hengxin", False, None)),
    (["--preset=hengxin", "--preset-force"], ("", "hengxin", True, None)),
])
def test_parse_args_keeps_legacy_forms_and_accepts_date(helper, args, expected):
    assert helper["parse_args"](args) == expected


@pytest.mark.parametrize("args,kw", [
    (["--date"], ["缺少日期"]),
    (["--preset"], ["缺少数据包名"]),
    (["2026-11-11", "2026-11-12"], ["只能给一次"]),
    (["hengxin", "other"], ["多余参数"]),
    (["--unknown"], ["无法识别"]),
])
def test_parse_args_reports_clear_errors(helper, args, kw):
    _date, _preset, _force, err = helper["parse_args"](args)
    assert err and any(k in err for k in kw)


# ------------------------------------------------------------------ 四、扫描与选择
def test_scan_issues_only_collects_real_issue_html(helper, out):
    rows = helper["scan_issues"](str(out))
    names = sorted(_base(r[2]) for r in rows)
    assert names == ["20261105.html", "20261109.html",
                     "arxiv_digest_20261101.html", "arxiv_digest_20261105.html",
                     "arxiv_digest_20261109.html"]
    assert all(isinstance(r[0], datetime.date) for r in rows)


def test_scan_issues_tolerates_missing_dir(helper, out):
    assert helper["scan_issues"](str(out / "nope")) == []


def test_choose_default_picks_latest_issue_date(helper, out):
    rows = helper["scan_issues"](str(out))
    got = helper["choose_issue"](rows, None)
    assert _base(got) == "arxiv_digest_20261109.html"


@pytest.mark.parametrize("target,expected", [
    (datetime.date(2026, 11, 9), "arxiv_digest_20261109.html"),   # 含指定当天
    (datetime.date(2026, 11, 8), "20261105.html"),                 # 不晚于且最接近
    (datetime.date(2026, 11, 5), "20261105.html"),
    (datetime.date(2026, 11, 2), "arxiv_digest_20261101.html"),
    (datetime.date(2026, 12, 31), "arxiv_digest_20261109.html"),   # 未来日期回落到最新
])
def test_choose_closest_issue_not_later_than_target(helper, out, target, expected):
    rows = helper["scan_issues"](str(out))
    assert _base(helper["choose_issue"](rows, target)) == expected


def test_choose_returns_none_when_all_issues_are_later(helper, out):
    rows = helper["scan_issues"](str(out))
    assert helper["choose_issue"](rows, datetime.date(2026, 10, 31)) is None


def test_choose_same_issue_date_prefers_newest_generation_time(helper):
    d = _make_out("dup", {
        "arxiv_digest_20261201.html": 2000,
        "arxiv_digest_20261201_v2.html": 2100,
        "archive/20261201.html": 2200,
    })
    rows = helper["scan_issues"](str(d))
    assert _base(helper["choose_issue"](rows, datetime.date(2026, 12, 1))) == "20261201.html"


def test_choose_same_mtime_prefers_canonical_root_file(helper):
    d = _make_out("tie", {
        "arxiv_digest_20261201.html": 2000,
        "archive/20261201.html": 2000,
    })
    rows = helper["scan_issues"](str(d))
    assert _base(helper["choose_issue"](rows, datetime.date(2026, 12, 1))) == \
        "arxiv_digest_20261201.html"


# ------------------------------------------------------------------ 五、resolve / 输出契约
def test_resolve_no_args_opens_latest_and_no_preset(helper, out):
    path, flags, err = helper["resolve"](str(out), [])
    assert _base(path) == "arxiv_digest_20261109.html" and flags == "" and err == ""


def test_resolve_keeps_preset_flags_when_date_is_invalid(helper, out):
    path, flags, err = helper["resolve"](str(out), ["hengxin", "force", "2026-02-30"])
    assert path == ""                       # 不打开任何文件
    assert flags == "--preset hengxin --preset-force"
    assert "日期" in err


def test_resolve_reports_no_match_without_falling_back_to_wrong_file(helper, out):
    path, _flags, err = helper["resolve"](str(out), ["2026-10-31"])
    assert path == ""
    assert "找不到" in err and "2026-11-01" in err


def test_resolve_empty_output_dir_is_a_clear_error(helper):
    d = _make_out("empty", {})
    path, _flags, err = helper["resolve"](str(d), [])
    assert path == "" and "未" in err
    path2, _f2, err2 = helper["resolve"](str(d), ["2026-11-11"])
    assert path2 == "" and "找不到" in err2


def test_browser_allowed_follows_config(helper, out):
    cfg = out / "config.json"          # 只测读配置，不往共享的 tmp_pytest/ 写文件
    check = helper["browser_allowed"]
    assert check(str(cfg)) is True                      # 文件不存在 → 默认开
    cfg.write_text(json.dumps({"open_browser": False}), encoding="utf-8")
    assert check(str(cfg)) is False
    cfg.write_text(json.dumps({"open_browser": "no"}), encoding="utf-8")
    assert check(str(cfg)) is False
    cfg.write_text(json.dumps({"open_browser": "yes"}), encoding="utf-8")
    assert check(str(cfg)) is True
    cfg.write_text("{broken", encoding="utf-8")
    assert check(str(cfg)) is True                      # 坏配置不能拖垮启动


def test_main_emits_key_value_contract(helper, out, monkeypatch, capsys):
    monkeypatch.setitem(helper, "browser_allowed", lambda _p: True)
    monkeypatch.setattr(sys, "argv", ["helper", str(out), "2026-11-07"])
    rc = helper["main"]()
    lines = dict(line.split("=", 1) for line in capsys.readouterr().out.strip().splitlines())
    assert rc == 0
    assert set(lines) == {"PRESETFLAGS", "DIGEST", "OPEN"}
    assert _base(lines["DIGEST"]) == "20261105.html"
    assert lines["OPEN"] == "1"


def test_main_emits_empty_digest_plus_err_on_failure(helper, out, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["helper", str(out), "2026-11-1"])
    rc = helper["main"]()
    lines = dict(line.split("=", 1) for line in capsys.readouterr().out.strip().splitlines())
    assert rc == 1
    assert lines["DIGEST"] == "" and "日期" in lines["ERR"]


# ------------------------------------------------------------------ 六、真实引导串
def _bootstrap_code(bat_text):
    """只取 for /f 那行的 -c 串（文件里还有一条 Python 版本检查的 -c）。"""
    line = next(l for l in bat_text.splitlines() if l.startswith("for /f "))
    m = re.search(r'-c "([^"]+)"', line)
    assert m, "找不到 python -c 引导串"
    return m.group(1)


def _run_bootstrap(bat_text, out, args, capsys):
    """在进程内执行**脚本里那一串 -c 代码**（标记抽取 + argv 改写 + exec 帮助块）。

    不另起 Python 进程：全量套件里集成测试会留下继承 stdio 句柄的子进程，
    Windows 上偶发让 communicate() 等不到 EOF；而这里要验的是引导串本身，
    in-process exec 等价且确定性更好。真实 cmd 层由下面的干跑用例覆盖。
    """
    code = _bootstrap_code(bat_text)
    saved = sys.argv
    try:
        # 对齐 `python -c CODE bat out [args...]`：argv[0] 是 -c 占位，
        # 引导串才会把 a[1] 当脚本、a[2] 当 output 目录。
        sys.argv = ["-c", str(BAT), str(out)] + list(args)
        rc = 0
        try:
            exec(compile(code, str(BAT), "exec"), {"__name__": "__main__"})
        except SystemExit as e:
            rc = e.code or 0
        text = capsys.readouterr().out
    finally:
        sys.argv = saved
    rows = dict(line.split("=", 1) for line in text.strip().splitlines() if "=" in line)
    return rc, rows


@pytest.mark.parametrize("args,expected", [
    ([], "arxiv_digest_20261109.html"),
    (["2026-11-07"], "20261105.html"),
    (["--date=2026-11-09"], "arxiv_digest_20261109.html"),
    (["hengxin", "2026-11-05"], "20261105.html"),
])
def test_bootstrap_code_uses_the_real_bat_helpers(bat_text, out, args, expected, capsys):
    rc, rows = _run_bootstrap(bat_text, out, args, capsys)
    assert rc == 0
    assert _base(rows["DIGEST"]) == expected
    assert "ERR" not in rows


def test_bootstrap_code_returns_no_path_on_invalid_date(bat_text, out, capsys):
    rc, rows = _run_bootstrap(bat_text, out, ["2026-02-30"], capsys)
    assert rc == 1
    assert rows["DIGEST"] == "" and "日期" in rows["ERR"]


# ------------------------------------------------------------------ 七、cmd 干跑
def _make_case(tag, files, open_browser=None):
    """独立父目录的 output/（便于在父目录放 config.json，不污染共享目录）。"""
    TMP.mkdir(exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix="bat-%s-" % tag, dir=str(TMP)))
    d = base / "output"
    (d / "archive").mkdir(parents=True)
    for rel, ts in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("<html>digest</html>", encoding="utf-8")
        os.utime(str(p), (ts, ts))
    if open_browser is not None:
        (base / "config.json").write_text(
            json.dumps({"open_browser": open_browser}), encoding="utf-8")
    return base, d


def _dry_run(bat_text, out, args):
    TMP.mkdir(exist_ok=True)
    bat = Path(tempfile.mkdtemp(prefix="bat-run-", dir=str(TMP))) / "start_digest_dryrun.bat"
    dry = (bat_text
           .replace('"%~dp0output"', '"%s"' % str(out))
           .replace('start "" "!DP_DIGEST!"', 'echo DRYOPEN=!DP_DIGEST!')
           .replace('%PY% server.py !DP_PRESETFLAGS! --no-open',
                    'echo DRYSERVER=!DP_PRESETFLAGS!')
           .replace("pause", "rem pause"))
    bat.write_text(dry, encoding="utf-8")
    r = subprocess.run(["cmd", "/c", str(bat)] + list(args), capture_output=True,
                       text=True, stdin=subprocess.DEVNULL,
                       encoding="utf-8", errors="replace", timeout=60)
    return r.stdout or ""


@batcmd
@pytest.mark.skipif(os.name != "nt", reason="start_digest.bat 只在 Windows 上运行")
def test_cmd_no_args_is_compatible_and_opens_latest(bat_text, out):
    text = _dry_run(bat_text, out, [])
    assert "DRYOPEN=" in text
    assert "arxiv_digest_20261109.html" in text
    assert "DRYSERVER=" in text
    assert "Starting local paper server" in text


@batcmd
@pytest.mark.skipif(os.name != "nt", reason="start_digest.bat 只在 Windows 上运行")
def test_cmd_date_and_legacy_preset_flags(bat_text, out):
    text = _dry_run(bat_text, out, ["hengxin", "force", "2026-11-07"])
    assert "20261105.html" in text
    assert "DRYSERVER=--preset hengxin --preset-force" in text


@batcmd
@pytest.mark.skipif(os.name != "nt", reason="start_digest.bat 只在 Windows 上运行")
@pytest.mark.parametrize("args,kw", [
    (["2026-02-30"], "日期不存在"),
    (["2026-11-1"], "日期参数不合法"),
    (["2026-10-31"], "找不到期次日期"),
])
def test_cmd_bad_input_prints_hint_and_opens_nothing(bat_text, out, args, kw):
    text = _dry_run(bat_text, out, args)
    assert kw in text
    assert "本次不打开任何 HTML" in text
    assert "DRYOPEN=" not in text                # 绝不打开错误文件
    assert "DRYSERVER=" in text                 # 但服务照常启动


@batcmd
@pytest.mark.skipif(os.name != "nt", reason="start_digest.bat 只在 Windows 上运行")
def test_cmd_open_browser_false_skips_opening(bat_text):
    _base_dir, d = _make_case("cfg", {"arxiv_digest_20261109.html": 1200},
                              open_browser=False)
    text = _dry_run(bat_text, d, [])
    assert "open_browser=false" in text
    assert "DRYOPEN=" not in text
    assert "DRYSERVER=" in text
