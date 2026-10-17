#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""并发回归：验证「一篇论文正在下载」时，其它操作不再被串行阻塞。

问题背景：server.py 原先用一把全局锁把整个 /api/download 包起来（含最长 90s 的
网络取数），于是下载一篇 PDF 期间，另一篇的 Downvote / 收藏 全排在后面等价 ——
页面看起来像卡死。现在库锁只保护 library.json 的读-改-写，下载走每篇独立的锁。

做法：进程内起 ThreadingHTTPServer（复用 server.Handler），把 download_pdf 换成
「睡 2s」的桩，library.json 指到临时目录、learn 置空 —— 全程不碰真实文库与画像。

断言：
  1. 下载进行中（模拟 2s）时，对**另一篇**的 Downvote 必须快速返回（< 0.6s）；
     改前它会等满 2s。
  2. /api/download_all 三篇：总耗时 ≈ 一个 2s（3 路并行），而不是三个 2s。
  3. 同一篇并发下载仍串行（每篇一把锁，防止交叉写同名 .part）：≈ 两个 2s。

运行： python tools/concurrency_check.py
"""
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import paperutil as pu          # noqa: E402
import server as S              # noqa: E402

PORT = int(os.environ.get("CONC_PORT", "8799"))
BASE = "http://127.0.0.1:%d" % PORT
SLOW = float(os.environ.get("CONC_SLOW", "2.0"))
DL = 0.35        # Downvote 在下载进行中的耗时上限（秒）
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))

_tmp = tempfile.mkdtemp(prefix="conc-lib-")
_LIB = os.path.join(_tmp, "library.json")


def _slow_download(sid, papers, cfg, force=False):
    """桩：只睡 2s，不联网、不写文件。"""
    time.sleep(SLOW)
    return True, "桩下载", os.path.join(cfg["download_dir"], sid + ".pdf")


def post(path, body=None, timeout=60):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(body or {}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t = time.time()
    with OP.open(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return time.time() - t, data


def drop_in_background(path, body):
    out = {}

    def run():
        out["r"] = post(path, body)

    th = threading.Thread(target=run, daemon=True)
    th.start()
    return th, out


def main():
    pu.LIB_PATH = _LIB                                    # 落库到临时目录
    S.download_pdf = _slow_download
    S.learn = lambda *a, **k: None                        # 不动画像
    S.papers = lambda force=False: {}                     # 不读真实论文索引

    srv = ThreadingHTTPServer(("127.0.0.1", PORT), S.Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    time.sleep(0.4)

    fails = []
    try:
        # --- 1) 下载进行中，Downvote 另一篇不被阻塞 -------------------------
        t, _ = post("/api/download", {"id": "9999.00001"})
        print("[1] 单独下载耗时 %.2fs（桩 %.1fs）" % (t, SLOW))

        dl_th, dl_out = drop_in_background("/api/download", {"id": "9999.00002"})
        time.sleep(0.3)                                   # 确保下载已在服务端执行
        dt, d = post("/api/downvote", {"id": "9999.00003"})
        dl_th.join()
        print("[1] 下载进行中 → Downvote 另一篇耗时 %.3fs，ok=%s（阈值 %.2fs）"
              % (dt, d.get("ok"), DL))
        if not d.get("ok") or dt > DL:
            fails.append("Downvote 被下载串行阻塞了（%.3fs）" % dt)

        # --- 2) 批量下载并行 ----------------------------------------------
        ids = ["9999.1000%d" % i for i in range(1, 4)]
        t2, d2 = post("/api/download_all", {"ids": ids})
        par = t2
        print("[2] download_all 3 篇耗时 %.2fs（串行应为 %.1fs，并行应约 %.1fs）"
              % (par, SLOW * 3, SLOW))
        if d2.get("n_ok") != 3:
            fails.append("download_all 成功数 %s != 3" % d2.get("n_ok"))
        if par > SLOW * 2:
            fails.append("download_all 仍是串行（%.2fs）" % par)
        if [r["id"] for r in d2.get("results", [])] != ids:
            fails.append("download_all 结果顺序与请求不一致")

        # --- 3) 同一篇并发下载仍串行（每篇一把锁） -------------------------
        t3a, _x = None, None
        th_a, _o = drop_in_background("/api/download", {"id": "9999.77777"})
        Th_b, _ob = drop_in_background("/api/download", {"id": "9999.77777"})
        t0 = time.time()
        th_a.join()
        Th_b.join()
        same = time.time() - t0 + 0.0
        print("[3] 同一篇并发下载两次耗时 %.2fs（应约 %.1fs = 两次串行）"
              % (same, SLOW * 2))
        if not (SLOW * 1.7 <= same <= SLOW * 2.6):
            fails.append("同一篇的下载锁没有生效（%.2fs）" % same)

        # --- 4) 库文件完整性：6 篇下载记录都写进去了 ------------------------
        # 1（单独）+ 1（下载中那次）+ 3（批量）+ 1（同一篇并发两次只算一篇）
        lib = pu.load_library()
        n_dl = len(lib.get("downloads", {}))
        print("[4] library.json：downloads=%d favorites=%d downvotes=%d"
              % (n_dl, len(lib.get("favorites", {})), len(lib.get("downvotes", {}))))
        if n_dl != 6:
            fails.append("并发落库丢记录：downloads=%d（应为 6）" % n_dl)
        if "9999.00003" not in lib.get("downvotes", {}):
            fails.append("下载期间的那次 Downvote 没落库")
    finally:
        srv.shutdown()

    print()
    if fails:
        for f in fails:
            print("FAIL:", f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
