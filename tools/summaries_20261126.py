# -*- coding: utf-8 -*-
"""补齐 20261126 期 14 篇推荐的双语简介（summaries.json，value = {en, zh}）。"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "output", "summaries.json")

DATA = {
    "2611.32032": {
        "en": "PIEQ keeps every language model strictly outside the trusted computing base: diagnostic preconditions are certified by disjoint physical failure domains and mutations are gated across all unrefuted fault worlds, falling back to read-only probes under ambiguity. Formal guarantees, etcd fault suites and a live PostgreSQL/Patroni cluster yield zero unsafe admissions.",
        "zh": "把大模型整体移出可信基：诊断前提由互不相交的物理故障域出证，变更要对所有未被推翻的故障世界都安全才放行，证据不足退回只读诊断。etcd 故障套件与 PostgreSQL/Patroni 实测零不安全放行、零假前提提交。",
    },
    "2611.32868": {
        "en": "Proves that a deadline-bounded distributed runtime monitor cannot be simultaneously sound, decisive and available when evidence can be suppressed, so monitors must be able to abstain; implements the mechanisms in a three-tier MQTT/NATS JetStream architecture and validates them on an LLM-planned robot swarm.",
        "zh": "证明证据可被扣押时，截止时间受限的分布式运行时监控不可能同时健全、果断、可用，因此监控必须允许弃权；用序号与周期报告识别缺失事件、静默流依赖时间假设，并在 MQTT/NATS 三层架构与机器人集群上验证。",
    },
    "2611.32440": {
        "en": "Joule models the coupling between energy, sustained frequency and runtime for tensor-core kernels under a power cap, deriving a power-aware speed of light; on B200 it predicts energy within 0.69% mean error and beats exhaustively tuned cuBLAS by 4.94% geometric mean across 60 dense-layer shapes.",
        "zh": "把功耗帽下能耗、持续频率与运行时间耦合建模，导出功耗感知的速度上限；B200 上能耗预测平均误差 0.69%，60 种稠密层形状的 GEMM 几何平均比穷举选优的 cuBLAS 快 4.94%。",
    },
    "2611.32973": {
        "en": "SpecEngineeringBench removes issue descriptions and designated test entry points across 100 instances from 78 Python repositories, forcing agents to decide what to test; seven frontier agents reach 91.47% head pass rate but only 26.36% fail-to-pass, with localization recall dropping from 78.11% (file) to 51.29% (function).",
        "zh": "100 个实例取自 78 个开源 Python 仓库，且不给问题描述与测试入口，逼智能体自己决定测什么、去哪查；七个前沿智能体头部通过率 91.47%，但失败转通过率仅 26.36%，函数级定位召回从文件级 78.11% 掉到 51.29%。",
    },
    "2611.32636": {
        "en": "Derives property-based regression tests from multipath symbolic execution: each path semantics (path condition, symbolic return value, state-change map) induces a Hoare triple compiled into an executable property. The Java implementation scores 63.8% mutation on EqBench versus 55.2% for EvoSuite.",
        "zh": "用多路径符号执行为每条路径记录路径条件、符号返回值与状态变更表，诱导 Hoare 三元组并编译成可执行性质测试；Java 实现在 EqBench 上变异得分 63.8%，高于 EvoSuite 的 55.2% 与 Teralizer 的 60.3%。",
    },
    "2611.32217": {
        "en": "Vx makes machine declarations, memory spaces and links part of the program text, treats the signature as the whole contract callers see, and checks ownership, borrow, race and placement in safe code; function bodies can be checked in parallel with results independent of thread count.",
        "zh": "把机器声明、内存空间与链路写进程序文本，函数签名即调用者可见的全部契约；安全代码自动做所有权、借用、竞争与放置检查，函数体可并行检查且输出与线程数无关。",
    },
    "2611.32676": {
        "en": "Combines 914 GitHub commits explicitly attributing fixes to AI-generated code, 299 developer-AI conversations containing code and mistake signals, and 20 practitioner interviews to derive a taxonomy of 87 developer-attributed quality issues for review and testing.",
        "zh": "三路取证——914 个明确归因于 AI 代码的修复提交、299 段含代码与错误信号的开发者对话、20 位从业者访谈——归纳出 87 类开发者归因的质量问题，可直接用于排定评审清单与测试优先级。",
    },
    "2611.32234": {
        "en": "An operational game semantics for call-by-value concurrent higher-order languages with first-order store: visibility is adapted to concurrency, a complete-trace preorder is proved sound for contextual preorder, and completeness is established for the fragment where functions return first-order values.",
        "zh": "为带一阶存储的并发高阶语言提出操作博弈语义，把可见性概念搬到并发场景，并为线程依赖引入树状结构；完整迹前序对上下文前序健全，在函数只返回一阶值的子集上进一步证得完备。",
    },
    "2611.32946": {
        "en": "ShellBench draws 100 everyday tasks from over 10 million user requests, with 53,100 rollouts over 12 models, 5 harnesses and 3 reasoning levels: model choice matters more than harness, yet the top three models differ by only 1.1 percentage points and harnesses span just 42.9 to 45.2 pass@1.",
        "zh": "从千万级真实请求中取 100 个日常任务，跑 12 个模型 × 5 套框架 × 3 档推理共 53100 次 rollout：模型选择比框架影响更大，但前三名模型仅差 1.1 个百分点，各框架 pass@1 只在 42.9 到 45.2 之间。",
    },
    "2611.32894": {
        "en": "Uses alert decisions as the correctness criterion for lossy compression of monitoring series: for PromQL threshold rules over last, avg/sum/min/max_over_time and rate it derives a per-sample sound error budget computable in linear time, preserving the exact alert-state sequence at any evaluation interval and phase.",
        "zh": "以告警决策为正确性判据压缩监控时序：针对 PromQL 的 last、avg/sum/min/max_over_time 与 rate 阈值规则，导出每采样点可线性时间计算的可靠误差预算，保证任意求值间隔与相位下告警状态序列（Inactive/Pending/Firing）与原序列完全一致。",
    },
    "2611.32731": {
        "en": "A thesis that treats energy as a first-class engineering instrument rather than a reporting metric: useful-work semantics define a successful transaction, attribution assigns shared and auxiliary consumption, and objectives bound energy per successful transaction under stated workload conditions.",
        "zh": "主张把能耗做成像 SRE 指标那样的可执行工程工具，而不只是报表：用有效工作语义界定成功事务，把共享与辅助组件的能耗归因到事务，并以「给定负载下每成功事务能耗」作为目标上限。",
    },
    "2611.32668": {
        "en": "Seeds nine defects in each of 47 public design documents, each with a scripted drafting conversation: a fresh reviewer given the conversation detects 94.8% of omitted decisions versus 62.4% for the document alone, and 98.3% of conversation-only requirement violations, while document-visible recall stays equivalent.",
        "zh": "在 47 份公开设计文档中各埋九个缺陷并附上起草对话：拿到对话的新鲜评审者检出 94.8% 的遗漏决策（仅给文档为 62.4%），并检出 98.3% 的「只存在于对话里」的需求违背；对文档可见缺陷召回基本持平。",
    },
    "2611.32517": {
        "en": "A Wi-Fi edge-AI framework connecting low-power IoT camera nodes to an NVIDIA Jetson Nano: local inference is feasible only for lightweight models at low frame rates, whereas GPU offloading reaches near-real-time for heavier models without 5G or wired backhaul.",
        "zh": "把低功耗 IoT 相机节点经 Wi-Fi 接到 Jetson Nano 的边缘推理框架：节点本地推理只适用于轻量模型与低帧率，把推理卸载到 GPU 才能让复杂模型接近实时，且不依赖 5G 或有线回传。",
    },
    "2611.32480": {
        "en": "VISE revises agent skills without task-specific verifiers by extracting tool capabilities, input requirements, usage conditions and output formats from source code and diffing them against the execution trace; as an extra revision stage it lifts average task success by 9.14-13.35 points.",
        "zh": "不依赖任务专用验证器：从工具源码抽取能力、输入要求、使用条件与输出格式，对照任务请求与执行轨迹找出缺失或冲突步骤，直接给出 SKILL.md 的修改建议；作为附加改写阶段把平均成功率抬高 9.14 到 13.35 个百分点。",
    },
}

s = json.load(io.open(PATH, encoding="utf-8"))
before = len(s)
for k, v in DATA.items():
    s[k] = v
json.dump(s, io.open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("summaries %d -> %d" % (before, len(s)))
