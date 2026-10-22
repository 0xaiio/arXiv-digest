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


@pytest.fixture()
def fixed_free_port(monkeypatch):
    """让端口选择返回起点本身 —— 用例不该依赖本机 8791 恰好空着。"""
    monkeypatch.setattr(RD.serveport, "find_free_port",
                        lambda start, **k: (start, [start]))
    return None


def test_ensure_server_reuses_running_instance(monkeypatch, sandbox):
    monkeypatch.setattr(RD, "server_alive", lambda port, timeout=2.0: True)
    url, started = RD.ensure_server(port=8765)
    assert url == "http://127.0.0.1:8765" and started is False


def test_ensure_server_starts_and_waits(monkeypatch, sandbox, fake_popen, fixed_free_port):
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
    assert cmd[-2:] == ["--port", "8791"], "端口要显式传给 server.py"


def test_ensure_server_reports_timeout(monkeypatch, sandbox, fake_popen, fixed_free_port):
    monkeypatch.setattr(RD, "server_alive", lambda port, timeout=2.0: False)
    monkeypatch.setattr(RD.time, "sleep", lambda *_: None)
    monkeypatch.setattr(RD.time, "time", lambda: 0.0)     # 立刻超时
    url, started = RD.ensure_server(port=8791, wait=0)
    assert started is False


def test_ensure_server_survives_spawn_failure(monkeypatch, sandbox, fixed_free_port):
    monkeypatch.setattr(RD, "server_alive", lambda port, timeout=2.0: False)

    def boom(*a, **k):
        raise OSError("cannot spawn")

    monkeypatch.setattr(RD.subprocess, "Popen", boom)
    url, started = RD.ensure_server(port=8791)
    assert url.endswith(":8791") and started is False, "起不来也不能让流水线崩掉"


# ---------------------------------------------------------------- 端口顺延（2026-10-20）

@pytest.fixture()
def busy_port():
    """真占住一个端口，模拟「config 里的端口被别的软件用着」。"""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for _ in range(20):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        if sock.getsockname()[1] < 65000:
            break
        sock.close()
    try:
        yield sock.getsockname()[1]
    finally:
        sock.close()


def test_ensure_server_shifts_port_when_busy(busy_port, monkeypatch, sandbox, fake_popen):
    """端口被占时：自己先选空闲端口再传给 server.py，轮询的端口就是它绑的端口。"""
    started_ports = []

    def alive(port, timeout=2.0):
        started_ports.append(port)
        return port != busy_port       # 被占的那个永远"不通"，顺延后的可以

    monkeypatch.setattr(RD, "server_alive", alive)
    monkeypatch.setattr(RD.time, "sleep", lambda *_: None)
    url, started = RD.ensure_server(port=busy_port, wait=5)

    assert started is True
    assert url != "http://127.0.0.1:%d" % busy_port
    asked = int(url.rsplit(":", 1)[1])
    assert asked > busy_port
    cmd, _kw = fake_popen[0]
    assert cmd[-2:] == ["--port", str(asked)], "传下去的端口必须与轮询的一致"


def test_ensure_server_reports_exhausted_ports(monkeypatch, sandbox, fake_popen, capsys):
    monkeypatch.setattr(RD, "server_alive", lambda port, timeout=2.0: False)
    monkeypatch.setattr(RD.serveport, "find_free_port",
                        lambda start, **k: (None, [start, start + 1]))
    url, started = RD.ensure_server(port=8765)
    assert started is False
    err = capsys.readouterr().err
    assert "都不可用" in err and "config.json" in err
    assert not fake_popen, "选不到端口就不该拉起进程"


def test_ensure_server_adopts_actual_port_from_runtime_info(monkeypatch, sandbox, fake_popen):
    """极端竞态：选完端口又被抢，服务自己顺延了 —— 以它落盘的 server.json 为准。"""
    import json

    (sandbox.out / "server.json").write_text(
        json.dumps({"port": 8777, "url": "http://127.0.0.1:8777", "pid": 1,
                    "started_at": "2026-10-20 16:00:00"}), encoding="utf-8")
    monkeypatch.setattr(RD, "server_alive", lambda port, timeout=2.0: port == 8777)
    monkeypatch.setattr(RD.time, "sleep", lambda *_: None)
    url, started = RD.ensure_server(port=8791, wait=5)
    assert started is True and url == "http://127.0.0.1:8777"


def test_port_of_reads_config(sandbox, monkeypatch):
    sandbox.set_config(port=9001)
    assert RD.port_of() == 9001


# ------------------------------------------------------------------ --preset 启动参数

def _pack(sandbox, name="demo", cats=("cs.DB",)):
    sandbox.make_pack(name, {"config.json": {"categories": list(cats),
                                             "download_dir": "papers"}})


def test_apply_preset_arg_is_noop_without_flag(sandbox):
    _pack(sandbox)
    before = sandbox.config()
    assert RD.apply_preset_arg(["--skip-fetch"]) is True
    assert sandbox.config() == before


def test_apply_preset_arg_imports_on_clean_machine(bare_sandbox):
    _pack(bare_sandbox)
    assert RD.apply_preset_arg(["--preset", "demo"]) is True
    assert bare_sandbox.config()["categories"] == ["cs.DB"]


def test_apply_preset_arg_replaces_pristine_template(bare_sandbox):
    _pack(bare_sandbox)
    assert RD.apply_preset_arg(["--preset", "demo"]) is True
    assert bare_sandbox.config()["categories"] == ["cs.DB"]


def test_apply_preset_arg_refuses_to_clobber_existing_config(sandbox, capsys):
    """用户改过的配置不覆盖，且**不阻断**启动（返回 False 但继续跑）。"""
    sandbox.set_config(categories=["cs.LG"])          # 不再是模板初值
    _pack(sandbox, cats=("cs.PL",))
    assert RD.apply_preset_arg(["--preset", "demo"]) is False
    assert sandbox.config()["categories"] == ["cs.LG"]
    assert "未完全导入" in capsys.readouterr().err


def test_apply_preset_arg_force_overrides(sandbox):
    sandbox.set_config(categories=["cs.LG"])
    _pack(sandbox, cats=("cs.PL",))
    assert RD.apply_preset_arg(["--preset", "demo", "--preset-force"]) is True
    assert sandbox.config()["categories"] == ["cs.PL"]


def test_preset_runs_before_categories_flag(sandbox):
    """`--preset` 先导入、`--categories` 再覆盖：类别以命令行显式值为准。"""
    _pack(sandbox, cats=("cs.DB",))
    RD.apply_preset_arg(["--preset", "demo", "--preset-force"])
    assert RD.apply_categories_arg(["--categories", "cs.LG,cs.DC"]) is True
    assert sandbox.config()["categories"] == ["cs.LG", "cs.DC"]


def test_server_apply_preset_arg_matches_run_daily(sandbox):
    """服务与流水线必须用同一套导入语义（同一函数），只差参数名。"""
    import server as S

    _pack(sandbox, cats=("cs.PL",))
    assert S.argv_value(["--preset", "demo"], "--preset") == "demo"
    assert S.argv_value(["--preset=demo"], "--preset") == "demo"
    assert S.argv_value(["--no-open"], "--preset") is None
    assert S.apply_preset_arg(["--preset", "demo", "--preset-force"]) is True
    assert sandbox.config()["categories"] == ["cs.PL"]
