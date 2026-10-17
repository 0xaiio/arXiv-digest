# -*- coding: utf-8 -*-
"""集成：run_daily 的编排逻辑。

不真的抓取、不起服务：把 `run()` / `ensure_server()` 换成记录器，验证
「调用顺序、开关语义、失败降级」这三件最容易在重构中走样的事。
"""
import json
import sys

import pytest

import run_daily as RD

pytestmark = pytest.mark.integration


@pytest.fixture()
def recorder(monkeypatch, sandbox):
    """替换子进程封装；可选择让某一步失败，模拟 arXiv 限流。"""
    state = {"calls": [], "fail": set(), "write_raw": True}

    def fake_run(script, capture=None, keep_previous=False):
        state["calls"].append(script)
        if capture and state["write_raw"] and script not in state["fail"]:
            papers = [{"id": "http://arxiv.org/abs/2609.10001v1", "title": "T"}]
            sandbox.write(capture, {"papers": papers, "generated_at": "2026-10-15T08:00:00+08:00",
                                    "newest_seen": "2026-10-15"})
        return script not in state["fail"]

    monkeypatch.setattr(RD, "run", fake_run)
    monkeypatch.setattr(RD, "ensure_server",
                        lambda port=None, wait=15.0: ("http://127.0.0.1:8765", False))
    return state


def _args(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["run_daily.py", *argv])


def test_full_pipeline_order(sandbox, recorder, monkeypatch):
    _args(monkeypatch)
    RD.main()
    assert recorder["calls"] == ["fetch_arxiv.py", "fetch_expand.py", "recommend.py",
                                "fetch_affil.py", "build_report.py"]


def test_skip_fetch_reuses_existing_pool(sandbox, recorder, monkeypatch):
    sandbox.write("raw.json", {"papers": [{"id": "http://arxiv.org/abs/2609.10001v1"}]})
    _args(monkeypatch, "--skip-fetch")
    RD.main()
    assert "fetch_arxiv.py" not in recorder["calls"]
    assert "fetch_expand.py" not in recorder["calls"]
    assert recorder["calls"][0] == "recommend.py"


def test_skip_affil(sandbox, recorder, monkeypatch):
    _args(monkeypatch, "--skip-affil")
    RD.main()
    assert "fetch_affil.py" not in recorder["calls"]


def test_no_serve_does_not_touch_server(sandbox, recorder, monkeypatch):
    called = []
    monkeypatch.setattr(RD, "ensure_server",
                        lambda *a, **k: (called.append(1), ("u", False))[1])
    _args(monkeypatch, "--no-serve")
    RD.main()
    assert called == []


def test_serve_runs_server_in_foreground(sandbox, recorder, monkeypatch):
    _args(monkeypatch, "--serve")
    RD.main()
    assert recorder["calls"][-1] == "server.py"


def test_partial_fetch_failure_triggers_rss_fallback(sandbox, recorder, monkeypatch):
    recorder["fail"] = {"fetch_expand.py"}
    _args(monkeypatch)
    RD.main()
    assert "fetch_rss.py" in recorder["calls"], "只要有一路失败就必须走 RSS 增量"


def test_no_data_skips_recommend_and_render(sandbox, recorder, monkeypatch):
    recorder["write_raw"] = False          # 抓取全失败且无历史数据
    recorder["fail"] = {"fetch_arxiv.py", "fetch_expand.py"}
    _args(monkeypatch)
    RD.main()
    assert "recommend.py" not in recorder["calls"]
    assert "build_report.py" not in recorder["calls"]


def test_no_data_still_keeps_server_online(sandbox, recorder, monkeypatch):
    recorder["write_raw"] = False
    recorder["fail"] = {"fetch_arxiv.py", "fetch_expand.py"}
    called = []
    monkeypatch.setattr(RD, "ensure_server",
                        lambda *a, **k: (called.append(1), ("u", False))[1])
    _args(monkeypatch)
    RD.main()
    assert called == [1], "没有新内容时仍应保证页面可访问"


def test_ensure_server_reuses_online_instance(monkeypatch):
    monkeypatch.setattr(RD, "server_alive", lambda port, timeout=2.0: True)
    url, started = RD.ensure_server(port=8765)
    assert url.endswith(":8765") and started is False


def test_payload_validation():
    assert RD._payload_ok(json.dumps({"papers": [{"id": "x"}]}))
    assert not RD._payload_ok(json.dumps({"error": "no data"}))
    assert not RD._payload_ok(json.dumps({"papers": []}))
    assert not RD._payload_ok("not json")
    assert not RD._payload_ok('["list"]')
