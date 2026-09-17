#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""截几张图，肉眼核对侧栏横线 / 回顶按钮 / Downvote 打灰的视觉呈现。

沙箱里 python 子进程启动的 Edge 绑不上调试端口，故支持 EDGE_ATTACH_PORT。
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
URL = "http://127.0.0.1:8765/"
ATTACH = int(os.environ.get("EDGE_ATTACH_PORT", "0") or 0)
PORT = ATTACH or 9225
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))


def http_json(path):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open("http://127.0.0.1:%d%s" % (PORT, path), timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    prof = tempfile.mkdtemp(prefix="edge-shot-")
    proc = None
    if not ATTACH:
        proc = subprocess.Popen([EDGE, "--headless=new", "--remote-debugging-port=%d" % PORT,
                                 "--user-data-dir=" + prof, "--no-first-run",
                                 "--no-default-browser-check", "--no-proxy-server",
                                 "about:blank"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        targets = None
        for _ in range(60):
            try:
                targets = http_json("/json/list")
                if targets:
                    break
            except Exception:
                time.sleep(0.5)
        page = [t for t in targets if t.get("type") == "page"][0]
        ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=60,
                                        suppress_origin=True)
        n = [0]

        def send(m, p=None):
            n[0] += 1
            ws.send(json.dumps({"id": n[0], "method": m, "params": p or {}}))
            while True:
                r = json.loads(ws.recv())
                if r.get("id") == n[0]:
                    if "error" in r:
                        raise RuntimeError(r["error"])
                    return r.get("result", {})

        def ev(e):
            r = send("Runtime.evaluate", {"expression": e, "returnByValue": True,
                                          "awaitPromise": True})
            if r.get("exceptionDetails"):
                raise RuntimeError(json.dumps(r["exceptionDetails"], ensure_ascii=False)[:600])
            return r["result"].get("value")

        send("Page.enable")
        send("Runtime.enable")
        send("Emulation.setDeviceMetricsOverride",
             {"width": 1440, "height": 980, "deviceScaleFactor": 1, "mobile": False})
        send("Page.navigate", {"url": URL})
        time.sleep(4)

        def shot(name):
            d = send("Page.captureScreenshot", {"format": "png"})
            p = os.path.join(OUT, name)
            with open(p, "wb") as f:
                f.write(base64.b64decode(d["data"]))
            print("saved", p)

        shot("ui_top.png")                        # 停在顶部：侧栏 + 推荐区

        # 滚到分类区，并让某个已 Downvote 的论文可见（临时标记后立即撤销）
        ev(r"""
        (() => {
          document.documentElement.classList.add('nosm');
          const s = document.querySelector('#rec-list .rec-card:not(.hidden)');
          const sid = s.dataset.sid;
          window.__sid = sid;
          document.querySelector('.btn.dv[data-act="dv"][data-sid="' + sid + '"]').click();
          const el = document.getElementById('cat-cs.LO');
          window.scrollTo(0, el.offsetTop + 40);
          return sid;
        })()
        """)
        time.sleep(2.5)
        shot("ui_cat.png")                        # 分类区：侧栏活动横线 + 回顶按钮 + 打灰

        # 撤销，恢复用户状态
        sid = ev("window.__sid")
        ev("fetch('/api/undownvote',{method:'POST',headers:{'Content-Type':'application/json'},"
           "body:JSON.stringify({id:'" + str(sid) + "'})}).then(r=>r.json())")
        print("reverted downvote for", sid)
    finally:
        try:
            if proc:
                proc.terminate()
        except Exception:
            pass
        time.sleep(0.5)
        shutil.rmtree(prof, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
