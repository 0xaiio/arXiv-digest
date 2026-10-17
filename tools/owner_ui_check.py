#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""画像主来源（owners）增删改的 UI 回归：在 /profile 上真实点击，全程只用临时条目。

「画像主来源」此前只能手改 interests.json，现在由 /profile 表单 + POST /api/owner 维护。
这个回归把「新增 → 编辑（改名/改字段）→ 删除」整条链路点一遍，断言：

  1. 新增后卡片立即出现，代表方向按行拆成条目；
  2. 点「编辑」把该条回填进表单：按钮变「保存修改」、出现「取消编辑」；
  3. 保存修改后卡片内容立即更新（含改名）；
  4. 删除后卡片消失，owners 数量回到基线；
  5. 全程无 JS 异常。

安全边界：只增删「UI Test Owner」这一条临时数据，结束即清理；
不会触碰真实的 owners（Constantin Enea 等）。

运行： python tools/owner_ui_check.py
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
PORT = ATTACH or 9231
TMP = "UI Test Owner"

JS = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const q = s => document.querySelector(s);
  const cardOf = n => [...document.querySelectorAll('.owner')].find(e => e.dataset.owner === n);
  const out = {base: [...document.querySelectorAll('.owner')].map(e => e.dataset.owner)};

  // 1) 新增
  q('#own-name').value = 'UI Test Owner';
  q('#own-label').value = 'UI-TEST';
  q('#own-site').value = 'https://example.com/ui-test';
  q('#own-affil').value = 'temp-affil';
  q('#own-topics').value = 'topic one\ntopic two';
  q('#own-save').click();
  await sleep(1500);
  const c1 = cardOf('UI Test Owner');
  out.added = !!c1;
  out.addedTopics = c1 ? c1.querySelectorAll('li').length : 0;
  out.formCleared = q('#own-name').value === '';

  // 2) 编辑回填
  c1.querySelector('[data-edit-owner]').click();
  await sleep(250);
  out.editName = q('#own-name').value;
  out.editTopics = (q('#own-topics').value || '').split('\n').filter(Boolean).length;
  out.btnText = q('#own-save').textContent;
  out.cancelVisible = q('#own-cancel').style.display !== 'none';

  // 3) 保存修改：改名 + 改单位
  q('#own-name').value = 'UI Test Owner 2';
  q('#own-affil').value = 'temp-affil-2';
  q('#own-save').click();
  await sleep(1500);
  const c2 = cardOf('UI Test Owner 2');
  out.renamed = !!c2;
  out.fieldUpdated = c2 ? c2.textContent.includes('temp-affil-2') : false;
  out.oldGone = !cardOf('UI Test Owner');

  // 4) 删除（confirm 直接放行）
  window.confirm = () => true;
  (cardOf('UI Test Owner 2') || {}).querySelector('[data-del-owner]').click();
  await sleep(1500);
  out.removed = !cardOf('UI Test Owner 2');
  out.final = [...document.querySelectorAll('.owner')].map(e => e.dataset.owner);
  return out;
})()
"""


def hj(path):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open("http://127.0.0.1:%d%s" % (PORT, path), timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    prof = tempfile.mkdtemp(prefix="edge-own-")
    proc = None
    if not ATTACH:
        proc = subprocess.Popen([EDGE, "--headless=new", "--remote-debugging-port=%d" % PORT,
                                 "--user-data-dir=" + prof, "--no-first-run",
                                 "--no-default-browser-check", "--no-proxy-server",
                                 "about:blank"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        tg = None
        for _ in range(60):
            try:
                tg = hj("/json/list")
                if tg:
                    break
            except Exception:
                time.sleep(0.5)
        page = [t for t in tg if t.get("type") == "page"][0]
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
                if r.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded"):
                    logs.append(r)

        def ev(e):
            r = send("Runtime.evaluate", {"expression": e, "returnByValue": True,
                                          "awaitPromise": True})
            if r.get("exceptionDetails"):
                d = r["exceptionDetails"]
                return {"__exception": (d.get("exception") or {}).get("description") or d.get("text")}
            return r["result"].get("value")

        send("Page.enable")
        send("Runtime.enable")
        send("Log.enable")
        send("Page.navigate", {"url": "http://127.0.0.1:8765/profile"})
        for _ in range(50):
            time.sleep(0.4)
            if ev("document.readyState") == "complete":
                break
        time.sleep(2.0)

        res = ev(JS)
        print(json.dumps(res, ensure_ascii=False, indent=1))
        if res.get("__exception"):
            print("FAIL: 页面执行异常 ——", res["__exception"])
            return 1

        errs = [l["params"]["exceptionDetails"].get("text") for l in logs
                if l["method"] == "Runtime.exceptionThrown"]
        print("JS 异常:", errs or "无")

        fails = []
        checks = [
            ("added", "新增后卡片未出现"),
            ("formCleared", "保存后表单未清空"),
            ("cancelVisible", "编辑态没有出现「取消编辑」"),
            ("renamed", "改名后卡片未更新"),
            ("fieldUpdated", "保存修改后字段未更新"),
            ("oldGone", "改名后旧卡片仍存在"),
            ("removed", "删除后卡片仍存在"),
        ]
        for k, msg in checks:
            if not res.get(k):
                fails.append(msg)
        if res.get("addedTopics") != 2:
            fails.append("代表方向未按行拆条（%s）" % res.get("addedTopics"))
        if res.get("editName") != TMP:
            fails.append("「编辑」没有把姓名回填表单（%s）" % res.get("editName"))
        if res.get("editTopics") != 2:
            fails.append("「编辑」没有回填代表方向（%s）" % res.get("editTopics"))
        if "保存修改" not in (res.get("btnText") or ""):
            fails.append("编辑态按钮文案未切换（%s）" % res.get("btnText"))
        if TMP in (res.get("final") or []) or (TMP + " 2") in (res.get("final") or []):
            fails.append("临时条目残留：%s" % (res.get("final"),))
        if sorted(res.get("base") or []) != sorted(res.get("final") or []):
            fails.append("owners 未回到基线：%s" % (res.get("final"),))
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
