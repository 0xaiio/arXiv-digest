# -*- coding: utf-8 -*-
"""2026-11-11 批次：本期 24 篇待补论文的双语简介（summaries.json）。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- key 一律 arXiv 短号。
- 本轮只补双语简介（摘要全文中译 abstracts_zh 未做）。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2611.11117": {
        "zh": "Linux eBPF 验证器的抽象域证不出的安全条件由内核内证明检查器核对用户态证明，检查器单个 bug 即可危及整个内核；作者在形式化 BCF 检查器时发现 13 个 bug（不健全重写规则、静默跳过的证明步骤、内存安全错误），并演示伪造证书可让内核接受任意不安全 eBPF 程序。Keel 在 Lean 中把检查器写成纯函数程序并对位向量语义证明可靠性，且把检查器步骤与数学重写规则解耦以便扩展；再用 EmbC 深嵌入 C 片段实现，证明 C 实现精化功能规格、无未定义行为与内存泄漏，并用摊还势能法证明线性时间与内存界。Keel 构造即正确，且比 BCF 检查器总共快 1.3 倍、在最慢的 1.4% 证书上快 2 倍。",
        "en": "Keel is a formally verified in-kernel proof checker for Proof-Carrying BPF. While formalizing the BCF in-kernel checker the authors found 13 bugs, and forged certificates can trick the kernel into accepting arbitrary unsafe eBPF programs. Keel specifies the checker as a pure functional program in Lean, proves soundness against bit-vector semantics, implements it in EmbC with a proved refinement (no undefined behavior or memory leaks), and proves linear time and memory bounds; it is faster than the BCF checker (1.3x overall, 2.0x on the slowest 1.4% of certificates).",
    },
    "2611.12412": {
        "zh": "LLM 智能体常成组部署并共享基础设施，已有研究靠提示词告知伙伴存在或直接要求协调；本文问：只靠共享状态、无任何提示，协调是否仍会出现，并给出首次独立复现。四个智能体各领一小段算术任务和一个被呈现为私有草稿区的键值存储，其中两个持有同一计算互补的一半，提示词只字未提其他智能体、共享或协作；环境按书面协议独立重建，两次实现都对设计、数据与分析做哈希锁定。联合成功只通过共享存储发生；模型是否协调不取决于厂商档位，而取决于它是否写下中间结果并再次查看存储，一句「提交前再检查工作区」即可开关这一行为，结论在复现中保持。实践含义：智能体间共享状态就是通信信道，应分离、命名空间化并记录日志。",
        "en": "The study asks whether coordination between LLM agents arises through shared state alone, with no prompt disclosing other agents, and provides the first independent replication. Four agents received arithmetic tasks and a key-value store presented as private scratch space; joint success occurred only via the shared store, and one sentence—'check your workspace again before submitting'—switched the decisive second look on and off. Shared agent state is a communication channel and should be separated, namespaced and logged.",
    },
    "2611.12338": {
        "zh": "作者回顾自己从形式化方法转向模糊测试的路径：形式化承诺数学化的强正确性保证，但多年难以规模化；模糊测试不够有原则却「就是好用」，能应用于超大系统并高效找到开发者真正会修的 bug。经 GPUVerify（GPU 核验证）与 GraphicsFuzz（GPU 编译器随机测试）两个项目，作者主张 oracle 问题（如何判定测试输出对错）是两者的智识纽带，并在 GPU 编程语言设计上继续有针对性地使用形式化。最后讨论生成式 AI 能否成为让形式化规模化的缺失要素，并介绍 Keystone 项目的大规模形式化计划。",
        "en": "A personal account of moving from formal methods to fuzzing via GPUVerify and GraphicsFuzz. The author argues the oracle problem provides an intellectual link between fuzzing and formal methods, describes targeted uses of formal methods in GPU language design, and asks whether generative AI is the missing ingredient that lets formal methods scale, via the Keystone project.",
    },
    "2611.13250": {
        "zh": "验证技术已能处理较大项目，但项目管理手段跟不上：工具跑通只说明证明闭合，实际达成什么取决于被验代码的规格与证明中的未验证假设（如对未验证库的行为假设），人工核查既易错又昂贵。作者提出自动化技术，核心是证明依赖分析：对项目中每个证明义务自动计算其所依赖的规格、语句与假设。该分析支持证明审计（列出证明依赖的全部假设）、判定程序中哪些语句受规格约束（衡量规格强度），并据此提出验证项目的新进度指标、指导后续验证以最大化进度。实现于 Viper 符号执行后端并提升至 Go 验证器 Gobra，在含已验证互联网路由器的真实基准上评估。",
        "en": "The paper presents automated techniques to assess and guide verification projects, based on proof dependency analysis: for each proof obligation it computes the specifications, statements and assumptions needed to prove it. This enables proof audits, measuring specification strength, and a novel progress metric, implemented in Viper's symbolic execution backend and lifted to the Go verifier Gobra.",
    },
    "2611.13401": {
        "zh": "真实使用中往往缺测试用例，LLM 生成的代码难以自动验证。SPARK 在共识验证（同时生成代码解与测试、按功能一致性评价）之上引入对题面的保义变异：改写、语法调整、函数重命名等；对每个变异描述生成一组代码解与测试，解的质量由其一致通过所生成测试的程度衡量。在 LiveCodeBench、BigCodeBench、DLBench 三个基准与三个 LLM（o4-mini、DeepSeek-R1-Basic、Gemini-2.5-Pro）上，SPARK 超过最先进的共识验证方法最多 4.1%，适合传统验证资源稀缺的场景。",
        "en": "SPARK adds semantic-preserving mutations of problem descriptions (paraphrasing, renaming, etc.) to consensus-based verification of LLM code generation: for each mutated description it generates solutions and tests and scores solutions by how consistently they pass the generated tests. Across LiveCodeBench, BigCodeBench and DLBench with three LLMs, SPARK outperforms state-of-the-art consensus verification by up to 4.1%.",
    },
    "2611.14371": {
        "zh": "自动化立体仓库（AVS/RS）被广泛用于提效降本，但仿真研究往往缺解释。框架把离散事件仿真与统计模型检查（SMC，经 MultiVeStA）及过程挖掘（PM）结合：SMC 以用户指定置信度给出周期时间、吞吐与存储利用率等指标的统计可靠估计，并黑盒编排多次独立仿真实现自动验证；PM 摄入事件日志揭示驱动这些指标的行为模式与瓶颈，弥合可解释性缺口。在按近期工业指南配置的开源 AVS/RS 仿真器上评估多种控制策略，是首个 SMC+PM 联合评估 AVS/RS 的工作，工具链可复用，支持预测性 what-if 分析与事后诊断。",
        "en": "An integrated framework couples discrete-event simulation with Statistical Model Checking (MultiVeStA) and Process Mining to quantify and explain Automated Vehicle Storage and Retrieval System performance: SMC yields statistically reliable estimates at user-specified confidence, while PM uncovers behavioral patterns and bottlenecks from event logs. Evaluated on an open-source AVS/RS simulator, it is the first combined SMC+PM assessment of AVS/RS operations.",
    },
    "2611.13627": {
        "zh": "语言模型大幅降低了形式验证门槛，但 verifier-in-the-loop 只给粗粒度二元反馈；反例更有可操作性（把证明失败落到具体程序状态），推理期生成有用反例又需昂贵的迭代精化。TopoVerus 把反例制导诊断内化为模型能力，单次生成结构化源级反例、修复理由与修复证明：把「反例有用」定义为「以其为条件能产出安全且通过验证的证明」这一数据驱动诊断目标，用 Verus 反馈的强化学习加证明代码安全门优化；并引入基于不变式依赖（由归纳性测试导出）的拓扑图奖励课程，引导反例生成按拓扑序修复不变式。七个 Verus 基准 471 题上加权平均 Safe-Pass@1/@3 达 61.6%/72.2%，比最强基线 Claude Sonnet 4.5 高 5.7/6.3 分。",
        "en": "TopoVerus is an LM framework for Verus proof repair that internalizes counterexample-guided diagnosis as a model capability, generating a structured counterexample, repair rationale and repaired proof in one pass. It is trained with RL from Verus feedback plus a proof-code safety gate, and a curriculum with topological graph reward over invariant dependencies orders the repairs. Across seven Verus benchmarks (471 problems) it reaches 61.6%/72.2% weighted-average Safe-Pass@1/@3, beating Claude Sonnet 4.5 by 5.7/6.3 points.",
    },
    "2611.14106": {
        "zh": "证明助手给出强正确性保证但构造证明费时费力；已有 LLM 方法多困在固定的策略生成循环里，前提检索、证明状态管理与回溯都由外部系统控制。ProofCoder 从编码智能体视角做 Rocq 证明合成：模型在证明搜索全程持续推理，按证明助手反馈自行决定何时收集更多信息、查看证明状态、修订已生成片段或回溯到更早位置，可在策略级或整证明粒度迭代构造、修复与精化。在 AutoRocq 基准 280 个高难验证任务上，最佳配置把证明成功率从 47% 提到 60%（相对提升 27.7%），成本约为原系统一半；消融显示持续推理是关键设计：去掉后解题更少、成本更高、回溯多 4–6 倍。",
        "en": "ProofCoder is an agentic proof-synthesis system for Rocq that reasons continuously throughout proof search, using proof-assistant feedback to decide when to gather information, inspect proof states, revise fragments or backtrack. On 280 AutoRocq tasks it raises proof success from 47% to 60% at about half the cost; ablations identify continuous reasoning as the key design choice.",
    },
    "2611.13241": {
        "zh": "Claude Code 等编码智能体能解决真实仓库 issue，但迭代交互循环成本高；已有做法主要靠限制、压缩或选择性跳过修复中的信息与动作。FlowPlan 走互补路线：让智能体在抽象程序层面推理，以逐函数控制流/数据流图组织定位、规划与验证——先在抽象上定位候选故障位置，把修复意图表达为显式图增量，再改具体源码；改完后重建同一抽象，比较观测到的结构变化与计划是否一致，终止前再做完整修复验证。六个基准-模型组合中，FlowPlan 不显著改变解决率，但每个设置都降低 token 消耗（五个设置显著；Claude Haiku 4.5 在 SWE-bench 上只用基线 0.46–0.47 倍 token）。",
        "en": "FlowPlan structures coding-agent repair around per-function control-flow/data-flow graphs: it localizes faults on the abstraction, expresses repairs as explicit graph deltas before editing source, then reconstructs the abstraction to verify the observed structural change matches the plan. Across six benchmark-model settings it keeps resolution rates while cutting tokens in every setting (significantly in five; 0.46–0.47x with Claude Haiku 4.5 on SWE-bench).",
    },
    "2611.11848": {
        "zh": "LLM 提升 Verilog 生成，但仿真通常只给模块级 pass/fail，丢弃了部分正确 RTL 模块的证据，也判断不了哪条源语句应对输出行为负责。CSCA 是反事实偏好优化框架：先对采样候选模块做连续信号级行为验证，定位驱动输出的赋值片段，在固定其余模块与 testbench 的条件下做五种干预，把信号级误差变化与行为一致性合成连续的语句级信用，再映射为响应 token 权重做严格加权 DPO——从局部正确的语句学习，而不是对整体错误的响应均匀强化。基于 Icarus Verilog 与 CodeV 语料，在 VerilogEval 2.0 与 RTLLM v2.0（补全与规格到 RTL 两类任务）上，Qwen2.5-Coder-7B 骨干领跑 7B 级模型、可比更大的 GPT-4 级模型。",
        "en": "CSCA is a counterfactual preference-optimization framework for Verilog generation: it performs signal-level behavioral verification, locates output-driving assignment spans, applies interventions to derive continuous statement credit, and maps it to token weights for weighted DPO, learning from locally supported statements. With a Qwen2.5-Coder-7B backbone it leads 7B-scale models on VerilogEval 2.0 and RTLLM v2.0.",
    },
    "2611.11045": {
        "zh": "公共科学数据集很少拿来即用：宽矩阵、长表、电子表格与分队列文件混杂，键与编码各异，每次再分析都得先重新连接。管线建立在一条规则上：LLM 智能体提议、确定性代码验证、人类拍板——窄智能体只见紧凑可引用的文件证据（不见数据本身），返回类型化提议；含 39 类检查的验证器在模式结构与语义两轮循环中核验每个提议，人工审阅者批准模式与加载。代码编译 PostgreSQL DDL、重塑数据、隔离放不下的行、记录溯源，并把每个暂存行与数据库对账。四个公共生物医学数据集上，20 个首次提议有 9 个未过检查且全部被抓住（8 个由循环修复、1 个由审阅者一行修改）；4510 万个值零对账缺口加载；每数据集结构发现 4–7 次 LLM 调用、成本低于 0.5 美元。",
        "en": "An AI-assisted ingestion pipeline for heterogeneous scientific tables into relational databases, built on 'agents propose, code verifies, humans decide': narrow LLM agents see compact citable evidence and return typed proposals, a verifier with 39 check types tests each proposal in two loops, and a human approves schema and load. On four public biomedical datasets every failed proposal was caught and repaired; 45.1 million values loaded with zero reconciliation gap, under $0.50 per dataset.",
    },
    "2611.13442": {
        "zh": "并行 drafter 一次前向提出整块草稿 token，适合 LLM 服务；现有系统只控制验证多少 token，每个请求仍要起草整块。高负载下起草可占步时长 40%，其中多数因从未被验证而作废；并行 drafter 在单次前向前就得定长，自回归 drafter 的长度控制搬不过来，草稿与验证长度又在批内耦合，须逐请求联合选择且决策要便宜。本文提出 work-conserving speculation（WCS）设计，在 LLM 服务中逐请求联合分配草稿与验证预算；原型 ForeSpark 用上下文感知预草稿估计器预测各候选长度的接受率、轻量联合草稿-验证调度器经全局排序同时选两个长度、以及把验证预算花在最有希望请求上的事后预算分配。",
        "en": "ForeSpark realizes work-conserving speculation for LLM serving: it jointly allocates draft and verification budgets per request, using a context-aware pre-draft estimator predicting acceptance for candidate lengths, a lightweight joint scheduler selecting both lengths via a global sort, and post-draft budget distribution. At high serving load, drafting consumes up to 40% of step time, most of it discarded.",
    },
    "2611.14493": {
        "zh": "企业部署 LLM 分析智能体需要能在复杂多工具工作流中可靠发现失败的评估框架。三阶段对比研究比较三种评估范式（基于 trace 的 LLM 判分、纯文本 LLM 判分加红队、确定性启发式），在受控研究环境对两个分析智能体用冻结执行 trace 评估。Phase 1 量化评估框架稳定性：97% 配置达标且稳定性格式与智能体无关；Phase 2 在 72 个带真值用例上测已知风险检出，trace 框架取得最佳精确率-召回平衡（F1=0.90），纯文本评估召回持平但误报多 5 倍；Phase 3 评估未知风险发现，发现 24 个新失败且功能测试与安全红队零重叠。结论：评估质量取决于 harness 可见信息、功能与安全评估互补、LLM 评估能发现人类审阅者遗漏的细微错误；推荐「trace 评估管功能、红队管安全」的双框架策略。",
        "en": "A three-phase comparative study of three evaluation paradigms (trace-based LLM judging, text-only judging with red-teaming, deterministic heuristics) for enterprise analytics agents. Trace-based evaluation achieved the best precision-recall balance (F1=0.90) while text-only judging produced 5x more false alarms; unknown-risk discovery found 24 novel failures with zero overlap between functional testing and security red-teaming. The authors recommend trace-based evaluation for function and adversarial red-teaming for security.",
    },
    "2611.12620": {
        "zh": "边缘计算引入异构硬件、有限资源与多变的网络条件；Wasm 模块紧凑、可移植、启动快，但冷启动仍是挑战：节点没有所需制品时要先取再执行，传输开销直接抬高端到端延迟，请求者与被分配节点的地理距离又经网络路由开销独立贡献延迟——制品本地性与网络邻近不总指向同一放置决策，朴素调度两头都没顾上。本文在 Wasm 原生边缘编排器上扩展状态感知调度策略，联合优化两目标；在 Raspberry Pi 测试床加仿真区域网络延迟的评估中，结合缓存状态与网络邻近信号的混合调度器把平均端到端延迟比 round-robin 基线最多降 40.8%；制品本地性感知在制品大或被重复请求时最有效，网络感知在制品小、路由延迟占比大时占优。",
        "en": "The paper extends a Wasm-native edge orchestrator with state-aware scheduling that jointly optimizes artifact locality and network proximity for cold-start latency. On a Raspberry Pi testbed with emulated regional latency, a hybrid scheduler reduces mean end-to-end latency by up to 40.8% versus round-robin; locality-aware placement wins for large or repeatedly requested artifacts, network-aware placement for small ones.",
    },
    "2611.13705": {
        "zh": "特邀综述：AI 智能体日益能生成与优化硬件电路，验证 AI 生成设计的正确性愈发重要，而 AI 进展也降低了形式化方法的开发与应用门槛。文章从规格、证明构造、推理引擎三个层面梳理智能体如何推进硬件形式化；再讨论形式化如何支撑可靠的 AI 驱动硬件开发（RTL 生成、调试、保正确性优化）；结合代表性工作与作者团队贡献总结技术要点与实验洞见，展望「证明原生」的自主硬件设计——让形式推理成为自主设计流程的组成部分。",
        "en": "An invited overview of hardware formal methods in the AI era: how agentic AI advances formal methods at three levels (specification, proof construction, reasoning engines), and how formal methods support reliable AI-driven hardware development through RTL generation, debugging and correctness-preserving optimization, toward proof-native hardware development.",
    },
    "2611.13042": {
        "zh": "2026 年 10 月单个实验室放出 700 多篇 AI 生成的数学稿，其中仅一部分有机器检验证明；如此体量将主要由调用专用软件的 AI 智能体核查，但通过的检查只认证被检的那个产物——翻译成 Lean 的证明可能陈述的并非作者文本所言，翻译是否忠实一般不可判定。作者提出领域无关的人在回路核查框架：由有不同信任根据、经验证的可用工具检查结果；保真审计追问每次检查是否针对原文所陈的主张；人类在固定节点决策；对话式报告把工作归属到人与 AI。工具层给出两个自动实现（数学：Wolfram、MATLAB、Lean；统计：Python、R），数学实现跑在一个两主张示例上：一条歧义主张被拆成两种读法，一伪一真。",
        "en": "A domain-independent human-in-the-loop framework for checking AI-produced research results: validated agent-usable tools with different grounds of trust, a fidelity audit asking whether each check addressed the claim as stated, human decisions at fixed points, and a dialog report attributing work to human and AI. Implementations for mathematics (Wolfram, MATLAB, Lean) and statistics (Python, R) are described; on a two-claim example an ambiguous claim split into two readings, one refuted and one proved.",
    },
    "2611.11477": {
        "zh": "Swarm Learning 把模型聚合与验证分散到参与节点、去掉单一可信协调者，但也把更新验证交给私有数据可能有偏、无代表性甚至对抗的 peers，现有协议一般不证明数据质量，去中心化验证成了攻击面。框架把「可验证的数据质量」作为加入学习的条件：验证者先经零知识证明，在不泄露任何原始样本的前提下证明参考模型在其私有数据上正确运行才准入；证明的输出还产出无标签类画像，使网络能从个体偏斜的验证者拼出集体 IID 池（与均匀分布的总变差距离 0.025，oracle 为 0.021、随机选择 0.21）。准入验证者对客户端更新打分，经 Tendermint 式 BFT 共识就梯度掩码与按质量导出的聚合权重达成一致，取代按数据集大小加权；借鉴 Split Learning 切层的挑战式审计让 peers 复核掩码确在已证明的数据上计算，免去昂贵的端到端零知识证明。",
        "en": "A robust, privacy-preserving Swarm Learning framework where validator admission requires a zero-knowledge attestation that a reference model ran correctly on the validator's private data. Attested outputs yield a label-free class profile for assembling a collectively IID validator pool (total-variation 0.025 vs 0.021 oracle, 0.21 random). Admitted validators score updates and agree on gradient masks and quality-derived weights via Tendermint-style BFT consensus, with a challenge-based audit re-verifying masks without end-to-end ZK proofs.",
    },
    "2611.13150": {
        "zh": "多模态大模型多以答案对错评价，但正确不等于输出有正确的视觉证据支撑。VIGOR 基准把视觉理据表示为显式概念加像素级 grounding，覆盖低层视觉属性、中间结构、物体、部件与高层运动/关系多个抽象层级；规模化构建靠自动标注框架——有密集监督就复用，缺的经提议式标注加保守多模态验证生成。用 VIGOR 检验模型是否「看着它说的」：把模型对每个所陈概念导出的视觉证据与标注真值比对。结果显示当前 MLLM 视觉理据正确性有限，且各概念层级呈现不同的 grounding 失败。",
        "en": "VIGOR benchmarks visually grounded rationales in MLLMs, representing rationales as explicit concepts paired with pixel-level groundings across abstraction levels, built by reusing dense supervision and proposal-based annotation with conservative multimodal verification. Evaluation shows current MLLMs have limited visual rationale correctness with distinct grounding failures across levels.",
    },
    "2611.14272": {
        "zh": "疫情暴发在区域间往往不同步，协同预测受隐私法规与异构干预掣肘。概念验证：广东、澳门与葡萄牙三地的新冠预测联邦学习框架（LSTM，Flower 框架，超参一致），用 WHO 与中国 CDC 的每日病例数据，与本地及集中式训练基准对比 RMSE/MAE/sMAPE。数据集为 2021-11-24 至 2023-01-08 的 411 天 1233 个日观测。葡萄牙更早的 Omicron 波提供了传播动力学，改善了澳门与广东这些晚发地区的预测；FL 模型归一化 RMSE 0.028，比本地模型（0.240）改善 88.3%、与集中式相当，网络开销主要由模型大小与聚合频率决定。",
        "en": "A proof-of-concept federated learning framework for cross-regional COVID-19 forecasting under asynchronous outbreaks among Guangdong, Macau and Portugal. LSTM models trained via FL achieved normalized RMSE 0.028, an 88.3% improvement over local models and comparable to centralized training, as the earlier Omicron wave in Portugal improved forecasts in later-onset regions.",
    },
    "2611.12871": {
        "zh": "现有异常检测多经局部密度、隔离启发式或与拟合分布的距离定义异常，对邻域尺度、划分选择或分布假设敏感。本文从多样性视角重新表述：提出 Vendi Anomaly Score（VAS），用移除一个样本后数据集 Vendi 分数（多样性）的变化量化其异常程度，同时捕捉局部冗余与全局数据结构，无需密度估计或划分启发式，无需调参（自动适配数据谱结构），非参数且随数据规模线性扩展。在来自 10 个源数据集、4 种嵌入架构的 148 个基准嵌入数据集上取得 SOTA，并在 ImageNet 大规模实验中随污染率与规模增大保持稳健。",
        "en": "The Vendi Anomaly Score (VAS) detects anomalies by how much removing a sample changes the dataset's diversity (Vendi score), capturing local redundancy and global structure without density estimation or partitioning heuristics, with no hyperparameter tuning and linear scaling. It achieves state-of-the-art performance on 148 benchmark embedding datasets and stays robust on ImageNet-scale experiments.",
    },
    "2611.12300": {
        "zh": "行动理论通常固定词汇与因果律，而智能体 harness 会在执行中更换工具、提供商与策略。本文提出可重构行动理论（RAT）：动作可以改变行动理论本身；理论模块含词汇、因果律与初始化器，RAT 配置记录活跃模块与世界状态，模块加载/卸载由普通因果律治理的动作表示；活跃模块集固定时保持该语言片段的标准因果行动语义。给出至多一个后继配置、加模块保持既有行为、两序加载结果相等的充分条件；确立推理任务的计算复杂度，并把有限 RAT 系统翻译为非单调因果理论与 ASP（保持有界执行）。实验对比有限 RAT 模型与 DeepSeek Harness、Pi、OpenHands 官方实现的执行；RAT 为检查组件变化如何影响 harness 可用动作、行为与可达目标提供形式基础。",
        "en": "Reconfigurable Action Theories (RAT) let actions change the action theory itself, providing a formal foundation for dynamically composable agent harnesses: theory modules with vocabulary, causal laws and initializers are loaded/unloaded by actions governed by ordinary causal laws. The paper gives conditions for determinism and behavior preservation, establishes reasoning complexity, and translates finite RAT systems into nonmonotonic causal theories and ASP, comparing against DeepSeek Harness, Pi and OpenHands.",
    },
    "2611.13613": {
        "zh": "带证明助手工具的通用编码智能体在独立竞赛题上表现出色，但低资源数学库内的累积式教材形式化仍有三道坎：教材概念与库声明的对齐、长程搜索与实时证明状态的同步、局部已验证证明可靠并入增长的代码库。Megrez 是基于 Morse–Kelley 集合论的 Rocq 库知识制导形式化智能体，靠三个机制协调通用编码智能体：(1) 可从源码重建的知识图，合并形式声明、编译器引用与人工元数据，支持中文别名、概念簇、证明依赖与多路全文检索；(2) 反馈驱动的 1–5 步策略短爆发证明循环，配目标局部分支台账与指数间隔的结构化反思；(3) 三重检查验收管线（陈述忠实性、公理审计、完整构建）加多语料 Provider 栈与候选绑定可恢复批状态机。在点集拓扑语料上的部署与评估显示跨章形式化与可扩展前提检索有效。",
        "en": "Megrez is a knowledge-guided formalization agent for Rocq libraries on Morse–Kelley set theory, coordinating a general coding agent with a source-rebuildable knowledge graph (retrieval via aliases, concept clusters, proof dependencies), a feedback-driven short-burst tactic proving loop with branch ledgers and structured reflection, and a three-check acceptance pipeline (statement fidelity, axiom auditing, full builds). Evaluated on a point-set topology corpus.",
    },
    "2611.13057": {
        "zh": "室内定位常组合 WiFi RSSI 指纹与惯性测量，但两路流异步采样、速率不同，观测难以在时间上对齐且可能缺失或过时；既有方法多把数据重采样到共享时钟并为每个模态设独立分支。本文提出连续时间 Transformer：观测表示为无序的时间戳 token 集合，每个 token 编码测量值、模态与距今时长，单一注意力块跨模态与时间联合融合，避免重采样与模态专属分支且对 token 顺序不变；训练时随机屏蔽整个模态与单个观测，使模型能在输入缺失或过时下工作。在模拟与真实数据集（含未见天的跨会话数据）上验证，跨会话漂移下超过开源 WiFi 指纹基线，与学习式融合及航位推算基线相当，且随观测缺失或过时优雅退化。",
        "en": "A continuous-time transformer represents WiFi and IMU observations as an unordered set of timestamped tokens (measurement, modality, elapsed time) fused by a single attention block, avoiding resampling and modality-specific branches; random masking of modalities and observations during training enables robustness to missing or stale inputs, with improved cross-session performance and graceful degradation.",
    },
    "2611.13137": {
        "zh": "基于 LMO 与动量正交化的 Muon 优化器在大规模分布式学习中经验表现强，但对对抗行为与数据异构的稳健性不清楚。本文在统一的一阶信赖域框架内研究这些方法，分析带稳健聚合的 Muon 型更新以实现拜占庭稳健的分布式与联邦学习：分析不依赖 i.i.d. 假设，引入与信赖域几何一致的非欧异构性度量；对一般非凸与星凸目标建立收敛保证，给出与已知不可能结果一致的加性异构误差底，并在明确聚合假设下覆盖不精确正交化。在 CIFAR-10 上 ResNet-18 与 ViT-Tiny 的模拟联邦训练、附加图像基准与 TinyStories 上 38M 参数字节级语言模型中，受测 Muon 配置的受攻击准确率（更低困惑度）高于受测 SGD 与归一化 SGD 配置。",
        "en": "The paper analyzes Muon-based updates with robust aggregation in a unified first-order trust-region framework for Byzantine-robust distributed and federated learning, without i.i.d. assumptions and with a non-Euclidean heterogeneity notion, establishing convergence guarantees for non-convex and star-convex objectives and covering inexact orthogonalization. Empirically the Muon configuration attains higher attacked accuracy than SGD and normalized-SGD on CIFAR-10 federated training, image benchmarks and a 38M-parameter language model.",
    },
}


def main():
    path = os.path.join(OUT, "summaries.json")
    with open(path, encoding="utf-8") as f:
        summ = json.load(f)
    added, skipped = [], []
    for sid, pair in SUMM.items():
        old = summ.get(sid)
        # dict 且 en/zh 均非空 → 视为完整，不覆盖；旧单语字符串可升级
        if isinstance(old, dict) and old.get("en") and old.get("zh"):
            skipped.append(sid)
            continue
        summ[sid] = {"en": pair["en"], "zh": pair["zh"]}
        added.append(sid)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summ, f, ensure_ascii=False, indent=1)
    print(f"[ok] summaries.json {len(summ) - len(added)}/{len(summ)} -> 补 {len(added)} 篇：{added}")
    if skipped:
        print(f"[skip] 已存在不覆盖 {len(skipped)} 篇：{skipped}")


if __name__ == "__main__":
    main()
