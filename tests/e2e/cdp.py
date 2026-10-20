# -*- coding: utf-8 -*-
"""浏览器端到端测试的公共底座：Edge + CDP（不依赖 Selenium）。

抽成独立模块的理由：分类选择器与首页交互两套 UI 用例都要用同一套「导航 /
执行 JS / 点击」的机械动作，复制一份必然漂移（尤其 ``goto`` 里那段
「等新文档」的判断，踩过一次就会再踩一次）。

用法：
    from cdp import Browser, click  # noqa: F401  （fixture 也要 import 进来才会被发现）
"""
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request

import pytest

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/microsoft-edge",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def edge_path():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    return shutil.which("microsoft-edge") or shutil.which("msedge")


@pytest.fixture(scope="module")
def edge_exe():
    """找不到 Edge / 缺 websocket-client / 显式 SKIP_UI_E2E=1 时跳过整层。"""
    if os.environ.get("SKIP_UI_E2E") == "1":
        pytest.skip("SKIP_UI_E2E=1")
    exe = edge_path()
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
        """导航并等到「新文档已加载完、内联脚本已执行」。

        只等 ``document.readyState == 'complete'`` 会踩坑：``Page.navigate`` 之后
        有一小段时间 ``location.href`` 已经变成目标地址，但 ``document`` 仍是上一份
        （about:blank 也已经是 complete）。此时返回，后续断言就在**旧文档**上执行 ——
        表现是「卡片能找到、点按钮却毫无反应」（事件委托还没绑定）。

        判别新文档的办法：先在旧文档上打一个标记，新文档里它必然不存在。
        """
        want = url.rstrip("/")
        try:
            self.evaluate("window.__wbStaleDoc = 1")
        except Exception:
            pass
        self.send("Page.navigate", {"url": url})
        for _ in range(120):
            time.sleep(0.15)
            try:
                if self.evaluate("typeof window.__wbStaleDoc !== 'undefined'"):
                    continue          # 还是旧文档
                if (self.evaluate("location.href") or "").rstrip("/") != want:
                    continue
                if self.evaluate("document.readyState") != "complete":
                    continue
                return
            except Exception:
                continue
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
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    b = Browser(edge_exe, str(sandbox.root / "edge-profile"), port)
    try:
        yield b
    finally:
        b.close()


def click(browser, sel, act):
    """在页面上点一次某个操作按钮。

    这里用 ``dispatchEvent`` 而不是 ``element.click()``：headless Edge 下，
    对「卡片池里被 data-limit 隐藏、或刚被 DocumentFragment 重排过」的按钮
    调用 ``.click()`` 有时不会把事件冒泡到 document，委托监听器就收不到
    （表现为「点了没反应」，但直接调内部函数一切正常）。``dispatchEvent``
    走的是同一条冒泡与委托路径，且稳定复现用户点击的语义。
    """
    browser.evaluate(
        "(()=>{var b=document.querySelector(\"%s button[data-act='%s']\");"
        "b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));})()"
        % (sel, act))


def js_click(browser, sel):
    """对任意元素派发一次冒泡的点击（用于非按钮元素，如标签、下拉选项）。"""
    browser.evaluate(
        "(()=>{var e=document.querySelector(%s);if(!e)throw new Error('not found');"
        "e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));})()"
        % json.dumps(sel))
