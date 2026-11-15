# -*- coding: utf-8 -*-
"""周报的取数解析、渲染、归档与历史累积。

这里刻意不联网：解析用一段固定 Atom，主流程用 `--skip-fetch` 走缓存。
网络的正确性由「抓一天真实数据」的冒烟验证，不进单测——单测跑一次要 40 秒
并且依赖 arXiv 的可用性，那不是回归测试该承担的东西。
"""
import json
import os

import pytest

import trend_report as TR

pytestmark = pytest.mark.unit

ISSUE = "20261115"

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>2</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2611.00001v2</id>
    <title>Agent Planning with   Tools</title>
    <summary>We study agent planning
    with tools.</summary>
    <published>2026-11-10T00:00:00Z</published>
    <category term="cs.LG"/><category term="cs.AI"/>
    <arxiv:primary_category term="cs.LG"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2611.00002v1</id>
    <title>Transactional Indexing</title>
    <summary>Query and storage.</summary>
    <published>2026-11-11T00:00:00Z</published>
    <category term="cs.DB"/>
  </entry>
</feed>
"""


def papers(n=24):
    out = []
    groups = [("agent planning tool retrieval", "cs.LG"),
              ("query index transaction storage", "cs.DB")]
    for i in range(n):
        words, cat = groups[i % 2]
        out.append({
            "sid": "2611.%05d" % i,
            "title": " ".join(words.split()[:4]),
            "abstract": " ".join(words.split() * 5),
            "cats": [cat],
            "primary": cat,
        })
    return out


@pytest.fixture
def env(sandbox, monkeypatch):
    monkeypatch.setattr(TR, "OUT", sandbox.out)
    monkeypatch.setattr(TR, "ARCHIVE_DIR", sandbox.out / "trend_archive")
    monkeypatch.setattr(TR, "HISTORY_PATH", sandbox.out / "trend_history.json")
    return TR, sandbox


def seed_cache(sandbox, issue=ISSUE, data=None):
    path = sandbox.out / ("trend_raw_%s.json" % issue)
    payload = papers() if data is None else data
    path.write_text(json.dumps({"issue": issue, "papers": payload},
                               ensure_ascii=False), encoding="utf-8")
    return path


def test_week_window_covers_seven_days_and_skips_lag():
    """窗口必须整体回退：arXiv 只索引已公告论文，周日看最近 7 天会少掉一半。"""
    from datetime import date

    start, end = TR.week_window(date(2026, 11, 15))
    assert (start.isoformat(), end.isoformat()) == ("2026-11-06", "2026-11-12")
    assert (end - start).days == 6
    # lag 可调：lag=0 时窗口就在当天结束
    s0, e0 = TR.week_window(date(2026, 11, 15), lag=0)
    assert e0.isoformat() == "2026-11-15" and s0.isoformat() == "2026-11-09"


def test_parse_feed_extracts_only_needed_fields():
    items, total = TR.parse_feed(FEED)
    assert total == 2 and len(items) == 2
    first = items[0]
    assert first["sid"] == "2611.00001", "要去掉版本号 v2"
    assert first["title"] == "Agent Planning with Tools", "空白要压平"
    assert first["primary"] == "cs.LG" and first["cats"] == ["cs.LG", "cs.AI"]
    assert items[1]["primary"] == "cs.DB", "没有 primary_category 时退到第一个 category"
    assert set(first) >= {"sid", "title", "abstract", "cats", "primary", "published"}


def test_build_html_has_sections_and_escapes(env):
    TR, _ = env
    from datetime import date
    data = {"total": 2, "categories": [{"cat": "cs.LG", "count": 2, "share": 1.0}],
            "clusters": [{"size": 2, "share": 1.0, "terms": ["agent"], "label": "智能体",
                          "samples": [{"sid": "x", "title": "<script>alert(1)</script>"}]}],
            "growth_up": [], "growth_down": [], "cat_growth": [],
            "method": {"vectorizer": "TF-IDF", "cluster": "k-means", "vocab": 10,
                       "growth": "z"}}
    page = TR.build_html(ISSUE, (date(2026, 11, 9), date(2026, 11, 15)), data, 1)
    assert "本周主题分布" in page and "异常增长方向" in page and "分类分布" in page
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


def test_build_md_has_tables(env):
    TR, _ = env
    from datetime import date
    data = {"total": 2, "categories": [{"cat": "cs.DB", "count": 2, "share": 1.0}],
            "clusters": [{"size": 2, "share": 1.0, "terms": ["query", "index"], "label": "查询"}],
            "growth_up": [], "growth_down": [], "cat_growth": [],
            "method": {"vectorizer": "TF-IDF", "cluster": "k", "vocab": 3, "growth": "z"}}
    md = TR.build_md(ISSUE, (date(2026, 11, 9), date(2026, 11, 15)), data, 0)
    assert md.startswith("# arXiv cs.* 本周趋势")
    assert "| 主题 | 篇数 | 占比 | 代表词 |" in md
    assert "| 查询 | 2 |" in md


def test_upsert_week_is_idempotent_and_trimmed(env):
    TR, _ = env
    hist = {"weeks": []}
    for i in range(12):
        TR.upsert_week(hist, "2026%04d" % (i + 1), papers(2))
    assert len(hist["weeks"]) == TR.MAX_BASELINE_WEEKS, "只保留最近 8 周"
    TR.upsert_week(hist, "20260005", papers(4))
    entry = [w for w in hist["weeks"] if w["date"] == "20260005"][0]
    assert entry["total"] == 4, "同日期重跑应覆盖而不是追加"
    assert len([w for w in hist["weeks"] if w["date"] == "20260005"]) == 1


def test_baseline_excludes_current_issue(env):
    TR, _ = env
    hist = {"weeks": [{"date": "20261108", "total": 1, "cats": {}, "terms": {}},
                      {"date": ISSUE, "total": 1, "cats": {}, "terms": {}}]}
    assert [w["date"] for w in TR.baseline_for(hist, ISSUE)] == ["20261108"]


def test_run_with_cache_writes_all_artifacts(env):
    TR, sandbox = env
    seed_cache(sandbox)
    assert TR.run(ISSUE, skip_fetch=True, bootstrap=False) == 0
    assert (sandbox.out / ("arxiv_trend_%s.html" % ISSUE)).is_file()
    assert (sandbox.out / ("arxiv_trend_%s.md" % ISSUE)).is_file()
    assert (sandbox.out / "trend_archive" / ("%s.html" % ISSUE)).is_file()
    assert (sandbox.out / "trend_archive" / ("%s.json" % ISSUE)).is_file()
    hist = json.loads((sandbox.out / "trend_history.json").read_text(encoding="utf-8"))
    assert [w["date"] for w in hist["weeks"]] == [ISSUE]
    assert hist["weeks"][0]["total"] == 24


def test_run_twice_does_not_duplicate_history(env):
    TR, sandbox = env
    seed_cache(sandbox)
    TR.run(ISSUE, skip_fetch=True, bootstrap=False)
    TR.run(ISSUE, skip_fetch=True, bootstrap=False)
    hist = json.loads((sandbox.out / "trend_history.json").read_text(encoding="utf-8"))
    assert len(hist["weeks"]) == 1


def test_run_without_cache_returns_2(env):
    TR, _ = env
    assert TR.run(ISSUE, skip_fetch=True, bootstrap=False) == 2


def test_run_with_empty_cache_returns_2(env):
    TR, sandbox = env
    seed_cache(sandbox, data=[])
    assert TR.run(ISSUE, skip_fetch=True, bootstrap=False) == 2


def test_main_rejects_bad_date(env):
    TR, _ = env
    assert TR.main(["-d", "2026-11-15"]) == 2


def test_main_json_output(env, capsys):
    TR, sandbox = env
    seed_cache(sandbox)
    assert TR.main(["-d", ISSUE, "--skip-fetch", "--no-bootstrap", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["issue"] == ISSUE and payload["total"] == 24
    assert os.path.isfile(payload["files"]["html"])
