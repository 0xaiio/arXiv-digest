#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Edge(CDP) 实测摘要页交互：重排是否跳动 / Downvote 打灰是否一致 / 侧栏与回顶。
留档工具，不属于日刊流水线。

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

import websocket  # websocket-client

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
URL = "http://127.0.0.1:8765/"
ATTACH = int(os.environ.get("EDGE_ATTACH_PORT", "0") or 0)
PORT = ATTACH or 9222


def http_json(path):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path))
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=60,
                                             suppress_origin=True)
        self.i = 0

    def send(self, method, params=None, timeout=90):
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

    def ev(self, expr, timeout=90):
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True,
        }, timeout=timeout)
        if r.get("exceptionDetails"):
            raise RuntimeError(json.dumps(r["exceptionDetails"], ensure_ascii=False)[:900])
        return r["result"].get("value")


PROBE = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const y = () => Math.round(window.pageYOffset);
  const rectTop = el => el ? Math.round(el.getBoundingClientRect().top) : null;
  const nosm = () => document.documentElement.classList.add('nosm');
  const smooth = () => document.documentElement.classList.remove('nosm');
  const O = {marker: (window.__probe = (window.__probe || 0) + 1)};
  const rec = document.getElementById('rec-list');
  O.totopAtLoad = document.getElementById('totop').classList.contains('show');
  // 侧栏是否压住正文：取「活动标签」最左边 vs 正文列最右边
  O.overlap = (() => {
    const wrap = document.querySelector('.wrap').getBoundingClientRect();
    const rail = document.getElementById('rail').getBoundingClientRect();
    return {wrapRight: Math.round(wrap.right), railLeft: Math.round(rail.left),
            gap: Math.round(rail.left - wrap.right)};
  })();
  nosm();                       // 探针全程用瞬时滚动，排除动画未结束造成的假象

  // ---------- 1) 点 Abstract：不能重排、不能跳 ----------
  let cards = [...rec.querySelectorAll('.rec-card:not(.hidden)')];
  let c = cards[2], sid = c.dataset.sid;
  c.scrollIntoView({block: 'center'}); await sleep(250);
  let y0 = y(), t0 = rectTop(c);
  let firstBefore = rec.querySelector('.rec-card').dataset.sid;
  let orderBefore = [...rec.querySelectorAll('.rec-card:not(.hidden)')].map(e => e.dataset.sid).join(',');

  c.querySelector('button[data-act="abs"]').click();
  await sleep(1500);
  let ca = document.querySelector('#rec-list .rec-card[data-sid="' + sid + '"]');
  O.abs = {
    sid, dy: y() - y0, topBefore: t0, topAfter: rectTop(ca),
    open: ca.querySelector('.abst').classList.contains('open'),
    orderChanged: [...rec.querySelectorAll('.rec-card:not(.hidden)')].map(e => e.dataset.sid).join(',') !== orderBefore,
    firstUnchanged: rec.querySelector('.rec-card').dataset.sid === firstBefore,
  };

  // ---------- 2) 点 Downvote：不跳顶；卡片/分类条目/重点论文三处都要打灰划掉 ----------
  cards = [...rec.querySelectorAll('.rec-card:not(.hidden)')];
  c = cards[2];
  const dvid = c.dataset.sid;
  c.scrollIntoView({block: 'center'}); await sleep(250);
  y0 = y(); t0 = rectTop(c);
  c.querySelector('button[data-act="dv"]').click();
  await sleep(2500);
  const dvc = document.querySelector('#rec-list .rec-card[data-sid="' + dvid + '"]');
  const li = document.querySelector('li.item[data-sid="' + dvid + '"]');
  const hl = document.querySelector('.hl[data-sid="' + dvid + '"]');
  O.dv = {
    sid: dvid, dy: y() - y0, topBefore: t0,
    cardDown: dvc.classList.contains('down'), cardHidden: dvc.classList.contains('hidden'),
    cardLineThrough: getComputedStyle(dvc.querySelector('.rec-t')).textDecorationLine,
    liFound: !!li, liDown: li ? li.classList.contains('down') : null,
    liOpacity: li ? getComputedStyle(li).opacity : null,
    liLineThrough: li ? getComputedStyle(li.querySelector('.r-t a')).textDecorationLine : null,
    hlFound: !!hl, hlDown: hl ? hl.classList.contains('down') : null,
  };

  // 全页扫一遍：所有「已 Downvote」的容器是否都带 down 类
  const dvBtns = [...new Set([...document.querySelectorAll('.btn.dv.on')].map(b => b.dataset.sid))];
  O.dvCoverage = dvBtns.map(s => {
    const card = document.querySelector('.rec-card[data-sid="' + s + '"]');
    const item = document.querySelector('li.item[data-sid="' + s + '"]');
    const h = document.querySelector('.hl[data-sid="' + s + '"]');
    return {sid: s,
      card: card ? card.classList.contains('down') : 'n/a',
      item: item ? item.classList.contains('down') : 'n/a',
      hl: h ? h.classList.contains('down') : 'n/a'};
  });
  const undo = await fetch('/api/undownvote', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: dvid})});
  O.undo = (await undo.json()).ok;
  await sleep(300);

  // ---------- 3) 侧栏：数量 / 标签 / scrollspy ----------
  O.railCount = document.querySelectorAll('#rail .navi').length;
  O.railLabels = [...document.querySelectorAll('#rail .navlbl')].map(e => e.textContent.trim());
  O.railTitles = [...document.querySelectorAll('#rail .navi')].map(e => e.getAttribute('title'));
  O.railVisible = getComputedStyle(document.getElementById('rail')).display;
  O.railError = window.__railErr || null;

  const activeNow = () => {
    const n = document.querySelector('#rail .navi.on');
    if (!n) return null;
    const l = n.querySelector('.line');
    return {lbl: n.querySelector('.navlbl').textContent.trim(),
            lineW: getComputedStyle(l).width, lineBg: getComputedStyle(l).backgroundColor};
  };
  const goesTo = async (target) => {
    window.scrollTo(0, document.getElementById(target).offsetTop + 40);
    await sleep(1000);          // 无头环境里 scroll 事件可能延迟 300-400ms 才送达
    const a = activeNow();
    // 不变式：视口顶部所在的小节 = 绝对位置 <= y+150 中最大的那个
    const anch = 150, cur = y();
    let exp = null, expTop = -Infinity;
    [...document.querySelectorAll('#rail .navi')].forEach(n => {
      const el = document.getElementById(n.dataset.target);
      const abs = cur + Math.round(el.getBoundingClientRect().top);
      if (abs <= cur + anch && abs > expTop) { expTop = abs; exp = n.dataset.target; }
    });
    if (!exp) exp = document.querySelector('#rail .navi').dataset.target;
    return {want: target, got: a && a.lbl, expectedTarget: exp,
            activeTarget: (document.querySelector('#rail .navi.on') || {}).dataset &&
                          document.querySelector('#rail .navi.on').dataset.target,
            ok: exp === (document.querySelector('#rail .navi.on') || {dataset: {}}).dataset.target};
  };
  O.spy = {};
  for (const t of ['cat-cs.DB', 'cat-cs.FL', 'cat-cs.SE', 'sec-exp', 'sec-rec']) {
    O.spy[t] = await goesTo(t);
  }
  // 活动标签最左边 vs 正文列最右边（含活动标签可见状态）
  O.overlapActive = (() => {
    const wrap = document.querySelector('.wrap').getBoundingClientRect();
    const lbl = document.querySelector('#rail .navi.on .navlbl');
    if (!lbl) return null;
    return {wrapRight: Math.round(wrap.right), lblLeft: Math.round(lbl.getBoundingClientRect().left)};
  })();

  // ---------- 4) 回到顶部按钮 ----------
  O.totopHiddenAtTop = !document.getElementById('totop').classList.contains('show');
  window.scrollTo(0, 3000); await sleep(400);
  O.totopShown = document.getElementById('totop').classList.contains('show');
  smooth();
  document.getElementById('totop').click(); await sleep(3500);
  O.totopY = y();
  O.totopHiddenAfter = !document.getElementById('totop').classList.contains('show');

  // ---------- 5) 点侧栏横线（平滑滚动）真的跳到对应分类 ----------
  const nav = [...document.querySelectorAll('#rail .navi')].find(e => e.dataset.target === 'cat-cs.LO');
  O.railClickable = !!nav;
  nav.click(); await sleep(4000);
  O.railJumpTop = rectTop(document.getElementById('cat-cs.LO'));
  O.railActiveAfterClick = activeNow();

  O.navEntries = performance.getEntriesByType('navigation').length;
  smooth();
  return O;
})()
"""


def main():
    prof = tempfile.mkdtemp(prefix="edge-probe-")
    proc = None
    if not ATTACH:
        proc = subprocess.Popen([
            EDGE, "--headless=new", "--remote-debugging-port=%d" % PORT,
            "--user-data-dir=" + prof, "--no-first-run", "--no-default-browser-check",
            "--no-proxy-server", "--disable-extensions",
            "--window-size=" + os.environ.get("PROBE_WIN", "1440,900"),
            "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        targets = None
        for _ in range(60):
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
        # 附加模式下窗口尺寸不一定生效，显式固定视口，否则 #rail 会被 max-width 媒体查询隐藏
        W, H = (os.environ.get("PROBE_WIN", "1440,900").split(",") + ["900"])[:2]
        c.send("Emulation.setDeviceMetricsOverride",
               {"width": int(W), "height": int(H), "deviceScaleFactor": 1, "mobile": False})
        c.send("Page.navigate", {"url": URL})
        time.sleep(3.5)
        title = c.ev("document.title")
        print("title:", title)
        res = c.ev(PROBE)
        print(json.dumps(res, ensure_ascii=False, indent=1))
    finally:
        try:
            if proc:
                proc.terminate()
        except Exception:
            pass
        time.sleep(0.6)
        shutil.rmtree(prof, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
