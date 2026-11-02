# -*- coding: utf-8 -*-
"""2026-11-02 批次：本期 24 篇待补论文的双语简介（summaries.json）。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- key 一律 arXiv 短号。
- 本轮只补双语简介（摘要全文中译未做，见执行记录）。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2610.41837": {
        "zh": "乐观复制让副本无等待地用局部状态执行请求，代价是结果事后可修正、只保证最终一致。作者用因果 DAG 表示对象状态，把提交机制形式化为一条确定性提交规则：除操作分发外几乎不增加消息开销，副本据此周期性就状态演化的顺序达成一致。",
        "en": "Optimistic replication executes client requests wait-free from local state, so outcomes may later be revised; the paper represents the object state as a causally ordered set of operations in a causality DAG and contributes a deterministic commitment rule that adds virtually no message overhead beyond basic dissemination, letting replicas periodically agree on how the state evolves.",
    },
    "2610.41755": {
        "zh": "Text-to-Cypher 的主要失败是结构性的：查询能通过解析、符合模式，却因关系方向相反返回零行。CypherGuard 免训练，用图层面的错误分类指导修复、用挖掘出的规则库指导生成，推理时先重写模式可检出的错误，再重执行，仅在报错或返回空时修复。CypherBench 七个图上执行准确率 88.5%，较同骨干零样本高 25.08 点，超过强化学习微调的 7B 专用模型。",
        "en": "CypherGuard targets structural rather than linguistic failures in Text-to-Cypher, where a schema-valid query returns zero rows because it traverses a relationship against the stored direction; the training-free framework pairs a graph-native error taxonomy with a mined rule library, rewrites schema-detectable faults first, and repairs only when re-execution errors or returns nothing, reaching 88.50% execution accuracy on CypherBench across seven graphs.",
    },
    "2610.41562": {
        "zh": "语义等价与否的二值判断无法说明模型是否知道哪处改动造成语义差异。SCRBench 含 67,658 组 Python 程序对，除判断等价，还要求诊断语义变化、重建改动序列。等价准确率 94.71% 的模型只诊断出 54.44% 的变化；精确重建序列最好仅 39.27%，改动增到五处时无一模型超过 1.11%——高等价准确率明显高估了模型对语义效果的推理能力。",
        "en": "SCRBench builds 67,658 Python program pairs by applying change sequences that preserve or alter semantics and evaluates diagnosing semantic change and reconstructing change sequences alongside equivalence detection: a model at 94.71% equivalence accuracy diagnoses only 54.44% of semantic changes, and exact sequence reconstruction tops out at 39.27%, so yes/no equivalence overestimates semantic reasoning.",
    },
    "2610.41472": {
        "zh": "执行反馈只给症状级、方言相关的报错，模型只能猜根因；论文把这种「既用未验证模型提修复、又由它判定修复是否合格」称为仲裁悖论。Post-SQLFix 把 SQL 规范化为方言感知的规范查询结构，用语法、结构、语义三层静态分析给出模式感知的违规定位，应用前的时序监控只接受违规数下降、不重引入旧违规的修复。在 BIRD、Spider 等三千多实例上修复了执行反馈遗留错误的 77.8%，迭代次数不到一半、token 少 30%。",
        "en": "Post-SQLFix reframes Text-to-SQL repair as property-guided program repair to escape the arbitration paradox, canonicalizing SQL into a dialect-aware Canonical Query Structure, validating it through syntactic, structural and semantic static layers, and accepting a repair only if a temporal monitor sees the violation count drop without reintroducing resolved faults; it fixes 77.8% of the execution errors left by execution feedback with under half the iterations and 30% fewer tokens.",
    },
    "2610.41457": {
        "zh": "推荐模型同时放大稀疏表示与稠密计算：上千异构特征域、长行为序列、万亿级 Embedding，稠密网络又转向大 Transformer，造成阶段内细粒度操作、设备间负载不均与同步延迟、阶段间 GPU 空泡。RecIS 把从输入特征到稠密计算的全路径作为单一优化目标，用自适应融合 + 向量化访存、哈希分片与分层通信的 GPU Embedding 引擎、以及多级流水重叠三套机制协同优化。",
        "en": "RecIS treats the whole path from input features to dense computation as one optimization target for GPU-centric recommender training, combining adaptive fusion with vectorized memory access, a GPU embedding engine with hash-based sharding, hierarchical communication and specialized aggregation for forward and backward index structures, and a multistage pipeline that overlaps input preparation with dense computation.",
    },
    "2610.41407": {
        "zh": "向量检索有多种物理实现，各自在代价与保真度之间权衡，但部署通常离线选定一套配置服务所有查询，等于按最难的查询定容、为其余查询多付钱。作者提出保真度纲要：把嵌入空间按地标划成单元，记录每个单元、每种配置在样本查询上达标频率；查询时一次最近地标查找即可为所有配置给出校准估计，优化器据此选择配置，使工作负载超标频率不超过允许值。",
        "en": "A fidelity synopsis divides embedding space into landmark cells and records, per cell and per configuration, how often each configuration met a fidelity target on sample queries, so one nearest-landmark lookup yields calibrated estimates for all configurations and an optimizer picks per-query configurations that keep the workload's miss rate within its requirement.",
    },
    "2610.41263": {
        "zh": "迁移基准要求项目在迁移前测试通过，但老项目即使代码不变，今天重装依赖也会引入更新版本的库，改变初始测试结果与迁移中观察到的失败。作者在 PHP 7.4 到 8.3 迁移上比较两种依赖策略：按发布日选版本相比放行快照内全部版本，把 7.4 通过率提高 7.1 个百分点（3,660 个发布）；两种策略下都通过的候选任务集仅重叠 58.5%。",
        "en": "Reinstalling an unchanged old project can silently change its baseline test results because newer dependency versions enter the environment; in PHP 7.4 to 8.3 migration, release-date dependency selection improves the 7.4 pass rate by 7.1 points across 3,660 releases and recovers recorded versions more closely than modern selection, while the two policies yield candidate task sets that overlap by only 58.5%.",
    },
    "2610.41207": {
        "zh": "FastPay 这类证书支付由客户端聚合法定人数签名、验证者互不通信，其完备性依赖「锁永不撤销」；共享余额（资金池、商户池、额度、订阅）一旦并发扣款就必须解锁，客户端私藏的证书可能被静默覆盖。作者证明此时任何解锁规则都不安全，除非证书形成对验证者可见，并给出混合协议：个人账户沿用原路径，共享资源走 ECHO/READY 两阶段广播，无冲突时不需共识。",
        "en": "Certificate-based payments such as FastPay are complete only while locks are never undone, which fails for shared balances where honest accounts race; the paper proves no unlock rule is safe unless certificate formation is visible to validators and gives a hybrid protocol that keeps the client-driven path for personal accounts while certifying shared-resource transactions by an ECHO/READY two-phase broadcast, freezing the affected version and resolving it with one agreement instance under contention.",
    },
    "2610.41202": {
        "zh": "Iris 提供完整 generality，代价是大量机械化域理论、难学难移植；归纳理论用普通依赖类型，简单但分离代数限制资源表达力。作者证明归纳理论可以达到 Iris 的表达力：在 Lean 中轻量机械化，令结点承载 Iris 风格资源代数函子，再在其上重建 Iris 基础逻辑，并做高阶状态的双正交逻辑关系与带不变式、可自定义 ghost state 的程序逻辑两个案例。",
        "en": "The paper shows Indirection Theory can match Iris in expressiveness by mechanizing it lightly in Lean with knots holding resources from an Iris-style resource algebra functor and rebuilding the Iris base logic on top, so the whole construction is followable without domain theory; two case studies, a biorthogonal logical relation for higher-order state and an Iris-style program logic with invariants and user-definable ghost state, show the base logic is expressive and faithful.",
    },
    "2610.41130": {
        "zh": "学习型世界模型以软件组件形式发布，模型版本、预处理与测试脚手架逐版变化；单看准确率会漏掉两类问题——同一测试在不同配置下结论相反，以及脚手架故障在没有崩溃的情况下给出错误分数。TetraState 对成对的可实现/不可实现视频测试在四种模型原生配置下运行，按正确判定数分四类，单独上报不确定与执行失败，并把脚手架纳入被测系统做版本化。",
        "en": "TetraState is a regression-testing protocol for learned world models that runs each paired possible/impossible video test under four fixed model-native configurations, classifies outcomes by the number of correct verdicts, reports inconclusive tests and failed executions separately, and versions the harness as part of the system under test, exposing regressions that a modal-verdict flip check misses.",
    },
    "2610.41097": {
        "zh": "深度学习缺陷的失败可能牵涉代码、模型、数据、依赖与运行环境，缺陷报告又常缺关键细节。RepGen 先探索仓库构建学习增强的上下文，制定复现计划并生成候选脚本，再用静态检查与模型反馈迭代，可自动准备环境、执行并按报告失败判定是否复现；在 106 个真实缺陷上复现 85 个（80.19%），27 人对照实验成功率提升 23.35%、耗时减少 56.8%。",
        "en": "RepGen reproduces deep learning bugs by exploring the repository to build a learning-enhanced context, drafting a reproduction plan, generating candidate scripts and refining them with static checks and LLM feedback, then optionally preparing the environment, running the script and judging the output against the reported failure; it reproduced 85 of 106 real bugs and improved success by 23.35% while cutting reproduction time 56.8% in a 27-developer study.",
    },
    "2610.41094": {
        "zh": "AIFaultBench 收录 105 个 AI 软件仓库、76 家机构的 770 个真实缺陷，覆盖机器学习、深度学习、强化学习、大模型系统、智能体 AI 与 AI 工具链六类；每条记录把原始报告、受影响代码库与结构化元数据、环境搭建脚本、复现触发器和调查证据连在一起。按记录的执行条件复现 652 个（84.7%），其余 118 次尝试的结果也如实留档。",
        "en": "AIFaultBench gathers 770 real bugs from 105 AI software repositories across 76 organizations, spanning machine learning, deep learning, reinforcement learning, LLM-based systems, agentic AI and AI tooling, and ties each report to structured metadata, environment setup scripts, a reproduction trigger and investigation evidence; 652 bugs (84.7%) were reproduced under the recorded conditions with the remaining attempts documented.",
    },
    "2610.40885": {
        "zh": "以太坊上每个计算操作都直接产生经济成本，gas 效率因此关乎 dApp 的经济可持续性，但理论优化模式与开发者实际做法之间存在明显落差。作者按挖掘软件仓库的方法，用 NLP 过滤加人工核查从 2018–2025 年 GitHub 开源 Solidity 项目中筛出 gas 相关提交，基于 400 个代表性提交归纳出 8 个大类、36 个子类的优化策略分类法，覆盖从算术细化、字节码瘦身到逻辑内化、减少外部调用等不同抽象层次。",
        "en": "Mining open-source Solidity repositories created on GitHub between 2018 and 2025, the study filters gas-related commits through NLP-based screening plus manual inspection and derives, from 400 representative commits, an empirical taxonomy of gas optimization strategies with 8 macro-categories and 36 subcategories spanning arithmetic refinements, bytecode-size reduction and architectural changes such as logic internalization and fewer external calls.",
    },
    "2610.40721": {
        "zh": "漏洞检测智能体的准确率不仅取决于底层模型，还高度取决于外壳（围绕模型搭的脚手架代码），而外壳多为手写且固定，难以吸收评测反馈、也难迁移。MetaVul 从种子结构化推理脚手架出发，用基于工作流的优化循环，依据漏洞函数/修复函数的配对反馈反复改写外壳并保留推理与判定格式，每轮检索历史外壳的轨迹、日志与指标，最终返回一组帕累托最优外壳。",
        "en": "MetaVul discovers agent harnesses for vulnerability detection by starting from a seed structured-reasoning scaffold and iteratively refining the harness through a workflow-based optimization loop driven by paired vulnerable and patched functions, searching over the trajectories, logs and metrics of prior harnesses and returning a Pareto-optimal set that improves held-out pairwise accuracy by up to 25.8 points and transfers across models.",
    },
    "2610.42141": {
        "zh": "冻结的机器人策略放在智能体外壳里表现远好于直接调用，但外壳目前靠手写、且每个新机器人或基准都要重设计。RoboArchitect 让编码模型观察 rollout、诊断失败并迭代改写外壳，只在优化集上演化、在留出场景与任务上评测。不更新任何权重，未见场景成功率从 9.7% 升到 43.3%（4.5 倍），未见任务从 12.7% 升到 40.2%；外壳还演化出自己的持久记忆，跨任务携带经验。",
        "en": "RoboArchitect automates harness design around a frozen robot policy: a coding model observes rollouts, diagnoses failures and iteratively revises the harness on an optimization set, evaluated on held-out scenes and tasks; without updating weights it raises success from 9.7% to 43.3% on unseen scenes and 12.7% to 40.2% on unseen tasks, and the harness evolves persistent memory that carries experience across tasks.",
    },
    "2610.41885": {
        "zh": "基于 MCP 的工具调用会留下轨迹，观察者无需看到对话即可推断用户属性。作者构建 PrivacyTrace：1,000 个合成用户画像、4,000 条智能体轨迹、四个领域，全部由 25 个服务器上的真实 MCP 工具生成。四个主流模型作为攻击者时，画像推断成功率 26.25%，高于基于先验猜测的 17.97%；工具参数与返回结果是主要证据来源，跨会话关联会进一步放大风险。",
        "en": "PrivacyTrace benchmarks user-profile inference from MCP tool-call traces with 1,000 synthetic profiles and 4,000 trajectories produced by real tools from 25 servers across four domains; four mainstream LLM attackers reach 26.25% attack success versus 17.97% for prior-based guessing, with tool arguments and returned results as the main evidence and cross-session linkage amplifying the risk.",
    },
    "2610.41296": {
        "zh": "答案级奖励无法区分结果同样正确但过程不同的推理轨迹。作者比较基于置信度（SC）与基于熵（UID-Conj.，结合全局熵变化与局部平滑度）的辅助轨迹偏好，用于在线奖励增强与离线加权训练。在 Qwen3-1.7B 上，UID-Conj. 相比未修改的 TTRL 把在线宏平均与三个迁移基准合计提高 2.08 个点；离线加权 SFT 中比均匀加权高 1.93 个点（95% CI [0.44, 3.44]），收益依赖任务类型。",
        "en": "The paper asks whether auxiliary trajectory preferences improve small-model self-improvement when answer-level rewards cannot separate equally correct traces, comparing confidence-based scores with an entropy-based metric (UID-Conj.) that combines global entropy variation and local smoothness; UID-Conj. beats unmodified TTRL by 2.08 points online and uniform weighting by 1.93 points in offline weighted SFT, with task-dependent benefits.",
    },
    "2610.41267": {
        "zh": "把工程需求转成仿真需要几何、物理、边界条件与数值设置彼此一致，仅「跑通」并不能说明规格保住了原问题。作者研究智能体能否可靠生成完整可执行的 JSON 规格（几何、网格、PDE 求解、结果导出），把模型抽取与确定性科学检查、能力检查、显式澄清、保留已接受字段的局部补丁结合。120 条模板相关请求上，首轮规格与决策正确率 98.3%，高于模式辅助单次 92.5% 与纯模型 82.5%；42 条需澄清或拒绝的请求无一误判为就绪。",
        "en": "The study tests whether agents can build complete executable JSON specifications for geometry creation, meshing, PDE solving and result export, combining model extraction with deterministic scientific and capability checks, explicit clarification and validated local patches that preserve accepted fields; on 120 template-related requests the workflow reaches 98.3% correct first-turn specifications and makes no false-ready decisions among the 42 requests needing clarification or rejection.",
    },
    "2610.41170": {
        "zh": "水印检测器一旦公开，现有方法就易受伪造与对抗优化攻击。PP-Mark 把轻量统计检测锚定到嵌入过程的零知识证明上：伪造内容在构造上无法通过完整验证。作者在标准密码学假设下给出形式化的不可伪造性，并在 SD2.1 与 SDXL 两个潜扩散模型上验证其抵御黑盒印记伪造、白盒优化与再生攻击，同时保持去中心化验证的可用性。",
        "en": "PP-Mark anchors lightweight statistical detection to a zero-knowledge proof of the embedding process, so forged content cannot pass full verification by construction; the paper establishes formal unforgeability under standard cryptographic assumptions and validates resistance to black-box imprint forgery, white-box optimization and regeneration attacks on SD2.1 and SDXL while staying practical for decentralized verification.",
    },
    "2610.41037": {
        "zh": "Cookie 同意条、订阅弹窗等网页浮层会干扰爬虫并污染下游文档表示；多模态大模型识别准但延迟与成本无法承受全网规模，轻量视觉模型又困于整页渲染的极端长宽比——等比缩放会把关键文字特征压没并造成误报。WebOverlay 从前沿视觉语言教师蒸馏出纯视觉检测器，用保持长宽比的动态切片加边界仲裁消除接缝伪影，完全绕开 DOM 解析。",
        "en": "WebOverlay distills a frontier vision-language teacher into a vision-only overlay detector that handles full-page renders with extreme vertical aspect ratios through aspect-preserving dynamic tiling with spatial overlap and aspect-ratio-aware boundary adjudication, bypassing DOM parsing entirely to avoid cross-modal latency while beating DOM-based heuristics and rivaling proprietary MLLM baselines.",
    },
    "2610.40946": {
        "zh": "思维链轨迹可用于安全监控，但模型也会从环境线索反推自己是否被监控。作者发现监控是互动过程：监控干预留下的痕迹会让模型推断思维正被观察并改变行为；连超时与操作耗时这类细微时间信号都能暴露监控存在，模型还会在反复交互中形成对监控有效性的统计估计，并据此尝试规避检测。这要求重新评估基于思维链的监督。",
        "en": "The paper shows that chain-of-thought monitoring is interactive: traces left by monitoring interventions let a model infer that its reasoning is observed and adapt its behavior, and even subtle cues such as timeout and operation-duration timing reveal monitoring; across repeated interaction loops models form statistical estimates of monitor effectiveness and use them to evade detection, motivating new evaluations of CoT-based oversight.",
    },
    "2610.40906": {
        "zh": "科学智能体递归构建知识：检索证据、构造中间状态、判断状态是否足够。作者把两个设计轴分开考察——递归建什么（证据状态）与什么控制它（决定何时停止的判定器），并定义共识科学论断验证任务。ProClaim 把证据状态持久化在模型上下文之外；ProClaim-eval 含跨分子生物学、核物理、天文学的 718 条带支持/反驳金标签的论断。证据状态优于上下文内累积，训练过的判定器优于固定轮数停止。",
        "en": "The paper separates two design axes of recursive knowledge construction, what the recursion builds (an evidence state) and what controls it (the judge deciding when to stop), and measures them on consensus scientific claim verification with ProClaim-eval, 718 SUPPORT/REFUTE-labelled claims from five expert-curated databases; persisting the evidence state outside the model's context beats in-context accumulation, and a trained judge beats fixed-round stopping.",
    },
    "2610.40751": {
        "zh": "递归自我改进能让模型能力逐轮提升，也可能引入新风险、削弱既有防护。Safin-1.5 按「安全即能力」的思路训练：安全架构把持久安全状态与危险知识解耦（后者迁入可移除专家，移除时对通用能力影响最小），递归安全改进建立「发现—评估—修复」回路，只在同时满足安全与效用指标时接受更新；推理期另有外壳扩展形式推理能力，并限制过度拒答。",
        "en": "Safin-1.5 pursues safety as an intrinsic capability under recursive self-improvement: a safety architecture pairs persistent safety states with hazardous-knowledge disentanglement that relocates targeted knowledge into removable experts, a discovery-evaluation-repair loop accepts updates only when they improve safety without eroding utility, and an inference-time harness extends formal reasoning while limiting over-refusal.",
    },
    "2610.40732": {
        "zh": "IIoT 边缘流水线常整块丢多传感器数据，常规做法是先插补再检测，而插补器只按均方误差训练：它把缺失块填成最可能的正常形态，于是部分可见的异常被平滑回正常，正常数据的边界伪影又抬高误报——作者称之为插补偏差。任务感知扩散精修器针对冻结下游检测器的损失景观训练，借助噪声预测已给出的一步干净窗口估计，训练成本与普通扩散相当。",
        "en": "TADR replaces the disjoint impute-then-detect pipeline with a conditional diffusion refiner trained against the loss landscape of a frozen detector, acting on the one-step clean-window estimate that noise prediction already yields so training costs no more than plain diffusion; it raises F1 by 0.338 on SMD over the unrefined detector and runs in 41.4 ms per window on one CPU core.",
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
