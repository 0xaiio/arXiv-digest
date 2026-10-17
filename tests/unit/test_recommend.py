# -*- coding: utf-8 -*-
"""recommend：打分公式的逐项验证。

公式本身写在 docs/architecture/ranking.md，这里用固定输入把每一项钉住——
公式改了而文档没改、或前端重排与后端不一致，都能在这里暴露。
"""
import json

import pytest

import paperutil as pu
import profile as PF
import recommend as R

pytestmark = pytest.mark.unit

T1 = {"name": "事务与隔离级别", "weight": 1.5, "seed": 1.5, "custom": False,
      "rx": [R._rx(k) for k in ("isolation level", "serializability", "transaction")]}
T2 = {"name": "一致性模型", "weight": 1.0, "seed": 1.0, "custom": False,
      "rx": [R._rx(k) for k in ("linearizability",)]}


def _p1(make_paper):
    return make_paper(
        "2609.10001",
        "Isolation Level Selection for Serializable Transactions",
        "We study isolation level and serializability in transactional databases "
        "with linearizability guarantees.",
        authors=("Ada Lovelace", "Alan Turing"))


def test_features_splits_static_base_from_weighted_topics(make_paper):
    p = _p1(make_paper)
    f = R.features(p, [T1, T2], -1.0, [R._rx("blockchain")],
                   ["Ada Lovelace"], ["RocksDB"], {})
    # base = 10×1 位熟悉作者 + 6×0 系统 + (-1.0)×3×0 降权词
    assert f["base"] == 10.0
    assert f["fam"] == ["Ada Lovelace"]
    assert f["sys"] == [] and f["neg_hits"] == 0

    raw = {d["topic"]: d["raw"] for d in f["detail"]}
    # T1: 标题命中 "Isolation Level" 1 个；摘要命中 isolation level / serializability 2 个
    #（"transaction" 被词边界挡住：transactional / Transactions 不算）
    assert raw["事务与隔离级别"] == pytest.approx(4 * 1 + 0.8 * 2)
    # T2: 只在摘要命中
    assert raw["一致性模型"] == pytest.approx(0.8)
    assert f["detail"][0]["topic"] == "事务与隔离级别", "detail 按原始分降序"


def test_features_counts_systems_and_negative(make_paper):
    p = make_paper("2609.10003", "Blockchain Consensus on RocksDB",
                   "We use RocksDB for blockchain storage.")
    f = R.features(p, [T1, T2], -1.0, [R._rx("blockchain")], [], ["RocksDB"], {})
    assert f["base"] == pytest.approx(6.0 - 3.0), "+6 系统，降权词 -3"
    assert f["neg_hits"] == 1
    assert f["tv"] == [], "没有命中任何主题"


def test_negative_hits_are_capped_at_four(make_paper):
    """每个降权词只计一次，但最多计 4 个词 —— 防止一篇文章堆满热词被扣成负无穷。"""
    words = ["blockchain", "crypto", "nft", "metaverse", "web3"]
    p = make_paper("2609.10004", "blockchain crypto nft metaverse web3",
                   "blockchain crypto nft metaverse web3")
    f = R.features(p, [], -1.0, [R._rx(w) for w in words], [], [], {})
    assert f["neg_hits"] == 5
    assert f["base"] == pytest.approx(-12.0), "最多按 4 次计：-1.0×3×4"


def test_score_is_base_plus_weighted_topics_plus_keywords(make_paper):
    p = _p1(make_paper)
    f = R.features(p, [T1, T2], -1.0, [], ["Ada Lovelace"], [], {})
    kwmap = {t: 0.5 for t in f["toks"]}
    got = R.score(f, [T1, T2], kwmap, 0.0)

    expect = f["base"] + (4 * 1 + 0.8 * 2) * 1.5 + 0.8 * 1.0 + 0.5 * len(f["toks"])
    assert got == pytest.approx(expect, abs=1e-6)


def test_score_applies_paper_penalty(make_paper):
    p = _p1(make_paper)
    f = R.features(p, [T1, T2], -1.0, [], [], [], {})
    clean = R.score(f, [T1, T2], {}, 0.0)
    punished = R.score(f, [T1, T2], {}, -12.0)
    assert punished == pytest.approx(clean - 12.0)


def test_topic_weight_scales_contribution(make_paper):
    p = _p1(make_paper)
    f = R.features(p, [T1], -1.0, [], [], [], {})
    low = R.score(f, [dict(T1, weight=0.5)], {}, 0.0)
    high = R.score(f, [dict(T1, weight=2.0)], {}, 0.0)
    assert high > low


def test_load_profile_uses_effective_topics_and_multiplier(seeded):
    st = PF.load()
    st["topic_mult"] = {"事务与隔离级别": 2.0}
    PF.save(st)

    prof, topics, neg_w, neg_rx = R.load_profile()
    assert [t["name"] for t in topics][:2] == ["事务与隔离级别", "一致性模型"]
    assert topics[0]["weight"] == pytest.approx(1.5 * 2.0)
    assert topics[0]["seed"] == pytest.approx(1.5)
    assert neg_w == pytest.approx(-1.0)
    assert len(neg_rx) == 1


def test_load_profile_defaults_are_safe(bare_sandbox):
    """画像模板缺 negative / weight 时不能 KeyError —— 新用户第一次跑就会撞上。"""
    bare_sandbox.interests.write_text(json.dumps({"topics": []}), encoding="utf-8")
    prof, topics, neg_w, neg_rx = R.load_profile()
    assert topics == []
    assert neg_w == pytest.approx(-1.0)
    assert neg_rx == []


def test_load_profile_accepts_missing_negative_key(bare_sandbox):
    bare_sandbox.interests.write_text(
        json.dumps({"negative": {"keywords": ["x"]}}), encoding="utf-8")
    _, _, neg_w, neg_rx = R.load_profile()
    assert neg_w == pytest.approx(-1.0), "weight 缺失时回落 -1.0"
    assert len(neg_rx) == 1


def test_rx_matches_multiword_terms_with_separator_variants():
    """多词关键词必须能命中，且空格/连字符/下划线等价（曾在链式 replace 里被写坏）。"""
    rx = R._rx("isolation level")
    assert rx.search("we study isolation level here")
    assert rx.search("isolation-level anomalies")
    assert rx.search("isolation_level anomalies")
    assert not rx.search("isolation levels"), "词边界：复数不命中"
    assert not rx.search("level isolation"), "顺序不可颠倒"


def test_rx_empty_term_never_matches():
    assert not R._rx("").search("anything")
    assert not R._rx("   ").search("anything")


def test_rx_escapes_regex_metacharacters():
    rx = R._rx("c++ (concurrency)")
    assert rx.search("a c++ (concurrency) model")


def test_short_id_used_for_topic_scores(seeded):
    """papers_index 里的 key 必须是短号，前端才能按 data-sid 对上。"""
    assert pu.short_id("http://arxiv.org/abs/2609.10001v1") == "2609.10001"
