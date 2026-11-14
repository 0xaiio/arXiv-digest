# -*- coding: utf-8 -*-
"""bili_upload 的标题公式 / 封面渲染。

回归背景（2026-10-22）
----------------------
`build_title` 曾把「DB·分布式·形式化」写死在字符串里。那期十篇全是
cs.SE / math.OC / cs.CL / cs.CR / cs.AI，标题却宣称是数据库·分布式·形式化 ——
公开可见的错误，且人眼很难在自动流水线里发现（标题长度、格式都"正常"）。
所以这里保留一条断言：**标题里的领域名必须来自当期 papers 的 `cat`**。

回归背景（2026-11-14）
----------------------
标题改为 `{钩子 ≤18 字}｜arXiv 日报 #MMDD`：前半段是点开理由，后半段是系列锚点。
钩子优先取 `video_notes.json` 的 `hook`，缺失时退化为当期领域名 —— 退化档也要能
通过同一套校验，否则流水线会在「模型没写 hook」的那天直接断掉。
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


def test_title_uses_hook_and_badge(BU):
    papers = [{"hook": "把 LLM 推理成本砍到 1/4", "cat": "cs.LG"}] + PAPERS
    t = BU.build_title("20261114", papers)
    assert t == "把 LLM 推理成本砍到 1/4｜arXiv 日报 #1114"


def test_title_falls_back_to_topics_without_hook(BU):
    """没有人工钩子时退化为领域名，但**只能来自当期分类**，且格式仍成立。"""
    t = BU.build_title("20261022", PAPERS)
    assert t == "优化·软件工程｜arXiv 日报 #1022"
    for wrong in ("DB", "分布式", "形式化"):
        assert wrong not in t, "标题出现与当期内容无关的领域：%s" % t


def test_title_without_papers_still_matches_formula(BU):
    assert BU.build_title("20261022") == "本周论文精选｜arXiv 日报 #1022"


def test_hook_is_truncated_to_limit(BU):
    long_hook = "这是一个非常非常长的钩子超过十八个字需要被截断处理的例子"
    hook = BU.clean_hook(long_hook)
    assert len(hook) == BU.HOOK_MAX and hook.endswith("…")
    title = BU.build_title("20261114", [{"hook": long_hook}])
    assert len(title) == BU.HOOK_MAX + len(BU.TITLE_TAG) + 4
    assert title.endswith("｜arXiv 日报 #1114")


def test_hook_whitespace_is_collapsed(BU):
    assert BU.clean_hook("  多余   空白\n换行  ") == "多余 空白 换行"


def test_pick_hook_prefers_first_non_empty(BU):
    papers = [{"hook": ""}, {"hook": "第二个"}, {"hook": "第三个"}]
    assert BU.pick_hook(papers) == "第二个"


def test_issue_badge_is_mmdd(BU):
    assert BU.issue_badge("20261114") == "#1114"
    assert BU.issue_badge("2026-11-14") == "#1114"
    assert BU.issue_badge("") == "#"


def test_title_keeps_series_anchor(BU):
    """系列锚点必须可被正则识别 —— verify_episode 就是按这个形状判定的。"""
    import re

    t = BU.build_title("20261114", [{"hook": "事务隔离可以更便宜", "cat": "cs.DB"}])
    assert re.match(r"^.+｜arXiv 日报 #\d{4}$", t)


def test_tags_carry_actual_topics(BU):
    tags = BU.build_tags(PAPERS)
    assert "arXiv" in tags and "论文解读" in tags
    assert "软件工程" in tags
    assert "数据库" not in tags and "分布式系统" not in tags
    assert len(tags) <= BU.TAG_MAX


def test_unknown_category_is_skipped(BU):
    papers = [{"sid": "x", "cat": "physics.gen-ph"}, {"sid": "y", "cat": "cs.DB"}]
    assert BU.topic_labels(papers) == ["数据库"]
