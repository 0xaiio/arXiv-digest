# -*- coding: utf-8 -*-
"""周报视频的数据整理与旁白稿：分段选取、数字口径、片头片尾长度。

周报的旁白是**模板生成**的，所以这里的断言就是「模板有没有说错数字」：
段数、排名、篇数、占比、增长列表都必须能追溯到 `trend_archive/<期号>.json`。
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


def sample(issue="20261115"):
    return {
        "issue": issue,
        "window": {"start": "2026-11-06", "end": "2026-11-12"},
        "total": 3840,
        "generated_at": "2026-11-15T23:54:00",
        "categories": [{"cat": "cs.LG", "count": 900, "share": 0.23}] * 86,
        "clusters": [
            {"size": 554, "share": 0.1443, "label": "智能体 / 大模型",
             "terms": ["agents", "agent", "llm", "agentic", "code"],
             "samples": [{"sid": "2611.00001", "title": "Agentic Workflows"}]},
            {"size": 404, "share": 0.1052, "label": "GPU / 内存",
             "terms": ["gpu", "memory", "weights"], "samples": [{"sid": "2611.00002", "title": "GPU Kernels"}]},
            {"size": 344, "share": 0.0896, "label": "视频",
             "terms": ["video", "image"], "samples": [{"sid": "2611.00003", "title": "Video Models"}]},
        ],
        "growth_up": [
            {"key": "reconstruction", "cur": 223, "base": 178.1, "ratio": 1.25, "z": 3.36},
            {"key": "simulation", "cur": 269, "base": 224.4, "ratio": 1.20, "z": 2.98},
        ],
        "growth_down": [],
    }


def test_pick_segments_topics_then_growth(G):
    segs = G.pick_segments(sample(), k=2)
    assert [s["kind"] for s in segs] == ["topic", "topic", "growth"]
    assert [s["rank"] for s in segs] == [1, 2, 3]
    assert segs[0]["label"] == "智能体 / 大模型" and segs[0]["count"] == 554
    assert segs[2]["items"][0]["key"] == "reconstruction"


def test_pick_segments_sorted_by_size(G):
    data = sample()
    data["clusters"].reverse()
    segs = G.pick_segments(data, k=3)
    sizes = [s["count"] for s in segs if s["kind"] == "topic"]
    assert sizes == sorted(sizes, reverse=True)


def test_notes_cover_every_segment(G):
    segs = G.pick_segments(sample(), k=3)
    notes = G.build_notes(sample(), segs)
    assert set(notes) == {"_intro", "_outro", "t1", "t2", "t3", "t4"}
    for key in ("t1", "t2", "t3", "t4"):
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
    assert "554" in text and "14%" in text and "agents" in text


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


def test_main_writes_data_and_notes(G, sandbox, monkeypatch, capsys):
    data = sample()
    src = sandbox.out / "trend_archive" / "20261115.json"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = sandbox.out / "trend.json"
    notes = sandbox.out / "trend_notes.json"
    monkeypatch.setattr(G, "ARCHIVE", sandbox.out / "trend_archive")
    assert G.main(["-d", "20261115", "--k", "2", "--out", str(out), "--notes", str(notes)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["issue"] == "20261115" and len(doc["segments"]) == 3
    assert doc["stats"]["total"] == 3840 and doc["stats"]["cats"] == 86
    assert json.loads(notes.read_text(encoding="utf-8"))["_intro"]


def test_main_missing_data_returns_2(G, sandbox, monkeypatch):
    monkeypatch.setattr(G, "ARCHIVE", sandbox.out / "trend_archive")
    assert G.main(["-d", "20990101", "--out", str(sandbox.out / "x.json"),
                   "--notes", str(sandbox.out / "y.json")]) == 2

def test_default_segment_count_meets_three_minutes(G):
    """默认段数必须让成片越过 3 分钟：段长锁死 20s，只能靠段数凑时长。"""
    assert G.MIN_SECONDS == 180
    # TOPICS_DEFAULT 是主题段数，加 1 段增长才是总段数
    assert G.estimate_seconds(G.TOPICS_DEFAULT + 1) >= G.MIN_SECONDS


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

