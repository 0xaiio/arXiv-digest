# -*- coding: utf-8 -*-
"""run_daily 的两个底层能力：子进程封装 `run()` 与服务拉起 `ensure_server()`。

这两个函数决定了「抓取失败时会不会把上一期数据冲掉」和「服务会不会起在错误的
工作目录」，都属于改一行就可能静默出错的地方。
"""
import json
import sys

import pytest

import run_daily as RD

pytestmark = pytest.mark.unit


@pytest.fixture()
def script_dir(sandbox, monkeypatch):
    """把 RD.HERE 指到沙箱，脚本用 Python 一行代码模拟抓取进程。"""
    d = sandbox.root
    monkeypatch.setattr(RD, "HERE", str(d))
    monkeypatch.setattr(RD, "PY", sys.executable)
    monkeypatch.setattr(RD, "OUT", str(sandbox.out))
    return d


def _write_script(d, name, body):
    (d / name).write_text(body, encoding="utf-8")


def test_run_writes_capture_on_success(script_dir, sandbox):
    _write_script(script_dir, "ok.py",
                  'import json;print(json.dumps({"papers":[{"id":"x"}]}))')
    assert RD.run("ok.py", capture="raw.json") is True
    assert sandbox.read("raw.json")["papers"][0]["id"] == "x"


def test_run_keeps_previous_pool_on_bad_payload(script_dir, sandbox):
    """抓取输出无效时绝不能覆盖上一期 —— 这是「历史数据被清空」的唯一防线。"""
    sandbox.write("raw.json", {"papers": [{"id": "keep-me"}]})
    _write_script(script_dir, "bad.py",
                  'import json;print(json.dumps({"error":"no data"}))')

    assert RD.run("bad.py", capture="raw.json", keep_previous=True) is False
    assert sandbox.read("raw.json")["papers"][0]["id"] == "keep-me"
    bads = list(sandbox.out.glob("raw.json.bad_*"))
    assert bads, "坏输出应另存，便于排查"


def test_run_records_empty_output_when_no_history(script_dir, sandbox):
    _write_script(script_dir, "bad.py", 'print("")')
    assert RD.run("bad.py", capture="raw.json") is False
    assert sandbox.exists("raw.json"), "没有历史数据时仍要落盘，让下游报错真实"


def test_run_raises_for_non_capture_scripts(script_dir):
    _write_script(script_dir, "boom.py", "raise SystemExit(3)")
    with pytest.raises(SystemExit):
        RD.run("boom.py")


def test_run_without_capture_succeeds(script_dir):
    _write_script(script_dir, "quiet.py", "print('done')")
    assert RD.run("quiet.py") is True


# ------------------------------------------------------------------ 服务拉起

@pytest.fixture()
def fake_popen(monkeypatch):
    calls = []

    class Proc:
        pass

    def popen(cmd, **kw):
        calls.append((cmd, kw))
        return Proc()

    monkeypatch.setattr(RD.subprocess, "Popen", popen)
    return calls


def test_ensure_server_reuses_running_instance(monkeypatch, sandbox):
    monkeypatch.setattr(RD, "server_alive", lambda port, timeout=2.0: True)
    url, started = RD.ensure_server(port=8765)
    assert url == "http://127.0.0.1:8765" and started is False


def test_ensure_server_starts_and_waits(monkeypatch, sandbox, fake_popen):
    state = {"n": 0}

    def alive(port, timeout=2.0):
        state["n"] += 1
        return state["n"] > 1          # 第一次 False（拉起），之后 True（就绪）

    monkeypatch.setattr(RD, "server_alive", alive)
    monkeypatch.setattr(RD.time, "sleep", lambda *_: None)
    url, started = RD.ensure_server(port=8791, wait=5)
    assert url == "http://127.0.0.1:8791" and started is True
    assert fake_popen, "应真的尝试拉起子进程"
    cmd, kw = fake_popen[0]
    assert kw.get("cwd") == RD.HERE, "cwd 必须是项目根"


def test_ensure_server_reports_timeout(monkeypatch, sandbox, fake_popen):
    monkeypatch.setattr(RD, "server_alive", lambda port, timeout=2.0: False)
    monkeypatch.setattr(RD.time, "sleep", lambda *_: None)
    monkeypatch.setattr(RD.time, "time", lambda: 0.0)     # 立刻超时
    url, started = RD.ensure_server(port=8791, wait=0)
    assert started is False


def test_ensure_server_survives_spawn_failure(monkeypatch, sandbox):
    monkeypatch.setattr(RD, "server_alive", lambda port, timeout=2.0: False)

    def boom(*a, **k):
        raise OSError("cannot spawn")

    monkeypatch.setattr(RD.subprocess, "Popen", boom)
    url, started = RD.ensure_server(port=8791)
    assert url.endswith(":8791") and started is False, "起不来也不能让流水线崩掉"


def test_port_of_reads_config(sandbox, monkeypatch):
    sandbox.set_config(port=9001)
    assert RD.port_of() == 9001
