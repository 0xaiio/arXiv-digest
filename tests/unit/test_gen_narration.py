# -*- coding: utf-8 -*-
"""gen_narration：TTS 出网路由的选择与故障切换。

背景（2026-10-22 实测）
------------------------
Edge TTS 端点 `speech.platform.bing.com:443` 在本机**直连被拦、经本机代理才通**，
失败表现是 `ClientConnectorError: Cannot connect to host ...`。原实现只做「同一路由重试
3 次」，于是 12 段合成在第 3 段整轮崩掉 —— 而同一时刻单跑一次合成是成功的，
说明是**路由**问题，不是服务或稿件问题。

所以这里要守住三条：
1. 走不通就**换路由**，别在同一路由上空转；
2. NoAudioReceived 这类服务端抽风才值得**原地重试**；
3. 成功过的路由要**记住**，后面 11 段不必再等直连的 connect 超时。
"""
import asyncio
import json
import os

import pytest

import tools.gen_narration as GN

pytestmark = pytest.mark.unit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REAL_RUN = asyncio.run


class _AioShim:
    """把 asyncio 的两处调用换成同步执行，测试里无需真跑事件循环的计时逻辑。"""

    TimeoutError = asyncio.TimeoutError

    @staticmethod
    def wait_for(coro, timeout=None):
        return coro

    @staticmethod
    def run(coro):
        return _REAL_RUN(coro)


@pytest.fixture()
def reset_route():
    """每个用例从「未解析」开始，避免上一个用例记下的路由泄漏进来。"""
    GN._ROUTE.update(proxy="__unset__", label="")
    yield
    GN._ROUTE.update(proxy="__unset__", label="")


class _ConnError(Exception):
    """模拟 aiohttp.ClientConnectorError（按类名判断，不依赖 aiohttp 装没装）。"""


_ConnError.__name__ = "ClientConnectorError"


def _workdir(tag):
    """项目内一次目录（不用 tmp_path：pytest.ini 禁了 tmpdir，删除会被沙箱拦）。"""
    d = os.path.join(ROOT, "tmp_pytest", "narration-%s-%d" % (tag, os.getpid()))
    os.makedirs(d, exist_ok=True)
    return d


def test_explicit_proxy_wins(reset_route):
    assert GN.tts_proxy_candidates("http://127.0.0.1:7890") == [
        ("http://127.0.0.1:7890", "指定 http://127.0.0.1:7890")
    ]


def test_candidates_start_direct_then_proxy(monkeypatch, reset_route):
    """未解析时应先试直连，再试代理；顺序来自 netroute，不在这里另造一套。"""
    import netroute

    monkeypatch.setattr(
        netroute, "candidates",
        lambda prefer=None: [(None, "直连"), ("http://127.0.0.1:7890", "本机代理 :7890")],
    )
    cands = GN.tts_proxy_candidates()
    assert cands[0][0] is None
    assert cands[1][0] == "http://127.0.0.1:7890"


def test_remembered_route_is_preferred(monkeypatch, reset_route):
    """上次成功的路由要作为 prefer 传给 netroute，让它排在最前面。"""
    import netroute

    seen = {}

    def fake_candidates(prefer=None):
        seen["prefer"] = prefer
        return [("http://127.0.0.1:7890", "本机代理 :7890")]

    monkeypatch.setattr(netroute, "candidates", fake_candidates)
    GN._ROUTE.update(proxy="http://127.0.0.1:7890", label="本机代理 :7890")
    GN.tts_proxy_candidates()
    assert seen["prefer"] == "http://127.0.0.1:7890"


def test_conn_error_switches_route(monkeypatch, reset_route):
    """建连失败 → 立刻换下一条路由，成为后续段落的首选。"""
    calls = []

    async def fake_synth(text, voice, rate, path, proxy=None):
        calls.append(proxy)
        if proxy is None:
            raise _ConnError("Cannot connect to host speech.platform.bing.com:443")

    monkeypatch.setattr(GN, "synth", fake_synth)
    monkeypatch.setattr(GN, "asyncio", _AioShim)
    monkeypatch.setattr(GN, "_sleep", lambda s: None)
    monkeypatch.setattr(GN, "tts_proxy_candidates",
                        lambda proxy=None: [(None, "直连"), ("http://127.0.0.1:7890", "本机代理")])

    GN.run_synth("测试", GN.DEFAULT_VOICE, "+0%", "x.mp3")

    # 同一条路由连续两次建连失败才换（可用代理也会偶发抽风）
    assert calls == [None, None, "http://127.0.0.1:7890"]
    assert GN._ROUTE["proxy"] == "http://127.0.0.1:7890"


def test_server_hiccup_retries_same_route(monkeypatch, reset_route):
    """NoAudioReceived 属于服务端抽风：同一路由内重试，不换路。"""
    calls = []

    async def fake_synth(text, voice, rate, path, proxy=None):
        calls.append(proxy)
        if len(calls) == 1:
            raise RuntimeError("NoAudioReceived: No audio was received.")

    monkeypatch.setattr(GN, "synth", fake_synth)
    monkeypatch.setattr(GN, "asyncio", _AioShim)
    monkeypatch.setattr(GN, "_sleep", lambda s: None)
    monkeypatch.setattr(GN, "tts_proxy_candidates",
                        lambda proxy=None: [(None, "直连"), ("http://127.0.0.1:7890", "本机代理")])

    GN.run_synth("测试", GN.DEFAULT_VOICE, "+0%", "x.mp3")
    assert calls == [None, None]


def test_single_route_error_still_retries_same_route(monkeypatch, reset_route):
    """一次建连失败不该立刻丢路由：实测可用代理约 1/3 请求会瞬时失败。"""
    calls = []

    async def flaky(text, voice, rate, path, proxy=None):
        calls.append(proxy)
        if len(calls) == 1:
            raise _ConnError("Cannot connect to host speech.platform.bing.com:443")

    monkeypatch.setattr(GN, "synth", flaky)
    monkeypatch.setattr(GN, "asyncio", _AioShim)
    monkeypatch.setattr(GN, "_sleep", lambda s: None)
    monkeypatch.setattr(GN, "tts_proxy_candidates",
                        lambda proxy=None: [(None, "直连"), ("http://127.0.0.1:7890", "本机代理")])

    GN.run_synth("测试", GN.DEFAULT_VOICE, "+0%", "x.mp3")
    assert calls == [None, None]        # 第二次仍在直连上成功，没有换路


def test_all_routes_failed_raises_last(monkeypatch, reset_route):
    async def always_fail(text, voice, rate, path, proxy=None):
        raise _ConnError("Cannot connect to host speech.platform.bing.com:443")

    monkeypatch.setattr(GN, "synth", always_fail)
    monkeypatch.setattr(GN, "asyncio", _AioShim)
    monkeypatch.setattr(GN, "_sleep", lambda s: None)
    monkeypatch.setattr(GN, "tts_proxy_candidates",
                        lambda proxy=None: [(None, "直连"), ("http://127.0.0.1:7890", "本机代理")])

    with pytest.raises(Exception) as ei:
        GN.run_synth("测试", GN.DEFAULT_VOICE, "+0%", "x.mp3")
    assert "Cannot connect" in str(ei.value)


def test_segment_failure_keeps_going_and_disables_manifest(monkeypatch, reset_route):
    """单段失败不能让整轮 traceback 掉线：要写 audio.json（enabled=false）并返回 1。"""
    d = _workdir("fail")
    papers = {"papers": [{"sid": "2610.00001", "title_en": "T", "rank": 1, "lane": "推荐"}]}
    notes = {"_intro": {"narration": "片头"}, "_outro": {"narration": "片尾"}}
    pfile = os.path.join(d, "papers.json")
    nfile = os.path.join(d, "notes.json")
    with open(pfile, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False)
    with open(nfile, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False)
    out_json = os.path.join(d, "audio.json")

    def boom(*a, **kw):
        raise RuntimeError("Edge TTS 全线不可用")

    monkeypatch.setattr(GN, "synthesize", boom)
    monkeypatch.setattr(GN, "ffmpeg_exe", lambda: None)

    rc = GN.main(["--papers", pfile, "--notes", nfile,
                  "--outdir", os.path.join(d, "audio"), "--audio-json", out_json])
    assert rc == 1
    with open(out_json, encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["enabled"] is False


def test_failed_segment_gets_second_round(monkeypatch, reset_route):
    """第一轮失败的段要在第二轮补跑，补上就整体成功（enabled=true）。"""
    d = _workdir("twopass")
    papers = {"papers": [{"sid": "2610.00001", "title_en": "T", "rank": 1, "lane": "推荐"}]}
    notes = {"_intro": {"narration": "片头"}, "_outro": {"narration": "片尾"}}
    pfile = os.path.join(d, "papers.json")
    nfile = os.path.join(d, "notes.json")
    with open(pfile, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False)
    with open(nfile, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False)
    out_json = os.path.join(d, "audio.json")

    seen = {"intro": 0}

    def fake_synth(text, voice, budget, target, path, ff, no_tts=False, proxy=None):
        if text == "片头":
            seen["intro"] += 1
            if seen["intro"] == 1:
                raise RuntimeError("Cannot connect to host speech.platform.bing.com:443")
        return (3.9, "+0%", 0.0)

    monkeypatch.setattr(GN, "synthesize", fake_synth)
    monkeypatch.setattr(GN, "ffmpeg_exe", lambda: None)
    monkeypatch.setattr(GN, "mean_volume", lambda p, f: -18.0)

    rc = GN.main(["--papers", pfile, "--notes", nfile,
                  "--outdir", os.path.join(d, "audio"), "--audio-json", out_json])
    assert rc == 0
    assert seen["intro"] == 2
    with open(out_json, encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["enabled"] is True
    assert set(manifest["segments"]) == {"intro", "paper1", "outro"}
