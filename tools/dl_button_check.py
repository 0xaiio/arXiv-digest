#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证「日报页的下载按钮」这条链路真的通（Edge CDP 真点击）。

为什么需要它：下载按钮报错最常见的两个原因是
  1) 取数路由不通（本机被注入出口代理 → SSL: UNEXPECTED_EOF_WHILE_READING）；
  2) 前端 → 本地服务的往返断了。
二者靠读代码都看不出来，必须真点一次。

做法（**不产生副作用**）：
  · 只在 http://127.0.0.1:8765/ 同源页面上点「已下载过」的论文的下载按钮 ——
    服务端会走「已存在，跳过下载」分支，不写任何新文件；
  · 断言页面出现「已下载并收藏」toast，且按钮变为已下载态。
网络取数这一半另由 `python netroute.py` 与隔离目录测试覆盖。

依赖 websocket-client，请用默认 venv 运行：
  C:\\Users\\hfwei\\.workbuddy\\binaries\\python\\envs\\default\\Scripts\\python.exe tools/dl_button_check.py
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
APIPORT = 8765
API = "http://127.0.0.1:%d" % APIPORT


def find_edge():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("未找到 msedge.exe")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def api(path):
    with opener().open(API + path, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def page_text(url, timeout=60):
    with opener().open(url, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def pick_target(dlset, forced=None):
    """找「页面上有下载按钮」且「已下载过」的论文 —— 这样点击不会写新文件。

    当前期页面只含本期新增论文，往期已下载的论文得去 /archive/<日期> 快照页上点。
    返回 (url, sid)。
    """
    try:
        dates = [i["date"] for i in (api("/api/archive/days").get("issues") or [])]
    except Exception:
        dates = []
    urls = [API + "/"] + [API + "/archive/" + d for d in dates]
    for url in urls:
        try:
            html = page_text(url)
        except Exception:
            continue
        if forced:
            if 'data-sid="%s"' % forced in html:
                return url, forced
            continue
        for sid in sorted(dlset):
            if 'data-sid="%s"' % sid in html:
                return url, sid
    return None, None


class CDP:
    def __init__(self, ws_url):
        import websocket
        self.ws = websocket.create_connection(ws_url, timeout=120, suppress_origin=True)
        self.i = 0

    def send(self, method, params=None, timeout=180):
        self.i += 1
        mid = self.i
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError("%s -> %s" % (method, msg["error"]))
                return msg.get("result", {})
        raise TimeoutError(method)

    def ev(self, expr, timeout=180):
        r = self.send("Runtime.evaluate",
                      {"expression": expr, "returnByValue": True, "awaitPromise": True},
                      timeout=timeout)
        if r.get("exceptionDetails"):
            raise RuntimeError(json.dumps(r["exceptionDetails"], ensure_ascii=False)[:600])
        return r["result"].get("value")


CLICK_DL = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  await sleep(2500);
  const sid = "__SID__";
  const sel = 'button[data-act="dl"][data-sid="' + sid + '"]';
  const btn = document.querySelector(sel);
  const O = {sid: sid, found: !!btn};
  if (!btn) return O;
  O.consoleErrors = (window.__errs || []).slice(0, 5);
  btn.click();
  // 轮询等结果 toast（下载完成会追加 .tst 节点）
  const t0 = Date.now();
  let txt = null;
  while (Date.now() - t0 < 90000) {
    const all = [...document.querySelectorAll('#toast .tst')].map(e => e.textContent);
    const hit = all.reverse().find(t => t.indexOf('下载') >= 0);
    if (hit) { txt = hit; break; }
    await sleep(400);
  }
  O.toast = txt;
  const b2 = document.querySelector(sel);
  O.doneState = b2 ? b2.classList.contains('done') : null;
  O.label = b2 ? (b2.querySelector('.lb') || {}).textContent : null;
  O.consoleErrors = (window.__errs || []).slice(0, 5);
  return O;
})()
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", default=None, help="指定论文短号；默认取一篇已下载的")
    ap.add_argument("--keep-prof", action="store_true")
    a = ap.parse_args()

    try:
        st = api("/api/state")
        route = api("/api/net_route")
    except Exception as e:
        raise SystemExit("本地服务不可达（先启动 server.py --no-open）：%s" % e)
    dls = sorted((st.get("downloads") or {}).keys())
    sys.stdout.write("服务端下载记录 %d 条；下载路由 = %s\n" % (len(dls), route.get("route") or "（无）"))
    target_url, sid = pick_target(set(dls), a.sid)
    if not sid:
        raise SystemExit("找不到「已下载且页面有按钮」的论文（用 --sid 指定一篇已下载的）")
    sys.stdout.write("测试页面：%s\n测试目标：%s（已下载过 → 走「已存在，跳过下载」分支，不写新文件）\n"
                     % (target_url, sid))

    edge = find_edge()
    port = free_port()
    prof = tempfile.mkdtemp(prefix="edge-dlcheck-")
    proc = subprocess.Popen(
        [edge, "--headless=new", "--disable-gpu", "--no-proxy-server", "--no-first-run",
         "--no-default-browser-check", "--user-data-dir=" + prof,
         "--remote-debugging-port=%d" % port, "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = True
    try:
        targets = None
        for _ in range(60):
            try:
                targets = json.loads(opener().open(
                    "http://127.0.0.1:%d/json/list" % port, timeout=3).read())
                if targets:
                    break
            except Exception:
                time.sleep(0.5)
        if not targets:
            raise SystemExit("Edge 调试端口不可达")
        page = [t for t in targets if t.get("type") == "page"][0]
        c = CDP(page["webSocketDebuggerUrl"])
        c.send("Page.enable")
        c.send("Runtime.enable")
        c.send("Emulation.setDeviceMetricsOverride",
               {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        c.send("Page.navigate", {"url": target_url})
        time.sleep(4)
        # 收集页面 JS 报错（下载按钮若抛 TypeError 会在这里现形）
        c.ev("window.__errs=[];window.addEventListener('error',e=>window.__errs.push(String(e.message)));"
             "window.addEventListener('unhandledrejection',e=>window.__errs.push('rej:'+String(e.reason)));true")

        r = c.ev(CLICK_DL.replace("__SID__", sid))
        sys.stdout.write("按钮存在：%s\n" % r.get("found"))
        sys.stdout.write("结果 toast：%r\n" % (r.get("toast") or "(无)"))
        sys.stdout.write("按钮态：done=%s label=%r\n" % (r.get("doneState"), r.get("label")))
        sys.stdout.write("页面 JS 报错：%s\n" % (r.get("consoleErrors") or "无"))
        good = (r.get("found") and r.get("toast") and "下载失败" not in r["toast"]
                and r.get("doneState") and not (r.get("consoleErrors") or []))
        sys.stdout.write("\n结论：%s\n" % ("下载按钮链路 OK" if good else "下载按钮仍有问题"))
        ok = bool(good)
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        time.sleep(0.5)
        if not a.keep_prof:
            shutil.rmtree(prof, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
