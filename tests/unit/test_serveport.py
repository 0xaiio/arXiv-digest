# -*- coding: utf-8 -*-
"""serveport：端口解析、占用探测与顺延、浏览器开关、运行期信息落盘。

这一层的价值全在「边界」上：非法端口、连续占用、端口耗尽、无桌面环境、
进程在探测与绑定之间被抢。每条都单独钉住，避免以后改一行变成静默丢功能。
"""
import json
import socket

import pytest

import paperutil as pu
import serveport as SP

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------ 端口解析

@pytest.mark.parametrize("value,expected", [
    (8765, 8765),
    ("8765", 8765),
    (" 8765 ", 8765),
    (1, 1),
    (65535, 65535),
    (0, None),          # 0 = 内核随机分配，不是可配置的端口
    (-1, None),
    (65536, None),
    ("70000", None),
    ("abc", None),
    ("", None),
    (None, None),
    (8765.9, None),      # float 字符串化是 "8765.9"，int() 失败 → 非法
])
def test_valid_port(value, expected):
    assert SP.valid_port(value) == expected


@pytest.mark.parametrize("cfg,expected", [
    ({}, SP.DEFAULT_PORT),
    ({"port": 9001}, 9001),
    ({"port": "9001"}, 9001),
    ({"port": "abc"}, SP.DEFAULT_PORT),   # 手写坏的配置不能让服务起不来
    ({"port": 99999}, SP.DEFAULT_PORT),
    (None, SP.DEFAULT_PORT),
])
def test_configured_port_falls_back_instead_of_raising(cfg, expected):
    assert SP.configured_port(cfg) == expected


def test_url_for_is_loopback():
    assert SP.url_for(8765) == "http://127.0.0.1:8765"


# ------------------------------------------------------------------ 占用探测

@pytest.fixture()
def listener():
    """真监听一个临时端口（返回 (sock, port)），用完关掉。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    try:
        yield sock, sock.getsockname()[1]
    finally:
        sock.close()


def test_port_in_use_sees_listening_socket(listener):
    _sock, port = listener
    assert SP.port_in_use(port) is True
    assert SP.usable(port) is False


def test_port_in_use_false_after_close():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    assert SP.port_in_use(port) is False


def test_can_bind_false_for_unassignable_host():
    """地址不属于本机时不能算「可用」——这是 connect 探测看不到的那一半。"""
    assert SP.can_bind(8765, host="192.0.2.1") is False


# ------------------------------------------------------------------ 顺延查找

def test_find_free_port_skips_busy_port(listener):
    _sock, busy = listener
    port, tried = SP.find_free_port(busy, limit=5)
    assert tried[0] == busy, "第一个候选就是被占用的那个端口"
    assert port is not None and port > busy


def test_find_free_port_respects_limit(monkeypatch):
    monkeypatch.setattr(SP, "port_in_use", lambda *a, **k: True)
    port, tried = SP.find_free_port(8700, limit=3)
    assert port is None
    assert tried == [8700, 8701, 8702], "上限是候选个数，不是尝试次数之外的东西"


def test_find_free_port_stops_at_max_port(monkeypatch):
    """端口耗尽：绝不从 65535 绕回 1（那会偷偷占一个低端口）。"""
    monkeypatch.setattr(SP, "port_in_use", lambda *a, **k: True)
    port, tried = SP.find_free_port(65530, limit=20)
    assert port is None
    assert tried[0] == 65530 and tried[-1] == SP.MAX_PORT
    assert len(tried) == SP.MAX_PORT - 65530 + 1
    assert all(p >= 65530 for p in tried)


def test_find_free_port_normalises_bad_start(monkeypatch):
    monkeypatch.setattr(SP, "usable", lambda *a, **k: True)
    port, tried = SP.find_free_port("not-a-port")
    assert port == SP.DEFAULT_PORT and tried == [SP.DEFAULT_PORT]


def test_find_free_port_needs_both_probes(monkeypatch):
    """connect 说空着、bind 说不行 → 仍然跳过（Windows 端口劫持场景）。"""
    monkeypatch.setattr(SP, "port_in_use", lambda *a, **k: False)
    monkeypatch.setattr(SP, "can_bind", lambda port, host=SP.HOST: port != 8765)
    port, tried = SP.find_free_port(8765, limit=3)
    assert port == 8766 and tried == [8765, 8766]


# ------------------------------------------------------------------ 页面端口改写

def test_rewrite_api_port_replaces_baked_value():
    text = "<script>var APIPORT=8765;var u='http://127.0.0.1:'+APIPORT;</script>"
    out = SP.rewrite_api_port(text, 8766)
    assert "var APIPORT=8766;" in out
    assert out.count("APIPORT=8766") == 1
    assert "'+APIPORT" in out, "读取点（String(APIPORT) / +APIPORT）不能被改写"


def test_rewrite_api_port_is_noop_without_marker():
    assert SP.rewrite_api_port("<html>no port</html>", 8766) == "<html>no port</html>"


def test_rewrite_api_port_ignores_invalid_target():
    text = "var APIPORT=8765;"
    assert SP.rewrite_api_port(text, None) == text
    assert SP.rewrite_api_port(text, 0) == text
    assert SP.rewrite_api_port("", 8766) == ""


def test_rewrite_api_port_is_idempotent():
    once = SP.rewrite_api_port("var APIPORT=8765;", 8766)
    assert SP.rewrite_api_port(once, 8766) == once


# ------------------------------------------------------------------ 浏览器开关

@pytest.mark.parametrize("argv,cfg,expected", [
    ([], {}, True),                                     # 默认打开
    ([], {"open_browser": True}, True),
    ([], {"open_browser": False}, False),
    ([], {"open_browser": "false"}, False),              # 手写成字符串也要认
    ([], {"open_browser": "off"}, False),
    (["--no-open"], {"open_browser": True}, False),      # 命令行优先于配置
    (["--open"], {"open_browser": False}, True),
    (["--no-open", "--open"], {}, False),                # 同时给时以「关」为准
    (["--preset", "x"], {}, True),
])
def test_browser_enabled_precedence(argv, cfg, expected):
    assert SP.browser_enabled(argv, cfg) is expected


def test_open_browser_calls_opener_asynchronously():
    seen = []

    def opener(url):
        seen.append(url)
        return True

    timer = SP.open_browser("http://127.0.0.1:8765", delay=0, opener=opener)
    timer.join(5)
    assert seen == ["http://127.0.0.1:8765"]


def test_open_browser_swallows_opener_exception(capsys):
    """无桌面环境（webbrowser 抛错）不得让启动失败，只打一行提示。"""
    def boom(_url):
        raise RuntimeError("no runnable browser")

    timer = SP.open_browser("http://127.0.0.1:8765", delay=0, opener=boom)
    timer.join(5)
    assert "请手动访问" in capsys.readouterr().out


def test_open_browser_reports_when_opener_declines(capsys):
    timer = SP.open_browser("http://127.0.0.1:8765", delay=0, opener=lambda u: False)
    timer.join(5)
    assert "http://127.0.0.1:8765" in capsys.readouterr().out


# ------------------------------------------------------------------ 运行期信息

def test_runtime_info_roundtrip(sandbox):
    path = str(sandbox.out / "server.json")
    info = SP.write_runtime_info(path, 8766, pid=1234, when="2026-10-20 16:00:00")
    assert info["url"] == "http://127.0.0.1:8766"

    back = SP.read_runtime_info(path)
    assert back["port"] == 8766 and back["pid"] == 1234
    assert back["started_at"] == "2026-10-20 16:00:00"
    assert json.loads(open(path, encoding="utf-8").read())["port"] == 8766


def test_runtime_info_missing_or_corrupt_is_none(sandbox):
    assert SP.read_runtime_info(str(sandbox.out / "nope.json")) is None
    bad = sandbox.out / "server.json"
    bad.write_text("{not json", encoding="utf-8")
    assert SP.read_runtime_info(str(bad)) is None
    bad.write_text(json.dumps({"port": "abc"}), encoding="utf-8")
    assert SP.read_runtime_info(str(bad)) is None
    bad.write_text(json.dumps(["list"]), encoding="utf-8")
    assert SP.read_runtime_info(str(bad)) is None


def test_runtime_info_write_failure_returns_none(sandbox):
    """落盘只是辅助信息：目录不可用时返回 None，不抛、也不留垃圾文件。"""
    blocker = sandbox.out / "blocker"
    blocker.write_text("x", encoding="utf-8")
    assert SP.write_runtime_info(str(blocker / "server.json"), 8765) is None


# ------------------------------------------------------------------ 与 paperutil 的接口

def test_effective_port_prefers_runtime_override(sandbox, monkeypatch):
    sandbox.set_config(port=9100)
    assert pu.effective_port() == 9100

    monkeypatch.setattr(pu, "RUNTIME_PORT", 9200)
    assert pu.effective_port() == 9200, "服务顺延后页面必须指向真实端口"


def test_effective_port_survives_broken_config(sandbox):
    sandbox.set_config(port="oops")
    assert pu.effective_port() == SP.DEFAULT_PORT


def test_set_runtime_port_normalises(monkeypatch):
    monkeypatch.setattr(pu, "RUNTIME_PORT", None)
    assert pu.set_runtime_port("9300") == 9300
    assert pu.RUNTIME_PORT == 9300
    assert pu.set_runtime_port(0) is None
    assert pu.RUNTIME_PORT is None
