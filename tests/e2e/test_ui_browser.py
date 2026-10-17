# -*- coding: utf-8 -*-
"""端到端（浏览器）：真实点击，验证「用户看到的」而不是「接口返回的」。

这一层补的是前两层看不到的东西：内联 JS 是否执行、CSS 是否真的生效、
点击后的乐观更新是否即时。默认执行；以下情况自动跳过：

  * 没有 Edge（非 Windows 或未安装）；
  * 没有 websocket-client；
  * 设置了 SKIP_UI_E2E=1（例如 CI 环境）。

实现方式：`msedge --headless=new --remote-debugging-port` + CDP，不依赖 Selenium。
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.ui]

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/microsoft-edge",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def _edge():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    return shutil.which("microsoft-edge") or shutil.which("msedge")


@pytest.fixture(scope="module")
def edge_exe():
    if os.environ.get("SKIP_UI_E2E") == "1":
        pytest.skip("SKIP_UI_E2E=1")
    exe = _edge()
    if not exe:
        pytest.skip("未找到 Edge，跳过浏览器端到端测试")
    pytest.importorskip("websocket", reason="缺少 websocket-client")
    return exe


class Browser:
    """极简 CDP 客户端：导航 + evaluate。"""

    def __init__(self, exe, profile_dir, port):
        self.proc = subprocess.Popen(
            [exe, "--headless=new", "--remote-debugging-port=%d" % port,
             "--user-data-dir=%s" % profile_dir, "--no-first-run",
             "--no-default-browser-check", "--no-proxy-server", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.port = port
        self.ws = None
        self.n = 0
        self._connect()

    def _http(self, path):
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open("http://127.0.0.1:%d%s" % (self.port, path), timeout=5) as r:
            return json.loads(r.read().decode())

    def _connect(self):
        import websocket

        targets = []
        for _ in range(80):
            try:
                targets = [t for t in self._http("/json/list") if t.get("type") == "page"]
                if targets:
                    break
            except Exception:
                pass
            time.sleep(0.25)
        if not targets:
            raise RuntimeError("Edge 调试端口未就绪")
        self.ws = websocket.create_connection(targets[0]["webSocketDebuggerUrl"],
                                              timeout=30, suppress_origin=True)
        self.send("Page.enable")
        self.send("Runtime.enable")
        # 在文档创建前注入错误收集器：内联脚本被模板转义破坏时不会抛到 CDP，只会静默失败
        self.send("Page.addScriptToEvaluateOnNewDocument", {
            "source": "window.__jsErrors=[];"
                      "window.addEventListener('error',function(e){"
                      "window.__jsErrors.push(String(e.message||e.type));});"})

    def send(self, method, params=None):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                return msg.get("result", {})

    def evaluate(self, expr):
        r = self.send("Runtime.evaluate",
                      {"expression": expr, "returnByValue": True, "awaitPromise": True})
        if r.get("exceptionDetails"):
            raise AssertionError("页面 JS 抛异常：%s"
                                 % (r["exceptionDetails"].get("exception") or {}))
        return r["result"].get("value")

    def goto(self, url):
        self.send("Page.navigate", {"url": url})
        for _ in range(80):
            time.sleep(0.2)
            if self.evaluate("document.readyState") == "complete":
                return
        raise AssertionError("页面加载超时：%s" % url)

    def close(self):
        try:
            if self.ws:
                self.ws.close()
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()


@pytest.fixture()
def browser(edge_exe, sandbox):
    # 动态取空闲端口：固定端口在连续跑多个 UI 用例时会与上一个 Edge 实例撞车
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    b = Browser(edge_exe, str(sandbox.root / "edge-profile"), port)
    try:
        yield b
    finally:
        b.close()


def test_downvote_click_changes_visual_state(seeded, http, browser, monkeypatch):
    """点一次 Downvote：卡片变灰 + 标题删除线 + 按钮文字变化；再点恢复。"""
    import build_report as B
    import recommend as R

    R.main()
    B.main()

    browser.goto(http.base + "/")
    assert browser.evaluate("document.querySelectorAll('.rec-card').length") >= 1

    sid = browser.evaluate("document.querySelector('.rec-card').dataset.sid")
    sel = "[data-sid='%s']" % sid

    def style(expr):
        return browser.evaluate(
            "(()=>{var e=document.querySelector(\"%s\");%s})()" % (sel, expr))

    browser.evaluate("document.querySelector(\"%s button[data-act='dv']\").click()" % sel)
    time.sleep(0.6)

    assert style("return !!e.classList.contains('down')") is True
    assert style("return getComputedStyle(e).opacity") == "0.42"
    assert "line-through" in style(
        "return getComputedStyle(e.querySelector('.rec-t')).textDecorationLine")
    assert style("return e.querySelector('button[data-act=\"dv\"] .lb').textContent") == "已 Downvote"

    # 撤销
    browser.evaluate("document.querySelector(\"%s button[data-act='dv']\").click()" % sel)
    time.sleep(0.6)
    assert style("return !!e.classList.contains('down')") is False
    assert float(style("return getComputedStyle(e).opacity")) > 0.9


def test_no_javascript_errors_on_load(seeded, http, browser):
    """首屏不应有 JS 异常（内联脚本被模板转义破坏时会静默失败）。"""
    import build_report as B
    import recommend as R

    R.main()
    B.main()

    browser.goto(http.base + "/")
    errors = browser.evaluate(
        "(()=>{try{return window.__jsErrors||[]}catch(e){return []}})()")
    assert errors == []


def test_favorite_button_roundtrip_in_browser(seeded, http, browser):
    """点收藏 → 按钮变「已收藏」；再点 → 取消。"""
    import build_report as B
    import recommend as R

    R.main()
    B.main()
    browser.goto(http.base + "/")

    sel = "[data-sid='2609.10001']"
    browser.evaluate("document.querySelector(\"%s button[data-act='fav']\").click()" % sel)
    time.sleep(0.6)
    assert browser.evaluate(
        "document.querySelector(\"%s button[data-act='fav']\").classList.contains('on')" % sel)
    label = browser.evaluate(
        "document.querySelector(\"%s button[data-act='fav'] .lb\").textContent" % sel)
    assert "已收藏" in label

    browser.evaluate("document.querySelector(\"%s button[data-act='fav']\").click()" % sel)
    time.sleep(0.6)
    assert not browser.evaluate(
        "document.querySelector(\"%s button[data-act='fav']\").classList.contains('on')" % sel)
