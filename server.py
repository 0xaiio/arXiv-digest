#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地论文服务：为摘要页提供「收藏 / 下载 PDF」等交互能力（端口与下载目录见 config.json）。

启动： python server.py  (默认 http://127.0.0.1:8765)
接口：
  GET  /                     最新一期摘要页（只含本期新增论文）
  GET  /favorites            收藏列表页
  GET  /profile              兴趣画像与设置页（类别 / 来源 / 下载目录）
  GET  /archive              历史存档总览（按日期浏览往期日报）
  GET  /archive/<YYYYMMDD>   某一期的日报快照
  GET  /api/archive/days     存档日期列表与统计（JSON）
  GET  /files/<name>         output 目录下的静态文件
  GET  /api/state            收藏/下载/画像状态
  GET  /api/net_route        下载路由诊断（下载失败时先看这里）
  GET  /api/customize        定制项 + 完整画像（画像页用）
  POST /api/favorite         {id}  收藏（可带 meta）
  POST /api/unfavorite       {id}  取消收藏
  POST /api/download         {id}  下载 PDF 到 download_dir 并自动收藏
  POST /api/download_all     {ids:[...]}  批量下载（DL_WORKERS 路并发）
  POST /api/open             {id}  打开已下载的 PDF
  POST /api/open_folder      {dir?}  打开下载目录
  POST /api/owner            {op:add|update|remove, name, label?, site?, affiliation?,
                              interests?, signature_topics[], link_person?, orig?}  画像主来源
  POST /api/category         {op:add|remove, cat, name?}  增删 arXiv 类别
  POST /api/config           {download_dir}                指定下载目录
  POST /api/source           {op:add|remove, type, value, note?, sid?}  兴趣来源

并发模型：库锁（_lib_lock）只保护 library.json / profile_state.json 的读-改-写，
网络下载不持库锁、每篇论文一把独立锁 —— 不同论文的下载与 Downvote 可同时执行。
"""
import json
import os
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import customize as CZ
import netroute as NR
import paperutil as pu
import profile as PF

HERE = os.path.dirname(os.path.abspath(__file__))
# 防御：无论以何种方式被拉起（含 `start /b` 不继承 cwd 的情况），
# 都把进程工作目录固定到脚本自身所在目录，避免读到别处的 output/。
try:
    os.chdir(HERE)
except Exception:
    pass
OUT = pu.OUT
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) arxiv-digest/2.0"}
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------------- 并发模型
# 服务是 ThreadingHTTPServer，但「共享文件」必须串行读-改-写，否则两个请求
# 各自 load→改→save 会互相覆盖（收藏 / Downvote 丢记录）。
#
# 这里把锁拆成两级，关键在于**网络下载不再持库锁**：
#   _lib_lock  只覆盖 library.json / profile_state.json 的内存操作 + 落盘（毫秒级）
#   _dl_locks  每篇论文一把，防止同一篇被连点两次时并发写同名 .part 文件
# 由此，一篇 PDF 下到一半（最长 90s）时，另一篇的 Downvote / 收藏 / 下载
# 都能同时进行 —— 之前所有请求排在同一把锁后面，一个下载就把整个页面卡住。
_lib_lock = threading.Lock()
_dl_locks = {}
_dl_locks_guard = threading.Lock()
DL_WORKERS = 3


def dl_lock(sid):
    """取某篇论文的下载锁（同一篇串行，不同篇并行）。"""
    with _dl_locks_guard:
        return _dl_locks.setdefault(sid, threading.Lock())


def latest_digest():
    fs = [f for f in os.listdir(OUT) if f.startswith("arxiv_digest_") and f.endswith(".html")]
    if not fs:
        return None
    fs.sort()
    return os.path.join(OUT, fs[-1])


def ensure_dir(d):
    os.makedirs(d, exist_ok=True)


def quiet_remove(p):
    try:
        os.remove(p)
    except OSError:
        pass


def download_pdf(sid, papers, cfg, force=False):
    """下载到 cfg['download_dir']，返回 (ok, message, path)。

    取数一律走 ``netroute``（自动挑选可用路由：直连 / 环境代理 / 本机代理端口）。
    本机常被注入出口代理，它会对 arxiv 完成 CONNECT 却立刻掐断 TLS 流
    （SSL: UNEXPECTED_EOF_WHILE_READING），直连又被拒 —— 用默认 opener 必失败，
    这正是「点下载就报错」的根因。
    """
    p = papers.get(sid)
    if not p:
        # 也可能来自历史收藏
        lib = pu.load_library()
        p = lib["favorites"].get(sid) or lib["downloads"].get(sid)
    if not p:
        return False, "未找到论文元数据（可能已过期，请重新生成摘要）", ""

    year = (p.get("published") or "")[:4] or str(time.localtime().tm_year)
    fname = pu.build_filename(sid, p.get("title", ""), year)
    ddir = cfg["download_dir"]
    try:
        ensure_dir(ddir)
    except Exception as e:
        return False, "无法创建目录 %s：%s" % (ddir, e), ""

    path = os.path.join(ddir, fname)
    if os.path.exists(path) and not force:
        return True, "已存在，跳过下载", path

    tmp = path + ".part"
    try:
        data, label, _url = NR.fetch_first(NR.pdf_urls(sid, p.get("pdf")), timeout=90)
    except NR.RouteError as e:
        fail = NR.last_failure()
        print("[download] %s 取数失败：%s | %s" % (sid, e, fail.get("detail", "")))
        return False, ("所有网络路由都不通（已试 直连 / 环境代理 / 本机代理）：%s。"
                       "诊断见 http://127.0.0.1:8765/api/net_route" % e), ""
    except Exception as e:
        return False, "下载失败：%s" % str(e)[:200], ""

    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception as e:
        quiet_remove(tmp)
        return False, "写入失败 %s：%s" % (path, e), ""
    return True, "已下载（%s，%.0f KB）" % (label, len(data) / 1024.0), path


_papers_cache = {"ts": 0.0, "data": {}}
_papers_lock = threading.Lock()


def papers(force=False):
    """带缓存的论文索引（抓取结果较大，避免每次请求都重新解析）。

    并发下载线程会同时要索引：加锁 + 双重检查，只让一个线程真正去解析大 JSON，
    其余线程等它解析完直接复用缓存（比各自解析 N 份更省内存与时间）。
    """
    now = time.time()
    if force or now - _papers_cache["ts"] > 60:
        with _papers_lock:
            if force or time.time() - _papers_cache["ts"] > 60:
                _papers_cache["data"] = pu.load_papers()
                _papers_cache["ts"] = time.time()
    return _papers_cache["data"]


def profile_snapshot():
    st = PF.load()
    return {
        "topics": [n for n, _ in PF.seed_weights()],
        "weights": [w for _, w in PF.weights(st)],
        "kw": {k: round(v, 3) for k, v in st.get("kw", {}).items() if abs(v) > 0.05},
        "pens": st.get("paper_bonus", {}),
    }


def learn(sid, action):
    """记录行为并更新画像（论文元数据缺失时只记录计数）。"""
    try:
        PF.apply_event(sid, action, paper=papers().get(sid))
    except Exception as e:  # noqa
        sys.stderr.write("learn %s %s failed: %s\n" % (sid, action, e))


_rebuild_lock = threading.Lock()


def rebuild_digest():
    """重跑 recommend + build_report（不重新抓取）。

    类别增删 / 兴趣来源变化改的是画像与配置，只有重算才会反映到摘要页。
    返回 (ok, msg)。
    """
    with _rebuild_lock:
        for name in ("recommend.py", "build_report.py"):
            cmd = [sys.executable, os.path.join(HERE, name)]
            try:
                r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=300)
            except subprocess.TimeoutExpired:
                return False, "%s 超时（>300s）" % name
            except Exception as e:  # noqa
                return False, "%s 启动失败：%s" % (name, e)
            if r.returncode != 0:
                return False, "%s 失败：%s" % (name, (r.stderr or r.stdout or "")[-400:])
        _papers_cache["ts"] = 0.0        # 让下一次请求重新读论文索引
    return True, "已重算推荐并重建摘要页，回到摘要页刷新即可看到更新"


def add_favorite(sid, note=None):
    lib = pu.load_library()
    p = papers().get(sid) or lib["favorites"].get(sid) or lib["downloads"].get(sid)
    meta = pu.paper_meta(p) if p else {"id": sid, "title": sid}
    meta.setdefault("id", sid)
    rec = lib["favorites"].get(sid, {})
    if not rec.get("added_at"):
        rec["added_at"] = pu.now_str()
    rec.update({k: v for k, v in meta.items() if v})
    if note:
        rec["note"] = note
    if sid in lib["downloads"]:
        rec["downloaded"] = True
        rec["path"] = lib["downloads"][sid].get("path", "")
    lib["favorites"][sid] = rec
    pu.save_library(lib)
    return lib


def _record_download(sid, path):
    """把「已下载」写进 library.json 并自动收藏（纯内存 + 落盘，毫秒级，持库锁）。"""
    with _lib_lock:
        lib = pu.load_library()
        lib["downloads"][sid] = {
            "path": path, "at": pu.now_str(),
            "title": (papers().get(sid) or {}).get("title", "")}
        pu.save_library(lib)
        add_favorite(sid)
        learn(sid, "download")


def _download_one(sid, cfg):
    """单篇下载（批量下载的工作单元）：取数不持库锁，落库才持锁。"""
    with dl_lock(sid):
        ok, msg, path = download_pdf(sid, papers(), cfg)
    if ok:
        _record_download(sid, path)
    return {"id": sid, "ok": ok, "msg": msg, "path": path}


class Handler(BaseHTTPRequestHandler):
    server_version = "arxiv-digest/2.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # ---------- helpers ----------
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def _file(self, path, ctype="text/html; charset=utf-8"):
        try:
            with open(path, "rb") as f:
                self._send(200, f.read(), ctype)
        except FileNotFoundError:
            self._send(404, "not found", "text/plain; charset=utf-8")

    # ---------- GET ----------
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        path = u.path

        if path in ("/", "/index.html", "/digest"):
            f = q.get("f", [None])[0]
            target = os.path.join(OUT, f) if f else latest_digest()
            if not target or not os.path.exists(target):
                self._send(404, "尚无摘要页，请先运行 run_daily.py", "text/plain; charset=utf-8")
                return
            self._file(target)
            return

        if path == "/favorites":
            # 动态渲染，保证与 library.json 始终一致
            try:
                # 每到这一步都 reload：否则改了 build_report.py 的模板后，
                # 服务进程里缓存的旧模块会让收藏页一直吐旧版 HTML（只有重启才生效）。
                import importlib
                import build_report
                importlib.reload(build_report)
                html = build_report.build_favorites(pu.load_library())
                with open(os.path.join(OUT, "favorites.html"), "w", encoding="utf-8") as f:
                    f.write(html)
                # 必须显式声明 text/html，否则默认 application/json，浏览器会把页面当纯文本渲染
                self._send(200, html, "text/html; charset=utf-8")
            except Exception as e:  # noqa
                import traceback
                traceback.print_exc()
                self._file(os.path.join(OUT, "favorites.html"))
            return

        if path == "/profile":
            # 画像与设置页：类别 / 兴趣来源 / 下载目录 都在这里增删
            try:
                import importlib
                import build_report
                importlib.reload(build_report)
                html = build_report.build_profile_page()
                self._send(200, html, "text/html; charset=utf-8")
            except Exception:  # noqa
                import traceback
                traceback.print_exc()
                self._send(500, "画像页渲染失败，见服务日志", "text/plain; charset=utf-8")
            return

        if path == "/api/state":
            lib = pu.load_library()
            self._json({
                "favorites": list(lib["favorites"].keys()),
                "downloads": {k: v.get("path", "") for k, v in lib["downloads"].items()},
                "downvotes": list(lib.get("downvotes", {}).keys()),
                "download_dir": pu.load_config()["download_dir"],
                "categories": CZ.categories(),
                "category_names": {c: CZ.category_label(c) for c in CZ.categories()},
                "profile": profile_snapshot(),
            })
            return

        if path == "/api/customize":
            self._json(CZ.view())
            return

        if path == "/api/profile":
            self._json(profile_snapshot())
            return

        if path == "/api/library":
            self._json(pu.load_library())
            return

        if path.startswith("/files/"):
            name = os.path.basename(path[len("/files/"):])
            self._file(os.path.join(OUT, name),
                       "text/html; charset=utf-8" if name.endswith(".html")
                       else "application/octet-stream")
            return

        if path == "/archive":
            # 历史存档总览：按日期列出往期日报（数据来自 archive.db + output/archive/）
            try:
                import importlib
                import build_report
                importlib.reload(build_report)
                html = build_report.build_archive_page()
                with open(os.path.join(OUT, "archive.html"), "w", encoding="utf-8") as f:
                    f.write(html)
                self._send(200, html, "text/html; charset=utf-8")
            except Exception:  # noqa
                import traceback
                traceback.print_exc()
                self._file(os.path.join(OUT, "archive.html"))
            return

        if path.startswith("/archive/"):
            # 某一期的快照：output/archive/<date>.html，退化到 output/arxiv_digest_<date>.html
            date = os.path.basename(path[len("/archive/"):]).replace(".html", "")
            if not (len(date) == 8 and date.isdigit()):
                self._send(400, "日期格式应为 YYYYMMDD（例如 /archive/20260914）",
                           "text/plain; charset=utf-8")
                return
            try:
                import archive as AR
                f = AR.snapshot_path(date, "html")
            except Exception:  # noqa
                f = None
            if not f:
                self._send(404, "该日期没有存档", "text/plain; charset=utf-8")
                return
            self._file(f)
            return

        if path == "/api/archive/days":
            try:
                import archive as AR
                self._json({"issues": AR.list_issues(), "dates": AR.available_dates(),
                            "stats": AR.stats()})
            except Exception as e:  # noqa
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/ping":
            self._json({"ok": True})
            return

        if path == "/api/net_route":
            # 下载路由诊断：/api/download 报错时先看这里
            try:
                proxy, label = NR.ensure_route()
                self._json({"ok": bool(label), "route": label, "proxy": proxy,
                            "cache": NR.CACHE_PATH, "cands": len(NR.candidates()),
                            "last_failure": NR.last_failure()})
            except Exception as e:  # noqa
                self._json({"ok": False, "msg": str(e)}, 500)
            return

        self._send(404, "not found", "text/plain; charset=utf-8")

    # ---------- CORS 预检（允许以 file:// 打开的摘要页访问本地服务） ----------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---------- POST ----------
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        body = self._body()
        cfg = pu.load_config()

        try:
            if u.path == "/api/favorite":
                sid = pu.short_id(body.get("id", ""))
                if not sid:
                    return self._json({"ok": False, "msg": "缺少 id"}, 400)
                with _lib_lock:
                    add_favorite(sid, body.get("note"))
                    lib = pu.load_library()
                    lib["downvotes"].pop(sid, None)
                    pu.save_library(lib)
                    learn(sid, "favorite")
                return self._json({"ok": True, "favorited": True, "id": sid,
                                   "profile": profile_snapshot()})

            if u.path == "/api/unfavorite":
                sid = pu.short_id(body.get("id", ""))
                with _lib_lock:
                    lib = pu.load_library()
                    lib["favorites"].pop(sid, None)
                    pu.save_library(lib)
                    learn(sid, "unfavorite")
                return self._json({"ok": True, "favorited": False, "id": sid,
                                   "profile": profile_snapshot()})

            if u.path == "/api/downvote":
                sid = pu.short_id(body.get("id", ""))
                if not sid:
                    return self._json({"ok": False, "msg": "缺少 id"}, 400)
                with _lib_lock:
                    lib = pu.load_library()
                    p = papers().get(sid) or lib["favorites"].get(sid) or {}
                    rec = {"title": p.get("title", sid), "at": pu.now_str()}
                    if p.get("published"):
                        rec.update({k: v for k, v in pu.paper_meta(p).items() if v})
                    lib["downvotes"][sid] = rec
                    pu.save_library(lib)
                    learn(sid, "downvote")
                return self._json({"ok": True, "downvoted": True, "id": sid,
                                   "profile": profile_snapshot()})

            if u.path == "/api/undownvote":
                sid = pu.short_id(body.get("id", ""))
                with _lib_lock:
                    lib = pu.load_library()
                    lib["downvotes"].pop(sid, None)
                    pu.save_library(lib)
                    learn(sid, "undownvote")
                return self._json({"ok": True, "downvoted": False, "id": sid,
                                   "profile": profile_snapshot()})

            if u.path == "/api/event":
                sid = pu.short_id(body.get("id", ""))
                action = (body.get("action") or "").strip()
                if not sid or action not in ("abstract", "pdf", "open", "expand"):
                    return self._json({"ok": False, "msg": "参数不合法"}, 400)
                with _lib_lock:
                    learn(sid, action)
                return self._json({"ok": True, "id": sid, "action": action,
                                   "profile": profile_snapshot()})

            if u.path == "/api/download":
                sid = pu.short_id(body.get("id", ""))
                if not sid:
                    return self._json({"ok": False, "msg": "缺少 id"}, 400)
                # 取数（最长 90s 的网络 IO）只持有「本篇」的下载锁：
                # 别的论文的下载 / Downvote / 收藏 / Abstract 完全不受影响。
                with dl_lock(sid):
                    ok, msg, path = download_pdf(sid, papers(), cfg,
                                                 force=bool(body.get("force")))
                if ok:
                    _record_download(sid, path)
                return self._json({"ok": ok, "msg": msg, "path": path, "id": sid,
                                   "favorited": ok, "profile": profile_snapshot()})

            if u.path == "/api/download_all":
                ids = [x for x in (pu.short_id(x) for x in (body.get("ids") or [])) if x]
                # 批量下载不再一篇一篇排队：DL_WORKERS 路并发，明显缩短总耗时，
                # 又不会把 arXiv 打出频控。结果顺序与请求顺序一致。
                with ThreadPoolExecutor(max_workers=DL_WORKERS) as ex:
                    res = list(ex.map(lambda s: _download_one(s, cfg), ids))
                return self._json({"ok": True, "results": res,
                                   "n_ok": sum(1 for r in res if r["ok"]),
                                   "profile": profile_snapshot()})

            if u.path == "/api/owner":
                # 画像主来源（interests.json 的 owners）增 / 删 / 改
                op = (body.get("op") or "").strip()
                link = body.get("link_person") if "link_person" in body else None
                with _lib_lock:
                    if op == "add":
                        ok, msg, info = CZ.add_owner(body, link_person=True if link is None else bool(link))
                    elif op == "update":
                        ok, msg, info = CZ.update_owner(body.get("orig") or "", body,
                                                        link_person=link)
                    elif op == "remove":
                        ok, msg, info = CZ.remove_owner(body.get("name") or "")
                    else:
                        ok, msg, info = False, "未知操作 %s" % op, None
                return self._json({"ok": ok, "msg": msg, "info": info, "state": CZ.view()})

            if u.path == "/api/category":
                op = (body.get("op") or "add").strip()
                if op == "add":
                    ok, msg, info = CZ.add_category(body.get("cat", ""), body.get("name", ""))
                elif op == "remove":
                    ok, msg, info = CZ.remove_category(body.get("cat", ""))
                else:
                    ok, msg, info = False, "未知操作 %s" % op, None
                return self._json({"ok": ok, "msg": msg, "info": info, "state": CZ.view()})

            if u.path == "/api/config":
                ok, msg, info = CZ.set_download_dir(body.get("download_dir", ""))
                return self._json({"ok": ok, "msg": msg, "info": info, "state": CZ.view()})

            if u.path == "/api/source":
                op = (body.get("op") or "add").strip()
                if op == "add":
                    ok, msg, info = CZ.add_source(body.get("type", ""),
                                                  body.get("value", ""),
                                                  body.get("note", ""))
                elif op == "remove":
                    ok, msg, info = CZ.remove_source(body.get("sid", ""))
                elif op == "refresh":
                    ok, msg, info = CZ.refresh_all()
                elif op == "block":
                    ok, msg, info = CZ.block_keyword(body.get("kw", ""), True)
                elif op == "unblock":
                    ok, msg, info = CZ.block_keyword(body.get("kw", ""), False)
                else:
                    ok, msg, info = False, "未知操作 %s" % op, None
                return self._json({"ok": ok, "msg": msg, "info": info, "state": CZ.view()})

            if u.path == "/api/rebuild":
                ok, msg = rebuild_digest()
                return self._json({"ok": ok, "msg": msg, "state": CZ.view()})

            if u.path == "/api/open":
                sid = pu.short_id(body.get("id", ""))
                lib = pu.load_library()
                path = lib["downloads"].get(sid, {}).get("path", "")
                if not path:
                    ddir = cfg["download_dir"]
                    p = papers().get(sid) or {}
                    path = os.path.join(ddir, pu.build_filename(
                        sid, p.get("title", ""), (p.get("published") or "")[:4] or None))
                if not os.path.exists(path):
                    return self._json({"ok": False, "msg": "文件不存在：" + path})
                try:
                    os.startfile(path)  # noqa: S606
                except Exception:
                    subprocess.Popen(["explorer", path])
                return self._json({"ok": True, "path": path})

            if u.path == "/api/open_folder":
                d = body.get("dir") or cfg["download_dir"]
                ensure_dir(d)
                try:
                    os.startfile(d)  # noqa: S606
                except Exception:
                    subprocess.Popen(["explorer", d])
                return self._json({"ok": True, "dir": d})

        except Exception as e:  # noqa
            import traceback
            traceback.print_exc()
            return self._json({"ok": False, "msg": "服务端异常：%s" % e}, 500)

        self._json({"ok": False, "msg": "未知接口 " + u.path}, 404)


def main():
    cfg = pu.load_config()
    port = int(cfg.get("port", 8765))
    url = "http://127.0.0.1:%d" % port
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("serving %s  (download_dir=%s)" % (url, cfg["download_dir"]))
    print("digest:", latest_digest())
    if "--no-open" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
