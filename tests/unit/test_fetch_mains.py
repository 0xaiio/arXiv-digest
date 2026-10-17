# -*- coding: utf-8 -*-
"""抓取脚本的 main()：用桩替换网络，验证「写盘契约」与「时间窗/合并」语义。

这里不打真实 arXiv：`fetch` / `get` 都换成返回固定 XML 的函数。
重点看三个容易出错的点：时间窗过滤、累积池并集、无数据时的错误输出。
"""
import json

import pytest

import fetch_arxiv
import fetch_expand
import fetch_rss
import paperutil as pu

pytestmark = pytest.mark.unit


def _atom(sid, published, primary="cs.DB", title="T"):
    return """<entry>
      <id>http://arxiv.org/abs/%s</id>
      <published>%s</published><updated>%s</updated>
      <title>%s</title><summary>S</summary>
      <author><name>Ada Lovelace</name></author>
      <arxiv:primary_category term="%s"/>
      <category term="%s"/>
    </entry>""" % (sid, published, published, title, primary, primary)


def _feed(*entries):
    return ('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" '
            'xmlns:arxiv="http://arxiv.org/schemas/atom">%s</feed>' % "".join(entries))


@pytest.fixture()
def fast_sleep(monkeypatch):
    """抓取脚本每个分类后 sleep(3.5)：测试里必须抹掉。"""
    monkeypatch.setattr(fetch_arxiv.time, "sleep", lambda *_: None)
    monkeypatch.setattr(fetch_expand.time, "sleep", lambda *_: None)
    monkeypatch.setattr(fetch_rss.time, "sleep", lambda *_: None)


# ------------------------------------------------------------------ 主分类

def test_fetch_arxiv_main_writes_window_and_merges(sandbox, monkeypatch, capsys, fast_sleep):
    monkeypatch.setattr(fetch_arxiv, "CATS", ["cs.DB"])
    monkeypatch.setattr(fetch_arxiv, "WINDOW_DAYS", 3)
    monkeypatch.setattr(fetch_arxiv, "fetch", lambda cat, max_results=80: _feed(
        _atom("2609.00001", "2026-10-14T00:00:00Z"),
        _atom("2609.00002", "2026-09-01T00:00:00Z"),   # 超出时间窗
    ))
    # 既有池里有一条更早的，必须保留（只增不删）
    sandbox.write("raw.json", {"papers": [{"id": "http://arxiv.org/abs/2608.99999v1",
                                           "title": "old", "published": "2026-08-01T00:00:00Z"}]})

    fetch_arxiv.main()
    doc = json.loads(capsys.readouterr().out)

    ids = [pu.short_id(p) for p in doc["papers"]]
    assert "2609.00001" in ids
    assert "2609.00002" not in ids, "窗口外的不该进池"
    assert "2608.99999" in ids, "既有条目必须保留（并集语义）"
    assert doc["window_days"] == 3
    assert doc["newest_seen"].startswith("2026-10-14")
    fresh = [p for p in doc["papers"] if pu.short_id(p) == "2609.00001"][0]
    assert fresh["_primary"] == "cs.DB"
    # 老条目缺 primary 也不能让整轮抓取崩掉（曾在此 KeyError）
    old = [p for p in doc["papers"] if pu.short_id(p) == "2608.99999"][0]
    assert old["_primary"] == ""


def test_fetch_arxiv_main_reports_no_data(sandbox, monkeypatch, capsys, fast_sleep):
    monkeypatch.setattr(fetch_arxiv, "CATS", ["cs.DB"])
    monkeypatch.setattr(fetch_arxiv, "fetch", lambda *a, **k: "")
    fetch_arxiv.main()
    assert json.loads(capsys.readouterr().out) == {"error": "no data"}


# ------------------------------------------------------------------ 扩展

def test_fetch_expand_main_filters_core_and_out_of_window(sandbox, monkeypatch, capsys,
                                                          fast_sleep):
    monkeypatch.setattr(fetch_expand, "CORE_CATS", ["cs.DB"])
    monkeypatch.setattr(fetch_expand, "EXPAND_CATS", ["cs.PL", "cs.DB"])
    monkeypatch.setattr(fetch_expand, "WINDOW_DAYS", 3)
    monkeypatch.setattr(fetch_expand, "fetch", lambda q, start=0, max_results=600: _feed(
        _atom("2610.00001", "2026-10-14T00:00:00Z", primary="cs.PL"),
        _atom("2610.00002", "2026-10-14T00:00:00Z", primary="cs.DB"),   # 属于主分类
        _atom("2610.00003", "2026-08-01T00:00:00Z", primary="cs.PL"),   # 窗口外
    ))

    fetch_expand.main()
    doc = json.loads(capsys.readouterr().out)
    ids = [pu.short_id(p) for p in doc["papers"]]
    assert ids == ["2610.00001"]
    assert "cs.DB" not in doc["categories"], "主分类不应出现在扩展分类池里"


def test_fetch_expand_main_reports_no_data(sandbox, monkeypatch, capsys, fast_sleep):
    monkeypatch.setattr(fetch_expand, "CORE_CATS", [])
    monkeypatch.setattr(fetch_expand, "EXPAND_CATS", ["cs.PL"])
    monkeypatch.setattr(fetch_expand, "fetch", lambda *a, **k: "")
    fetch_expand.main()
    assert json.loads(capsys.readouterr().out) == {"error": "no data"}


# ------------------------------------------------------------------ RSS 降级

RSS_FEED = """<?xml version="1.0"?><rss version="2.0"
  xmlns:arxiv="http://arxiv.org/schemas/atom"
  xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
  <item><title>RSS Paper</title><link>http://arxiv.org/abs/2609.50001</link>
    <description>Abstract: about isolation level</description>
    <dc:creator>Ada Lovelace</dc:creator>
    <category>cs.DB</category><arxiv:announce_type>new</arxiv:announce_type>
    <pubDate>Wed, 14 Oct 2026 00:00:00 -0400</pubDate></item>
</channel></rss>"""


@pytest.fixture()
def rss_env(sandbox, monkeypatch, fast_sleep):
    monkeypatch.setattr(fetch_rss, "get", lambda cat, retries=3: RSS_FEED)
    sandbox.set_config(categories=["cs.DB"], expand_categories=["cs.PL"])
    return sandbox


def test_rss_dry_run_does_not_write(rss_env, monkeypatch, capsys):
    monkeypatch.setattr(fetch_rss.sys, "argv", ["fetch_rss.py", "--dry"])
    fetch_rss.main()
    out = capsys.readouterr().out
    assert "干跑" in out
    assert not rss_env.exists("raw.json"), "干跑不得落盘"


def test_rss_merges_into_both_pools(rss_env, monkeypatch, capsys):
    rss_env.write("raw.json", {"papers": [{"id": "http://arxiv.org/abs/2609.00009v1",
                                           "title": "kept", "published": "2026-10-13T00:00:00Z"}]})
    monkeypatch.setattr(fetch_rss.sys, "argv", ["fetch_rss.py"])
    fetch_rss.main()

    raw = rss_env.read("raw.json")
    ids = [pu.short_id(p) for p in raw["papers"]]
    assert "2609.50001" in ids, "RSS 条目应并入核心池"
    assert "2609.00009" in ids, "既有条目不能丢"
    assert rss_env.exists("raw_expand.json")
    assert "written" in capsys.readouterr().out


def test_rss_skips_core_papers_in_expand_pool(rss_env, monkeypatch):
    monkeypatch.setattr(fetch_rss.sys, "argv", ["fetch_rss.py"])
    fetch_rss.main()
    exp = rss_env.read("raw_expand.json")
    assert all(p["primary"] not in ("cs.DB",) for p in exp["papers"])
