# -*- coding: utf-8 -*-
"""周报视频的数据整理与旁白稿：分段选取、数字口径、三篇相关工作、片头片尾长度。

周报的旁白是**模板生成**的，所以这里的断言就是「模板有没有说错数字」：
段数、排名、篇数、占比、增长列表都必须能追溯到 `trend_archive/<期号>.json`。
2026-11-16 起多了两件事：第一段是词云，每段主题要列出三篇代表工作并各带一句说明。
"""
import importlib.util
import json
import os

import pytest

pytestmark = pytest.mark.unit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "tools", "gen_trend_video_data.py")


def _load():
    spec = importlib.util.spec_from_file_location("gen_trend_video_data_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def G():
    return _load()


def _samples(prefix):
    return [
        {"sid": "2611.%s1" % prefix, "title": "Paper %s A" % prefix,
         "short": "Paper %s A" % prefix, "note": "长上下文 · KV 缓存"},
        {"sid": "2611.%s2" % prefix, "title": "Paper %s B" % prefix,
         "short": "Paper %s B" % prefix, "note": "混合专家 · 能耗"},
        {"sid": "2611.%s3" % prefix, "title": "Paper %s C" % prefix,
         "short": "Paper %s C" % prefix, "note": "推理 · 服务系统"},
    ]


def sample(issue="20261115"):
    return {
        "issue": issue,
        "window": {"start": "2026-11-06", "end": "2026-11-12"},
        "total": 3840,
        "generated_at": "2026-11-15T23:54:00",
        "categories": [{"cat": "cs.LG", "count": 900, "share": 0.23}] * 86,
        "cloud": [{"text": "智能体", "count": 520, "weight": 1.0},
                  {"text": "基准测试", "count": 260, "weight": 0.5}],
        "clusters": [
            {"size": 554, "share": 0.1443, "label": "大语言模型 / 智能体",
             "terms": ["大语言模型", "智能体"], "term_weights": [1.0, 0.6],
             "samples": _samples("1")},
            {"size": 404, "share": 0.1052, "label": "混合专家",
             "terms": ["混合专家"], "term_weights": [1.0], "samples": _samples("2")},
            {"size": 344, "share": 0.0896, "label": "计算机视觉",
             "terms": ["计算机视觉"], "term_weights": [1.0], "samples": _samples("3")},
        ],
        "growth_up": [
            {"key": "reconstruction", "cur": 223, "base": 178.1, "ratio": 1.25, "z": 3.36},
            {"key": "simulation", "cur": 269, "base": 224.4, "ratio": 1.20, "z": 2.98},
        ],
        "growth_down": [],
    }


def test_pick_segments_cloud_topics_then_growth(G):
    segs = G.pick_segments(sample(), k=2)
    assert [s["kind"] for s in segs] == ["cloud", "topic", "topic", "growth"]
    assert [s["rank"] for s in segs] == [1, 1, 2, 3]
    assert segs[0]["words"][0]["text"] == "智能体"
    assert segs[1]["label"] == "大语言模型 / 智能体" and segs[1]["count"] == 554
    assert segs[-1]["items"][0]["key"] == "reconstruction"


def test_each_topic_carries_three_annotated_samples(G):
    """「最接近的工作」必须有三篇，且每篇带一句说明（画面上的蓝色小字）。"""
    segs = G.pick_segments(sample(), k=3)
    for s in segs:
        if s["kind"] != "topic":
            continue
        assert len(s["samples"]) == 3
        for p in s["samples"]:
            assert p["sid"] and p["title"] and p["note"]


def test_pick_segments_sorted_by_size(G):
    data = sample()
    data["clusters"].reverse()
    segs = G.pick_segments(data, k=3)
    sizes = [s["count"] for s in segs if s["kind"] == "topic"]
    assert sizes == sorted(sizes, reverse=True)


def test_notes_cover_every_segment(G):
    segs = G.pick_segments(sample(), k=3)
    notes = G.build_notes(sample(), segs)
    assert set(notes) == {"_intro", "_outro", "te1", "t1", "t2", "t3", "t4"}
    for key in ("te1", "t1", "t2", "t3", "t4"):
        assert 20 <= len(notes[key]["narration"]) <= 125


def test_intro_outro_fit_five_seconds(G):
    """片头/片尾各 5 秒（≈20 字）；超了会压进相邻段，两段旁白叠着说。"""
    notes = G.build_notes(sample(), G.pick_segments(sample(), k=3))
    assert len(notes["_intro"]["narration"]) <= 20
    assert len(notes["_outro"]["narration"]) <= 20


def test_topic_narration_quotes_real_numbers(G):
    data = sample()
    notes = G.build_notes(data, G.pick_segments(data, k=1))
    text = notes["t1"]["narration"]
    assert "554" in text and "14%" in text and "大语言模型" in text


def test_topic_narration_lists_three_related_works(G):
    """口播必须把三篇都念出来，而不是只说「画面右侧能看到」。"""
    data = sample()
    notes = G.build_notes(data, G.pick_segments(data, k=1))
    text = notes["t1"]["narration"]
    for name in ("Paper 1 A", "Paper 1 B", "Paper 1 C"):
        assert name in text
    assert text.count("；") == 2, "三篇之间用两个分号分隔"


def test_topic_narration_stays_within_budget(G):
    """20 秒段的上限：超过 120 字会读出 19 秒以上，压到下一段。"""
    data = sample()
    segs = G.pick_segments(data, k=3)
    for key, item in G.build_notes(data, segs).items():
        if key.startswith("t") and key != "te1":
            assert len(item["narration"]) <= 125


def test_growth_narration_mentions_top_direction(G):
    data = sample()
    notes = G.build_notes(data, G.pick_segments(data, k=1))
    text = notes["t2"]["narration"]
    assert "reconstruction" in text and "1.25" in text


def test_growth_narration_handles_empty(G):
    data = sample()
    data["growth_up"] = []
    notes = G.build_notes(data, G.pick_segments(data, k=1))
    assert "没有达到门槛" in notes["t2"]["narration"]


def test_relation_notes_override(G, sandbox, monkeypatch):
    """人工/模型写的说明优先于词典结果：sid 对上就覆盖。"""
    data = sample()
    src = sandbox.out / "trend_archive" / "20261115.json"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rel = sandbox.out / "rel.json"
    rel.write_text(json.dumps({"2611.11": "手写说明一", "2611.12": "手写说明二"},
                              ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(G, "ARCHIVE", sandbox.out / "trend_archive")
    out = sandbox.out / "trend.json"
    assert G.main(["-d", "20261115", "--k", "1", "--out", str(out),
                   "--notes", str(sandbox.out / "n.json"),
                   "--related-notes", str(rel)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    topic = next(s for s in doc["segments"] if s["kind"] == "topic")
    notes = [p["note"] for p in topic["samples"]]
    assert notes[0] == "手写说明一" and notes[1] == "手写说明二"
    assert notes[2] == "推理 · 服务系统", "没覆盖的保持自动结果"


def test_main_writes_data_and_notes(G, sandbox, monkeypatch, capsys):
    data = sample()
    src = sandbox.out / "trend_archive" / "20261115.json"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = sandbox.out / "trend.json"
    notes = sandbox.out / "trend_notes.json"
    monkeypatch.setattr(G, "ARCHIVE", sandbox.out / "trend_archive")
    assert G.main(["-d", "20261115", "--k", "2", "--out", str(out),
                   "--notes", str(notes),
                   "--related-notes", str(sandbox.out / "none.json")]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["issue"] == "20261115" and len(doc["segments"]) == 4
    assert doc["stats"]["total"] == 3840 and doc["stats"]["cats"] == 86
    assert doc["categories"][0]["name"] == "机器学习"
    assert json.loads(notes.read_text(encoding="utf-8"))["_intro"]


def test_main_missing_data_returns_2(G, sandbox, monkeypatch):
    monkeypatch.setattr(G, "ARCHIVE", sandbox.out / "trend_archive")
    assert G.main(["-d", "20990101", "--out", str(sandbox.out / "x.json"),
                   "--notes", str(sandbox.out / "y.json")]) == 2


def test_default_segment_count_meets_three_minutes(G):
    """默认段数必须让成片越过 3 分钟：段长锁死 20s，只能靠段数凑时长。"""
    assert G.MIN_SECONDS == 180
    # 1 段词云 + TOPICS_DEFAULT 个主题 + 1 段增长
    assert G.estimate_seconds(G.TOPICS_DEFAULT + 2) >= G.MIN_SECONDS


def test_short_episode_warns_but_still_writes(G, sandbox, monkeypatch, capsys):
    """主题簇不足时不许悄悄缩短段长，必须给出 warn（后续会被 A/V 闸门拦住）。"""
    data = sample()
    src = sandbox.out / "trend_archive" / "20261115.json"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(G, "ARCHIVE", sandbox.out / "trend_archive")
    rc = G.main(["-d", "20261115", "--k", "2",
                 "--out", str(sandbox.out / "t.json"), "--notes", str(sandbox.out / "n.json")])
    err = capsys.readouterr().err
    assert rc == 0 and "低于 180 秒下限" in err
