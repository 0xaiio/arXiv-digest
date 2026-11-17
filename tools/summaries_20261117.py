# -*- coding: utf-8 -*-
"""2026-11-17 批次：本期 24 篇待补论文的双语简介（summaries.json）。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- key 一律 arXiv 短号。
- 本轮只补双语简介（摘要全文中译 abstracts_zh 未做）。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2611.18477": {
        "zh": "软件工程与机器学习中大量「反馈驱动的黑箱过程」（策略生成输入→观测反馈→指导下一轮输入）缺乏统一的评测框架：许多策略是在对系统的结构性假设下设计的，而真实系统往往不具备这些假设。本文提出一个随机化评测框架，用马尔可夫链建模策略与系统的交互并用仿真评估策略表现，把方法论研究（基准测试）与实际部署（优化）两个此前割裂的社区连接起来。",
        "en": "The paper introduces a stochastic evaluation framework for feedback-driven black-box processes, modeling policy-system interaction with Markov chains and simulation, thereby connecting the benchmarking and deployment communities that study such policies separately.",
    },
    "2611.18338": {
        "zh": "Text-to-SQL 基准普遍把问题当独立请求评估，忽视了「同一数据库上先前查询可复用」的场景。作者提出 HARE（History-AwaRe Text-to-SQL BEnchmark），由 4 个数据集、823 条已验证查询派生出的 1,600 条请求组成，标注每条请求复用与改写了历史查询的哪些成分，测量把历史 SQL 适配到新问题的准确率与成本。",
        "en": "HARE is a history-aware Text-to-SQL benchmark of 1,600 requests derived from 823 verified queries over four datasets, annotated by which query components are preserved or edited, measuring accuracy and cost of adapting historical SQL to new questions.",
    },
    "2611.18293": {
        "zh": "代码审查智能体能否抓住 GDPR 等法律要求的隐私缺陷，此前几乎没有数据集支撑。PrivacyPR 从 1,469 个仓库收集 2018-06 至 2024-01 间 4,131 条已合并 PR（含提交、diff、评审讨论），用 LLM 打上隐私相关性、修复类型与 GDPR 原则标签，提供 1,169 条高置信隐私修复与 1,643 条非修复 PR，可用于基准测试隐私感知的代码评审。",
        "en": "PrivacyPR is a benchmark dataset of 4,131 merged GitHub PRs from 1,469 repositories (2018-2024) with commits, diffs, review discussions, and LLM labels for privacy relevance, fix type, and GDPR principles, yielding 1,169 high-confidence privacy fixes for benchmarking privacy-aware code review.",
    },
    "2611.18069": {
        "zh": "DPOR（动态偏序约减）靠在交错关系上定义等价类来压缩并发程序的探索空间，Mazurkiewicz 迹等价之外的 reads-from / reads-value-from 等价更粗、理论上类更少，但「更粗就更快」的承诺并不总是兑现。本文把等价关系参数化为可插拔组件，给出统一的 DPOR 框架并系统量化粗化的实际收益：收益取决于等价类内部如何避免重复访问，粗化甚至可能拖慢探索。",
        "en": "The paper presents a unified, equivalence-parameterized DPOR framework and quantifies the actual benefit of coarser equivalences (reads-from, reads-value-from) over Mazurkiewicz trace equivalence, showing the promise of faster exploration does not always materialize and can even slow search.",
    },
    "2611.18055": {
        "zh": "DeCompCert 是一个经 Rocq（Coq）机器验证的反编译器：面向 CompCert 生成的 AArch64 汇编，通过九个逆向遍重建 CompCert C，把演绎验证的变换与翻译验证相结合——不可信的 OCaml 与 Datalog 分析提出候选重建，经验证的校验器只接受满足语义对应关系的候选。组合正确性定理保证被接受的 C 重建的每个已定义安全行为都与输入汇编匹配；在安全性假设下两者观测等价。",
        "en": "DeCompCert is a Rocq-verified decompiler for CompCert-generated AArch64 assembly, reconstructing CompCert C through nine reverse passes that combine deductively verified transformations with translation validation: untrusted OCaml and Datalog analyses propose candidates, verified validators accept only semantically corresponding ones, and the composed theorem guarantees behavioral equivalence under a safety assumption.",
    },
    "2611.18036": {
        "zh": "把遗留 C 代码迁移到 Rust 是提升软件安全的热门路线，但现有转换器（无论规则式还是 LLM 式）都没有形式保证，正确性检查止步于测试与有界检查。R2C2 在 LLVM IR 层做 C→Rust 翻译验证：在 Rocq 中证明 Rust 程序精化（refine）C 程序，即 Rust 侧的每个行为都能被 C 侧匹配。证明由 LLM 辅助生成，并通过差分翻译验证等手段检验 LLM 生成引理的健全性。",
        "en": "R2C2 performs C-to-Rust translation validation at the LLVM IR level by proving in Rocq that the Rust program refines the C program. Refinement proofs are generated with AI assistance, and soundness of the LLM-generated lemmas is checked via differential translation validation.",
    },
    "2611.17880": {
        "zh": "执行多步工具调用的 LLM 智能体要同时满足任务完成（效用）与领域政策/正确性约束（安全），两者有张力：封锁不安全动作虽阻止违规，却可能让智能体无路可走。Soteria 用「经验证的分层规划 + 运行时强制（runtime enforcement）」调和两者：执行前先生成结构化计划并证明其满足规格，执行时由强制器监控并按需回退，兼顾安全与效用。",
        "en": "Soteria reconciles safety and utility for multi-step LLM agents through verified hierarchical planning plus runtime enforcement: the agent first produces a structured plan proven against specifications, then a monitor enforces them at execution with principled recovery instead of hard blocking.",
    },
    "2611.17827": {
        "zh": "GPU 栈式 reconvergence（共享 warp PC）执行高效，但会把发散路径固定串行化，可能死锁依赖 warp 内同步的程序：自旋等待的子组会饿死持有资源的兄弟子组。独立线程调度（ITS）粒度更细但硬件代价高。SIMTurn 是轻量的编译器-硬件协同机制，在保留栈式 reconvergence 的同时让发散子组可向前推进。",
        "en": "SIMTurn is a lightweight compiler-hardware mechanism that enables forward progress among divergent subgroups while retaining stack-based reconvergence, avoiding the serialization-induced deadlocks of stack-based SIMT without the full hardware cost of Independent Thread Scheduling.",
    },
    "2611.17780": {
        "zh": "用托管 LLM 智能体做 Text-to-SQL 准确率最高，但每查询调外部 API 又慢又贵且暴露敏感查询（例：日均 1 万次的 Claude Opus 智能体按牌价一年超 7 万美元）。LuthorSQL 是一个非自回归的 7B 本地模型，作为快速「系统 1」闸门：简单查询本地直答，疑难查询才升级给较慢的 LLM 智能体（系统 2），在保准确率的前提下大幅降低成本与延迟。",
        "en": "LuthorSQL is a non-autoregressive 7B Text-to-SQL model that serves as a fast System 1 gate in front of a slower hosted LLM agent, answering simple queries locally and escalating only hard ones—cutting cost and latency without compromising accuracy.",
    },
    "2611.17770": {
        "zh": "歧义是 Text-to-SQL 的顽固难题：欠指代的自然语言问题可能对应多个合理 SQL。近期工作靠多轮澄清，但严重依赖 LLM 参数知识做临时推理，效果有限且成本高。作者观察到许多歧义错误源于列 grounding 的歧义，提出 Bridge——一个基于数据库证据的交互式消歧框架，用数据库自身的统计与内容证据来定位用户真实意图。",
        "en": "Bridge is a database-grounded disambiguation framework for Text-to-SQL: instead of relying on LLM parametric knowledge for ad hoc clarification, it uses evidence from the database itself (schema statistics and content) to resolve ambiguously grounded columns and recover the user's intended interpretation.",
    },
    "2611.17681": {
        "zh": "完整的 HTML5 游戏生成要求智能体协同规则、交互、状态与呈现，单一总分掩盖了「哪些能力已实现、哪些需求未满足」。OCTAVE 按 8 个能力维度组织，含 180 个任务与 1,800 条评估需求（来自真实玩家请求、商业玩法复原与人类专家设计），覆盖 PC/移动 Web 与 2D/3D；评估需求区分「完整性」（公开声明的核心实现）与「正确性」。",
        "en": "OCTAVE is a capability-resolved benchmark for end-to-end HTML5 game generation: 180 tasks and 1,800 evaluation requirements across eight capability dimensions, sourced from real player requests, commercial-mechanics reconstruction, and expert design, covering PC/mobile Web and 2D/3D, with requirements distinguishing completeness from correctness.",
    },
    "2611.17669": {
        "zh": "SZZ 算法把修复 bug 的提交追溯到引入 bug 的提交，其标签支撑缺陷预测数据集与大量 MSR 研究；但 SZZ 实现大多用从真实项目挖掘的 oracle 评估，而真实历史把多种因素混在一起，总分说不清成败原因。SZZBench 从声明式场景生成带显式 oracle 的受控 Git 仓库，在声明的演化事件下为任意 SZZ 实现打分，从而解释「为什么错」。",
        "en": "SZZBench generates ordinary Git repositories from declarative scenarios with explicit oracles and scores any SZZ implementation under declared evolution events, replacing mined real-project oracles whose mixed factors obscure why an implementation succeeds or fails.",
    },
    "2611.17587": {
        "zh": "带效应的语言通常有两套独立给出的语义：基于（自由）模型的指称语义与按效应定制归约规则的操作语义，两者的关系只能事后建立。本文给出统一构造：在按值推入调用（call-by-push-value）上扩展某代数理论的操作，指称解释与操作归约都从同一代数理论构造，并证明等式典范形式（equational canonical forms）等性质，把两套语义在同一框架内对齐。",
        "en": "The paper gives a unified construction where both denotational interpretation and operational reduction are built from a single algebraic theory of effects, working with call-by-push-value extended by the theory's operations and proving equational canonical forms, aligning the two semantics a priori rather than a posteriori.",
    },
    "2611.17440": {
        "zh": "主流编码智能体基准只评二元的任务成败，把执行过程当黑盒，掩盖了产生结果的行为差异。作者分析 143,209 条执行轨迹（125 种智能体配置、117 个模型），开发规则解析器把原始轨迹映射为仓库搜索、文件编辑、测试执行等高层动作，并用六模型共识在 500 个事件上审计其预测。结果显示解出率相近的智能体，其行为轨迹可能截然不同。",
        "en": "Analyzing 143,209 execution trajectories from 125 agent configurations spanning 117 models, the authors develop a rule-based parser mapping raw traces to high-level actions (repository search, file editing, test execution) audited against a six-model consensus, showing agents with similar solve rates can exhibit very different behavioral trajectories.",
    },
    "2611.18516": {
        "zh": "屏幕历史可作为人与智能体的可搜索视觉记忆，但它必须随截图到达实时编码与索引：OCR 索引快但丢失视觉信息，视觉编码又要 2 秒以上。StreamEmbed 利用「多数像素在截图间重复」这一增量特性，仅凭像素差异引导，结合空间分块与哈希缓存实现增量视觉嵌入，把每张新截图的编码开销降到近实时。",
        "en": "StreamEmbed is an incremental visual embedding system for screenshot retrieval that exploits pixel redundancy across screenshots: guided solely by pixel differences, it combines spatial partitioning and hash caching to encode and index each arriving screenshot in near real time.",
    },
    "2611.18471": {
        "zh": "LLM 验证器越来越多地被用来评估智能体执行，但其可靠性通常只在轨迹的单一表示下度量；部署中同一执行可能经工具组合、委托边界或历史压缩暴露给验证器，可直接观测的证据随之改变。作者提出 Verification Transport——度量验证器判断在抽象边界两侧是否保持稳定性的可靠性测试，并发现部分判断在抽象后不可迁移。",
        "en": "Verification Transport is a reliability test measuring whether LLM verifier judgments remain stable when the same agent execution is exposed through composed tools, delegation boundaries, or compacted histories—abstraction changes that alter what execution evidence the verifier can directly observe.",
    },
    "2611.18220": {
        "zh": "科学论文中的数学证明常冗长且依赖对早期结果的引用链，读者与审稿人难以逐步核验。本文面向系统辨识与控制领域的读者（无需形式方法背景）介绍 Lean 4 证明助手：先用两个初等例子展示如何阅读 Lean 证明，再把「笔纸证明→机器检验证明」的过程用于系统辨识中的一个真实定理。",
        "en": "An introduction to the Lean 4 proof assistant for a system identification and control audience with no prior formal-methods exposure: two elementary examples show how a Lean proof is read, then a real theorem from system identification is carried from pen-and-paper to machine-checked proof.",
    },
    "2611.18190": {
        "zh": "许多合成时间序列应用需要远长于训练窗口的长序列：可从短窗口池拼接（需决定取哪些窗口、什么顺序、接缝如何处理），也可由长序列生成器直接产出。MarathonTS 是首个在统一协议下比较两条路线的公开基准：9 个开放小时级数据集、10 个种子，所有方法产出等长序列，按保真度与下游任务效用评估。",
        "en": "MarathonTS is the first open benchmark comparing long synthetic time series from window assembly versus long-series generators under one protocol: nine open hourly datasets, ten seeds, equal-length series, evaluated by fidelity and downstream task utility.",
    },
    "2611.18130": {
        "zh": "LLM 在金融领域的应用需要覆盖不同国家金融体系的基准，而现有基准对国别金融系统覆盖有限，且题目泄露进训练数据后难以保持时效。JFinBench 从 2026 年版六类定期举行的资格考试（会计、税务、理财、银行）抽取 321 题，构建可持续更新的日本金融基准。",
        "en": "JFinBench is a continuously refreshable Japanese financial benchmark of 321 examples drawn from the 2026 editions of six regularly administered certification exams covering accounting, tax, financial planning, and banking.",
    },
    "2611.17955": {
        "zh": "现有可复现的 Web 智能体基准只覆盖少量应用、模态限于文本+视觉；live 基准站点覆盖广却牺牲可复现性（页面与数据在轮次间漂移），且都不评估音视频内容理解。WebArena-Pro 用同构异质站点复现真实网站，支持多模态内容与有状态工作流，兼顾可复现性与覆盖面。",
        "en": "WebArena-Pro is a heterogeneous, multimodal, reproducible benchmark for web agents: it replicates real websites with homogeneous heterogeneous sites, embeds audio/video content, and supports stateful workflows, combining the reproducibility of static benchmarks with the coverage of live ones.",
    },
    "2611.17884": {
        "zh": "一种逻辑能为「它自己的副本」证成什么？作者在 Isabelle/HOL 中把 Church 简单类型论深度嵌入（Henkin 语义 + 自然演绎），分两层回答：不带无穷公理的逻辑可由「只有一个个体的标准模型」的一层 Isabelle/HOL 直接证成；带 Dedekind 无穷公理的逻辑只能在扩展了足够大集合论宇宙的 Isabelle/HOL 中证成。两层都出现在 Harrison 对 HOL Light 的自验证中，本形式化补齐了 Henkin 完备性。",
        "en": "The paper mechanizes in Isabelle/HOL the soundness, completeness, and consistency of Church's simple theory of types (deep embedding, Henkin semantics, natural deduction) in two tiers: without an axiom of infinity it is certified by plain HOL; with a Dedekind-style infinity axiom only within HOL extended by a large enough set-theoretic universe, adding Henkin completeness over Harrison's self-verification of HOL Light.",
    },
    "2611.17776": {
        "zh": "Thomson 问题求球面上 N 个单位电荷的最小库仑能构型；大 N 的最优已知构型由 Cambridge Cluster Database 维护，其最大 N 条目设定于 2026 年 10 月。本文用 LLM 智能体搭建的搜索流水线，报告 N=912、1382、2502 的构型，能量分别低于数据库值 0.0036186、0.0109730、0.0614033，且全部经精确整数算术认证、数值上是模旋转的严格局部极小，并保持数据库构型的缺陷清单与疤痕成分。",
        "en": "Using a search pipeline built with LLM agents, the paper reports Thomson-problem configurations for N = 912, 1382 and 2502 with Coulomb energies 0.0036–0.0614 below the Cambridge Cluster Database values, certified by exact integer arithmetic as strict local minima modulo rotations while preserving the defect inventory and scar compositions.",
    },
    "2611.17680": {
        "zh": "AIoT 系统把传感时间序列与专家报告、新闻等外部文本结合，但模型对「文本与传感历史一致/冲突」时的使用可靠性尚不清楚。作者提出首个按文本-历史关系组织的真实诊断基准：气象、维基百科流量、金融行情三域共 1,762 个文本-窗口对，按文本方向与历史趋势一致、相反或未述标注为 Aligned/Conflicting/Unspecified，在十个模型上诊断多模态时序预测的失败模式。",
        "en": "The paper introduces the first real-world diagnostic benchmark organized by text-history relationship for multimodal time series forecasting: 1,762 text-window pairs across weather, Wikipedia traffic, and market data, labeled Aligned, Conflicting, or Unspecified by whether the text's direction agrees with, opposes, or is absent from the historical trend.",
    },
    "2611.17556": {
        "zh": "因果发现有望找出哪些记录变量驱动产品质量、良率、能耗等过程目标，但已知因果的工业过程数据稀缺，且现有基准中目标因果识别的难度或由已录数据固定、或对整图统一设置。本文提出面向工业过程目标中心因果发现的合成基准：生成器是受批生产启发的两级结构因果模型，由控制回路、延迟效应等单现象组件拼装，可独立控制目标相关的识别难度。",
        "en": "The paper presents a synthetic benchmark for target-centric causal discovery in industrial processes: its generator is a two-level structural causal model inspired by batch production, assembled from components each modeling one phenomenon (control loops, delayed effects), allowing the difficulty of identifying a target's causes to be controlled independently.",
    },
}


def main():
    p = os.path.join(OUT, "summaries.json")
    with open(p, encoding="utf-8") as f:
        summ = json.load(f)
    added = 0
    for sid, val in SUMM.items():
        old = summ.get(sid)
        # value 可能为旧版纯字符串或 {"en","zh"}
        if isinstance(old, dict) and old.get("zh") and old.get("en"):
            continue
        summ[sid] = dict(val)
        added += 1
    with open(p, "w", encoding="utf-8") as f:
        json.dump(summ, f, ensure_ascii=False, indent=1)
    print(f"summaries.json: +{added} -> {len(summ)}")


if __name__ == "__main__":
    main()
