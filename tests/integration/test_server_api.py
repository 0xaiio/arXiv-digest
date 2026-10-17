# -*- coding: utf-8 -*-
"""集成：HTTP 接口面（真实 ThreadingHTTPServer + 真实 Handler）。

覆盖三类契约：
  1) 路由与状态码（含 400/404/500 的错误约定）；
  2) 写接口的**副作用**（library.json / interests.json / config.json 真的变了）；
  3) 跨源约定（CORS 头、OPTIONS 预检、/files/ 的目录穿越防护）。
"""
import json

import pytest

import customize as CZ
import paperutil as pu
import server as S

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """所有出网/开窗/子进程动作都桩掉：接口测试不该依赖外部世界。"""
    monkeypatch.setattr(S.NR, "ensure_route", lambda force=False, log=False:
                        ("http://127.0.0.1:7890", "本机代理 :7890"))
    monkeypatch.setattr(S.NR, "candidates", lambda prefer=None: [(None, "直连")])
    monkeypatch.setattr(S.NR, "last_failure", lambda: None)
    monkeypatch.setattr(S.os, "startfile", lambda *a, **k: None, raising=False)


# ------------------------------------------------------------------ 健康与页面

def test_ping(http):
    code, body = http.get_json("/api/ping")
    assert code == 200 and body == {"ok": True}


def test_home_is_404_before_first_pipeline(sandbox, http):
    code, body = http.get("/")
    assert code == 404
    assert "尚无摘要页" in body


def test_home_serves_latest_digest(seeded, http):
    import build_report as B
    import recommend as R
    R.main()
    B.main()

    code, body = http.get("/")
    assert code == 200
    assert "为你推荐" in body
    assert body.lstrip().startswith("<!DOCTYPE html>")


def test_home_accepts_explicit_file(seeded, http):
    import build_report as B
    import recommend as R
    R.main()
    B.main()

    code, body = http.get("/?f=arxiv_digest_20261015.html")
    assert code == 200 and "分类详解" in body


def test_dynamic_pages_render(seeded, http):
    for path, marker in (("/favorites", "收藏"), ("/profile", "画像主来源"), ("/archive", "存档")):
        code, body = http.get(path)
        assert code == 200, path
        assert marker in body, path
        assert "text/html" not in body  # 只是确保拿到的是 HTML 正文而非 JSON


def test_archive_snapshot_and_errors(seeded, http):
    import build_report as B
    import recommend as R
    R.main()
    B.main()

    code, body = http.get("/archive/20261015")
    assert code == 200 and "为你推荐" in body

    code, body = http.get("/archive/2026-10-15")
    assert code == 400 and "YYYYMMDD" in body

    code, body = http.get("/archive/20200101")
    assert code == 404


def test_files_route_serves_output_and_blocks_traversal(seeded, http):
    (seeded.out / "note.html").write_text("<p>hello</p>", encoding="utf-8")
    code, body = http.get("/files/note.html")
    assert code == 200 and "hello" in body

    # basename 处理：不能穿出 output/
    code, _ = http.get("/files/../config.json")
    assert code == 404


def test_unknown_get_is_404(http):
    code, body = http.get("/api/nope")
    assert code == 404 and "not found" in body


# ------------------------------------------------------------------ 只读接口

def test_state_shape(seeded, http):
    code, st = http.get_json("/api/state")
    assert code == 200
    assert set(st) >= {"favorites", "downloads", "downvotes", "download_dir",
                       "categories", "category_names", "profile"}
    assert isinstance(st["favorites"], list)
    assert st["categories"] == ["cs.DB"]
    assert set(st["profile"]) == {"topics", "weights", "kw", "pens"}
    assert len(st["profile"]["topics"]) == len(st["profile"]["weights"])


def test_customize_exposes_profile_view(seeded, http):
    code, d = http.get_json("/api/customize")
    assert code == 200
    assert d["download_dir"] == str(seeded.download_dir)
    prof = d["profile"]
    assert [o["name"] for o in prof["owners"]] == ["Ada Lovelace"]
    assert [t["name"] for t in prof["themes"]][:2] == ["事务与隔离级别", "一致性模型"]
    assert prof["themes"][0]["weight"] == prof["themes"][0]["seed"]


def test_profile_and_library_endpoints(seeded, http):
    code, prof = http.get_json("/api/profile")
    assert code == 200 and "topics" in prof

    lib = pu.load_library()
    lib["favorites"]["2609.10001"] = {"id": "2609.10001", "title": "T"}
    pu.save_library(lib)
    code, d = http.get_json("/api/library")
    assert code == 200 and "2609.10001" in d["favorites"]


def test_archive_days_endpoint(seeded, http):
    import archive as AR
    AR.record_issue("20261015", papers=[{"sid": "2609.10001"}], n_new=1)
    code, d = http.get_json("/api/archive/days")
    assert code == 200
    assert "20261015" in d["dates"]
    assert d["stats"]["issues"] == 1
    assert d["issues"][0]["n_new"] == 1


def test_net_route_endpoint(seeded, http):
    code, d = http.get_json("/api/net_route")
    assert code == 200
    assert d["ok"] is True and "7890" in d["proxy"]


# ------------------------------------------------------------------ 跨源

def test_options_preflight(http):
    code, headers = http.options("/api/favorite")
    assert code == 204
    assert headers.get("Access-Control-Allow-Origin") == "*"
    assert "POST" in headers.get("Access-Control-Allow-Methods", "")


# ------------------------------------------------------------------ 收藏 / Downvote

def test_favorite_then_downvote_then_favorite(seeded, http):
    code, d = http.post("/api/favorite", {"id": "2609.10001"})
    assert code == 200 and d["ok"] and d["favorited"]
    assert "2609.10001" in pu.load_library()["favorites"]

    code, d = http.post("/api/downvote", {"id": "2609.10001"})
    assert d["ok"] and d["downvoted"]
    lib = pu.load_library()
    assert "2609.10001" in lib["downvotes"]
    assert "2609.10001" in lib["favorites"], "Downvote 不自动取消收藏"

    code, d = http.post("/api/favorite", {"id": "2609.10001"})
    assert "2609.10001" not in pu.load_library()["downvotes"], "重新收藏应撤销 Downvote"


def test_favorite_requires_id(seeded, http):
    code, d = http.post("/api/favorite", {})
    assert code == 400 and d["ok"] is False and "缺少 id" in d["msg"]


def test_unfavorite_and_undownvote(seeded, http):
    http.post("/api/favorite", {"id": "2609.10001"})
    code, d = http.post("/api/unfavorite", {"id": "2609.10001"})
    assert d["ok"] and d["favorited"] is False
    assert "2609.10001" not in pu.load_library()["favorites"]

    http.post("/api/downvote", {"id": "2609.10002"})
    code, d = http.post("/api/undownvote", {"id": "2609.10002"})
    assert d["ok"] and d["downvoted"] is False
    assert "2609.10002" not in pu.load_library()["downvotes"]


def test_downvote_records_metadata(seeded, http):
    http.post("/api/downvote", {"id": "2609.10001"})
    rec = pu.load_library()["downvotes"]["2609.10001"]
    assert rec["title"].startswith("Isolation Level")
    assert rec["at"]


def test_event_endpoint_validates_action(seeded, http):
    code, d = http.post("/api/event", {"id": "2609.10001", "action": "teleport"})
    assert code == 400 and "不合法" in d["msg"]

    for action in ("abstract", "pdf", "open", "expand"):
        code, d = http.post("/api/event", {"id": "2609.10001", "action": action})
        assert d["ok"] and d["action"] == action


# ------------------------------------------------------------------ 下载

def test_download_success_marks_favorite(seeded, http, monkeypatch):
    target = str(seeded.download_dir / "arXiv2026 2609.10001 T.pdf")
    monkeypatch.setattr(S, "download_pdf", lambda sid, papers, cfg, force=False:
                        (True, "", target))

    code, d = http.post("/api/download", {"id": "2609.10001"})
    assert code == 200 and d["ok"] and d["path"] == target
    lib = pu.load_library()
    assert lib["downloads"]["2609.10001"]["path"] == target
    assert "2609.10001" in lib["favorites"], "下载即收藏"


def test_download_failure_is_reported(seeded, http, monkeypatch):
    monkeypatch.setattr(S, "download_pdf", lambda *a, **k:
                        (False, "未找到论文元数据（可能已过期）", ""))
    code, d = http.post("/api/download", {"id": "2609.99999"})
    assert d["ok"] is False and "未找到" in d["msg"]
    assert pu.load_library()["downloads"] == {}


def test_download_all_keeps_request_order(seeded, http, monkeypatch):
    calls = []

    def fake(sid, papers, cfg, force=False):
        calls.append(sid)
        return True, "", "papers/%s.pdf" % sid

    monkeypatch.setattr(S, "download_pdf", fake)
    code, d = http.post("/api/download_all", {"ids": ["2609.10002", "2609.10001"]})
    assert d["ok"] and d["n_ok"] == 2
    assert [r["id"] for r in d["results"]] == ["2609.10002", "2609.10001"]
    assert sorted(calls) == ["2609.10001", "2609.10002"]


def test_download_exception_returns_500(seeded, http, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("网络炸了")

    monkeypatch.setattr(S, "download_pdf", boom)
    code, d = http.post("/api/download", {"id": "2609.10001"})
    assert code == 500 and d["ok"] is False and "服务端异常" in d["msg"]


# ------------------------------------------------------------------ 画像 / 配置写接口

def test_owner_crud_over_http(seeded, http):
    code, d = http.post("/api/owner", {"op": "add", "name": "Grace Hopper",
                                       "label": "Grace", "site": "https://example.org",
                                       "link_person": True})
    assert d["ok"], d["msg"]
    names = [o["name"] for o in d["state"]["profile"]["owners"]]
    assert "Grace Hopper" in names

    code, d = http.post("/api/owner", {"op": "update", "orig": "Grace Hopper",
                                       "name": "Grace Murray Hopper",
                                       "label": "Grace", "site": "https://example.org"})
    assert d["ok"], d["msg"]
    names = [o["name"] for o in d["state"]["profile"]["owners"]]
    assert "Grace Murray Hopper" in names and "Grace Hopper" not in names

    code, d = http.post("/api/owner", {"op": "remove", "name": "Grace Murray Hopper"})
    assert d["ok"]
    assert "Grace Murray Hopper" not in [o["name"] for o in d["state"]["profile"]["owners"]]


def test_owner_unknown_op(seeded, http):
    code, d = http.post("/api/owner", {"op": "explode"})
    assert d["ok"] is False and "未知操作" in d["msg"]


def test_category_add_remove_over_http(seeded, http):
    code, d = http.post("/api/category", {"op": "add", "cat": "cs.PL", "name": "编程语言"})
    assert d["ok"] and "cs.PL" in d["state"]["categories"]
    assert d["state"]["category_names"]["cs.PL"] == "编程语言"

    code, d = http.post("/api/category", {"op": "remove", "cat": "cs.PL"})
    assert d["ok"] and "cs.PL" not in d["state"]["categories"]


def test_config_endpoint_sets_download_dir(seeded, http):
    target = seeded.root / "newpapers"
    code, d = http.post("/api/config", {"download_dir": str(target)})
    assert d["ok"] and target.is_dir()
    assert pu.load_config()["download_dir"].replace("\\", "/") == str(target).replace("\\", "/")


def test_source_add_block_remove_over_http(seeded, http):
    doc = seeded.root / "home.md"
    doc.write_text("Ada Lovelace " * 6 + "\nchoreography specification\n" * 2,
                   encoding="utf-8")

    code, d = http.post("/api/source", {"op": "add", "type": "doc",
                                        "value": str(doc), "note": "主页"})
    assert d["ok"], d["msg"]
    assert d["state"]["sources"], "来源应出现在状态里"

    sid = d["state"]["sources"][0]["sid"]
    code, d = http.post("/api/source", {"op": "block", "kw": "choreography"})
    assert d["ok"] and "choreography" in d["state"]["blocked_keywords"]
    code, d = http.post("/api/source", {"op": "unblock", "kw": "choreography"})
    assert d["ok"] and d["state"]["blocked_keywords"] == []

    code, d = http.post("/api/source", {"op": "remove", "sid": sid})
    assert d["ok"] and d["state"]["sources"] == []


def test_source_unknown_op(seeded, http):
    code, d = http.post("/api/source", {"op": "zap"})
    assert d["ok"] is False and "未知操作" in d["msg"]


def test_rebuild_runs_subprocesses(seeded, http, monkeypatch):
    seen = []

    class R:
        returncode = 0
        stderr = ""
        stdout = ""

    monkeypatch.setattr(S.subprocess, "run", lambda cmd, **kw: (seen.append(cmd[1]), R())[1])
    code, d = http.post("/api/rebuild", {})
    assert d["ok"] is True
    assert [p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in seen] == \
        ["recommend.py", "build_report.py"]


def test_rebuild_reports_failure(seeded, http, monkeypatch):
    class R:
        returncode = 1
        stderr = "boom"
        stdout = ""

    monkeypatch.setattr(S.subprocess, "run", lambda cmd, **kw: R())
    code, d = http.post("/api/rebuild", {})
    assert d["ok"] is False and "失败" in d["msg"]


def test_open_missing_file(seeded, http):
    code, d = http.post("/api/open", {"id": "2609.99999"})
    assert d["ok"] is False and "文件不存在" in d["msg"]


def test_open_existing_file(seeded, http):
    f = seeded.download_dir / "x.pdf"
    seeded.download_dir.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"%PDF-1.4")
    lib = pu.load_library()
    lib["downloads"]["2609.10001"] = {"path": str(f), "at": "now", "title": "T"}
    pu.save_library(lib)

    code, d = http.post("/api/open", {"id": "2609.10001"})
    assert d["ok"] and d["path"] == str(f)


def test_open_folder_creates_directory(seeded, http):
    target = seeded.root / "brand-new-dir"
    code, d = http.post("/api/open_folder", {"dir": str(target)})
    assert d["ok"] and target.is_dir()


def test_unknown_post_is_404(seeded, http):
    code, d = http.post("/api/nonexistent", {})
    assert code == 404 and d["ok"] is False
