# -*- coding: utf-8 -*-
"""scoring：打分公式的分解与合成。

这里刻意用「手算一遍」的方式断言数值，而不是复述实现：
公式一旦被改动（哪怕只是把 4.0 写成 5.0），文档、前端展示与排序会一起漂移，
必须有测试把数字钉住。
"""
import pytest

import recommend as R
import scoring as SC

pytestmark = pytest.mark.unit


def _topic(name, weight=1.0, kws=("isolation level",)):
    return {"name": name, "weight": weight, "seed": weight, "custom": False,
            "rx": [SC._rx(k) for k in kws]}


# ------------------------------------------------------------------ 常量

def test_score_constants_match_documented_formula():
    """docs/architecture/ranking.md 里写的数字必须与代码一致。"""
    assert (SC.TITLE_HIT_W, SC.TITLE_HIT_CAP) == (4.0, 4)
    assert (SC.ABS_HIT_W, SC.ABS_HIT_CAP) == (0.8, 15)
    assert (SC.FAMILIAR_W, SC.SYSTEM_W) == (10.0, 6.0)
    assert (SC.NEG_CAP, SC.NEG_SCALE) == (4, 3.0)


# ------------------------------------------------------------------ 主题命中

def test_topic_hits_counts_title_and_abstract_separately(make_paper):
    p = make_paper(title="Isolation Level Matters",
                   abstract="about isolation level and serializability too")
    tv, detail = SC.topic_hits(p, [_topic("T", kws=("isolation level", "serializability"))])
    assert detail[0]["title_hits"] == 1, "标题只命中 isolation level"
    assert detail[0]["abstract_hits"] == 2, "摘要命中两个关键词"
    assert tv == [[0, 4.0 * 1 + 0.8 * 2]]


def test_topic_hits_counts_each_keyword_at_most_once_per_field(make_paper):
    """同一关键词在标题里出现 5 次也只算 1 次 —— 计的是「命中了几个关键词」。"""
    p = make_paper(title="isolation level " * 5, abstract="")
    tv, detail = SC.topic_hits(p, [_topic("T")])
    assert detail[0]["title_hits"] == 1
    assert tv[0][1] == SC.TITLE_HIT_W


def test_topic_hits_caps_hits_per_field(make_paper):
    """一个主题挂 5 个关键词全命中，标题分最多按 4 个计（防关键词堆砌刷分）。"""
    kws = ("alpha", "beta", "gamma", "delta", "epsilon")
    p = make_paper(title="alpha beta gamma delta epsilon", abstract="")
    tv, detail = SC.topic_hits(p, [_topic("T", kws=kws)])
    assert detail[0]["title_hits"] == 5
    assert tv[0][1] == SC.TITLE_HIT_W * SC.TITLE_HIT_CAP


def test_topic_hits_skips_topics_without_any_hit(make_paper):
    p = make_paper(title="Graph Neural Networks", abstract="molecules")
    tv, detail = SC.topic_hits(p, [_topic("T", kws=("isolation level",))])
    assert tv == [] and detail == []


def test_topic_hits_orders_detail_but_keeps_tv_indexed(make_paper):
    p = make_paper(title="isolation level", abstract="linearizability")
    topics = [_topic("weak", kws=("linearizability",)),
              _topic("strong", kws=("isolation level",))]
    tv, detail = SC.topic_hits(p, topics)
    assert [d["topic"] for d in detail] == ["strong", "weak"]
    # tv 里的下标必须指向原始 topics 顺序（score 用它取 weight）
    assert dict((i, raw) for i, raw in tv) == {0: 0.8, 1: 4.0}


# ------------------------------------------------------------------ 静态分

def test_base_score_weights_authors_and_systems(make_paper):
    p = make_paper(authors=("Ada Lovelace", "Alan Turing"))
    base, fam, syshit, neg = SC.base_score(
        p, people=["Ada Lovelace"], systems=["RocksDB"], neg_w=-1.0, neg_rx=[])
    assert fam == ["Ada Lovelace"] and syshit == [] and neg == 0
    assert base == pytest.approx(SC.FAMILIAR_W)


def test_base_score_is_case_insensitive_for_authors(make_paper):
    p = make_paper(authors=("ADA LOVELACE",))
    base, fam, _, _ = SC.base_score(p, ["ada lovelace"], [], -1.0, [])
    assert fam == ["ada lovelace"] and base == SC.FAMILIAR_W


def test_base_score_negative_hits_capped_by_word_count(make_paper):
    """每个降权词只计一次，最多计 4 个词。"""
    words = ("blockchain", "crypto", "nft", "metaverse", "web3")
    p = make_paper(title=" ".join(words), abstract=" ".join(words))
    base, _, _, neg = SC.base_score(p, [], [], -1.0, [SC._rx(w) for w in words])
    assert neg == 5
    assert base == pytest.approx(-1.0 * SC.NEG_CAP * SC.NEG_SCALE)


def test_base_score_negative_weight_scales_linearly(make_paper):
    p = make_paper(title="blockchain", abstract="")
    b1, _, _, _ = SC.base_score(p, [], [], -1.0, [SC._rx("blockchain")])
    b2, _, _, _ = SC.base_score(p, [], [], -2.0, [SC._rx("blockchain")])
    assert b2 == pytest.approx(b1 * 2)


# ------------------------------------------------------------------ 合成

def test_score_adds_topic_weight_penalty_and_keywords(make_paper, monkeypatch):
    monkeypatch.setattr(SC.PF, "tokens", lambda text: ["alpha", "beta"])
    p = make_paper(title="isolation level", abstract="")
    topics = [_topic("T", weight=1.5)]
    f = SC.features(p, topics, -1.0, [], [], [], {})
    s = SC.score(f, topics, {"alpha": 0.4, "beta": -0.1}, pen=-12.0)
    assert s == pytest.approx(f["base"] + (-12.0) + 4.0 * 1.5 + 0.4 - 0.1)


def test_score_ignores_unknown_tokens(make_paper, monkeypatch):
    monkeypatch.setattr(SC.PF, "tokens", lambda text: ["unknown"])
    p = make_paper(title="", abstract="")
    f = SC.features(p, [], -1.0, [], [], [], {})
    assert SC.score(f, [], {}, pen=0) == pytest.approx(f["base"])


def test_features_is_pure_and_reports_components(make_paper, monkeypatch):
    monkeypatch.setattr(SC.PF, "tokens", lambda text: ["tok"])
    p = make_paper(title="isolation level", abstract="x",
                   authors=("Ada Lovelace",))
    f = SC.features(p, [_topic("T")], -1.0, [], ["Ada Lovelace"], [], {})
    assert set(f) == {"tv", "base", "toks", "detail", "fam", "sys", "neg_hits"}
    assert f["fam"] == ["Ada Lovelace"]
    assert f["detail"][0]["topic"] == "T"


def test_features_accepts_omitted_kwmap(make_paper, monkeypatch):
    """kwmap 不参与 features 计算，省略它必须与显式传等价（向后兼容）。"""
    monkeypatch.setattr(SC.PF, "tokens", lambda text: [])
    p = make_paper()
    assert SC.features(p, [], -1.0, [], [], []) == \
        SC.features(p, [], -1.0, [], [], [], {"x": 1.0})


# ------------------------------------------------------------------ 与 recommend 的契约

def test_recommend_reexports_scoring_functions():
    """拆分后 `recommend.features` 等名字必须仍然可用（外部脚本依赖）。"""
    assert R.features is SC.features
    assert R.score is SC.score
    assert R._rx is SC._rx
    assert R._norm is SC._norm
