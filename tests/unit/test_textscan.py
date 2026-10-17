# -*- coding: utf-8 -*-
"""textscan：纯文本 → 结构化信号。

这些函数原先埋在 customize.py 里，要测它们得先造 config/interests 文件；
现在可以用字符串字面量直接测。
"""
import pytest

import customize as CZ
import textscan as TS

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------ strip_html

def test_strip_html_drops_script_and_style():
    html = "<html><head><style>p{color:red}</style><title>T</title></head>" \
           "<body><script>var x=1;</script><p>Hello</p><div>World</div></body></html>"
    out = TS.strip_html(html)
    assert "color:red" not in out and "var x" not in out
    assert "Hello" in out and "World" in out and "T" in out


def test_strip_html_inserts_line_breaks_for_block_tags():
    out = TS.strip_html("<p>first</p><p>second</p><li>third</li>")
    assert out.splitlines() == ["first", "second", "third"]


def test_strip_html_collapses_whitespace_runs():
    assert TS.strip_html("<p>a     b\t\tc</p>") == "a b c"


def test_strip_html_collapses_blank_lines():
    out = TS.strip_html("<div>a</div><div></div><div></div><div>b</div>")
    assert "\n\n" not in out


def test_strip_html_tolerates_broken_markup():
    """解析失败也要返回已读到的内容 —— 一个坏标签不该毁掉整次来源解析。"""
    assert "hello" in TS.strip_html("<p>hello<b>world")


def test_strip_html_empty_input():
    assert TS.strip_html("") == ""
    assert TS.strip_html(None or "") == ""


def test_strip_html_decodes_entities():
    assert TS.strip_html("<p>a &amp; b &lt;c&gt;</p>") == "a & b <c>"


# ------------------------------------------------------------------ extract_people

def test_extract_people_requires_repetition():
    text = "Ada Lovelace once said. Ada Lovelace again."
    assert TS.extract_people(text, min_count=2) == ["Ada Lovelace"]
    assert TS.extract_people("Ada Lovelace once", min_count=2) == []


def test_extract_people_drops_stopword_pairs():
    """`The Paper` / `Research Group` 这类首词是噪音的配对不能进画像。"""
    text = "The Paper is here. The Paper again."
    assert TS.extract_people(text) == []


def test_extract_people_sorted_by_frequency_then_name():
    text = ("Bob Smith. " * 3) + ("Ann Lee. " * 2) + "Zoe Kim. Zoe Kim."
    assert TS.extract_people(text) == ["Bob Smith", "Ann Lee", "Zoe Kim"]


def test_extract_people_respects_limit():
    text = "Ada Smith. Bob Smith. Cid Smith." * 3
    assert len(TS.extract_people(text, min_count=1, limit=2)) == 2


def test_extract_people_empty_input():
    assert TS.extract_people("") == []
    assert TS.extract_people(None) == []


# ------------------------------------------------------------------ extract_keywords

@pytest.fixture()
def prof():
    return {"topics": [{"name": "T", "keywords": ["serializability"]}],
            "negative": {"keywords": ["blockchain"]}}


def test_extract_keywords_prefers_hyphenated_terms(prof):
    kws = TS.extract_keywords("tee-assisted memory reclamation here", prof)
    assert "tee-assisted" in kws


def test_extract_keywords_rejects_numeric_hyphen_tokens(prof):
    """sub-670 / 2024-01 这类编号不能当术语。"""
    kws = TS.extract_keywords("see sub-670 and 2024-01 for details", prof)
    assert "sub-670" not in kws and "2024-01" not in kws


def test_extract_keywords_skips_existing_and_negative(prof):
    text = "serializability blockchain " * 3
    assert TS.extract_keywords(text, prof) == []


def test_extract_keywords_skips_generic_and_stopwords(prof):
    text = "important performance analysis our results " * 3
    assert TS.extract_keywords(text, prof) == []


def test_extract_keywords_skips_short_tokens(prof):
    assert TS.extract_keywords("abc def ghij " * 5, prof) == []


def test_extract_keywords_title_terms_rank_higher(prof):
    """标题里的长词（>=8 字符）比正文里出现 3 次的词更靠前。"""
    body = "algorithmic verification " * 3 + "quantum supremacy " * 1
    kws = TS.extract_keywords(body, prof, title="quantum supremacy")
    assert kws.index("supremacy") < kws.index("algorithmic")


def test_extract_keywords_respects_limit(prof):
    text = " ".join("token%02d" % i for i in range(30)) * 3
    assert len(TS.extract_keywords(text, prof, limit=5)) == 5


# ------------------------------------------------------------------ matched_topics

def test_matched_topics_orders_by_hit_count(prof):
    prof = {"topics": [
        {"name": "T1", "keywords": ["isolation", "level"]},
        {"name": "T2", "keywords": ["consensus"]},
    ]}
    hits = TS.matched_topics("isolation level consensus", prof)
    assert hits[0] == "T1" and set(hits) == {"T1", "T2"}


def test_matched_topics_returns_empty_when_nothing_hits(prof):
    assert TS.matched_topics("nothing relevant", prof) == []


def test_matched_topics_caps_at_six():
    prof = {"topics": [{"name": "T%d" % i, "keywords": ["kw%d" % i]} for i in range(9)]}
    assert len(TS.matched_topics(" ".join("kw%d" % i for i in range(9)), prof)) == 6


# ------------------------------------------------------------------ 兼容门面

def test_customize_reexports_text_helpers():
    """customize 里的这些名字被 tools / 测试直接用过，不能消失。"""
    for name in ("strip_html", "extract_people", "extract_keywords",
                 "matched_topics", "NAME_PAIR", "NAME_STOP", "GENERIC"):
        assert getattr(CZ, name) is getattr(TS, name)
