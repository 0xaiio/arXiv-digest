# -*- coding: utf-8 -*-
"""snapshot_episode：每期成品按日期归档，且同一期重跑不丢旧版本。

最核心的两条不变量：
  1. 跨日不覆盖 —— 每天的目录各存一份，昨天的文件不会因为今天再跑一次而消失；
  2. 同期重跑留痕 —— 内容变了就把旧文件收进 `history/`，不是直接覆盖。
"""
import importlib.util
import json
import os

import pytest

pytestmark = pytest.mark.unit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "tools", "snapshot_episode.py")
ISSUE = "20261114"


def _load():
    spec = importlib.util.spec_from_file_location("snapshot_episode_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def S():
    return _load()


@pytest.fixture
def env(S, sandbox, monkeypatch):
    monkeypatch.setattr(S, "OUT", sandbox.out)
    monkeypatch.setattr(S, "EPISODES", sandbox.out / "episodes")
    monkeypatch.setattr(S, "REEL", sandbox.root / "reel")
    return S, sandbox


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def seed(env, issue=ISSUE, shared_issue=None, with_video=True):
    S, sb = env
    _write(sb.out / ("arxiv_digest_%s.html" % issue), "<html>%s</html>" % issue)
    _write(sb.out / ("arxiv_digest_%s.md" % issue), "# digest")
    if with_video:
        _write(sb.out / ("arxiv_weekly_%s.mp4" % issue), "fake-mp4-bytes")
    _write(sb.out / ("bili_meta_%s.json" % issue), json.dumps({"issue": issue}))
    _write(sb.out / ("bili_cover_%s.jpg" % issue), "fake-jpg")
    _write(sb.out / ("bili_cover_%s.json" % issue), "{}")
    _write(sb.out / ("bili_comment_%s.txt" % issue), "1. paper")
    _write(sb.out / "video_notes.json", json.dumps({"_intro": {"narration": "x"}}))
    _write(sb.root / "reel" / "src" / "papers.json",
           json.dumps({"issue": shared_issue or issue, "papers": []}))
    _write(sb.root / "reel" / "src" / "audio.json", json.dumps({"enabled": True}))
    _write(sb.root / "reel" / "public" / "audio" / "p1.mp3", "mp3")
    _write(sb.root / "reel" / "public" / "audio" / "intro.mp3", "mp3")


def test_archives_dated_and_shared_artifacts(env):
    S, sb = env
    seed(env)
    res = S.snapshot(ISSUE)
    assert res["ok"]
    ep = sb.out / "episodes" / ISSUE
    for name in ("digest.html", "digest.md", "video.mp4", "meta.json", "cover.jpg",
                 "cover.json", "comment.txt", "papers.json", "video_notes.json",
                 "audio.json", "audio/p1.mp3", "audio/intro.mp3"):
        assert (ep / name).is_file(), "缺少归档文件：%s" % name
    assert not (ep / "published.json").exists(), "没有的产物不该凭空出现"
    assert (ep / "MANIFEST.json").is_file()


def test_manifest_records_hash_and_source(env):
    S, sb = env
    seed(env)
    S.snapshot(ISSUE)
    m = json.loads((sb.out / "episodes" / ISSUE / "MANIFEST.json").read_text(encoding="utf-8"))
    assert m["issue"] == ISSUE and m["revision"] == 1
    names = {f["name"]: f for f in m["files"]}
    assert names["video.mp4"]["source"].endswith("arxiv_weekly_%s.mp4" % ISSUE)
    assert len(names["video.mp4"]["sha256"]) == 64


def test_second_run_is_idempotent(env):
    S, sb = env
    seed(env)
    S.snapshot(ISSUE)
    res = S.snapshot(ISSUE)
    assert set(res["actions"].values()) == {"same"}
    m = json.loads((sb.out / "episodes" / ISSUE / "MANIFEST.json").read_text(encoding="utf-8"))
    assert m["revision"] == 1 and m["history"] == []


def test_changed_file_is_moved_to_history(env):
    S, sb = env
    seed(env)
    S.snapshot(ISSUE)
    ep = sb.out / "episodes" / ISSUE
    _write(sb.out / ("arxiv_digest_%s.html" % ISSUE), "<html>v2</html>")
    res = S.snapshot(ISSUE)
    assert res["actions"]["digest.html"] == "copied"
    assert (ep / "digest.html").read_text(encoding="utf-8") == "<html>v2</html>"
    hist = list((ep / "history").rglob("digest.html"))
    assert len(hist) == 1 and "v2" not in hist[0].read_text(encoding="utf-8")
    m = json.loads((ep / "MANIFEST.json").read_text(encoding="utf-8"))
    assert m["revision"] == 2 and len(m["history"]) == 1


def test_shared_files_skipped_when_issue_mismatch(env):
    """共享文件属于「当前那一期」，不能塞进别的日期。"""
    S, sb = env
    seed(env, shared_issue="20261110")
    res = S.snapshot(ISSUE)
    ep = sb.out / "episodes" / ISSUE
    assert (ep / "digest.html").is_file(), "带期号的产物照常归档"
    assert not (ep / "papers.json").exists()
    assert not (ep / "audio").exists()
    assert any("不符" in s for s in res["skipped"])


def test_skip_video(env):
    S, sb = env
    seed(env)
    res = S.snapshot(ISSUE, skip_video=True)
    assert "video.mp4" not in res["actions"]
    assert not (sb.out / "episodes" / ISSUE / "video.mp4").exists()
    assert any("skip-video" in s for s in res["skipped"])


def test_missing_required_is_recorded_but_still_archives(env):
    S, sb = env
    _write(sb.out / ("bili_meta_%s.json" % ISSUE), "{}")
    res = S.snapshot(ISSUE)
    assert res["ok"] and set(res["missing"]) == {"digest.html", "video.mp4"}
    assert (sb.out / "episodes" / ISSUE / "meta.json").is_file()


def test_nothing_to_archive(env):
    S, sb = env
    res = S.snapshot(ISSUE)
    assert not res["ok"] and "没有任何可归档的产物" in res["reason"]


def test_dry_run_writes_nothing(env):
    S, sb = env
    seed(env)
    res = S.snapshot(ISSUE, dry_run=True)
    assert res["ok"]
    assert not (sb.out / "episodes" / ISSUE).exists()
    assert set(res["actions"].values()) == {"would-copy"}


def test_latest_issue_by_mtime(env):
    S, sb = env
    seed(env, issue="20261110")
    seed(env, issue="20261114")
    old = sb.out / "arxiv_weekly_20261110.mp4"
    os.utime(old, (1, 1))
    assert S.latest_issue() == "20261114"


def test_normalize_issue(S):
    assert S.normalize_issue("2026-11-14") == "20261114"
    assert S.normalize_issue("") == ""


def test_main_returns_2_when_empty(env, capsys):
    S, _ = env
    assert S.main([]) == 2


def test_main_happy_path(env, capsys):
    S, sb = env
    seed(env)
    assert S.main(["-d", ISSUE]) == 0
    out = capsys.readouterr().out
    assert "期号 %s" % ISSUE in out and (sb.out / "episodes" / ISSUE / "digest.html").is_file()


def test_main_json_output(env, capsys):
    S, sb = env
    seed(env)
    assert S.main(["-d", ISSUE, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["issue"] == ISSUE and payload["ok"]
