# -*- coding: utf-8 -*-
"""bili_upload 的标题 / 标签必须来自当期入选论文的分类。

回归背景（2026-10-22）
----------------------
`build_title` 曾把「DB·分布式·形式化」写死在字符串里。那期十篇全是
cs.SE / math.OC / cs.CL / cs.CR / cs.AI，标题却宣称是数据库·分布式·形式化 ——
公开可见的错误，且人眼很难在自动流水线里发现（标题长度、格式都"正常"）。
所以这里断言：标题里的每个领域名都必须能在当期 papers 的 `cat` 里找到出处。
"""
import importlib.util
import os

import pytest

pytestmark = pytest.mark.unit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, ".workbuddy", "skills", "bili-auto-upload", "scripts", "bili_upload.py")


def _load():
    spec = importlib.util.spec_from_file_location("bili_upload_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def BU():
    return _load()


PAPERS = [
    {"sid": "2610.29145", "cat": "math.OC"},
    {"sid": "2610.27826", "cat": "cs.SE"},
    {"sid": "2610.29147", "cat": "cs.SE"},
    {"sid": "2610.29767", "cat": "cs.CL"},
    {"sid": "2610.26642", "cat": "cs.CR"},
    {"sid": "2610.28560", "cat": "cs.AI"},
]


def test_topic_labels_follow_paper_order(BU):
    assert BU.topic_labels(PAPERS) == ["优化", "软件工程", "自然语言处理"]


def test_title_has_no_hardcoded_topics(BU):
    t = BU.build_title("20261022", PAPERS)
    assert "20261022" in t and "Top6" in t
    for wrong in ("DB", "分布式", "形式化"):
        assert wrong not in t, "标题出现与当期内容无关的领域：%s" % t
    for label in ("优化", "软件工程"):
        assert label in t


def test_title_falls_back_without_papers(BU):
    t = BU.build_title("20261022")
    assert t == "arXiv 日报 20261022｜论文精选 Top10 速览"


def test_tags_carry_actual_topics(BU):
    tags = BU.build_tags(PAPERS)
    assert "arXiv" in tags and "论文解读" in tags
    assert "软件工程" in tags
    assert "数据库" not in tags and "分布式系统" not in tags
    assert len(tags) <= BU.TAG_MAX


def test_unknown_category_is_skipped(BU):
    papers = [{"sid": "x", "cat": "physics.gen-ph"}, {"sid": "y", "cat": "cs.DB"}]
    assert BU.topic_labels(papers) == ["数据库"]
