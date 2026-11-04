# -*- coding: utf-8 -*-
"""2026-11-04 批次：本期 24 篇待补论文的双语简介（summaries.json）。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- key 一律 arXiv 短号。
- 本轮只补双语简介（摘要全文中译未做，见执行记录）。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2611.02849": {
        "zh": "TLAPS-Bench 是面向真实系统 TLA+ 规范机器检验证明的基准与执行脚手架：智能体在 TLA+ 证明系统上迭代开发证明，配备证明工具与库、并设防奖励作弊的护栏。基准含 95 个真实系统规范中的 265 个证明目标，覆盖缓存一致性、拜占庭共识与写前日志。在 12 个规范的 70 个目标上，最强的 GPT-6.1 Sol (max) 证明 31 个（44.3%）。",
        "en": "TLAPS-Bench is a benchmark and execution harness for machine-checked proofs of real-world TLA+ specifications with agentic AI: agents iteratively develop proofs atop the TLA+ Proof System with proof tools, libraries and safeguards against reward hacking. It contains 265 proof targets from 95 specifications of real systems spanning cache coherence, Byzantine consensus and write-ahead logs; on 70 targets across 12 specifications the best model, GPT-6.1 Sol (max), proved 31 (44.3%).",
    },
    "2611.01363": {
        "zh": "SMR 依赖服务器物化并持久化状态，服务器因此成为脆弱而昂贵的瓶颈点。Serverless SMR（S²MR）把物化状态与持久全序都放到分解式存储上，由客户端在外部存储上并发维护状态副本；核心洞察是共享日志不仅用于给命令定序，还能支撑分布式物化，从而成为实现 SMR 的唯一接口。作者以事务型键值存储 AirDB 验证了该方案。",
        "en": "Serverless SMR (S2MR) removes servers—the brittle, expensive choke-points of state machine replication—by keeping both the materialized state and the durable total order on disaggregated storage, with clients concurrently maintaining state copies on external storage; the key insight is that the shared log abstraction serves not only to order commands but also to enable distributed materialization, becoming the only interface for achieving SMR. The authors demonstrate it with AirDB, a transactional key-value store.",
    },
    "2611.01323": {
        "zh": "许多共识协议在「移动崩溃」对手（可在副本间移动并反复崩溃其一）攻击下无法终止。ML-FVS 在保留 Simplex 共识简洁结构与良好情况延迟的同时引入多领导：各副本对已见提案集合投票，投票截止后揭示的隐藏阈值信标给出领导优先级，把每票解析到最高优先级提案。在常数崩溃预算与 Δ 延迟拜占庭腐化下，期望延迟 O(Δ)。",
        "en": "Many consensus protocols fail to terminate against a mobile-crash adversary that moves between replicas and repeatedly crashes one of them. Multi-Leader Fixed-View Simplex (ML-FVS) keeps the simple structure and good-case latency of Simplex while adding multiple leaders: replicas vote on the set of proposals seen so far, and a hidden threshold beacon revealed after voting orders the leaders, resolving each vote to its highest-priority proposal; with a constant crash budget and Delta-delayed Byzantine corruption it achieves O(Delta) expected latency.",
    },
    "2611.02779": {
        "zh": "数据库引擎随硬件与负载反复重构，而错误答案缺陷在成熟系统中仍屡见不鲜。GenDB-V 让 AI 智能体合成针对硬件与负载特化、且经形式化验证的数据库引擎：SQLSpec 把 SQL 语义形式化并确定性构造与实现无关的合成目标；再通过存储—执行协同优化与性能优先探索，联合合成快速代码与形式化证明。",
        "en": "GenDB-V enables AI agents to synthesize database engines specialized to hardware and workloads and formally verified for correctness: SQLSpec formalizes SQL semantics and deterministically constructs fixed, implementation-agnostic synthesis targets, and joint synthesis of fast code and formal proofs proceeds through storage-execution co-optimization and performance-first exploration, supporting specialized SQL-template implementations and general-purpose engines over a supported SQL subset.",
    },
    "2611.04561": {
        "zh": "研究两进程经不可靠链路（每轮至少送达一条消息）通信下的分布式 LTL 合成：即使消息携带完整因果历史，合成也不可判定。作者给出使合成可判定的通信限制的完整刻画——用消息对手（允许的无限图历史集合）描述限制，经迭代染色细分配到 [0,1] 区间，对每个 ω-正则对手，合成可判定当且仅当其像无处稠密；可判定情形给出实现性判定与分布式算法构造。",
        "en": "The paper studies distributed LTL synthesis for two processes communicating over unreliable links that deliver at least one message per round and shows synthesis is undecidable even when messages carry complete causal histories; it gives a complete characterization of decidable communication restrictions via message adversaries—sets of allowed infinite graph histories mapped by iterated chromatic subdivision into [0,1]—where synthesis is decidable iff the image is nowhere dense, with a realizability procedure and algorithm construction in the decidable cases.",
    },
    "2611.02285": {
        "zh": "当自主编码智能体同时生成实现、形式规范与机械证明时，软件工程层级倒置：规范成为人类评审的主要产物，代码与证明脚本变成可抛弃的构建产物。论文提出 spec-first 架构：零代码评审、由自动化 CI 门禁把关的工作流；经薄验证翻译器下降的最小验证中间表示（VIR）；以及跨多团队组织的个人 Spec-Copilot 与共享合成舰队协作机制。",
        "en": "When autonomous coding agents synthesize implementation, formal specifications and mechanical proofs simultaneously, the software-engineering hierarchy inverts: the formal specification becomes the primary human-reviewed artifact while code and proof scripts become disposable build outputs. The paper presents a spec-first architecture combining zero-code-review workflows gated by automated CI, a minimal Verification Intermediate Representation lowered via a thin verified translator, and organizational-scale collaboration through Personal Spec-Copilots and a Shared Synthesis Fleet.",
    },
    "2611.05173": {
        "zh": "编码智能体能生成性能优异的定制数据系统，但纯智能体路线并不自动继承社区数十年积累的正确性保证。论文提出「正确性防火墙」：轻量设计模式，让合成组件只能影响系统性能、绝不能影响结果。三个案例分别对应三类防火墙——基数估计（advisory）、有序数据搜索（guarded）与数据压缩（certified）；合成组件搜索有序数据比学习型索引快至 3 倍，文本压缩比 Zstd 小 1.5 倍。",
        "en": "Coding agents can now generate bespoke, instance-optimized data systems, but a purely agentic approach does not automatically inherit decades of correctness guarantees. The paper proposes correctness firewalls—lightweight design patterns under which a synthesized component can affect a system's performance but never its results—illustrated by three case studies: cardinality estimation (advisory), searching sorted data (guarded) and data compression (certified), with synthesized components up to 3x faster than learned indexes and 1.5x smaller text compression than Zstd.",
    },
    "2611.02164": {
        "zh": "区块链吞吐量日益受限于交易执行，而现有并行执行引擎在块内套用单一并发控制策略。RegionFence 面向区块链并行执行做自适应并发控制：用 region 把控制粒度从整笔交易细化到触碰争用键的部分；用 fence 在运行时决定每个 region 如何处理冲突；并引入块内/块间在线学习预判冲突。系统仍产出与按共识序串行执行一致的结果，已在 go-ethereum 实现。",
        "en": "RegionFence is an adaptive concurrency control mechanism for blockchain parallel transaction execution, where blocks fix the serial order, accesses emerge only at runtime and workloads vary widely: regions refine control granularity from whole transactions to parts touching contended keys, fences decide at runtime how each region handles conflicts, and intra- and inter-block online learning anticipates likely conflicts while preserving serial-equivalent results in consensus order; it is implemented in go-ethereum.",
    },
    "2611.01743": {
        "zh": "软件开发者惯于复用成熟库，但把成功的验证方案变成可复用库仍需大量专家投入。VeriBase 从成功的验证方案出发，联合泛化代码及其定理：把代码与定理视为声明族，经三阶段流水线（证明种子任务、泛化代码与定理、收割成共享接口）构建，接口变更时更新依赖声明，并用 Lean 检查代码与证明。基于 4,191 个独立程序构建的通用库平均提升了任务表现。",
        "en": "VeriBase automatically constructs software-verification libraries by jointly generalizing code and its associated theorems from successful verification solutions: it treats code and theorems as declaration families, runs a three-phase pipeline that proves seed tasks, generalizes code and theorems and harvests the families into shared interfaces, updates dependent declarations on interface change, and checks results with Lean; the general-purpose library built from 4,191 independent programs increases average task performance across four benchmarks and three backend LLMs.",
    },
    "2611.02132": {
        "zh": "时序数据库的 Text-to-SQL 缺乏高质量基准与大规模训练语料。TSSDA 提出 Time-Series SQL 生成数据智能体框架，构建 TERN 基准：系统建模 TSSQL 语法语义以构造数据生成空间，覆盖合法查询组合；数据智能体自主编排生成与校验，随语料增长维持多样性与价值，并处理模式与数据异质性以复用时序查询结构。",
        "en": "TSSDA is a Time-Series SQL generation data-agent framework that constructs TERN, a comprehensive time-series Text-to-SQL benchmark: it systematically models TSSQL syntax and semantics to build a generation space covering valid query combinations, and a data agent autonomously orchestrates generation and validation to keep new data valuable and diverse as the corpus grows, while handling schema and data heterogeneity to reuse temporal query structures.",
    },
    "2611.01357": {
        "zh": "Lean 内核只检查证明是否确立其陈述，而陈述是否表达了本意仍靠人工评审——LLM 批量书写形式陈述使这一老问题愈发紧迫。ProofPatch 帮助评审者向内核定向提问（某假设是否必要、是否存在反例），并把每项决定连同陈述及其依赖定义的指纹存储，可钉住任何声明以阻止修改它的补丁。在 Mathlib 相邻 229 对修订上，118 对中的陈述决定可复用。",
        "en": "ProofPatch helps reviewers judge Lean statements—the kernel checks proofs but not whether statements say what was intended—and keeps their judgments valid as formalizations evolve: reviewers ask the kernel targeted questions such as whether a hypothesis is needed or a counterexample exists, decisions are stored with fingerprints of the elaborated statement and its definitions, and declarations can be pinned to block patches changing them; on 229 pairs of consecutive Mathlib revisions it reuses 118 statement decisions.",
    },
    "2611.02811": {
        "zh": "现有延迟预测模型依赖在目标硬件上采集负载轨迹，覆盖大量消费级 GPU 成本过高。作者反其道行之：配置本地 GPU 的设备参数去复现低端目标卡的执行性能，把延迟预测重构为零样本问题——不再拟合轨迹数据集，而是寻找最能复现目标设备表现的本地配置。在 21 款消费级 GPU、60 个视觉模型上 MAPE 14.21%，基线超过 25%。",
        "en": "Instead of fitting ML models to traces collected on target hardware, the paper configures a local host GPU to reproduce the execution performance of less powerful target GPUs by selectively modifying device parameters, reformulating latency prediction as zero-shot: identify local configurations that best reproduce the target device. Evaluated on 60 computer-vision models across 21 consumer GPUs it achieves 14.21% MAPE versus over 25% for comparable baselines.",
    },
    "2611.05121": {
        "zh": "GPU 程序易患数值缺陷：依赖特定输入值或类型、缺乏可靠错误检查机制与测试预言，且 GPU 特有编程惯例增加根因定位难度。作者分析 GitHub 上 397 个真实样本，归纳根因、症状、输入模式、触发缺陷的测试预言与修复策略，并给出覆盖六类缺陷的初步检测工具 GPU-NBDetect。",
        "en": "The paper studies numerical bugs in GPU programs—hard to detect, debug and fix because they depend on specific input values or types, lack reliable error-checking mechanisms and oracles, and interact with GPU-specific programming conventions—by analyzing 397 real-world samples from GitHub to identify root causes, symptoms, input patterns, triggering oracles and fix strategies, and presenting GPU-NBDetect, a preliminary tool covering six bug categories.",
    },
    "2611.04973": {
        "zh": "面向 SDN 环境中基于 eBPF/XDP 的时延测量，提出并评估模块化架构：用 Observer、Strategy、Factory Method 三种设计模式把指标采集与分析流水线模块化，支持动态接入策略与数据汇。Mininet + Python 代理 + eBPF/XDP 的实验表明引入设计模式无可测性能劣化，持续测量的开销最低约 5%。",
        "en": "The paper proposes, implements and evaluates a modular architecture for latency measurement in SDN with eBPF/XDP, applying the Observer, Strategy and Factory Method design patterns to modularize the metric collection and analysis pipeline for dynamic integration of policies and data sinks; experiments with Mininet, Python agents and eBPF/XDP programs show no clear performance degradation from the design patterns, maintaining continuous measurements with a minimum of 5% overhead.",
    },
    "2611.01950": {
        "zh": "编码智能体服务按所声称的模型计价，但现有模型审计隐含「部署静态」假设——提供方可以合法更改采样预设、推理模式或系统提示而不换模型，导致误告诚实提供方或漏检廉价衍生。CertClaim 把「经授权的部署集合」纳入被验声称，测试是否存在某个授权部署能解释服务的全部证据：在每次授权部署内校准多证据通道并融合，给出误告率与检测条件的理论分析。",
        "en": "CertClaim targets certified model-claim verification for coding-agent services, where providers may legitimately change sampling presets, reasoning modes or system prompts without changing the model, breaking the static-deployment assumption of existing audits: it makes authorized deployments part of the claim and tests whether some authorized deployment explains all evidence of the service, calibrating and fusing multiple evidence channels per deployment, with theoretical analyses of false-accusation rate and detection conditions.",
    },
    "2611.05340": {
        "zh": "MedPhysBench 评估语言模型在医学物理计算与差错检测上的能力：十个种子生成器产出放疗、影像诊断、核医学与辐射防护的计算题（含 TG-51 校准工作表），参考答案来自实现规程的代码，评分器换算单位并按容差带判分；同源输入另派生出同事工作表的差错检测题。1,200 题留出集上 12 个模型计算题得分 33.3–100%，最强的四款答错的 9 题里有 5 题是模型自身错误。",
        "en": "MedPhysBench evaluates language models on medical physics calculations and error detection: ten seeded generators produce calculation items in radiation therapy, diagnostic imaging, nuclear medicine and radiation protection up to clinical tasks like a TG-51 calibration worksheet, with reference answers from protocol-implementing code and a unit-aware, tolerance-band grader; on a 1,200-item held-out split 12 models scored 33.3–100.0% on calculations, and of the nine answers graded incorrect for the four best models five contained model errors.",
    },
    "2611.03493": {
        "zh": "横向基准比较三种可验证凭证格式的签名与验证性能：SD-JWT VC、W3C VCDM 2.0（Data Integrity）与 mdoc（ISO/IEC 18013-5），覆盖签发、选择性披露出示与验证，Node.js/Go/Python 四环境实测。披露 20 属性中 5 个的端到端交换：mdoc 0.265 ms、SD-JWT VC 0.298 ms、W3C VCDM 0.534 ms；VCDM 慢 1.73–2.04 倍，根因是 RDFC-1.0 规范化每次操作做两次规范化。",
        "en": "A cross-language benchmark compares signing and verification performance of SD-JWT VC, W3C VCDM 2.0 with Data Integrity, and mdoc (ISO/IEC 18013-5) over issue, present-with-selective-disclosure and verify across Node.js, Go and Python in four environments; for an end-to-end exchange disclosing 5 of 20 attributes, totals are 0.265 ms (mdoc), 0.298 ms (SD-JWT VC) and 0.534 ms (W3C VCDM), with VCDM 1.73–2.04x slower than mdoc, attributed to RDFC-1.0 canonicalization running twice per operation.",
    },
    "2611.04240": {
        "zh": "图数据往往结构敏感，客户端难以验证服务方对私有图的查询结果。VerfGraph 提出零知识的可验证图查询求值系统：客户端能确认结果确是对已承诺图数据的正确计算，而不泄露私有记录或查询中间值。在 ZKGraph（ICDE'26）的扩展中心模型上，为核心扩展与最短路算子提出新的算子—证明方法，更高效且更具表达力。",
        "en": "VerfGraph is a zero-knowledge system for verifiable graph query evaluation: a client can verify that a query result was correctly computed over committed graph data without revealing private graph records or intermediate query values beyond public inputs and what the result implies; building on the expansion-centric model of ZKGraph (ICDE'26), it advances operator-proof methods for core expansion and shortest-path operations for more efficient and expressive evaluation.",
    },
    "2611.03852": {
        "zh": "长推理链昂贵，而专有模型的隐藏草稿限制了对其压缩机制的研究。论文考察开源权重模型能否不重训练而生成更简洁的推理：在工具结果揭晓前，把此前的推理改写成紧凑状态记录，再对比原始与紧凑历史的续写。各模型上被接受的紧凑历史通常缩短后续推理；软件智能体部署中压缩可降低总开销，但任务质量与含改写的耗时取决于目标与压缩器。",
        "en": "The paper investigates whether open-weight models can generate less verbose reasoning without retraining by rewriting their own earlier thoughts into compact state records before pending tool results are revealed and comparing continuations from original versus compact histories; accepted compact histories usually shorten future reasoning, and in software-agent deployments compaction can reduce total spending, though task quality and rewrite-inclusive time depend on the target and compressor.",
    },
    "2611.05142": {
        "zh": "针对无关机调度最小化工期的随机真实机制，本文证明 (m+1)/2 下界，把真实期望（TIE）机制的最优近似比确定到 m/2+Θ(1)（此前上界 (m+5)/2、下界仅 2−1/m）。同时把普遍真实机制的下界首项常数从 3/2−√2≈0.086 提升到 1/2，与已有的 m/2+o(m) 上界相呼应。",
        "en": "For randomized truthful mechanisms minimizing makespan on m unrelated machines, the paper proves a lower bound of (m+1)/2, pinning down the optimal truthful-in-expectation approximation ratio as m/2+Theta(1)—closing the gap between the (m+5)/2 upper bound and the 2−1/m lower bound—and improves the leading constant of the universally truthful lower bound from 3/2−√2≈0.086 to 1/2, complementing the known m/2+o(m) upper bound.",
    },
    "2611.03952": {
        "zh": "把旋转不变性直接建进架构的点云分类器在姿态扰动下最稳，但在 5 个域中的 4 个噪声鲁棒性排名垫底。作者以假设检验而非点估计分析 10 种架构 × 5 域的姿态/噪声/遮挡基准，并统一加不变性损失重训：收益 narrowly 但可靠地迁移到其扰动所针对的损坏族（遮挡 +10.5、激光雷达 +13.4 点）；同等训练预算下，最佳标准骨干与最佳不变架构在未见损坏上打平（2.5 点内）。",
        "en": "Benchmarking 10 point-cloud architectures across 5 domains under pose, noise and occlusion with confirmatory hypothesis tests, the paper finds rotation-invariant architectures achieve the best pose robustness but rank among the lowest on noise robustness in 4 of 5 domains; retraining all with a simple invariance loss transfers narrowly but reliably to the corruption families its perturbations target (occlusion +10.5, lidar +13.4 points), and at matched budget the best standard backbone and best RI architecture end on par on unseen corruptions within 2.5 points.",
    },
    "2611.03509": {
        "zh": "研究只求破坏活性的 P2P gossip 攻击：不伪造、不篡改任何消息，只让诚实节点收不到新消息。对以太坊使用的 GossipSub，地理位置分散、持有固定延迟优势的常数规模对手可接管「首次消息送达」评分项，把常数比例节点从诚实 mesh 中隔离，且在真实 churn 下可维持；对 CometBFT 的 DOG 传播协议，先给出路由过滤即可断图的反例，再给出实用攻击。",
        "en": "The paper studies liveness attacks on P2P gossip—an adversary violating liveness without forging, altering or invalidating any message: for GossipSub as used by Ethereum, a constant number of geographically distributed nodes with a fixed latency advantage can take over the First Message Deliveries peer-scoring term and separate a constant fraction of nodes from the honest mesh, maintained under realistic churn; for DOG, a dissemination protocol for CometBFT, it gives simple counterexamples where route filtering disconnects the dissemination graph plus a practical attack.",
    },
    "2611.05092": {
        "zh": "研究度量图上随机化设施选址的策略防护（SP）机制的自动设计：对给定图与代理数，计算最优近似比的上、下界。下界经保代价归约到有限域，由线性规划对偶证书给出；上界引入分段线性归因（PL attributions）这一机制的有限表示，证明检查 SP 与近似保证归为紧多面体上有限个二次非负性检验，配合精确算术可给出性质证明或失败位置。另提出强化的强策略防护概念。",
        "en": "The paper develops automated design of strategyproof mechanisms for randomized facility location on continuous metric graphs, computing upper and lower bounds on the optimal approximation ratio for a given graph and number of agents: lower bounds come from a cost-preserving reduction to a finite domain yielding LP dual certificates, upper bounds from piecewise-linear attributions—finite mechanism representations for which checking SP and approximation reduces to finitely many quadratic nonnegativity tests over compact polytopes, certified with exact arithmetic—and a strengthening called strong strategyproofness is introduced.",
    },
    "2611.04835": {
        "zh": "面向资源受限设备的时间序列异常检测，研究蓄水池状态马氏距离（MDRS）并给出两项优化：用循环移位替代随机蓄水池连接（MDRS-Circ），并证明整条序列的异常分数可只由最终蓄水池状态算出；再利用蓄水池的时间记忆简化输入预处理。在 MLPerf Tiny 异常检测基准上，仅 MDRS 与自编码器达标，且 MDRS 计算需求更低；已在 NUCLEO-F401RE 微控制器上部署推理内核评估延迟、能耗与内存。",
        "en": "The paper investigates the Mahalanobis Distance of Reservoir States (MDRS), an unsupervised time-series anomaly detection method, for resource-constrained devices with two optimizations: replacing random reservoir connectivity with a circular shift (MDRS-Circ) and computing the anomaly score of an entire series from the final reservoir state alone, plus cheaper input preprocessing that exploits the reservoir's temporal memory; on the MLPerf Tiny benchmark only MDRS and the autoencoder meet the target with MDRS cheaper, and inference kernels were deployed on a NUCLEO-F401RE microcontroller to assess latency, energy and memory.",
    },
}


def merge_summaries():
    path = os.path.join(OUT, "summaries.json")
    data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    before, added = len(data), 0
    for sid, val in SUMM.items():
        cur = data.get(sid)
        if isinstance(cur, dict):
            if not cur.get("zh") or not cur.get("en"):
                data[sid] = {"en": val["en"], "zh": val["zh"]}
                added += 1
        elif not cur:
            data[sid] = {"en": val["en"], "zh": val["zh"]}
            added += 1
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("summaries: %d -> %d (added/updated %d)" % (before, len(data), added))


if __name__ == "__main__":
    merge_summaries()
