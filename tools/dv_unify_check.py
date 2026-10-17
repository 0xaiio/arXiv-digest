#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Downvote 一致性回归：三个模块真的「一处逻辑、同一表现」。

逐一在「为你推荐」（#rec-list .rec-card）、「兴趣扩展」（#exp-list .rec-card）、
「分类详解」（.plist li.item）、以及「重点论文」（.hl）上真点一次 Downvote，然后断言：

  1. 变灰：容器自身的 computed opacity < 0.9 —— 且四处取值相同；
  2. 删除线：标题 computed text-decoration-line == line-through；
  3. 不消失：容器没有 .hidden、仍在同一父节点里，位次与原位相差 ≤ 1（钉在点击处）；
  4. 乐观更新：点击后**同步**就已经加上了 .down（不等服务端往返）；
  5. 撤销往返：再点一次，.down 消失、透明度回到 1（结束时状态复原）。

需要本地服务在线（127.0.0.1:8765）与 websocket-client。
沙箱里 python 起 Edge 常绑不上调试端口，支持 EDGE_ATTACH_PORT 附加到已开的 Edge。

运行： python tools/dv_unify_check.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ATTACH = int(os.environ.get("EDGE_ATTACH_PORT", "0") or 0)
PORT = ATTACH or 9227

TARGETS = [
    ("rec", "#rec-list .rec-card", ".rec-t"),
    ("exp", "#exp-list .rec-card", ".rec-t"),
    ("item", ".plist li.item", ".r-t a"),
    ("hl", ".hl", ".hl-t a"),
]

PROBE_JS = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const TARGETS = __TARGETS__;
  const out = [];
  const probe = (e, tsel) => {
    const t = tsel ? e.querySelector(tsel) : null;
    return {
      opacity: getComputedStyle(e).opacity,
      deco: t ? getComputedStyle(t).textDecorationLine : null,
      hidden: e.classList.contains('hidden'),
      down: e.classList.contains('down'),
    };
  };
  const sibIdx = e => [...e.parentNode.children].indexOf(e);
  for (const [kind, sel, tsel] of TARGETS) {
    const pool = [...document.querySelectorAll(sel)]
      .filter(e => !e.classList.contains('down') && !e.classList.contains('hidden'));
    const el = pool[0];
    if (!el) { out.push({kind, err: 'no target'}); continue; }
    const btn = el.querySelector('button[data-act="dv"]');
    if (!btn) { out.push({kind, err: 'no dv button'}); continue; }
    const sid = el.dataset.sid;
    const before = {...probe(el, tsel), idx: sibIdx(el), parent: el.parentNode.className};
    btn.click();
    // 乐观更新：点击返回时（尚未有网络往返）应已加 .down
    const optimistic = el.classList.contains('down');
    await sleep(1100);
    const after = {...probe(el, tsel), idx: sibIdx(el)};
    // 撤销往返
    el.querySelector('button[data-act="dv"]').click();
    await sleep(900);
    const back = probe(el, tsel);
    out.push({kind, sid, optimistic, before, after, back,
              sameParent: el.parentNode.className === before.parent});
  }
  return out;
})()
"""


def http_json(port, path):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open("http://127.0.0.1:%d%s" % (port, path), timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    prof = tempfile.mkdtemp(prefix="edge-dv-")
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
                targets = http_json(PORT, "/json/list")
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

        def ev(expr, awaitp=True):
            r = send("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                          "awaitPromise": awaitp})
            if r.get("exceptionDetails"):
                return {"__exception": json.dumps(r["exceptionDetails"], ensure_ascii=False)[:500]}
            return r["result"].get("value")

        send("Page.enable")
        send("Runtime.enable")
        send("Log.enable")
        send("Emulation.setDeviceMetricsOverride",
             {"width": 1440, "height": 980, "deviceScaleFactor": 1, "mobile": False})

        send("Page.navigate", {"url": "http://127.0.0.1:8765/"})
        for _ in range(50):
            time.sleep(0.4)
            if ev("document.readyState", awaitp=False) == "complete":
                break
        time.sleep(2.5)                       # 等 /api/state 回流（已 Downvote 的标灰）

        rows = ev(PROBE_JS.replace("__TARGETS__", json.dumps(TARGETS)))

        errs = []
        for l in logs:
            if l["method"] == "Runtime.exceptionThrown":
                errs.append(l["params"]["exceptionDetails"].get("text"))
            elif l["method"] == "Log.entryAdded":
                e = l["params"]["entry"]
                if e.get("level") == "error":
                    errs.append(e.get("text"))
            elif l["method"] == "Runtime.consoleAPICalled" and l["params"]["type"] == "error":
                errs.append("console.error")

        fails = []
        print("Downvote 三模块一致性 —— 实测：")
        for r in rows:
            print("  ", json.dumps(r, ensure_ascii=False))
            k = r.get("kind")
            if r.get("err"):
                # 重点论文块不是每期都有，没有就跳过；三个主模块缺一个即失败
                if r["err"] == "no target" and k == "hl":
                    continue
                fails.append("%s: %s" % (k, r["err"]))
                continue
            a, b = r["after"], r["back"]
            if not r["optimistic"]:
                fails.append("%s: 点击后未立即变灰（乐观更新失效）" % k)
            if not a["down"]:
                fails.append("%s: 点击后没有 .down" % k)
            if a["hidden"]:
                fails.append("%s: 卡片被隐藏了（应为保留可见）" % k)
            if a["deco"] != "line-through":
                fails.append("%s: 标题没有删除线（%s）" % (k, a["deco"]))
            if float(a["opacity"]) >= 0.9:
                fails.append("%s: 没有变灰（opacity=%s）" % (k, a["opacity"]))
            if abs(a["idx"] - r["before"]["idx"]) > 1:
                fails.append("%s: 卡片位移了（%d → %d）" % (k, r["before"]["idx"], a["idx"]))
            if not r["sameParent"]:
                fails.append("%s: 卡片换了容器" % k)
            if b["down"] or float(b["opacity"]) < 0.9:
                fails.append("%s: 撤销后没有恢复（down=%s opacity=%s）"
                             % (k, b["down"], b["opacity"]))

        ops = {r["after"]["opacity"] for r in rows if r.get("after")}
        decos = {r["after"]["deco"] for r in rows if r.get("after")}
        print("  三处 opacity 取值：%s ｜ text-decoration：%s"
              % (sorted(ops), sorted(decos)))
        if len(ops) != 1 or len(decos) != 1:
            fails.append("三处表现不一致：opacity=%s deco=%s" % (sorted(ops), sorted(decos)))
        if errs:
            fails.append("页面报错：%s" % errs[:3])

        print()
        if fails:
            for f in fails:
                print("FAIL:", f)
            return 1
        print("ALL PASS")
        return 0
    finally:
        try:
            if proc:
                proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
