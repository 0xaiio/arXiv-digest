# -*- coding: utf-8 -*-
"""verify_episode：把「标题公式 / 封面方案 / 选题约束」变成一道发布前闸门。

这里既验证「合格的一期能通过」，也逐条验证「违规会被抓住」——只测前者的话，
脚本退化成永远返回 0 的摆设，反而比没有检查更危险。
"""
import importlib.util
import json
import os

import pytest

pytestmark = pytest.mark.unit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "tools", "verify_episode.py")
ISSUE = "20261116"


def _load():
    spec = importlib.util.spec_from_file_location("verify_episode_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def V():
    return _load()


@pytest.fixture
def env(V, sandbox, monkeypatch):
    monkeypatch.setattr(V, "OUT", sandbox.out)
    monkeypatch.setattr(V, "PAPERS", sandbox.out / "papers.json")
    return V, sandbox


def _make_jpeg(path, size):
    pytest.importorskip("PIL")
    from PIL import Image

    Image.new("RGB", size, (11, 18, 32)).save(path, "JPEG", quality=90)


def build(env, *, hook="事务隔离可以更便宜", title=None, count=3,
          cats=None, hooks=None, renderer="pillow", size=(1146, 717),
          issue=ISSUE, badge=None):
    """在沙箱里摆好一期产物；参数用来制造各种违规。"""
    V, sandbox = env
    title = title if title is not None else "%s｜arXiv 日报 #1616" % hook
    cats = cats or ["cs.DB", "cs.DC", "cs.SE"]
    hooks = hooks if hooks is not None else [True, False, False]
    papers = [
        {"rank": i + 1, "sid": "2611.%05d" % i, "cat": cats[i % len(cats)],
         "title_en": "2.5× Faster Queries" if hooks[i % len(hooks)] else "A Survey",
         "title_hook": hooks[i % len(hooks)]}
        for i in range(count)
    ]
    (sandbox.out / "papers.json").write_text(
        json.dumps({"issue": issue, "papers": papers}, ensure_ascii=False), encoding="utf-8")

    cover = sandbox.out / ("bili_cover_%s.jpg" % issue)
    _make_jpeg(cover, size)
    manifest = {
        "issue": issue, "renderer": renderer, "size": list(size), "hook": hook,
        "lines": [hook], "badge": badge or ("#" + issue[4:8]),
        "count": count, "topics": ["数据库"], "font": "msyhbd.ttc",
    }
    (sandbox.out / ("bili_cover_%s.json" % issue)).write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (sandbox.out / ("bili_meta_%s.json" % issue)).write_text(json.dumps({
        "issue": issue, "title": title, "hook": hook, "cover": str(cover),
        "cover_manifest": str(sandbox.out / ("bili_cover_%s.json" % issue)),
        "links_total": count,
    }, ensure_ascii=False), encoding="utf-8")
    return V.evaluate(issue)


def _failed_names(rep):
    return [i["check"] for i in rep.failed]


def test_good_episode_passes(env):
    rep, code = build(env)
    assert code == 0 and not rep.failed, _failed_names(rep)
    assert len(rep.items) >= 10


def test_wrong_title_formula_is_caught(env):
    rep, code = build(env, title="arXiv 日报 20261116｜程序语言 Top3 速览")
    assert code == 1 and "标题公式" in _failed_names(rep)


def test_too_long_hook_is_caught(env):
    hook = "这是一个超过十八个字的钩子用来触发长度校验"
    rep, code = build(env, hook=hook)
    assert code == 1 and "钩子长度" in _failed_names(rep)


def test_hook_mismatch_is_caught(env):
    rep, code = build(env, hook="事务隔离可以更便宜",
                      title="另一句话｜arXiv 日报 #1616")
    assert code == 1 and "标题与钩子一致" in _failed_names(rep)


def test_frame_grab_cover_is_caught(env):
    """旧版抽帧封面没有设计清单、尺寸也不对 —— 两种失败都要报出来。"""
    rep, code = build(env, renderer="ffmpeg", size=(1920, 1080))
    names = _failed_names(rep)
    assert code == 1 and "封面非抽帧" in names and "封面尺寸" in names


def test_cover_hook_mismatch_is_caught(env):
    V, sandbox = env
    build(env)
    mf = sandbox.out / ("bili_cover_%s.json" % ISSUE)
    data = json.loads(mf.read_text(encoding="utf-8"))
    data["hook"] = "封面写了别的"
    mf.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rep, code = V.evaluate(ISSUE)
    assert code == 1 and "封面钩子一致" in _failed_names(rep)


def test_category_cap_violation_is_caught(env):
    rep, code = build(env, count=10, cats=["cs.DB"] * 5 + ["cs.SE"] * 5,
                      hooks=[True, False, False, False, False] * 2)
    assert code == 1 and "单分类上限" in _failed_names(rep)


def test_missing_hook_is_caught(env):
    rep, code = build(env, count=3, hooks=[False, False, False])
    assert code == 1 and "至少一篇钩子" in _failed_names(rep)


def test_issue_mismatch_is_caught(env):
    V, sandbox = env
    build(env)
    p = sandbox.out / "papers.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["issue"] = "20261110"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rep, code = V.evaluate(ISSUE)
    assert code == 1 and "期号一致" in _failed_names(rep)


def test_missing_meta_returns_2(env):
    rep, code = env[0].evaluate("20990101")
    assert rep is None and code == 2


def test_jpeg_size_reads_dimensions(env, sandbox):
    V, _ = env
    path = sandbox.out / "probe.jpg"
    _make_jpeg(path, (1146, 717))
    assert V.jpeg_size(path) == (1146, 717)


def test_latest_issue_follows_mtime(env):
    V, sandbox = env
    build(env)
    old = sandbox.out / "bili_meta_20261101.json"
    old.write_text("{}", encoding="utf-8")
    os.utime(old, (1, 1))
    assert V.latest_issue() == ISSUE


def test_text_output_mentions_pass(env, capsys):
    V, _ = env
    rep, code = build(env)
    V.emit_text(rep)
    out = capsys.readouterr().out
    assert "[PASS]" in out and "项通过" in out
