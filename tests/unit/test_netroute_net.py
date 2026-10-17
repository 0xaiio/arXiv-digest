# -*- coding: utf-8 -*-
"""netroute 的底层原语：opener 构造、请求头、端口探测。

不访问外网：只验证「构造是否正确」与「本机端口枚举能跑通」。
"""
import socket
import urllib.request

import pytest

import netroute as NR

pytestmark = pytest.mark.unit


def test_ssl_context_is_permissive_for_arxiv_mirrors():
    ctx = NR.ssl_context()
    assert ctx.check_hostname is False
    assert ctx.verify_mode.name == "CERT_NONE"


def test_user_agent_identifies_project():
    ua = NR.user_agent()
    assert isinstance(ua, dict) and "User-Agent" in ua
    assert "arxiv-digest" in ua["User-Agent"]


def test_build_opener_without_proxy():
    assert isinstance(NR.build_opener(None), urllib.request.OpenerDirector)


def test_build_opener_with_proxy():
    op = NR.build_opener("http://127.0.0.1:7890")
    assert isinstance(op, urllib.request.OpenerDirector)


def test_make_request_sets_headers():
    req = NR.make_request("https://arxiv.org/pdf/2609.10001")
    assert req.get_header("User-agent") == NR.user_agent()["User-Agent"]
    assert req.full_url.startswith("https://arxiv.org/")


def test_make_request_accepts_extra_headers():
    req = NR.make_request("https://example.org", headers={"X-Test": "1"})
    assert req.get_header("X-test") == "1"


def test_listening_ports_finds_a_bound_socket():
    """本机枚举：绑一个端口，应该能被发现。"""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        NR._listen_cache["ts"] = 0.0
        assert port in NR.listening_ports(ttl=0)
    finally:
        srv.close()
        NR._listen_cache["ts"] = 0.0


def test_listening_ports_are_cached():
    NR._listen_cache.update({"ts": 0.0, "ports": []})
    first = NR.listening_ports(ttl=30)
    second = NR.listening_ports(ttl=30)
    assert second == first, "TTL 内应复用缓存（避免每次下载都扫端口）"


def test_alive_detects_closed_port():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.close()
    assert NR._alive(port) is False


def test_pdf_urls_prefers_recorded_link():
    urls = NR.pdf_urls("2609.10001", "https://arxiv.org/pdf/2609.10001v2")
    assert urls[0] == "https://arxiv.org/pdf/2609.10001v2"
    assert any("2609.10001" in u for u in urls)


def test_pdf_urls_falls_back_to_abs():
    urls = NR.pdf_urls("2609.10001", "")
    assert any("arxiv.org/pdf/2609.10001" in u for u in urls)
