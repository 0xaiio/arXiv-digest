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

# 词形归并：周报里 agents / agent / agentic 必须收敛成同一个概念，
# 否则同一簇会并排出「agents、agent、agentic」三个近义词，看起来像没做去重。
LEMMA_ALIAS = {
    "agents": "agent", "agentic": "agent", "agent-based": "agent",
    "llms": "llm", "llm-based": "llm",
    "embeddings": "embedding", "proofs": "proof", "queries": "query",
    "databases": "database", "compilers": "compiler", "transactions": "transaction",
    "networks": "network", "graphs": "graph", "images": "image", "videos": "video",
    "models": "model", "algorithms": "algorithm", "methods": "method",
    "diffusion": "diffusion", "transformers": "transformer",
}


def lemma(term: str) -> str:
    """粗糙但够用的词形归并：先查别名表，再去复数。

    不追求语言学正确，只要求「同一概念只出现一次」；周报的代表词是展示用品，
    宁可把 analyses 归成 analyse，也不能让 agents / agent 同时占两个位置。
    """
    t = (term or "").strip().lower()
    if not t:
        return ""
    if t in LEMMA_ALIAS:
        return LEMMA_ALIAS[t]
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if t.endswith(("ses", "xes")) and len(t) > 4:
        return t[:-2]
    if t.endswith("s") and not t.endswith("ss") and len(t) > 3:
        return t[:-1]
    return t


# 宽泛词：单独出现时不构成任何方向（用户明确点名 weights / image / video / algorithm）。
# 它们仍可参与短语（如 image segmentation），但不会作为独立代表词出现。
BROAD_TERMS = frozenset("""
weights weight image images video videos algorithm algorithms cost costs memory gpu gpus
data dataset datasets information model models method methods approach approaches system
systems result results performance accuracy efficiency latency throughput speed scale size
quality number amount user users human humans work works paper papers study studies time
times way ways task tasks problem problems novel new existing recent large small high low
better best good effective efficient significant important key main current future general
specific given make makes made use uses used using based show shows shown propose proposed
presents introduce provides allows enable enables achieve achieves improve improves support
supports offer offers require requires include includes lead leads address addresses focus
focuses examine examines explore explores remains remain suggest suggests findings finding
challenge challenges towards toward understanding learning training generation modeling
layer layers token tokens step steps method-based
via et al https http github com io org doi arxiv supplementary preprint
often yet also still even well much many however moreover therefore thus
reduce reduces yields gives obtains called named termed respectively etc
execution knowledge representation representations policy reward latent
""".split())

# 通用搭配：出现频率高但没有任何区分度，作为代表词属于「说了等于没说」。
GENERIC_PHRASES = frozenset("""
success rate average success remains challenging consistently outperforms findings suggest
real world case study experimental results state art end end large language models
code generation experimental evaluation extensive experiments ablation study
""".split())


# 少量高信号词的固定中文译名：只覆盖「一眼能认出来」的方向词，
# 没收录的一律显示英文原词——宁可中英混排，也不硬翻译出一个不像术语的中文名。
TERM_ZH = {
    # 大模型 / 学习范式
    "llm": "大模型", "transformer": "Transformer", "attention": "注意力机制",
    "agent": "智能体", "rag": "检索增强", "retrieval": "检索",
    "embedding": "向量表示", "reasoning": "推理", "alignment": "对齐",
    "prompt": "提示词", "prompting": "提示工程", "fine-tuning": "微调",
    "finetuning": "微调", "lora": "LoRA", "distillation": "蒸馏",
    "diffusion": "扩散模型", "generation": "生成", "multimodal": "多模态",
    "vision": "视觉", "speech": "语音", "code": "代码", "coding": "编程",
    "program": "程序", "programming": "程序设计", "software": "软件",
    "compiler": "编译器", "compilation": "编译", "verification": "验证",
    "verified": "验证", "formal": "形式化", "proof": "证明", "theorem": "定理",
    "logic": "逻辑", "type": "类型", "types": "类型", "semantics": "语义",
    "synthesis": "合成", "interpretability": "可解释性",
    "reinforcement": "强化学习", "rl": "强化学习", "transfer": "迁移",
    "pretraining": "预训练", "pretrained": "预训练", "finetune": "微调",
    "quantization": "量化", "pruning": "剪枝", "sparsity": "稀疏化",
    "distributed": "分布式", "federated": "联邦学习", "consensus": "共识",
    "replication": "复制", "fault": "容错", "byzantine": "拜占庭",
    "partition": "分区", "replication-based": "复制",
    # 数据与系统
    "database": "数据库", "query": "查询", "transaction": "事务",
    "storage": "存储", "index": "索引", "indexing": "索引", "sql": "SQL",
    "olap": "OLAP", "key-value": "键值存储", "workflow": "工作流",
    "pipeline": "流水线", "scheduling": "调度", "latency": "时延",
    "throughput": "吞吐", "cache": "缓存", "kv": "KV",
    "serving": "服务系统", "inference": "推理", "compression": "压缩",
    "eviction": "淘汰", "prefetch": "预取", "prefetching": "预取",
    "offloading": "卸载", "batching": "批处理", "parallelism": "并行",
    "checkpoint": "检查点", "sharding": "分片", "routing": "路由",
    # 网络与安全
    "security": "安全", "attack": "攻击", "privacy": "隐私",
    "adversarial": "对抗", "malware": "恶意软件", "vulnerability": "漏洞",
    "encryption": "加密", "authentication": "认证", "anonymity": "匿名",
    "network": "网络", "congestion": "拥塞", "wireless": "无线",
    "edge": "边缘计算", "cloud": "云", "serverless": "无服务器",
    "energy": "能耗", "power": "功耗", "thermal": "散热",
    # 视觉 / 图形 / 机器人
    "segmentation": "分割", "detection": "检测", "reconstruction": "重建",
    "splatting": "泼溅", "gaussian": "高斯", "rendering": "渲染",
    "geometry": "几何", "spatial": "空间", "scene": "场景", "intelligence": "智能",
    "robot": "机器人", "robotics": "机器人", "motion": "运动",
    "planning": "规划", "navigation": "导航", "manipulation": "操作",
    "control": "控制", "humanoid": "人形", "autonomous": "自主",
    # 图 / 优化 / 理论
    "graph": "图", "recommendation": "推荐", "recommender": "推荐",
    "search": "搜索", "ranking": "排序", "cluster": "聚类",
    "clustering": "聚类", "optimization": "优化", "quantum": "量子",
    "estimation": "估计", "sampling": "采样", "gradient": "梯度",
    "convergence": "收敛", "approximation": "近似", "complexity": "复杂度",
    "polynomial": "多项式", "linear": "线性", "robust": "鲁棒",
    "stochastic": "随机", "theoretical": "理论", "bound": "界",
    # 应用域
    "clinical": "临床", "medical": "医疗", "health": "健康",
    "education": "教育", "students": "学生", "online": "在线",
    "social": "社会", "media": "媒体", "finance": "金融",
    "legal": "法律", "scientific": "科学", "discovery": "发现",
    "benchmark": "基准测试", "evaluation": "评测", "dataset": "数据集",
    "hallucination": "幻觉", "safety": "安全", "bias": "偏见",
    "fairness": "公平性", "ethics": "伦理", "governance": "治理",
}

# 短语译名：优先于单词匹配（长词优先），并把同义短语归到同一个概念键。
# 概念键用于去重：抓到一个 "kv cache" 之后，"cache" 就不再单列。
PHRASE_ZH = {
    "kv cache": ("KV 缓存", "kv-cache"),
    "key-value cache": ("KV 缓存", "kv-cache"),
    "mixture of experts": ("混合专家", "moe"),
    "mixture-of-experts": ("混合专家", "moe"),
    "gaussian splatting": ("高斯泼溅", "splatting"),
    "3d gaussian splatting": ("3D 高斯泼溅", "splatting"),
    "diffusion model": ("扩散模型", "diffusion"),
    "diffusion models": ("扩散模型", "diffusion"),
    "retrieval-augmented generation": ("检索增强生成", "rag"),
    "retrieval augmented generation": ("检索增强生成", "rag"),
    "chain-of-thought": ("思维链", "cot"),
    "chain of thought": ("思维链", "cot"),
    "reinforcement learning": ("强化学习", "rl"),
    "federated learning": ("联邦学习", "fl"),
    "graph neural network": ("图神经网络", "gnn"),
    "graph neural networks": ("图神经网络", "gnn"),
    "vision-language-action": ("视觉-语言-动作", "vla"),
    "vision-language model": ("视觉语言模型", "vlm"),
    "long context": ("长上下文", "long-context"),
    "long-context": ("长上下文", "long-context"),
    "test-time compute": ("测试时计算", "ttc"),
    "speculative decoding": ("投机解码", "spec-decoding"),
    "prompt engineering": ("提示工程", "prompting"),
    "in-context learning": ("上下文学习", "icl"),
    "self-supervised": ("自监督", "ssl"),
    "zero-shot": ("零样本", "zero-shot"),
    "few-shot": ("少样本", "few-shot"),
    "knowledge graph": ("知识图谱", "kg"),
    "knowledge graphs": ("知识图谱", "kg"),
    "multi-agent": ("多智能体", "multi-agent"),
    "multi-agent system": ("多智能体系统", "multi-agent"),
    "llm agents": ("LLM 智能体", "agent"),
    "language agents": ("语言智能体", "agent"),
    "agentic workflow": ("智能体工作流", "agent-workflow"),
    "agentic workflows": ("智能体工作流", "agent-workflow"),
    "tool use": ("工具调用", "tool-use"),
    "tool calling": ("工具调用", "tool-use"),
    "context window": ("上下文窗口", "context"),
    "state space model": ("状态空间模型", "ssm"),
    "neural network": ("神经网络", "nn"),
    "neural networks": ("神经网络", "nn"),
    "large language model": ("大语言模型", "llm"),
    "large language models": ("大语言模型", "llm"),
    "world model": ("世界模型", "world-model"),
    "world models": ("世界模型", "world-model"),
    "reasoning model": ("推理模型", "reasoning-model"),
    "fault tolerance": ("容错", "fault"),
    "query optimization": ("查询优化", "query-opt"),
    "query processing": ("查询处理", "query-proc"),
    "transaction processing": ("事务处理", "txn"),
    "data lake": ("数据湖", "lake"),
    "data lakehouse": ("数据湖仓", "lakehouse"),
    "vector database": ("向量数据库", "vector-db"),
    "vector search": ("向量检索", "vector-search"),
    "program synthesis": ("程序合成", "synthesis"),
    "formal verification": ("形式化验证", "formal"),
    "type system": ("类型系统", "type-system"),
    "static analysis": ("静态分析", "static-analysis"),
    "fuzzing": ("模糊测试", "fuzzing"),
    "side channel": ("侧信道", "side-channel"),
    "differential privacy": ("差分隐私", "dp"),
    "membership inference": ("成员推断", "mia"),
    "prompt injection": ("提示注入", "prompt-injection"),
    "jailbreak": ("越狱攻击", "jailbreak"),
    "reinforcement learning from human feedback": ("人类反馈强化学习", "rlhf"),
    "energy consumption": ("能耗", "energy"),
    "carbon footprint": ("碳足迹", "carbon"),
    "predictive control": ("预测控制", "mpc"),
    "simultaneous localization and mapping": ("即时定位与建图", "slam"),
    "point cloud": ("点云", "point-cloud"),
    "point clouds": ("点云", "point-cloud"),
    "remote sensing": ("遥感", "remote-sensing"),
    "time series": ("时间序列", "time-series"),
    "causal inference": ("因果推断", "causal"),
    "anomaly detection": ("异常检测", "anomaly"),
    "recommender system": ("推荐系统", "recsys"),
    "recommender systems": ("推荐系统", "recsys"),
    "information retrieval": ("信息检索", "ir"),
    "question answering": ("问答", "qa"),
    "machine translation": ("机器翻译", "mt"),
    "speech recognition": ("语音识别", "asr"),
    "text-to-image": ("文生图", "t2i"),
    "text-to-video": ("文生视频", "t2v"),
    "image generation": ("图像生成", "image-gen"),
    "video generation": ("视频生成", "video-gen"),
    "code generation": ("代码生成", "code-gen"),
    "program repair": ("程序修复", "repair"),
    "software engineering": ("软件工程", "se"),
    "operating system": ("操作系统", "os"),
    "file system": ("文件系统", "fs"),
    "memory management": ("内存管理", "mem-mgmt"),
    "garbage collection": ("垃圾回收", "gc"),
    "just-in-time": ("即时编译", "jit"),
    "instruction tuning": ("指令微调", "sft"),
    "parameter-efficient": ("参数高效", "peft"),
    "knowledge distillation": ("知识蒸馏", "kd"),
    "model merging": ("模型合并", "merging"),
    "continual learning": ("持续学习", "cl"),
    "domain adaptation": ("领域自适应", "da"),
    "contrastive learning": ("对比学习", "contrastive"),
    "self-improvement": ("自我改进", "self-improve"),
    "self-improving": ("自我改进", "self-improve"),
    "recursive self-improvement": ("递归自我改进", "self-improve"),
    "digital twin": ("数字孪生", "twin"),
    "smart grid": ("智能电网", "grid"),
    "autonomous driving": ("自动驾驶", "ad"),
    "human-robot collaboration": ("人机协作", "hrc"),
    "human-computer interaction": ("人机交互", "hci"),
}

# arXiv 官方分类的中文名（taxonomy 的通用译名）。代表词优先从这里取：
# 分类词是 arXiv 自己维护的术语，比 TF-IDF 抽出来的词更稳、更像「领域」。
CAT_ZH = {
    "cs.AI": "人工智能", "cs.CL": "自然语言处理", "cs.CV": "计算机视觉",
    "cs.LG": "机器学习", "cs.DB": "数据库", "cs.DC": "分布式计算",
    "cs.PL": "程序语言", "cs.SE": "软件工程", "cs.CR": "密码与安全",
    "cs.NI": "网络", "cs.RO": "机器人", "cs.HC": "人机交互",
    "cs.IR": "信息检索", "cs.DS": "算法与数据结构", "cs.MA": "多智能体",
    "cs.NE": "神经与进化计算", "cs.SI": "社会网络", "cs.MM": "多媒体",
    "cs.GR": "图形学", "cs.SD": "声音处理", "cs.AR": "硬件架构",
    "cs.ET": "新兴技术", "cs.LO": "数理逻辑", "cs.FL": "形式语言",
    "cs.CC": "计算复杂性", "cs.CE": "计算工程", "cs.MS": "数学软件",
    "cs.NA": "数值分析", "cs.OS": "操作系统", "cs.PF": "性能分析",
    "cs.SC": "符号计算", "cs.CY": "计算与社会", "cs.GT": "博弈论",
    "eess.SY": "系统与控制", "stat.ML": "统计机器学习", "math.CO": "组合数学",
    "math.OC": "优化与控制", "quant-ph": "量子物理",
}

# 这些分类覆盖太宽，作为代表词等于没给信息（一个 60% 是 cs.LG 的簇，
# 标「机器学习」对读者没有任何帮助）。
CAT_TOO_BROAD = frozenset({"cs.LG", "cs.AI"})

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

    中文词（分类名、短语译名）本身就是成品，直接采用，不再套权重门槛。
    """
    if not terms:
        return ""
    top_w = terms[0][1] or 1.0
    names = []
    for rank, (term, weight) in enumerate(terms):
        if has_cjk(term):
            zh = term
        else:
            zh = TERM_ZH.get(term) or TERM_ZH.get(lemma(term))
        if not zh or zh in names:
            continue
        if not has_cjk(term) and (rank >= 4 or weight < 0.5 * top_w):
            continue
        names.append(zh)
        if len(names) >= 2:
            break
    return " / ".join(names) if names else " / ".join(t for t, _ in terms[:2])


# ------------------------------------------------------------------ 代表词
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WORD_RE = re.compile(r"[a-z][a-z0-9\-]*")


def has_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text or ""))


def normalize_text(text: str) -> str:
    """短语匹配用的规范化：小写、连字符与斜杠归一成空格、压缩空白。"""
    t = (text or "").lower().replace("-", " ").replace("/", " ")
    return " ".join(t.split())


_PHRASE_INDEX = sorted(
    ((normalize_text(p), zh, concept) for p, (zh, concept) in PHRASE_ZH.items()),
    key=lambda x: (-len(x[0]), x[0]),
)


def _term_key(term: str) -> str:
    """去重用的概念键：短语查概念表，单词走词形归并。"""
    t = (term or "").strip().lower()
    if t in PHRASE_ZH:
        return PHRASE_ZH[t][1]
    return lemma(t)


def _display_term(term: str) -> str:
    if has_cjk(term):
        return term
    if term in PHRASE_ZH:
        return PHRASE_ZH[term][0]
    return TERM_ZH.get(term) or TERM_ZH.get(lemma(term)) or term


GENERIC_ZH = frozenset("代码 生成 学习 方法 系统 数据 任务 设计 分析 评测 模型 训练 研究".split())


def _skip_unigram(term: str) -> bool:
    """单个词是否过于宽泛（weights / image / video / algorithm …）。"""
    t = (term or "").strip().lower()
    if not t:
        return True
    if " " not in t and (t in BROAD_TERMS or t in STOPWORDS):
        return True
    if t in GENERIC_ZH:
        return True
    return len(t) < 3 or t.isdigit()


def _add_term(picked: list[dict], keys: set[str], term: str, weight: float,
              concept: str | None = None) -> None:
    """按「概念键 + 中文包含关系」双重去重后加入代表词。"""
    term = (term or "").strip()
    if not term:
        return
    key = concept or _term_key(term)
    if key in keys:
        return
    for p in picked:
        a, b = p["term"], term
        if has_cjk(a) and has_cjk(b) and (a in b or b in a):
            return
    keys.add(key)
    picked.append({"term": term, "weight": round(float(weight), 4), "key": key})


def select_terms(members: list[int], papers: list[dict], centroid: list[float],
                 vocab: list[str], top_n: int = 5) -> list[dict]:
    """为一个簇挑代表词：短语 → 分类词 → 高权重单词，逐层去重、剔除宽泛词。

    为什么要自己挑而不是直接取质心前 6：
    - 质心会在 agents / agent / agentic 上各给一个位置，读者看到的是同一个词的三次重复；
    - weights、image、video、algorithm 这类词几乎每周都在前列，但它们不构成方向；
    - 短语（KV 缓存、混合专家、高斯泼溅）比单词更能说清一个簇在做什么。
    """
    if not members:
        return []
    picked: list[dict] = []
    keys: set[str] = set()
    texts = [normalize_text("%s %s" % (papers[i].get("title") or "",
                                       papers[i].get("abstract") or "")) for i in members]
    size = len(members)

    # 1) 策展短语：出现在簇内 ≥3 篇、且不低于 1% 的论文里才算数。
    #    只认词表里的短语，避免 "remains challenging" / "success rate" 这类搭配混进来。
    hits = []
    for phrase, zh, concept in _PHRASE_INDEX:
        k = sum(1 for t in texts if phrase in t)
        if k >= max(3, int(size * 0.03)):
            hits.append((k, phrase.count(" ") + 1, zh, concept))
    hits.sort(key=lambda x: (-x[0], -x[1], x[2]))
    added = 0
    for k, _, zh, concept in hits:
        if concept in keys:
            continue
        _add_term(picked, keys, zh, min(1.0, k / max(3.0, size * 0.15)), concept)
        added += 1
        if added >= 2:
            break

    # 2) arXiv 分类词：簇的主导分类足够集中、且不是 cs.LG / cs.AI 这种大口袋时采用。
    cats = Counter(primary_category(papers[i]) for i in members)
    if cats:
        cat, cnt = cats.most_common(1)[0]
        share = cnt / float(size)
        if share >= 0.35 and cat not in CAT_TOO_BROAD and cat in CAT_ZH:
            _add_term(picked, keys, CAT_ZH[cat], 0.95, "cat:" + cat)

    # 3) 质心高权重单词：只收词典里有的词（中文术语），按词形归并去重；
    #    没收录的英文词一律不进正式位次，留给第 4 步兜底 —— 否则
    #    execution / knowledge / representations 这类半通用词会把位置占满。
    for term, w in label_terms(centroid, vocab, top=60):
        if _skip_unigram(term):
            continue
        zh = _display_term(term)
        if zh == term or zh in GENERIC_ZH:
            continue
        _add_term(picked, keys, zh, w, lemma(term))
        if len(picked) >= top_n:
            break

    # 4) 兜底：词表没覆盖的小众方向，保留最强的两个原词，总比空着强。
    if len(picked) < 3:
        for term, w in label_terms(centroid, vocab, top=20):
            if _skip_unigram(term):
                continue
            _add_term(picked, keys, term, w, lemma(term))
            if len(picked) >= 3:
                break
    return picked[:top_n]


# ------------------------------------------------------------------ 相关工作
def paper_highlights(paper: dict, limit: int = 3) -> list[str]:
    """一篇论文的 2–3 个中文关键词：标题优先、摘要补足，只用词典里有的术语。

    这是画面蓝色小字与口播「最接近的三项工作」的取材来源。刻意不做整句翻译：
    词典之外的词一律不进，宁可少说，也不拼出「提出recursive capability co…」
    这种半英半中的残句。摘要只取单词、不取短语：摘要里的搭配经常与论文主题无关
    （数据集论文的摘要里出现 video generation 并不代表它做视频生成）。
    """
    title = normalize_text(paper.get("title") or "")
    picked: list[str] = []

    def push(text: str) -> None:
        if not text or text in picked:
            return
        for old in picked:
            if has_cjk(old) and has_cjk(text) and (old in text or text in old):
                return
        picked.append(text)

    # 1) 标题里的策展短语（长词优先）
    for phrase, zh, _ in _PHRASE_INDEX:
        if " " in phrase and phrase in title:
            push(zh)
            if len(picked) >= limit:
                return picked
    # 2) 标题里的词典词
    for tok in _WORD_RE.findall(title):
        if _skip_unigram(tok):
            continue
        zh = TERM_ZH.get(tok) or TERM_ZH.get(lemma(tok))
        if zh:
            push(zh)
            if len(picked) >= limit:
                return picked
    # 标题关键词少于两个时不再从摘要凑：摘要里的搭配常与主题无关
    # （数据集的摘要里出现 video generation，不代表它做视频生成）。
    return picked


_LEAD_STOP = frozenset("on the a an towards toward how why what when is are from for in of to "
                       "with under about into via using".split())
_TAIL_STOP = frozenset("of for and with via in on to by using from at as".split())


def short_name(title: str, limit: int = 22) -> str:
    """口播用的短名：冒号前的主名（PACE / GreyZone），否则取前两三个实词。

    直接截前三个词会得到 "On the Global" / "A New Framework" 这种没有辨识度的串；
    先去掉开头的虚词、再在介词处截断，才拿得到 "Global Convergence" 这类说法。
    """
    title = (title or "").strip()
    if not title:
        return ""
    head = title.split(":", 1)[0] if ":" in title else title
    words = head.split()
    while words and words[0].lower().strip(".,") in _LEAD_STOP:
        words.pop(0)
    out: list[str] = []
    for w in words:
        if out and w.lower().strip(".,") in _TAIL_STOP:
            break
        out.append(w)
        if len(out) >= 3:
            break
    while len(out) > 1 and out[-1].lower().strip(".,") in _TAIL_STOP | {"the", "a", "an", "is"}:
        out.pop()
    name = " ".join(out) or (title.split()[0] if title.split() else title)
    name = name.strip(" .,-—\"'“”")
    if len(name) > limit:
        cut = name[:limit]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]      # 英文按词边界切，别切出 "Direct GPU Ene"
        name = cut
    return name


def brief_note(paper: dict, limit: int = 24) -> str:
    """画面上的蓝色小字：两三个中文术语，用「 · 」连接；没有术语时退回英文副标题。"""
    tags = paper_highlights(paper, 3)
    # 只有一个标签时，只有它本身够具体（≥4 字，如「KV 缓存」）才单独用；
    # 「几何」这种两字泛词配不上当一句介绍，退回英文副标题更准确。
    if tags and (len(tags) >= 2 or len(tags[0]) >= 4):
        text = ""
        for tag in tags:
            nxt = tag if not text else text + " · " + tag
            if len(nxt) > limit:
                break
            text = nxt
        if text:
            return text
    title = (paper.get("title") or "").strip()
    sub = title.split(":", 1)[1].strip() if ":" in title else title
    return _clip_note(sub, limit)


def _clip_note(text: str, limit: int) -> str:
    """超长时优先整段丢弃标签（「 · 」分段），避免把 KV 缓存截成 KV。"""
    text = (text or "").strip(" ,.;:，。；：")
    if len(text) <= limit:
        return text
    if "·" in text:
        parts = [p.strip() for p in text.split("·") if p.strip()]
        out = ""
        for part in parts:
            nxt = part if not out else out + " · " + part
            if len(nxt) > limit:
                break
            out = nxt
        if out:
            return out
    cut = text[: limit - 1]
    if " " in cut and not has_cjk(cut):
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def term_cloud(papers: list[dict], top_n: int = 36) -> list[dict]:
    """全周词云：按文档频率取词，剔除宽泛词并做词形归并，权重归一到 1。

    只收词典里有的词（显示为中文）：词云的每一格都会被观众当成「本周方向」，
    放 fixed / prediction / design 这类通用词只会稀释信息。
    """
    df = Counter()
    for p in papers:
        seen = set()
        for w in set(_WORD_RE.findall((p.get("title") or "").lower())) | set(
                _WORD_RE.findall((p.get("abstract") or "").lower())):
            if _skip_unigram(w):
                continue
            seen.add(lemma(w))
        df.update(seen)
    rows = sorted(df.items(), key=lambda kv: (-kv[1], kv[0]))
    out, seen_text = [], set()
    for word, c in rows:
        text = _display_term(word)
        if text == word or text in GENERIC_ZH or text in seen_text:   # 未收录/过泛 → 不进词云
            continue
        seen_text.add(text)
        out.append({"text": text, "count": c})
        if len(out) >= top_n:
            break
    top = out[0]["count"] if out else 1
    for row in out:
        row["weight"] = round(row["count"] / float(top), 3)
    return out


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
        picked = select_terms(members, papers, cen, vocab)
        names = [p["term"] for p in picked]
        label = zh_label([(p["term"], p["weight"]) for p in picked])
        if label in used_labels:
            # 两个簇代表词撞车时补第三个词，避免报告里出现两行同名主题。
            extra = next((t for t in names[2:] if t not in label), "")
            label = "%s·%s" % (label, extra) if extra else label
        used_labels.add(label)
        # 代表论文：与质心最相似的三篇（vectors 已归一化，点积即余弦）。
        # 每篇配一句蓝色小字（brief_note），视频里直接显示在标题与编号下方。
        ranked = sorted(members, key=lambda i: (-_dot(vectors[i], cen), i))[:3]
        clusters.append({
            "size": len(members),
            "share": round(len(members) / n, 4) if n else 0.0,
            "terms": names,
            "term_weights": [p["weight"] for p in picked],
            "label": label,
            "samples": [{"sid": papers[i].get("sid") or "",
                         "title": papers[i].get("title") or "",
                         "short": short_name(papers[i].get("title") or ""),
                         "note": brief_note(papers[i])} for i in ranked],
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
        "cloud": term_cloud(papers),
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
