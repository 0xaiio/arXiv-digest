# -*- coding: utf-8 -*-
"""archive：本期新增判定与期次存档。

这是「日报只呈现本期新增」的唯一实现，语义错误的表现是「旧论文重复出现」或
「当天页面莫名清空」，所以覆盖：bootstrap、同日幂等、跨日隔离、期次读写、快照。
"""
import pytest

import archive as AR
import paperutil as pu

pytestmark = pytest.mark.unit


def test_init_creates_database(sandbox):
    assert not AR.exists()
    AR.init()
    assert AR.exists()
    assert (sandbox.out / "archive.db").exists()
    assert AR.stats()["issues"] == 0


def test_known_sids_empty_without_db(sandbox):
    assert AR.known_sids() == {}


def test_mark_seen_keeps_first_date(seeded):
    AR.mark_seen(["2609.10001"], "20261014")
    AR.mark_seen(["2609.10001"], "20261015")
    assert AR.known_sids()["2609.10001"] == "20261014", "首次期次不可被覆盖"


def test_mark_seen_counts_only_new_rows(seeded):
    assert AR.mark_seen(["a", "b"], "20261015") == 2
    assert AR.mark_seen(["a", "c"], "20261015") == 1


def test_filter_new_splits_on_first_date(seeded, pool):
    core, _ = pool()
    AR.mark_seen(["2609.10001"], "20261014")
    new, old = AR.filter_new(core["papers"], "20261015")
    assert [pu.short_id(p).startswith("2609.10002") for p in new]
    assert [pu.short_id(p) for p in old] == ["2609.10001"]


def test_same_day_rerun_is_idempotent(seeded, pool):
    """当天重跑：首次期次 == 本期的论文仍算本期，页面不会被清空。"""
    core, exp = pool()
    nc, ne, mode = AR.filter_issues(core["papers"], exp["papers"], "20261015")
    assert mode == "bootstrap"

    AR.mark_seen([p["id"].rsplit("/", 1)[-1] for p in core["papers"]], "20261015")
    nc2, _, mode2 = AR.filter_issues(core["papers"], exp["papers"], "20261015")
    assert mode2 == "seen"
    assert len(nc2) == len(core["papers"]), "同一天重跑不能把本期论文判成历史"


def test_next_day_only_new_papers(seeded, pool, make_paper):
    core, exp = pool()
    AR.mark_seen(["2609.10001", "2609.10002", "2609.10003",
                  "2610.20001", "2610.20002"], "20261015")

    fresh = make_paper("2610.30001", "A Brand New Paper", published="2026-10-16T00:00:00Z")
    nc, ne, mode = AR.filter_issues([fresh], exp["papers"], "20261016")
    assert mode == "seen"
    assert [pu.short_id(p) for p in nc] == ["2610.30001"]
    assert ne == [], "已见过的扩展论文不能再算新增"


def test_bootstrap_uses_publish_date_not_today(seeded, make_paper):
    """首次启用时，历史论文按各自提交日入档 —— 写成今天的话明天又会变成「新增」。"""
    old = make_paper("2609.00009", published="2026-09-01T00:00:00Z")
    today = make_paper("2609.00010", published="2026-10-15T00:00:00Z")

    nc, ne, mode = AR.filter_issues([old, today], [], "20261015",
                                    bootstrap_date="2026-10-15")
    assert mode == "bootstrap"
    assert [pu.short_id(p) for p in nc] == ["2609.00010"]
    assert AR.known_sids()["2609.00009"] == "20260901"


def test_bootstrap_judges_core_and_expand_together(seeded, make_paper):
    """核心与扩展必须一次判定：分两次调用会让扩展池整批变成「新增」。"""
    core = [make_paper("2609.00001", published="2026-10-15T00:00:00Z")]
    exp = [make_paper("2610.00001", published="2026-09-20T00:00:00Z"),
           make_paper("2610.00002", published="2026-10-15T00:00:00Z")]
    nc, ne, mode = AR.filter_issues(core, exp, "20261015", bootstrap_date="2026-10-15")
    assert mode == "bootstrap"
    assert len(nc) == 1 and len(ne) == 1, "只有提交日等于本期基准的才算新增"
    assert AR.known_sids()["2610.00001"] == "20260920"


def test_record_and_query_issue(seeded):
    rows = [{"sid": "2609.10001", "pool": "core", "is_new": 1, "primary": "cs.DB",
             "title": "T1", "authors": ["Ada Lovelace"], "published": "2026-10-14",
             "score": 21.5, "tier": "必读", "summary": "摘要", "note": "理由",
             "topics": ["事务与隔离级别"], "affil": "Lab", "pdf": "https://x"},
            {"sid": "2610.20001", "pool": "expand", "is_new": 0, "primary": "cs.PL",
             "title": "T2", "authors": [], "published": "2026-10-14"}]
    n = AR.record_issue("20261015", html="20261015.html", md="20261015.md",
                        generated_at="2026-10-15T08:00:00+08:00",
                        newest_seen="2026-10-15", papers=rows,
                        n_new=2, n_core=1, n_rec=1, n_exp=1)
    assert n == 2

    issues = AR.list_issues()
    assert issues[0]["date"] == "20261015"
    assert issues[0]["n_rec"] == 1

    got = AR.get_issue("20261015")
    assert got["n_new"] == 2 and got["html"] == "20261015.html"

    papers = AR.get_papers("20261015")
    assert len(papers) == 2
    assert papers[0]["authors"] == "Ada Lovelace", "作者列表落库时折叠成字符串"
    assert AR.get_papers("20261015", pool="core")[0]["sid"] == "2609.10001"
    assert [p["sid"] for p in AR.get_papers("20261015", only_new=True)] == ["2609.10001"]


def test_record_issue_is_idempotent_per_date(seeded):
    AR.record_issue("20261015", papers=[{"sid": "a"}], n_new=1)
    AR.record_issue("20261015", papers=[{"sid": "b"}], n_new=1)
    assert [p["sid"] for p in AR.get_papers("20261015")] == ["b"], "replace=True 覆盖本期"
    assert AR.stats()["issues"] == 1


def test_latest_issue(seeded):
    assert AR.latest_issue() is None
    AR.record_issue("20261014")
    AR.record_issue("20261015")
    assert AR.latest_issue()["date"] == "20261015"


def test_snapshot_copy_and_lookup(seeded, sandbox):
    html = sandbox.out / "arxiv_digest_20261015.html"
    md = sandbox.out / "arxiv_digest_20261015.md"
    html.write_text("<html>ok</html>", encoding="utf-8")
    md.write_text("# ok", encoding="utf-8")

    hname, mname = AR.archive_digest("20261015", str(html), str(md))
    snap = AR.snapshot_path("20261015", "html")
    assert snap and snap.endswith(hname)
    assert "20261015" in AR.available_dates()
    assert AR.snapshot_path("20260901", "html") is None, "不存在的日期返回 None"


def test_stats_reports_counts(seeded):
    AR.record_issue("20261015", papers=[{"sid": "a"}, {"sid": "b"}])
    st = AR.stats()
    assert st["issues"] == 1 and st["papers"] == 2
