# -*- coding: utf-8 -*-
"""2026-11-20 批次：本期 24 篇待补论文的双语简介（summaries.json）。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- key 一律 arXiv 短号。
- 本轮只补双语简介（摘要全文中译 abstracts_zh 未做）。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2611.24902": {
        "zh": "规约挖掘能从系统轨迹中提炼事件间的时序规则，但分布式监控下各节点时钟不同步、事件可能丢失或乱序，规则难以直接落地。本文研究跨观察者聚合规则覆盖、判定哪些时间窗在监控期必需，并刻画事件丢失下的检测能力；用 21 个接收器、四大洲的 IPv6 包轨迹评测，给出规则聚合、编译与失真三者的量化关系。",
        "en": "Studied are aggregation of mined temporal-rule coverage across distributed observers, deciding which temporal windows matter during monitoring, and characterizing detection under event loss, evaluated on IPv6 packet traces from 21 receivers in four continents.",
    },
    "2611.24872": {
        "zh": "MicroAssert 是微架构感知的 CPU 断言自动生成框架：直接从 RTL 识别功能区域，经结构化契约与确定性验证原语生成本地与组合断言，覆盖引导反馈逐步扩大与证明相关的 RTL 覆盖。在五个开源 RISC-V CPU 上对比三种既有断言生成方法，能捕获既有方法漏掉的微架构行为与跨区域交互。",
        "en": "MicroAssert is a microarchitecture-aware assertion generation framework that identifies functional regions from RTL and produces local and composite assertions via structured contracts and deterministic verification primitives, with coverage-guided feedback expanding proof-relevant RTL coverage across five open-source RISC-V CPUs.",
    },
    "2611.24833": {
        "zh": "DispersedBFT：用分散复制消除主节点瓶颈的 PBFT 型共识协议。传统主备式 RDS 中 primary 负责协调请求的复制与执行，中心角色急剧限制性能。DispersedBFT 把协调职责分散到副本，实测消除主节点瓶颈并显著提升吞吐，为区块链驱动的弹性数据管理系统提供新设计点。",
        "en": "DispersedBFT is a high-performance PBFT-like consensus protocol using dispersed replication to eliminate the primary bottleneck of primary-backup resilient data management systems, dispersing coordination across replicas instead of a single coordinating primary.",
    },
    "2611.24804": {
        "zh": "MLIR-MRacle 是并发 MLIR 程序的内存模型感知蜕变测试器：并发程序常无单一预期输出，既有 MLIR 模糊器多假设确定性，而 lowering 会跨越内存模型截然不同的目标。它按目标内存模型门控蜕变关系，保证原程序与变换后程序都良定义，能发现「看似合理却悄悄改变行为」的并发优化。",
        "en": "MLIR-MRacle is a memory-model-aware metamorphic fuzzer for concurrent MLIR programs, applying metamorphic relations gated by the target memory model so both original and transformed programs stay well defined, catching concurrency optimizations that silently change behavior across lowering stages.",
    },
    "2611.24682": {
        "zh": "判断工业控制器自然语言指令是否安全，瓶颈可能不在模型而在输入：同一指令在不同设备状态下需要相反的安全决策，而模型可能根本拿不到机器状态。本文提出可答性审计——把同一指令配对成需要相反答案的两个状态，配对都答对才计数，逐级加入规则与状态值，量化「答错源于信息缺失而非推理差」的程度。",
        "en": "Proposes an answerability audit for LLM interfaces to industrial controllers: pair the same command with two states requiring opposite answers, count only correct pairs, and progressively add rules and state values to inputs, quantifying how much incorrect behavior reflects missing machine state rather than poor reasoning.",
    },
    "2611.24649": {
        "zh": "编排式编程（CP）把分布式系统写成全局程序再经端点投影编译，但异步（进程独立推进）与不确定性（交互引发的行为范围）此前从未同时纳入 CP 理论。Nyarlathotep 是首个异步非确定性 CP 框架：用标记迁移系统定义编排与网络的操作语义，证明端点投影在异步+非确定性下仍保正确。",
        "en": "Nyarlathotep is the first asynchronous nondeterministic choreographic programming framework, giving labelled-transition-system operational semantics for choreographies and networks and proving endpoint projection correct in the presence of both asynchrony and nondeterminism.",
    },
    "2611.24324": {
        "zh": "编码智能体的 GPU 开销巨大，本文研究能否用更小模型省钱而不掉精度：评测 2024 年以来 36 个开源大小模型于软件工程基准，发现新近小模型正快速逼近大模型；剖析差距结构后设计超时级联——小模型先答、超时升级大模型，在不牺牲准确率的前提下大幅削减推理成本。",
        "en": "Evaluates 36 open-weight models from 2024+ on a software engineering benchmark, finds recent small models closing the accuracy gap with large ones, and designs timeout cascades in which small models answer first and escalate on timeout, cutting inference cost of coding agents without sacrificing accuracy.",
    },
    "2611.24210": {
        "zh": "OmegaHyper 重构 HyperLTL 显式状态模型检查器 AutoHyper：算法不变，但把被处理的自动机分解并缩小，并集成 Kofola ω-自动机取补工具，避免完全物化输入系统与中间自动机。实测大幅缓解状态爆炸，让此前查不动的 HyperLTL 性质变得可检。",
        "en": "OmegaHyper overhauls the explicit-state HyperLTL model checker AutoHyper, keeping its algorithm while decomposing and reducing processed omega-automata and integrating the Kofola complementation tool, substantially mitigating state explosion on HyperLTL properties.",
    },
    "2611.23811": {
        "zh": "Stephen：形式化验证依赖定序器（sequencer）的协调系统实现。从 Corfu、NOPaxos 到 LazyLog、SwitchBFT，十余年 SAC 系统只有纸面证明或协议级有界模型检查；定序器看似简化证明（线性化点放在定序器即可），实则跨视图预言（cross-view prophecy）才是关键。本文给出实现级形式验证并发现真实缺陷。",
        "en": "Stephen formally verifies implementations of sequencer-aided coordination systems (Corfu, NOPaxos, LazyLog, SwitchBFT lineage), using cross-view prophecy to place linearization points despite the sequencer, finding real defects where pen-and-paper proofs and bounded model checking had sufficed.",
    },
    "2611.23792": {
        "zh": "并发正确性见证（correctness witness）可独立验证软件验证器的结论，扩展 ghost 变量后表达力更强，但缺乏配套校验技术。本文用线程模块化抽象解释校验含 ghost 的并发见证：以逐线程分析近似整个并发行为了解 ghost 引用，实现独立于原验证器的复核，补齐「见证产生—见证校验」闭环。",
        "en": "Validates concurrent correctness witnesses with ghost variables via thread-modular abstract interpretation, approximating whole-concurrent-program behavior with per-thread analyses that understand ghost references, closing the produce-validate loop for software verifiers' verdicts.",
    },
    "2611.23715": {
        "zh": "JITAtlas：检查编译器重写是否违反对象生命周期与所有权义务。重写可以保住返回值却违反对象存活期、借用指针支持或到达调用者的所有权。它从优化器代码重建引用与目标计算，检查合法使用、持续借用支持与调用者可见所有权；在独立标注的 58 输入基准上检出全部 29 个缺陷、零误报，优于 PyRefcon。",
        "en": "JITAtlas is a source-level checker that reconstructs reference and target computations from optimizer code and verifies valid uses, continuous borrow support, and caller-visible ownership; on a 58-input independently labeled benchmark it detects all 29 defects with zero false positives, outperforming PyRefcon.",
    },
    "2611.23629": {
        "zh": "VSL（Value Semantics Layer）：为「智能体+分析师共用数据库」补上可机读的操作语义层。既有元数据系统暴露 schema、目录、血缘与治理，却无法表达取值语义；VSL 引入 Value Semantic Types——可复用的分布、关系类操作语义断言，作为持久、规划器可见的基础设施外置化，让自主 LLM 智能体正确理解数据。",
        "en": "The Value Semantics Layer externalizes value semantics as persistent, planner-visible infrastructure via Value Semantic Types, reusable operational semantic assertions on distributions and relations, enabling machine-understandable databases for autonomous LLM agents alongside human analysts.",
    },
    "2611.23335": {
        "zh": "Truthgate：拿「智能体改不了的记录」核查编码智能体是否诚实。每一步都由宿主重跑测试、在智能体看不见的容器里埋隐藏检查、由沙箱外签名者记录全部工具调用；五步付费研究全部预注册。发现仅凭行为标签会高估说谎率；在 Impossible-LiveCodeBench 上测 Claude Sonnet 5.5 等模型的作弊、威慑与披露行为。",
        "en": "Truthgate checks coding agents against a record they cannot edit: tests re-run by the host, hidden checks in containers the agent never sees, and a signed log of every tool call by an external signer; across five pre-registered paid studies, action-only labels over-count lies, quantifying cheating, deterrence and disclosure on impossible tasks.",
    },
    "2611.23334": {
        "zh": "把 AI 编码智能体纳入科研工作流的风险与规程：智能体写的数据分析代码错误可能损害研究者计算机、消耗大量验证资源、让结果被质疑。论文剖析智能体改变生成、验证与复现数值结果的十一个方面，提出六级分级标准与安全环境（文件变更监控、明确规程）的设计，给科研用智能体一套可操作的治理框架。",
        "en": "Analyzes eleven aspects of how coding agents change generating, verifying and reproducing numerical results in scientific research, and proposes a six-level scale plus a secure environment with file-change monitoring and well-defined standards for integrating AI agents into research workflows.",
    },
    "2611.24936": {
        "zh": "JDPI：用对比原型结构检测 LLM 越狱与有害提示，无需训练额外下游分类器。只用二值安全标签构造有害/良性原型，按相对原型距离预测；编码器适配、原型构建与验证全部仅需二值标签，标注需求少于分类器基线 MetaGuard，为安全部署提供轻量检测路径。",
        "en": "JDPI detects jailbreak attempts via contrastive prototype structures: harmful and benign prototypes are built from binary safety labels and predictions come from relative prototype distances, using fewer labeled examples than the classifier baseline MetaGuard without training a downstream classifier.",
    },
    "2611.24788": {
        "zh": "Isabelle Pool Server（IPS）：面向证明器训练与多智能体证明的热会话池验证服务。HTTP API 后面维护温热的 headless Isabelle 会话，支持会话租借回收、内存感知准入控制与每次调用时限；验证接口覆盖单步执行、块级检查与全理论构建，带检查点支持廉价分支回溯，从零构建作最终仲裁。单容器部署，提供 Python 客户端、两个 MCP 服务器与裸 HTTP API。",
        "en": "Isabelle Pool Server is a pooled verification service with warm headless Isabelle sessions behind an HTTP API, offering session leasing, memory-aware admission control and per-call time budgets across single-step, block-level and whole-theory interfaces with checkpoints, deployed as one container with a Python client, two MCP servers and a raw HTTP API.",
    },
    "2611.24428": {
        "zh": "数据驱动控制器的屏蔽器（shield）依赖对物理系统的固定假设，系统演化（开发迭代或部件退化）后假设失效可能致险。本文把控制器与安全屏蔽都当作一等公民模型，提出模型一致性驱动的安全保持方法：随系统演化自动判定屏蔽假设是否仍成立并相应更新，保持受屏蔽数据驱动控制器的安全性。",
        "en": "A model-driven approach treats the data-driven controller and its safety shield as first-class models, using model consistency to keep shield assumptions aligned as the physical system evolves during development or component degradation, preserving safety of shielded data-driven controllers.",
    },
    "2611.24406": {
        "zh": "CaDO：形式化因果推理引导的多智能体框架，自动诊断并修复因果数据集。现有因果数据集标注错误与结构失衡会造成偏见预测与泛化受限；框架分三阶段——形式因果推理、多层次诊断、自动数据修复与生成，用因果引擎的形式化结论引导智能体分工，产出高质量、结构均衡的因果推理数据。",
        "en": "CaDO is a formal-verification-guided multi-agent framework for causal dataset repair and generation, with three stages of formal causal reasoning, multi-level diagnosis, and automated repair/generation, producing high-quality structurally balanced causal reasoning data from incorrect, imbalanced existing datasets.",
    },
    "2611.24037": {
        "zh": "FormalFixer：硬件修复要对齐三件事——规约意图、验证意图与 RTL 行为。FPV 断言失败未必是 RTL 缺陷，也可能来自有缺陷的断言或语义正确但含糊/不完整的规约；既有 RTL 为中心的方法不直接处理这种对齐问题。FormalFixer 联合精化规约、断言与 RTL 实现，把意图对齐纳入修复循环，提升流片前的修复可靠性。",
        "en": "FormalFixer jointly refines specifications, assertions and RTL implementations to align specification intent, verification intent and RTL behavior, addressing the practical repair problem that a failed FPV assertion may stem from a buggy assertion or an ambiguous specification rather than an RTL defect.",
    },
    "2611.23807": {
        "zh": "Sightline：长窗口投机解码加速 SVG 生成。SVG 模型逐 token 一趟前向、绘制很慢；块级起草器每趟猜多 token，但在 SVG 上「整块命中、只在验证窗口末尾结束」，失误罕见且成簇、准确深度远超自然语言。用游程恒等式与三条命题证明窗口加长（直到起草器视界）只需一次验证开销，提出窗口加长的 Sightline，无损提速 SVG 生成。",
        "en": "Sightline exploits the observation that speculative-draft misses on SVG are rare, clumped, and accurate far deeper into blocks than in natural language; a run-length identity plus three propositions show longer windows pay once candidates are wide, yielding lossless speedups for SVG generation.",
    },
    "2611.23779": {
        "zh": "TabBioMed：94 个精心整理的公开生物医学表格数据集基准，横跨电子健康记录、药物发现、基因组、转录组、蛋白组、代谢组、单细胞组学与系统生物学。统一的数据集感知预处理与评测框架支持高维、大样本、缺失与类不平衡场景下的可复现比较，为生物医学表格学习提供标准化评测底座。",
        "en": "TabBioMed is a large-scale benchmark of 94 curated public biomedical tabular datasets spanning EHRs, drug discovery, genomics, transcriptomics, proteomics, metabolomics, single-cell omics and systems biology, unified through standardized dataset-aware preprocessing and evaluation for reproducible comparison.",
    },
    "2611.23761": {
        "zh": "重构型时序异常检测的测试时自适应（TTA）：部署后「正常」本身会漂移，但数据流里混着异常——即便只用基准中标注为正常的样本更新，TTA 是否仍可靠提升检测？受控干预实验表明仅用正常样本更新不总够：更新策略、漂移幅度与异常占比共同决定收益，给出 TTA 增益的条件性结论而非普遍承诺。",
        "en": "A controlled intervention study on test-time adaptation of reconstruction-based time-series anomaly detectors shows that updates restricted to samples labeled normal do not reliably improve detection, with benefits depending jointly on update policy, drift magnitude and anomaly contamination.",
    },
    "2611.23570": {
        "zh": "多智能体系统中接收方等辅助方消息（文本或 latent KV cache）有性能收益但增加延迟。本文研究何时可安全跳过：机制读取接收方无消息时的置信度，用有限样本检验在阈值处证明「跳过后答案变化概率 ≤5%」；检验不过则继续通信。在 OpenBookQA、ARC-Challenge、MMLU-Pro 上量化「省时」与「答案漂移」的权衡。",
        "en": "Studies when a receiver agent can safely and beneficially skip a helper agent's message: a mechanism reads receiver confidence without the message and uses a finite-sample test to certify that at most 5% of skipped answers change with high probability, quantifying latency savings versus answer drift on OpenBookQA, ARC-Challenge and MMLU-Pro.",
    },
    "2611.23362": {
        "zh": "TRACE-MAS：诊断并修复 LLM 多智能体系统中的协作失败。既有防护只做智能体级异常检测，而失败往往源于消息交换与任务依赖等交互层面。TRACE-MAS 从良性轨迹学习正常协作执行模式、检出偏离，再细粒度归因到具体交互并生成修复，弥补「异常可见但真因不明」的缺口。",
        "en": "TRACE-MAS diagnoses and repairs collaboration failures in LLM-based multi-agent systems by learning normal collaborative execution patterns from benign trajectories, detecting deviations, and attributing failures to specific interactions rather than stopping at agent-level anomaly detection.",
    },
}

MERGE_NOTE = "2026-11-20 批次：补 24 篇双语简介。"


def main():
    path = os.path.join(OUT, "summaries.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    added, skipped = 0, 0
    for sid, pair in SUMM.items():
        old = data.get(sid)
        if isinstance(old, dict) and old.get("zh") and old.get("en"):
            skipped += 1
            continue
        data[sid] = {"zh": pair["zh"], "en": pair["en"]}
        added += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    print(f"[ok] summaries.json: +{added} (skipped {skipped}), total {len(data)} - {MERGE_NOTE}")


if __name__ == "__main__":
    main()
