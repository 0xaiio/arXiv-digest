# -*- coding: utf-8 -*-
"""netroute 的探测与缓存决策（网络换成桩）。

选路逻辑值得单测，因为它的失败模式是「批量下载时反复探测」与「明明能下却报无路由」，
两者都只在特定缓存状态下出现。
"""
import time

import pytest

import netroute as NR

pytestmark = pytest.mark.unit


class FakeResp:
    def __init__(self, head):
        self.head = head

    def read(self, n=None):
        return self.head

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeOpener:
    def __init__(self, head=None, exc=None):
        self.head = head
        self.exc = exc

    def open(self, req, timeout=None):
        if self.exc:
            raise self.exc
        return FakeResp(self.head)


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setattr(NR, "listening_ports", lambda ttl=0: [])
    NR._cache.update({"proxy": "__unset__", "label": "", "ts": 0.0, "url": "",
                      "dead_ts": 0.0})
    monkeypatch.setattr(NR.time, "sleep", lambda *_: None)
    yield
    NR._cache.update({"proxy": "__unset__", "label": "", "ts": 0.0, "url": "",
                      "dead_ts": 0.0})


def test_probe_success_caches_route(sandbox, monkeypatch):
    monkeypatch.setattr(NR, "candidates", lambda prefer=None: [("http://p:1", "P1")])
    monkeypatch.setattr(NR, "build_opener", lambda proxy=None: FakeOpener(b"%PDF-1.4"))
    proxy, label = NR.probe()
    assert (proxy, label) == ("http://p:1", "P1")
    assert NR._from_cache()[0] == "http://p:1"


def test_probe_skips_non_pdf_response(sandbox, monkeypatch):
    monkeypatch.setattr(NR, "candidates", lambda prefer=None: [("http://p:1", "P1")])
    monkeypatch.setattr(NR, "build_opener", lambda proxy=None: FakeOpener(b"<html>oops"))
    proxy, label = NR.probe()
    assert (proxy, label) == (None, "")
    assert NR._cache["dead_ts"] > 0, "全失败要写负缓存，避免批量下载反复探测"


def test_probe_survives_connection_errors(sandbox, monkeypatch):
    monkeypatch.setattr(NR, "candidates", lambda prefer=None:
                        [("http://p:1", "P1"), (None, "直连")])

    def opener(proxy=None):
        if proxy:
            return FakeOpener(exc=OSError("Connection refused"))
        return FakeOpener(b"%PDF-1.7")

    monkeypatch.setattr(NR, "build_opener", opener)
    proxy, label = NR.probe()
    assert proxy is None and label == "直连", "第一条失败后应继续试下一条"


def test_negative_cache_short_circuits(sandbox, monkeypatch):
    NR._cache["dead_ts"] = time.time()
    called = []
    monkeypatch.setattr(NR, "probe", lambda **k: called.append(1) or (None, ""))
    assert NR.ensure_route() == (None, ""), "负缓存期间直接返回，不再探测"
    assert called == []


def test_fresh_positive_cache_is_reused(sandbox, monkeypatch):
    NR.note_ok("http://p:9", "缓存路由")
    called = []
    monkeypatch.setattr(NR, "probe", lambda **k: called.append(1) or (None, ""))
    assert NR.ensure_route() == ("http://p:9", "缓存路由")
    assert called == []


def test_force_ignores_cache(sandbox, monkeypatch):
    NR.note_ok("http://p:9", "缓存路由")
    monkeypatch.setattr(NR, "probe", lambda **k: ("http://p:2", "fresh"))
    assert NR.ensure_route(force=True) == ("http://p:2", "fresh")


def test_stale_cache_triggers_probe(sandbox, monkeypatch):
    import json

    # ensure_route 读的是**文件里的** ts，所以要改文件而不是内存
    (sandbox.out / "netroute.json").write_text(json.dumps({
        "proxy": "http://old:1", "label": "old", "url": "",
        "ts": time.time() - NR.CACHE_TTL - 1}), encoding="utf-8")
    monkeypatch.setattr(NR, "probe", lambda **k: ("http://new:1", "new"))
    assert NR.ensure_route()[0] == "http://new:1"


@pytest.mark.parametrize("head, total, expect", [
    (b"%PDF-1.4", None, True),
    (b"<html>", None, False),
    (b"{}", None, False),
    (b"partial", 1024, False),        # 短且不是 PDF
    (b"partial", 10 ** 6, False),     # 头部太短一律不当 PDF（宁可多下也别说没路由）
    (b"%PDF-1.5" + b"x" * 6000, 10 ** 6, True),
])
def test_looks_like_pdf(head, total, expect):
    assert NR._looks_like_pdf(head, total) is expect


def test_forget_clears_cache(sandbox):
    NR.note_ok("http://p:1", "x")
    NR.forget()
    assert NR._cache["proxy"] == "__unset__"
    assert NR._from_cache()[0] == "__unset__"


# ------------------------------------------------------------------ fetch_first（多 URL × 多路由）

@pytest.fixture()
def reset_failure():
    NR._last_fail.update({"summary": "", "detail": "", "ts": 0.0})
    yield
    NR._last_fail.update({"summary": "", "detail": "", "ts": 0.0})


def test_fetch_first_returns_pdf_via_first_route(sandbox, monkeypatch, reset_failure):
    monkeypatch.setattr(NR, "ensure_route", lambda force=False, log=False: (None, "直连"))
    monkeypatch.setattr(NR, "candidates", lambda prefer=None: [(None, "直连")])
    monkeypatch.setattr(NR, "build_opener", lambda proxy=None: FakeOpener(b"%PDF-1.4 body"))

    data, label, url = NR.fetch_first("https://arxiv.org/pdf/2609.10001")
    assert data.startswith(b"%PDF") and label == "直连"
    assert url.endswith("2609.10001")


def test_fetch_first_accepts_large_non_pdf_body(sandbox, monkeypatch, reset_failure):
    """有些镜像先返回 HTML 错误页；只要体量足够大就当作可用（避免误判无路由）。"""
    monkeypatch.setattr(NR, "ensure_route", lambda force=False, log=False: (None, "直连"))
    monkeypatch.setattr(NR, "candidates", lambda prefer=None: [(None, "直连")])
    monkeypatch.setattr(NR, "build_opener", lambda proxy=None: FakeOpener(b"x" * 6000))
    data, label, _ = NR.fetch_first("https://arxiv.org/pdf/x")
    assert len(data) == 6000


def test_fetch_first_falls_through_urls(sandbox, monkeypatch, reset_failure):
    """第一条 URL 返回 404 小页面 → 换第二条 URL 重试。"""
    calls = []

    def opener(proxy=None):
        calls.append(1)
        return FakeOpener(b"%PDF-1.4" if len(calls) > 1 else b"<html>404</html>")

    monkeypatch.setattr(NR, "ensure_route", lambda force=False, log=False: (None, "直连"))
    monkeypatch.setattr(NR, "candidates", lambda prefer=None: [(None, "直连")])
    monkeypatch.setattr(NR, "build_opener", opener)

    data, label, url = NR.fetch_first(["https://a/x", "https://b/x"])
    assert data.startswith(b"%PDF") and url == "https://b/x"


def test_fetch_first_raises_route_error_and_records_failure(sandbox, monkeypatch,
                                                            reset_failure):
    monkeypatch.setattr(NR, "ensure_route", lambda force=False, log=False: (None, "直连"))
    monkeypatch.setattr(NR, "candidates", lambda prefer=None: [(None, "直连")])
    monkeypatch.setattr(NR, "build_opener",
                        lambda proxy=None: FakeOpener(exc=OSError("Connection reset 10054")))

    with pytest.raises(NR.RouteError) as ei:
        NR.fetch_first("https://arxiv.org/pdf/2609.10001")
    assert "连接被重置" in str(ei.value)
    fail = NR.last_failure()
    assert fail["summary"] and fail["detail"]


def test_fetch_first_respects_negative_cache(sandbox, monkeypatch, reset_failure):
    NR._cache["dead_ts"] = time.time()
    NR._last_fail["summary"] = "全部失败"
    monkeypatch.setattr(NR, "ensure_route",
                        lambda **k: pytest.fail("负缓存期间不应再探测"))

    with pytest.raises(NR.RouteError):
        NR.fetch_first("https://arxiv.org/pdf/x")


def test_candidates_includes_listening_proxy_port(sandbox, monkeypatch):
    monkeypatch.setattr(NR, "listening_ports", lambda ttl=0: [7890])
    monkeypatch.setattr(NR, "_alive", lambda p, timeout=0.25: True)
    cands = NR.candidates()
    assert ("http://127.0.0.1:7890", "本机代理 :7890") in cands


def test_candidates_includes_other_listening_ports(sandbox, monkeypatch):
    monkeypatch.setattr(NR, "listening_ports", lambda ttl=0: [54321])
    monkeypatch.setattr(NR, "_alive", lambda p, timeout=0.25: True)
    labels = [l for _, l in NR.candidates()]
    assert any("本机端口 :54321" == l for l in labels)


def test_cli_quick_lists_candidates(sandbox, monkeypatch, capsys):
    monkeypatch.setattr(NR, "candidates", lambda prefer=None: [(None, "直连")])
    monkeypatch.setattr(NR.sys, "argv", ["netroute.py", "--quick"])
    assert NR.main() == 0
    out = capsys.readouterr().out
    assert "候选路由" in out and "直连" in out
