# -*- coding: utf-8 -*-
"""2026-11-18 批次：本期 24 篇待补论文的双语简介（summaries.json）。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- key 一律 arXiv 短号。
- 本轮只补双语简介（摘要全文中译 abstracts_zh 未做）。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2611.19267": {
        "zh": "AI 生成软件与验证制品激增，有界模型检查（BMC）可对软件直接自动检查正确性与安全性质，成为可靠软件保证的实用基础。但有效验证依赖性质选择、输入假设、函数建模与执行界等决策，实践者如何做这些决策缺乏系统证据。本文对 12 家组织的 17 位实践者做访谈与调查，归纳出「小型 harness、默认检查、覆盖有限」的实践形态，并提炼出对自动化验证工具设计的启示。",
        "en": "An interview and survey study with 17 practitioners from 12 organizations on how they apply bounded model checking to software, characterizing their choices of properties, assumptions, function models, and bounds as small harnesses with default checks and limited coverage, and deriving implications for automated verification tooling.",
    },
    "2611.21084": {
        "zh": "CompCert4Lean 把 CompCert 3.17 经验证编译器核心从 Rocq 大规模移植到 Lean：由一名专家指挥并行 LLM 编码智能体，约六周完成。迁移流程沿依赖关系切分开发，先审计翻译后的定义与定理陈述，再对照稳定接口并行重建证明。结果覆盖类型化 CompCert C 到 x86-64 汇编，清偿全部 4,908 条证明义务、无项目专属公理，并能产出可执行 Linux 二进制。",
        "en": "CompCert4Lean is a large-scale port of CompCert 3.17's verified compiler core from Rocq to Lean, completed in about six weeks by one expert directing parallel LLM coding agents. It covers typed CompCert C through x86-64 assembly, discharges all 4,908 proof obligations without project-specific axioms, and produces executable Linux binaries.",
    },
    "2611.21148": {
        "zh": "JavaScript 分析器对检测 Web 应用安全漏洞至关重要，但多数现有工具文档匮乏或闭源，难以理解、修改与复现。本文给出 SAFE（可扩展 ECMAScript 分析框架）的形式化规范与实现：形式定义其架构与组件接口，并讨论以调用图构建为核心的实现挑战，为分析器的设计与演进提供可验证的规范基线。",
        "en": "The paper presents a formal specification and implementation of SAFE, a scalable analysis framework for ECMAScript: it formally defines the architecture and component interfaces and discusses implementation challenges centered on call graph construction, providing a verifiable specification baseline for JavaScript analyzers.",
    },
    "2611.20807": {
        "zh": "量子通信等新兴应用产生海量高维量子数据，经典数据库系统难以满足量子处理与版本管理等需求。QuarkDB 是面向量子数据管理的混合数据库系统：建立关系数据与量子数据的统一对象模型，定义 Quantum SQL 语法，集成混合查询引擎（代价模型路由经典/量子计算）、量子数据版本管理器和分布式并行执行引擎。",
        "en": "QuarkDB is a hybrid database system for quantum data management: it establishes a unified object model for relational and quantum data, defines Quantum SQL, and integrates a hybrid query engine with cost-based routing, quantum data version management, and distributed parallel execution.",
    },
    "2611.21421": {
        "zh": "形式规格是验证的基础，但用 Lean 等定理证明器写规格又慢又依赖专家，是形式正确代码规模化的主要瓶颈。AuXSpec 是一个 Lean 框架：用可执行后置条件（executable postconditions）自动获得「生成的规格是否刻画预期行为」的反馈信号，替代昂贵的显式证明或另写代码+对应性证明，把该信号用于训练与选择自动形式化模型，效果显著优于现有基线。",
        "en": "AuXSpec is a Lean framework for autoformalizing program specifications: executable postconditions provide cheap, automatic feedback on whether generated specifications capture intended behavior, replacing expensive explicit proofs, and this signal measurably improves specification generation over existing baselines.",
    },
    "2611.20195": {
        "zh": "LLM 把需求变成代码时，每条未写明的约束都成了模型生成时的自行决定。受控实验让 72 名参与者在三种规格显性程度下用 LLM 实现并修改 Python 任务：轻量结构（仅结构模板）只把隐藏测试失败减少 8.7%，而要求写明约束、不变量、否定需求与边界条件后改善显著更大。结果划出了「结构模板」与「行为义务」之间的清晰断点，对提示工程与规格工具有直接指导意义。",
        "en": "A controlled experiment with 72 participants implementing and revising Python tasks with an LLM under three levels of specification explicitness: lightweight structure reduces hidden-test failures by only 8.7%, while requiring explicit constraints, invariants, negative requirements, and edge cases yields substantially larger improvements, marking a clear break between structure and behavioral obligations.",
    },
    "2611.19960": {
        "zh": "智能体 harness 是围绕语言模型的程序：构造请求、执行工具、决定哪些动作免确认、存储会话、故障恢复并向人呈现结果。这些决策大多散落在代码里很少被写下来，每个 harness 都要重新踩一遍同样的坑。本文把这些决策写成可测试的不变量：给出带信任边界的系统模型、六组 30 张决策卡（各含选项、代价、不变量、破坏它的角落案例、测试与评估证据）。",
        "en": "The paper writes down the implicit decisions of LLM agent harnesses as testable invariants: a system model with trust boundaries and 30 decision cards in six groups, each with options, costs, an invariant, the corner cases that break it, a test, and evaluation evidence.",
    },
    "2611.19618": {
        "zh": "动态量子线路在运行中途测量量子比特并按结果选择后续操作，分支使量子比特等待经典控制器的往返。qlin 是降低这段等待的编译器：把操作移出分支而不延迟程序，该性质在 Lean 4 中证明；对几乎总是零综合的纠错解码器，把大概率综合编译进一条多路分支、其余保留原程序，由代价模型决定何时值得做经典控制转换。",
        "en": "qlin is a compiler that reduces qubit waiting time in dynamic quantum circuits: it moves operations out of branches without delaying the program (a property proved in Lean 4), and for error-correction decoders compiles likely syndromes into a single multiway branch, with a cost model deciding when classical control rewrites are worthwhile.",
    },
    "2611.19569": {
        "zh": "循环不变式合成是自动程序验证的长期障碍，前沿 LLM 有望但只能经第三方 API 使用，妨碍可复现与本地部署。本文提出失败驱动的数据构造方法：受变异测试启发，对真值不变式施加语义变异算子生成「有缺陷的候选」，让小模型从失败中学习；微调后的小模型在循环不变式合成上达到有竞争力的通过率，且可本地部署。",
        "en": "A failure-driven data curation method inspired by mutation testing: semantic mutation operators generate defective candidate invariants from ground truth, and small language models fine-tuned on this data achieve competitive pass rates in loop invariant synthesis while remaining locally deployable.",
    },
    "2611.19079": {
        "zh": "静态代码分析工具误报率高，已有研究用机器学习分类误报，但多聚焦有限告警类型、用大数据集。本文用小数据集做实证研究，比较多种 ML 方法对静态分析误报的分类效果，评估在小样本约束下的可行性与局限，为资源受限团队的误报过滤提供务实参考。",
        "en": "An empirical study using small datasets to classify false positives from static analysis tools with machine learning, examining feasibility and limitations of ML-based alarm triage when data is scarce, complementing prior work that assumes large datasets.",
    },
    "2611.18930": {
        "zh": "安全基准被当作理解生成式 AI 风险的首要工具，但越来越多证据表明它们满足不了真实安全评估的需求。本文对学术界与工业界的 AI 安全基准开发者做五次访谈，发现「预期有用性」与「部署系统安全评估中的实际有用性」之间存在脱节，两大成因是评分者间信度难以达成与基准维护的持续负担。",
        "en": "Interviews with five AI safety benchmark developers in academia and industry reveal a disconnect between the intended usefulness of safety benchmarks and their practical usefulness in evaluating deployed systems, driven by difficulty achieving inter-rater reliability and the ongoing burden of benchmark maintenance.",
    },
    "2611.18926": {
        "zh": "数据库智能体诊断流水线故障，但根因只有配上「智能体确实查过的证据」才可信；现有基准只给最终答案打分，分不清「有证据支撑的正确诊断」与「蒙对」。DataTrace 是证据接地根因定位基准：在 83 个可运行环境中用受控故障注入派生根因与证据路径、无需人工标注，同时给根因正确性与支撑证据覆盖度打分。最佳智能体根因定位尚不理想，证据覆盖是主要短板。",
        "en": "DataTrace is a benchmark for evidence-grounded root-cause localization over typed graphs of database artifacts: controlled fault injection across 83 runnable environments derives root causes and evidence paths without human annotation, scoring both root-cause correctness and evidence coverage; best agents still struggle, with evidence coverage the main weakness.",
    },
    "2611.18890": {
        "zh": "部署编码智能体的团队需要用自家代码构建基准，但人工策展与验证成本高，未验证的基准还会悄悄误导。Benchmark Factory 是带人工检查点的自主元智能体循环：智能体对落库的生产代码变更写检索查询、让已知相对强弱的模型跑候选、诊断失败并修补查询/提示/配置，直到通过无需逐任务人工标注的质量锚点；已在多团队生产代码上构建基准。",
        "en": "Benchmark Factory is an autonomous meta-agent loop with human checkpoints that builds coding-agent benchmarks from a team's own code: it writes sourcing queries over landed production changes, runs models of known relative strength, diagnoses failures, and repairs candidates until they clear label-free quality anchors.",
    },
    "2611.21548": {
        "zh": "入侵检测要在攻击标签稀缺或残缺时识别不断演化的恶意行为。TRACE 是拓扑感知的图对比学习框架：仅从良性系统活动图学习，结合消息传递与拓扑（持续同调）表示，在对比目标优化的同一投影嵌入空间里打异常分，无需攻击标签即可同时捕捉局部交互与图级结构偏差，在标签高效设定下优于基线。",
        "en": "TRACE is a topology-aware graph contrastive learning framework for label-efficient intrusion detection: it learns from benign system-activity graphs by combining message-passing with topological representations and scores anomalies in the same projected embedding space, capturing both local interactions and graph-scale structural deviations without attack labels.",
    },
    "2611.21299": {
        "zh": "LLM 正把数学推向「证明过剩」时代，核心挑战变成如何确保海量 AI 生成证明的正确性并转化为可信的机器验证知识。Turing Agent 是编排研究级数学端到端形式验证的智能体 harness：双尺度架构整合定理形式化与证明搜索，在 IMO-ProofBench 等基准上表现领先，并展示了把研究级数学命题完整形式化的案例。",
        "en": "Turing Agent is an agent harness orchestrating end-to-end formal verification of research-level mathematics: its two-scale architecture integrates theorem formalization and proof search, achieving leading results on benchmarks like IMO-ProofBench and fully formalizing research-level mathematical propositions.",
    },
    "2611.21003": {
        "zh": "K2-Horizon 是六款全开源大模型的模型群，从 0.9B 稠密模型到 375B-A23B MoE，面向通用推理与数学/科学、软件工程、深度研究、办公自动化等智能体任务，在同级开源模型中领先或具竞争力。建模上引入 MoVA（把 MoE 用于注意力值投影）与 softplus 注意力门控，36B-A4B 模型同时用上两者、接近更大模型的表现。",
        "en": "K2-Horizon is a fleet of six fully open language models (0.9B dense to 375B-A23B MoE) leading or matching strong open models of their size on agentic and coding benchmarks, introducing Mixture-of-Value Attention and softplus attention gating to strengthen reasoning.",
    },
    "2611.20997": {
        "zh": "跨领域构建多智能体应用要把多样需求转成可执行系统，涉及任务分解、智能体与工具选择、执行组织；但现有方法各自独立发展，任务规格、组件资源与执行设定互不兼容，难以比较。OpenMAS-GApp 是领域自适应多智能体应用构建的综合基准，统一设定下评估这些能力并揭示差距。",
        "en": "OpenMAS-GApp is a comprehensive benchmark for domain-adaptive multi-agent application construction, unifying task specifications, component resources, and execution settings so that previously incomparable methods for agent generation, architecture design, workflow generation, and component selection can be evaluated together.",
    },
    "2611.20695": {
        "zh": "LLM 被广泛探索用于工业任务，但少有基准按认知需求分层评估工业知识。IndustrialKnowEval 含 43,282 个样本，覆盖航空航天、电力、冶金等七个行业的 21 种任务，按记忆、理解、推理、工程应用四层认知需求组织，由企业领域专家与资深研究者参与构建，揭示模型在工程应用层的明显短板。",
        "en": "IndustrialKnowEval is a benchmark of 43,282 samples covering 21 task types across seven industrial sectors, organized into four levels of cognitive demand (memory, comprehension, reasoning, engineering application), built with enterprise domain specialists and revealing clear weaknesses at the engineering-application level.",
    },
    "2611.20693": {
        "zh": "扩散语言模型每次前向可提交多个 token：置信度过阈值的掩码位按任意顺序提交、无一过阈值则回退提交最自信的一个、且提交后不再修订。宽窗口让解码器远远领先于文本、应该更快，却常损精度。本文逐 commit 追踪四个现成 DLM 在数学/代码/翻译/摘要上的表现，定位模型在何处自信、哪些 commit 造错，并发现多数 token 都在走回退路径。",
        "en": "A commit-level analysis of threshold decoding in diffusion language models: tracing every commit of four off-the-shelf DLMs across math, code, translation, and summarization, locating where the model is confident and which commits cause errors, and finding that most tokens fall back to the conservative single-commit path.",
    },
    "2611.20671": {
        "zh": "基于 Tamarin 的安全协议形式验证需要专家手写多重集重写规则与时序逻辑引理，LLM 直译自然语言协议描述时，语法、可达性与性质级错误会在多步建模中复合，而「既写又自评」的单智能体难以定位问题。MASTA 用三个创新应对：操作-评估角色分解（Architect 建模、Evaluator 定位错误）、跨建模阶段回溯循环、以及按性质上下文指导引理生成。",
        "en": "MASTA is a multi-agent system for end-to-end Tamarin modeling and analysis of security protocols, combining operational-evaluative role decomposition (Architect models, Evaluator localizes errors), a loop that backtracks across modeling phases, and property-context-guided lemma generation.",
    },
    "2611.20484": {
        "zh": "SMT 求解器暴露大量配置选项，决定既有算法在给定负载上的表现。本文提出首个用通用 LLM 智能体调优 SMT 求解器配置的工作流：智能体阅读求解器文档、源码与持久实验记录提出选项改动，确定性 harness 度量每个提案、验证返回模型、并按竞赛分组分别选择。约九周的 cvc5 调优战役记录 13 个分组、36 种逻辑的 4,545 条提案，显著提升求解成绩。",
        "en": "The first workflow using general-purpose LLM agents to tune SMT solver configurations: agents read solver documentation, source code, and persistent experiment records to propose option changes, while a deterministic harness measures each proposal and validates returned models; a nine-week cvc5 campaign recorded 4,545 proposals across 13 divisions and 36 logics with significant gains.",
    },
    "2611.20423": {
        "zh": "金融智能体产出的数值断言即使计算执行正确也可能出错：报告期间错配、来源不支持、单位不兼容、金融定义错误。FinVerify 是证据接地的金融智能体数值断言验证框架：基于对 190 条错误轨迹的分析定义五类错误（时间完整性、来源保真、可比性、会计完整性、金融模型保真）并操作化为验证协议，由 LLM 结构化抽取断言与证据后逐一核查。",
        "en": "FinVerify is an evidence-grounded framework for verifying financial agents' numerical claims: from an analysis of 190 incorrect trajectories it defines five error categories (temporal integrity, source fidelity, comparability, accounting integrity, financial-model fidelity), operationalized as verification protocols applied to structured claims and evidence.",
    },
    "2611.20039": {
        "zh": "IsaGraphLib 是 Isabelle/HOL 中经形式验证的图算法库，覆盖组合优化的主要问题：可达性、最短路、最小生成树、匹配、最大流与最小费用流。算法用到了绝大多数标准设计技术：图搜索、拟阵贪心、动态规划、增广路径、花收缩、阻塞流、push-relabel、缩放、原始对偶、随机化与证书检查，并附不同图类型间的适配器。",
        "en": "IsaGraphLib is a library of formally verified graph algorithms in Isabelle/HOL covering reachability, shortest paths, minimum spanning trees, matching, maximum flow, and minimum-cost flow, employing most standard design techniques including greedy on matroids, blossom contraction, push-relabel, primal-dual, randomization, and certificate checking.",
    },
    "2611.21298": {
        "zh": "构建智能体应用要把 LLM 调用、工作流结构与状态、模型引导路由组合起来；SDK 与框架下开发者靠支撑代码衔接各组件，工作流一变就要联动修改，且执行逻辑分散在应用与框架内部、编译器看不清控制流与状态依赖、难以自动优化。本文提出专为智能体应用设计的编程语言，把这三类组件作为一等公民，让编译器获得全局可见性。",
        "en": "An agent-native programming language that makes LLM operations, workflow structure and state, and model-guided routing first-class citizens, eliminating glue code, giving compilers full visibility into control flow and state dependencies, and enabling automatic optimization for agentic applications.",
    },
}

MERGE_NOTE = "2026-11-18 批次：补 24 篇双语简介。"


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
