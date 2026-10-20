#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP 路由层：路径 → 处理函数，一张表注册。

重构动机（开闭原则）
--------------------
原先 ``Handler.do_GET`` 与 ``do_POST`` 是两个各 130 / 170 行的 if 链。加一个接口
要往中间插一段，且必须读懂上下文才知道该放哪；路由清单也无法被程序读取，
只能靠 grep。

现在：
    @get("/api/ping")
    def ping(req): ...

新增接口 = 加一个装饰器函数，**不用改 Handler、不用改已有路由**。

职责边界
--------
本模块只处理 HTTP 语义：路径匹配、参数校验、状态码、响应体形状。
业务动作全部委托给 ``req.api``（由 server 注入的运行时），因此：

  * 路由处理器可以脱离网络单测（构造一个假 api + 假 Request 即可）；
  * ``server.download_pdf = stub`` 这类外部替换仍然生效 —— api 每次访问都回查
    服务模块，不做 import 期的名字绑定（tools/concurrency_check.py 依赖这点）。

响应用 ``Reply`` 描述，不直接写 socket：``Reply.file(path)`` 只带路径，由 Handler
去读盘，于是路由单测不需要准备真实文件。
"""
import json
import os


class Reply:
    """一次响应的完整描述（状态码 / 体 / 类型 / 待读文件）。"""

    __slots__ = ("status", "body", "ctype", "file_path")

    def __init__(self, body=b"", status=200, ctype="application/json; charset=utf-8",
                 file_path=None):
        self.status = status
        self.body = body
        self.ctype = ctype
        self.file_path = file_path

    @classmethod
    def json(cls, obj, status=200):
        return cls(json.dumps(obj, ensure_ascii=False), status)

    @classmethod
    def text(cls, s, status=200):
        return cls(s, status, "text/plain; charset=utf-8")

    @classmethod
    def html(cls, s, status=200):
        return cls(s, status, "text/html; charset=utf-8")

    @classmethod
    def file(cls, path, ctype="text/html; charset=utf-8"):
        """延迟读盘：文件不存在时由 Handler 转成 404。"""
        return cls(b"", 200, ctype, file_path=path)


class Request:
    """一次请求的只读视图。``api`` 是 server 模块（见模块文档）。"""

    __slots__ = ("path", "query", "body", "api")

    def __init__(self, path, query, body, api):
        self.path = path
        self.query = query or {}
        self.body = body or {}
        self.api = api

    # ---- 常用取值（把「缺 id 就 400」这类重复判断收敛到一处） ----
    def sid(self):
        return self.api.pu.short_id(self.body.get("id", ""))

    def arg(self, name, default=""):
        return self.body.get(name, default)

    def q(self, name, default=None):
        return self.query.get(name, [default])[0]

    def op(self, default="add"):
        return (self.body.get("op") or default).strip()


# ---------------------------------------------------------------- 路由表
_GET_EXACT = {}
_GET_PREFIX = []          # [(prefix, handler)]，按前缀长度降序匹配
_POST = {}


def get(path):
    """注册精确匹配的 GET 路由。"""
    def deco(fn):
        _GET_EXACT[path] = fn
        return fn
    return deco


def get_prefix(prefix):
    """注册前缀匹配的 GET 路由（如 /files/）。"""
    def deco(fn):
        _GET_PREFIX.append((prefix, fn))
        _GET_PREFIX.sort(key=lambda kv: -len(kv[0]))
        return fn
    return deco


def post(path):
    """注册 POST 路由。"""
    def deco(fn):
        _POST[path] = fn
        return fn
    return deco


def resolve_get(path):
    """返回 (handler, 参数)；未匹配返回 (None, None)。

    精确优先、前缀次之 —— 因此 ``/archive`` 不会被 ``/archive/`` 抢走。
    """
    fn = _GET_EXACT.get(path)
    if fn:
        return fn, None
    for prefix, fn in _GET_PREFIX:
        if path.startswith(prefix):
            return fn, path[len(prefix):]
    return None, None


def resolve_post(path):
    return _POST.get(path)


def table():
    """路由清单（供文档生成与「路由完整性」测试用）。"""
    return {
        "get": sorted(_GET_EXACT),
        "get_prefix": [p for p, _ in _GET_PREFIX],
        "post": sorted(_POST),
    }


# ================================================================ 页面
@get("/")
@get("/index.html")
@get("/digest")
def digest_page(req):
    """当期日报。``?f=<文件名>`` 可指定其它期；默认取日期最新的一份。

    尚无日报时不算错误：通用版首次运行还没选分类，这里给「去选类别」的引导页；
    已选分类但还没抓取，才提示去跑 run_daily.py。
    """
    f = req.q("f")
    target = os.path.join(req.api.OUT, f) if f else req.api.latest_digest()
    if target and os.path.exists(target):
        return Reply.file(target)
    try:
        cats = req.api.CZ.categories()
    except Exception:  # noqa
        cats = None
    if cats == []:
        # 通用版首次运行：还没选分类 → 引导页（比一句 404 文本有用得多）
        try:
            return Reply.html(req.api.digest_module().build_welcome())
        except Exception:  # noqa
            pass
    return Reply.text("尚无摘要页，请先运行 run_daily.py", 404)


@get("/favorites")
def favorites_page(req):
    """收藏页：每次动态渲染，保证与 library.json 一致。"""
    try:
        html = req.api.digest_module().build_favorites(req.api.pu.load_library())
        _write_side_effect(req.api.OUT, "favorites.html", html)
        return Reply.html(html)
    except Exception:  # noqa
        import traceback
        traceback.print_exc()
        return Reply.file(os.path.join(req.api.OUT, "favorites.html"))


@get("/profile")
def profile_page(req):
    """画像与设置页：类别 / 兴趣来源 / 画像主来源 / 下载目录都在这里增删。"""
    try:
        return Reply.html(req.api.digest_module().build_profile_page())
    except Exception:  # noqa
        import traceback
        traceback.print_exc()
        return Reply.text("画像页渲染失败，见服务日志", 500)


@get("/archive")
def archive_page(req):
    """历史存档总览：按日期列出往期日报。"""
    try:
        html = req.api.digest_module().build_archive_page()
        _write_side_effect(req.api.OUT, "archive.html", html)
        return Reply.html(html)
    except Exception:  # noqa
        import traceback
        traceback.print_exc()
        return Reply.file(os.path.join(req.api.OUT, "archive.html"))


@get_prefix("/archive/")
def archive_snapshot(req, date_part):
    """某一期的快照：output/archive/<date>.html（退化到当期文件）。"""
    date = os.path.basename(date_part).replace(".html", "")
    if not (len(date) == 8 and date.isdigit()):
        return Reply.text("日期格式应为 YYYYMMDD（例如 /archive/20260914）", 400)
    try:
        f = req.api.AR.snapshot_path(date, "html")
    except Exception:  # noqa
        f = None
    if not f:
        return Reply.text("该日期没有存档", 404)
    return Reply.file(f)


@get_prefix("/files/")
def output_file(req, name_part):
    """output/ 下的静态文件（只允许一层文件名，防目录穿越）。"""
    name = os.path.basename(name_part)
    ctype = ("text/html; charset=utf-8" if name.endswith(".html")
             else "application/octet-stream")
    return Reply.file(os.path.join(req.api.OUT, name), ctype)


def _write_side_effect(out_dir, name, text):
    """把渲染结果落一份到 output/（供 file:// 直接打开，历史行为）。失败不影响响应。"""
    try:
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:  # noqa
        pass


# ================================================================ 只读 API
@get("/api/ping")
def ping(req):
    return Reply.json({"ok": True})


@get("/api/state")
def state(req):
    """前端首屏需要的全部状态（收藏 / 下载 / Downvote / 目录 / 分类 / 画像）。"""
    api = req.api
    lib = api.pu.load_library()
    cats = api.CZ.categories()
    return Reply.json({
        "favorites": list(lib["favorites"].keys()),
        "downloads": {k: v.get("path", "") for k, v in lib["downloads"].items()},
        "downvotes": list(lib.get("downvotes", {}).keys()),
        "download_dir": api.pu.load_config()["download_dir"],
        "categories": cats,
        "category_names": {c: api.CZ.category_label(c) for c in cats},
        "profile": api.profile_snapshot(),
    })


@get("/api/customize")
def customize_state(req):
    return Reply.json(req.api.CZ.view())


@get("/api/arxiv_categories")
def arxiv_categories(req):
    """arXiv 官方分类全表（两个联动下拉框的数据源）。

    单独成接口而不是写死在前端：分类表是**数据**，随 arXiv 增删而变；
    前端只负责展示与搜索，避免一份 JSON 在 JS 与 Python 里各存一份、互相漂移。
    """
    return Reply.json(req.api.AC.taxonomy())


@get("/api/profile")
def profile_state(req):
    return Reply.json(req.api.profile_snapshot())


@get("/api/library")
def library(req):
    return Reply.json(req.api.pu.load_library())


@get("/api/datapacks")
def datapacks(req):
    """可用数据包 + 本机个人数据清单。

    只返回**形状**（包名 / 文件清单 / 体积），不返回包的标题、描述与任何内容 ——
    那句描述往往就是作者的类别选择与研究方向，属要隔离的内容。
    规则见 docs/architecture/data-isolation.md §六。
    """
    DP = req.api.DP
    return Reply.json({"packs": DP.public_view(),
                       "state": DP.state(),
                       "groups": list(DP.GROUP_ORDER),
                       "defaults": list(DP.DEFAULT_IMPORT)})


@get("/api/archive/days")
def archive_days(req):
    try:
        AR = req.api.AR
        return Reply.json({"issues": AR.list_issues(), "dates": AR.available_dates(),
                           "stats": AR.stats()})
    except Exception as e:  # noqa
        return Reply.json({"error": str(e)}, 500)


@get("/api/net_route")
def net_route(req):
    """下载路由诊断：/api/download 报错时先看这里。"""
    try:
        NR = req.api.NR
        proxy, label = NR.ensure_route()
        return Reply.json({"ok": bool(label), "route": label, "proxy": proxy,
                           "cache": NR.CACHE_PATH, "cands": len(NR.candidates()),
                           "last_failure": NR.last_failure()})
    except Exception as e:  # noqa
        return Reply.json({"ok": False, "msg": str(e)}, 500)


# ================================================================ 写操作
@post("/api/favorite")
def favorite(req):
    api, sid = req.api, req.sid()
    if not sid:
        return Reply.json({"ok": False, "msg": "缺少 id"}, 400)
    with api.LIB_LOCK:
        api.add_favorite(sid, req.arg("note") or None, api.papers().get(sid))
        lib = api.pu.load_library()
        lib["downvotes"].pop(sid, None)     # 收藏 = 正面信号，撤掉此前的否定
        api.pu.save_library(lib)
        api.learn(sid, "favorite", api.papers().get(sid))
    return Reply.json({"ok": True, "favorited": True, "id": sid,
                       "profile": api.profile_snapshot()})


@post("/api/unfavorite")
def unfavorite(req):
    api, sid = req.api, req.sid()
    with api.LIB_LOCK:
        lib = api.pu.load_library()
        lib["favorites"].pop(sid, None)
        api.pu.save_library(lib)
        api.learn(sid, "unfavorite", api.papers().get(sid))
    return Reply.json({"ok": True, "favorited": False, "id": sid,
                       "profile": api.profile_snapshot()})


@post("/api/downvote")
def downvote(req):
    api, sid = req.api, req.sid()
    if not sid:
        return Reply.json({"ok": False, "msg": "缺少 id"}, 400)
    with api.LIB_LOCK:
        lib = api.pu.load_library()
        p = api.papers().get(sid) or lib["favorites"].get(sid) or {}
        rec = {"title": p.get("title", sid), "at": api.pu.now_str()}
        if p.get("published"):
            rec.update({k: v for k, v in api.pu.paper_meta(p).items() if v})
        lib["downvotes"][sid] = rec
        api.pu.save_library(lib)
        api.learn(sid, "downvote", p or None)
    return Reply.json({"ok": True, "downvoted": True, "id": sid,
                       "profile": api.profile_snapshot()})


@post("/api/undownvote")
def undownvote(req):
    api, sid = req.api, req.sid()
    with api.LIB_LOCK:
        lib = api.pu.load_library()
        lib["downvotes"].pop(sid, None)
        api.pu.save_library(lib)
        api.learn(sid, "undownvote", api.papers().get(sid))
    return Reply.json({"ok": True, "downvoted": False, "id": sid,
                       "profile": api.profile_snapshot()})


@post("/api/event")
def event(req):
    api, sid = req.api, req.sid()
    action = (req.arg("action") or "").strip()
    if not sid or action not in ("abstract", "pdf", "open", "expand"):
        return Reply.json({"ok": False, "msg": "参数不合法"}, 400)
    with api.LIB_LOCK:
        api.learn(sid, action, api.papers().get(sid))
    return Reply.json({"ok": True, "id": sid, "action": action,
                       "profile": api.profile_snapshot()})


@post("/api/download")
def download(req):
    api, sid = req.api, req.sid()
    if not sid:
        return Reply.json({"ok": False, "msg": "缺少 id"}, 400)
    # 取数（最长 90s 的网络 IO）只持有「本篇」的下载锁：
    # 别的论文的下载 / Downvote / 收藏 / Abstract 完全不受影响。
    with api.dl_lock(sid):
        ok, msg, path = api.download_pdf(sid, api.papers(), api.pu.load_config(),
                                        force=bool(req.arg("force")))
    if ok:
        api.record_download(sid, path,
                            (api.papers().get(sid) or {}).get("title", ""))
        api.learn(sid, "download", api.papers().get(sid))
    return Reply.json({"ok": ok, "msg": msg, "path": path, "id": sid,
                       "favorited": ok, "profile": api.profile_snapshot()})


@post("/api/download_all")
def download_all(req):
    api = req.api
    ids = [x for x in (api.pu.short_id(x) for x in (req.arg("ids") or [])) if x]
    # 并发而非排队：总耗时≈单篇，结果顺序与请求顺序一致。
    # 显式把 api.download_pdf 注入下去，桩化单篇下载时批量下载同步生效。
    res = api.download_many(ids, api.pu.load_config(), api.papers(),
                            download_fn=api.download_pdf, learn_fn=api.learn)
    return Reply.json({"ok": True, "results": res,
                       "n_ok": sum(1 for r in res if r["ok"]),
                       "profile": api.profile_snapshot()})


@post("/api/owner")
def owner(req):
    """画像主来源（interests.json 的 owners）增 / 删 / 改。"""
    api = req.api
    op = req.op()
    link = req.body.get("link_person") if "link_person" in req.body else None
    with api.LIB_LOCK:
        if op == "add":
            ok, msg, info = api.CZ.add_owner(
                req.body, link_person=True if link is None else bool(link))
        elif op == "update":
            ok, msg, info = api.CZ.update_owner(req.arg("orig") or "", req.body,
                                                link_person=link)
        elif op == "remove":
            ok, msg, info = api.CZ.remove_owner(req.arg("name") or "")
        else:
            ok, msg, info = False, "未知操作 %s" % op, None
    return Reply.json({"ok": ok, "msg": msg, "info": info, "state": api.CZ.view()})


def _as_list(v):
    """把请求体里的「列表」字段收敛成 list。

    前端正常发的是数组，但手写 curl / 老客户端可能传字符串。直接迭代字符串会
    逐字符当成分类号，错误信息会变成一串莫名其妙的单字 —— 这里一句归一化掉。
    """
    if v is None or v == "":
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.replace("，", ",").split(",") if x.strip()]
    return list(v) if isinstance(v, (list, tuple)) else [v]


@post("/api/category")
def category(req):
    """类别增删改排序。

    op:
      add       单个添加（cat / name）
      add_many  批量添加（cats[]）—— 界面多选下拉一次提交
      remove    删除单个（cat）
      reorder   拖拽排序（order[]，必须是当前集合的一个排列）
      set       整体替换（cats[]，空数组表示清空）—— 导入预设 / 重建列表
    """
    api, op = req.api, req.op()
    if op == "add":
        ok, msg, info = api.CZ.add_category(req.arg("cat", ""), req.arg("name", ""))
    elif op == "add_many":
        ok, msg, info = api.CZ.add_categories(_as_list(req.arg("cats")))
    elif op == "remove":
        ok, msg, info = api.CZ.remove_category(req.arg("cat", ""))
    elif op == "reorder":
        ok, msg, info = api.CZ.reorder_categories(_as_list(req.arg("order")))
    elif op == "set":
        ok, msg, info = api.CZ.set_categories(_as_list(req.arg("cats")),
                                             allow_empty=bool(req.arg("allow_empty")))
    else:
        ok, msg, info = False, "未知操作 %s" % op, None
    return Reply.json({"ok": ok, "msg": msg, "info": info, "state": api.CZ.view()})


@post("/api/config")
def config(req):
    api = req.api
    ok, msg, info = api.CZ.set_download_dir(req.arg("download_dir", ""))
    return Reply.json({"ok": ok, "msg": msg, "info": info, "state": api.CZ.view()})


# 来源操作是多分支的，用表驱动替代 if-elif 链：
# 新操作 = 一行；每个分支只负责「把 body 里的字段取出来交给 customize」。
_SOURCE_OPS = {
    "add": lambda api, b: api.CZ.add_source(b.get("type", ""), b.get("value", ""),
                                            b.get("note", "")),
    "remove": lambda api, b: api.CZ.remove_source(b.get("sid", "")),
    "refresh": lambda api, b: api.CZ.refresh_all(),
    "block": lambda api, b: api.CZ.block_keyword(b.get("kw", ""), True),
    "unblock": lambda api, b: api.CZ.block_keyword(b.get("kw", ""), False),
}


@post("/api/source")
def source(req):
    api, op = req.api, req.op()
    fn = _SOURCE_OPS.get(op)
    if not fn:
        return Reply.json({"ok": False, "msg": "未知操作 %s" % op, "info": None,
                           "state": api.CZ.view()})
    ok, msg, info = fn(api, req.body)
    return Reply.json({"ok": ok, "msg": msg, "info": info, "state": api.CZ.view()})


@post("/api/rebuild")
def rebuild(req):
    api = req.api
    ok, msg = api.rebuild_digest()
    return Reply.json({"ok": ok, "msg": msg, "state": api.CZ.view()})


@post("/api/preset")
def preset(req):
    """导入一份数据包（`presets/<名字>/`）。

    op:
      import  导入（默认 core + usage + notes）；force=true 才覆盖 core 文件
      export  把本机设置导出成包（界面上不提供入口，保留给脚本与调试）

    语义（合并 / 拒绝 / 备份）全在 ``datapack.import_pack``，这里只做参数归一化与状态码：
    拒绝导入返回 400，界面据 ``ok`` 弹出逐文件原因。
    """
    api, op = req.api, req.op("import")
    name = (req.arg("name") or "").strip()
    if not name:
        return Reply.json({"ok": False, "msg": "缺少数据包名称", "state": api.CZ.view()}, 400)
    groups = req.arg("groups") or None
    if isinstance(groups, str):
        groups = [g.strip() for g in groups.replace("，", ",").split(",") if g.strip()]
    if op == "import":
        ok, msg, report = api.DP.import_pack(name, groups=groups,
                                            force=bool(req.arg("force")))
        return Reply.json({"ok": ok, "msg": msg, "report": report,
                           "state": api.CZ.view()}, 200 if ok else 400)
    if op == "export":
        ok, msg, report = api.DP.export_pack(name, groups=groups)
        return Reply.json({"ok": ok, "msg": msg, "report": report,
                           "state": api.CZ.view()}, 200 if ok else 400)
    return Reply.json({"ok": False, "msg": "未知操作 %s" % op,
                       "state": api.CZ.view()}, 400)


@post("/api/open")
def open_pdf(req):
    """用系统默认阅读器打开已下载的 PDF（找不到就按命名规则推断路径）。"""
    api, sid = req.api, req.sid()
    lib = api.pu.load_library()
    path = lib["downloads"].get(sid, {}).get("path", "")
    if not path:
        cfg = api.pu.load_config()
        p = api.papers().get(sid) or {}
        path = os.path.join(cfg["download_dir"], api.pu.build_filename(
            sid, p.get("title", ""), (p.get("published") or "")[:4] or None))
    ok, msg = api.service_open(path)
    if not ok:
        return Reply.json({"ok": False, "msg": msg})
    return Reply.json({"ok": True, "path": path})


@post("/api/open_folder")
def open_folder(req):
    api = req.api
    d = req.arg("dir") or api.pu.load_config()["download_dir"]
    api.ensure_dir(d)
    api.service_open(d)
    return Reply.json({"ok": True, "dir": d})
