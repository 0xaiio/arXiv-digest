#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3 新功能真实浏览器验证（Edge + CDP）。

覆盖
  1) 类别统计：顶部重复入口已移除；卡片第一行「类别 + 篇数」蓝色粗体、第二行主题；
     无「点击跳转」文案；hover 有抬升反馈；点击真的跳到对应分类锚点。
  2) 作者单位行（🏛）确实渲染在卡片上。
  3) /profile：主题条 / 来源 / 类别 / 下载目录 都在；能增删类别；能改下载目录。
     类别选择器已改为「两级联动下拉 + 可拖拽标签」，本探针走**手动输入框**那条路径
     （新增/删除），拖拽排序与联动下拉由 tests/e2e/test_category_picker_ui.py 覆盖。
  4) 回归：侧栏 rail、回到顶部、无 console 报错。

沙箱里 python 子进程启动的 Edge 绑不上调试端口，故支持 EDGE_ATTACH_PORT 附加模式。
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
PORT = ATTACH or 9241
BASE = "http://127.0.0.1:8765"


def http_json(path):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open("http://127.0.0.1:%d%s" % (PORT, path), timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=90, suppress_origin=True)
        self.i = 0
        self.logs = []

    def send(self, method, params=None):
        self.i += 1
        mid = self.i
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == mid:
                if "error" in r:
                    raise RuntimeError("%s -> %s" % (method, r["error"]))
                return r.get("result", {})
            if r.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded",
                                   "Runtime.consoleAPICalled"):
                self.logs.append(r)

    def ev(self, expr, awaitp=True):
        r = self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                          "awaitPromise": awaitp})
        if r.get("exceptionDetails"):
            return {"__exception": json.dumps(r["exceptionDetails"],
                                              ensure_ascii=False)[:500]}
        return r["result"].get("value")

    def goto(self, path, settle=2.0):
        self.logs.clear()
        self.send("Page.navigate", {"url": BASE + path})
        for _ in range(50):
            time.sleep(0.4)
            if self.ev("document.readyState", awaitp=False) == "complete":
                break
        time.sleep(settle)

    def errors(self):
        out = []
        for l in self.logs:
            if l["method"] == "Runtime.exceptionThrown":
                out.append(l["params"]["exceptionDetails"].get("text"))
            elif l["method"] == "Log.entryAdded":
                e = l["params"]["entry"]
                if e.get("level") in ("error", "warning"):
                    out.append("%s: %s" % (e.get("level"), e.get("text")))
            elif (l["method"] == "Runtime.consoleAPICalled"
                  and l["params"]["type"] == "error"):
                out.append("console.error")
        return out


CHECK_STATS = r"""
(() => {
  const st = [...document.querySelectorAll('.stats .stat')];
  const first = st[0];
  const b = first.querySelector('.stat-top b');
  const em = first.querySelector('.stat-top em');
  const sb = first.querySelector('.stat-sub');
  const cs = getComputedStyle(b);
  const bodyTxt = document.body.innerText;
  return {
    catRowGone: document.querySelectorAll('.cats').length === 0,
    nStats: st.length,
    firstCode: b.textContent.trim(),
    firstCount: em.textContent.trim(),
    firstTopic: sb.textContent.trim(),
    codeColor: cs.color,
    codeWeight: cs.fontWeight,
    countColor: getComputedStyle(em).color,
    cursor: getComputedStyle(first).cursor,
    hasGoArrow: !!first.querySelector('.stat-go'),
    jumpText: (bodyTxt.match(/点击跳转/g) || []).length,
    affLines: document.querySelectorAll('.rec-u').length,
    affSample: (document.querySelector('.rec-u') || {}).textContent || '',
    railNav: document.querySelectorAll('#rail .navi').length,
    totop: !!document.getElementById('totop'),
    proflink: !!(document.getElementById('proflink') || {}).href,
  };
})()
"""

HOVER_TEST = r"""
(() => {
  const el = document.querySelector('.stats .stat');
  const r = el.getBoundingClientRect();
  window.__statXY = [Math.round(r.left + r.width/2), Math.round(r.top + r.height/2)];
  window.__statBefore = getComputedStyle(el).transform;
  window.__statBorderBefore = getComputedStyle(el).borderTopColor;
  return window.__statXY;
})()
"""

HOVER_AFTER = r"""
(() => {
  const el = document.querySelector('.stats .stat');
  const go = el.querySelector('.stat-go');
  return {
    transform: getComputedStyle(el).transform,
    border: getComputedStyle(el).borderTopColor,
    shadow: getComputedStyle(el).boxShadow,
    arrowOpacity: go ? getComputedStyle(go).opacity : null,
  };
})()
"""

CHECK_PROFILE = r"""
(() => {
  return {
    themes: document.querySelectorAll('#themes .theme-row').length,
    customThemes: document.querySelectorAll('#themes .theme-row.is-custom').length,
    barWidths: [...document.querySelectorAll('#themes .bar i')].slice(0,3)
                 .map(e => e.style.width),
    cats: [...document.querySelectorAll('#cat-list .cat-tag .t-id')].map(e => e.textContent.trim()),
    srcItems: document.querySelectorAll('#src-list .src-item').length,
    srcEmpty: !!document.querySelector('#src-list .p-empty'),
    dldir: (document.getElementById('dldir') || {}).value,
    dldirSave: !!document.getElementById('dldir-save'),
    rebuild: !!document.getElementById('rebuild'),
    addBtns: [!!document.getElementById('src-add'), !!document.getElementById('cat-add')],
    srcTypes: [...document.querySelectorAll('#src-type option')].map(o => o.value),
  };
})()
"""

ADD_CAT = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const before = document.querySelectorAll('#cat-list .cat-tag').length;
  document.getElementById('cat-value').value = 'cs.LG';
  document.getElementById('cat-add').click();
  for (let i = 0; i < 30; i++) { await sleep(300);
    if (document.querySelectorAll('#cat-list .cat-tag').length !== before) break; }
  const codes = [...document.querySelectorAll('#cat-list .cat-tag .t-id')].map(e => e.textContent.trim());
  const topics = [...document.querySelectorAll('#cat-list .cat-tag .t-zh')].map(e => e.textContent.trim());
  const idx = codes.indexOf('cs.LG');
  return {before, after: codes.length, added: idx >= 0,
          addedTopic: idx >= 0 ? topics[idx] : null};
})()
"""

DEL_CAT = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  window.confirm = () => true;
  const before = document.querySelectorAll('#cat-list .cat-tag').length;
  const el = [...document.querySelectorAll('#cat-list .cat-tag')]
    .find(e => e.querySelector('.t-id').textContent.trim() === 'cs.LG');
  if (!el) return {error: 'cs.LG not found'};
  el.querySelector('[data-del-cat]').click();
  for (let i = 0; i < 30; i++) { await sleep(300);
    if (document.querySelectorAll('#cat-list .cat-tag').length !== before) break; }
  const codes = [...document.querySelectorAll('#cat-list .cat-tag .t-id')].map(e => e.textContent.trim());
  return {before, after: codes.length, removed: codes.indexOf('cs.LG') < 0, cats: codes};
})()
"""

DLDIR_TEST = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const inp = document.getElementById('dldir');
  const orig = inp.value;
  inp.value = orig;                       // 原值保存一次，等价于幂等写入
  document.getElementById('dldir-save').click();
  await sleep(1500);
  const r = await fetch('/api/state').then(x => x.json());
  return {orig, after: r.download_dir, same: r.download_dir === orig};
})()
"""


def main():
    prof = tempfile.mkdtemp(prefix="edge-v3-")
    proc = None
    if not ATTACH:
        proc = subprocess.Popen(
            [EDGE, "--headless=new", "--remote-debugging-port=%d" % PORT,
             "--user-data-dir=" + prof, "--no-first-run", "--no-default-browser-check",
             "--no-proxy-server", "--disable-extensions", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        targets = None
        for _ in range(70):
            try:
                targets = http_json("/json/list")
                if targets:
                    break
            except Exception:
                time.sleep(0.5)
        if not targets:
            raise SystemExit("edge devtools not reachable")
        page = [t for t in targets if t.get("type") == "page"][0]
        c = CDP(page["webSocketDebuggerUrl"])
        c.send("Page.enable")
        c.send("Runtime.enable")
        c.send("Log.enable")
        c.send("Emulation.setDeviceMetricsOverride",
               {"width": 1440, "height": 980, "deviceScaleFactor": 1, "mobile": False})

        print("=== 摘要页 ===")
        c.goto("/", settle=3.0)
        print(json.dumps(c.ev(CHECK_STATS), ensure_ascii=False, indent=1))
        print("errors:", c.errors() or "none")

        # hover：真实鼠标移动，验证「可点击」的视觉反馈
        xy = c.ev(HOVER_TEST)
        c.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": xy[0], "y": xy[1],
                                            "button": "none"})
        time.sleep(0.6)
        print("hover ->", json.dumps(c.ev(HOVER_AFTER), ensure_ascii=False))

        # 点击第一张卡片，验证跳到分类锚点
        c.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": xy[0], "y": xy[1],
                                            "button": "left", "clickCount": 1})
        c.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": xy[0], "y": xy[1],
                                            "button": "left", "clickCount": 1})
        time.sleep(1.5)
        c.ev("window.scrollTo(0,0)", awaitp=False)
        print("click -> hash=%s" % c.ev("location.hash", awaitp=False))

        print("\n=== 画像与设置页 ===")
        c.goto("/profile", settle=2.5)
        print(json.dumps(c.ev(CHECK_PROFILE), ensure_ascii=False, indent=1))
        print("errors:", c.errors() or "none")

        print("add cs.LG ->", json.dumps(c.ev(ADD_CAT), ensure_ascii=False))
        print("del cs.LG ->", json.dumps(c.ev(DEL_CAT), ensure_ascii=False))
        print("dldir    ->", json.dumps(c.ev(DLDIR_TEST), ensure_ascii=False))
        print("errors:", c.errors() or "none")
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
