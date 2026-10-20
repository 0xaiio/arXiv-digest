# -*- coding: utf-8 -*-
"""routes：路由表、响应描述与运行时契约。

没有 HTTP socket 参与 —— 这正是不把业务写在 Handler 里的收益：
路由处理器的分支可以用普通断言覆盖。
"""
import json
import threading
import types

import pytest

import paperutil as pu
import routes as RT
import server as S

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------ 路由表

EXPECTED_GET = {
    "/", "/index.html", "/digest", "/favorites", "/profile", "/archive",
    "/api/state", "/api/customize", "/api/profile", "/api/library",
    "/api/archive/days", "/api/net_route", "/api/ping",
    "/api/arxiv_categories",
}
EXPECTED_PREFIX = {"/archive/", "/files/"}
EXPECTED_POST = {
    "/api/favorite", "/api/unfavorite", "/api/downvote", "/api/undownvote",
    "/api/event", "/api/download", "/api/download_all", "/api/owner",
    "/api/category", "/api/config", "/api/source", "/api/rebuild",
    "/api/open", "/api/open_folder",
}


def test_route_table_covers_every_documented_endpoint():
    """路由被误删/改名会在这里直接红，而不是等前端点了没反应。"""
    t = RT.table()
    assert set(t["get"]) == EXPECTED_GET
    assert set(t["get_prefix"]) == EXPECTED_PREFIX
    assert set(t["post"]) == EXPECTED_POST


def test_every_route_is_callable():
    for path in RT.table()["get"]:
        assert callable(RT.resolve_get(path)[0]), path
    for path in RT.table()["post"]:
        assert callable(RT.resolve_post(path)), path


def test_exact_route_wins_over_prefix():
    """/archive 必须命中总览页，不能被 /archive/ 前缀抢走。"""
    fn, arg = RT.resolve_get("/archive")
    assert fn is RT.archive_page and arg is None


def test_prefix_route_returns_remainder():
    fn, arg = RT.resolve_get("/archive/20261016")
    assert fn is RT.archive_snapshot and arg == "20261016"
    fn, arg = RT.resolve_get("/files/foo.html")
    assert fn is RT.output_file and arg == "foo.html"


def test_longer_prefix_wins_when_nested():
    """/files/ 与 /archive/ 互不干扰；这是排序规则的回归保护。"""
    assert RT.resolve_get("/files/x")[0] is RT.output_file
    assert RT.resolve_get("/archive/x")[0] is RT.archive_snapshot


def test_unknown_paths_do_not_match():
    assert RT.resolve_get("/nope") == (None, None)
    assert RT.resolve_post("/nope") is None


# ------------------------------------------------------------------ Reply

def test_reply_json_encodes_unicode():
    r = RT.Reply.json({"msg": "中文"})
    assert r.status == 200 and "中文" in r.body
    assert r.ctype.startswith("application/json")


def test_reply_text_and_html_set_ctype():
    assert RT.Reply.text("x").ctype.startswith("text/plain")
    assert RT.Reply.html("<b>x</b>").ctype.startswith("text/html")


def test_reply_file_defers_body():
    r = RT.Reply.file("/tmp/a.html")
    assert r.file_path == "/tmp/a.html" and r.body == b""


def test_reply_status_can_be_overridden():
    assert RT.Reply.json({"ok": False}, 400).status == 400


# ------------------------------------------------------------------ Request

class _FakePu(types.SimpleNamespace):
    pass


def _req(body=None, query=None, api=None):
    return RT.Request("/x", query or {}, body or {}, api)


def test_request_sid_normalises_and_defaults_empty():
    req = _req({"id": "arXiv:2609.09742v2"}, api=types.SimpleNamespace(pu=pu))
    assert req.sid() == "2609.09742"
    assert _req(api=types.SimpleNamespace(pu=pu)).sid() == ""


def test_request_arg_and_query_defaults():
    req = _req({"a": 1}, {"f": ["x.html"]})
    assert req.arg("a") == 1
    assert req.arg("missing") == ""
    assert req.q("f") == "x.html"
    assert req.q("missing") is None


def test_request_op_strips_and_defaults():
    assert _req({"op": "  remove  "}).op() == "remove"
    assert _req().op() == "add"


# ------------------------------------------------------------------ 运行时契约

def test_runtime_rejects_unlisted_attributes():
    """接口隔离：路由层不能顺手摸到 server 的内部成员。"""
    rt = S._Runtime(S)
    with pytest.raises(AttributeError) as ei:
        rt.Handler
    assert "无权访问" in str(ei.value)


def test_runtime_exposes_declared_capabilities():
    rt = S._Runtime(S)
    for name in S._Runtime.ALLOWED:
        assert getattr(rt, name) is not None, name


def test_runtime_forwards_dynamically_so_patching_works(monkeypatch):
    """桩化契约：替换 server 模块属性后，路由层立刻看到新对象。

    tools/concurrency_check.py 与若干集成测试依赖这一点（不这么做就会去真下载）。
    """
    stub = lambda *a, **k: (True, "stub", "/p/x.pdf")     # noqa: E731
    monkeypatch.setattr(S, "download_pdf", stub)
    assert S._Runtime(S).download_pdf is stub


def test_handlers_receive_the_server_module_in_real_dispatch():
    """Handler 传给路由的 api 必须是 server 模块本身（否则桩化失效）。

    这里不启 socket，只用 Handler 的同一条构造路径：``_Runtime(sys.modules[__name__])``。
    """
    api = S._Runtime(S)
    req = RT.Request("/api/ping", {}, {}, api)
    assert api.__getattr__("pu") is pu
    assert req.api is api


# ------------------------------------------------------------------ 处理器分支（纯校验路径）

def _fake_api(**over):
    """最小 api：只提供被校验路径用到的能力（不读写真实数据）。"""
    base = dict(
        LIB_LOCK=threading.Lock(),
        pu=types.SimpleNamespace(short_id=pu.short_id,
                                 load_library=lambda: {"favorites": {}, "downloads": {},
                                                       "downvotes": {}},
                                 load_config=lambda: {"download_dir": "p"},
                                 save_library=lambda lib: None,
                                 now_str=lambda: "now",
                                 paper_meta=lambda p: {}),
        CZ=types.SimpleNamespace(view=lambda: {"ok": "view"}),
        learn=lambda *a, **k: None,
        papers=lambda force=False: {},
        profile_snapshot=lambda: {},
    )
    base.update(over)
    return types.SimpleNamespace(**base)


@pytest.mark.parametrize("fn", [RT.favorite, RT.downvote, RT.download])
def test_id_required_endpoints_return_400(fn):
    r = fn(_req({}, api=_fake_api()))
    assert r.status == 400 and "缺少 id" in r.body


def test_event_rejects_unknown_action():
    r = RT.event(_req({"id": "2609.1", "action": "delete"}, api=_fake_api()))
    assert r.status == 400 and "参数不合法" in r.body


def test_event_accepts_whitelisted_action():
    r = RT.event(_req({"id": "2609.1", "action": "abstract"}, api=_fake_api()))
    assert r.status == 200 and '"ok": true' in r.body


def test_source_rejects_unknown_op():
    r = RT.source(_req({"op": "explode"}, api=_fake_api()))
    assert r.status == 200
    assert '"ok": false' in r.body and "未知操作" in r.body


def test_owner_rejects_unknown_op():
    r = RT.owner(_req({"op": "explode"}, api=_fake_api()))
    assert '"ok": false' in r.body and "未知操作" in r.body


def test_source_ops_table_covers_all_documented_operations():
    assert set(RT._SOURCE_OPS) == {"add", "remove", "refresh", "block", "unblock"}


# ------------------------------------------------------------------ 分类接口

def test_arxiv_categories_endpoint_returns_full_taxonomy():
    """分类表要能被前端完整取到（两个联动下拉框的数据源）。"""
    r = RT.arxiv_categories(_req(api=S._Runtime(S)))
    d = json.loads(r.body)
    assert d["total"] >= 150
    assert {a["id"] for a in d["archives"]} >= {"cs", "math", "stat", "quant-ph"}
    assert d["version"] and d["source"].startswith("https://arxiv.org")
    # 单类 archive 也必须给出可选项，否则下拉框的第二级是空的
    for a in d["archives"]:
        assert a["categories"], a["id"]


@pytest.mark.parametrize("op", ["add", "add_many", "remove", "reorder", "set", "explode"])
def test_category_route_handles_every_op(sandbox, op):
    sandbox.set_config(categories=["cs.DB", "cs.PL"])
    body = {
        "add": {"op": "add", "cat": "cs.LG"},
        "add_many": {"op": "add_many", "cats": ["cs.CV", "cs.IR"]},
        "remove": {"op": "remove", "cat": "cs.PL"},
        "reorder": {"op": "reorder", "order": ["cs.PL", "cs.DB"]},
        "set": {"op": "set", "cats": ["math.LO", "math.CO"], "allow_empty": True},
        "explode": {"op": "explode"},
    }[op]
    r = RT.category(_req(body, api=S._Runtime(S)))
    d = json.loads(r.body)
    assert r.status == 200
    if op == "explode":
        assert d["ok"] is False and "未知操作" in d["msg"]
    else:
        assert d["ok"] is True, d["msg"]
        assert "category_meta" in d["state"]


def test_category_reorder_rejects_non_permutation(sandbox):
    sandbox.set_config(categories=["cs.DB", "cs.PL"])
    r = RT.category(_req({"op": "reorder", "order": ["cs.DB"]}, api=S._Runtime(S)))
    d = json.loads(r.body)
    assert d["ok"] is False and "不一致" in d["msg"]
    assert d["state"]["categories"] == ["cs.DB", "cs.PL"], "失败的排序不能改动配置"


def test_category_list_fields_accept_comma_string(sandbox):
    """手写 curl 传 "cs.LG,cs.IR" 也要能用，不能被逐字符当成分类号。"""
    sandbox.set_config(categories=["cs.DB"])
    r = RT.category(_req({"op": "add_many", "cats": "cs.LG,cs.IR"}, api=S._Runtime(S)))
    assert json.loads(r.body)["ok"] is True
    assert sandbox.config()["categories"] == ["cs.DB", "cs.LG", "cs.IR"]


def test_as_list_normalises():
    assert RT._as_list(None) == []
    assert RT._as_list("") == []
    assert RT._as_list("cs.DB, cs.LG") == ["cs.DB", "cs.LG"]
    assert RT._as_list("cs.DB，cs.LG") == ["cs.DB", "cs.LG"]
    assert RT._as_list(["cs.DB"]) == ["cs.DB"]


def test_digest_page_404s_without_any_digest(sandbox):
    r = RT.digest_page(_req(api=types.SimpleNamespace(
        OUT=str(sandbox.out), latest_digest=lambda: None)))
    assert r.status == 404


def test_digest_page_renders_welcome_when_no_categories(sandbox):
    """通用版首次运行：没有分类 = 引导页（200），而不是一句 404 文本。"""
    sandbox.set_config(categories=[])
    r = RT.digest_page(_req(api=S._Runtime(S)))
    assert r.status == 200
    assert "选择要跟踪的 arXiv 分类" in r.body
    assert r.ctype.startswith("text/html")


def test_digest_page_still_404s_when_categories_chosen(sandbox):
    """已选分类但还没抓取：保留原来的 404 文案（提示去跑 run_daily.py）。"""
    sandbox.set_config(categories=["cs.DB"])
    r = RT.digest_page(_req(api=S._Runtime(S)))
    assert r.status == 404 and "run_daily.py" in r.body


def test_digest_page_returns_file_reply(sandbox):
    f = sandbox.out / "arxiv_digest_20261015.html"
    f.write_text("<html></html>", encoding="utf-8")
    r = RT.digest_page(_req(api=types.SimpleNamespace(
        OUT=str(sandbox.out), latest_digest=lambda: str(f))))
    assert r.file_path == str(f)


def test_archive_snapshot_rejects_bad_date():
    r = RT.archive_snapshot(_req(), "not-a-date")
    assert r.status == 400 and "YYYYMMDD" in r.body


def test_archive_snapshot_404s_when_missing():
    api = types.SimpleNamespace(AR=types.SimpleNamespace(snapshot_path=lambda d, e: None))
    assert RT.archive_snapshot(_req(api=api), "20261015").status == 404


def test_output_file_only_serves_basename(sandbox):
    r = RT.output_file(_req(api=types.SimpleNamespace(OUT=str(sandbox.out))),
                       "../../etc/passwd")
    assert r.file_path == str(sandbox.out / "passwd"), "必须剥掉目录部分"
