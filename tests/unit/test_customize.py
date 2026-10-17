# -*- coding: utf-8 -*-
"""customize：可定制项的唯一读写层。

重点覆盖三类风险：
  1) 写文件时**只改目标键**（不能把用户手写的画像冲掉）；
  2) 画像主来源与「熟悉研究者」的联动（改名 / 取消联动 / 删除都要正确回滚）；
  3) 合并视图的顺序不变式（topics 顺序 = 前端权重索引顺序）。
"""
import json

import pytest

import customize as CZ
import paperutil as pu

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------ 分类

def test_categories_and_labels(sandbox):
    sandbox.set_config(categories=["cs.DB", "cs.PL"],
                       category_names={"cs.PL": "编程语言"})
    assert CZ.categories() == ["cs.DB", "cs.PL"]
    assert CZ.category_label("cs.DB") == "数据库"      # 内置词典
    assert CZ.category_label("cs.PL") == "编程语言"     # config 覆盖
    assert CZ.category_label("cs.ZZ") == "（未命名主题）"


# "cs.db" 是合法的（arXiv 有 cond-mat.stat-mech 这类小写子类），故不在坏例里
@pytest.mark.parametrize("bad", ["", "csdb", "CS.DB", "cs.", "not a cat", "cs.DB.x"])
def test_add_category_rejects_bad_format(sandbox, bad):
    ok, msg, _ = CZ.add_category(bad)
    assert not ok and "格式" in msg
    assert CZ.categories() == json.loads(sandbox.cfg.read_text("utf-8"))["categories"]


def test_add_category_appends_and_names(sandbox):
    before = CZ.categories()
    ok, msg, info = CZ.add_category("cs.PL")
    assert ok and info["cat"] == "cs.PL"
    assert CZ.categories() == before + ["cs.PL"]
    assert CZ.category_label("cs.PL") == "程序设计语言"
    assert "重新抓取" in msg, "提示里必须说明要重抓才生效"


def test_add_category_rejects_duplicate(sandbox):
    cat = CZ.categories()[0]
    ok, msg, _ = CZ.add_category(cat)
    assert not ok and "已存在" in msg


def test_remove_category_keeps_at_least_one(sandbox):
    sandbox.set_config(categories=["cs.DB"])
    ok, msg, _ = CZ.remove_category("cs.DB")
    assert not ok and "至少要保留" in msg


def test_remove_category_drops_name_too(sandbox):
    sandbox.set_config(categories=["cs.DB", "cs.PL"],
                       category_names={"cs.PL": "编程语言"})
    ok, _, _ = CZ.remove_category("cs.PL")
    assert ok
    assert CZ.categories() == ["cs.DB"]
    assert "cs.PL" not in sandbox.config()["category_names"]


def test_remove_unknown_category(sandbox):
    ok, msg, _ = CZ.remove_category("cs.ZZ")
    assert not ok and "不存在" in msg


# ------------------------------------------------------------------ 下载目录

def test_set_download_dir_creates_and_persists(sandbox):
    target = sandbox.root / "mypapers"
    ok, msg, info = CZ.set_download_dir(str(target))
    assert ok and info["download_dir"].replace("\\", "/") == str(target).replace("\\", "/")
    assert target.is_dir(), "目录应自动创建"
    assert CZ.download_dir().replace("\\", "/") == str(target).replace("\\", "/")


def test_set_download_dir_rejects_empty(sandbox):
    ok, msg, _ = CZ.set_download_dir("   ")
    assert not ok and "不能为空" in msg


def test_set_download_dir_rejects_existing_file(sandbox):
    f = sandbox.root / "afile"
    f.write_text("x", encoding="utf-8")
    ok, msg, _ = CZ.set_download_dir(str(f))
    assert not ok


# ------------------------------------------------------------------ 画像主来源

def _owner(**kw):
    base = {"name": "Ada Lovelace", "label": "Ada", "site": "https://example.org",
            "affiliation": "Analytical Engine Lab", "interests": "程序化推理",
            "signature_topics": ["分析机", "符号运算"]}
    base.update(kw)
    return base


def test_add_owner_requires_name(sandbox):
    ok, msg, _ = CZ.add_owner({"name": "  "})
    assert not ok and "姓名" in msg


def test_add_owner_rejects_bad_site(sandbox):
    ok, msg, _ = CZ.add_owner(_owner(site="example.org"))
    assert not ok and "http" in msg


def test_add_owner_rejects_duplicate_case_insensitive(sandbox):
    assert CZ.add_owner(_owner())[0]
    ok, msg, _ = CZ.add_owner(_owner(name="ada lovelace"))
    assert not ok and "已存在" in msg


def test_add_owner_links_people_and_splits_topics(sandbox):
    ok, _, info = CZ.add_owner(_owner(signature_topics="分析机\n符号运算\n"))
    assert ok
    prof = sandbox.profile()
    assert prof["owners"][0]["people_linked"] is True
    assert prof["owners"][0]["signature_topics"] == ["分析机", "符号运算"]
    assert "Ada Lovelace" in prof["people"]


def test_add_owner_without_link_keeps_people_clean(sandbox):
    CZ.add_owner(_owner(name="Grace Hopper"), link_person=False)
    assert "Grace Hopper" not in sandbox.profile()["people"]


def test_update_owner_rename_moves_people_entry(sandbox):
    CZ.add_owner(_owner())
    ok, msg, _ = CZ.update_owner("Ada Lovelace", _owner(name="Ada King"))
    assert ok and "原 Ada Lovelace" in msg
    prof = sandbox.profile()
    assert [o["name"] for o in prof["owners"]] == ["Ada King"]
    assert "Ada King" in prof["people"]
    assert "Ada Lovelace" not in prof["people"], "旧名字的加成必须撤销"


def test_update_owner_rename_to_existing_is_rejected(sandbox):
    CZ.add_owner(_owner())
    CZ.add_owner(_owner(name="Grace Hopper"))
    ok, msg, _ = CZ.update_owner("Grace Hopper", _owner(name="Ada Lovelace"))
    assert not ok and "已存在" in msg


def test_update_owner_unlink_removes_people_but_keeps_handwritten(sandbox):
    sandbox.set_profile(people=["Alan Turing"])
    CZ.add_owner(_owner())
    ok, _, _ = CZ.update_owner("Ada Lovelace", _owner(), link_person=False)
    assert ok
    prof = sandbox.profile()
    assert prof["owners"][0]["people_linked"] is False
    assert prof["people"] == ["Alan Turing"], "手写的人名不能被联动删除"


def test_update_unknown_owner(sandbox):
    ok, msg, _ = CZ.update_owner("Nobody", _owner())
    assert not ok and "未找到" in msg


def test_remove_owner_unlinks_and_refuses_last(sandbox):
    CZ.add_owner(_owner())
    ok, msg, _ = CZ.remove_owner("Ada Lovelace")
    assert not ok and "至少" in msg, "最后一条主来源不允许删空"

    CZ.add_owner(_owner(name="Grace Hopper"))
    ok, _, _ = CZ.remove_owner("Grace Hopper")
    assert ok
    prof = sandbox.profile()
    assert [o["name"] for o in prof["owners"]] == ["Ada Lovelace"]
    assert "Grace Hopper" not in prof["people"]


def test_owners_view_exposes_only_known_fields(sandbox):
    CZ.add_owner(_owner(internal="secret"))
    view = CZ.owners_view()
    assert set(view[0]) == {"name", "label", "site", "affiliation", "interests",
                            "signature_topics", "people_linked"}


# ------------------------------------------------------------------ 兴趣来源

def test_add_source_doc_derives_people_and_keywords(sandbox):
    doc = sandbox.root / "home.md"
    doc.write_text(
        "Ada Lovelace works on symbolic computation and choreography specification.\n"
        "Ada Lovelace leads the analytical engine project.\n"
        "Ada Lovelace publishes on choreography specification regularly.\n",
        encoding="utf-8")
    ok, msg, info = CZ.add_source("doc", str(doc), "我的主页")
    assert ok, msg
    derived = CZ.load_extra()["_derived"]
    assert "Ada Lovelace" in derived["people"]
    assert isinstance(derived["keywords"], list)
    assert info["derived"] or CZ.sources_view()[0]["derived"] is not None


def test_add_source_rejects_duplicate_and_empty(sandbox):
    ok, msg, _ = CZ.add_source("doc", "")
    assert not ok and "不能为空" in msg
    doc = sandbox.root / "a.md"
    doc.write_text("Ada Lovelace Ada Lovelace", encoding="utf-8")
    assert CZ.add_source("doc", str(doc))[0]
    ok, msg, _ = CZ.add_source("doc", str(doc))
    assert not ok and "已存在" in msg


def test_remove_source_revokes_derived(sandbox):
    doc = sandbox.root / "home.md"
    doc.write_text("Ada Lovelace " * 5, encoding="utf-8")
    CZ.add_source("doc", str(doc))
    sid = CZ.load_extra()["sources"][0]["sid"]
    ok, _, _ = CZ.remove_source(sid)
    assert ok
    assert CZ.load_extra()["_derived"]["people"] == []


def test_block_keyword_roundtrip(sandbox):
    # 直接构造派生关键词，绕开文本抽取（抽词规则由 test_fetch_parsers 之外的算法决定）
    extra = CZ.load_extra()
    extra["_derived"] = {"people": [], "keywords": ["choreography"], "matched_topics": []}
    CZ.save_extra(extra)

    ok, _, _ = CZ.block_keyword("choreography", True)
    assert ok
    assert CZ.load_extra()["block_kw"] == ["choreography"]

    ok, _, _ = CZ.block_keyword("choreography", False)
    assert ok and CZ.load_extra()["block_kw"] == []


# ------------------------------------------------------------------ 合并视图

def test_effective_topics_keeps_order_and_appends_custom(sandbox):
    sandbox.set_profile(topics=[
        {"name": "B", "weight": 2.0, "keywords": ["b"]},
        {"name": "A", "weight": 1.0, "keywords": ["a"]},
    ])
    base = CZ.effective_topics()
    assert [t["name"] for t in base] == ["B", "A"], "顺序是前端权重索引，不能重排"

    extra = CZ.load_extra()
    extra["_derived"] = {"people": [], "keywords": ["from-source"], "matched_topics": []}
    CZ.save_extra(extra)

    merged = CZ.effective_topics()
    assert [t["name"] for t in merged] == ["B", "A", CZ.CUSTOM_TOPIC]
    assert merged[-1]["custom"] is True
    assert merged[-1]["weight"] == CZ.CUSTOM_TOPIC_WEIGHT
    assert merged[-1]["keywords"] == ["from-source"]


def test_effective_seed_weights_same_order_as_topics(sandbox):
    sandbox.set_profile(topics=[{"name": "X", "weight": 1.7, "keywords": ["x"]}])
    names = [t["name"] for t in CZ.effective_topics()]
    seeds = [n for n, _ in CZ.effective_seed_weights()]
    assert names == seeds


def test_effective_people_merges_derived_without_dup(sandbox):
    sandbox.set_profile(people=["Ada Lovelace"])
    extra = CZ.load_extra()
    extra["_derived"] = {"people": ["Ada Lovelace", "Grace Hopper"],
                         "keywords": [], "matched_topics": []}
    CZ.save_extra(extra)
    people = CZ.effective_people()
    assert people.count("Ada Lovelace") == 1
    assert "Grace Hopper" in people


def test_snapshot_and_view_shape(sandbox):
    snap = CZ.snapshot()
    assert {"categories", "category_names", "download_dir", "sources",
            "derived", "blocked_keywords", "updated_at"} <= set(snap)
    view = CZ.view()
    assert set(view["profile"]) == {"owners", "themes", "people", "systems",
                                    "negative", "counts", "downvoted", "updated_at"}


def test_view_themes_weight_is_seed_times_mult(sandbox):
    sandbox.set_profile(topics=[{"name": "X", "weight": 1.2, "keywords": ["x"]}])
    PF = __import__("profile")
    st = PF.load()
    st["topic_mult"] = {"X": 1.5}
    PF.save(st)
    theme = CZ.profile_view()["themes"][0]
    assert theme["seed"] == 1.2
    assert theme["mult"] == 1.5
    assert theme["weight"] == round(1.2 * 1.5, 3)


def test_interests_file_is_created_from_example(bare_sandbox):
    prof = CZ.load_interests()
    assert bare_sandbox.interests.exists()
    assert "topics" in prof and isinstance(prof["topics"], list)
