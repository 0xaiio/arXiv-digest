#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arXiv cs.* 周度趋势分析：TF-IDF + 球形 k-means + 增长检测。

这个模块只做**纯计算**：输入是「一批论文的 title / abstract / categories」，
输出是一份可直接渲染的结构化结果，不碰文件、不联网 —— 所以它可以被单测逐条
钉住，也不会因为哪天数据源挂了而把「分析逻辑」和「取数逻辑」一起拖下水。

三个刻意的取舍
--------------
1. **只用标准库**。项目对运行期的承诺是「零依赖」（见 README 的 runtime badge），
   所以这里不用 numpy / sklearn。3200 篇、4000 维、k≈13、8 轮迭代的规模，
   纯 Python 的稀疏点积约几十秒，周更任务完全够用。
2. **确定性**。不随机初始化：用「最远优先」选初始中心，同一批数据永远得到同一
   份报告。周报要能对比、能回归，随机种子会让「本周主题变了」和「这次初始点
   抽歪了」混在一起。
3. **只谈可观测量**。「异常增长」= 本周文档频率 vs 历史周均值，用 z 与倍数双重
   阈值；不引入「热议」「爆款」这类无法验证的措辞。
"""
from __future__ import annotations

import math
import re
from collections import Counter

# 词形规则：小写、至少 3 个字符、允许连字符（long-context / zero-shot）。
TOKEN_RE = re.compile(r"[a-z][a-z0-9\-]{2,}")

# 停用词：英文功能词 + 学术写作里的通用词。
# 后者（paper / method / results …）在每篇摘要里都出现，留着只会把每个簇都染成
# 同一个颜色，对「本周主题分布」没有任何区分度。
STOPWORDS = frozenset("""
a about above after again against all also am an and any are aren as at be because been
before being below between both but by can cannot could did do does doing down during each
few for from further had has have having he her here hers herself him himself his how i if
in into is it its itself just me more most my myself no nor not now of off on once only or
other our ours ourselves out over own same she should so some such than that the their
theirs them themselves then there these they this those through to too under until up very
was we were what when where which while who whom why will with would you your yours
paper papers work works study studies approach approaches method methods technique
techniques framework frameworks system systems model models result results experiment
experiments experimental evaluation evaluations evaluate evaluated analyze analysis
propose proposed proposes present presents introduce introduces show shows shown
demonstrate demonstrates provide provides allow allows enable enables achieve achieves
uses require requires required include includes including rely relies leverage leverages
address addresses lead leads
improve improves improvement high low large small different various several many much
well better best good effective efficient efficiently significant significantly important
key main current future potential general specific given due make makes made taking take
takes toward towards across within without however therefore thus moreover furthermore
new novel existing recent state art one two three first second third single multiple
also can may might must shall using used use based time real world problem problems
solution solutions case cases way ways task tasks setting settings number set sets
data dataset datasets information approachable point points bound bounds every give gives
learning training performance language neural deep optimal upper lower order similar
compared comparison general form forms kind kinds terms term
error errors log logs answer answers common reach reaches understanding
test tests testing whether evidence baseline baselines accuracy trained
four five six seven eight nine ten score scores gain gains matched runs run per
mathrm mathcal mathbb mathbf mathsf frac sqrt leq geq approx equiv varepsilon epsilon
theta alpha beta gamma lambda delta sigma omega omega mu tau phi psi eta rho ell ldots
cdots times cdot sum prod int partial infty forall exists rightarrow leftarrow quad qquad
text textbf textit begin end align equation cite ref caption table figure appendix
""".split())

# 少量高信号词的固定中文译名：只覆盖「一眼能认出来」的方向词，
# 没收录的一律显示英文原词——宁可中英混排，也不硬翻译出一个不像术语的中文名。
TERM_ZH = {
    "llm": "大模型", "llms": "大模型", "transformer": "Transformer",
    "attention": "注意力机制", "agent": "智能体", "agents": "智能体", "agentic": "智能体",
    "rag": "检索增强", "retrieval": "检索", "embedding": "向量表示", "embeddings": "向量表示",
    "reasoning": "推理", "alignment": "对齐", "prompt": "提示词", "prompting": "提示工程",
    "fine-tuning": "微调", "finetuning": "微调", "lora": "LoRA", "distillation": "蒸馏",
    "diffusion": "扩散模型", "generation": "生成", "multimodal": "多模态", "vision": "视觉",
    "video": "视频", "speech": "语音", "code": "代码", "coding": "编程", "program": "程序",
    "compiler": "编译器", "compilation": "编译", "verification": "验证", "verified": "验证",
    "formal": "形式化", "proof": "证明", "proofs": "证明", "theorem": "定理", "logic": "逻辑",
    "type": "类型", "types": "类型", "semantics": "语义", "synthesis": "程序合成",
    "database": "数据库", "databases": "数据库", "query": "查询", "queries": "查询",
    "transaction": "事务", "transactions": "事务", "storage": "存储", "index": "索引",
    "indexing": "索引", "sql": "SQL", "olap": "OLAP", "key-value": "键值存储",
    "distributed": "分布式", "consensus": "共识", "replication": "复制", "fault": "容错",
    "byzantine": "拜占庭", "fault-tolerant": "容错", "partition": "分区",
    "security": "安全", "attack": "攻击", "attacks": "攻击", "privacy": "隐私",
    "adversarial": "对抗", "malware": "恶意软件", "vulnerability": "漏洞",
    "federated": "联邦学习", "quantum": "量子", "robotics": "机器人", "robot": "机器人",
    "graph": "图", "graphs": "图", "recommendation": "推荐", "recommender": "推荐",
    "search": "搜索", "ranking": "排序", "cluster": "聚类", "clustering": "聚类",
    "optimization": "优化", "scheduling": "调度", "latency": "时延",
    "throughput": "吞吐", "memory": "内存", "cache": "缓存", "gpu": "GPU", "kernel": "内核",
    "network": "网络", "networks": "网络", "routing": "路由", "congestion": "拥塞",
    "edge": "边缘计算", "cloud": "云", "serverless": "无服务器",
    "reinforcement": "强化学习", "rl": "强化学习", "transfer": "迁移", "pretraining": "预训练",
    "benchmark": "基准测试", "benchmarks": "基准测试", "evaluation": "评测",
    "hallucination": "幻觉", "safety": "安全对齐", "interpretability": "可解释性",
}

# 通用词到方向的归并：把同义/词形变体并成一个可读方向名（只影响展示，不影响计算）。
TERM_GROUP = {
    "llms": "llm", "llm": "llm", "agentic": "agent", "agents": "agent",
    "embeddings": "embedding", "proofs": "proof", "queries": "query",
    "databases": "database", "compilers": "compiler", "transactions": "transaction",
}


def tokens(text: str) -> list[str]:
    """切词：小写化 → 去掉停用词 → 只留 3 字符以上的词。"""
    return [t for t in TOKEN_RE.findall((text or "").lower()) if t not in STOPWORDS]


def paper_terms(paper: dict) -> list[str]:
    """一篇论文的词序列：标题权重 ×2（标题比摘要更能代表主题），摘要 ×1。"""
    title = tokens(paper.get("title") or "")
    abstract = tokens(paper.get("abstract") or "")
    return title * 2 + abstract


def build_tfidf(docs: list[list[str]], min_df: int = 3, max_terms: int = 4000):
    """构建 TF-IDF 稀疏矩阵。

    返回 `(vocab, vectors)`：vocab 是词表（按文档频率降序，保证确定性），
    vectors 是每篇的 `[(词下标, 权重)]`，已做 L2 归一化，点积即余弦相似度。

    只保留 df 在 `[min_df, 0.5N]` 之间的词：太少是噪声（拼写错误、罕见缩写），
    太多则没有区分度（每篇都出现的词）。
    """
    n = len(docs)
    df = Counter()
    for terms in docs:
        df.update(set(terms))
    if n == 0 or not df:
        return [], []

    upper = max(n * 0.5, min_df + 1)
    keep = [t for t, c in df.items() if min_df <= c <= upper]
    keep.sort(key=lambda t: (-df[t], t))
    vocab = keep[:max_terms]
    index = {t: i for i, t in enumerate(vocab)}
    idf = [math.log((1.0 + n) / (1.0 + df[t])) + 1.0 for t in vocab]

    vectors: list[list[tuple[int, float]]] = []
    for terms in docs:
        counts = Counter(terms)
        vec = []
        for term, c in counts.items():
            i = index.get(term)
            if i is None:
                continue
            vec.append((i, (1.0 + math.log(c)) * idf[i]))
        norm = math.sqrt(sum(w * w for _, w in vec))
        if norm > 0:
            vec = [(i, w / norm) for i, w in vec]
        vectors.append(vec)
    return vocab, vectors


def choose_k(n_docs: int) -> int:
    """簇数：随规模次线性增长，夹在 [8, 20]。3200 篇 → 13 个簇。"""
    return max(8, min(20, int(round(math.sqrt(max(n_docs, 1) / 20.0)))))


def _dot(vec: list[tuple[int, float]], centroid: list[float]) -> float:
    return sum(w * centroid[i] for i, w in vec)


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm > 0 else vec


def seed_centroids(vectors: list[list[tuple[int, float]]], k: int, dim: int) -> list[list[float]]:
    """最远优先（farthest-first）选初始中心，保证确定性。

    先取「向量权重和」最大的一篇（信息量最大），之后每次取「与已选中心的最大
    相似度最小」的一篇 —— 比随机取样更不容易把两个中心放进同一个簇里。
    """
    if not vectors:
        return []
    order = sorted(range(len(vectors)),
                   key=lambda i: (-sum(w for _, w in vectors[i]), i))
    chosen = [order[0]]
    first = _dense(vectors[chosen[0]], dim)
    best_sim = [_dot(vectors[i], first) for i in range(len(vectors))]

    while len(chosen) < min(k, len(vectors)):
        idx = min(range(len(vectors)), key=lambda i: (best_sim[i], i))
        chosen.append(idx)
        for i in range(len(vectors)):
            s = _dot(vectors[i], _dense(vectors[idx], dim))
            if s > best_sim[i]:
                best_sim[i] = s
    return [_dense(vectors[i], dim) for i in chosen]


def _dense(vec: list[tuple[int, float]], dim: int) -> list[float]:
    out = [0.0] * dim
    for i, w in vec:
        out[i] = w
    return out


def spherical_kmeans(vectors: list[list[tuple[int, float]]], k: int,
                     iters: int = 8, dim: int | None = None):
    """球形 k-means：余弦相似度 + 单位球面上的质心。

    返回 `(labels, centroids)`；空簇用「离自己质心最远的点」补位，避免出现空方向。
    """
    n = len(vectors)
    if n == 0:
        return [], []
    dim = dim if dim is not None else (max((i for v in vectors for i, _ in v), default=-1) + 1)
    k = max(1, min(k, n))
    centroids = seed_centroids(vectors, k, dim)
    labels = [-1] * n
    for _ in range(iters):
        changed = False
        for i, vec in enumerate(vectors):
            best, best_sim = 0, -1e9
            for c, cen in enumerate(centroids):
                s = _dot(vec, cen)
                if s > best_sim:
                    best, best_sim = c, s
            if labels[i] != best:
                labels[i] = best
                changed = True
        sums = [[0.0] * dim for _ in centroids]
        for i, vec in enumerate(vectors):
            target = sums[labels[i]]
            for idx, w in vec:
                target[idx] += w
        # 空簇补位：把离自己质心最远的点挪过去，保证每个方向都有代表。
        counts = Counter(labels)
        for c in range(len(centroids)):
            if counts.get(c, 0) == 0:
                far = max(range(n), key=lambda i: -_dot(vectors[i], centroids[labels[i]]))
                labels[far] = c
                counts[c] = 1
                for idx, w in vectors[far]:
                    sums[c][idx] += w
        centroids = [_normalize(s) for s in sums]
        if not changed:
            break
    return labels, centroids


def collapse_small(labels: list[int], vectors: list[list[tuple[int, float]]],
                   centroids: list[list[float]], min_size: int = 8):
    """把小簇并进最近的大簇，避免报告里出现「1 篇论文的主题」。

    球形 k-means 对噪声敏感：空簇补位会把离群点硬拉成新中心，迭代结束时容易留下
    若干 1–3 篇的碎片。周报要的是方向，不是碎片清单，所以在收敛后做一次归并。
    """
    labels = list(labels)
    while True:
        counts = Counter(labels)
        if len(counts) <= 1:
            break
        small = [c for c, n in counts.items() if n < min_size]
        if not small:
            break
        victim = min(small, key=lambda c: (counts[c], c))
        others = [c for c in counts if c != victim]
        for i, lab in enumerate(labels):
            if lab != victim:
                continue
            labels[i] = max(others, key=lambda c: (_dot(vectors[i], centroids[c]), -c))
        dim = len(centroids[0]) if centroids else 0
        sums = [[0.0] * dim for _ in centroids]
        for i, lab in enumerate(labels):
            for idx, w in vectors[i]:
                sums[lab][idx] += w
        centroids = [_normalize(s) for s in sums]
    return labels, centroids


def label_terms(centroid: list[float], vocab: list[str],
                top: int = 6) -> list[tuple[str, float]]:
    """簇的代表词：按质心权重取前 top 个，返回 `[(词, 权重)]`（跳过权重为 0 的维度）。"""
    idx = sorted(range(len(centroid)), key=lambda i: (-centroid[i], i))[:top]
    return [(vocab[i], centroid[i]) for i in idx if centroid[i] > 0]


def zh_label(terms: list[tuple[str, float]]) -> str:
    """把代表词翻成可读方向名：最多取两个可信的词，拼成「智能体 / 检索」。

    只认**排在前 4 且权重不低于首位一半**的词。放宽到任意代表词会出事：
    一个由 participants / human / findings 组成的综述簇，会因为第 6 位恰好是
    `llm` 而被标成「大模型」——看起来专业，实际上指错了东西。
    """
    if not terms:
        return ""
    top_w = terms[0][1] or 1.0
    names = []
    for rank, (term, weight) in enumerate(terms):
        zh = TERM_ZH.get(term)
        if not zh or zh in names:
            continue
        if rank >= 4 or weight < 0.5 * top_w:
            continue
        names.append(zh)
        if len(names) >= 2:
            break
    return " / ".join(names) if names else " / ".join(t for t, _ in terms[:2])


def primary_category(paper: dict) -> str:
    cats = paper.get("cats") or []
    prim = paper.get("primary")
    if prim:
        return prim
    return cats[0] if cats else ""


def category_counts(papers: list[dict]) -> dict[str, int]:
    c = Counter(primary_category(p) for p in papers)
    return {k: v for k, v in c.items() if k}


def term_doc_counts(papers: list[dict], top_n: int = 300) -> dict[str, int]:
    """每个词出现在多少篇里（文档频率），取前 top_n —— 用于跨周对比。"""
    df = Counter()
    for p in papers:
        df.update(set(tokens(p.get("title") or "") + tokens(p.get("abstract") or "")))
    return dict(sorted(df.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n])


def growth(cur: dict[str, int], baseline: list[dict], *,
           cur_total: int | None = None,
           base_totals: list[int] | None = None) -> list[dict]:
    """把一个计数字典与历史周列表对比，返回全部可比项的 z 与倍数（不排序）。

    **按总量归一化**：本期总篇数如果比基线周少 20%，所有方向的绝对计数都会下降，
    直接比绝对数会把「整周变少」误判成「所有方向都在萎缩」。所以把基线的计数按
    `本期总量 / 基线总量` 缩放成「如果这周也是这么多论文，本该出现多少篇」，
    再与本周实测比较 —— 这样报出来的是**份额变化**，而不是总量变化。

    `cur_total` / `base_totals` 缺省时退化为直接比较绝对数（只有老调用方或单测会走到）。
    """
    if not baseline:
        return []
    rows = []
    for key, c in cur.items():
        vals = [float(b.get(key, 0)) for b in baseline]
        if cur_total and base_totals and len(base_totals) == len(baseline) and cur_total > 0:
            vals = [v * (float(cur_total) / float(t or cur_total)) for v, t in zip(vals, base_totals)]
        mean = sum(vals) / len(vals)
        if mean <= 0:
            continue
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        # 方差下限取 sqrt(mean)：泊松型计数的波动本就随均值增长，否则小计数会虚高 z。
        sd = max(math.sqrt(var), math.sqrt(mean))
        rows.append({
            "key": key,
            "cur": c,
            "base": round(mean, 1),
            "ratio": round(c / mean, 2),
            "z": round((c - mean) / sd, 2),
        })
    return rows


def compare(cur: dict[str, int], baseline: list[dict], *, min_cur: int = 10,
            min_base: float = 3.0, top_n: int = 12, sort: str = "desc",
            min_z: float | None = None, min_ratio: float | None = None,
            cur_total: int | None = None,
            base_totals: list[int] | None = None) -> list[dict]:
    """本周 vs 历史周均值的增长信号，带双重门槛。

    判据同时要求「绝对量够大」与「偏离够远」：只用倍数会让 1→5 这种噪声上榜，
    只用 z 会让小样本里的一次抖动看起来像趋势。`min_z` / `min_ratio` 用于"只报
    增长"的场景——否则整体下行的一周会把「跌得最少」的方向排到增长榜第一。
    """
    rows = [r for r in growth(cur, baseline, cur_total=cur_total, base_totals=base_totals)
            if r["cur"] >= min_cur and r["base"] >= min_base]
    if min_z is not None:
        rows = [r for r in rows if r["z"] >= min_z]
    if min_ratio is not None:
        rows = [r for r in rows if r["ratio"] >= min_ratio]
    if sort == "asc":
        rows.sort(key=lambda r: (r["z"], r["cur"], r["key"]))
    else:
        rows.sort(key=lambda r: (-r["z"], -r["cur"], r["key"]))
    return rows[:top_n]


def analyze(papers: list[dict], baseline: list[dict] | None = None,
            k: int | None = None) -> dict:
    """主入口：一批论文 → 结构化趋势结果（供渲染层直接消费）。"""
    n = len(papers)
    kk = k or choose_k(n)
    docs = [paper_terms(p) for p in papers]
    vocab, vectors = build_tfidf(docs)
    labels, centroids = spherical_kmeans(vectors, kk, dim=len(vocab))
    labels, centroids = collapse_small(labels, vectors, centroids,
                                       min_size=max(5, n // 100))

    clusters = []
    used_labels: set[str] = set()
    for c, cen in enumerate(centroids):
        members = [i for i, lab in enumerate(labels) if lab == c]
        if not members:
            continue
        terms = label_terms(cen, vocab)
        names = [t for t, _ in terms]
        label = zh_label(terms)
        if label in used_labels:
            # 两个簇代表词撞车时补第三个词，避免报告里出现两行同名主题。
            extra = next((TERM_ZH.get(t) or t for t, _ in terms[2:] if t not in label), "")
            label = "%s·%s" % (label, extra) if extra else label
        used_labels.add(label)
        # 代表论文：与质心最相似的三篇（vectors 已归一化，点积即余弦）。
        ranked = sorted(members, key=lambda i: (-_dot(vectors[i], cen), i))[:3]
        clusters.append({
            "size": len(members),
            "share": round(len(members) / n, 4) if n else 0.0,
            "terms": names,
            "label": label,
            "samples": [{"sid": papers[i].get("sid") or "",
                         "title": papers[i].get("title") or ""} for i in ranked],
        })
    clusters.sort(key=lambda c: (-c["size"], c["label"]))

    cats = category_counts(papers)
    terms_df = term_doc_counts(papers)
    base_list = baseline or []
    base_totals = [int(b.get("total") or 0) for b in base_list]
    base_cats = [b.get("cats", {}) for b in base_list]
    base_terms = [b.get("terms", {}) for b in base_list]
    return {
        "total": n,
        "clusters": clusters,
        "categories": [{"cat": kk2, "count": v, "share": round(v / n, 4) if n else 0.0}
                       for kk2, v in sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))],
        "growth_up": compare(terms_df, base_terms, min_cur=12, min_base=4.0, top_n=12,
                             min_z=1.5, min_ratio=1.2,
                             cur_total=n, base_totals=base_totals),
        "growth_down": [r for r in compare(
            terms_df, base_terms, min_cur=1, min_base=8.0, top_n=200, sort="asc",
            cur_total=n, base_totals=base_totals) if r["z"] <= -2.0][:6],
        "cat_growth": compare(cats, base_cats, min_cur=20, min_base=20.0, top_n=8,
                              cur_total=n, base_totals=base_totals),
        "method": {
            "vectorizer": "TF-IDF（tf=1+log tf，idf=log((1+N)/(1+df))+1，L2 归一化）",
            "cluster": "球形 k-means（最远优先初始化，%d 簇，8 轮上限）" % kk,
            "vocab": len(vocab),
            "growth": "本周计数 vs 按总量缩放后的历史周均值；z=(c-μ)/max(σ,√μ)，倍数=c/μ",
        },
    }
