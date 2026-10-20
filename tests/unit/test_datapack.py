# -*- coding: utf-8 -*-
"""数据包（datapack）：导入导出的语义契约。

这一层的测试重点不是"文件有没有复制过去"，而是三条**安全性质**：

  1. core 默认不覆盖（配置与画像是用户调出来的，静默覆盖等于丢工作）；
  2. usage / notes 只并集（永远不删用户已有的收藏与笔记）；
  3. learning 默认不导入（它是本机训练出来的结果）。

以及两条**隐私性质**：

  4. 界面/接口拿到的视图只有"形状"（包名 + 文件清单 + 体积），没有标题与描述；
  5. 导出默认不含高敏分组，且绝对路径会被裁剪。

设计与边界：docs/architecture/data-isolation.md。
"""
import json

import pytest

import customize as CZ
import datapack as DP
import paperutil as pu

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------- 文件名与列表

def test_valid_name_rejects_traversal_and_hidden_dirs():
    for bad in ("", ".", "..", "../etc", "a/b", "a\\b", ".hidden"):
        assert DP.valid_name(bad) is False, bad
    for ok in ("hengxin", "my-own", "p1", "示例包"):
        assert DP.valid_name(ok) is True, ok


def test_pack_path_raises_on_bad_name():
    with pytest.raises(ValueError):
        DP.pack_path("../escape")


def test_list_packs_finds_only_dirs_with_known_files(sandbox):
    sandbox.make_pack("alpha", {"config.json": {"categories": ["cs.DB"]}})
    (sandbox.packs / "empty-dir").mkdir(parents=True, exist_ok=True)
    (sandbox.packs / "not-a-pack").mkdir(parents=True, exist_ok=True)
    (sandbox.packs / "not-a-pack" / "notes.txt").write_text("x", encoding="utf-8")

    names = [p["name"] for p in DP.list_packs()]
    assert names == ["alpha"]

    p = DP.list_packs()[0]
    assert p["files"] == ["config.json"]
    assert p["groups"] == {"core": ["config.json"]}
    assert p["has_manifest"] is False


def test_manifest_falls_back_to_legacy_meta(sandbox):
    sandbox.make_pack("old", {"interests.json": {"topics": []}})
    (sandbox.packs / "old" / "meta.json").write_text(
        json.dumps({"title": "旧版包", "description": "只有 meta.json"}),
        encoding="utf-8")
    m = DP.manifest("old")
    assert m["title"] == "旧版包" and m["schema"] == 0
    assert m["_source"] == "meta.json"


def test_public_view_hides_title_and_description(sandbox):
    """界面/接口只该看到形状：描述里往往就是作者的类别选择与研究方向。"""
    sandbox.make_pack("p", {"config.json": {"categories": ["cs.DB"]}},
                      manifest={"schema": 1, "title": "某人的画像",
                                "description": "数据库系统 / 分布式计算"})
    view = DP.public_view()
    assert view[0]["name"] == "p"
    assert set(view[0]) == {"name", "files", "groups", "bytes"}
    text = json.dumps(view, ensure_ascii=False)
    assert "某人" not in text and "数据库" not in text


def test_state_reports_no_personal_data_in_bare_sandbox(bare_sandbox):
    st = DP.state()
    assert st["has_personal_data"] is False
    assert all(not v["exists"] for v in st["files"].values())


def test_state_marks_existing_files_without_leaking_absolute_paths(sandbox):
    pu.save_library({"favorites": {}, "downloads": {}, "downvotes": {}})
    st = DP.state()
    assert st["has_personal_data"] is True
    assert st["files"]["library.json"]["exists"] is True
    assert "path" not in st["files"]["library.json"]
    assert str(sandbox.root) not in json.dumps(st, ensure_ascii=False)


# ---------------------------------------------------------------- 导入：core

def _pack_config(cats=("cs.DB",), dldir="papers"):
    return {"categories": list(cats), "download_dir": dldir}


def test_import_core_into_clean_machine_writes_files(bare_sandbox):
    bare_sandbox.make_pack("p1", {"config.json": _pack_config(["cs.PL"]),
                                  "interests.json": {"topics": [], "owners": []}})
    ok, msg, report = DP.import_pack("p1")
    assert ok, msg
    assert {r["action"] for r in report} == {"written"}
    assert bare_sandbox.cfg.exists() and bare_sandbox.interests.exists()
    assert CZ.categories() == ["cs.PL"]
    assert pu.load_config()["download_dir"] == "papers"


def test_import_core_replaces_pristine_template_without_force(sandbox):
    """新用户第一次打开就会生成模板 config.json —— 它不是"用户的劳动成果"，
    一键导入必须能直接替换它，否则界面上那个按钮对目标用户永远报错。"""
    assert DP._is_pristine("config.json", str(sandbox.cfg)) is True
    assert sandbox.config()["categories"] == [], "沙箱起手就是模板"
    sandbox.make_pack("p1", {"config.json": _pack_config(["cs.PL"])})
    ok, msg, report = DP.import_pack("p1", groups=["core"])
    assert ok, msg
    assert report[0]["action"] == "replaced"
    assert CZ.categories() == ["cs.PL"]


def test_import_core_refuses_to_overwrite_different_local_file(sandbox):
    sandbox.set_config(categories=["cs.LG"])       # 用户已经改过 → 不再算模板初值
    assert DP._is_pristine("config.json", str(sandbox.cfg)) is False
    before = sandbox.config()
    sandbox.make_pack("p1", {"config.json": _pack_config(["cs.PL"])})
    ok, msg, report = DP.import_pack("p1", groups=["core"])
    assert ok is False
    assert any(r["action"] == "refused" and r["file"] == "config.json" for r in report)
    assert "force" in msg
    assert sandbox.config() == before, "拒绝时不得改动本机文件"


def test_pristine_judgement_ignores_local_port(sandbox):
    """端口是本机基础设施，不属于"某人的设置"：改过端口仍算模板初值。"""
    sandbox.set_config(port=9123)
    assert DP._is_pristine("config.json", str(sandbox.cfg)) is True


def test_import_keeps_local_port(sandbox):
    sandbox.set_config(port=9123)
    sandbox.make_pack("p1", {"config.json": _pack_config(["cs.PL"], dldir="papers")})
    ok, msg, _r = DP.import_pack("p1", groups=["core"])
    assert ok, msg
    cfg = sandbox.config()
    assert cfg["categories"] == ["cs.PL"], "包里的设置要进来"
    assert cfg["port"] == 9123, "端口必须保留本机的（导入不该把服务挪到别人的端口）"


def test_import_core_with_force_backs_up_then_replaces(sandbox):
    sandbox.set_config(categories=["cs.LG"])          # 与包内不同 → 默认会被拒绝
    sandbox.make_pack("p1", {"config.json": _pack_config(["cs.DB"])})
    ok, msg, report = DP.import_pack("p1", groups=["core"], force=True)
    assert ok, msg
    assert report[0]["action"] == "replaced"
    assert CZ.categories() == ["cs.DB"]
    backups = list((sandbox.out / "backup").glob("*/config.json"))
    assert backups, "覆盖前必须备份"


def test_import_is_idempotent(sandbox):
    sandbox.make_pack("p1", {"config.json": sandbox.config(),
                             "interests.json": sandbox.profile()})
    ok1, _m1, r1 = DP.import_pack("p1", groups=["core"])
    ok2, _m2, r2 = DP.import_pack("p1", groups=["core"])
    assert ok1 and ok2
    assert {r["action"] for r in r1} == {"skipped"}
    assert {r["action"] for r in r2} == {"skipped"}


def test_import_dry_run_writes_nothing(bare_sandbox):
    bare_sandbox.make_pack("p1", {"config.json": _pack_config(["cs.DB"])})
    ok, _msg, report = DP.import_pack("p1", dry_run=True)
    assert ok and report[0]["action"] == "written"      # 报告上仍是"将写入"
    assert not bare_sandbox.cfg.exists(), "预演不得写盘"


# ---------------------------------------------------------------- 导入：usage / notes

def test_import_library_merges_and_keeps_local_records(sandbox):
    pu.save_library({"favorites": {"2609.00001": {"id": "2609.00001", "title": "本机"}},
                     "downloads": {"2609.00001": {"path": "D:/local.pdf", "at": "x"}},
                     "downvotes": {}})
    sandbox.make_pack("p1", {"library.json": {
        "favorites": {"2609.00001": {"id": "2609.00001", "title": "包内"},
                      "2609.00002": {"id": "2609.00002", "title": "包内新"}},
        "downloads": {"2609.00001": {"path": "C:/other.pdf", "at": "y"}},
        "downvotes": {"2609.00003": {"title": "dv"}}}})
    ok, msg, report = DP.import_pack("p1", groups=["usage"])
    assert ok, msg
    lib = pu.load_library()
    assert set(lib["favorites"]) == {"2609.00001", "2609.00002"}
    assert lib["favorites"]["2609.00001"]["title"] == "本机", "同名条目保留本机"
    assert lib["downloads"]["2609.00001"]["path"] == "D:/local.pdf", "本机路径优先"
    assert "2609.00003" in lib["downvotes"]
    assert "并集" in report[0]["reason"]


def test_import_notes_merges_and_keeps_local_text(sandbox):
    sandbox.write("summaries.json", {"2609.1": "本机摘要"})
    sandbox.make_pack("p1", {"summaries.json": {"2609.1": "包内摘要", "2609.2": "包内新增"}})
    ok, _msg, _r = DP.import_pack("p1", groups=["notes"])
    assert ok
    d = sandbox.read("summaries.json")
    assert d["2609.1"] == "本机摘要" and d["2609.2"] == "包内新增"


def test_learning_is_not_imported_by_default(sandbox):
    sandbox.make_pack("p1", {"profile_state.json": {"topic_mult": {"X": 2.0}},
                             "behavior.json": [{"id": "1", "action": "favorite"}]})
    DP.import_pack("p1")
    assert not (sandbox.out / "profile_state.json").exists()
    assert not (sandbox.out / "behavior.json").exists()


def test_learning_imported_when_requested_and_backed_up(sandbox):
    sandbox.write("profile_state.json", {"topic_mult": {}, "kw": {}, "paper_bonus": {},
                                        "counts": {}})
    sandbox.make_pack("p1", {"profile_state.json": {"topic_mult": {"X": 2.0}}})
    ok, _msg, report = DP.import_pack("p1", groups=["learning"])
    assert ok
    assert any(r["action"] == "replaced" for r in report)
    assert sandbox.read("profile_state.json")["topic_mult"] == {"X": 2.0}
    assert list((sandbox.out / "backup").glob("*/profile_state.json"))


def test_groups_filter_limits_what_is_touched(sandbox):
    sandbox.make_pack("p1", {"config.json": _pack_config(["cs.DB"]),
                             "library.json": {"favorites": {"x": {"title": "x"}}}})
    DP.import_pack("p1", groups=["core"])
    assert not pu.load_library()["favorites"], "未请求 usage 时不得写库"


# ---------------------------------------------------------------- 导入：拒绝路径

def test_import_unknown_pack_reports_available(sandbox):
    ok, msg, report = DP.import_pack("nope")
    assert ok is False and "找不到" in msg and report == []


def test_import_unknown_group_is_rejected(sandbox):
    sandbox.make_pack("p1", {"config.json": {}})
    ok, msg, _ = DP.import_pack("p1", groups=["weird"])
    assert ok is False and "未知分组" in msg


def test_import_rejects_newer_manifest_schema(sandbox):
    sandbox.make_pack("p1", {"config.json": _pack_config()},
                      manifest={"schema": DP.SCHEMA + 1})
    ok, msg, _ = DP.import_pack("p1")
    assert ok is False and "版本" in msg
    assert not (sandbox.out / "backup").exists()


def test_import_rejects_file_with_bad_hash(sandbox):
    sandbox.make_pack("p1", {"config.json": _pack_config(["cs.DB"])},
                      manifest={"schema": 1,
                                "files": [{"name": "config.json",
                                           "sha256": "0" * 64}]})
    ok, msg, report = DP.import_pack("p1")
    assert ok is False
    assert report[0]["action"] == "refused" and "sha256" in report[0]["reason"]
    assert CZ.categories() == [], "校验失败的文件不得写入"


def test_import_rejects_broken_json(sandbox):
    d = sandbox.make_pack("p1", {})
    (d / "config.json").write_text("{not json", encoding="utf-8")
    ok, _msg, report = DP.import_pack("p1")
    assert ok is False and report[0]["action"] == "refused"


# ---------------------------------------------------------------- 导出的安全默认

def test_export_default_is_core_only(sandbox):
    pu.save_library({"favorites": {"a": {"title": "a"}}, "downloads": {}, "downvotes": {}})
    ok, msg, _ = DP.export_pack("mine")
    assert ok, msg
    assert (sandbox.packs / "mine" / "config.json").exists()
    assert not (sandbox.packs / "mine" / "library.json").exists(), \
        "默认不得导出阅读史"


def test_export_with_usage_strips_absolute_paths(sandbox):
    sandbox.set_config(download_dir="D:/papers/arXiv")
    pu.save_library({"favorites": {"a": {"title": "a", "path": "D:/papers/arXiv/a.pdf"}},
                     "downloads": {"a": {"path": "C:/Users/me/papers/x.pdf", "at": "t"}},
                     "downvotes": {}})
    ok, _msg, _r = DP.export_pack("mine", groups=["core", "usage"])
    assert ok
    cfg = json.loads((sandbox.packs / "mine" / "config.json").read_text(encoding="utf-8"))
    assert cfg["download_dir"] == "papers", "绝对下载目录必须中性化"
    lib = json.loads((sandbox.packs / "mine" / "library.json").read_text(encoding="utf-8"))
    assert lib["downloads"]["a"]["path"] == "x.pdf"
    assert lib["favorites"]["a"]["path"] == "a.pdf"


def test_export_keep_paths_is_opt_in(sandbox):
    sandbox.set_config(download_dir="D:/papers/arXiv")
    DP.export_pack("mine", sanitize=False)
    cfg = json.loads((sandbox.packs / "mine" / "config.json").read_text(encoding="utf-8"))
    assert cfg["download_dir"] == "D:/papers/arXiv"


def test_export_writes_manifest_with_hash(sandbox):
    ok, _msg, _r = DP.export_pack("mine")
    assert ok
    m = DP.manifest("mine")
    assert m["schema"] == DP.SCHEMA
    assert m["_source"] == "manifest.json"
    names = [f["name"] for f in m["files"]]
    assert names == ["config.json", "interests.json"]
    assert all(len(f["sha256"]) == 64 for f in m["files"])


def test_export_then_import_roundtrip(sandbox):
    sandbox.set_config(categories=["cs.SE"], download_dir=str(sandbox.download_dir))
    ok, msg, _ = DP.export_pack("mine")
    assert ok, msg
    # 把本机改成别的设置，再从刚导出的包导回来
    sandbox.set_config(categories=["cs.DB"])
    ok, msg, _ = DP.import_pack("mine", groups=["core"], force=True)
    assert ok, msg
    assert CZ.categories() == ["cs.SE"]
    assert pu.load_config()["download_dir"] == "papers", "导出时已中性化"


def test_compare_pack_reports_relationship(sandbox):
    sandbox.make_pack("p1", {"config.json": {"categories": ["cs.DB"]},
                             "interests.json": sandbox.profile()})
    rows = {r["file"]: r["status"] for r in DP.compare_pack("p1")}
    assert rows["config.json"] == "pristine", "沙箱配置仍是模板 → 直接替换"
    assert rows["interests.json"] == "same"

    sandbox.set_config(categories=["cs.LG"])           # 用户改过 → 需要 --force
    rows = {r["file"]: r["status"] for r in DP.compare_pack("p1")}
    assert rows["config.json"] == "diff"


# ---------------------------------------------------------------- 路径自检

def test_scan_paths_finds_machine_paths_but_not_urls():
    hits = DP.scan_paths({"a": "D:/papers/x.pdf", "b": "https://example.org/x",
                          "c": ["/home/me/y", "plain"]})
    joined = " ".join(hits)
    assert "D:/papers/x.pdf" in joined and "/home/me/y" in joined
    assert "https://" not in joined
