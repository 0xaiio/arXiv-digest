# -*- coding: utf-8 -*-
"""集成：流水线协议（抓取池 → 推荐 → 渲染 → 归档）。

断言的是**跨模块的契约**，而不是单个函数的返回值：
  raw*.json 的字段契约 → recommend 的产物集合 → build_report 的落盘 → archive 的登记
以及两件容易被改坏的性质：同一天重跑幂等、扩展区兜底。
"""
import json
import re

import pytest

import archive as AR
import build_report as B
import paperutil as pu
import recommend as R

pytestmark = pytest.mark.integration


def _run_pipeline():
    R.main()
    B.main()


def test_pipeline_writes_all_expected_artifacts(seeded):
    _run_pipeline()

    for name in ("recommend.json", "expand.json", "papers_index.json",
                 "issue_core.json", "issue_expand.json", "issue_stats.json",
                 "scores.json", "arxiv_digest_20261015.html",
                 "arxiv_digest_20261015.md", "favorites.html", "archive.html"):
        assert seeded.exists(name), "缺少产物：%s" % name
    assert (seeded.out / "archive" / "20261015.html").exists(), "归档快照未生成"


def test_recommendations_respect_threshold_and_order(seeded):
    R.main()
    recs = seeded.read("recommend.json")
    assert recs, "至少应有一篇过线（p1 命中事务主题 + 熟悉作者）"
    ids = [r["id"] for r in recs]
    assert ids[0] == "2609.10001", "强命中的那篇必须排第一"
    assert "2609.10003" not in ids, "命中降权词的区块链论文不该进推荐"
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True)
    assert all(s >= 7 for s in scores), "推荐区的阈值是 7"


def test_expand_falls_back_when_nothing_passes(seeded):
    """扩展区阈值 9 更严：这批种子数据无人过线，应退化为按分数取前 N。"""
    R.main()
    exp = seeded.read("expand.json")
    assert len(exp) == 2, "兜底应取满 top_expand"
    assert all("画像尚未命中" in (e.get("note") or "") or e["score"] < 9 for e in exp)


def test_issue_core_only_contains_this_issue(seeded):
    R.main()
    doc = seeded.read("issue_core.json")
    assert doc["issue_date"] == "20261015"
    assert {pu.short_id(p) for p in doc["papers"]} == \
        {"2609.10001", "2609.10002", "2609.10003"}


def test_papers_index_carries_rescore_inputs(seeded):
    """前端重排只用 papers_index.json，字段缺一个就会算错分。"""
    R.main()
    idx = seeded.read("papers_index.json")
    assert set(idx) >= {"topics", "weights", "seeds", "kw", "pens", "papers", "expand_ids"}
    assert len(idx["topics"]) == len(idx["weights"]) == len(idx["seeds"])

    by_id = {p["id"]: p for p in idx["papers"]}
    item = by_id["2609.10001"]
    assert set(item) >= {"base", "tv", "toks", "pen"}
    assert item["base"] > 0
    assert item["tv"], "命中了主题就必须带 tv，否则前端重排会把它算成基准分"
    assert all(len(pair) == 2 for pair in item["tv"])


def test_html_contains_three_sections_and_cards(seeded):
    _run_pipeline()
    html = (seeded.out / "arxiv_digest_20261015.html").read_text(encoding="utf-8")

    for marker in ("为你推荐", "兴趣扩展", "分类详解"):
        assert marker in html
    assert 'data-sid="2609.10001"' in html
    assert 'id="rec-list"' in html and 'id="exp-list"' in html
    # 自包含：不应引用外部 CDN
    assert "http://cdn" not in html and "https://cdn" not in html


def test_html_marks_api_base_and_rewrites_links(seeded):
    _run_pipeline()
    html = (seeded.out / "arxiv_digest_20261015.html").read_text(encoding="utf-8")
    assert "file:" in html, "须保留 file:// 打开时的基址改写逻辑"
    assert "/api/favorite" in html and "/api/downvote" in html


def test_markdown_export_lists_recommendations(seeded):
    _run_pipeline()
    md = (seeded.out / "arxiv_digest_20261015.md").read_text(encoding="utf-8")
    assert md.lstrip().startswith("#")
    assert "2609.10001" in md


def test_archive_records_issue_and_marks_seen(seeded):
    _run_pipeline()
    issue = AR.get_issue("20261015")
    assert issue is not None
    assert issue["n_new"] == 3, "本期新增 = 核心池的新论文数"
    assert issue["n_rec"] >= 1
    assert AR.known_sids()["2609.10001"] == "20261015"
    assert AR.known_sids()["2610.20001"] == "20261015", "扩展池也要登记"


def test_same_day_rerun_is_idempotent(seeded):
    _run_pipeline()
    first = seeded.read("issue_core.json")["papers"]
    rec_first = seeded.read("recommend.json")

    _run_pipeline()
    second = seeded.read("issue_core.json")["papers"]
    rec_second = seeded.read("recommend.json")

    assert [p["id"] for p in first] == [p["id"] for p in second], "同日重跑不能清空页面"
    assert [r["id"] for r in rec_first] == [r["id"] for r in rec_second]
    assert len(AR.list_issues()) == 1, "同一日期只应有一期记录"


def test_previous_issue_is_excluded_next_day(seeded, make_paper):
    _run_pipeline()

    fresh = make_paper("2610.30001", "Isolation Level for New Hardware",
                       "isolation level and serializability on new hardware",
                       authors=("Ada Lovelace",),
                       published="2026-10-16T00:00:00Z")
    core = seeded.read("raw.json")
    core["papers"].append(fresh)
    core["newest_seen"] = "2026-10-16"
    core["generated_at"] = "2026-10-16T08:00:00+08:00"
    seeded.write("raw.json", core)

    R.main()
    doc = seeded.read("issue_core.json")
    assert doc["issue_date"] == "20261016"
    assert {pu.short_id(p) for p in doc["papers"]} == {"2610.30001"}, "昨天那三篇不应再出现"


def test_downvote_penalty_removes_paper_from_recommendation(seeded):
    R.main()
    assert "2609.10001" in [r["id"] for r in seeded.read("recommend.json")]

    import profile as PF
    lib = pu.load_library()
    lib["downvotes"]["2609.10001"] = {"title": "x"}
    pu.save_library(lib)
    st = PF.load()
    st["paper_bonus"] = {"2609.10001": -12.0}
    PF.save(st)

    R.main()
    assert "2609.10001" not in [r["id"] for r in seeded.read("recommend.json")], \
        "-12 的惩罚必须把它挤出推荐区"


def test_favorites_page_reflects_library(seeded):
    lib = pu.load_library()
    lib["favorites"]["2609.10001"] = {"id": "2609.10001", "title": "Isolation Level Selection",
                                      "authors": ["Ada Lovelace"], "added_at": "2026-10-15 09:00:00"}
    pu.save_library(lib)

    html = B.build_favorites(pu.load_library())
    assert "Isolation Level Selection" in html
    assert "2609.10001" in html


def test_profile_page_renders_owners_and_themes(seeded):
    html = B.build_profile_page()
    assert "画像主来源" in html
    assert 'data-owner="Ada Lovelace"' in html, "主来源卡片由服务端首屏渲染"
    assert "renderThemes" in html, "主题列表由 /api/customize 的数据在客户端渲染"


def test_archive_page_lists_issues(seeded):
    _run_pipeline()
    html = B.build_archive_page()
    assert "20261015" in html


def test_scores_snapshot_covers_whole_pool(seeded):
    R.main()
    scores = seeded.read("scores.json")
    assert len(scores) == 3, "scores.json 是核心池的全量打分（扩展池另存，索引里只取前 80）"
    assert all("score" in s and "id" in s for s in scores)


def test_issue_stats_counts(seeded):
    R.main()
    stats = seeded.read("issue_stats.json")
    assert stats["issue_date"] == "20261015"
    assert stats["new_core"] == 3 and stats["new_expand"] == 2


# ---------------------------------------------------------------- 双语：简介 / 摘要

def test_card_renders_summary_in_two_languages(seeded):
    """简介的契约：英文在上、中文在下，两行都在。"""
    seeded.write("summaries.json",
                 {"2609.10001": {"en": "We study isolation levels.",
                                 "zh": "研究事务的隔离级别。"}})
    _run_pipeline()
    html = (seeded.out / "arxiv_digest_20261015.html").read_text(encoding="utf-8")
    assert 'class="s-en"' in html and 'class="s-zh"' in html
    assert html.index("We study isolation levels.") < html.index("研究事务的隔离级别。"), \
        "英文必须在中文之上"


def test_legacy_chinese_only_summary_is_treated_as_chinese(seeded):
    """历史单语文件（含汉字）不该被当成英文，也不该要求先迁移。"""
    seeded.write("summaries.json", {"2609.10001": "研究事务的隔离级别。"})
    _run_pipeline()
    html = (seeded.out / "arxiv_digest_20261015.html").read_text(encoding="utf-8")
    assert 'class="s-zh"' in html
    # 英文行缺失时用摘要开头兜底，而不是留空
    assert "We study isolation level and serializability" in html


def test_abstract_is_split_into_en_and_ch_versions(seeded):
    """两个 Abstract 按钮对应两个折叠块：EN 是原文，CH 是中文译文。"""
    seeded.write("abstracts_zh.json", {"2609.10001": "我们研究了事务数据库中的隔离级别。"})
    _run_pipeline()
    html = (seeded.out / "arxiv_digest_20261015.html").read_text(encoding="utf-8")
    assert "Abstract (EN)" in html and "Abstract (CH)" in html
    assert 'id="ab-2609.10001"' in html and 'id="abz-2609.10001"' in html
    assert "我们研究了事务数据库中的隔离级别。" in html


def test_missing_chinese_abstract_shows_a_hint_instead_of_hiding_button(seeded):
    """译文缺失时不隐藏按钮：写明去哪里补，比让按钮消失更可自愈。"""
    _run_pipeline()
    html = (seeded.out / "arxiv_digest_20261015.html").read_text(encoding="utf-8")
    assert 'data-act="abszh"' in html
    assert "abstracts_zh.json" in html


def test_markdown_export_is_bilingual(seeded):
    seeded.write("summaries.json",
                 {"2609.10001": {"en": "We study isolation levels.",
                                 "zh": "研究事务的隔离级别。"}})
    _run_pipeline()
    md = (seeded.out / "arxiv_digest_20261015.md").read_text(encoding="utf-8")
    assert "- EN We study isolation levels." in md
    assert "- 中 研究事务的隔离级别。" in md


def test_papers_index_carries_english_summary(seeded):
    seeded.write("summaries.json",
                 {"2609.10001": {"en": "We study isolation levels.", "zh": "研究事务的隔离级别。"}})
    R.main()
    item = {p["id"]: p for p in seeded.read("papers_index.json")["papers"]}["2609.10001"]
    assert item["summary"] == "研究事务的隔离级别。"
    assert item["summary_en"] == "We study isolation levels."


def test_build_report_is_resilient_to_missing_editorial_files(seeded):
    """summaries / rec_notes / highlights / themes 都是可选编辑内容，缺了也必须能渲染。"""
    for name in ("summaries.json", "rec_notes.json", "highlights.json", "themes.json"):
        assert not seeded.exists(name), "前置条件：这些文件本来就不存在"
    _run_pipeline()
    assert seeded.exists("arxiv_digest_20261015.html")


# ---------------------------------------------------------------- 下载态与 arXiv 入口

def test_downloaded_paper_renders_open_local_file_state(seeded):
    """library.json 里已有的下载，首屏就必须是「已下载 → 打开本地文件」。

    这一条覆盖的是**服务端渲染**：只靠前端 fetch /api/state 回填的话，
    首屏会先闪一下「下载」，禁用 JS 时更是直接错。
    """
    seeded.download_dir.mkdir(parents=True, exist_ok=True)
    target = seeded.download_dir / "arXiv2026 2609.10001 Isolation Level.pdf"
    target.write_bytes(b"%PDF-1.4 test")
    lib = pu.load_library()
    lib["downloads"]["2609.10001"] = {"path": str(target), "at": "now", "title": "T"}
    lib.setdefault("favorites", {})["2609.10001"] = {
        "title": "Isolation Level Selection for Serializable Transactions",
        "primary": "cs.DB", "published": "2026-10-15T00:00:00Z",
        "added_at": "2026-10-15T09:00:00+08:00", "authors": ["Ada Lovelace"]}
    pu.save_library(lib)

    _run_pipeline()
    html = (seeded.out / "arxiv_digest_20261015.html").read_text(encoding="utf-8")

    done = re.findall(r'class="btn dl done" data-act="dl" data-sid="([^"]+)"', html)
    assert set(done) == {"2609.10001"}, "只有库里记录过下载的那篇才该是已下载态"
    assert html.count('title="打开本地文件"') == len(done)
    assert html.count('title="下载 PDF 并自动收藏"'), "其余论文仍应是下载按钮"

    fav = (seeded.out / "favorites.html").read_text(encoding="utf-8")
    assert 'class="btn dl done" data-act="dl" data-sid="2609.10001"' in fav
    assert 'title="打开本地文件"' in fav
    assert 'data-open=' not in fav, "单独的「打开」按钮已合并进「已下载」按钮，别再重复一份"


def test_arxiv_entry_points_at_abs_pages_not_pdf_files(seeded):
    """卡片上的 arXiv 入口指向 /abs/ 论文页，并带品牌字标与外链箭头。"""
    _run_pipeline()
    html = (seeded.out / "arxiv_digest_20261015.html").read_text(encoding="utf-8")
    assert 'href="https://arxiv.org/abs/2609.10001"' in html
    assert 'class="arx-wm"' in html and 'class="ext"' in html
    assert "在 arXiv 上打开论文页" in html
    assert "https://arxiv.org/pdf/2609.10001" not in html.split('class="acts"')[1][:4000], \
        "按钮组里不应再出现直链 PDF 的入口（标题链接仍可指向 PDF）"


# ---------------------------------------------------------------- 通用分类：顺序契约

def test_digest_sections_follow_config_category_order(seeded, make_paper):
    """拖拽排序的效果必须落到页面上：分类小节的顺序 = config.json 的顺序。

    页面的数据来自 raw.json 的抓取快照，顺序来自 config —— 两者不一致时，
    用户拖完顺序会以为「没生效」。这里就是钉住这条链路（config → 页面）。
    """
    core = [make_paper("2609.20001", "DB paper", "isolation level", primary="cs.DB"),
            make_paper("2609.20002", "PL paper", "refinement types", primary="cs.PL")]
    seeded.write("raw.json", {"generated_at": "2026-10-15T08:00:00+08:00",
                              "newest_seen": "2026-10-15", "window_days": 3,
                              "categories": ["cs.DB", "cs.PL"], "papers": core})
    seeded.write("raw_expand.json", {"generated_at": "2026-10-15T08:00:00+08:00",
                                     "newest_seen": "2026-10-15", "window_days": 3,
                                     "categories": [], "papers": []})
    seeded.set_config(categories=["cs.PL", "cs.DB"])
    _run_pipeline()

    html = (seeded.out / "arxiv_digest_20261015.html").read_text(encoding="utf-8")
    assert html.index('id="cat-cs.PL"') < html.index('id="cat-cs.DB"'), \
        "分类小节顺序应与 config.json 一致"

    seeded.set_config(categories=["cs.DB", "cs.PL"])
    _run_pipeline()
    html = (seeded.out / "arxiv_digest_20261015.html").read_text(encoding="utf-8")
    assert html.index('id="cat-cs.DB"') < html.index('id="cat-cs.PL"')


def test_ordered_categories_keeps_snapshot_extras(monkeypatch):
    """config 里没有、但快照里有的分类不能被丢掉（手改过 raw.json 的场景）。"""
    import customize as CZ
    monkeypatch.setattr(CZ, "categories", lambda: ["cs.PL"])
    assert B.ordered_categories(["cs.DB", "cs.PL", "math.LO"]) == \
        ["cs.PL", "cs.DB", "math.LO"]


def test_ordered_categories_without_config_keeps_snapshot_order(monkeypatch):
    import customize as CZ
    monkeypatch.setattr(CZ, "categories", lambda: [])
    assert B.ordered_categories(["cs.DB", "cs.PL"]) == ["cs.DB", "cs.PL"]
    assert B.ordered_categories(None) == []


def test_fresh_install_renders_profile_and_welcome(bare_sandbox):
    """全新克隆（没有任何 config / output）时，引导页与画像页都必须能渲染。

    这是通用版的第一个用户触点：分类为空 → `/` 是引导页 → 点进 `/profile` 选类别。
    任何一步抛异常，新用户看到的都是 500。
    """
    welcome = B.build_welcome()
    assert "/profile" in welcome and "选择要跟踪的 arXiv 分类" in welcome

    html = B.build_profile_page()
    assert "arXiv 类别" in html
    assert 'id="taxdata"' in html, "分类表要内嵌到页面（离线也能开下拉框）"
    assert "cp-arch-btn" in html and "cp-add" in html
    assert bare_sandbox.cfg.exists(), "渲染画像页会顺手把 config.json 初始化出来"
