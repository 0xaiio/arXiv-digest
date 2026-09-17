#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""终检：两个页面是否有 JS 报错 / 关键元素是否就位。

沙箱里 python 子进程启动的 Edge 绑不上调试端口，故支持 EDGE_ATTACH_PORT：
外部（如 PowerShell）先起好 Edge，这里只做附加。
"""
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
ATTACH = int(os.environ.get("EDGE_ATTACH_PORT", "0") or 0)
PORT = ATTACH or 9226


def http_json(path):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open("http://127.0.0.1:%d%s" % (PORT, path), timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    prof = tempfile.mkdtemp(prefix="edge-fin-")
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
        logs = []

        def send(m, p=None):
            n[0] += 1
            ws.send(json.dumps({"id": n[0], "method": m, "params": p or {}}))
            while True:
                r = json.loads(ws.recv())
                if r.get("id") == n[0]:
                    if "error" in r:
                        raise RuntimeError(r["error"])
                    return r.get("result", {})
                if r.get("method") in ("Runtime.consoleAPICalled", "Runtime.exceptionThrown",
                                       "Log.entryAdded"):
                    logs.append(r)

        def ev(e, awaitp=True):
            r = send("Runtime.evaluate", {"expression": e, "returnByValue": True,
                                          "awaitPromise": awaitp})
            if r.get("exceptionDetails"):
                return {"__exception": json.dumps(r["exceptionDetails"], ensure_ascii=False)[:400]}
            return r["result"].get("value")

        send("Page.enable")
        send("Runtime.enable")
        send("Log.enable")
        send("Emulation.setDeviceMetricsOverride",
             {"width": 1440, "height": 980, "deviceScaleFactor": 1, "mobile": False})

        for path in ("/", "/favorites"):
            logs.clear()
            send("Page.navigate", {"url": "http://127.0.0.1:8765" + path})
            for _ in range(40):
                time.sleep(0.4)
                st = ev("document.readyState + '|' + location.pathname", awaitp=False)
                if st == "complete|" + path:
                    break
            time.sleep(1.5)
            errs = []
            for l in logs:
                if l["method"] == "Runtime.exceptionThrown":
                    errs.append(l["params"]["exceptionDetails"].get("text"))
                elif l["method"] == "Log.entryAdded":
                    e = l["params"]["entry"]
                    if e.get("level") in ("error", "warning"):
                        errs.append("%s: %s" % (e.get("level"), e.get("text")))
                elif l["method"] == "Runtime.consoleAPICalled" and l["params"]["type"] == "error":
                    errs.append("console.error: " + json.dumps(
                        [a.get("value") for a in l["params"]["args"]], ensure_ascii=False))
            info = ev(r"""
            ({
              title: document.title,
              rail: document.querySelectorAll('#rail .navi').length,
              totop: !!document.getElementById('totop'),
              cards: document.querySelectorAll('.rec-card').length,
              items: document.querySelectorAll('li.item').length,
              favBtn: !!document.querySelector('.btn.fav'),
              apiBase: typeof APIBASE === 'string' ? APIBASE : 'undefined',
              railActive: !!document.querySelector('#rail .navi.on') || null,
              railVisible: document.getElementById('rail')
                ? getComputedStyle(document.getElementById('rail')).display : 'absent',
            })
            """)
            print(path, "->", json.dumps(info, ensure_ascii=False))
            print("   errors:", errs if errs else "none")

        # Downvote 计算样式扫描：三类容器是否都真的「划线 + 半透明」
        send("Page.navigate", {"url": "http://127.0.0.1:8765/"})
        for _ in range(40):
            time.sleep(0.4)
            if ev("document.readyState", awaitp=False) == "complete":
                break
        time.sleep(2.5)
        dv = ev(r"""
        (() => {
          // opacity 不继承：必须量「容器自身」的半透明，标题只量 text-decoration
          const probe = (el, sel) => {
            const t = sel ? el.querySelector(sel) : el;
            const deco = t ? getComputedStyle(t).textDecorationLine : null;
            return {opacity: getComputedStyle(el).opacity, deco: deco};
          };
          const rows = [];
          document.querySelectorAll('.rec-card.down').forEach(e => rows.push(
            {kind: 'card', sid: e.dataset.sid, ...probe(e, '.rec-t')}));
          document.querySelectorAll('.plist li.item.down').forEach(e => rows.push(
            {kind: 'item', sid: e.dataset.sid, ...probe(e, '.r-t a')}));
          document.querySelectorAll('.hl.down').forEach(e => rows.push(
            {kind: 'hl', sid: e.dataset.sid, ...probe(e, '.hl-t a')}));
          const bad = rows.filter(r => r.deco !== 'line-through' || parseFloat(r.opacity) >= 0.9);
          return {total: rows.length, kinds: [...new Set(rows.map(r => r.kind))],
                  opacities: [...new Set(rows.map(r => r.opacity))],
                  bad: bad, sample: rows.slice(0, 4)};
        })()
        """)
        print("downvote-style ->", json.dumps(dv, ensure_ascii=False))

        # 收藏页「回到顶部」实测：滚动后出现、点击后回到 0
        send("Page.navigate", {"url": "http://127.0.0.1:8765/favorites"})
        for _ in range(40):
            time.sleep(0.4)
            if ev("document.readyState", awaitp=False) == "complete":
                break
        time.sleep(1.2)
        fv = ev(r"""
        (async () => {
          const sleep = ms => new Promise(r => setTimeout(r, ms));
          const b = document.getElementById('totop');
          const y = () => Math.round(window.pageYOffset);
          const hiddenAtTop = !b.classList.contains('show');
          window.scrollTo(0, Math.max(1200, document.body.scrollHeight));
          await sleep(500);
          const shownAfterScroll = b.classList.contains('show');
          b.click(); await sleep(3000);
          return {hiddenAtTop, shownAfterScroll, yAfterClick: y(),
                  hiddenAfter: !b.classList.contains('show')};
        })()
        """)
        print("/favorites totop ->", json.dumps(fv, ensure_ascii=False))
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
