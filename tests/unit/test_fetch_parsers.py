# -*- coding: utf-8 -*-
"""抓取层的纯函数：XML/RSS 解析与「累积池并集合并」。

这些函数是整条链路唯一会接触不可信外部输入的地方，因此用固定 XML 固件覆盖：
字段映射、缺字段、非法 XML、并集语义（**只增不删**）。
"""
import pytest

import fetch_arxiv
import fetch_affil
import fetch_expand
import fetch_rss

pytestmark = pytest.mark.unit


ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2609.09742v2</id>
    <updated>2026-10-15T10:00:00Z</updated>
    <published>2026-10-14T09:00:00Z</published>
    <title>Isolation   Level
      Selection for Transactions</title>
    <summary>We study   isolation level and
      serializability.</summary>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
    <link title="pdf" href="http://arxiv.org/pdf/2609.09742v2"/>
    <arxiv:primary_category term="cs.DB"/>
    <category term="cs.DB"/>
    <category term="cs.LO"/>
    <arxiv:comment>Accepted at VLDB</arxiv:comment>
  </entry>
</feed>
"""

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:arxiv="http://arxiv.org/schemas/atom"
     xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <item>
      <title>Consensus  Revisited</title>
      <link>http://arxiv.org/abs/2609.11111</link>
      <description>arXiv:2609.11111 Announce Type: new
      Abstract: We revisit consensus under partitions.</description>
      <dc:creator>Grace Hopper, Alan Turing</dc:creator>
      <category>cs.DC</category>
      <arxiv:announce_type>new</arxiv:announce_type>
      <pubDate>Wed, 14 Oct 2026 00:00:00 -0400</pubDate>
    </item>
    <item>
      <title>Broken item without link</title>
      <description>nothing useful</description>
    </item>
  </channel>
</rss>
"""


# ------------------------------------------------------------------ Atom

def test_arxiv_parse_maps_all_fields():
    papers = fetch_arxiv.parse(ATOM, "cs.DB")
    assert len(papers) == 1
    p = papers[0]
    assert p["title"] == "Isolation Level Selection for Transactions", "标题需折叠空白"
    assert p["abstract"] == "We study isolation level and serializability."
    assert p["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert p["primary"] == "cs.DB"
    assert p["cats"] == ["cs.DB", "cs.LO"]
    assert p["pdf"] == "http://arxiv.org/pdf/2609.09742v2"
    assert p["comment"] == "Accepted at VLDB"
    assert p["queried_cat"] == "cs.DB"


def test_arxiv_parse_empty_and_malformed():
    assert fetch_arxiv.parse("", "cs.DB") == []
    with pytest.raises(Exception):
        fetch_arxiv.parse("<feed><entry>", "cs.DB")


def test_expand_parse_swallows_malformed_xml():
    """扩展抓取容忍坏 XML（返回空表），不能把整轮抓取炸掉。"""
    assert fetch_expand.parse("<feed><entry>") == []
    assert len(fetch_expand.parse(ATOM)) == 1


def test_expand_build_query_chunks():
    cats = ["cs.%s" % chr(65 + i) for i in range(10)]
    qs = fetch_expand.build_query(cats, chunk=9)
    assert len(qs) == 2
    assert qs[0].count("cat:") == 9 and qs[1].count("cat:") == 1
    assert qs[0].startswith("(") and qs[0].endswith(")")


def test_expand_dt_parses_arxiv_timestamp():
    d = fetch_expand.dt("2026-10-14T09:00:00Z")
    assert d.year == 2026 and d.month == 10 and d.tzinfo is not None


# ------------------------------------------------------------------ 并集合并

def test_merge_pool_is_union_and_never_drops(make_paper):
    from paperutil import short_id

    prev = [make_paper("2609.00001"), make_paper("2609.00002")]
    fresh = [make_paper("2609.00002", title="updated"), make_paper("2609.00003")]
    merged, added = fetch_arxiv.merge_pool(fresh, prev)
    assert len(merged) == 3, "并集：旧的两篇必须保留"
    assert added == 1
    titles = {short_id(p): p["title"] for p in merged}
    assert titles["2609.00002"] == "updated", "同短号以新数据覆盖字段"


def test_merge_pool_with_empty_prev_returns_fresh(make_paper):
    fresh = [make_paper("2609.00001")]
    merged, added = fetch_arxiv.merge_pool(fresh, [])
    assert len(merged) == 1 and added == 1


def test_expand_merge_pool_same_semantics(make_paper):
    prev = [make_paper("2610.00001")]
    fresh = [make_paper("2610.00002")]
    merged, added = fetch_expand.merge_pool(fresh, prev)
    assert len(merged) == 2 and added == 1


# ------------------------------------------------------------------ RSS

def test_rss_parse_extracts_abstract_and_authors():
    papers = fetch_rss.parse(RSS, "cs.DC")
    assert len(papers) == 1, "缺 link 的条目应被跳过"
    p = papers[0]
    assert p["title"] == "Consensus Revisited"
    assert p["abstract"] == "We revisit consensus under partitions."
    assert p["authors"] == ["Grace Hopper", "Alan Turing"]
    assert p["primary"] == "cs.DC"
    assert p["published"].startswith("2026-10-14")
    assert p["_source"] == "rss"


def test_rss_parse_rejects_garbage():
    assert fetch_rss.parse("<rss>", "cs.DC") == []
    assert fetch_rss.parse("<rss><channel></channel></rss>", "cs.DC") == []


def test_rss_merge_adds_and_enriches_without_overwrite(sandbox, make_paper):
    old = make_paper("2609.00001", abstract="", authors=[])
    new_same = make_paper("2609.00001", abstract="filled by rss", authors=["A"])
    new_other = make_paper("2609.00002", published="2026-10-16T00:00:00Z")
    doc = {"papers": [old]}

    out, added = fetch_rss.merge(doc, [new_same, new_other], "test")
    assert added == 1, "只有真正的新短号计数"
    idx = {p["id"].rsplit("/", 1)[-1].replace("v1", ""): p for p in out["papers"]}
    assert idx["2609.00001"]["abstract"] == "filled by rss", "空字段允许补全"
    assert out["newest_seen"].startswith("2026-10-16")
    assert out["papers"][0]["published"] >= out["papers"][-1]["published"], "按提交日倒序"


def test_rss_merge_sets_window_from_config(sandbox, make_paper):
    sandbox.set_config(window_days=5)
    doc, _ = fetch_rss.merge({}, [make_paper("2609.00001",
                                            published="2026-10-16T00:00:00Z")], "t")
    assert doc["window_days"] == 5
    assert doc["cutoff"].startswith("2026-10-11")


# ------------------------------------------------------------------ 作者单位清洗

@pytest.mark.parametrize("raw, expect_not", [
    ("<span>Dept. of CS</span>", "<span>"),
    ("1 Beijing Academy of Sciences", "1 "),
    ("  Spaced   Out  ", "  "),
])
def test_affil_clean_strips_markup_numbers_and_spacing(raw, expect_not):
    assert expect_not not in fetch_affil._clean(raw)


def test_affil_org_detection_is_strict():
    assert fetch_affil._looks_like_org("Beijing Academy of Blockchain and Edge Computing")
    assert fetch_affil._looks_like_org("University of Oxford")
    # 人名、城市、纯数字、太短的都不算机构
    assert not fetch_affil._looks_like_org("Ada Lovelace")
    assert not fetch_affil._looks_like_org("Beijing, China")
    assert not fetch_affil._looks_like_org("12345")
    assert not fetch_affil._looks_like_org("MIT")


def test_affil_acceptable_requires_sane_length():
    """ltx_affiliation 是作者明文标注，判定较宽松：只挡空串、城市串、超长串。"""
    assert fetch_affil._acceptable_affil("Dept. of Computer Science")
    assert fetch_affil._acceptable_affil("Beijing, China")
    assert not fetch_affil._acceptable_affil("")
    assert not fetch_affil._acceptable_affil("Beijing, CA"), "城市+州缩写不是机构"
    assert not fetch_affil._acceptable_affil("x" * 200)


def test_affil_tidy_strips_author_prefix_and_tail():
    got = fetch_affil._tidy_unit(
        "J. Dong, Beijing Academy of Blockchain and Edge Computing (BABEC), "
        "Beijing, China (dong@example.cn)",
        persons=("J. Dong",))
    assert got.startswith("Beijing Academy")
    assert "(" not in got and "@" not in got
