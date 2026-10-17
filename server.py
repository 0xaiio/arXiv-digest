#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地论文服务：为摘要页提供收藏 / 下载 / Downvote / 画像维护能力。

只监听 127.0.0.1:8765，不对外暴露。

分层（自下而上）
    paperutil / profile / netroute / archive  数据与基础设施
    service.py                                业务用例（不认识 HTTP）
    routes.py                                 HTTP 语义（路径 → 处理函数）
    server.py  ← 本文件：进程与 IO 装配（解析请求、写响应、启动服务）

本文件只做三件事：
  1. 装配运行时（导入各模块、把路径常量固定到脚本目录）；
  2. 把 ``routes`` 的 ``Reply`` 写到 socket 上；
  3. 启动 / 停止服务进程。

业务规则一律不写在这里 —— 见 service.py 与 routes.py 的模块说明。

对外接口
--------
GET
  /            当期日报（``?f=<文件名>`` 指定其它期）
  /favorites   收藏页（动态渲染）
  /profile     画像与设置页
  /archive     历史存档总览
  /archive/<YYYYMMDD>   某一期快照
  /files/<name>         output/ 下的静态文件
  /api/state /api/customize /api/profile /api/library
  /api/archive/days /api/net_route /api/ping
POST
  /api/favorite /api/unfavorite /api/downvote /api/undownvote /api/event
  /api/download /api/download_all
  /api/owner /api/category /api/config /api/source /api/rebuild
  /api/open /api/open_folder

并发模型
--------
ThreadingHTTPServer；库锁（LIB_LOCK）只保护 library.json / profile_state.json 的
读-改-写，网络下载不持库锁、每篇论文一把独立锁 —— 不同论文的下载与 Downvote
可同时执行。详见 service.py。
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# 防御：无论以何种方式被拉起（含 `start /b` 不继承 cwd 的情况），
# 都把进程工作目录固定到脚本自身所在目录，避免读到别处的 output/。
try:
    os.chdir(HERE)
except Exception:
    pass

import archive as AR  # noqa: E402
import customize as CZ  # noqa: E402
import netroute as NR  # noqa: E402
import paperutil as pu  # noqa: E402
import paths  # noqa: E402
import profile as PF  # noqa: E402
import routes  # noqa: E402
import service  # noqa: E402

OUT = pu.OUT
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) arxiv-digest/2.0"}
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------------- 运行时装配
# 这些名字从 service 取到本模块的命名空间后，就成了「可替换点」：
# 路由层通过 _Runtime 每次回查本模块，因此 `server.download_pdf = stub`
# （tools/concurrency_check.py 与集成测试都这么做）会立即生效。
LIB_LOCK = service.LIB_LOCK
_lib_lock = LIB_LOCK                  # 兼容旧名
DL_WORKERS = service.DL_WORKERS
dl_lock = service.dl_lock
papers = service.papers
reset_papers = service.reset_papers
download_pdf = service.download_pdf
download_many = service.download_many
add_favorite = service.add_favorite
record_download = service.record_download
profile_snapshot = service.profile_snapshot
learn = service.learn
rebuild_digest = service.rebuild_digest
ensure_dir = service.ensure_dir
quiet_remove = service.quiet_remove


def latest_digest():
    """当期日报路径（用本模块的 OUT，便于测试整体重定向）。"""
    return service.latest_digest(OUT)


def _record_download(sid, path):
    """兼容旧名：记录下载并从索引补标题。"""
    service.record_download(sid, path, (papers().get(sid) or {}).get("title", ""))


def service_open(path):
    """用系统默认程序打开路径（开放给路由层调用）。"""
    return service.open_path(path)


_build_lock = threading.Lock()
_build_mod = None


def digest_module(reload=True):
    """惰性加载 build_report，并按需 reload。

    为什么要 reload：模板已改为按 mtime 自动刷新（见 build_report.read_template），
    但**代码**改动仍需要重新执行模块体。以前是在每个页面路由里直接
    ``importlib.reload``，三处重复且无锁 —— 两个请求同时 reload 会互相打架。
    现在收敛到一处并加锁。
    """
    global _build_mod
    with _build_lock:
        if _build_mod is None:
            import build_report
            _build_mod = build_report
        elif reload:
            import importlib
            importlib.reload(_build_mod)
    return _build_mod


class _Runtime:
    """路由层能看到的全部能力（接口隔离 + 桩化支持）。

    ``ALLOWED`` 就是路由层与服务层之间的契约：加能力要显式登记，读不到的属性
    会抛 AttributeError 而不是悄悄拿到 None。每次访问都回查 server 模块，
    所以外部对模块属性的替换（测试与 tools 的桩）立即生效。
    """

    ALLOWED = frozenset({
        "OUT", "pu", "CZ", "NR", "AR", "PF", "LIB_LOCK",
        "papers", "reset_papers", "dl_lock", "download_pdf", "download_many",
        "add_favorite", "record_download", "profile_snapshot", "learn",
        "rebuild_digest", "latest_digest", "ensure_dir", "service_open",
        "digest_module",
    })
    __slots__ = ("_mod",)

    def __init__(self, mod):
        object.__setattr__(self, "_mod", mod)

    def __getattr__(self, name):
        if name not in _Runtime.ALLOWED:
            raise AttributeError("路由层无权访问 server.%s（如需开放，登记到 _Runtime.ALLOWED）"
                                 % name)
        return getattr(object.__getattribute__(self, "_mod"), name)


# ---------------------------------------------------------------- HTTP 编解码
class Handler(BaseHTTPRequestHandler):
    server_version = "arxiv-digest/2.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # ---------- 写响应 ----------
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

    def _reply(self, reply):
        """把 routes.Reply 落到 socket 上（含延迟读盘与 404 降级）。"""
        if reply.file_path:
            try:
                with open(reply.file_path, "rb") as f:
                    body = f.read()
            except FileNotFoundError:
                return self._send(404, "not found", "text/plain; charset=utf-8")
            return self._send(reply.status, body, reply.ctype)
        return self._send(reply.status, reply.body, reply.ctype)

    # ---------- 读请求 ----------
    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    # ---------- 分发 ----------
    def _dispatch(self, fn, req, arg=None):
        try:
            return fn(req, arg) if arg is not None else fn(req)
        except Exception as e:  # noqa
            import traceback
            traceback.print_exc()
            return routes.Reply.json({"ok": False, "msg": "服务端异常：%s" % e}, 500)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        fn, arg = routes.resolve_get(u.path)
        if not fn:
            return self._send(404, "not found", "text/plain; charset=utf-8")
        req = routes.Request(u.path, urllib.parse.parse_qs(u.query), {},
                             _Runtime(sys.modules[__name__]))
        return self._reply(self._dispatch(fn, req, arg))

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        fn = routes.resolve_post(u.path)
        if not fn:
            return self._json({"ok": False, "msg": "未知接口 " + u.path}, 404)
        req = routes.Request(u.path, {}, self._body(),
                             _Runtime(sys.modules[__name__]))
        return self._reply(self._dispatch(fn, req))

    # ---------- CORS 预检（允许以 file:// 打开的摘要页访问本地服务） ----------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()


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
