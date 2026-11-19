# -*- coding: utf-8 -*-
"""2026-11-19 批次：本期 24 篇待补论文的双语简介（summaries.json）。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- key 一律 arXiv 短号。
- 本轮只补双语简介（摘要全文中译 abstracts_zh 未做）。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2611.22967": {
        "zh": "CodeReel 是免训练执行层，加在编码智能体生成视频的「构建-检查-编辑」循环之后。按绘制命令为帧建立精确键，命中即复用（时间平移与编辑场景内的旧帧同样可用）；阻塞感知调度先跑检查、渲染以空闲优先级并行启动。EditLoop 基准上等待较热重建管线降 36.3%、较顺序管线降 57.9%；真实智能体中每轮构建等待中位数降至热管线的 0.62 倍，增益跨 5 个模型、2 个框架成立。",
        "en": "CodeReel is a training-free execution layer that speeds the build-inspect-edit loop of video-making coding agents via exact frame reuse keyed by drawing commands and blocking-aware scheduling, cutting agent wait by 36.3% over a warm rebuild pipeline and 57.9% over sequential builds, holding across five models and two frameworks.",
    },
    "2611.22663": {
        "zh": "弱内存鲁棒性判定此前对每个内存模型都要单独证明 PSPACE 成员资格。本文证明统一元定理：对任何前缀封闭、可用带测试 Kleene 代数（KAT）定义的内存模型，鲁棒性判定都在 PSPACE 内——一举覆盖 TSO、PSO、Release/Acquire 等既有结果，并把完整 RC11 与 OCaml 内存模型首次纳入。正确性已在 Lean 中形式化；另证明去掉前缀封闭后不可判定（KAT 可定义的 Relaxed 模型），并实现原型 RoboKAT 检查 9 个内存模型。",
        "en": "A unifying metatheorem shows robustness against any prefix-closed, KAT-definable memory model is in PSPACE, recovering prior results for TSO/PSO/Release-Acquire and covering full RC11 and the OCaml model; correctness is formalized in Lean, undecidability without prefix-closedness is proved, and the prototype RoboKAT checks nine memory models.",
    },
    "2611.22631": {
        "zh": "研究轮转调度下 n 个匿名、健忘平面机器人的确定性聚集，其中 f 个为拜占庭机器人、局部坐标系可在激活间被敌手改变。分析极简算法 ToMax：移动到重数最大的点，仅当自己处于唯一最大点时保持不动。证明 ToMax 在 f ≤ ⌊√n/2⌋ 时完成聚集，并给出可达拜占庭韧性的 Ω(√n) 下界。",
        "en": "Under round-robin scheduling with rigid movement, the simple ToMax algorithm deterministically gathers n anonymous oblivious robots in the plane whenever f ≤ ⌊√n/2⌋ of them are Byzantine, establishing an Ω(√n) lower bound on achievable Byzantine resilience.",
    },
    "2611.22613": {
        "zh": "为 Isabelle 代码生成器新增 Python 后端，让经证明的算法进入 Python 生态：既可直接用于 Python 应用，也可作为差分测试既有 Python 库的验证参照，不离开 Python 生态即可使用验证实现。用覆盖 HOL 库大部分内容的回归套件验证，并把六个经证明的数据结构与算法对照主流 Python 库测试；生成代码慢于手写库，但适合充当验证参照。",
        "en": "A Python backend for Isabelle's code generator brings verified algorithms into the Python ecosystem, usable directly or as verified references for differential testing of established libraries; validated on HOL regression suites and six verified data structures and algorithms.",
    },
    "2611.22474": {
        "zh": "精确 k-NN 向量检索会被浮点舍入与溢出悄悄带偏，返回数学上错误的 top-k。Errpedia 是专测数值正确性的数据集：21 类错误、1,616 条查询，真值用精确有理数算术独立核验。实测 20 个主流库/数据库配置，每个配置至少在 1 条适用查询上返回错误 top-10，包括漏掉全部 10 个精确匹配、返回不足 k 个邻居等失效模式。",
        "en": "Errpedia is a 1,616-query, 21-category dataset with ground truth independently verified via exact rational arithmetic for testing numerical correctness of exact k-NN vector search; all 20 tested library and database configurations return mathematically incorrect top-10 results on at least one applicable query.",
    },
    "2611.22403": {
        "zh": "BehaVerify 是行为树与神经符号行为树的验证工具箱：用带形式语法与语义的 DSL 描述行为树，语言内置 LTL/CTL 规约；经 fastforwarding 高效编码到 nuXmv 快速判定规约是否成立，并能生成 Python/Haskell 实现、接入 PyTrees 与 ROS，已在多个自主机器人系统上部署（含运行时监视器验证）。开源，本文聚焦工具箱的使用、功能与实现。",
        "en": "BehaVerify is an open-source toolbox for verifying behavior trees and neuro-symbolic BTs: a formally specified DSL with LTL/CTL, an efficient fastforwarding encoding into nuXmv, and Python/Haskell generation integrated with PyTrees and ROS, deployed on autonomous robotic systems including runtime monitor verification.",
    },
    "2611.22401": {
        "zh": "RyBench 是面向发布/订阅中间件的运行时验证（RV）基准框架：以合成事件发布器替代被监控系统，统一测量监控吞吐与判定延迟。框架把事件生成、序列化、传输拆成独立组件，可自由组合不同策略与格式；用 OSI 模式与 Timescales 属性评估各配置吞吐，并以 Reelay 应用与 MonPoly 集成展示端到端基准流程。",
        "en": "RyBench is a pub/sub benchmarking framework acting as a synthetic event publisher to measure monitoring throughput and verdict latency of runtime verification tools, with pluggable generation, serialization and transport components, demonstrated via Reelay and an integration with MonPoly.",
    },
    "2611.22397": {
        "zh": "经典 Petri 网语义过简、高层形式化又过于专门，再加状态爆炸，使 Petri 网难以走出学界。本文提出带数据感知变迁与令牌的解释 Petri 网形式模型，把实现相关的行为与经典语义分离，保留简单触发语义与模型检验能力的同时贴合真实系统；配套轻量工具做数据感知状态空间探索，并以工业巡检机器人完整任务对比经典语义与新语义下的仿真和模型检验结果。",
        "en": "Interpreted Petri nets with data-aware transitions and tokens strike a middle ground between the overly simple classical formalism and overly specialized high-level ones, keeping simple firing semantics and model checking while reflecting real system behavior; showcased on a complete industrial robot inspection mission.",
    },
    "2611.22394": {
        "zh": "用 COMPASTA（ESA TASTE 之上的模型驱动设计工具）分析 ROSACE 飞控基准的运行时韧性：加入基于三模冗余的 FDIR（故障检测、识别与恢复）组件，构造含故障与含 FDIR 的形式模型并注入故障，按用户定义覆盖率自动生成并执行测试用例，分析对系统实时性质的影响；形式模型与仿真用的 Simulink 模型耦合。",
        "en": "Using COMPASTA on top of ESA's TASTE, the ROSACE flight-control benchmark is extended with a triple-modular-redundancy FDIR component; fault injection and coverage-driven test automation support formal analysis of runtime resilience, coupled with the Simulink models used for simulation.",
    },
    "2611.22333": {
        "zh": "MoL-SQL 是混合语言 Text-to-SQL 基准：问题、模式、存储值三者语言可独立切换而任务不变，每条跨语言实体映射按四级难度评分。统一对齐管线迁移五个不同领域/源语言的基准，得到 MoL-Full（16,892 样本）与覆盖所有语言组合的 MoL-Cube（3,840 样本）。8 个 LLM 实验显示模式与值语言影响各异，存储值最多损失 23 分，症结在跨语言实体映射；问题翻译与额外推理都不缩差距，让模型看到目标库的值才显著缩小——混合语言 Text-to-SQL 最受益于语言感知的上下文落地。",
        "en": "MoL-SQL independently switches the languages of question, schema and stored values while keeping each task fixed, grading every cross-lingual entity mapping at four difficulty levels; experiments with 8 LLMs show stored values cost up to 23 points, and access to target-database values substantially narrows the gap.",
    },
    "2611.22323": {
        "zh": "提议把可观测的智能体轨迹当作软件质量保证的证据：与软件/智能体规约及 AI 生成产物一并分析，用于圈定值得审查的关键决策、追溯其对软件问题的可能贡献、并反哺规约与开发实践改进。工业经验支持动机，执行记录与初步分析方法使其可行；作者坦承轨迹本身不能证明决策合理，讨论了它何时够用、何时更简单的 QA 已足，并列举需求工程、验证、因果推断等视角的开放问题。",
        "en": "A position paper proposing agent trajectories—analyzed alongside software and agent specifications and AI-generated artifacts—as evidence for targeted quality assurance: prioritizing consequential decisions for scrutiny, while acknowledging limits and when simpler QA approaches suffice.",
    },
    "2611.22291": {
        "zh": "综述「物理世界的智能体」这一新兴方向：为机器人、实验室、工业控制器写程序的编码智能体没有现成测试套件，程序对错要靠真机、物理仿真或训练出的策略判定。按「如何写、如何测、如何学」组织：物理试验的成本，轨迹、学习型裁判、仿真器与形式检查能替代什么，以及安全要求如何超出任务成功本身。结论：写程序越来越便宜而可信证据仍昂贵，进展取决于物理世界的持续集成。",
        "en": "A survey of agentic intelligence for the physical world treating the world as the program's test suite: how agents write robot programs, how physical trials, learned judges, simulators and formal checks substitute for missing test suites, and why progress depends on a physical counterpart of continuous integration.",
    },
    "2611.22171": {
        "zh": "代码沙箱启动慢的根因是难以构造既紧凑又覆盖多样智能体生成代码的预热快照。Readie 改学一组启动快照：每个快照小、初始化快、只覆盖一部分代码，合起来覆盖大多数工作负载；把快照集合构造形式化为优化问题并用近似算法求解。在 15K 公开+LLM 合成脚本上规划，相同存储预算下启动延迟降 3–22 倍、端到端运行时降 1.3–3.3 倍。",
        "en": "Readie learns a set of small, fast-initializing startup snapshots that together cover most agent-generated code, formulated as an optimization problem solved with an approximation algorithm; at equal storage budget it cuts startup latency 3-22x and end-to-end runtime 1.3-3.3x.",
    },
    "2611.21797": {
        "zh": "基准测试三个主流编码智能体（各配原生前沿模型、高推理档）写测试与跨语言转译测试的能力：智能体测试套件在覆盖率等传统指标上远超人类写的，但优势不均——项目越大质量下滑越明显，且不少优势只是「写得更多」；跨语言测试转译总量看似强，实则不一致、不可靠。",
        "en": "Benchmarking three popular coding agents with native frontier models shows their test suites far exceed human-written ones on coverage, but quality degrades sharply with project size and much of the edge is sheer test count; agentic cross-language test translation remains inconsistent and unreliable.",
    },
    "2611.23228": {
        "zh": "混合架构 VLM（注意力+GDN 等线性递归层）维护视频滑窗很贵：递归层把历史压进共享状态，过期旧帧通常要整窗重放。Spool 观察到递归更新对状态是仿射的，遂免训练地缓存每帧的状态变换并随窗口推进做结合性复合，无需重放即可把过期帧从各递归层状态中精确移除；专用数据结构与 GPU 内核压低开销。5 个开源混合 VLM × 4 个视频推理基准共 20 组测试，p95 首 token 延迟全部最低（几何平均快 6.6 倍），准确率平均 +2.3 分。",
        "en": "Spool is a training-free framework that caches per-frame state transformations and composes them associatively to remove expired frames from recurrent-layer states without replaying; across 20 model-benchmark tests it achieves the lowest p95 time-to-first-token (6.6x geometric-mean speedup) plus a 2.3-point average accuracy gain.",
    },
    "2611.23074": {
        "zh": "VFM 是树注意力验证器：编码共享上下文与目标文本后并行给 N 条自然语言判据打分，逐条给出满足/违反/不适用三元判定。先在 394K 元组、321K+ 条判据的 CriteriaBank 上预训练；微调后的 VFM-4B 在治理基准上超过 GPT-5.4，在 DynaBench 上轨迹级失败检测优于 DynaGuard-4B，并能定位被违反的规则、支持升级到更大模型重点复核。单张 H100 上 4K 上下文、1000 条判据 2 秒内评完、显存 <11GB，适合运行时验证。",
        "en": "VFM is a tree-attention verifier scoring N natural-language criteria in parallel with per-criterion ternary verdicts, pretrained on the 394K-tuple CriteriaBank; finetuned VFM-4B beats GPT-5.4 on a governance benchmark and evaluates 1,000 criteria against 4K-token context in under 2s on one H100 at <11 GB VRAM.",
    },
    "2611.22591": {
        "zh": "GUI 智能体常见「计划对、动作错」的执行鸿沟：结果监督 RL 把负优势广播到所有生成 token，会把正确规划连坐惩罚。PACT 用参考动作定位执行鸿沟：对已验证计划的 token 区间屏蔽负策略梯度贡献（计划保护），再以停梯度偏好代理让参考动作胜过错误动作（动作修复），不改原始标量动作奖励。AndroidWorld 成功率 60.34%→68.97%（+8.63 分），AndroidControl High 一致性 +6.03 分，OSWorld 桌面 +3.25 分。",
        "en": "PACT combines reference-aligned plan protection (masking negative policy-gradient contributions on plan tokens) with plan-aligned action repair to bridge GUI agents' execution gaps, raising AndroidWorld success from 60.34% to 68.97% and improving consistency on AndroidControl High and OSWorld.",
    },
    "2611.22514": {
        "zh": "MM-ReportBench 评「从表格生成多模态报告」：386 个任务、185 张真实表格，参考报告由 MCTS 生成+人工严格质检建成，含标准章节结构与可核验关键洞见。双裁判框架分别评文本（结构完整性、对照源表的数值事实核查、区分真发现与复述的新颖性）与可视化（数据保真、表现力、技术正确性），并评跨模态一致性。20 个 SOTA 模型最强总分仅 68.9，38.5% 报告有数值幻觉，真正新颖的洞见稀少；单裁判评分系统性虚高 8–12 分。",
        "en": "MM-ReportBench evaluates multimodal report generation from tables with 386 tasks over 185 real tables and a dual-judge framework (text + visualization); the best of 20 SOTA models scores only 68.9, numerical hallucination affects 38.5% of reports, and single-judge scoring inflates results by 8-12 points.",
    },
    "2611.22509": {
        "zh": "MIPR 是多模态「意图到商品」检索基准：3,522 条多模态查询 + 30,731 商品共享库，特点是推理密集、一个意图可由多品类商品满足、相关标签细粒度。最佳嵌入检索器全量 nDCG@10 仅 49.23%，多品类查询的解品类 recall@10 为 55.86%；重排升至 60.11%/67.00%，但距候选池上界仍有大差距，是具挑战性与诊断价值的基准（数据与代码已公开）。",
        "en": "MIPR is a multimodal intent-to-product retrieval benchmark of 3,522 queries and 30,731 products featuring reasoning-intensive, multi-category intents and fine-grained relevance labels; the best retriever reaches 49.23% nDCG@10, improved to 60.11% with reranking, leaving large oracle gaps.",
    },
    "2611.22490": {
        "zh": "SciWorkBench 评「智能体能否像科学家一样完成项目」：任务来自同行评审文献或专家贡献的真实科研场景，覆盖生物、化学、材料、物理；提出经领域专家校验的统一科学分析框架给任务归类。在 Claude Code 与 Codex 框架下统一执行与评分，最强智能体平均 57.38 分；失败分析归纳三个工作流级弱点：科学知识难转成任务特定步骤、跨模态证据整合弱、科学性自我纠错不足。",
        "en": "SciWorkBench evaluates agents on real scientific workflows across biology, chemistry, materials science and physics under a unified execution and grading protocol; the best agent averages 57.38, with recurring weaknesses in translating knowledge into task-specific procedures, cross-modal evidence integration, and scientific self-correction.",
    },
    "2611.22408": {
        "zh": "研究预览：把「威胁目录→可检验攻击者模型」的人工流程机械化。攻击树每片叶子映射到 CAPEC 攻击模式并写成「攻击者前提蕴含攻击效果」的一阶逻辑规则；把规则绑定到具体系统部件后，可从绑定模式导出攻击者模型、把效果变成时序逻辑性质，分别在有/无对抗措施下用模型检验器检查，报告能击败该攻击的安全控制。并探讨 CAPEC 支持机器人安全推理的方式。",
        "en": "A research preview mechanising the path from threat catalogue to checkable attacker model: CAPEC attack patterns become first-order rules bound to system parts, from which an attacker model and temporal-logic properties are derived and model-checked with and without countermeasures, reporting the control that defeats the attack.",
    },
    "2611.22404": {
        "zh": "概率时间自动机（PTA）验证的难点在于同一符号状态（位置+时钟区域）内最优行为并不一致，PRISM 最强方法靠不断切分区域并重建入边，把性质根本不依赖的区域也切了。SYMAR 改让值函数符号化：每个符号状态携带「时钟子区域→概率界」的函数，精化只是新子区域出现，已生成状态不切分、入边不重建；启发式前向搜索沿最有希望的行为扩展 And-Or 图，把精力限制在性质相关片段，部分精化备份控制子区域的组合爆炸。",
        "en": "SYMAR makes the value function symbolic in probabilistic timed automata verification: refinement is the appearance of new clock sub-regions without splitting existing states or rebuilding transitions, with heuristic forward search on an And-Or graph confining effort to the property-relevant fragment.",
    },
    "2611.21975": {
        "zh": "PathoDraw 是带病灶的脑 MRI 生成模型：先按「健康解剖→病灶」条件分布把病灶画进标签图，再做对比度无关渲染；单个 3D UNet 直接学习病灶下的健康标签与有符号强度偏差，经稳健组织统计与习得特征识别病灶，全程未用真实病理数据训练。在公开卒中/肿瘤/白质高信号数据集与临床存档数据上零样本检测，跨 T1w/FLAIR/T2w 与多种分辨率，优于或媲美真实扫描训练的对比度专属检测器；同一生成器还可训练超分辨与带病灶配准。",
        "en": "PathoDraw is a generative model of brain MRI with pathology that draws lesions into label maps before contrast-agnostic rendering; a single 3D UNet trained without real pathology achieves zero-shot detection across stroke, tumor and WMH datasets, matching or beating contrast-specific detectors, and also trains super-resolution and registration networks.",
    },
    "2611.21679": {
        "zh": "形式上下文协议（FCP）：当 LLM 既写产物又写测试时，测试通过是弱证据。FCP 对照「请求本身」检查 AI 产物，把一致性（产物是否满足需求的一个形式读法？由模型检查器/SMT 判定）与保真（该读法是否符合散文原意？无判定过程但可被具体见证驳倒）分开；证明可能虚假认证需求的八种方式各变成一个机械检查。四个硬件设计上，信任 AI 断言会认证 23% 被违反的需求，FCP 认证 0；十个代码任务上三个 LLM 全都「过自己的测试、违反请求」，模型/读法/测试间的一致并不蕴含正确。",
        "en": "The Formal Context Protocol checks AI-generated artifacts against the request itself, separating conformance (decided by model checkers/SMT) from fidelity (refutable by concrete witnesses); on four hardware designs trusting AI-written assertions certified 23% of violated requirements while FCP certified none, and on ten code tasks all three LLMs passed their own tests while violating the request.",
    },
}

MERGE_NOTE = "2026-11-19 批次：补 24 篇双语简介。"


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
