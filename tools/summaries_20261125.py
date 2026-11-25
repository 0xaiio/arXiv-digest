# -*- coding: utf-8 -*-
"""2026-11-25 批次：本期 24 篇待补论文的双语简介（summaries.json）。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- key 一律 arXiv 短号。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2611.31202": {
        "zh": "拜占庭一致协议默认对「谁出故障」做最坏假设，把对手腐化预算 t 与系统的认知不确定性绑死。已有工作证明辅助故障预测能降轮数复杂度，但预测错误不受约束时无法降低通信复杂度。本文开启互补方向的理论研究：当每个进程对自身预测误差有局部保证时，拜占庭一致能受益多少？作者给出算法与匹配下界，量化「局部可预测性」换通信复杂度的收益边界。",
        "en": "This paper initiates the theoretical study of Byzantine Agreement when each process has a local bound on its failure-prediction error, giving algorithms and matching lower bounds that quantify how much communication complexity such local predictability can save.",
    },
    "2611.30815": {
        "zh": "不可靠故障检测器（UFD）是容错分布式系统的基本抽象，但现有 ◇P 类实现的评测环境、负载与 QoS 要求各不相同，选型无据可依。本文系统化整理 14 个 ◇P 及近缘 UFD、实现其中 13 个，并在真实网络轨迹上给出可复用的基准：统一故障注入、负载与 QoS 指标，为共识等上层算法的检测器选型提供实证依据。",
        "en": "The authors systematize 14 diamond-P-style unreliable failure detectors, implement 13 of them, and release a reusable benchmark on real network traces with unified fault injection, workloads, and QoS metrics for principled detector selection.",
    },
    "2611.30776": {
        "zh": "Julia 解决了两语言问题，但不规则、自适应的科学计算负载仍难靠 BSP 模型吃满并行度。Torcalia.jl 是基于 MPI 的异步多任务（AMT）运行时：把计算拆成细粒度任务，按数据依赖动态调度到现代 HPC 的分层架构上，让 Julia 用户在不换语言的前提下获得 AMT 运行时的任务级并行能力。",
        "en": "Torcalia.jl is an MPI-based asynchronous many-task runtime for Julia that decomposes irregular scientific workloads into fine-grained tasks dynamically scheduled across hierarchical HPC architectures.",
    },
    "2611.30713": {
        "zh": "Rust 的安全保证不含免死锁：中断处理路径抢锁触发的死锁尤其隐蔽。难点在于从跨函数边界的 guard 同步用法中恢复「中断敏感」的锁依赖图。本文把中断感知静态分析与诊断引导的智能体审计结合，用轻量源码注解声明各项目的同步语义，在真实 Rust OS 项目中检出既有工具漏报的中断死锁。",
        "en": "The approach combines interrupt-aware static analysis with diagnostic-guided agent auditing, using lightweight source-level annotations to recover interrupt-sensitive lock dependencies across function boundaries and detect deadlocks that existing tools miss in real Rust OS projects.",
    },
    "2611.30455": {
        "zh": "边云协同投机解码让边缘端起草 token、云端共享模型验证，但草稿目标分歧浪费通信，异构客户端的返回时间也难统一调度。CGSpec 用草稿与目标分布的散度自适应调整投机预算，并提出提名-竞争机制在全局增长约束下构造候选树、按重叠感知调度验证窗口，多客户端共享验证器的利用率显著提升。",
        "en": "CGSpec adapts the speculative budget by draft-target divergence and introduces a nomination-and-competition mechanism with overlap-aware verification scheduling for multi-client edge-cloud speculative decoding.",
    },
    "2611.30361": {
        "zh": "Lean 能验证「证明与形式化命题匹配」，但命题是否保留了非形式化原始文献的数学内容，需要另行审查——项目级形式化中这依赖散布在众多声明里的定义与约束。LeanReviewBench 收集 18 个真实 Lean 项目的 197 个版本化输入（87 对齐 / 110 错位），把非形式目标、形式声明与差异描述绑定在一起，评测模型能否发现语义错位。",
        "en": "LeanReviewBench contains 197 versioned inputs from 18 real Lean projects (87 aligned, 110 misaligned), each binding an informal mathematical target to formal declarations and an extracted difference description, to evaluate project-level semantic alignment review.",
    },
    "2611.30202": {
        "zh": "软件工程之外的智能体任务（法律、金融）多为开放式分析，产出难以验证，导致高质量任务只能靠专家手写、难以规模化。VADE 从专业来源构造「可验证的智能体数据」：把开放式分析转化为带结构化答案键的任务，使结果可自动核验，从而把专家级任务数据的获取成本降到可扩展的水平。",
        "en": "VADE is a verifiable agent data engine that converts open-ended professional-domain analysis tasks from expert sources into structured, automatically checkable tasks, making high-quality agent training and evaluation data scalable beyond software engineering.",
    },
    "2611.30021": {
        "zh": "统计结论的可靠性取决于模型、假设、抽样计划与分析方案彼此兼容。StatClaim 是声明式 DSL：研究协议与分析计划被写成程序，对象类型编码其统计角色，编译器做类型兼容检查并用契约校验额外约束；需要验证时，后端在给定假设下用 Lean 构造并检查受支持的统计断言，把「研究设计即类型、协议即程序、统计断言即证明义务」落到实处。",
        "en": "StatClaim is a declarative DSL encoding study designs and analysis plans as typed programs with contracts, whose backend constructs Lean proofs of supported statistical claims under stated assumptions.",
    },
    "2611.30017": {
        "zh": "OWE-Bench 收录 26 个由领域专家撰写的长周期工程任务，覆盖软件工程、物理工程、机器学习与科学计算：从内核优化、飞机设计到定位地震成因故障。每题需要大量领域知识与真实工程量（模型平均耗数亿 token），并在可见用例与隐藏用例上按速度、成本与准确率计分，衡量的是真实世界工程能力而非刷点。",
        "en": "OWE-Bench comprises 26 expert-written long-horizon engineering tasks across software, physical engineering, ML, and scientific computing, scored on speed, cost, and accuracy over both provided and hidden test cases, with models averaging hundreds of millions of tokens per task.",
    },
    "2611.29800": {
        "zh": "安全关键驾驶场景在真实数据里稀少，需主动生成来测试自动驾驶的运动规划器。引导扩散模型中每种场景要单独设计加权目标，且被测车可在攻击起点前察觉攻击者而取消攻击。本文把场景写成带角色类型的信号时序逻辑规约：每个子句声明可改谁、可读谁，被测车在攻击起点前读不到攻击者，再由 LLM 起草规约、优化器执行，生成更公平的攻防场景。",
        "en": "Safety-critical driving scenarios are stated as role-typed signal temporal logic specifications drafted by LLMs, where each clause names which agents it may change or read and the vehicle under test reads the attacker only from attack onset, yielding fairer adversarial scenarios for guided diffusion generation.",
    },
    "2611.29673": {
        "zh": "手游 RPG 的自动战斗是质量保障的关键，要求既像人一样做细粒度实时操作、又不能拖高推理延迟。AutoRPG 把战斗拆成两阶段：高层策略规划定下整体打法的低频决策，底层行为控制做高频精细操作，分层设计兼顾行为可控性与低延迟，在真实手游上验证了非侵入式部署的可行性。",
        "en": "AutoRPG is a systematic AI framework for non-intrusive mobile RPG combat automation that decomposes gameplay into a low-frequency strategic planning stage and a low-latency fine-grained behavioral control stage.",
    },
    "2611.28916": {
        "zh": "组合符号执行（CSE）是程序验证与找缺陷的利器，但既有形式化理论与真实工具之间存在断层。本文在 Rocq 中给出端到端的现实化 CSE 理论：前端支持代数数据类型、逻辑函数与引理等表达力强的规约，后端给出到 SMT-LIB 兼容求解器的已验证连接，把「从规约到 SMT」整条管线形式化打通。",
        "en": "This work develops a realistic, end-to-end theory of compositional symbolic execution in Rocq, supporting an expressive specification frontend with algebraic data types and a verified connection to SMT-LIB compliant solvers.",
    },
    "2611.28704": {
        "zh": "安全分析依赖求解器回答「不可满足」「最优」这类无法靠看模型来检查的结论，而 SAT/SMT 求解器与翻译层都有过健全性缺陷。Zero-Trust Formal Methods 默认不信任任何组件：AI 智能体为不可信求解器构造已验证的检查器，把求解器结论也纳入可验证范围，信任基础从「求解器代码」缩小到「规格说明」。",
        "en": "The framework trusts no component by default: AI agents build verified checkers for untrusted SAT/SMT solvers, shrinking the trusted computing base from solver code to specifications alone.",
    },
    "2611.28617": {
        "zh": "训练会写 Verilog 的 LLM 缺数据：RTL 代码很少公开，现有数据集多只查语法不查功能正确。VeriLadder 构建五级 Verilog 数据集与配套多智能体框架：LLM 智能体撰写并修订规格，综合器与形式等价检查器等 EDA 工具裁决是否接受，分级对齐工程师的真实检查流程，产出工具验证过的指令级正确数据。",
        "en": "VeriLadder builds a five-level Verilog dataset via a multi-agent framework in which LLM agents write and revise specifications and EDA tools (synthesizer, formal equivalence checker) decide acceptance, following an engineer's checks for tool-verified correctness.",
    },
    "2611.31205": {
        "zh": "用一个编码智能体控制整台机器人，会让本可并行的工作互相阻塞。ACAP 把一台机器人组织成常驻智能体团队：每个成员为一个可控组件组（如机械臂+夹爪、躯干+底盘）推理与执行，实现异步；再由一个超智能体协调组件间的物理依赖，让编码智能体在机器人运行期高效并行地构建与修订行为。",
        "en": "ACAP organizes one robot as a team of persistent coding agents, each reasoning and acting for a control group asynchronously, with a hyper-agent coordinating physical dependencies between components.",
    },
    "2611.30766": {
        "zh": "LLM 从自然语言规约生成 RTL 的可靠性与控制逻辑复杂度呈反差：高层描述留白太多，实现关键细节只能靠模型猜。本文提出分层形式引导：用形式化属性作为自然语言与 RTL 之间的中间语义层，逐层把未言明的假设显式化，在复杂时序行为的设计上显著提升生成可靠性与可检查性。",
        "en": "Layered Formal Guidance uses formal properties as an intermediate semantic layer between natural-language specifications and RTL generation, making unstated assumptions explicit and improving reliability on designs with complex control logic.",
    },
    "2611.30555": {
        "zh": "指令跟随的评测常与感知、规划、泛化混在一起，任务成功率高不等于指令保真度高。RoboInF 专测操作策略对指令变化的响应：8 个任务各配 6–12 条经专家验证的指令分支，只在指令维度做对照，直接量化「指令保真度」，暴露那些靠场景泛化刷分的策略在指令维度上的短板。",
        "en": "RoboInF is a benchmark measuring instruction fidelity in robotic manipulation, with 8 tasks each having 6-12 expert-validated instruction branches that isolate behavioral adherence to instruction changes.",
    },
    "2611.30035": {
        "zh": "ESG 标注高度依赖上下文、标签边界模糊、又需要领域专长，直接用 LLM 标注成本与风险都高。TRAE 用多智能体共识做可信自动化标注：多个智能体独立标注后对齐共识，再以置信度评估决定是否需要人工复核，在规模化与可靠性之间给出可量化的取舍，显著降低单位标注成本。",
        "en": "TRAE is a multi-agent ESG annotation framework that reaches consensus across independently annotating agents and assesses confidence to route only uncertain cases to human review.",
    },
    "2611.29903": {
        "zh": "信息物理系统（CPS）互联组件越多，异常检测越重要。本文在 Edge-IIoTset 数据集（保留 222 万条观测、38 个数值特征）上训练深度自编码器：只用正常样本学习模式，以重构误差判定异常。架构 38-24-12-6-12-24-38，阈值按验证集错误率选取，给出可复现的 CPS 异常检测基线。",
        "en": "A deep autoencoder (38-24-12-6-12-24-38) trained exclusively on normal observations detects anomalies in cyber-physical systems via reconstruction error on the Edge-IIoTset dataset with 2,219,201 observations and 38 numerical features.",
    },
    "2611.29847": {
        "zh": "手机 GUI 智能体的运行时护栏通常托管在云端多模态大模型上——每一屏（含支付、消息、医疗记录）都要送远端。MobileGrail 是可端侧部署的护栏模型：以循环任务状态只保留后续安全决策所需的证据，使授权与执行进度可跨上下文延续；学习紧凑的护栏边界，在精准拦截与早介入之间取得平衡。",
        "en": "MobileGrail is an on-device guardrail for mobile GUI agents that maintains a recurrent task state retaining only evidence needed for safety decisions, learning compact guardrails that intervene early without exposing screens to remote servers.",
    },
    "2611.29697": {
        "zh": "事实核查器会因「找不到证据」或「不会用证据」而失败，端到端准确率分不清两者。本文提出沿参考证据从存储到裁决的追踪协议，分离检索、搜索控制、判断与裁决验证四个环节；用同一 9B 开放权重模型在 FEVER、FEVER 2.0 与 AVeriTeC 的 293 条声明上、两种证据条件下评测，定位错误的真实来源。",
        "en": "A diagnostic protocol follows reference evidence from store to verdict, separating retrieval, search control, judgement, and verdict validation, and is applied to 293 claims from FEVER, FEVER 2.0, and AVeriTeC with one open-weights 9B model.",
    },
    "2611.29309": {
        "zh": "多模态大模型数得清自然照片里的物体，却常数不清机械图上的螺栓孔或化学结构里的氮原子：技术图纸目标小、密集、还常被画法约定隐含。CountDrawBench 覆盖平面图、电气原理图、机械图与分子结构，含 1574 道计数题与实例级标注；另提出 Code-Verified Rewards，用可执行代码核验计数推理过程做奖励。",
        "en": "CountDrawBench spans floor plans, electrical schematics, mechanical drawings, and molecular structures with 1,574 counting questions and instance-level annotations, paired with Code-Verified Rewards for counting-based reasoning.",
    },
    "2611.29306": {
        "zh": "自进化智能体把反馈沉淀为记忆或技能，但一次错误批准可能影响后续大量行为；两条更新可给验证器完全相同的证据却导向相反的安全结果，仅凭证据无法区分。DoppelVet 在更新进入持久状态前做对照验证：构造一个与现有验证器信号完全一致的替代更新，从同一状态重放两者、直接对比行为，不需安全标签即可拦截危险更新。",
        "en": "DoppelVet verifies proposed agent updates before they enter persistent state by constructing an alternative matching every signal the verifier uses and replaying both from the same state, distinguishing safety outcomes without access to safety labels.",
    },
    "2611.29147": {
        "zh": "逻辑推理天然提供过程级验证与监督的基础——显式中间推理步骤；但现有学习方法多依赖结果级信号，忽视轨迹内正确性的异质性：正确答案可能含无效推理，错误答案里也可能有有效步骤。VeriLogic 把内部推理轨迹变成显式可验证的监督信号做强化学习，按步骤粒度奖励，提升推理质量而非只对答案。",
        "en": "VeriLogic turns internal reasoning traces into explicit, verifiable process-level supervision for reinforcement learning, rewarding step-wise validity rather than outcome-only signals.",
    },
}

MERGE_NOTE = "2026-11-25 批次：补 24 篇双语简介。"


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
