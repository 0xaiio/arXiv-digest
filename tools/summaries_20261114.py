# -*- coding: utf-8 -*-
"""2026-11-14 批次：本期 24 篇待补论文的双语简介（summaries.json）。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- key 一律 arXiv 短号。
- 本轮只补双语简介（摘要全文中译 abstracts_zh 未做）。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2611.14795": {
        "zh": "分布式系统越来越多地依赖随机化，但这类系统的验证技术与构建它们所用的编程抽象彼此脱节。本文提出首个通用多参与方会话类型（MPST）的概率扩展：自底向上为会话定型、不需要全局规格，仅凭会话类型即可导出多参与方会话的定量性质。类型系统把概率选择与抽象数据相关控制流的非确定选择结合，并允许「分离选择」——选择/分支的每个分支可涉及不同参与方，这是此前概率 MPST 系统未覆盖的组合。为此作者发展了新的概率子类型关系与合并算子，证明类型可靠性与会话保真性；定型上下文的语义把非确定消解、概率选择与同步分层，使每个上下文诱导一个有限马尔可夫决策过程，从而导出在任意公平对抗调度下都成立的「无死锁」与「活」概率下界——这是概率会话演算的首个行为性质保证（哪怕是部分保证）。",
        "en": "The paper proposes the first probabilistic extension of general multiparty session types, typing sessions bottom-up with no global specification and deriving quantitative properties from the session types alone. It combines probabilistic with nondeterministic choice and supports separated choices across participants, develops a probabilistic subtyping relation and merge operator with type soundness and session fidelity, and shows that each typing context induces a finite MDP, yielding sound lower bounds on deadlock-freedom and liveness under every fair adversarial scheduler.",
    },
    "2611.15207": {
        "zh": "LLM 智能体正让形式验证规模化变得可行，但规模化验证只有在具备刻画功能的深层形式规格时才有意义；近期工作（如 Anthropic 与 Theorem 的 OSS-Verify）改用模糊测试 harness 充当规格、让智能体证明 harness 永不崩溃，而 fuzz harness 只走单一调用序列与单一调用上下文，所证只覆盖一个使用场景而非整个库。作者主张智能体验证的瓶颈已从「怎么证」转向「证什么」，因此先要能证的深层环境规格，故称 Pre-QED。方案是「验证 harness」：可执行 harness 建模一个 API 的全部合法用法，于是关于 harness 的证明即关于所有行为良好的客户端的证明。构造方式为智能体工作流：从代码/文档抽取 API 使用契约，再用线性时序逻辑（LTL）排除非法调用顺序；文中还识别了证明这类 harness 的挑战。",
        "en": "Pre-QED argues that the bottleneck of agentic verification has shifted from how to prove to what to prove: shallow fuzz harnesses used as specifications only cover one usage scenario. It proposes verification harnesses—executable harnesses modelling all legal usages of an API, so a proof about the harness is a proof about every well-behaved client—and constructs them with an agentic workflow that extracts the usage contract from code or documentation and uses LTL to rule out illegal call orders.",
    },
    "2611.15596": {
        "zh": "符号执行（如 Python 的 CrossHair）找 bug 能力很强，但采用受两道门槛阻碍：人工给代码加断言，以及为 Python 之外的外部环境（如外部数据库）建模。为此作者设计了一个智能体 harness，把 CrossHair 与 AI 编码智能体编排起来：无需人工干预即可给仓库插桩断言、为数据库合成约束感知的符号环境、运行符号执行，并为报出的每个 bug 构造具体测试作为证据。在 11 个流行开源 Python Web 应用（Zulip、NetBox、Apache Superset 等）、共 1,156,044 行代码上评估：有合成环境时 CrossHair 能执行 5,406 个带契约函数中的 81%，无环境时仅 4.5%；流水线共找到 1,050 个 bug，每个都由针对未修改应用的测试复现，其中 221 个由 CrossHair 发现，312 个被「同一 LLM 仅阅读代码」的基线漏掉。两者发现的 bug 类型不同：CrossHair 多为校验允许的输入域角例（空串、缺字段、异常字符）导致的崩溃，代码审阅类多为输出错误。",
        "en": "An agentic harness orchestrates the CrossHair symbolic execution tool with an AI coding agent to instrument a repository with assertions, synthesize a constraint-aware symbolic environment for external databases, run symbolic execution, and build a concrete test per reported bug. On 1,156,044 lines across 11 Python web applications it executes 81% of 5,406 contracted functions (vs 4.5% without the environment), finds 1,050 test-reproduced bugs, and catches 312 that an LLM code-inspection baseline misses.",
    },
    "2611.15847": {
        "zh": "Tendermint 是容拜占庭故障的共识协议，最早由 Tendermint Core 实现、现由 CometBFT 实现；其 ABCI 接口把共识与副本应用分离，使一个引擎可服务多条独立的 PoS 链，从而实现「共识与执行分离」。围绕该协议已有大量研究提出改动，覆盖从投票传播到出块与奖励分配等机制，但据作者所知尚无综述把协议与这些工作作为同一族系统研究，更宽的综述也不以 Tendermint 为主题。本文以「设计选择」为线索描述基线（由原始描述汇总而成的协议）：每个设计选择都是一项决定（如投票如何扩散、提议者如何轮换），基线在其故障与时序模型下靠它提供安全性与活性等性质；随后按「重新协商（修改或替换）了哪个设计选择」、「强化或弱化了哪些性质」、「结论是否需要更强的模型」对每项工作分类，并把方案归并为基线的几条关切主线：性能、验证者问责性、可利用信息的保护。",
        "en": "A systematization of knowledge on Tendermint/CometBFT BFT consensus that describes the baseline protocol by its design choices—each a decision through which the protocol provides safety and liveness under its fault and timing model—and classifies prior work by the design choice it renegotiates, the properties it strengthens or weakens, and whether it needs a stronger model. The solutions group into threads on performance, validator accountability, and protection of exploitable information.",
    },
    "2611.15920": {
        "zh": "软件越来越多由 AI 智能体依据自然语言规格生成实现（agentic coding），代码产出速度超过评审速度，并表现出特有的失效模式。基于性质的测试（PBT）用大量生成输入检验程序的不变性质，近期由 LLM 智能体代写性质，免去了长期阻碍其推广的性质推导成本；但现有方法仅从实现推导性质（Code-driven PBT），而 agentic coding 中详尽规格（如产品需求文档）已成常规，其在测试中的作用却鲜有研究。作者主张规格记录了代码「本该做什么」，由规格导出的不变性质不被具体实现选择偏置，因而提出 Spec-Driven PBT：智能体先仅依据规格用自然语言表述不变性质，之后才查看实现，把性质翻译为具体测试。在 ViBench、Spec-… 等 25 个应用上评估。",
        "en": "Spec-Driven PBT derives invariant properties from the specification (e.g. a product requirements document) in natural language first, and only then inspects the implementation to translate them into concrete tests, so the invariants are not biased by implementation choices. It is evaluated on 25 applications from ViBench and related suites against code-driven property-based testing.",
    },
    "2611.16516": {
        "zh": "近似最近邻（ANN）检索已成为向量数据库管理大规模嵌入数据的基础查询原语；为支撑不断增长的向量集合，机构把数据库管理与查询处理外包给第三方云，但不可信服务商可能返回次优或伪造结果，严重威胁 ANN 检索的完整性。已有可认证 ANN 方案可扩展性差：通常要传输高维向量以验证距离，并依赖与拓扑无关的认证结构，通信与验证开销过大。本文提出 VIDA：用紧凑向量承诺替代原始向量传输，用聚合内积论证一次高效验证多次距离计算；提出拓扑感知的认证数据结构 MeST，使认证路径与图遍历对齐，显著降低结构证明开销；并设计量化感知的认证策略，利用距离界做剪枝，减少需要密码学认证的精确距离数量。实验显示其效率优势。",
        "en": "VIDA is an efficient scheme for authenticated graph-based ANN search in outsourced vector databases: it replaces raw vector transmission with compact vector commitments, verifies many distance computations with an aggregated Inner Product Argument, introduces MeST—a topology-aware authenticated data structure aligning authentication paths with graph traversal—and exploits quantization-aware distance bounds for pruning, cutting communication and verification overhead.",
    },
    "2611.16566": {
        "zh": "稳态检测是软件性能基准测试的核心步骤，但不同检测方法依赖不同假设，可能在不同执行剖面上表现最佳。本文把稳态检测形式化为算法推荐问题：给定一条基准时间序列，预测两个互补检测器中哪个更合适——CP-SSD 通过执行轨迹的变点分段识别稳态，KB-KSSD 用核方法识别稳定行为。作者提出数据驱动的推荐器：用自动提取的特征刻画时间序列，并把监督预测与「行为相似的时间序列分组」信息结合。在 407 条有标注的基准序列上评估（以参考稳态指标可判定哪个检测器更优）：推荐器正确选出更优检测器的比例为 72.97%，而「总选最常最优的那个检测器」为 62.65%，绝对提升 10.32 个百分点，配对统计检验与自助法置信区间支持该结论；与仅用时间序列特征的推荐器对比表明聚类信息的贡献。",
        "en": "The paper formulates steady-state detection as algorithm recommendation between CP-SSD (changepoint segmentation) and KB-KSSD (kernel-based stability detection). A data-driven recommender combining automatically extracted time-series features with information from groups of similarly behaving series selects the better detector correctly for 72.97% of 407 labelled benchmark series, versus 62.65% for always picking the most often best detector—a 10.32 percentage point absolute gain.",
    },
    "2611.16588": {
        "zh": "漏洞库中的「受影响版本范围」决定扫描器、补丁流水线与应急响应把哪些部署视为有漏洞，但这些范围常不完整，导致有漏洞的发行版被静默当作安全。审计它需要可执行证据：给定某已列版本的 PoC 利用，证明同一漏洞能在更早的未列版本上触发。这种跨版本 PoC 迁移结合源码分析、环境修复与基于执行的验证。作者提出 CrossPloit：覆盖 Python Web 生态 45 个 CVE、127 个迁移实例的基准，每个实例含版本固定的容器、参考 PoC 与漏洞专用 oracle，并由两个校验器确认观察到的效果确实来自所披露漏洞。构建过程确认 149 个有漏洞的早期版本不在四个数据库的受影响列表中，其中 127 个需要迁移。18 种智能体配置（9 个模型 × 2 个 harness）中最佳解决 58.3%，改写的轨迹引导基线为 8.7%；攻击向量发生迁移的实例最难，无任何配置超过 37.9%；解决率更高与「漏用 API 类失败占比更低、不完整执行占比更高」相关。",
        "en": "CrossPloit is a benchmark of 127 cross-version PoC migration instances across 45 CVEs in the Python web ecosystem, each with a version-pinned container, reference PoC, vulnerability-specific oracle and two validators. Construction confirms 149 vulnerable prior versions missing from four databases' affected-version lists (127 requiring migration). Across 18 agent configurations the best resolves 58.3% versus 8.7% for an adapted trace-guided baseline; attack-vector shifts remain hardest, with no configuration above 37.9%.",
    },
    "2611.17044": {
        "zh": "LLM 已广泛用于数据库任务，但 Text2SQL 等工作都假定关系模式已存在。本文追问 LLM 能否从自然语言需求设计模式（Text2Schema）、把既有模式表述成文字（Schema2Text），并在 Schema→Text→Schema 往返中保持结构。作者提出 SchemaBridge：来自三个集合的 902 个模式，按规模与约束复杂度分层，分别对表、属性、域（数据类型与可空性）、实体与参照完整性打保真度分。评估 6 个开源与闭源 LLM 发现：(i) 人写需求对模式欠约束，无模型参照完整性 F1 超过 0.27；(ii) 明确要求「完整」时 LLM 生成的描述携带远多结构，GPT-5.4-mini 在 SchemaBench 上的参照 F1 从 0.228 升到 0.909，尽管 BLEU、ROUGE-L、BERTScore 反而下降；(iii) 受控实验表明在固定设定下构造器与描述器的选择都影响往返保真度；(iv) 掩码模式实验表明结构线索有助于恢复键与关系，而数据类型与可空性的联合信息在文字化过程中保留很差。",
        "en": "SchemaBridge is a benchmark of 902 schemata for Text2Schema, Schema2Text and schema round trips, scoring fidelity separately for tables, attributes, domain, entity and referential integrity. Across six LLMs, human-written requirements under-specify schemata (no model exceeds 0.27 referential F1), while explicitly complete LLM descriptions raise GPT-5.4-mini's referential F1 from 0.228 to 0.909 on SchemaBench even as BLEU/ROUGE-L/BERTScore drop; structural cues help recover keys and relationships, but joint data-type and nullability information survives verbalization poorly.",
    },
    "2611.16886": {
        "zh": "复杂算法的形式验证需要规格、不变式构造、数学证明与自动定理证明器管理等多重专长。LLM 虽能生成代码与证明片段，但可靠地完成完整的机器检查验证仍难：需要迭代地构造与校验规格和不变式、搭建证明、诊断求解器失败并优化验证性能。本文给出用 Dafny 做 LLM 辅助科学算法验证的系统化十步工作流，整合算法形式化、契约开发、不变式的经验性验证、证明构造、瓶颈剖析与资源驱动的证明优化；使用 Anthropic 的 Claude Opus 5 与 Opus 5.5，把 LLM 驱动开发与自动测试、验证反馈结合，同时在正确性关键决策与策略干预上保留人工监督。在图论与标号迁移系统共 37 个复杂算法上评估，其中包括验证 Hopcroft–Tarjan 三连通性判定——说明即便高难算法验证任务也可通过结构化的 LLM 辅助流程完成。",
        "en": "The paper presents a systematic ten-step workflow for LLM-assisted verification of scientific algorithms in Dafny, integrating formalization, contract development, empirical invariant validation, proof construction, bottleneck profiling and resource-driven proof optimization, with Claude Opus 5/5.5 and human oversight on correctness-critical decisions. It evaluates on 37 complex algorithms from graph theory and labelled transition systems, including a verified Hopcroft–Tarjan triconnectivity test.",
    },
    "2611.16590": {
        "zh": "长期航天器自主运行要求具身智能体在通信延迟、时敏操作、环境不确定性、复杂物理交互、功耗与算力约束、以及安全可靠性要求下使用运行历史。作者提出 AstroMemBench 与「场景—挑战—能力」设计方法，把这些要求映射为可执行的内存测试：覆盖 16 个内存子挑战、140 个模板、2,240 个实例，跨行星表面作业、在轨服务与深空探测的 9 项任务；确定性环境按任务完成、状态变化、安全与资源使用给动作打分。九种条件下的消融表明基准对「智能体恢复并使用历史信息的准确度」与内存系统设计差异都敏感。主实验比较六种配置：Mem0、Chain-of-Memory、LightMem 与 RAG 相对原生 Pi Agent 提升同会话平均分，但三种内存系统相对 RAG 并无明显优势；会话重启后 Mem0 比 RAG 高 12.25 分。收益更多来自指令保持与结果复用，而非持续状态跟踪与能量预留。",
        "en": "AstroMemBench is a benchmark for memory in embodied spacecraft agents, with 16 memory subchallenges, 140 templates and 2,240 instances across nine tasks in planetary surface operations, on-orbit servicing and deep space exploration, scored by a deterministic environment on completion, state change, safety and resource use. Mem0, Chain-of-Memory, LightMem and RAG beat the native Pi Agent within a session with no clear advantage over RAG, but after a session restart Mem0 leads RAG by 12.25 points; benefits favour instruction retention and result reuse over ongoing state tracking.",
    },
    "2611.16433": {
        "zh": "LLM 的进展正迅速改变形式定理证明，但进一步突破受限于缺少透明有效的训练数据配方来系统性提升证明模型。作者主张有效的智能体证明器既要强数学技能先验来为证明打底，又要智能体轨迹来支撑长程交互式证明构造。为此合成 33.7B token 的「智能体原生」中训练语料，覆盖分解、搜索、自验证与修订，并配有验证器锚定的智能体轨迹；进一步提出 daVinci-Prover harness，让模型在隔离工作区内构造证明并与 Lean 验证器交互，据此收集约 36K 条高质量轨迹做监督微调。该中训练配方在 MiniF2F、FATE-M 与 ProofNet 上相对匹配的 Qwen3-8B 仅 SFT 基线平均提升 13.7 分；用于 Qwen3.5 系列时在多个定理证明基准上同样表现强劲，配合内存压缩在 MiniF2F 上接近饱和。",
        "en": "daVinci-Prover introduces an agent-native 33.7B-token mid-training corpus covering decomposition, search, self-verification and revision, plus verifier-grounded agentic trajectories, and a harness that lets models build proofs against a Lean verifier in an isolated workspace (about 36K trajectories for SFT). The recipe yields a 13.7-point average gain over a matched Qwen3-8B SFT-only baseline on MiniF2F, FATE-M and ProofNet, and near-saturating MiniF2F performance with memory compaction on Qwen3.5.",
    },
    "2611.16184": {
        "zh": "表格数据的上下文异常检测旨在找出在其上下文条件下行为异常的记录；在数据工程流水线中，它用于筛出测量值违反上下文相关完整性关系的行。现有方法要么是分布表达力有限的浅层条件模型，要么是需要逐上下文建模的局部估计器，难以刻画复杂条件关系并扩展到高维。作者提出基于 Flow Matching 的 Flow-CAD：学习单个全局、摊还的条件生成模型，灵活表示以上下文为条件的行为分布，不假定简单参数形式、也无需为每个上下文重训局部模型。为得到稳健可解释的异常评分，提出由所学条件流导出的「尺度归一化截断残差能量」，可稳定评分、抑制极端偏差主导并支持逐特征归因；并从理论上说明该残差评分在速度估计误差下稳定、其蒙特卡洛估计量满足一致性。",
        "en": "Flow-CAD learns a single global, amortized conditional generative model via flow matching to represent behaviour distributions conditioned on context for tabular contextual anomaly detection, avoiding shallow conditional models and per-context estimators. A scale-normalized, truncated residual energy derived from the learned flow stabilizes scores, mitigates domination by extreme deviations and supports feature-wise attribution, with theoretical stability under velocity estimation error.",
    },
    "2611.15348": {
        "zh": "电子鼻（eNose）通过呼出气体分析为疾病筛查提供便携无创路径，但该领域缺少在真实条件下系统比较机器学习方法的基准，尤其是传感器漂移这一已知却少被量化的失效模式；现有研究多依赖小型私有数据集与不一致协议，结果不可比、进展缓慢。作者提出 Breath-Dx：首个面向呼气疾病筛查的时间序列分类综合基准。工作基于 Scent of Health（S-OH）数据集——迄今最大的公开临床 eNose 集合，含 1,234 名患者、9 个诊断组，每人提供 17 通道多变量时间序列，并给出显式考虑传感器漂移的时间序训练/测试划分。系统评估覆盖四个族系（基于特征的表格学习器、卷积模型、图模型、时间序列架构）的 10 种方法：所有方法在时间序验证下都显著退化（相对随机交叉验证 AUC 下降 0.05–0.12），证实漂移嵌入强时间信号。",
        "en": "Breath-Dx is the first comprehensive benchmark of time-series classification for breath-based disease screening, built on the Scent of Health dataset (1,234 patients, nine diagnostic groups, 17-channel multivariate series) with explicit temporal train/test splits that account for sensor drift. Evaluating 10 methods across four families, all degrade by 0.05–0.12 AUC under temporal validation versus random cross-validation, confirming that drift embeds a strong temporal signal.",
    },
    "2611.15465": {
        "zh": "声学异常检测（AAD）是非接触式设备状态监测手段，但现有研究多在离线环境评估，很少考虑嵌入式硬件约束或运行漂移下的麦克风差异。本文在两个嵌入式平台——ESP32-S3（外接 I2S 数字麦克风）与 Arduino Nicla Vision（板载 PDM 麦克风）——上，用同一检测模型做边缘端持续 AAD 的对比评估。模型用轻量 ShallowNet 编码器与对比原型学习，把频谱图映射到 32 维嵌入；两块板运行相同的 TFLM 编码器，在设备上以指数滑动平均更新原型；经 Firebase 与 MQTT 编排的云端流水线支持远程采集与再训练。用标准 DCASE Challenge Task 2 机器声、以受控扬声器回放协议评估：ESP32-S3 在五类机器上准确率 82.35%–95.00%，Nicla Vision 为 79.41%–95.00%，两平台表现相当。",
        "en": "A cross-platform study of on-edge continual acoustic anomaly detection on ESP32-S3 (external I2S microphone) and Arduino Nicla Vision (onboard PDM microphone) with a shared ShallowNet encoder plus contrastive prototype learning into a 32-dimensional space, identical TFLM encoders, on-device EMA prototype updates and a Firebase/MQTT retraining pipeline. Under a speaker-replay protocol with DCASE Task 2 machine sounds, accuracy is 82.35–95.00% on ESP32-S3 and 79.41–95.00% on Nicla Vision.",
    },
    "2611.16789": {
        "zh": "拧紧系统产生的过程数据不断增多，叠加算力、存储与算法的进步，正推动人工智能在该领域的应用。准确检测并分类拧紧错误对保证产品质量、避免昂贵的返工、以及通过便于维护/复用/回收螺纹连接产品来支撑可持续性都至关重要。在此背景下，机器学习相比窗口法、包络曲线等传统监测手段是更有前景的替代。本文研究用深度学习做拧紧过程的异常检测与错误分类：数据语料为记录扭矩、旋转角度等过程参数的多变量时间序列；异常检测分析向量量化变分自编码器（VQ-VAE）的嵌入空间，错误分类评估四种模型架构。结果验证了异常检测的有效性，并确认深度学习模型能区分多个错误类别，超越传统的二分类能力。",
        "en": "The study applies deep learning to anomaly detection and error classification in screwdriving processes using multivariate time series of torque and rotation angle: anomaly detection analyses the embedding space of a vector-quantized variational autoencoder, and error classification compares four model architectures. Results confirm effective anomaly detection and show that deep models distinguish multiple error categories beyond binary classification.",
    },
    "2611.14581": {
        "zh": "LLM 调用工具读写数据的智能体工作流有两种评估方式：基准把最终状态与标准答案比较；线上服务没有标准答案，由 LLM 裁判阅读轨迹判定。实践中两者被当作可互换，本文测量是否真的如此。作者在 tau2-bench 的航空与零售域跑 2,160 个 episode，记录每次数据库写入，并按四种方式评分：对照标准状态的原生评分、LLM 裁判、给裁判提供策略文档、以及边界评估器（仅用规则检查「是否预期写入」与「轨迹中是否真的写入」）。两名标注者独立标注 120 个 episode 的任务正确性、策略合规与承诺正确性。裁判对自身判定重复率 98.2%，但与原生评分一致率仅 56.2%。有 11 个 episode 智能体执行了被禁止的写入，裁判放过 10/11（无论是否给策略或轨迹），更强裁判仍放过 6 个；不做模型调用的边界评估器全部抓到 11 个，且在人工标签上无裁判显著优于它。无门控时 11.1% 的 episode 出现禁止写入，而验证、纠正与安全终止门控并未显著降低该比例。",
        "en": "The paper measures whether native scoring and LLM judges are interchangeable for agentic workflows. Over 2,160 tau2-bench episodes with every database write recorded and four scoring methods, the judge repeats its own verdict 98.2% of the time but agrees with native scoring only 56.2%; it passed 10 of 11 episodes containing forbidden writes (a stronger judge passed 6), while a model-free rule-based boundary evaluator caught all 11 and no judge significantly beat it on human labels. Forbidden writes occurred in 11.1% of ungated episodes and the tested gates did not significantly reduce them.",
    },
    "2611.14945": {
        "zh": "有效吞吐（原始吞吐 × 交易成功率）决定 Hyperledger Fabric 等「执行—排序—验证」（EOV）链的有用容量。已有工作要么调配置提高原始吞吐（需大量昂贵重部署），要么控制冲突提高成功率（且只能在执行后用内核修改修复）；少数联合方法只调少量参数，仍依赖内核改动解冲突。作者提出 Auriga：非侵入式框架，通过样本高效的 LLM 引导配置搜索与执行前冲突预防同时优化两个因子。其 harness 治理的多智能体架构协调 LLM 做参数探索、饱和感知评估与经验固化，由 harness 控制工具与内存访问并保留终止权。交易调度上，LLM 离线从智能合约抽取符号 AST 模板；运行时调度器在不执行交易的前提下预测读写集，把交易划分为无冲突组。在三个基准、冲突率高达 70% 的情形下，有效吞吐相对默认 Fabric 最高提升 6.0 倍、相对最强基线 2.0 倍；调参智能体还发现了未文档化的配置。",
        "en": "Auriga is a non-invasive framework that jointly optimizes raw throughput and transaction success rate in Execute-Order-Validate permissioned blockchains, combining sample-efficient LLM-guided configuration search under a harness-governed multi-agent architecture with pre-execution conflict prevention: an LLM extracts symbolic AST templates from contracts offline, and a runtime scheduler predicts read-write sets without executing transactions to partition them into conflict-free groups. Across three benchmarks and conflict rates up to 70% it improves effective throughput up to 6.0x over default Fabric and 2.0x over the strongest baseline.",
    },
    "2611.16991": {
        "zh": "编码智能体在软件开发上表现强劲，但其在受物理约束支配的长程工程任务上的能力仍不清楚。本文以模拟电路版图设计为切入点研究该问题——它同时要求领域知识、几何推理与对设计与验证工具的迭代交互。作者提出 AnalogLayoutWorld：开源智能体基准，含 40 个经专家评审的任务，要求从固定的晶体管级网表完成端到端版图生成；它把集成设计环境与独立的物理验证、版图后电气验证结合，并提供与模拟版图专家共同设计的客观质量指标。在 13 种模型—harness 配置下，91.1% 的尝试能产出 GDS 版图，但仅 23.0% 满足基准验收标准；作者还评估了内部智能体系统 Novara，其取得已报告的最高综合分。分析把性能差异与固定预算下的测试时扩展联系起来，提示推理效率与对验证反馈的有效利用有助于在任务复杂度上升时维持设计质量。",
        "en": "AnalogLayoutWorld is an open benchmark of 40 expert-reviewed tasks for end-to-end analog layout generation from fixed transistor-level netlists, combining an integrated design environment with independent physical and post-layout electrical verification and expert-co-designed quality metrics. Across 13 model–harness configurations, 91.1% of attempts produce GDS layouts but only 23.0% meet acceptance criteria; the internal agent Novara scores highest, and differences trace to test-time scaling under fixed budgets.",
    },
    "2611.15108": {
        "zh": "Coq、Agda、Lean 4 等证明助手把「证明无关性」内建进定义性转换（对 p, q : P 且 P : Prop 有 p ≡ q），抹去了定理是由哪条推导确立的。这对固定公理上的数学很自然，但与「已验证科学知识库」不相容——后者必须检视并比较同一主张的独立推导，以评估证据一致性（consilience），并在某个检测、试剂或模型失效时计算反事实撤回；此外，把定义性证明无关性与单元素消去结合会破坏强规范化，并使算法化转换失去传递性。作者给出 Eigenius（面向科学的已验证知识基底）的类型论与制度论基础：一是带累积宇宙（Prop、Set、Type_k）、非直谓 Prop、带索引强制单元素消去的归纳族与内涵恒等类型的依赖内核，其中定义相等 ≡ 是正交 CRS 下的无类型可连接性，而证明无关性是被见证的命题公理；二是把宇宙累积性、余域协变的 Π-子类型与本体类包含统一起来。",
        "en": "The paper presents the type-theoretic and institutional foundations of Eigenius, a verified knowledge substrate for science, arguing that judgmental proof irrelevance in Coq/Agda/Lean 4 erases which derivation established a claim and is incompatible with stores that must compare independent derivations (consilience) and compute counterfactual retractions. It formulates a dependent kernel with cumulative universes, impredicative Prop, inductive families with index-forced subsingleton elimination and intensional identity types, where proof irrelevance is a witnessed propositional axiom, and unifies cumulativity, codomain-covariant Π-subtyping and ontology class inclusions.",
    },
    "2611.15276": {
        "zh": "智能体自我改进需要关于任务是否成功的反馈，但测试时外部反馈可能不可得，智能体只能从可观察证据推断成功，而不完整的验证会误导后续更新。作者提出 Verify by Doing（VbD）：在单个任务内让 Actor 与 Evaluator 两套 harness 共同演化，同时保持模型权重固定。Evaluator 用工具主动检查产物与环境状态，其发现既为输出选择提供内部信号，也指导执行与验证流程的更新；候选 Evaluator 要在共同候选上接受比较评审，而 Actor 的更新必须由其自身的新输出支撑。在 AutomationBench、τ³ Banking 与部分 GDPval 任务上，VbD 在「无外部反馈」的方法中综合得分最高，在主干模型上相对最强基线分别提升 3.3、4.1 与 2.3 个百分点；消融支持主动验证与 Evaluator 演化的贡献，且从固定候选池中选择表明改进验证能在不生成新输出的情况下捞回成功结果。",
        "en": "Verify by Doing co-evolves Actor and Evaluator harnesses within a single task while keeping model weights fixed: the Evaluator actively inspects artifacts and environment state with tools, grounding an internal signal for output selection and for updates to both execution and verification procedures, with Evaluators subject to comparative review and Actor updates requiring support from fresh outputs. On AutomationBench, τ³ Banking and selected GDPval tasks it scores highest among methods without external feedback, gaining 3.3, 4.1 and 2.3 percentage points over the strongest baselines.",
    },
    "2611.14949": {
        "zh": "从采样解数据中辨识并求解偏微分方程（PDE）通常需要在方程发现、系数估计与数值求解器配置上投入大量专家精力，在噪声与分布偏移下尤甚。LLM 智能体能否准确高效地自动化这一流程？为此作者提出 RSI-PDEbench：含 1,001 个案例、42 个方程模板（含经典与分数阶 PDE）的基准，提供三种评估设定——Full（无噪解数据）、Noisy（高斯噪声 RMS 为干净信号 RMS 的 50%）、Hard-OOD（对未见方程模板与偏移系数范围的分布外泛化）。作者进一步提出 RSI-PDE：递归自我改进的智能体 harness，按残差损失筛选候选方程，用相对 L² 反馈精化系数与数值求解器，并对策略与记忆更新施加验证门控。在四个前沿模型上，把 RSI-PDE 与单次运行基线及原生智能体 harness（Claude Code、Codex）对比，三种设定下的平均通过率均有提升。",
        "en": "RSI-PDEbench is a benchmark of 1,001 cases over 42 equation templates (classical and fractional PDEs) with three settings—Full, Noisy (Gaussian noise at 50% of clean RMS) and Hard-OOD—for LLM agents that identify and solve PDEs from sampled solutions. RSI-PDE is a recursively self-improving harness that shortlists equations by residual loss, refines coefficients and solvers with relative L2 feedback, and gates policy/memory updates; across four frontier models it improves average pass rates over single-run baselines and native Claude Code/Codex harnesses.",
    },
}


def main():
    path = os.path.join(OUT, "summaries.json")
    with open(path, encoding="utf-8") as f:
        summ = json.load(f)
    added, skipped = [], []
    for sid, pair in SUMM.items():
        old = summ.get(sid)
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
