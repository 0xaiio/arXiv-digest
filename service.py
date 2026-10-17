#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""业务用例层：把「做什么」与「怎么通过 HTTP 说」分开。

分层位置
--------
    routes.py   HTTP 语义（路径、请求体、状态码、响应体形状）
    service.py  ← 本层：收藏 / 下载 / 画像学习 / 重建（不认识 HTTP）
    paperutil / profile / netroute   数据与基础设施

为什么值得单独一层
------------------
重构前这些逻辑全部内联在 ``Handler.do_POST`` 的 if 链里，与 ``self._json()``
缠在一起。后果有两个，都是实际发生过的：

  * 想验证「下载一篇时另一篇的 Downvote 不被阻塞」必须**起一个真 HTTP 服务**，
    于是并发回归只能写成独立脚本（tools/concurrency_check.py），进不了 pytest；
  * 「收藏要连带清掉该篇的 Downvote」这类规则夹在 30 行 if 里，改一处要看半天。

现在这些函数都是普通的可调用对象：传数据进去、返回数据出来，可以被单测直接调用，
也可以被 ``server`` 替换成桩（并发回归就是这么做的）。

依赖方向：``service`` → ``paperutil`` / ``profile`` / ``netroute`` / ``paths``。
**不 import server、不 import customize**，因此不会与 HTTP 层形成循环依赖。
"""
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import netroute as NR
import paperutil as pu
import paths
import profile as PF


# ---------------------------------------------------------------- 并发模型
# 共享文件必须串行读-改-写，否则两个请求各自 load→改→save 会互相覆盖。
# 关键是**网络下载不持库锁**：
#   LIB_LOCK    只覆盖 library.json / profile_state.json 的读-改-写（毫秒级）
#   dl_lock(sid) 每篇论文一把，防止同一篇被连点两次时并发写同名 .part
# 由此，一篇 PDF 下到一半（最长 90s）时，另一篇的 Downvote / 收藏照常响应。
LIB_LOCK = threading.Lock()
DL_WORKERS = 3

_dl_locks = {}
_dl_locks_guard = threading.Lock()


def dl_lock(sid):
    """取某篇论文的下载锁（同一篇串行，不同篇并行）。"""
    with _dl_locks_guard:
        return _dl_locks.setdefault(sid, threading.Lock())


# ---------------------------------------------------------------- 文件小工具

def ensure_dir(d):
    os.makedirs(d, exist_ok=True)


def quiet_remove(p):
    """尽力删除临时文件；失败不算错误（.part 残留不影响正式文件）。"""
    try:
        os.remove(p)
    except OSError:
        pass


def latest_digest(out_dir):
    """out_dir 下日期最新的日报文件；没有则 None。"""
    if not os.path.isdir(out_dir):
        return None
    fs = [f for f in os.listdir(out_dir)
          if f.startswith("arxiv_digest_") and f.endswith(".html")]
    if not fs:
        return None
    fs.sort()
    return os.path.join(out_dir, fs[-1])


# ---------------------------------------------------------------- 论文索引缓存

class PaperIndex:
    """带 TTL 的论文索引缓存（抓取结果较大，避免每次请求都重新解析）。

    并发下载线程会同时要索引：加锁 + 双重检查，只让一个线程真正解析大 JSON，
    其余线程等它解析完直接复用缓存。
    """

    def __init__(self, loader=None, ttl=60):
        self._loader = loader or pu.load_papers
        self._ttl = ttl
        self._ts = 0.0
        self._data = {}
        self._lock = threading.Lock()

    def get(self, force=False):
        now = time.time()
        if force or now - self._ts > self._ttl:
            with self._lock:
                if force or time.time() - self._ts > self._ttl:
                    self._data = self._loader()
                    self._ts = time.time()
        return self._data

    def reset(self):
        """让下一次请求重新解析（重建摘要后必须调，否则读到旧索引）。"""
        self._ts = 0.0


PAPER_INDEX = PaperIndex()


def papers(force=False):
    """论文索引（短号 -> 元数据）。"""
    return PAPER_INDEX.get(force)


def reset_papers():
    PAPER_INDEX.reset()


# ---------------------------------------------------------------- 下载

def download_pdf(sid, papers_map, cfg, force=False):
    """下载到 cfg['download_dir']，返回 (ok, message, path)。

    取数一律走 ``netroute``（自动挑选可用路由：直连 / 环境代理 / 本机代理端口）。
    本机常被注入出口代理，它会对 arxiv 完成 CONNECT 却立刻掐断 TLS 流
    （SSL: UNEXPECTED_EOF_WHILE_READING），直连又被拒 —— 用默认 opener 必失败，
    这正是「点下载就报错」的根因。
    """
    p = (papers_map or {}).get(sid)
    if not p:
        # 也可能来自历史收藏 / 已下载记录
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


# ---------------------------------------------------------------- 库操作
# 注意：这些函数**不自己取论文元数据**，由调用方把 paper 传进来。
# 这样它们不依赖索引缓存，桩化索引时也不会悄悄读到真实数据。

def add_favorite(sid, note=None, paper=None):
    """写入收藏（幂等）。返回最新 lib。调用方负责持 LIB_LOCK。"""
    lib = pu.load_library()
    meta = pu.paper_meta(paper) if paper else {"id": sid, "title": sid}
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


def record_download(sid, path, title=""):
    """把「已下载」写进 library.json 并自动收藏（纯内存 + 落盘，毫秒级）。"""
    with LIB_LOCK:
        lib = pu.load_library()
        lib["downloads"][sid] = {"path": path, "at": pu.now_str(), "title": title}
        pu.save_library(lib)
        add_favorite(sid, paper={"id": sid, "title": title} if title else None)


def download_one(sid, cfg, papers_map, download_fn=None, learn_fn=None):
    """单篇下载的工作单元：取数不持库锁，落库才持锁。

    ``download_fn`` / ``learn_fn`` 由调用方注入（默认本模块的实现）。路由层传的是
    ``api.download_pdf`` 与 ``api.learn``，因此外部把 ``server.download_pdf`` 换成桩时，
    批量下载也会走桩 —— 与单篇下载保持一致；学习行为同理可被替换。
    """
    fn = download_fn or download_pdf
    with dl_lock(sid):
        ok, msg, path = fn(sid, papers_map, cfg)
    if ok:
        paper = (papers_map or {}).get(sid)
        record_download(sid, path, (paper or {}).get("title", ""))
        if learn_fn:
            learn_fn(sid, "download", paper)
    return {"id": sid, "ok": ok, "msg": msg, "path": path}


def download_many(ids, cfg, papers_map, workers=DL_WORKERS,
                  download_fn=None, learn_fn=None):
    """批量下载：workers 路并发，结果顺序与请求顺序一致。"""
    fn = download_fn or download_pdf
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(
            lambda s: download_one(s, cfg, papers_map, fn, learn_fn), ids))


# ---------------------------------------------------------------- 画像

def profile_snapshot():
    """前端重排所需的最小画像快照（主题 / 权重 / 关键词 / 论文罚分）。"""
    st = PF.load()
    return {
        "topics": [n for n, _ in PF.seed_weights()],
        "weights": [w for _, w in PF.weights(st)],
        "kw": {k: round(v, 3) for k, v in st.get("kw", {}).items() if abs(v) > 0.05},
        "pens": st.get("paper_bonus", {}),
    }


def learn(sid, action, paper=None):
    """记录行为并更新画像（论文元数据缺失时只记录计数）。"""
    try:
        PF.apply_event(sid, action, paper=paper)
    except Exception as e:  # noqa
        sys.stderr.write("learn %s %s failed: %s\n" % (sid, action, e))


# ---------------------------------------------------------------- 重建

REBUILD_STEPS = ("recommend.py", "build_report.py")
_rebuild_lock = threading.Lock()


def rebuild_digest(root=None, steps=REBUILD_STEPS, timeout=300):
    """重跑 recommend + build_report（不重新抓取）。返回 (ok, msg)。

    类别增删 / 兴趣来源变化改的是画像与配置，只有重算才会反映到摘要页。
    """
    root = root or paths.ROOT
    with _rebuild_lock:
        for name in steps:
            cmd = [sys.executable, os.path.join(root, name)]
            try:
                r = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=timeout)
            except subprocess.TimeoutExpired:
                return False, "%s 超时（>%ds）" % (name, timeout)
            except Exception as e:  # noqa
                return False, "%s 启动失败：%s" % (name, e)
            if r.returncode != 0:
                return False, "%s 失败：%s" % (name, (r.stderr or r.stdout or "")[-400:])
        reset_papers()      # 让下一次请求重新读论文索引
    return True, "已重算推荐并重建摘要页，回到摘要页刷新即可看到更新"


def open_path(path):
    """用系统默认程序打开文件 / 目录，返回 (ok, msg)。"""
    if not os.path.exists(path):
        return False, "文件不存在：" + path
    try:
        os.startfile(path)  # noqa: S606
    except Exception:
        try:
            subprocess.Popen(["explorer", path])
        except Exception as e:  # noqa
            return False, "无法打开：%s" % e
    return True, ""
