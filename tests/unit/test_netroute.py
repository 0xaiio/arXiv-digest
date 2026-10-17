# -*- coding: utf-8 -*-
"""netroute：候选顺序、错误文案、缓存读写。

不测真实探测（需要外网）：`candidates()` 里的端口扫描被桩掉，
`ensure_route()` 的网络探测留给 e2e/人工，避免 CI 抖动。
"""
import json

import pytest

import netroute as NR

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def no_port_scan(monkeypatch):
    """端口扫描会真的去 connect 本机端口，测试里固定为空。"""
    monkeypatch.setattr(NR, "listening_ports", lambda ttl=0: [])
    monkeypatch.setenv("ARXIV_DL_PROXY", "")
    monkeypatch.setenv("HTTPS_PROXY", "")
    monkeypatch.setenv("https_proxy", "")
    monkeypatch.setenv("HTTP_PROXY", "")
    monkeypatch.setenv("http_proxy", "")


def test_direct_route_is_the_default_first_candidate():
    cands = NR.candidates()
    assert cands[0] == (None, "直连")


def test_arxiv_dl_proxy_goes_first(monkeypatch):
    monkeypatch.setenv("ARXIV_DL_PROXY", "127.0.0.1:7890")
    cands = NR.candidates()
    proxy, label = cands[0]
    assert label == "ARXIV_DL_PROXY"
    assert proxy == "http://127.0.0.1:7890", "缺 scheme 时自动补 http://"


def test_env_proxy_is_listed_after_direct(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:8080")
    cands = NR.candidates()
    labels = [l for _, l in cands]
    assert labels[0] == "直连"
    assert any(l.startswith("环境代理") for l in labels)
    assert len(cands) == 2, "同一代理不应重复出现"


def test_candidates_dedupes_prefer():
    cands = NR.candidates(prefer="http://127.0.0.1:7890")
    proxies = [p for p, _ in cands]
    assert cands[0][1].startswith("缓存")
    assert proxies.count("http://127.0.0.1:7890") == 1


@pytest.mark.parametrize("err, hint", [
    ("SSL: UNEXPECTED_EOF_WHILE_READING", "代理掐断 TLS"),
    ("[WinError 10054] ...", "连接被重置"),
    ("[WinError 10061] ...", "端口未监听"),
    ("getaddrinfo failed", "域名解析失败"),
    ("Connection refused", "连接被拒绝"),
])
def test_friendly_maps_known_network_errors(err, hint):
    assert hint in NR.friendly(Exception(err))


def test_friendly_truncates_unknown_error():
    out = NR.friendly(Exception("x" * 200))
    assert len(out) <= 60


def test_friendly_handles_empty_error():
    assert NR.friendly(Exception("")) == "未知错误"


def test_cache_roundtrip(sandbox):
    NR._to_cache("http://127.0.0.1:7890", "本机代理 :7890", "http://127.0.0.1:7890")
    proxy, label, ts = NR._from_cache()
    assert proxy == "http://127.0.0.1:7890"
    assert label.startswith("本机代理")
    assert ts > 0


def test_cache_of_direct_route_is_representable(sandbox):
    """直连的 proxy 是 None —— 缓存必须能区分「直连」与「没缓存」。"""
    NR._to_cache(None, "直连", "")
    proxy, label, _ = NR._from_cache()
    assert proxy is None and label == "直连"


def test_cache_unset_marker(sandbox):
    assert NR._from_cache()[0] == "__unset__"


def test_corrupt_cache_is_ignored(sandbox):
    (sandbox.out / "netroute.json").write_text("{oops", encoding="utf-8")
    assert NR._from_cache()[0] == "__unset__"


def test_last_failure_recorded_in_cache(sandbox):
    NR.note_ok("http://127.0.0.1:7890", "本机代理")
    data = json.loads((sandbox.out / "netroute.json").read_text(encoding="utf-8"))
    assert data["proxy"] == "http://127.0.0.1:7890"
