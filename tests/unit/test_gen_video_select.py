# -*- coding: utf-8 -*-
"""选题的两条硬约束：同一 primary 最多 4 篇；至少 1 篇标题自带可读钩子。

这两条不是「建议」而是「可校验的规则」：`tools/verify_episode.py` 会在投稿前
按同一份正则复核。规则若被静默放水，校验脚本就是摆设，所以这里逐条断言。
"""
import importlib.util
import os

import pytest

pytestmark = pytest.mark.unit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "tools", "gen_video_data.py")


def _load():
    spec = importlib.util.spec_from_file_location("gen_video_data_sel", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def G():
    return _load()


def mk(n, cat, score=10.0, title="A Survey of Systems"):
    return {"id": "2611.%05d" % n, "primary": cat, "score": score, "title": title}


@pytest.mark.parametrize("title,expect", [
    ("2.5× Faster Joins", True),
    ("40% Lower Latency", True),
    ("A 1/4-Size Index", True),
    ("Query Optimization without Statistics", True),
    ("Provably Correct Compilation", True),
    ("Zero-Shot Schema Matching", True),
    ("The First BFT Protocol with Reconfiguration", True),
    ("A Survey of Query Optimization", False),
    ("Towards Better Index Structures", False),
])
def test_has_readable_hook(G, title, expect):
    assert G.has_readable_hook(title) is expect


def test_cat_of_fallbacks(G):
    assert G.cat_of({"primary": "cs.DB"}) == "cs.DB"
    assert G.cat_of({"cats": ["cs.DC", "cs.OS"]}) == "cs.DC"
    assert G.cat_of({}) == ""


def test_selection_caps_per_primary(G):
    core = [mk(i, "cs.DB", 60 - i) for i in range(6)] + [mk(10 + i, "cs.SE", 50 - i) for i in range(4)]
    picked, stats = G.select_episode(core, [], 8, 2)
    counts = {}
    for p, _ in picked:
        counts[p["primary"]] = counts.get(p["primary"], 0) + 1
    assert counts["cs.DB"] == G.MAX_PER_PRIMARY, "同一分类必须被截到上限"
    assert len(picked) == 8
    assert stats["max_per_cat"] == G.MAX_PER_PRIMARY


def test_selection_keeps_lane_quotas(G):
    core = [mk(i, "cs.CAT%d" % i, 60 - i) for i in range(10)]
    expand = [mk(100 + i, "cs.EXP%d" % i, 40 - i) for i in range(4)]
    picked, _ = G.select_episode(core, expand, 8, 2)
    lanes = [lane for _, lane in picked]
    assert lanes.count("推荐") == 8 and lanes.count("兴趣扩展") == 2
    assert lanes[:8] == ["推荐"] * 8, "推荐位必须在前面，片内顺序不能乱"


def test_selection_dedupes_overlapping_pools(G):
    """扩展池里常出现与核心池重复的短号，不能因此多占一个片位。"""
    core = [mk(0, "cs.DB", 60), mk(1, "cs.SE", 59)]
    expand = [mk(0, "cs.DB", 60), mk(2, "cs.DC", 50)]
    picked, _ = G.select_episode(core, expand, 2, 2)
    sids = [G.sid_of(p["id"]) for p, _ in picked]
    assert len(sids) == len(set(sids)) == 3


def test_selection_swaps_in_a_hook_paper(G):
    """整期都没钩子时，必须换进一篇有钩子的，哪怕它在扩展池里排在后面。"""
    core = [mk(i, "cs.CAT%d" % i, 60 - i) for i in range(8)]
    expand = [mk(100, "cs.EXP0", 30), mk(101, "cs.EXP1", 29, "2.5× Faster Queries"),
              mk(102, "cs.EXP2", 28)]
    picked, stats = G.select_episode(core, expand, 8, 2)
    assert stats["hooks"] >= 1
    assert any(G.has_readable_hook(p["title"]) for p, _ in picked)
    assert len(picked) == 10, "换片不能改变总篇数"


def test_selection_reports_zero_hooks_when_pool_has_none(G):
    core = [mk(i, "cs.CAT%d" % i, 60 - i) for i in range(10)]
    picked, stats = G.select_episode(core, [], 8, 2)
    assert stats["hooks"] == 0 and len(picked) == 10


def test_selection_respects_cap_when_swapping(G):
    """换片也必须守住分类上限：不能为了凑钩子把某个分类顶到 5 篇。"""
    core = [mk(i, "cs.DB", 60 - i) for i in range(4)] + \
           [mk(10 + i, "cs.SE", 50 - i) for i in range(4)]
    expand = [mk(100 + i, "cs.DB", 40 - i, "2.5× Faster Queries") for i in range(2)]
    picked, stats = G.select_episode(core, expand, 8, 2)
    counts = {}
    for p, _ in picked:
        counts[p["primary"]] = counts.get(p["primary"], 0) + 1
    assert max(counts.values()) <= G.MAX_PER_PRIMARY
