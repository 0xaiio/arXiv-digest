#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前黑盒验收：**模拟一次真实的「首次克隆后启动」**，确认首屏是干净的。

为什么要单独一个脚本（而不是 pytest 用例）：
它要**复制整棵源码树**（排除本机运行态）、起一个真进程、走真 HTTP，属于"整机验收"；
pytest 的沙箱是进程内重定向，验证不到"新用户拿到的是哪份目录"。

判据（全部取真实 HTTP 响应）：
  1. `/` 是欢迎页（还没选分类），不是 404 也不是别人的日报；
  2. `/profile` 没有画像主来源、没有类别、显示"干净状态"；
  3. `/favorites` 是空态；`/api/state` 四个集合全空、`download_dir == papers`；
  4. `/api/datapacks` 能列出包，但**只有形状**（name/files/groups/bytes）；
  5. 三个页面都不出现任何私人痕迹（人名 / 研究方向 / 本机路径），
     也不出现作者跟踪的那几个分类号；
  6. 点「导入」等价的一步（POST /api/preset）在**模板初值**上直接成功，
     且导入后本机端口不变。

用法：
  python tools/fresh_clone_check.py            # 默认端口 8767
  python tools/fresh_clone_check.py --port 8790
退出码 0 = 全部通过。
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 私人痕迹：作者本人的人名 / 研究方向 / 本机路径；以及他跟踪的分类号
PRIVATE = ("魏恒峰", "Hengxin", "Gotsman", "Attiya", "Enea", "git-papers",
           "隔离级别", "IsoVista", "Plume", "数据库系统", "形式化方法",
           "Database Systems, Distributed Computing")
HIS_CATS = ("cs.DB", "cs.DC", "cs.FL", "cs.LO", "cs.PL", "cs.SE")


def _ignore(dirname, names):
    """只排除根目录的个人运行态；子目录里的同名文件（数据包！）必须保留。"""
    skip = set()
    for n in names:
        if n in ("output", "node_modules", "tmp_pytest", "site", "reel",
                 "__pycache__", ".git", ".secrets", ".workbuddy", ".coverage"):
            skip.add(n)
        elif n.endswith((".pyc", ".log")):
            skip.add(n)
        elif os.path.abspath(dirname) == ROOT and n in ("config.json", "interests.json"):
            skip.add(n)
    return skip


def _get(opener, port, path):
    with opener.open("http://127.0.0.1:%d%s" % (port, path), timeout=10) as r:
        return r.status, r.read().decode("utf-8", "replace")


def _post(opener, port, path, payload):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (port, path),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def main(argv=None):
    argv = argv or sys.argv[1:]
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8767
    fresh = os.path.join(ROOT, "tmp_pytest", "fresh-%d" % int(time.time()))
    shutil.copytree(ROOT, fresh, ignore=_ignore)
    # 真实首运行生成的就是模板副本；这里只改端口（= 用户改过一次 port，仍属模板初值）
    with open(os.path.join(fresh, "config.example.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["port"] = port
    with open(os.path.join(fresh, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    print("模拟目录：%s" % fresh)

    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen([sys.executable, "server.py", "--no-open"], cwd=fresh,
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    fail = []
    try:
        for _ in range(60):
            try:
                _get(opener, port, "/api/ping")
                break
            except Exception:
                time.sleep(0.3)

        code, home = _get(opener, port, "/")
        ok = code == 200 and "选择要跟踪的 arXiv 分类" in home
        print("[1] / 是欢迎页: %s" % ok)
        if not ok:
            fail.append("/ 不是欢迎页（code=%s）" % code)

        _, prof = _get(opener, port, "/profile")
        ok = "还没有画像主来源" in prof and "干净状态" in prof
        print("[2] /profile 空态且标记干净: %s" % ok)
        if not ok:
            fail.append("/profile 不是空态")

        _, fav = _get(opener, port, "/favorites")
        ok = "还没有收藏" in fav
        print("[3] /favorites 空态: %s" % ok)
        if not ok:
            fail.append("/favorites 不是空态")

        _, st = _get(opener, port, "/api/state")
        st = json.loads(st)
        ok = (not st["favorites"] and not st["downloads"] and not st["downvotes"]
              and not st["categories"] and st["download_dir"] == "papers")
        print("[4] /api/state 全空: %s -> %s"
              % (ok, {k: st[k] for k in ("favorites", "downloads", "downvotes",
                                         "categories", "download_dir")}))
        if not ok:
            fail.append("/api/state 不是空状态")

        _, dp = _get(opener, port, "/api/datapacks")
        dp = json.loads(dp)
        names = [p["name"] for p in dp["packs"]]
        print("[5] /api/datapacks: %s（%d 个包）" % (names, len(names)))
        if not names:
            fail.append("没有列出任何数据包")
        for p in dp["packs"]:
            if set(p) != {"name", "files", "groups", "bytes"}:
                fail.append("包视图 %s 泄漏了额外字段 %s" % (p.get("name"), set(p)))
        for f in ("library.json", "profile_state.json", "behavior.json"):
            if dp["state"]["files"][f]["exists"]:
                fail.append("干净机器却有 %s" % f)

        for name, html in (("首页", home), ("画像页", prof), ("收藏页", fav)):
            hit = [x for x in PRIVATE if x in html]
            print("[6] %s 私人痕迹: %s" % (name, hit or "无"))
            if hit:
                fail.append("%s 出现 %s" % (name, hit))
        hit = [x for x in HIS_CATS if x in home]
        print("[7] 首页分类暗示: %s" % (hit or "无"))
        if hit:
            fail.append("首页出现作者的分类 %s" % hit)

        code, payload = _post(opener, port, "/api/preset",
                             {"op": "import", "name": names[0]})
        cats = (payload.get("state") or {}).get("categories") or []
        print("[8] 一键导入 -> %s %s ｜ 分类 %s" % (code, payload.get("ok"), cats))
        if code != 200 or not payload.get("ok"):
            fail.append("一键导入失败：%s" % payload.get("msg"))
        if not cats:
            fail.append("导入后没有任何类别")

        _, prof2 = _get(opener, port, "/profile")
        ok = prof2 != prof
        print("[9] 导入后 /profile 已变化: %s" % ok)
        if not ok:
            fail.append("导入后画像页没有变化")

        print("\n结果：%s" % ("PASS" if not fail else "FAIL"))
        for f in fail:
            print("  - %s" % f)
        return 0 if not fail else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
