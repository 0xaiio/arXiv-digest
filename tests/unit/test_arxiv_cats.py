# -*- coding: utf-8 -*-
"""arxiv_cats：官方分类表与校验规则的单一真源。

为什么值得单独一层测试
----------------------
这个模块的每一处偏差都会以「用户配了分类却抓不到论文」的形式暴露，而且
很难从现象反推原因（拼错一个字母 → 空日报）。因此这里把三件事钉死：

  1) **表本身自洽**：格式、唯一、archive 归属、单段 archive 的虚拟分类都成立；
  2) **校验**：合法 / 格式错 / 大小写错 / 表内不存在，四类输入各有确定结论与
     可据以自救的提示；
  3) **检索与邻域**：前端下拉框的搜索、以及「兴趣扩展」默认池的推导规则。
"""
import pytest

import arxiv_cats as AC

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------ 表结构

def test_every_category_matches_the_format_rule():
    for cat in AC.CATEGORIES:
        assert AC.CAT_RE.match(cat), cat


def test_category_ids_are_unique():
    ids = [c["id"] for a in AC.ARCHIVES for c in a["categories"]]
    assert len(ids) == len(set(ids)) == AC.TOTAL


def test_archives_all_have_selectable_categories():
    """界面上「先选 abc 再选 def」要求每个 archive 的第二级都非空。"""
    for a in AC.ARCHIVES:
        assert a["categories"], "%s 没有可选项" % a["id"]
        for c in a["categories"]:
            assert c["id"].split(".")[0] == a["id"], c["id"]
            assert c["zh"] and c["en"], c["id"]


def test_single_part_archives_expose_one_virtual_category():
    singles = {a["id"] for a in AC.ARCHIVES if a["single"]}
    assert singles == {"gr-qc", "hep-ex", "hep-lat", "hep-ph", "hep-th",
                       "math-ph", "nucl-ex", "nucl-th", "quant-ph"}
    for aid in singles:
        a = [x for x in AC.ARCHIVES if x["id"] == aid][0]
        assert [c["id"] for c in a["categories"]] == [aid]
        assert AC.CATEGORIES[aid]["single"] is True


def test_every_category_has_chinese_name():
    """分类小节标题与标签都用中文名；缺一个就会在页面上露出英文 ID。"""
    missing = [c for c, v in AC.CATEGORIES.items() if not v["zh"]]
    assert missing == []


def test_known_reference_categories_exist():
    for cat in ("cs.DB", "cs.DC", "cs.FL", "cs.LO", "cs.PL", "cs.SE",
                "math.LO", "stat.ML", "quant-ph", "cond-mat.stat-mech",
                "physics.acc-ph", "q-bio.NC", "q-fin.EC", "econ.EM", "eess.AS"):
        assert cat in AC.CATEGORIES, cat


# ------------------------------------------------------------------ 结构拆分

@pytest.mark.parametrize("cat,abc,def_", [
    ("cs.DB", "cs", "DB"),
    ("cond-mat.stat-mech", "cond-mat", "stat-mech"),
    ("quant-ph", "quant-ph", ""),
])
def test_split(cat, abc, def_):
    assert AC.split(cat) == (abc, def_)


def test_archive_of_falls_back_to_prefix_for_unknown():
    assert AC.archive_of("cs.LG") == "cs"
    assert AC.archive_of("foo.BAR") == "foo"
    assert AC.archive_of("") == ""


def test_label_and_en_name():
    assert AC.label("cs.DB") == "数据库"
    assert AC.en_name("cs.DB") == "Databases"
    assert AC.label("cs.ZZ") == "cs.ZZ", "未知分类原样返回，不能显示成「未命名」"
    assert AC.en_name("cs.ZZ") == ""


def test_is_known_and_archive_helpers():
    assert AC.is_known("cs.DB") is True
    assert AC.is_known(" cs.DB ") is True, "轻量查询也要容忍首尾空白"
    assert AC.is_known("cs.ZZ") is False
    assert AC.is_known("") is False
    assert AC.archive_label("cs") == "计算机科学"
    assert AC.archive_label("nope") == "nope", "未知 archive 原样返回"
    assert AC.archive_info("math")["id"] == "math"
    assert AC.archive_info("nope") is None


# ------------------------------------------------------------------ 校验

@pytest.mark.parametrize("cat", ["cs.DB", "quant-ph", "cond-mat.stat-mech",
                                 "physics.acc-ph", "math.LO", "q-bio.BM"])
def test_validate_accepts_legal_categories(cat):
    ok, norm, msg = AC.validate(cat)
    assert ok and norm == cat and msg == ""


def test_validate_trims_whitespace_and_inner_spaces():
    assert AC.validate("  cs.DB  ")[1] == "cs.DB"
    assert AC.validate("cs . DB")[1] == "cs.DB"


@pytest.mark.parametrize("cat", ["", "   ", None])
def test_validate_rejects_empty(cat):
    ok, norm, msg = AC.validate(cat)
    assert not ok and "不能为空" in msg


@pytest.mark.parametrize("cat", ["cs.", ".DB", "cs..DB", "Cs.db", "1cs.DB",
                                 "cs.DB.x", "cs/DB", "-cs.DB"])
def test_validate_rejects_bad_format(cat):
    ok, _, msg = AC.validate(cat)
    assert not ok and ("格式" in msg or "大小写" in msg), (cat, msg)


def test_validate_explains_case_error_with_correct_spelling():
    ok, _, msg = AC.validate("cs.db")
    assert not ok and "区分大小写" in msg and "cs.DB" in msg
    ok, _, msg = AC.validate("CS.DB")
    assert not ok and "cs.DB" in msg


def test_validate_rejects_unknown_archive_with_hint():
    ok, _, msg = AC.validate("css.DB")
    assert not ok and "官方分类" in msg
    assert "你是不是指" in msg or "20 个归档" in msg


def test_validate_near_miss_suggestion_for_typo():
    ok, _, msg = AC.validate("math.LOO")
    assert not ok and "你是不是指" in msg and "math.LO" in msg


def test_validate_suggests_near_miss():
    ok, _, msg = AC.validate("cs.DBB")
    assert not ok and "你是不是指" in msg and "cs.DB" in msg


def test_validate_allow_unknown_only_checks_format():
    """导入别人手改过的旧配置时，只验格式（分类可能已下线）。"""
    ok, norm, msg = AC.validate("cs.LEGACY", allow_unknown=True)
    assert ok and norm == "cs.LEGACY" and msg == ""
    assert not AC.validate("cs.LEGACY")[0]


def test_validate_bare_archive_says_subcategory_is_missing():
    """cs / physics 这类「只写了主类」的输入要给出下一步，而不是只说不对。"""
    ok, _, msg = AC.validate("cs")
    assert not ok and "主类" in msg and "cs.AI" in msg
    ok, _, msg = AC.validate("physics")
    assert not ok and "physics.acc-ph" in msg


def test_validate_returns_the_normalised_id_on_failure():
    """失败时也要把用户输入原样带回，前端才能把它标红。"""
    ok, cat, _ = AC.validate(" cs.ZZ ")
    assert not ok and cat == "cs.ZZ"


# ------------------------------------------------------------------ 检索

def test_search_by_id_prefix_ranks_first():
    hits = AC.search("cs.D")
    assert hits[0]["id"].startswith("cs.D")
    assert {"cs.DB", "cs.DC", "cs.DL", "cs.DM", "cs.DS"} <= {h["id"] for h in hits}


def test_search_by_chinese_and_english_name():
    assert "cs.DB" in [h["id"] for h in AC.search("数据库")]
    assert "cs.DB" in [h["id"] for h in AC.search("databases")]


def test_search_respects_archive_filter_and_limit():
    hits = AC.search("", archive="math")
    assert hits and all(h["archive"] == "math" for h in hits)
    assert len(AC.search("", limit=5)) == 5


def test_search_empty_query_lists_archive_categories():
    assert AC.search("", archive="quant-ph")[0]["id"] == "quant-ph"


def test_search_no_match_returns_empty():
    assert AC.search("zzzz-no-such-thing") == []


def test_suggest_prefers_same_archive():
    near = AC.suggest("cs.DBB")
    assert near and near[0].startswith("cs.")


def test_suggest_empty_input():
    assert AC.suggest("") == []


def test_suggest_returns_exact_spelling_for_case_typo():
    """大小写写错时直接给正确写法，而不是靠相似度猜。"""
    assert AC.suggest("cs.db") == ["cs.DB"]
    assert AC.suggest("CS.DB") == ["cs.DB"]


def test_suggest_ignores_bare_archive_prefix_noise():
    """cs.ZZ 与 cs.SY 只共享 archive 前缀 —— 不该被当成「像」。"""
    assert AC.suggest("cs.ZZ") == []
    assert AC.suggest("cs.DBB") == ["cs.DB"]


def test_suggest_prefix_typo_is_caught():
    assert AC.suggest("css.DB") == ["cs.DB"]


# ------------------------------------------------------------------ 快照

def test_taxonomy_shape():
    t = AC.taxonomy()
    assert set(t) == {"version", "source", "total", "archives"}
    assert t["total"] == AC.TOTAL
    assert t["source"].startswith("https://arxiv.org/")
    assert t["archives"][0]["id"] == "cs"
    assert t["archives"][0]["categories"][0] == {
        "id": "cs.AI", "en": "Artificial Intelligence", "zh": "人工智能"}


def test_taxonomy_is_json_safe_and_detached():
    import json

    t = AC.taxonomy()
    json.dumps(t, ensure_ascii=False)
    t["archives"][0]["categories"][0]["zh"] = "被改了"
    assert AC.CATEGORIES["cs.AI"]["zh"] == "人工智能", "快照必须是副本"


# ------------------------------------------------------------------ 邻域

def test_neighbors_are_siblings_of_same_archives():
    near = AC.neighbors(["cs.DB"])
    assert len(near) == 39, "cs 共 40 个分类，去掉自己剩 39"
    assert "cs.DB" not in near
    assert all(n.startswith("cs.") for n in near)


def test_neighbors_preserve_archive_order_and_dedupe():
    near = AC.neighbors(["math.LO", "cs.DB", "math.CO"])
    assert near[0].startswith("math."), "按所选顺序先处理 math"
    assert near.count("cs.DB") == 0
    assert near.count("math.LO") == 0 and near.count("math.CO") == 0
    assert len(near) == len(set(near))
    # math 段之后才是 cs 段（同一 archive 只出现一次，不因选了两次而重复整段）
    first_cs = next(i for i, c in enumerate(near) if c.startswith("cs."))
    assert all(c.startswith("cs.") for c in near[first_cs:])


def test_neighbors_empty_for_single_part_archive():
    """quant-ph 没有兄弟分类：宁可返回空（本轮无扩展），也不要跨领域乱抓。"""
    assert AC.neighbors(["quant-ph"]) == []


def test_neighbors_limit_and_empty_input():
    assert len(AC.neighbors(["cs.DB"], limit=5)) == 5
    assert AC.neighbors([]) == []
    assert AC.neighbors(["", None]) == []


# ------------------------------------------------------------------ 自检脚本

def test_main_prints_summary(capsys):
    assert AC.main() == 0
    out = capsys.readouterr().out
    assert "arXiv 分类表" in out and "自检通过" in out and "cs" in out
