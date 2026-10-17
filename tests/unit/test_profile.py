# -*- coding: utf-8 -*-
"""profile：行为学习的状态机。

这是最容易「静默出错」的模块——权重全在 [0.25, 3.0] 与 [-4, 4] 里收敛，
一次错误的符号就会在几天后表现成「推荐全空」。因此这里逐条覆盖：
每种 action 的副作用、上下限裁剪、负向学习的开关差异、流水上限。
"""
import json

import pytest

import profile as PF

pytestmark = pytest.mark.unit


def _paper(make_paper, sid="2609.10001"):
    return make_paper(
        sid,
        "Isolation Level Selection for Serializable Transactions",
        "We study isolation level, serializability and transaction isolation "
        "in shared memory systems.",
        authors=("Ada Lovelace",))


def test_load_defaults_when_missing(sandbox):
    st = PF.load()
    assert st["topic_mult"] == {} and st["kw"] == {}
    assert st["paper_bonus"] == {} and st["counts"] == {}


def test_load_fills_missing_keys(sandbox):
    sandbox.write("profile_state.json", {"topic_mult": {"X": 1.2}})
    st = PF.load()
    assert st["topic_mult"]["X"] == 1.2
    assert st["kw"] == {} and st["paper_bonus"] == {}


def test_tokens_drops_stopwords_and_short_tokens():
    toks = PF.tokens("We propose a new approach for the linearizability of transactions")
    assert "linearizability" in toks
    assert "transactions" in toks
    for junk in ("we", "a", "new", "the", "of", "propose"):
        assert junk not in toks


def test_tokens_caps_at_45():
    text = " ".join("tok%02d" % i for i in range(120))
    assert len(PF.tokens(text)) == 45


def test_tokens_orders_by_frequency():
    toks = PF.tokens("alpha alpha beta beta beta gamma")
    assert toks[0] == "beta" and toks[1] == "alpha"


def test_favorite_raises_topic_mult_and_keyword_weights(seeded, make_paper):
    sid = "2609.10001"
    before = PF.load()
    assert before["topic_mult"] == {}

    st, info = PF.apply_event(sid, "favorite", paper=_paper(make_paper, sid))
    assert "事务与隔离级别" in info["topics"]
    assert st["topic_mult"]["事务与隔离级别"] > 1.0
    assert st["kw"]["isolation"] > 0
    assert st["counts"]["favorite"] == 1
    assert st["paper_bonus"] == {}, "收藏不是惩罚"


def test_download_learns_more_than_abstract(seeded, make_paper):
    """同一篇论文、同一主题：download(1.3) 的增量必须大于 abstract(0.3)。"""
    paper = _paper(make_paper)

    PF.apply_event("2609.10001", "download", paper=paper)
    dl_delta = PF.load()["topic_mult"]["事务与隔离级别"] - 1.0

    PF.save({"topic_mult": {}, "kw": {}, "paper_bonus": {}, "counts": {}})
    PF.apply_event("2609.10001", "abstract", paper=paper)
    ab_delta = PF.load()["topic_mult"]["事务与隔离级别"] - 1.0

    assert dl_delta > ab_delta > 0


def test_downvote_only_penalizes_that_paper(seeded, make_paper):
    """默认配置下 Downvote 不写全局权重——这是「推荐器被带偏」故障的修复点。"""
    st, info = PF.apply_event("2609.10003", "downvote",
                              paper=_paper(make_paper, "2609.10003"))
    assert st["paper_bonus"]["2609.10003"] == PF.DEFAULT_CFG["downvote_paper_penalty"]
    assert st["topic_mult"] == {}, "不得改主题倍率"
    assert st["kw"] == {}, "不得改关键词权重"
    assert info["note"].startswith("negative signal")


def test_downvote_can_learn_negatives_when_enabled(seeded, make_paper):
    seeded.set_profile(behavior={"learn_neg_topics": True, "learn_neg_keywords": True})
    st, _ = PF.apply_event("2609.10001", "downvote", paper=_paper(make_paper))
    assert st["topic_mult"]["事务与隔离级别"] < 1.0, "开关打开后应下调主题"
    assert st["paper_bonus"]["2609.10001"] == -12.0, "论文级惩罚始终生效"


def test_undownvote_clears_penalty(seeded, make_paper):
    PF.apply_event("2609.10001", "downvote", paper=_paper(make_paper))
    st, _ = PF.apply_event("2609.10001", "undownvote", paper=_paper(make_paper))
    assert "2609.10001" not in st["paper_bonus"]


def test_topic_mult_is_clamped_to_range(seeded, make_paper):
    p = _paper(make_paper)
    for _ in range(60):
        st, _ = PF.apply_event("2609.10001", "download", paper=p)
    mult = st["topic_mult"]["事务与隔离级别"]
    assert mult <= PF.DEFAULT_CFG["topic_range"][1]
    assert mult > 2.0, "多次下载应该显著提升（否则学习率/strength 计算有问题）"


def test_keyword_weights_are_clamped(seeded, make_paper):
    p = _paper(make_paper)
    for _ in range(200):
        st, _ = PF.apply_event("2609.10001", "download", paper=p)
    top = max(st["kw"].values())
    assert top <= PF.DEFAULT_CFG["keyword_range"][1]


def test_unknown_action_is_recorded_but_learns_nothing(seeded, make_paper):
    st, info = PF.apply_event("2609.10001", "teleport", paper=_paper(make_paper))
    assert info["weight"] == 0
    assert st["topic_mult"] == {} and st["kw"] == {}
    assert st["counts"]["teleport"] == 1


def test_event_without_paper_only_counts(seeded):
    st, info = PF.apply_event("2609.99999", "favorite")
    assert st["counts"]["favorite"] == 1
    assert st["topic_mult"] == {}
    assert info["topics"] == []


def test_behavior_log_appends(sandbox, seeded, make_paper):
    PF.apply_event("2609.10001", "favorite", paper=_paper(make_paper))
    beh = PF.load_behavior()
    assert len(beh) == 1
    assert beh[0]["action"] == "favorite"
    assert beh[0]["id"] == "2609.10001"


def test_behavior_log_is_capped_at_2000(sandbox):
    PF.save_behavior([{"id": "x%d" % i, "action": "favorite"} for i in range(2100)])
    beh = PF.load_behavior()
    assert len(beh) == 2000
    assert beh[-1]["id"] == "x2099", "保留最近的记录"


def test_weights_multiplies_seed_by_learned_mult(seeded):
    st = PF.load()
    st["topic_mult"] = {"事务与隔离级别": 2.0}
    PF.save(st)
    weights = dict(PF.weights())
    assert weights["事务与隔离级别"] == pytest.approx(1.5 * 2.0, abs=1e-6)


def test_paper_bonus_getter(seeded, make_paper):
    PF.apply_event("2609.10001", "downvote", paper=_paper(make_paper))
    assert PF.paper_bonus("2609.10001") == -12.0
    assert PF.paper_bonus("arXiv:2609.10001v2") == -12.0, "短号需归一化"
    assert PF.paper_bonus("2609.10002") == 0.0


def test_state_file_is_written_atomically(seeded, make_paper):
    PF.apply_event("2609.10001", "favorite", paper=_paper(make_paper))
    assert not (seeded.out / "profile_state.json.tmp").exists()
    data = json.loads((seeded.out / "profile_state.json").read_text(encoding="utf-8"))
    assert data["updated_at"]
