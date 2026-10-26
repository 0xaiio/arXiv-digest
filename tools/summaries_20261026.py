# -*- coding: utf-8 -*-
"""2026-10-26 批次：本期 24 篇推荐项（核心 14 + 兴趣扩展 10）的双语简介 + 摘要中文译文。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- abstracts_zh.json 的 value 为纯字符串（中文译文）；已存在的不覆盖。
key 一律 arXiv 短号。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    # ---------------- 核心六分类 ----------------
    "2610.32053": {
        "zh": "在「自然语言需求 + 正确性未知的实现」双模态下考察 LLM 生成的 ACSL 规约：1403 个 C 程序经 Frama-C 检验后发现，程序正确时给出需求并不提升通过率；程序错误时模型会写出过弱或被实现带偏的规约从而假性通过验证，换更强提示也压不住。",
        "en": "An empirical study of LLM-based ACSL specification generation in the bimodal setting of requirement plus unverified implementation: over 1,403 C programs checked by Frama-C, a correct implementation gains nothing from the requirement, while an incorrect one can still pass through weak or implementation-misled specifications that stronger prompting does not fix.",
    },
    "2610.32597": {
        "zh": "用失败断言引导 LLM 生成多行 RTL 补丁，每个候选补丁须经 JasperGold 模型检查器形式验证才被接受；在 BRISC-V 核上修复单行缺陷 98%、多行缺陷 93%，是目前首个面向多行 RTL 缺陷的自动化 LLM 修复结果。",
        "en": "LLM-generated RTL patches are guided by failing assertions and each candidate is admitted only after formal verification with the JasperGold model checker, repairing up to 98% of single-line and 93% of multi-line bugs on the BRISC-V core.",
    },
    "2610.32844": {
        "zh": "为时间戳对象给出紧界：在崩溃失败与带/不带签名的拜占庭失败下分别确定最优容错度，并（除一种情形外）确定最小时延；核心技术是新的下界方法「循环链论证」——构造一圈不可区分的调度，使返回的时间戳必须严格递增，从而矛盾。",
        "en": "The paper determines optimal resilience for the timestamp object under crash and signed/unsigned Byzantine failures and its minimum latency in all but one case, introducing a cyclic-chain argument that builds a cycle of indistinguishable schedules along which returned timestamps must strictly increase.",
    },
    "2610.32803": {
        "zh": "后量子共识干脆不用法定人数证书：每个验证者自行在已收消息中统计法定人数，安全性与活性都不依赖签名（签名只用于问责）；快速路径保持「分发 + 两轮投票」的最优时延，失败后转入无签名的多提议者拜占庭协议 Coda。",
        "en": "Quantum Cadence drops quorum certificates entirely: each validator counts quorums among the messages it has received, so safety and liveness need no signatures, and the optimal dissemination-plus-two-votes fast path falls back to the signature-free multi-proposer agreement Coda.",
    },
    "2610.32558": {
        "zh": "证明带嵌套会话类型的异步会话进程 ASP 是图灵完备的：把双计数器机编码为良类型进程，其状态感知的计数器与指令表示由嵌套会话类型精确约束——也就是说，这类类型系统能表达的协议远超正则语言。",
        "en": "ASP, the asynchronous session process model behind nested session types, is proved Turing complete by a correct encoding of two-counter machines into typed processes whose state-aware counters and instructions are governed by the nested types.",
    },
    "2610.32247": {
        "zh": "百度把元数据从通用数据库里拿出来重做：按目录树拓扑分片与执行、语义感知的关键路径外处理、生命周期感知的存储引擎（内存 MVCC + 局部性感知压缩），吞吐提升 2.2–4.1 倍、机器数减半；已生产运行五年、单集群 1000+ 节点 / 数十万亿记录 / EB 级。",
        "en": "MetaDB removes three mismatches between general-purpose databases and file-system metadata through tree-topology-induced sharding, semantic-aware off-critical-path processing and a lifecycle-aware storage engine, reaching 2.2-4.1x throughput at half the machines and running in production at Baidu for over five years.",
    },
    "2610.32015": {
        "zh": "把图查询当作查询处理而非搜索：查询以含通配符与比较操作的子图给出，先分区再用「聚焦探索 + 分布式处理」并行求全解或前 k 解，并给出减少加载分区数的启发式与负载均衡方案，同时论证存在分区时的正确性。",
        "en": "The paper treats graph querying as query processing rather than search: it partitions the graph and answers queries containing wildcards and comparisons through focused exploration plus distributed processing, with heuristics that bound the partitions loaded and explicit load balancing.",
    },
    "2610.32934": {
        "zh": "用运行时结构不变量在无头浏览器里抓 RTL 镜像缺陷：Bootstrap / Material 的 14 个真实缺陷检出 13 个、误报 0，负例与 43 个未改动组件同样零误报，还在 Bulma 1.0.4 里报出一个真实方向性缺陷；axe-core、Playwright 与 Stylelint 逻辑属性规则都定位不到。",
        "en": "Runtime structural invariants over computed style and geometry detect right-to-left mirroring defects that accessibility, actionability and logical-property linting miss, recovering 13 of 14 reconstructed real RTL bugs with zero false alarms and surfacing a live defect in Bulma 1.0.4.",
    },
    "2610.32118": {
        "zh": "145 名一年级软工学生、962 轮人机交互、172 次主动干预：74.4% 的干预指向输出「是否适合这项工程任务」，只有 16.9% 涉及正确性；手段以改写输出（51.0%）与精炼提示（28.2%）为主，被判为轻微瑕疵的输出反而让学生评估信心更低。",
        "en": "Across 962 student-AI turns and 172 declared interventions, oversight targets fitness for the engineering task (74.4%) far more than correctness (16.9%), enacted mostly by modifying outputs (51.0%) or refining prompts (28.2%), with perceived minor flaws lowering evaluation confidence.",
    },
    "2610.32438": {
        "zh": "对 Tour Perret LoRaWAN（421,937 帧、5 设备）先做覆盖审计：CO2 全缺、气压仅 4.24%，四变量联合分析不成立，改为温湿双变量——相关 r=-0.662、PC1 占 83.1%、孤立森林标出 2.12% 多变量异常（单变量 Z 分数一个都没抓到）、DBSCAN 隔离 0.17% 噪声。",
        "en": "A C++17 pipeline audits coverage in a 421,937-frame LoRaWAN dataset, finds CO2 entirely absent and pressure at 4.24%, then refocuses on temperature-humidity: r = -0.662, PC1 at 83.1% of variance, Isolation Forest flagging 2.12% multivariate anomalies where univariate Z-scores flag none.",
    },
    "2610.32583": {
        "zh": "给 madGLP 智能体平台补上此前缺失的网络层规范：凡 GLP 能表达的一律用 GLP，该层只提供网络栈、位置服务、应用证明与密码原语；BLE/局域网用由密钥与时间槽派生的轮转令牌，公网靠任何人都能跑的会合服务器打洞且不中继载荷。",
        "en": "The paper specifies the missing networking layer beneath madGLP: everything expressible in GLP stays in GLP, leaving the layer only the stack, location service, attestation and cryptographic primitives, with rotating recognition tokens on PAN/LAN and rendezvous servers that punch holes but relay no payload.",
    },
    "2610.32648": {
        "zh": "在执行前拦下「幻觉工具调用」：在 harness 边界拦截动作，用 AST 与命令分析抽取前置状态谓词并对活仓库做确定性校验；2508 个动作上精确率 0.940、F1 0.817，比最强 LLM 裁判高 35.3%，中位检测时延从 17.73 秒降到 1.50 毫秒且零 token 消耗。",
        "en": "StateMirror intercepts actions at the harness boundary, extracts state predicates by AST and command analysis and validates them deterministically against the live repository, reaching 0.940 precision and 0.817 F1 at 1.50 ms median latency with no token cost.",
    },
    "2610.31895": {
        "zh": "提出 ImpasseBench：在可解修复任务中注入 12 类真实阻塞，并标注「证据已充分」的那一步。八个前沿模型、19,371 条轨迹显示几乎每次需要外援的运行都攒够了证据，仍有三分之一耗尽预算，且所有不安全请求都出现在该点之后；加一个升级工具能把预算耗尽率从 34.0% 压到 6.7%。",
        "en": "ImpasseBench injects twelve realistic environment blockers and marks the step at which evidence suffices: nearly every run needing outside help has enough evidence, yet a third still exhaust their budget, and an escalation tool cuts exhaustion from 34.0% to 6.7%.",
    },
    "2610.31712": {
        "zh": "图—文模板把 UI 状态与动作转移、任务意图与类型化槽位分开存，复用前逐转移对照当前指令与实时界面校验——复用、改写或丢弃：五个基座在 AndroidWorld 上省约 80% 推理 token，多数达 1.5 倍以上加速；Android/HarmonyOS 真机动作复用率 70.7–79.8%、多数场景 2 倍以上。",
        "en": "Graph-text templates separate UI states and action transitions from task intent and typed slots so individual transitions are reused, adapted or discarded against live UI state, cutting inference tokens by about 80% with 1.5x or better speedups.",
    },
    # ---------------- 兴趣扩展 ----------------
    "2610.32661": {
        "zh": "发布水质 CPS 混合数据集：真实边缘节点 8.0 小时记录与 EPANET-MSX 13 节点仿真共登记，配参数化攻击库与样本级真值；并指出随机行划分 + 用输入特征算标签会给出 macro-F1=0.9998 的无意义高分，改用按时间切分与留出攻击类型的防泄漏协议后，攻击分类无人跑赢常数「正常」预测器（macro-F1=0.465）。",
        "en": "AquaSense-ICS co-registers real edge-node recordings with an EPANET-MSX simulated network plus a parameterised attack library, and shows random row splits with feature-derived labels yield a meaningless 0.9998 macro-F1 whereas a leakage-aware protocol caps attack classification at 0.465.",
    },
    "2610.32919": {
        "zh": "换掉「逻辑等价」这个过强判据：只要库能分别证明 P 与 Q，P↔Q 就自动成立，证明器越强越容易误判。SemantEq 要求两条陈述只能经由逻辑重排、用库内方程改写等允许步骤互推，并按 Lean 检查的证明项而非策略脚本判定；无模型搜索在 ProofNetVerif 上取 100% 精确率 / 65.6% 召回（BEq+ 为 95.8% / 61.8%）。",
        "en": "Because logical equivalence passes trivially once a prover can prove both sides, SemantEq instead requires each statement to reach the other only through allowed steps, judged by the Lean-checked proof term, reaching 100% precision and 65.6% recall where BEq+ gets 95.8% and 61.8%.",
    },
    "2610.32223": {
        "zh": "在被「防护」的 GUI 环境里，答对验证码并不等于完成任务：SolveBind 用分层求解树拆出感知/定位/求解/动作/验证五项能力，再由运行时监督把动作承诺锚在工具证据上、按恢复预算重规划；九类验证码任务族、九个基座里八个成功率最高，领先最强基线 13.3–34.5 个百分点；移除绑定使自动提交成功率从 82.22% 掉到 71.56%。",
        "en": "SolveBind decomposes CAPTCHA solving into perceive, ground, solve, act and verify capabilities and adds a runtime supervisor grounding commitments in tool evidence, topping eight of nine backbones by 13.3-34.5 points; removing the binding drops submission success from 82.22% to 71.56%.",
    },
    "2610.32486": {
        "zh": "零样本视频异常检测的省算力做法：在语义嵌入空间用 δ 信号抓突变、漂移信号抓渐变，OR 门控 + 自适应 EMA 阈值；再用阈值门控级联，只有置信度需要时才调用昂贵的视频级时序分析。XD-Violence 92.07%、MSAD 86.70%、ShanghaiTech 80.54% AUC-ROC，属免训练零样本方法的新最优。",
        "en": "SAAF gates a cheap frame-level VLM pass behind delta and drift signals in embedding space and escalates to video-level temporal analysis only when confidence warrants it, setting state of the art among training-free zero-shot methods at 92.07% AUC-ROC on XD-Violence.",
    },
    "2610.32639": {
        "zh": "给包处理 DSL 建共享中间表示：Peregrine 自带形式语义，等价性检查器用 Rocq 编写并证明正确，可用于校验不可信的编译器 pass，甚至为包分类算法的正确性出证明（时间可接受）。",
        "en": "Peregrine is a language-agnostic packet-processing IR with formal semantics and a Rocq-written, proved-correct equivalence checker, used to validate untrusted compiler passes and to certify packet-classification algorithms within reasonable time.",
    },
    "2610.32362": {
        "zh": "用算法子群发现做临床模型性能监控：223,228 张胸片上，自动发现的子群准确率跨度 0.61–0.90，比传统人口统计学分组（0.80–0.94）暴露更大差距，且多数可由患者/采集/模型元数据解释；这些子群标注还能反过来缓解它自己揭示的偏差。",
        "en": "On 223,228 chest X-rays, algorithmically discovered subgroups show wider accuracy gaps (0.61-0.90) than metadata-based analysis (0.80-0.94), are largely interpretable through patient, acquisition and model metadata, and their annotations can mitigate the biases they expose.",
    },
    "2610.31984": {
        "zh": "给浏览器里的 WebAssembly 应用建行为基线：监控良性条件下的函数级执行轨迹训练 LSTM，运行期把偏离判为攻击；67 个应用、十类漏洞上零漏报、误报率 0.42%，且不需要逐漏洞签名。",
        "en": "WADE learns each Wasm application's benign function-level execution traces with an LSTM and flags runtime deviations, reporting zero false negatives and a 0.42% false positive rate across 67 applications and ten vulnerability classes without per-vulnerability signatures.",
    },
    "2610.31810": {
        "zh": "把作者留在环内的论文形式化流水线：从 LaTeX 源码出发，把论文转成陈述依赖图，逐条做忠实性/歧义/正确性审计，再对 Mathlib 等库形式化并证明；凡陈述有多种读法就停下来问作者，任何可能改变论文主张的决定都交还作者。",
        "en": "PaperFormalizer turns a paper's LaTeX source into a dependency graph of statements, audits each in natural language, then formalizes and proves them in Lean, halting to ask the author whenever a statement admits more than one reading.",
    },
    "2610.32337": {
        "zh": "把单类多变量时序异常检测改写成「当前点系统状态相容性估计」：不重建、不预测，而以当前点为中心检索窗口上下文、按当前点编码时间并自适应混合，得到隐表示后用固定标准正态负对数似然打分——对局部波动因此不敏感。",
        "en": "TENET reframes one-class multivariate time-series anomaly detection as current-point state compatibility estimation, building a latent representation of the target point from variable-level context and scoring it with a fixed standard-normal negative log-likelihood rather than reconstruction or forecasting error.",
    },
    "2610.32103": {
        "zh": "把分子语言模型当提议器做推理期对齐：用 Metropolis–Hastings 搜索引导逐步编辑，兼顾性质提升、性质保持与先导物相似性；冻结基座在 C-MuMOInstruct 与 SMDD 上多目标优化成功率显著提高，搜索轨迹还可蒸馏回模型。",
        "en": "ReMedI uses a frozen molecular language model as base proposer and Metropolis-Hastings refinement to guide sequential edits under multi-objective rewards, improving multi-objective success on C-MuMOInstruct and SMDD without task-specific fine-tuning.",
    },
}

ABS = {
    "2610.32053": "形式规约生成是形式验证与软件正确性保证的关键一步，但现有基于大模型的规约生成方法往往假定输入程序正确，与「在正确性未知时判定程序是否满足需求」的验证本意相悖。作者在双模态设定下（同时给出自然语言需求与正确性未知的代码实现）构建 1403 个 C 程序的基准，用 Frama-C 检验生成 ACSL 规约，发现：代码正确时，额外提供自然语言需求并不能提高规约通过率；代码错误时，模型可能生成弱规约或受实现误导的规约而假性通过验证，且先进提示手段也无法完全缓解。与基于自然语言推理的 HoarePrompt 相比，LLM 生成的形式规约在预测程序正确性上更不有效。",
    "2610.32597": "RTL 设计的功能验证已成为半导体开发的瓶颈，常占用项目大部分资源，调试尤耗时间。现有 LLM 辅助 RTL 调试方法多针对单行缺陷、开环运行、依赖提示或检索，缺乏可扩展性且常给出错误修复。本文提出结合 LLM、断言与模型检查器的自动化修复方法：以失败断言引导 LLM 为多行缺陷生成补丁，每个候选补丁都由模型检查器 JasperGold 形式验证，只有有效修复才被接受。在 BRISC-V RISC-V 核上用多种变异类型做变异测试评估，可修复 98% 的单行缺陷与 93% 的多行缺陷；据作者所知，这是首个展示自动化、LLM 辅助的多行 RTL 缺陷修复的工作。",
    "2610.32844": "时间戳广泛用于分布式算法排序操作。本文研究时间戳对象（TS）——只提供一个操作、返回严格递增整数——在异步消息传递系统中的两个问题：最大容错度与最小时延（以最坏消息延迟度量），覆盖崩溃失败与带/不带数字签名的拜占庭失败。作者给出下界与算法，确定各类失败下 TS 实现的最优容错度，并在除一种情形外的所有情况下确定最优时延。为此提出新的下界证明技术「循环链论证」：构造由不可区分调度组成的环，环上返回的时间戳必须严格递增，从而导出矛盾。",
    "2610.32803": "高性能区块链的共识协议多用法定人数证书（把一组验证者的签名打包）。BLS 类方案可把整组签名聚合为单个短签名，使证书保持小巧，但大规模量子计算机会攻破这些方案，且目前没有聚合大小与聚合时间可比的后量子替代。若不聚合，证书需为每位成员携带一个大的后量子签名，使每个验证者广播证书在现代共识中不可行。本文提出支持多并发提议者的后量子共识 Quantum Cadence：完全避免证书，每个验证者在已收消息中自行统计法定人数，安全性与活性不依赖签名（签名仅为问责而加）。它基于 Cadence，把槽位共识 Chorus 换成 Quantum Chorus，保留「分发 + 两轮投票」的最优快速路径时延；快速路径失败时运行无签名的多提议者拜占庭协议 Coda，并给出调度槽位的 Conductor 的适配方案，附仿真结果。",
    "2610.32558": "会话类型以类型刻画通道协议，类型检查即保证通信正确，但传统会话类型只能表达正则协议，遗漏了实践中大量协议。嵌套会话类型（NST）可描述嵌套递归协议，已知与单计数器机及确定性上下文无关语言对应。本文研究 NST 对应的进程模型 ASP（异步会话进程）的表达力，通过把双计数器机正确编码为良类型进程，证明 ASP 图灵完备。该编码采用非平凡的状态感知计数器与指令表示，并由嵌套会话类型良好约束。",
    "2610.32247": "生产存储系统日益依赖分布式数据库管理元数据，但百度经验表明把通用数据库当黑盒会浪费大量性能：文件系统元数据具有目录树局部性、差异化一致性需求与成簇删除特性，通用数据库基本无视这些。本文提出 MetaDB，作为百度大规模存储系统共享元数据层的元数据感知分布式事务数据库，针对三处不匹配——数据模型、事务模型与存储实现——分别采用（1）树拓扑诱导的分片与执行、（2）语义感知的关键路径外处理、（3）带内存 MVCC 与局部性感知压缩的生命周期感知存储引擎。MetaDB 吞吐为此前通用数据库的 2.2–4.1 倍，元数据机器数量减半；已在百度生产部署五年以上，统一全公司存储机群的元数据管理，单集群扩展到 1000 以上元数据节点、数十万亿条记录与 EB 级存储。",
    "2610.32015": "本文关注图上的查询处理而非（近似或精确）搜索，目标是求出全部或前 k 个答案，并重视查询的表达力。SQL 查询处理已成熟数十年，图数据查询处理却未获同等关注；Neo4J 等系统虽已大规模用图表示数据，其算法仍属专有。作者提出先对任意规模图做划分、再借助分布式范式获得效率与可扩展性：查询以含通配符与比较操作的子图形式给出，分区方案利用聚焦探索与分布式处理获得并行度、改善响应时间，并给出减少查询时需加载分区数的启发式。文中给出分区算法、分布式处理架构与计算答案的负载均衡方案，论证存在分区时方法的正确性，比较多种负载均衡启发式，并给出大量实验。",
    "2610.32934": "双向（RTL）布局缺陷源于用物理方向 CSS（margin-left、border-left、text-align:left）书写的界面在 dir=\"rtl\" 下渲染时未做镜像。无障碍引擎（axe-core）、可操作性引擎（Playwright）乃至 Stylelint 当前核心逻辑属性规则都无法定位这类缺陷。本文提出运行时结构不变量——基于计算样式与几何的 zero-golden 模式，以及双向保守的差分模式——在无头浏览器中检出它们。在由 Bootstrap 与 Material Components Web 的修复提交重建的 14 个真实 RTL 缺陷留出集上，检出器恢复 13 个（zero-golden 2 个、差分 11 个），对任何已修复版本零误报；对实际提交的历史 bootstrap.rtl.css 检出 2 个中的 1 个。它在 16 个 LTR 孤岛负例上、以及四个设计系统与三种 RTL 架构下 43 个未改动真实组件上（两种模式）均为零误报（rule-of-three 95% 上界 ≤7%），并在当前 Bulma 1.0.4 中报出一个真实方向性缺陷。相比之下，Stylelint 核心规则在 Bootstrap 的 LTR 构建与正确 RTL 构建上给出完全相同的 1744 条告警，伪本地化检不出镜像缺陷，朴素的像素镜像差分只在针对测试集调阈值后才能达到 F1 0.87。",
    "2610.32118": "生成式 AI 正把软件工程学生的工作从产出制品转向评估与监督 AI 输出，但学生对输出报告了哪些特征、如何在真实工程工作中实施监督，所知甚少。作者分析 145 名一年级软工学生通过结构化 AI 日志记录的 962 轮人机交互，其中 172 次为学生自述的干预，用多维编码框架刻画所识别的输出特征、干预理由、采取的动作及实施方式。结果显示 74.4% 的干预识别出「适配性」问题，仅 16.9% 涉及正确性问题，说明监督更多在判断看似合理的输出是否适合工程任务，而非是否包含明确错误。在可归类的干预中，学生最常修改生成输出（51.0%）或精炼提示（28.2%），两类反应都与工程适配性相关。学生内部分析显示，被视为含轻微瑕疵的输出所对应的评估信心低于被视为完美的输出。",
    "2610.32438": "长期环境 IoT/LPWAN 部署常把来自不同设备的异构数据流混在一起，在分析前并不系统审计各变量的实际覆盖率，同一网络内多种传感器共存时风险更高。本文对 Tour Perret LoRaWAN 数据集（2021 年 6 月—2023 年 6 月、5 台设备、421,937 帧）提出 C++17 处理流水线：集成于抽取阶段的系统覆盖审计显示 CO2 完全缺失（0%）、气压仅由孤立基站模块 Wyres 上报（占语料 4.24%），使最初的四变量联合分析假设失效，分析改为聚焦 4 台 Elsys EMS 传感器在 205,005 帧（95.76%）上联合可用的温度—湿度对。流水线依次做异常检测（修正 Z 分数、孤立森林）、双变量主成分分析、聚类（K-means、DBSCAN）以及由温度与时间预测湿度的多层感知机，其残差用作缓慢漂移检测器。实测温湿相关 r=-0.662，两成分 PCA 的 PC1 占 83.1% 方差，孤立森林检出 2.12% 的多变量异常而单变量 Z 分数一个都未检出，校准后的 DBSCAN 在 13 个簇中隔离 0.17% 噪声，多层感知机取得较高 R²。",
    "2610.32583": "多智能体确定性 GLP（madGLP）把 GLP 程序作为仅通过异步消息传递通信的智能体运行，并假定公平投递：发出的每条消息最终都会被送达。每个智能体运行在个人手机上、以该人的公钥命名。草根平台除网络外不依赖任何全局资源，因此智能体必须跨蓝牙低功耗、局域网以及被 NAT 遮蔽的互联网（经任何人都可运行的会合服务器）互相到达。madGLP 对这样的网络有何要求、网络又对平台有何要求，此前并未被规范。本文规范 madGLP 之下的网络层：凡 GLP 能做的都用 GLP 做，该层只提供 GLP 触及不到的部分——网络协议栈、位置服务、应用证明与密码原语。三种传输底座共用一套接口：PAN 与 LAN 上，智能体广播由密钥与时间槽派生的轮转识别令牌，知道密钥的对端可在接触前认出它而他人无法追踪，是否响应未识别联系由 GLP 按底座设置信任级别；WAN 上会合服务器是运行无头层与 GLP 会合智能体的静态地址主机，负责协调打洞、不中继任何载荷、也不隶属任何社交图。",
    "2610.32648": "基于大模型的编码智能体会提出在执行环境中不可用的动作，例如访问不存在的路径或缺失的包，作者称之为「幻觉工具使用」。对 4398 条智能体轨迹的初步研究显示，此类幻觉普遍且代价高：恢复中位需要多 3 个交互步与 22.4K token。现有框架依赖执行后的被动反馈，浪费运行时资源。由于智能体的执行环境由具体代码库与 harness 组件构成，许多动作前置条件可在执行前抽取并校验。为此作者提出 StateMirror，一个轻量执行前检测器：在 harness 边界拦截动作，通过 AST 与命令分析提取状态谓词，并对活仓库做确定性校验；通过在执行前精确定位环境不匹配，抢先阻断无效动作及其后续恢复循环。在 2508 个动作上评估，StateMirror 检测此类幻觉的精确率 0.940、F1 0.817，比最强 LLM 裁判的 F1 高 35.3%，同时把中位检测时延从 17.73 秒降至 1.50 毫秒且零 token 消耗。",
    "2610.31895": "编码智能体被训练去完成任务，即使环境已使完成不可能，它们仍持续尝试。表明只有外部帮助才能恢复进展的证据通常在数步内即出现，但智能体很少据此行动：它们过度坚持、尝试不该做的绕路、宣称记录并不支持的成攻——作者称之为「证据—行动鸿沟」。为度量它，作者提出 ImpasseBench，在本来可解的修复任务中注入十二类真实环境阻塞，并在每条轨迹中标注已收集证据变得充分的那一步；相对于该步给动作打分，即可把恰当努力、过度坚持与过早移交区分开。在八个前沿模型、19,371 条轨迹上发现：几乎每个需要外援的运行都收集到了充分证据，但仍有三分之一耗尽预算，且检测到的所有不安全请求都出现在该点之后。所幸一个升级工具（对无视该工具的模型则用外部监视器）已能防住大部分此类行为：工具把预算耗尽率从 34.0% 降至 6.7%，监视器使环境恢复后的任务成功率近乎三倍。即便如此，触发的升级还不算有用的移交：工单能可靠指出阻塞点，却常遗漏智能体自身的进展与验证状态。",
    "2610.31712": "移动 GUI 智能体经常执行流程相似的重复任务，复用此前执行可减少冗余的模型推理与执行开销，但用户指令与执行环境的变化可能使此前成功的动作失效。作者把这类变化系统归纳为六个代表类别，并观察到变化未必使整段流程失效：单个转移在与当前任务上下文和界面状态校验一致时仍可复用。据此提出用于选择性轨迹复用的图—文模板：图刻画 UI 状态与动作转移，文本编码任务意图、流程结构与用于可变内容的类型化槽位；「记录—模板—重放」框架从已验证的执行中构建模板，并利用当前指令与实时 UI 状态复用、改写或丢弃单个转移。给定一条执行轨迹，该框架在 AndroidWorld 的五个基座智能体上平均减少约 80% 的推理 token，多数智能体相对纯 LLM 执行获得至少 1.5 倍加速；在 Android 与 HarmonyOS 真机评测中动作复用率达 70.7–79.8%，多数场景保持 2 倍以上加速。",
    "2610.32661": "水质信息物理系统的机器学习研究受数据集限制：真实数据化学质量差，仿真数据又缺少传感噪声与攻击。本文发布 AquaSense-ICS 开放数据集与基准，共登记四部分内容：(i) Raspberry Pi 5 边缘节点在 25.4 小时窗口内记录 8.0 小时数据（覆盖率 26%，TDS 探头与 BME680 环境传感器，1–2 秒采样，23,688 条记录）；(ii) 在 EPANET-MSX 中仿真的 13 节点环网（10 个汇合点、2 个水库、1 个水箱）与六种水质成分；(iii) 参数化网络攻击库（虚假数据注入、重放、拒绝服务、漂移）与无意的传感器故障，带样本级真值；(iv) 增强序列与 TimeGAN 生成序列，以 origin 列标记来源。攻击、故障与水质标签均可追溯到带种子的生成器、文档化规则或仿真输入。作者指出，此类混合数据最常见的评测方式——随机行划分、并由输入特征计算标签——会产生接近完美但无信息量的分数（随机森林 macro-F1=0.9998）；他们改用防泄漏协议：按时间切分、留出攻击类型，而非由标签重建。该协议下，攻击分类没有任何模型超过常数「正常」预测器（macro-F1=0.465），说明常规评测的高分主要来自信息泄漏。",
    "2610.32919": "陈述自动形式化把数学从自然语言译入 Lean 4 等证明助手，模型已能规模化完成。随着证明器变强，正确性负担从证明转移到陈述：形式陈述是否忠实翻译了来源。给定可信的参考形式化，自然的检验是逻辑等价，但它证明得过多——只要库能分别证明 P 与 Q，P↔Q 就平凡成立（可经 P↔True↔Q）；证明器越强，越多无关陈述对通过。此前方法限制证明器并要求每份证明指名另一条陈述。本文提出更有原则的关系 SemantEq：要求每条陈述只能经由一组允许步骤（逻辑重排、用库自带等式改写等）化为另一条；其程序按 Lean 检查的证明项判定，而非按策略脚本。无模型搜索 SemantEq-Eval 在 ProofNetVerif 测试划分上按作者裁定标签达到 100% 精确率与 65.6% 召回，而 BEq+ 为 95.8% 与 61.8%；其 CPU 时间增加 8.9 倍至多多判出三对。语言模型能找到更多证明，但在四种提示中的两种下证明得过多。",
    "2610.32223": "网站与应用部署验证码与反自动化机制，用交互轨迹与时序等行为信号而非仅凭结果区分人机。作者称此类环境为「受防护 GUI 环境」：正确解出验证任务并不足以端到端完成任务，智能体必须把求解器输出转化为被接受的交互，并在时限内根据运行时反馈调整执行。为此提出 SolveBind，一个把分层求解与运行时监督结合的 GUI 智能体框架：分层求解树把验证分解为相互依赖的感知、定位、求解、动作与验证五项能力；运行时监督把动作承诺锚定在工具导出的证据上，随证据到达修正承诺，并在显式恢复预算下调度执行。在九类验证码任务族、九个基座模型上，SolveBind 在八个基座上成功率最高，领先最强基线 13.3–34.5 个百分点；在 AndroidWorld 的六个基座上成功率均为最高。配对的 GPT-5.5 分析中，MobileAgent 在 90 个任务里有 13 个答对但未通过动态验证，SolveBind 解决了其中 7 个。在自动提交设定下，移除绑定使成功率从 82.22% 降到 71.56%，并增加时延与 token 消耗。",
    "2610.32486": "把视觉语言模型用于视频异常检测面临根本约束：其语义推理所需算力与真实视频流的规模不相容。本文提出信号感知自适应融合（SAAF），通过三项创新实现高效零样本异常检测。第一，语义嵌入空间中的双信号自适应采样器：δ 信号以帧间余弦距离捕捉突发事件，漂移信号以相对滚动时序上下文的偏离检测静态与渐变异常，二者以 OR 门控结合基于 EMA 的自适应阈值，无需训练数据即可覆盖各类异常。第二，阈值门控的级联结构：轻量帧级打分在前，仅在置信度表明需要更多上下文时才调用昂贵的视频级时序分析。第三，信号感知加权融合：依据触发帧选择的信号动态调整分数组合。在四个基准上，SAAF 以显著更低的代价取得有竞争力的精度；在免训练零样本方法中，它在 XD-Violence（92.07%）、MSAD（86.70%）与 ShanghaiTech（80.54%）的 AUC-ROC 上刷新最优，前两者还超过有监督基线。",
    "2610.32639": "近年出现大量可编程网络设备与用于编程它们的领域特定语言，但各 DSL 配套的编译基础设施未能跟上，导致编译结果不可靠、开发者体验差。针对这一碎片化生态，本文提出中间表示 Peregrine，把该领域通用的编译功能整合到共享的开源基础设施中。Peregrine 自设计之初就提供形式保证，而非事后补加：语言带形式语义，并配有以 Rocq 编写并证明正确的等价性检查器。实验表明 Peregrine 的表达力足以涵盖用多种先进网络编程语言编写的应用，其等价性检查器可用于验证一系列不可信编译器 pass 的正确性，也有出人意外的用途，例如在可接受的时间内为包分类算法的正确性出具证明。",
    "2610.32362": "临床流程中使用的机器学习模型常在不同患者群体上表现系统性差异，引发公平性与患者安全担忧。传统子群分析只有在元数据丰富且能刻画性能差异来源时才暴露此类差异，而这一条件在实践中很少满足。算法子群发现可从学到的特征表示中识别连贯分组，但真实底层分层未知，使这些方法难以评估，因而子群发现尚未被系统地用于或评估于性能监控。本文的主要目标是评估算法子群发现用于性能监控的效果，考察所发现子群的性能差距与语义连贯性。以 223,228 张胸片上的心脏肥大分类为对象，发现自动发现的子群表现出更大的性能差距（准确率 0.61–0.90），而基于元数据的传统分析为 0.80–0.94；这些子群常可用患者、采集与模型元数据解释。作为概念验证，作者还表明来自学习子群的标注可用于缓解其揭示的偏差。结论是：子群发现是增强临床模型监控的实用而有效的工具。",
    "2610.31984": "WebAssembly 以便携、沙箱化的执行模型为 Web 应用带来接近原生的性能，但其运行时防护机制有限（缺少栈保护金丝雀与地址空间布局随机化），使 Wasm 应用易受传统攻击。本文提出 WADE（WebAssembly 异常检测引擎），检测浏览器端执行的 WebAssembly 应用中的异常运行时行为。WADE 监控在良性条件下采集的函数级执行轨迹，训练 LSTM 网络学习每个应用的正常执行行为；运行期把偏离所学模式的轨迹标记为潜在攻击。与基于签名的方法不同，WADE 构建应用特定的行为模型，无需逐漏洞签名即可检测已知与未知攻击。作者在覆盖十类漏洞的 67 个 WebAssembly 应用数据集上评估 WADE，实现零漏报与 0.42% 的误报率。",
    "2610.31810": "即便经过仔细校对的论文，其证明或所述假设仍可能留下小缺口。本文提出 PaperFormalizer，一条基于 Lean 的智能体流水线，帮助作者在自己论文中发现并补上此类缺口，把论文变成经 Lean 验证的版本。它从 LaTeX 源码出发，把论文转写为陈述依赖图，逐条以自然语言审计其忠实性、歧义与正确性，再基于 Mathlib、可选领域库与作者个人工具包在 Lean 中形式化并证明。由于只有作者知道某条陈述的意图、以及结果中的形式化缺口应如何最佳修补，流水线在陈述存在多种读法时会停下来询问作者；每处修补都以自然语言与 TeX 符号呈现为提案，供作者接受、拒绝或改向；凡可能改变论文主张的决定都留给作者。产出是论文的批注修订版、变更报告，以及每条声明都链接到其所形式化陈述的 Lean 代码。随着更多论文被形式化，作者工具包不断壮大，作者也可共享已验证论文，供在其上继续研究的人复用 Lean 代码。",
    "2610.32337": "在无监督多变量时序异常检测中，局部波动会抬高重建与预测误差，使观测空间的偏差成为不可靠的异常指标；隐空间打分可缓解这一限制。本文把单类多变量时序异常检测重构为「当前点系统状态相容性估计」，提出 TENET（时间点编码网络）：当前点系统状态指目标时间点的隐表示，由输入窗口中各变量的时序上下文构建。TENET 通过时序层检索相对当前点的窗口上下文、以当前点为中心的嵌入编码时间，并把检索到的上下文与当前表示自适应混合来构造该状态。由此，输入窗口不再是被重建、预测、摘要或打分的对象，而是构造隐表示的上下文，该表示用固定的标准正态负对数似然打分。在多个基准数据集上取得当前最优性能；额外实验显示 TENET 在其它单类目标下仍然有效，且优于替换为通用序列编码器的版本，说明其优势来自决策设计而非骨干网络。",
    "2610.32103": "药物研发中的先导物优化须同时改善互相竞争的性质（如提高渗透性、降低毒性），同时限制可能损害活性的骨架改动。C-MORAL 等基于强化学习的后训练通过微调分子语言模型直接优化先导物，但依赖昂贵的任务专用数据集，且多目标优化仍具挑战。作者认为预训练模型可能已包含零样本生成难以高效抵达的有用分子编辑；受零样本生成搜索能力有限的启发，设计高效的 Metropolis–Hastings 搜索以更好地探索提议分布，并提出 ReMedI：把分子语言模型作为基础提议器做推理期对齐。给定先导物与一组多目标任务，模型以当前分子为条件提议编辑，Metropolis–Hastings 修正在性质提升、性质保持与先导物相似性目标下引导逐步编辑。在 C-MuMOInstruct 与 SMDD 两个基准上，该修正使三个骨干的冻结基座模型均有提升，多目标优化成功率显著高于基线；这些搜索轨迹随后可蒸馏进模型。",
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


def merge_abs():
    path = os.path.join(OUT, "abstracts_zh.json")
    data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    before, added = len(data), 0
    for sid, txt in ABS.items():
        if not data.get(sid):
            data[sid] = txt
            added += 1
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("abstracts_zh: %d -> %d (added %d)" % (before, len(data), added))


if __name__ == "__main__":
    merge_summaries()
    merge_abs()
