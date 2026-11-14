# -*- coding: utf-8 -*-
"""封面必须由 Pillow 设计稿渲染，而不是从视频里抽一帧。

设计约束：
  * 尺寸固定 1146×717（B站封面按 16:9 显示）；
  * 钩子最多两行、按像素折行、放不下时缩字号，不能把结论数字丢掉；
  * 每次渲染写一份 `bili_cover_<issue>.json`，供 verify_episode 对账。
"""
import importlib.util
import json
import os

import pytest

pytestmark = pytest.mark.unit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, ".workbuddy", "skills", "bili-auto-upload", "scripts", "bili_upload.py")


def _load():
    spec = importlib.util.spec_from_file_location("bili_upload_cover", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def BU():
    return _load()


def _measure(width_per_char):
    return lambda s: len(s) * width_per_char


def test_wrap_keeps_short_text_on_one_line(BU):
    lines, complete = BU.wrap_cjk("事务隔离可以更便宜", _measure(40), 760, 2)
    assert lines == ["事务隔离可以更便宜"] and complete


def test_wrap_splits_by_pixel_width(BU):
    lines, complete = BU.wrap_cjk("把 LLM 推理成本砍到 1/4", _measure(40), 400, 2)
    assert complete, "两行放得下就不该截断"
    assert len(lines) == 2
    assert "1/4" in "".join(lines).replace(" ", ""), "折行不能丢掉结论里的数字"


def test_wrap_marks_truncation(BU):
    """三行才放得下时必须给省略号，并且明确告诉调用方「不完整」。"""
    lines, complete = BU.wrap_cjk("一二三四五六七八九十一二三四五六七八", _measure(40), 160, 2)
    assert not complete and lines[-1].endswith("…")


def test_wrap_strips_leading_space(BU):
    """折行点常落在空格上，行首空格在封面上会变成莫名其妙的缩进。"""
    lines, _ = BU.wrap_cjk("Benchmark without supervision", _measure(10), 90, 2)
    assert all(ln == ln.lstrip() for ln in lines)


def test_find_cjk_font(BU):
    font = BU.find_cjk_font(True)
    assert font is None or os.path.isfile(font)


@pytest.mark.parametrize("lines,expect", [
    (["把 LLM 推理成本砍到", "1/4"], 1),
    (["事务隔离可以更便宜"], None),
    (["把 LLM 推理成本砍到", "新方法的若干细节"], None),
    (["短", "很长很长很长很长"], None),
])
def test_accent_line_index(BU, lines, expect):
    """短行 + 长行 = 强调行；两行都长就不该染色，否则整段都是彩色。"""
    assert BU.accent_line_index(lines) == expect


@pytest.fixture
def cover_env(BU, sandbox, monkeypatch):
    monkeypatch.setattr(BU, "OUT", sandbox.out)
    return BU


def _require_font(BU):
    if BU.find_cjk_font(True) is None:
        pytest.skip("本机没有中文字体，跳过渲染用例")
    pytest.importorskip("PIL")


def test_render_cover_writes_a_real_image(cover_env, sandbox):
    BU = cover_env
    _require_font(BU)
    from PIL import Image

    out = sandbox.out / "cover.jpg"
    manifest = BU.render_cover("20261116", "事务隔离可以更便宜", 10,
                               ["数据库", "分布式"], out)
    assert out.is_file() and out.stat().st_size > 10_000
    with Image.open(out) as img:
        assert img.size == (BU.COVER_W, BU.COVER_H)
    assert manifest["renderer"] == "pillow"
    assert manifest["size"] == [BU.COVER_W, BU.COVER_H]
    assert manifest["badge"] == "#1116"
    assert manifest["count"] == 10
    assert "".join(manifest["lines"]).replace(" ", "") == "事务隔离可以更便宜"


def test_render_cover_wraps_long_hook_into_two_lines(cover_env, sandbox):
    BU = cover_env
    _require_font(BU)
    out = sandbox.out / "cover_long.jpg"
    hook = "把 LLM 推理成本砍到 1/4 的新方法"
    manifest = BU.render_cover("20261116", hook, 8, ["机器学习"], out)
    assert 1 <= len(manifest["lines"]) <= 2
    assert "".join(manifest["lines"]).replace(" ", "") == hook.replace(" ", "")


def test_cmd_cover_writes_manifest(cover_env, sandbox, monkeypatch):
    BU = cover_env
    _require_font(BU)
    papers = [
        {"sid": "2611.00001", "cat": "cs.DB", "hook": "事务隔离可以更便宜"},
        {"sid": "2611.00002", "cat": "cs.DC"},
    ]
    monkeypatch.setattr(BU, "resolve_issue", lambda d=None: ("20261116", None, {"papers": papers}))
    ns = type("NS", (), {"date": None})()
    assert BU.cmd_cover(ns) == 0
    assert (sandbox.out / "bili_cover_20261116.jpg").is_file()
    manifest = json.loads((sandbox.out / "bili_cover_20261116.json").read_text(encoding="utf-8"))
    assert manifest["hook"] == "事务隔离可以更便宜"
    assert manifest["topics"] == ["数据库", "分布式"]


def test_cmd_cover_without_papers_fails(cover_env, monkeypatch):
    BU = cover_env
    monkeypatch.setattr(BU, "resolve_issue", lambda d=None: ("20261116", None, {"papers": []}))
    ns = type("NS", (), {"date": None})()
    assert BU.cmd_cover(ns) == 1
