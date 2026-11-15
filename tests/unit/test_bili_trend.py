# -*- coding: utf-8 -*-
"""周报视频的投稿元数据：标题/简介/标签/评论，以及产物路径的隔离。

同一天可能既有日报又有周报，两套产物必须能并存 —— 共用 `bili_meta_<期号>.json`
会让投稿对账读到另一条视频的标题，后果是「verify 永远找不到稿件」。
"""
import importlib.util
import json
import os

import pytest

pytestmark = pytest.mark.unit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, ".workbuddy", "skills", "bili-auto-upload", "scripts", "bili_upload.py")


def _load():
    spec = importlib.util.spec_from_file_location("bili_upload_trend", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def BU():
    return _load()


def data():
    return {
        "issue": "20261115",
        "stats": {"total": 3840, "cats": 86, "clusters": 14, "growth": 4},
        "segments": [
            {"kind": "topic", "rank": 1, "label": "智能体 / 大模型", "terms": ["agents", "agent"],
             "count": 554, "share": 0.1443, "sample": {"sid": "2611.00001", "title": "Agentic"}},
            {"kind": "topic", "rank": 2, "label": "GPU / 内存", "terms": ["gpu"],
             "count": 404, "share": 0.1052, "sample": {"sid": "2611.00002", "title": "GPU"}},
            {"kind": "topic", "rank": 3, "label": "视频", "terms": ["video"],
             "count": 344, "share": 0.0896, "sample": {"sid": "2611.00003", "title": "Video"}},
            {"kind": "growth", "rank": 4,
             "items": [{"key": "reconstruction", "cur": 223, "ratio": 1.25, "z": 3.36}]},
        ],
    }


def test_trend_title_follows_the_same_formula(BU):
    t = BU.build_trend_title("20261115", data())
    assert t == "智能体 / 大模型占 14%｜arXiv 周报 #1115"
    assert len(t.split("｜arXiv 周报 #")[0]) <= BU.HOOK_MAX


def test_trend_title_falls_back_without_topics(BU):
    t = BU.build_trend_title("20261115", {"segments": []})
    assert t == "本周 cs.* 趋势｜arXiv 周报 #1115"


def test_trend_desc_states_numbers(BU):
    d = BU.build_trend_desc("20261115", data())
    assert len(d) <= BU.DESC_MAX
    assert "3840 篇" in d and "14 个主题簇" in d
    assert "reconstruction ×1.25" in d and "每周日 10:00 更新" in d


def test_trend_desc_without_growth(BU):
    doc = data()
    doc["segments"] = [s for s in doc["segments"] if s["kind"] == "topic"]
    assert "无达到门槛的增长方向" in BU.build_trend_desc("20261115", doc)


def test_trend_tags_include_weekly_marker(BU):
    tags = BU.build_trend_tags(data())
    assert "周报" in tags and "arXiv" in tags and "智能体" in tags
    assert len(tags) <= BU.TAG_MAX


def test_trend_comment_lists_topics_and_links(BU):
    c = BU.build_trend_comment("20261115", data())
    assert "智能体 / 大模型（554 篇，14%）" in c
    assert "arxiv.org/abs/2611.00001" in c
    assert "reconstruction ×1.25" in c


def test_paths_are_isolated_between_kinds(BU):
    daily = BU.paths_for("20261115", "daily")
    trend = BU.paths_for("20261115", "trend")
    assert daily["meta"] != trend["meta"]
    assert trend["meta"].name == "bili_trend_meta_20261115.json"
    assert trend["video"].name == "arxiv_trend_20261115.mp4"
    assert daily["video"].name == "arxiv_weekly_20261115.mp4"
    for key in ("meta", "cover", "cover_manifest", "comment", "published", "video"):
        assert daily[key] != trend[key]


def test_kind_of_defaults_to_daily(BU):
    class A:
        pass

    assert BU.kind_of(A()) == "daily"
    A.kind = "trend"
    assert BU.kind_of(A()) == "trend"
