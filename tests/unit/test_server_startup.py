# -*- coding: utf-8 -*-
"""server 的启动逻辑：端口顺延、启动日志、浏览器开关、运行期信息。

为什么这些要单独测：`main()` 里的顺序一旦错（先开浏览器后定端口、或者日志打的是
"期望端口"而不是"实际端口"），用户拿到的就是一个点不动的页面 —— 而这类问题在
单元测试之外很难发现（要真的占住 8765 再看）。
"""
import socket

import pytest

import paperutil as pu
import serveport as SP
import server as S

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------ 辅助

class _FakeServer:
    """替身：serve_forever 立刻抛 KeyboardInterrupt，让 run() 走到收尾分支。"""

    def __init__(self, addr, handler=None):
        self.server_address = (addr[0], addr[1])
        self.bound_port = addr[1]
        self.handler = handler

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        pass


@pytest.fixture()
def no_loop(monkeypatch):
    """不真的进入事件循环，也不用真的 bind（端口选择仍是真的）。"""
    monkeypatch.setattr(S, "ThreadingHTTPServer", _FakeServer)
    monkeypatch.setattr(pu, "RUNTIME_PORT", None)     # 运行期状态不跨用例泄漏
    return _FakeServer


@pytest.fixture()
def opened(monkeypatch):
    """记录「打开了哪个地址」，不发真浏览器。"""
    seen = []
    monkeypatch.setattr(SP, "open_browser", lambda url, **kw: seen.append(url))
    return seen


@pytest.fixture()
def busy():
    """占住一个临时端口，模拟「默认端口被别的软件占用」。

    刻意避开 65000 以上：紧邻 65535 时「顺延一个」可能越界，用例会变成偶发失败。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for _ in range(20):
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        if sock.getsockname()[1] < 65000:
            break
        sock.close()
    try:
        yield sock.getsockname()[1]
    finally:
        sock.close()


# ------------------------------------------------------------------ 端口顺延

def test_bind_server_skips_busy_port(busy):
    srv, port, tried = S.bind_server(busy)
    try:
        assert port > busy and port != busy
        assert tried[0] == busy, "顺延从被占的端口开始尝试"
        assert srv.server_address[1] == port, "服务必须绑在报出来的那个端口上"
    finally:
        srv.server_close()


def test_bind_server_raises_when_ports_exhausted(monkeypatch):
    monkeypatch.setattr(SP, "find_free_port", lambda *a, **k: (None, [8765, 8766]))
    with pytest.raises(S.PortUnavailable):
        S.bind_server(8765)


def test_bind_server_retries_once_when_bind_is_raced(monkeypatch, capsys):
    """探测说空着、真 bind 却失败（被抢）时，顺延重试而不是直接崩。"""
    calls = []

    def fake_find(start, limit=SP.SCAN_LIMIT, host=SP.HOST):
        calls.append(start)
        return (start, [start])

    class Flaky(_FakeServer):
        def __init__(self, addr, handler=None):
            if addr[1] == 8765:
                raise OSError("address already in use")
            super().__init__(addr, handler)

    monkeypatch.setattr(SP, "find_free_port", fake_find)
    monkeypatch.setattr(S, "ThreadingHTTPServer", Flaky)
    srv, port, _tried = S.bind_server(8765)
    srv.server_close()
    assert port == 8766
    assert calls == [8765, 8766], "第二轮应从失败端口的后一个开始"
    assert "绑定失败" in capsys.readouterr().err


def test_run_reports_exhausted_ports_and_exits_2(no_loop, monkeypatch, sandbox, capsys):
    def boom(*a, **k):
        raise S.PortUnavailable("从 8765 起连续 20 个端口都不可用")

    monkeypatch.setattr(S, "bind_server", boom)
    assert S.run([]) == 2
    err = capsys.readouterr().err
    assert "不可用" in err and "--port" in err
    assert not (sandbox.out / "server.json").exists(), "没起来就不该留下运行期信息"


# ------------------------------------------------------------------ 日志与落盘

def test_run_logs_actual_port_when_shifted(busy, no_loop, opened, sandbox, monkeypatch, capsys):
    sandbox.set_config(port=busy)
    assert S.run([]) == 0
    out = capsys.readouterr().out
    assert pu.effective_port() > busy
    assert "serving %s" % SP.url_for(pu.effective_port()) in out
    assert "已向后顺延" in out and str(busy) in out
    assert opened == [SP.url_for(pu.effective_port())], "浏览器要开在实际端口上"


def test_run_logs_plain_port_when_free(no_loop, opened, sandbox, monkeypatch, capsys):
    monkeypatch.setattr(SP, "find_free_port", lambda start, **k: (start, [start]))
    sandbox.set_config(port=9123)
    assert S.run([]) == 0
    out = capsys.readouterr().out
    assert "serving http://127.0.0.1:9123" in out
    assert "未被占用" in out


def test_run_writes_runtime_info_and_publishes_port(no_loop, opened, sandbox, monkeypatch):
    monkeypatch.setattr(SP, "find_free_port", lambda start, **k: (start, [start]))
    sandbox.set_config(port=9124)
    assert S.run([]) == 0
    info = SP.read_runtime_info(str(sandbox.out / "server.json"))
    assert info["port"] == 9124 and info["url"] == "http://127.0.0.1:9124"
    assert info["pid"] > 0
    # 路由层与渲染层都必须看到这个端口（否则页面会指回 config.port）
    assert pu.effective_port() == 9124


# ------------------------------------------------------------------ 参数与配置

def test_run_port_argument_overrides_config(no_loop, opened, sandbox, monkeypatch):
    monkeypatch.setattr(SP, "find_free_port", lambda start, **k: (start, [start]))
    sandbox.set_config(port=9125)
    assert S.run(["--port", "9321"]) == 0
    assert pu.effective_port() == 9321


def test_run_ignores_invalid_port_argument(no_loop, opened, sandbox, monkeypatch):
    """`--port abc` 不该让服务起不来，回落到配置端口。"""
    monkeypatch.setattr(SP, "find_free_port", lambda start, **k: (start, [start]))
    sandbox.set_config(port=9126)
    assert S.run(["--port", "abc"]) == 0
    assert pu.effective_port() == 9126


def test_run_falls_back_when_config_port_is_invalid(no_loop, opened, sandbox, monkeypatch):
    seen = []
    monkeypatch.setattr(SP, "find_free_port",
                        lambda start, **k: (seen.append(start), (start, [start]))[1])
    sandbox.set_config(port="not-a-number")
    assert S.run([]) == 0
    assert seen == [SP.DEFAULT_PORT]


# ------------------------------------------------------------------ 浏览器开关

@pytest.mark.parametrize("argv,cfg,should_open", [
    ([], {}, True),
    ([], {"open_browser": False}, False),
    (["--no-open"], {}, False),
    (["--open"], {"open_browser": False}, True),
])
def test_run_respects_browser_switch(argv, cfg, should_open, no_loop, opened,
                                     sandbox, monkeypatch):
    monkeypatch.setattr(SP, "find_free_port", lambda start, **k: (start, [start]))
    sandbox.set_config(port=9127, **cfg)
    assert S.run(argv) == 0
    assert bool(opened) is should_open


def test_run_survives_browser_failure(no_loop, sandbox, monkeypatch, capsys):
    """无桌面环境：开浏览器炸了也不能影响服务（启动流程照常返回 0）。"""
    monkeypatch.setattr(SP, "find_free_port", lambda start, **k: (start, [start]))
    sandbox.set_config(port=9128)

    def boom(url, **kw):
        raise RuntimeError("no display")

    monkeypatch.setattr(SP, "open_browser", boom)
    assert S.run([]) == 0
    assert "手动访问 http://127.0.0.1:9128" in capsys.readouterr().out


# ------------------------------------------------------------------ 与 run_daily 的契约

def test_runtime_info_file_is_what_run_daily_reads(no_loop, opened, sandbox, monkeypatch):
    """run_daily 只能靠这个文件发现「服务自己又顺延了一次」，格式必须稳定。"""
    import run_daily as RD

    monkeypatch.setattr(SP, "find_free_port", lambda start, **k: (start, [start]))
    sandbox.set_config(port=9129)
    assert S.run([]) == 0
    assert RD._runtime_info_path() == str(sandbox.out / "server.json")
    info = SP.read_runtime_info(RD._runtime_info_path())
    assert info["port"] == pu.effective_port()
