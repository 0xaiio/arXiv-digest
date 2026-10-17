#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证「日报 HTML 当普通文件在浏览器里打开」时交互链路是否成立。

背景：日报 HTML 有两副面孔。
  1) 由本地服务同源提供（http://127.0.0.1:8765/）——相对路径 /api/* 天然正确；
  2) 当普通文件交付（预览面板 / 双击 / file://）——origin 变了，页面里的
     fetch('/api/*') 会打到错误 origin，站内链接 href="/favorites" 会变成 file:///favorites。
build_report.py 已用 APIBASE 兜底（跨源时改指 http://127.0.0.1:8765，服务端 CORS `*`），
本脚本用 Edge(CDP) 真跑一遍确认这条链路成立。

判据（全部取渲染后的真实 DOM / 真实网络往返）：
  A. APIBASE 在 file:// 下解析为绝对地址，且站内链接（收藏/画像/存档）同步改写；
  B. 加载后无「本地服务未运行」报错 toast，收藏计数 == 服务端 /api/state 的收藏数；
  C. 点一张卡片的「收藏」→ 服务端 state 立即出现该短号 → 点回取消并复原。

依赖 websocket-client，请用默认 venv 运行：
  python tools/ui_file_check.py
留档工具，不属于日刊流水线。
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


def no_proxy_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def api_state():
    with no_proxy_opener().open(API + "/api/state", timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


class CDP:
    def __init__(self, ws_url):
        import websocket  # websocket-client
        self.ws = websocket.create_connection(ws_url, timeout=90, suppress_origin=True)
        self.i = 0

    def send(self, method, params=None, timeout=120):
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

    def ev(self, expr, timeout=120):
        r = self.send("Runtime.evaluate",
                      {"expression": expr, "returnByValue": True, "awaitPromise": True},
                      timeout=timeout)
        if r.get("exceptionDetails"):
            raise RuntimeError(json.dumps(r["exceptionDetails"], ensure_ascii=False)[:600])
        return r["result"].get("value")


INSPECT = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  await sleep(3000);                        // 留足时间给 /api/state 往返
  const O = {origin: location.origin, protocol: location.protocol};
  O.apibase = (typeof APIBASE === 'string') ? APIBASE : null;
  O.favcount = (document.getElementById('favcount') || {}).textContent;
  O.toasts = [...document.querySelectorAll('#toast .tst')].map(e => e.textContent);
  O.links = {};
  ['favlink', 'proflink', 'archlink', 'backlink'].forEach(id => {
    const a = document.getElementById(id);
    if (a) O.links[id] = a.getAttribute('href');
  });
  O.absAnchorBroken = [...document.querySelectorAll('a[href^="file:"]')].length;
  // 最强判据：改写完成后页面里不应再残留根相对链接（file:// 下会变成 file:///x 打不开）
  O.relLeftover = [...document.querySelectorAll('a[href^="/"]')].map(a => a.getAttribute('href'));
  O.apiLinks = [...new Set([...document.querySelectorAll(
    'a[href^="http://127.0.0.1:' + __APIPORT__ + '"]')].map(a => a.getAttribute('href')))].slice(0, 8);
  // state 是否真的回流：跨源 GET 是否发生 + 页面内收藏态是否被点亮
  O.apiHits = performance.getEntriesByType('resource')
    .filter(e => e.name.indexOf('127.0.0.1:' + __APIPORT__) >= 0)
    .map(e => e.name.replace(/^.*?\/api\//, 'api/'));
  O.favOnCount = document.querySelectorAll('.btn.fav.on, .rec-card .btn[data-act="fav"].on').length;
  // 同一篇论文可能同时出现在推荐卡 / 扩展卡 / 高亮块里 → 按钮数会多于论文数。
  // 页面计数器 syncCount() 是按**去重后的短号**统计的，断言也要按短号比。
  const lit = [...document.querySelectorAll('.btn.fav[data-act="fav"].on')].map(b => b.dataset.sid);
  O.favOnBtn = lit.length;
  O.favOnSids = [...new Set(lit)].length;
  O.dlOnCount = document.querySelectorAll('.btn[data-act="dl"].done').length;
  const cards = [...document.querySelectorAll('.rec-card[data-sid]:not(.down)')]
      .filter(c => { const b = c.querySelector('button[data-act="fav"]');
                     return b && !b.classList.contains('on'); });
  const card = cards[0] || null;
  O.cardSid = card ? card.dataset.sid : null;
  O.favOnBefore = card ? card.querySelector('button[data-act="fav"]').classList.contains('on') : null;
  return O;
})()
"""

CLICK_FAV = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  // 只挑「尚未收藏」的卡片：挑到已收藏的会导致点击 = 取消收藏，
  // 服务端查不到该短号，判据误报 FAIL（2026-09-15 实测踩中）。
  const cards = [...document.querySelectorAll('.rec-card[data-sid]:not(.down)')]
      .filter(c => { const b = c.querySelector('button[data-act="fav"]');
                     return b && !b.classList.contains('on'); });
  const card = cards[0];
  if (!card) return {err: 'no unfavorited card'};
  const sid = card.dataset.sid;
  const btn = card.querySelector('button[data-act="fav"]');
  const before = btn.classList.contains('on');
  btn.click(); await sleep(2000);
  const c2 = document.querySelector('.rec-card[data-sid="' + sid + '"] button[data-act="fav"]');
  const after = c2 ? c2.classList.contains('on') : null;
  return {sid: sid, before: before, after: after};
})()
"""

CLICK_FAV_BACK = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const sid = "__SID__";
  // 复原必须定点作用在同一张卡：重新挑「未收藏」卡会挑到别的卡片，
  // 导致首点那篇没被还原（2026-09-15 实测踩中）。
  const card = document.querySelector('.rec-card[data-sid="' + sid + '"]');
  if (!card) return {err: 'card gone: ' + sid};
  const btn = card.querySelector('button[data-act="fav"]');
  btn.click(); await sleep(1500);
  const c2 = document.querySelector('.rec-card[data-sid="' + sid + '"] button[data-act="fav"]');
  return {sid: sid, back: c2 ? !c2.classList.contains('on') : null};
})()
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html", nargs="?", default=None)
    ap.add_argument("--keep-prof", action="store_true")
    ap.add_argument("--loose", action="store_true",
                    help="宽松模式：只查基址/链接/toast/state 回流，跳过点击往返与计数严格断言")
    a = ap.parse_args()

    if a.html:
        path = a.html if os.path.isabs(a.html) else os.path.join(ROOT, a.html)
    else:
        import paperutil as pu
        path = os.path.join(ROOT, "output",
                            "arxiv_digest_%s.html" % pu.now_str()[:10].replace("-", ""))
    if not os.path.exists(path):
        raise SystemExit("文件不存在：%s" % path)

    try:
        st = api_state()
    except Exception as e:
        raise SystemExit("本地服务不可达（先启动 server.py --no-open）：%s" % e)
    want_fav = len(st.get("favorites") or [])
    sys.stdout.write("文件：%s\n服务端收藏数：%d\n" % (path, want_fav))

    edge = find_edge()
    port = free_port()
    prof = tempfile.mkdtemp(prefix="edge-filecheck-")
    proc = subprocess.Popen(
        [edge, "--headless=new", "--disable-gpu", "--no-proxy-server", "--no-first-run",
         "--no-default-browser-check", "--user-data-dir=" + prof,
         "--remote-debugging-port=%d" % port, "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = True
    try:
        op = no_proxy_opener()
        targets = None
        for _ in range(60):
            try:
                targets = json.loads(op.open("http://127.0.0.1:%d/json/list" % port, timeout=3).read())
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
               {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        url = "file:///" + os.path.abspath(path).replace("\\", "/")
        c.send("Page.navigate", {"url": url})
        time.sleep(4)

        o = c.ev(INSPECT.replace("__APIPORT__", str(APIPORT)))
        sys.stdout.write("origin=%s  APIBASE=%r\n" % (o["origin"], o["apibase"]))
        sys.stdout.write("带 id 的入口：%s\n" % json.dumps(o["links"], ensure_ascii=False))
        sys.stdout.write("已改写为本地服务的链接：%s\n" % (o.get("apiLinks") or "无"))
        sys.stdout.write("残留根相对链接：%s\n" % (o.get("relLeftover") or "无"))
        sys.stdout.write("跨源请求命中：%s\n" % (o.get("apiHits") or "无"))

        exp_base = API
        base_ok = (o["apibase"] == exp_base)
        links_ok = not (o.get("relLeftover") or []) and bool(o.get("apiLinks"))
        toasts_ok = not any("本地服务" in t for t in o["toasts"])
        api_ok = any("api/state" in h for h in (o.get("apiHits") or []))
        # 页显收藏数是「本页」点亮数，不是全库收藏数（本页只含本期论文）；
        # 没有 #favcount 的页面（如存档页）跳过该断言。
        fc = o.get("favcount")
        if fc is None or a.loose:
            count_ok, count_txt = True, "N/A"
        else:
            count_ok = (str(fc).strip() == str(o.get("favOnSids")))
            count_txt = "页显=%s 页内点亮论文=%s（按钮 %s 个）" % (
                fc, o.get("favOnSids"), o.get("favOnBtn"))
        sys.stdout.write("A 跨源基址：%s（apibase=%s）｜链接改写：%s\n"
                         % ("OK" if base_ok else "FAIL", base_ok, "OK" if links_ok else "FAIL"))
        sys.stdout.write("B 无报错 toast：%s（toast=%s）\n" % ("OK" if toasts_ok else "FAIL", o["toasts"]))
        sys.stdout.write("B /api/state 跨源回流：%s\n" % ("OK" if api_ok else "FAIL"))
        sys.stdout.write("B 收藏计数自洽：%s（全库收藏=%d）%s\n"
                         % (count_txt, want_fav, "OK" if count_ok else "FAIL"))
        ok &= base_ok and links_ok and toasts_ok and api_ok and count_ok

        # C 真实点击一次收藏，看服务端是否收到（跨源 POST + CORS 预检）
        r = {"err": "loose 模式跳过点击往返"} if a.loose else c.ev(CLICK_FAV)
        if r.get("err"):
            sys.stdout.write("C 收藏往返：SKIP（%s）\n" % r["err"])
        else:
            time.sleep(0.6)
            now = set(api_state().get("favorites") or [])
            added = (r["sid"] in now)
            sys.stdout.write("C 点击收藏：sid=%s before=%s after=%s 服务端已记录=%s %s\n"
                             % (r["sid"], r["before"], r["after"], added,
                                "OK" if (r["after"] and added) else "FAIL"))
            ok &= bool(r["after"]) and added
            back = c.ev(CLICK_FAV_BACK.replace("__SID__", r["sid"]))
            time.sleep(0.6)
            now2 = set(api_state().get("favorites") or [])
            restored = (r["sid"] not in now2) if not r["before"] else (r["sid"] in now2)
            sys.stdout.write("C 复原：%s %s\n" % (back, "OK" if restored else "FAIL"))
            ok &= restored
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        time.sleep(0.5)
        if not a.keep_prof:
            shutil.rmtree(prof, ignore_errors=True)

    sys.stdout.write("\n结论：%s\n" % ("本地 HTML 在浏览器中打开时交互可用"
                                      if ok else "存在失败项，请排查"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
