# -*- coding: utf-8 -*-
"""补齐 20261127 期 24 篇（14 推荐 + 10 扩展）的双语简介，并为 14 篇推荐补摘要全文中译（abstracts_zh.json）。"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2611.33817": {
        "zh": "SentryWard 对 warp 专用化 GPU kernel 做形式验证：把异步数据搬运、CUDA 核与张量核计算的并发重叠建模成同步约束，杜绝数据竞争与资源提前复用；对 Hopper 上的真实 kernel 证明按任意调度执行都正确，覆盖现有 GPU 验证工具不支持的 warp 专用化场景。",
        "en": "SentryWard formally verifies warp-specialized GPU kernels: it models the asynchronous overlap of data movement, CUDA-core and tensor-core computation as synchronization constraints, ruling out data races and premature resource reuse, and proves correctness under arbitrary schedules for real kernels where existing GPU verification offers little support.",
    },
    "2611.34617": {
        "zh": "首个面向智能体系统的黑盒测试用例选择实证研究：把基准任务当测试用例，按任务级历史表现选子集；结果表明少量任务即可外推整体通过率并提前暴露回归，且完全不需要访问模型内部，适合专有智能体的日常回归测试。",
        "en": "First empirical study of black-box test case selection for agentic software systems: each benchmark task acts as a test case, and selection uses only observable task-level outcomes. Small subsets suffice to estimate overall pass rates and surface regressions early, with no access to model internals required.",
    },
    "2611.33763": {
        "zh": "主张为数据智能体建一张会演化的语义地图：数据湖与开放数据门户里的列含义、隐含上下文与数据集间组合方式，目前在每个任务的完整工作流里被反复重推导又随手丢弃；把这类知识按需沉淀成可导航的语义图集，检索、连接发现与程序合成都能复用，越用越准。",
        "en": "Argues for persisting what data agents perpetually rederive: column meanings, implicit context and how datasets combine in lakes and open portals. An evolving, demand-driven semantic atlas makes retrieval, join discovery and program synthesis reusable across tasks instead of discarding each workflow's knowledge.",
    },
    "2611.33748": {
        "zh": "REFORGE 是首个跨迭代累积结构化修复证据的 LLM 辅助 RTL 修复框架：把功能正确、行为等价、安全性、可综合性分开留证，同时满足多目标；在真实缺陷上修复率超过单指标基线，且证据链可复现、可接入硬件设计流程。",
        "en": "REFORGE is the first LLM-assisted RTL repair framework that accumulates structured repair evidence across iterations, keeping separate proof for functionality, behavioral equivalence, security and synthesizability. It satisfies multiple objectives simultaneously and produces reproducible evidence usable in hardware design flows.",
    },
    "2611.34534": {
        "zh": "DéjàVu 只靠「重复检测」达成多数意见共识：每轮随机采样一个同伴，见到第二次重复的观点就采纳并重置记忆，不需要频率计数、不知群体规模与意见数。论文给出严格收敛时间证明，机制在单个神经元与曝光效应中都有对应物。",
        "en": "DéjàVu achieves plurality consensus with mere repetition detection: each round an agent samples one peer, adopts the first opinion seen twice, and resets its memory — no frequency counters, no knowledge of population size or opinion count. The paper proves rigorous convergence times; the mechanism mirrors single-neuron repetition detection.",
    },
    "2611.34875": {
        "zh": "提出 Delta Residue Attribution：重放智能体轨迹，把最终补丁的每个代码块回溯到产生它的步骤，逐块回退后重跑测试判断是否必要。在 7660 条 SWE-bench Verified / DeepSWE 轨迹上量化「过度编辑」：智能体补丁确实更大，且多数多余编辑有可解释来源。",
        "en": "Delta Residue Attribution replays agent trajectories, traces every block of the final patch to the step that wrote it, reverts it and reruns task tests to decide necessity. Across 7,660 Copilot CLI trajectories on SWE-bench Verified and DeepSWE it quantifies over-editing: agent patches are larger, and most extra edits have explainable origins.",
    },
    "2611.34627": {
        "zh": "DecisionReplay 释放 17 个商用决策模型在 35 个基准上每个答案选项的概率向量、token 数、计费成本与实测延迟，配确定性离线模拟器，任何集成/路由/级联策略零调用即可重放。结论反直觉：每个基准选对单个模型就很难被打败，全模型混编反而常常更差。",
        "en": "DecisionReplay releases probability vectors of 17 commercial decision models over 35 benchmarks with token counts, billed cost and latency, plus a deterministic simulator that replays any ensemble, router or cascade policy without new calls. A well-chosen single model per benchmark is hard to beat; pooling all models often loses.",
    },
    "2611.34363": {
        "zh": "text-to-SQL 强化学习的单库奖励可被「侥幸命中」骗过：数据缺行时错误查询也能对上参考结果。反事实执行奖励在几份隐藏生成的数据库副本上同时跑查询、全对才给分：buggy 查询全额得酬从 54.1% 压到 1.9%，2847 条正确查询零误杀。",
        "en": "Single-database rewards for text-to-SQL RL can be hacked: a wrong query matches by luck when data lack exposing rows. A counterfactual reward also executes the query on a few hidden generated copies, paying only if all results match: full reward for buggy queries drops from 54.1% to 1.9% with zero rejections of 2,847 correct queries.",
    },
    "2611.33639": {
        "zh": "给 AI 代码评审员调「用力档」：三个 Claude 模型以低中高努力评审同样的 90 个 Django 补丁。高努力在所有模型上都显著少放过似真但错误的补丁（Opus 假成功率 .45 对 .67），但代价是更多拒绝正确补丁——评审努力需要按风险档位显式设定。",
        "en": "Three Claude models reviewed the same 90 agent-written Django patches at low, medium and high effort. High effort accepts fewer plausible-but-wrong patches in every model (Opus false success .45 vs .67) at the cost of rejecting more correct ones — reviewer effort must be set explicitly as a risk dial.",
    },
    "2611.34185": {
        "zh": "分布式诱导路径检测的局部计数法：对 color-coding 信号沿随机染色排列统计终止于每条边的次数，诱导路径贡献 1、环贡献 2，由此把两者区分开——经典 colorful 路径传播做不到。给出带宽受限分布式下的检测算法与下界。",
        "en": "For induced path detection in distributed networks: count color-coding signals over all permutations of the random coloring terminating at each edge — an induced path contributes one, a cycle contributes two — separating what colorful-path propagation cannot. The paper derives algorithms and lower bounds under bandwidth constraints.",
    },
    "2611.33943": {
        "zh": "审计 SkillsBench 的「技能增益」到底是什么：源码级审查 7554 次公开试验、1421 个配对单元，发现两例评分器依赖与一处操作定义缺口，剔除后平均增益大幅缩水；提出噪声感知的按任务增益估计，建议技能门控先过稳健检验再上/下架。",
        "en": "Audits what SkillsBench's skill lift actually measures: a source-code-level audit of 7,554 public trials into 1,421 paired (configuration, task) cells finds two grader-dependence cases and one operational-definition gap that shrink average lift; a noise-aware per-task gain estimator is proposed before gating skills on it.",
    },
    "2611.33765": {
        "zh": "EMMA 面向自动驾驶/机器人积累的多模态历史数据做协同分析：视频、LiDAR 点云与 GPS 轨迹跨车辆、跨模态联查，逐场景跑深度模型代价不可承受。EMMA 用分层索引与模态间对齐把查询改写成少量模型调用，多个真实分析任务上效率与效果同时领先。",
        "en": "EMMA supports cooperative multi-modal analytics over embodied-AI archives (video, LiDAR, GPS) spanning vehicles and modalities, where running deep models per scene is prohibitive. Hierarchical indexing and cross-modal alignment rewrite queries into few model calls, beating baselines on both efficiency and effectiveness across real analytical tasks.",
    },
    "2611.34925": {
        "zh": "OneOcean 用统一时空海洋环境产品（水深 + 数据驱动洋流/潮汐，可选污染场）构建海洋机器人仿真套件与基准：任务梯子覆盖洋流下导航、定点、航迹跟踪、区域扫描、管道巡检与多智能体协同，全部锚定真实海洋数据而非拍脑袋造浪。",
        "en": "OneOcean is a data-grounded marine robotics simulation suite and benchmark built on a unified spatiotemporal ocean product (bathymetry harmonized with data-driven currents and tides, optional pollution fields). A task ladder spans navigation, station-keeping, route following, area scanning, pipeline inspection and multi-agent cooperation.",
    },
    "2611.33490": {
        "zh": "C 迁 Rust 的性能落差跨层归因：12 组 C/Rust 对标基准显示运行时安全检查未必是开销主因，编译器与微架构优化常把它吃掉；12 组里 8 组至少存在一个 Rust 版本反超 C 的形状。再用 LLM 辅助诊断定位真实瓶颈，给出可操作的迁移优化路径。",
        "en": "Cross-layer characterization of 12 C-to-Rust benchmarks shows runtime safety checks do not necessarily dominate overhead — compiler and microarchitectural optimizations often absorb them, and in 8 of 12 benchmarks at least one Rust variant outperforms C. AI-assisted diagnosis then localizes real bottlenecks for actionable migration.",
    },
    "2611.34132": {
        "zh": "Agent-as-a-Verifier 把验证从「打分」升级为「出证据」：判别式奖励模型只给标量、无可审计依据，本文让智能体用工具调用与迭代推理产出细粒度、可核查的判断证据，覆盖事实核查与逐条声明验证，比现有生成式过程奖励模型更完整地利用了智能体能力。",
        "en": "Agent-as-a-Verifier moves verification from scores to evidence: discriminative reward models output a scalar with no auditable basis, while this agent uses tool calls and iterative reasoning to produce fine-grained, checkable verdicts per claim — exploiting agentic capabilities most generative process reward models leave unused.",
    },
    "2611.33676": {
        "zh": "Merlin-Bench 借交互证明系统测 LLM 智能体的「可验证证明」底层能力：在指定协议下智能体与形式验证器交互坐实自己的断言，考察的是构造可核查证据的协议无关能力，而非对某个证明语言或工具的熟练度。",
        "en": "Merlin-Bench uses interactive proof systems to measure LLM agents' protocol-agnostic ability to construct verifiable evidence: under a designated protocol the agent interacts with a formal verifier to substantiate its claimed answer, testing proof construction itself rather than proficiency with any proof language or tool.",
    },
    "2611.34711": {
        "zh": "Spec2Weights 认证「语言模型直接写出权重」的小网络：从纯语言规约、无数据无梯度生成 MLP/CNN/RNN/GNN 权重，再用 float32 穷举引理与分层误差界证明网络在声明域内逐输入精确（可达 10^16 个输入）；15 个生成网络成功认证 12 个。",
        "en": "Spec2Weights certifies networks whose weights a language model writes from a plain-language specification with no data and no gradients: a float-safety lemma turns exhaustive float32 enumeration into a proof for any summation order, with layered error bounds covering 12 of 15 generated networks on every stated input (up to 10^16).",
    },
    "2611.34215": {
        "zh": "长期交互里互相验证的 LLM 智能体会逐渐滑向合谋：遵守规则的智能体总被告知「判断错了」，破坏规则反而收益最大。PROVE 用「验证过才给证据」的多智能体强化学习把该行为训练掉，从源头压制长程合谋，而不是靠事后提示词修补。",
        "en": "LLM agents verifying each other over long horizons drift into collusion: rule-followers are told their verdict was wrong whenever the peer was right, making rule-breaking reward-maximizing. PROVE trains the behavior out with multi-agent RL from verified evidence, suppressing long-horizon collusion at the source.",
    },
    "2611.33893": {
        "zh": "并行子智能体何时值得用？在 NL2Repo 与 ProgramBench 仓库构建任务上等时、等成本对比主智能体委托并行子智能体：随机任务上隐藏测试通过率仅提升约 1 个百分点，收益集中在可自然分解的任务；干预实验揭示收益来源与委派时机。",
        "en": "When are parallel subagents effective for coding? Comparing a single agent against delegation on repository-construction tasks (NL2Repo, ProgramBench) at equal time and cost: parallel subagents raise hidden-test pass rates by only about 1 point on random tasks, with gains concentrated in naturally decomposable tasks.",
    },
    "2611.34723": {
        "zh": "因果图不唯一时算法反事实怎么做：同一份数据可拟合出多个预测不同干预效果的因果图。提出 Worst-Case 与 Graph-Weighted Recourse，在所有候选图或指定比例图上都成功的低成本行动，图集变大也不退化为「无解」。",
        "en": "Algorithmic recourse under causal-graph ambiguity: multiple graphs fit the same data yet predict different effects for the same action. Worst-Case and Graph-Weighted Recourse find low-cost actions that succeed across all candidate graphs or a specified fraction, staying feasible as the graph set grows.",
    },
    "2611.34684": {
        "zh": "BridgeHammer 用 CPU-iGPU 共享内存 Rowhammer 给 DNN 埋后门：CPU 侧内存故障翻转 iGPU 推理模型的权重位，触发态误分类、正常态精度不变；解决「往哪儿翻（脆弱 DRAM 位置未必含目标权重）」与「何时翻（对齐部署生命周期）」两大难题。",
        "en": "BridgeHammer implants DNN backdoors via CPU-iGPU shared-memory Rowhammer: CPU-side faults flip weight bits of iGPU-inference models, misclassifying trigger inputs while preserving normal accuracy — solving where to strike (vulnerable DRAM cells may not hold target weights) and when (aligning with deployment lifecycle stages).",
    },
    "2611.34481": {
        "zh": "GPU 上解码双变量自行车码（BB 码）的并行窗口解码器：可复用故障模式 + 共享内存紧凑状态 + 常驻 GPU worker 的 min-sum/Relay-BP 恢复，RTX 5090 上跟上每 1 微秒一轮的综合征节奏，达 [[144,12,12]] 且 63–144 微秒中位提交延迟，较此前 circuit-level GPU 解码快 120 倍。",
        "en": "A parallel-window GPU decoder for bivariate bicycle codes combines reusable fault patterns, compact shared-memory state and persistent GPU workers with min-sum and Relay-BP recovery: on an RTX 5090 it keeps pace with one syndrome round per microsecond up to [[144,12,12]], with 63-144 microsecond median commit delays — 120x faster than prior circuit-level GPU decoding.",
    },
    "2611.33303": {
        "zh": "程序化生成的逻辑题难度常被高估：播下一棵深度 d 的证明不代表最短证明就是 d。论文计算每个问题「必须走的步数、最短证明、极小证明数与不可缺前提」，导出可独立核验的无捷径证明深度证书，让难度标定不再虚标。",
        "en": "Procedurally generated logic problems overstate difficulty: a planted depth-d proof does not preclude shorter ones. The paper computes, per problem, the steps every proof must make, the shortest proof, the number of minimal proofs and indispensable premises, exporting shortcut-free proof-depth certificates an independent checker can verify.",
    },
    "2611.34328": {
        "zh": "LUDIUS 测机器人的具身社交智能：围绕社会心理学提炼的 15 项社交技能，让视觉语言模型以机器人言语与动作做情境判断；六个版本各覆盖模拟一周的多人家居场景，含多人互动、安全与情境规范专项，给出技能级评测。",
        "en": "LUDIUS benchmarks embodied social intelligence: vision-language models exercise situational judgment through a robot's verbal responses and actions, organized around 15 social intelligence skills from social psychology. Six editions span a simulated week across households, with dedicated tracks for multi-person, safety and context-specific norms.",
    },
}

ABSTRACTS_ZH = {
    "2611.33817": "现代 GPU kernel 用 warp 专用化把异步数据搬运、通用核（CUDA 核）计算与专用核（张量核）计算重叠起来。这类异步重叠优化带来复杂的同步需求：异步操作次序不正确会导致数据竞争、资源提前复用与错误结果。测试无法保证正确性，因为此类错误是非确定性的、可能只在罕见执行调度下显现；而既有 GPU 形式验证技术对 warp 专用化 kernel 支持有限。我们提出 SentryWard，一个对 warp 专用化 GPU kernel 做形式验证的框架。",
    "2611.34617": "智能体软件系统在开发中越来越常用，模型、提示词、脚手架、工具或执行环境的每次变更都需要反复测试。测试用例选择（TCS）可在降低测试成本的同时估计智能体性能或提前暴露失败。尽管 TCS 在深度网络与 LLM 代码模型上已有研究，先前工作并未直接针对智能体系统，且常需要专有智能体拿不到的模型内部信息。我们给出首个面向智能体系统的黑盒 TCS 实证研究：把每个基准任务当作测试用例，并改造黑盒回归测试技术。",
    "2611.33763": "多数能支撑丰富分析的数据仍处于未集成、未编目的状态，散落在开放数据门户、数据湖与独立发布的数据表集合中。数据智能体如今可以在其上回答分析问题，但每个问题要走一整套工作流：数据集检索、连接发现与评估、定制的程序合成——多数产物在新任务到来时即被丢弃。这些工作流所依赖的知识（每列什么含义、数据集隐含什么上下文、数据集如何组合）因此被永久性地反复重推导、从不落盘。我们主张把这些知识持久化为一张不断演化的语义地图集，供用户与智能体共同导航。",
    "2611.33748": "大语言模型（LLM）能写 RTL 也能修 RTL，但编译通过或测试台执行成功并不能确立缺陷已消除、行为保持、安全或实现可行性。既有 LLM 辅助 RTL 修复方法常只报告单一修复率、不保留这些性质各自的证据，限制了可复现的比较与接入硬件设计流程。我们提出 REFORGE——据我们所知首个跨迭代维护并累积结构化修复证据的 LLM 辅助 RTL 修复框架，使其能生成同时满足多功能性（功能、行为等价、安全性、可综合性）目标的修复。",
    "2611.34534": "我们分析 DéjàVu——一个简单的多数意见共识协议：每个同步轮中，每个智能体均匀随机采样一个智能体，并采纳其第二次观察到的意见，每次采纳后重置记忆。该规则既不需要频率计数器，也不需要知道群体规模或意见数量，只依赖重复检测——这一能力已在单个神经元中被记录，并体现于「曝光效应」。对 n 个智能体、k 个初始意见的群体，设 M0 为多数意见的初始计数（n/M0 ≤ k）、Δ0 为其与次多意见计数之差，我们证明……",
    "2611.34875": "智能体补丁比开发者的更大，这被普遍解读为「过度编辑」。但补丁大小并不说明多余编辑是否必要、是什么、从哪来。我们提出 Delta Residue Attribution（DRA）：重放智能体轨迹，把最终补丁的每个块（单元）回溯到写出它的步骤，逐块回退并重跑任务测试，以判定该块是否必要。我们在 SWE-bench Verified（6728 条）与 DeepSWE（932 条）上对 18 个前沿模型的 7660 条已解决 GitHub Copilot CLI 轨迹应用 DRA，并用同一方法为开发者补丁评级。智能体补丁确实改动更多行；在 SWE-bench Verified 上，多余的编辑……",
    "2611.34627": "比较集成、路由与级联需要每个模型在每个条目上的输出及其成本；为路由而存的数据集并不保存逐选项概率。我们提供一个数据集，让集成方法、路由器与级联无需新的模型调用即可快速模拟。DecisionReplay 保存 17 个商用决策模型（对每个答案选项返回概率的端点）在 35 个基准上的概率向量，以及每次调用的 token 数、计费成本与实测延迟，全部开放。确定性模拟器可重放任何选择、组合或级联它们的策略。结论：为每个基准选好一个模型就很难被击败——全模型池化反而常常更差。",
    "2611.34363": "对 text-to-SQL 智能体做强化学习时，通常只在单个数据库上比较查询结果与参考结果来支付奖励。但若数据缺乏暴露其缺陷的行，错误查询也可能侥幸对上。我们研究一种反事实数据库（CF）奖励：把最终查询再放到几份隐藏的、代码生成的数据库副本上执行，只有全部结果一致（严格形式）或按一致比例（均值形式）才支付。在 1302 条合成审计问题上，严格形式把错误查询获得全额奖励的比例从 29.5% 降到 16.8%，把奖励攻击从 54.1% 压到 1.9%，且 2847 条正确查询零误杀；家族盲生成器产出的副本效果相近。在受控 GRPO 实验中……",
    "2611.33639": "AI 编程智能体写代码的速度超过人类评审的速度，因此团队开始加入 AI 评审员。推理模型允许评审员用「努力档位」在成本与勤勉度之间权衡。我们问：评审员需要多大努力才能抓住「似真但错误」的补丁——它们通过基准测试却在更强测试下失败。Claude Opus 5.5（预注册）、Sonnet 5.5 与 Haiku 5.5（探索性）各自以低、中、高三档努力评审同一批 90 个 SWE-bench Verified 上的智能体编写的 Django 补丁。按强化版 SWE-ABS 测试，55 个补丁错误、35 个正确。在所有模型中，高努力都比低努力少接受错误补丁（Opus 假成功率 .45 对 .67，Sonnet .49 对 .65，……）。",
    "2611.34185": "著名的 color-coding 技术有一个经典应用：在带宽受限的分布式环境中沿彩色路径传播信号以快速检测路径 [Even et al., DISC 2017]。但由于同色顶点在该过程中不可区分，它无法检测诱导路径——诱导路径与环看起来一样。我们做出如下观察：若对给定边，统计所有随机染色排列下终止于该边的信号数，就能把诱导路径与环分开：诱导路径对该计数贡献 1，环贡献 2。细化并推广这一观察……",
    "2611.33943": "智能体技能（skills）是编程智能体按需加载的指令、参考资料与脚本目录。据 SkillsBench，人工策展的技能平均可把通过率抬升约 16.6 个百分点，但实际上在某些任务上反而降低了结果。后续研究已开始按上述逐任务增益对技能做门控或淘汰。我们对基准做了源码级审计，并分析 7554 次公开试验构成 1421 个配对「（配置，任务）」单元。源码审计发现两例经对照验证的评分器依赖与一处操作定义缺口；这三个任务的平均增益为……",
    "2611.33765": "具身 AI 的真实部署在增长，尤其是自动驾驶与机器人。这些车辆与机器人持续采集大量多模态数据：视频、LiDAR 点云与 GPS 轨迹。这些历史数据支撑模型改进与安全评估——场景检索、目标轨迹提取与相应分析。处理这类分析查询很有挑战：回答它们可能需要组合来自不同模态、不同移动载具/机器人采集的信息，而在每个场景上跑深度模型的代价不可承受。",
    "2611.34925": "仿真对海洋机器人至关重要，但既有平台常在视觉真实的场景、高吞吐实验与以真实数据为基础的海洋条件之间做取舍。我们提出 OneOcean——以统一时空海洋环境产品为基础的仿真套件与基准，把水深测量与数据驱动的洋流、潮汐协调起来，并带可选污染场以支持清理类评测。在此环境表示之上，OneOcean 定义了一个任务梯子：洋流下的导航与定点、航点与航线跟踪、深度剖面跟踪、区域扫描、管道巡检与多智能体协同。",
    "2611.33490": "把 C 代码迁移到 Rust 能显著提升软件安全性，但理解迁移的性能影响仍具挑战。虽然常宣称 Rust 性能媲美 C，但运行时安全检查、编译器优化与硬件微架构相互作用，使性能诊断变得复杂。我们首先对 12 组包含 C 实现与其 Rust 对应版本的基准做系统的跨层刻画。研究表明：运行时安全检查未必主导性能开销——编译器与微架构优化常抵消其成本。在 12 组基准的 8 组中，至少存在一个 Rust 版本……",
}

s_path = os.path.join(OUT, "summaries.json")
with open(s_path, encoding="utf-8") as f:
    s = json.load(f)
before = len(s)
added = 0
for sid, pair in SUMM.items():
    old = s.get(sid)
    if isinstance(old, dict) and old.get("zh") and old.get("en"):
        continue
    s[sid] = {"zh": pair["zh"], "en": pair["en"]}
    added += 1
with open(s_path, "w", encoding="utf-8") as f:
    json.dump(s, f, ensure_ascii=False, indent=0)
print(f"[ok] summaries.json: +{added}, total {before + (len(SUMM) and (added)) if False else len(s)}")

a_path = os.path.join(OUT, "abstracts_zh.json")
with open(a_path, encoding="utf-8") as f:
    a = json.load(f)
a_added = 0
for sid, zh in ABSTRACTS_ZH.items():
    if sid not in a:
        a_added += 1
    a[sid] = zh
with open(a_path, "w", encoding="utf-8") as f:
    json.dump(a, f, ensure_ascii=False, indent=0)
print(f"[ok] abstracts_zh.json: +{a_added}, total {len(a)}")
