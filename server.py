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
  /api/archive/days /api/net_route /api/ping /api/datapacks
POST
  /api/favorite /api/unfavorite /api/downvote /api/undownvote /api/event
  /api/download /api/download_all
  /api/owner /api/category /api/config /api/source /api/rebuild
  /api/open /api/open_folder /api/preset

启动参数
  --port <端口>         指定起始端口（覆盖 config.json 的 port）；被占用时仍会自动顺延
  --no-open            不自动打开浏览器（定时任务 / 服务器上用）
  --open               强制自动打开浏览器（配置里关掉了也能临时打开）
  --preset <名字>       启动前先导入一份数据包（presets/<名字>/），失败不阻断启动
  --preset-force       允许覆盖本机已有的 config.json / interests.json（先备份）

端口顺延
--------
绑定从「config.json 的 port」开始；若该端口已被别的进程占用（或 bind 失败），
就向后逐个尝试（8765 → 8766 → … 最多 serveport.SCAN_LIMIT 个），成功后在日志里
打印**实际**地址，并把结果写进 ``output/server.json`` 供 run_daily 等后台调用方对账。
全部不可用时以退出码 2 明确报错，不会留下半启动的进程。

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
import arxiv_cats as AC  # noqa: E402
import customize as CZ  # noqa: E402
import datapack as DP  # noqa: E402
import netroute as NR  # noqa: E402
import paperutil as pu  # noqa: E402
import paths  # noqa: E402
import profile as PF  # noqa: E402
import routes  # noqa: E402
import serveport as SP  # noqa: E402
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
        "OUT", "pu", "CZ", "NR", "AR", "PF", "AC", "DP", "LIB_LOCK",
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


def argv_value(argv, flag):
    """从 `--flag v` 或 `--flag=v` 取值；没出现返回 None。"""
    for i, a in enumerate(argv):
        if a == flag:
            return argv[i + 1] if i + 1 < len(argv) else ""
        if a.startswith(flag + "="):
            return a[len(flag) + 1:]
    return None


def apply_preset_arg(argv):
    """``--preset <名字>``：启动前先导入一份数据包。

    失败**不阻断**启动：名字打错、或本机已有不同配置，都应该让服务起来，
    这样用户能从 /profile 的数据包面板看到原因（与 run_daily.py 的策略一致）。
    """
    name = argv_value(argv, "--preset")
    if not name:
        return True
    force = "--preset-force" in argv
    ok, msg, report = DP.import_pack(name, force=force)
    print("[preset] %s：%s" % (name, msg))
    for r in report:
        if r["action"] != "skipped":
            print("         %-22s %-9s %s %s"
                  % (r["file"], r["group"], r["action"], r["reason"]))
    if not ok:
        print("[preset] 提示：配置类文件默认不覆盖；确认要覆盖请加 --preset-force",
              file=sys.stderr)
    return ok


class PortUnavailable(RuntimeError):
    """起始端口起连续若干端口都不可用（或已越过 65535）。"""


def bind_server(start, attempts=2, host=SP.HOST):
    """从 `start` 起找一个可用端口并完成绑定，返回 ``(srv, port, tried)``。

    为什么不是「探测一次 → bind 一次」：探测与 bind 之间仍有窗口，可能被别的进程
    抢走。所以失败再重来一轮（起点顺延到刚才那个端口之后），而不是直接报错退出。
    两轮都失败基本只剩「这段端口真的都不能用」，交给调用方明确报错。
    """
    want = start
    tried = []
    for _ in range(max(1, attempts)):
        port, round_tried = SP.find_free_port(want)
        tried += round_tried
        if not port:
            break
        try:
            return ThreadingHTTPServer((host, port), Handler), port, tried
        except OSError as e:
            print("[port] %d 绑定失败（%s），继续向后找" % (port, e), file=sys.stderr)
            want = port + 1
    raise PortUnavailable(
        "从 %d 起连续 %d 个端口都不可用（尝试过 %s）"
        % (want, len(tried) or 1,
           ("%d–%d" % (tried[0], tried[-1])) if tried else "（无）"))


def announce(port, want, tried, cfg):
    """启动日志：**明确**给出最终地址，顺延时说明原因与尝试范围。

    这行日志是排障的第一入口（run_daily 的 server.log、双击 bat 的窗口都看它），
    所以地址用固定前缀 `serving`，便于脚本 grep。
    """
    url = SP.url_for(port)
    print("serving %s  (download_dir=%s)" % (url, cfg.get("download_dir", "")))
    if port == want:
        print("port: %d（config.json / --port 的期望值，未被占用）" % port)
    else:
        print("port: %d（%d 已被占用，已向后顺延；尝试过 %s%s）"
              % (port, want,
                 ("%d–%d" % (tried[0], tried[-1])) if tried else "（无）",
                 ("，共 %d 个" % len(tried)) if tried else ""))


def run(argv=None):
    """启动服务的完整流程；返回进程退出码（0 正常，2 端口不可用）。

    顺序刻意如此：先定端口 → 再打日志 → 再落盘 server.json → 最后才开浏览器。
    这样"日志里的地址"、"页面里的端口"、"server.json 里的端口"永远是同一个值。
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    apply_preset_arg(argv)
    cfg = pu.load_config()
    want = SP.valid_port(argv_value(argv, "--port")) or SP.configured_port(cfg)
    try:
        srv, port, tried = bind_server(want)
    except PortUnavailable as e:
        print("[port] %s" % e, file=sys.stderr)
        print("[port] 请把 config.json 的 port 改成空闲端口，或用 --port 指定",
              file=sys.stderr)
        return 2

    pu.set_runtime_port(port)      # 让日志、server.json 与页面里的端口是同一个值
    url = SP.url_for(port)
    announce(port, want, tried, cfg)
    print("digest:", latest_digest())
    if SP.write_runtime_info(os.path.join(OUT, "server.json"), port) is None:
        print("[warn] 无法写 output/server.json（不影响服务）", file=sys.stderr)

    if SP.browser_enabled(argv, cfg):
        try:
            SP.open_browser(url)
        except Exception as e:  # noqa: BLE001 —— 开浏览器只是便利功能
            print("[browser] 自动打开失败（%s），请手动访问 %s" % (e, url))
    else:
        print("[browser] 已关闭自动打开（--no-open / config.open_browser=false）")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        try:
            srv.server_close()
        except Exception:  # noqa: BLE001
            pass
    return 0


def main():
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
