# -*- coding: utf-8 -*-
"""趋势分析的核心算法：切词、TF-IDF、球形 k-means、增长检测。

这些函数是整个周报的「判断部分」，一旦漂移，报告会以很专业的样子给出错误方向。
所以这里不测「跑得通」，而是测**性质**：归一化是否成立、簇是否按主题分开、
同一批数据是否给出同一结果、阈值是否真的挡住了小样本噪声。
"""
import math

import pytest

import trend_analysis as T

pytestmark = pytest.mark.unit


def mk(sid, title, abstract, cats=("cs.LG",), primary=None):
    return {"sid": sid, "title": title, "abstract": abstract,
            "cats": list(cats), "primary": primary or cats[0]}


def corpus(n_per=20):
    """三组主题词各 n_per 篇，用来验证聚类能不能分开。"""
    groups = [
        ("agent planning tool retrieval benchmark prompt", "cs.LG"),
        ("query index transaction storage database latency", "cs.DB"),
        ("proof type compiler semantics verification theorem", "cs.PL"),
    ]
    papers = []
    for gi, (words, cat) in enumerate(groups):
        for i in range(n_per):
            text = " ".join(words.split() * 4)
            papers.append(mk("26%02d.%05d" % (gi, i), " ".join(words.split()[:4]), text, (cat,)))
    return papers


def test_tokens_drops_stopwords_and_short_words():
    assert T.tokens("The LLM agent uses a tool") == ["llm", "agent", "tool"]
    assert T.tokens("A B C") == []
    assert T.tokens("") == []


def test_tokens_keeps_hyphenated_terms():
    assert "long-context" in T.tokens("long-context reasoning")


def test_paper_terms_weights_title_twice():
    terms = T.paper_terms({"title": "agent planning", "abstract": "planning"})
    assert terms.count("planning") == 3, "标题词 ×2 + 摘要 ×1"


def test_build_tfidf_vectors_are_unit_length():
    docs = [T.paper_terms(p) for p in corpus(5)]
    vocab, vectors = T.build_tfidf(docs, min_df=2, max_terms=200)
    assert vocab and len(vectors) == len(docs)
    for vec in vectors:
        norm = math.sqrt(sum(w * w for _, w in vec))
        assert abs(norm - 1.0) < 1e-9


def test_build_tfidf_is_deterministic():
    docs = [T.paper_terms(p) for p in corpus(5)]
    a = T.build_tfidf(docs, min_df=2, max_terms=50)
    b = T.build_tfidf(docs, min_df=2, max_terms=50)
    assert a[0] == b[0] and a[1] == b[1]


def test_build_tfidf_handles_empty_input():
    assert T.build_tfidf([], min_df=2) == ([], [])


def test_choose_k_is_bounded():
    assert T.choose_k(0) == 8
    assert 8 <= T.choose_k(3200) <= 20
    assert T.choose_k(10 ** 6) == 20


def test_kmeans_separates_three_topics():
    papers = corpus(20)
    docs = [T.paper_terms(p) for p in papers]
    vocab, vectors = T.build_tfidf(docs, min_df=2)
    labels, centroids = T.spherical_kmeans(vectors, 3, iters=10, dim=len(vocab))
    # 三组各 20 篇，同组同标签、异组异标签 = 完美分离
    groups = [labels[i * 20:(i + 1) * 20] for i in range(3)]
    assert len(set(groups[0])) == 1 and len(set(groups[1])) == 1 and len(set(groups[2])) == 1
    assert len({groups[0][0], groups[1][0], groups[2][0]}) == 3


def test_collapse_small_merges_orphans():
    papers = corpus(10)
    docs = [T.paper_terms(p) for p in papers]
    vocab, vectors = T.build_tfidf(docs, min_df=1)
    labels, centroids = T.spherical_kmeans(vectors, 6, iters=3, dim=len(vocab))
    merged, _ = T.collapse_small(labels, vectors, centroids, min_size=5)
    sizes = {}
    for lab in merged:
        sizes[lab] = sizes.get(lab, 0) + 1
    assert min(sizes.values()) >= 5


def test_zh_label_prefers_known_terms():
    assert T.zh_label([("agent", 0.5), ("retrieval", 0.3)]) == "智能体 / 检索"
    assert T.zh_label([("foobarbaz", 0.4)]) == "foobarbaz"


def test_zh_label_ignores_weak_tail_terms():
    """第 5 位才出现的 llm 不足以把「综述」簇标成「大模型」。"""
    terms = [("participants", 0.40), ("human", 0.30), ("findings", 0.20),
             ("research", 0.15), ("llm", 0.05)]
    assert T.zh_label(terms) == "participants / human"
    strong = [("llm", 0.60), ("agents", 0.30)]
    assert T.zh_label(strong) == "大模型 / 智能体"


def test_category_and_term_counts():
    papers = corpus(3)
    cats = T.category_counts(papers)
    assert cats == {"cs.LG": 3, "cs.DB": 3, "cs.PL": 3}
    terms = T.term_doc_counts(papers, top_n=5)
    assert len(terms) == 5 and all(v == 3 for v in terms.values())


def test_compare_requires_minimum_volume():
    cur = {"agent": 3, "query": 50}
    base = [{"agent": 1, "query": 10}]
    rows = T.compare(cur, base, min_cur=10, min_base=3.0)
    assert [r["key"] for r in rows] == ["query"], "3 篇的小波动不该上榜"


def test_compare_scores_and_sorts():
    cur = {"agent": 90, "query": 20}
    base = [{"agent": 30, "query": 18}]
    rows = T.compare(cur, base, min_cur=10, min_base=3.0)
    assert rows[0]["key"] == "agent"
    assert rows[0]["ratio"] == 3.0 and rows[0]["z"] > 0
    assert rows[1]["z"] < 1


def test_growth_normalizes_by_total():
    """总量腰斩但某方向绝对数持平 = 份额翻倍，必须算增长而不是持平。"""
    cur, base = {"agent": 50}, [{"agent": 50}]
    raw = T.growth(cur, base)
    norm = T.growth(cur, base, cur_total=500, base_totals=[1000])
    assert raw[0]["ratio"] == 1.0
    assert norm[0]["ratio"] == 2.0 and norm[0]["z"] > 0


def test_compare_empty_baseline():
    assert T.compare({"agent": 10}, []) == []


def test_analyze_structure_and_shares():
    data = T.analyze(corpus(15), baseline=[{"cats": {"cs.LG": 10}, "terms": {"agent": 5}}])
    assert data["total"] == 45
    assert data["clusters"] and abs(sum(c["share"] for c in data["clusters"]) - 1.0) < 0.01
    assert data["categories"][0]["count"] >= data["categories"][-1]["count"]
    assert data["growth_up"], "有基线且 agent 类词充足时应该报出增长"
    assert "vectorizer" in data["method"]


# ---------------------------------------------------------------- 代表词质量

def test_lemma_collapses_plural_and_agentic():
    assert T.lemma("agents") == T.lemma("agent") == "agent"
    assert T.lemma("agentic") == "agent"
    assert T.lemma("databases") == "database"
    assert T.lemma("networks") == "network"


def test_select_terms_never_repeats_the_same_concept():
    """agents / agent / agentic 只能占一个位次 —— 这是用户明确点名的缺陷。"""
    papers = [mk("26%02d.%05d" % (0, i),
                 "Agents and agentic workflows with agent tool use",
                 "agents agent agentic tool planning retrieval " * 6,
                 ("cs.AI",)) for i in range(30)]
    terms = [p["term"] for p in T.select_terms(list(range(len(papers))), papers,
                                               [0.0], [], top_n=5)]
    keys = [T.lemma(t) for t in terms]
    assert len(keys) == len(set(keys))
    assert not ({"agents", "agent", "agentic"} <= set(terms))


def test_select_terms_drops_broad_single_words():
    """weights / image / video / algorithm 不能作为独立代表词出现。"""
    papers = [mk("26%02d.%05d" % (0, i),
                 "Image and video model weights",
                 "image video weights algorithm memory " * 6, ("cs.CV",)) for i in range(30)]
    terms = [p["term"] for p in T.select_terms(list(range(len(papers))), papers,
                                               [0.0], [], top_n=5)]
    for bad in ("weights", "image", "video", "algorithm"):
        assert bad not in terms


def test_select_terms_prefers_arxiv_category_word():
    papers = [mk("26%02d.%05d" % (0, i), "Query optimization for storage engines",
                 "query transaction index storage latency " * 6, ("cs.DB",))
              for i in range(30)]
    terms = [p["term"] for p in T.select_terms(list(range(len(papers))), papers,
                                               [0.0], [], top_n=5)]
    assert "数据库" in terms, "主导分类是 cs.DB 时应采用 arXiv 官方分类词"


def test_brief_note_uses_curated_terms_only():
    paper = mk("1", "PACE: Keeping the Right Tokens in the KV Cache",
               "Long-horizon agents need a budget. We keep a small set of tokens.")
    note = T.brief_note(paper)
    assert "KV 缓存" in note and len(note) <= 24
    assert "keeping" not in note.lower(), "词典外的词不该拼进蓝色小字"


def test_brief_note_avoids_nested_tags():
    paper = mk("1", "Agentic Workflows for Enterprise Knowledge",
               "agentic workflow agents knowledge")
    note = T.brief_note(paper)
    parts = [p.strip() for p in note.split("·")]
    for a in parts:
        for b in parts:
            if a != b and a and b:
                assert not (a in b or b in a), "「智能体」与「智能体工作流」不该并列"


def test_term_cloud_is_chinese_and_deduped():
    papers = [mk(str(i), "Agent agents agentic LLM tool", "agent llm tool " * 5)
              for i in range(20)]
    cloud = T.term_cloud(papers, top_n=10)
    assert cloud and all(T.has_cjk(w["text"]) for w in cloud)
    assert len({w["text"] for w in cloud}) == len(cloud)
    assert cloud[0]["weight"] == 1.0


def test_analyze_exposes_cloud_and_three_samples_with_notes():
    data = T.analyze(corpus(12))
    assert data["cloud"], "报告要带全周词云数据"
    for c in data["clusters"]:
        assert len(c["samples"]) == 3
        assert all(s.get("note") for s in c["samples"])
        assert all(s.get("short") for s in c["samples"])
