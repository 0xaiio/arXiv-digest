# -*- coding: utf-8 -*-
"""2026-11-24 批次：本期 24 篇待补论文的双语简介（summaries.json）。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- key 一律 arXiv 短号。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2611.27910": {
        "zh": "业务数据系统既要判断两条记录是否指向同一实体，也要检索那些「决定性属性」隐含在请求里的记录；当智能体据此行动时，两者都需要可审计的理由。稠密向量效果好，但坐标不可解释、无法按语义过滤、新增属性要重编码整个语料。本文提出由「决策列」构造的可解释向量：每一列存一个判定模型对某个自然语言问题的校准答案（是/否/未说明），一条记录的向量就是它在一组有序问题上的答案序列。",
        "en": "Interpretable embeddings are built from decision columns, each holding a decision model's calibrated answer (yes, no, or not stated) to a natural-language question, so a record's vector is its answer pattern; this yields auditable reasons and semantic filtering without re-encoding the corpus when new properties are added.",
    },
    "2611.27895": {
        "zh": "编码智能体越来越多地实现领域专家写下的规则，而这类代码的缺陷是「静默」的：程序照跑，也给出一个看似合理的答案。TEA-Bench-BR 以巴西儿童孤独症（TEA）早筛路径为蓝本：三份结构仿真但内容虚构的量表、一条多专业转诊流程、以及符合国家 RNDS 规范的 FHIR R4 导出，全部用葡萄牙语书写。生成器为每个任务采样参数（144 个任务、6798 条隐藏用例），隐藏用例可杀灭参考实现的全部 1955 个非等价变异体，因此「能跑通」无法伪装成「正确」。",
        "en": "TEA-Bench-BR benchmarks coding agents on the Brazilian autism screening pathway with three structurally realistic instruments, a multi-professional referral flow, and FHIR R4 export under national RNDS profiles, using 144 generated tasks and 6,798 hidden cases that kill all 1,955 non-equivalent mutants of the reference implementation.",
    },
    "2611.27829": {
        "zh": "「氛围编程」把需求分析挤到一边，让未经核验的「先跑起来」假设层层累积，形成标准测试抓不到的复杂缺陷。当可靠的「真值判据」缺席时，作者主张把关注点从正确性验证转向逻辑一致性，并提出差分逻辑分析（DLA）：用逻辑推理在并行与串行的开发流程之间比对，找出内部矛盾。初步仿真显示 DLA 能拦下逻辑漂移——矛盾陈述与未说明的假设。",
        "en": "Differential Logic Analysis (DLA) reframes reliability from correctness verification to logic consistency, using logical inference to detect internal contradictions across parallel and sequential development workflows and thereby intercept logic drift such as contradictory statements and unspecified assumptions.",
    },
    "2611.27663": {
        "zh": "格一致（lattice agreement）是让进程对「可比较」而非「相同」的值达成决定的协调原语。在异步消息传递且存在拜占庭故障时，已有算法要么依赖认证，要么无法同时做到最优容错与对数级响应时间。本文给出一个异步拜占庭格一致算法：在 n>3f 下容忍 f 个拜占庭进程、无需认证、响应时间为 O(log f)。它建立在 Attiya 与 Rachman 的分类树框架之上，替换了其中的共享成分。",
        "en": "An asynchronous Byzantine lattice agreement algorithm tolerates f Byzantine failures among n>3f processes with no authentication and completes in O(log f) response time, built on the classifier-tree framework of Attiya and Rachman.",
    },
    "2611.27596": {
        "zh": "许多长提示共享前缀，复用其缓存的键值可省掉预填充计算；但缓存命中会让首字更早到达，从而泄漏「另一个请求用过同一前缀」这一事实，所以服务商通常只在同一账号内共享缓存。按最小权限原则，连「发包并付费」的权限都不该暴露同账号他人请求的提示内容——这在智能体发送未经审阅的私有数据、经销商把多用户塞进一个账号、凭据被盗时都成立。Isonomy 因此默认逐请求隔离，同时把吞吐维持在接近完全共享的水平。",
        "en": "Isonomy isolates every prefill request from timing side channels by default while retaining nearly full prefix-sharing throughput, motivated by cache-hit timing leaking that another request in the same account used the same prefix.",
    },
    "2611.27473": {
        "zh": "无证书 DAG 共识协议已有相当数量，覆盖部分同步与异步、崩溃/拜占庭/混合故障模型，但每个协议都要从零设计、证明与实现。Dugong 用一个参数化协议把它们统一起来：核心算法 Decider 通过调参即可实现 8 个已有协议，并派生出 4 个新协议。由于 DAG 把吞吐与延迟解耦，Dugong 给出一个清晰的权衡——延迟与对网络、节点故障的容忍度之间的取舍。",
        "en": "Dugong is a single parameterized protocol that unifies uncertified DAG consensus: its Decider core reimplements eight existing protocols and yields four new ones by parameter tuning, exposing an explicit latency versus fault-resilience trade-off.",
    },
    "2611.27255": {
        "zh": "云边部署让资源受限机器人上的双系统视觉语言导航（VLN）可以异步运行，但推理与通信延迟会造成潜在表示错配，进而走错路。既有适配方法复用历史引导，当历史不再适用时无法提供更新的导航信息。AceVLN 是免训练框架，做主动潜在刷新与边缘侧补偿。分析显示与动作相关的错配集中在紧凑的「关键子空间」，可由快系统特征漂移追踪，作者据此提出关键特征漂移熵来刻画导航敏感度。",
        "en": "AceVLN is a training-free framework for asynchronous cloud-edge visual-language navigation that actively refreshes the latent guidance and compensates on the edge, tracking action-relevant mismatch concentrated in a compact Critical Subspace via Critical Feature Drift Entropy.",
    },
    "2611.27196": {
        "zh": "GPU 加速已重塑电子设计自动化，但要进一步改进专家手写的 GPU 工具仍需大量人工。自动化这件事要求编码智能体能同时追踪主机码与设备码上的瓶颈，并守住正确性与设计质量。EDAGoat 是（据作者所知）首个面向该任务的 EDA 感知 GPU 优化智能体：优化增强模式用四个跨项目的 GPU 优化模式引导改写；强制验证模式要求智能体用编辑后的程序对照 EDA 约束做测试，不通过不得交付。",
        "en": "EDAGoat is an EDA-aware agent for project-level GPU optimization whose enhancement mode guides edits with four cross-project optimization patterns and whose mandatory validation mode forces the agent to test edited programs against EDA constraints.",
    },
    "2611.27154": {
        "zh": "代码模型越来越多地在仓库完整历史（每个文件的每个版本）上训练，而不只是一个快照；但去重工具是为快照设计的，它对「历史」做了什么从未被测量。本文在预注册的随机样本上测量：306 个公开仓库、25 个成熟项目、以及 SWE-bench 背后的 12 个仓库。结论是历史高度重复——用文本索引的话说是个「泛基因组」：典型仓库的历史相当于其当前代码的 19 份副本。",
        "en": "Measuring deduplication on code-repository histories over 306 public repositories, 25 mature projects, and the 12 SWE-bench repositories shows a history behaves like a pangenome, with a typical repository holding the equivalent of 19 copies of its current code.",
    },
    "2611.27106": {
        "zh": "LLM 被用于抽取记录、生成 SQL、总结报告、回答政策问题与分派运营工作。在这些软件边界上，输出「可解析」是必要的，但并不等于任务正确。本文给出可复现的基准协议、公开可执行产物，以及一次确证性在线 API 评测，把结构有效性与任务特定正确性分开考察，覆盖 5 类业务工作流任务与 6 种 Python 实现条件：PydanticAI、LangGraph、DSPy、CrewAI、Agno，以及无框架的 SDK 参考实现。",
        "en": "A reproducible benchmark protocol and live API evaluation separate structural validity from task-specific correctness across five business workflow tasks and six Python implementation conditions: PydanticAI, LangGraph, DSPy, CrewAI, Agno, and a framework-free SDK reference.",
    },
    "2611.27094": {
        "zh": "业界正把 LLM 智能体引入银行模型验证，但「智能体辅助 vs 人工」的比较会把来自电子化证据与确定性测试的收益也算到智能体头上。本文提出分阶段架构：不含 LLM 的受控流程 P1 既作兜底，也作单项授权智能体任务 P2 的对照组；配套的归因协议只把「P1 本来报不出的缺陷」记在智能体账上，同时把诱饵误报、多余动作、以及对开发者断言的附和计入成本，无效输出算漏检。",
        "en": "A staged architecture uses an LLM-free controlled workflow as both fallback and control arm, plus an attribution protocol that credits an agent only for faults the controlled workflow does not already report, charging decoy false alarms, unnecessary actions, and endorsed developer assertions.",
    },
    "2611.26980": {
        "zh": "Hermes、OpenClaw、Codex 这类智能体会反复重发不断增长的执行历史，推高 HBM 中共享 KV 缓存的需求。本文说明共享 KV 容量正是智能体服务吞吐的瓶颈；既有的上下文压缩方法看不到全局缓存状态，而运行期 KV 管理器又拿不到工具执行信息。把 token 追溯到其来源工具操作后可发现：后续操作会取代先前操作的输出与相关轮次，据此可把记录下来的最终历史 token 中的 64% 判为可移除候选。Contexture 是与框架、模型无关的实现。",
        "en": "Tracing tokens to the tool operations that produced them shows later operations supersede earlier outputs and turns, making 64% of recorded final-history tokens removal candidates; Contexture exploits this as a harness- and model-agnostic runtime context eviction policy for agent serving.",
    },
    "2611.26942": {
        "zh": "随着智能体在极少人工监督下交付代码，代码评审成了关键的质量控制关口——但它缺少可靠的客观判据：评审质量本身是细微的判断，最终由 PR 作者拍板。既有基准在结构上错位：标注者是第三方评审者（与被评测的机器人同类），而不是真正决定改什么的 PR 作者；它们还依赖小而静态的问题集，工具一更新就得整体重评。CodeReviewBench 据此重新设计。",
        "en": "CodeReviewBench targets the structural misalignment of existing review benchmarks, where annotators are third-party reviewers rather than the PR authors who decide what to fix, and where small static issue sets must be fully re-evaluated whenever tools change.",
    },
    "2611.26815": {
        "zh": "收敛最后 5%–15% 的代码与功能覆盖率，是芯片流片排期上的主要瓶颈。既有基于 LLM 的覆盖率闭环把未覆盖的 RTL 行或分支直接喂进迭代提示，在工业级子系统上会失败，原因有三：独立查询成千上万个相关空洞导致 token 与上下文爆炸；生成的激励违反跨信号不变式、产出「脏」覆盖；以及对结构上不可达的死代码幻觉出不安全的排除声明。ARGUS 以规格为锚做自适应分诊与形式化不变式排除合成。",
        "en": "ARGUS addresses the last 5-15% of coverage closure with specification-grounded adaptive triage and formal invariant exclusion synthesis, avoiding the token explosion, invariant-violating stimulus, and unsafe dead-code exclusion hallucinations of raw-LLM closure loops.",
    },
    "2611.27735": {
        "zh": "把已部署的 5G 核心网迁移到后量子密码很难：现网网元、基础镜像与 TLS 库各按不同节奏升级。本文评估一种由部署侧控制的迁移策略——通过外部部署的「边界密码执行实体」（BCEE）实现混合后量子/传统密钥建立，且不改动参与网元的源码。评测以 Open5GS 的 AMF–NRF 服务化接口为代表场景，对比传统与混合配置，并给出性能与回滚（rollback）结果。",
        "en": "A deployment-controlled migration enables hybrid post-quantum and classical key establishment through externally deployed Boundary Cryptographic Execution Entities without modifying network-function source code, evaluated on the Open5GS AMF-NRF service-based interface with performance and rollback results.",
    },
    "2611.27734": {
        "zh": "基础模型智能体正从软件工程走向自主科研，而获取并整合领域知识仍是关键难点；工业界越来越多地用知识图谱与本体构成的语义层来组织异构知识。本文追问：自主智能体能否构造出「有助于解决真实任务」的本体，相对其他知识表示是否有可度量的收益？既有基准把本体正确性与智能体任务成功率分开评，无法回答这个问题。AutoOntologyBench 因此以任务落地为锚来设计。",
        "en": "AutoOntologyBench asks whether autonomous agents can construct ontologies that help them solve real tasks, and whether ontologies measurably beat alternative knowledge representations, instead of evaluating ontology correctness and task success in isolation as prior benchmarks do.",
    },
    "2611.27536": {
        "zh": "要可靠比较连续扩散语言模型（CDLM），既需评模型拟合，也需评生成文本的分布。既有做法两头都不完整：基于似然的评测常报离散负对数似然的一个变分上界，其松弛量足以混淆比较；基于采样的评测习惯把生成困惑度与序列内 unigram 熵拼在一起，而这两个指标在采样器每次都吐出同一段文本时依然好看。Open CDLM 给出面向 CDLM 的基准与库。",
        "en": "Open CDLM is a benchmark and library for continuous diffusion language models that fixes two widely used but incomplete practices: reporting a variational upper bound on discrete negative log-likelihood, and combining generative perplexity with within-sequence unigram entropy, which stays favorable even when a sampler emits identical text on every draw.",
    },
    "2611.27410": {
        "zh": "RAG 系统靠检索到的段落作答，因此用户必须信任那个知识库。本文研究一种攻击者：在由 MITRE ATT&CK 与 CAPEC 构建的网络安全 RAG 中，悄悄把已有段落里的词换成同义词（PWWS、TextFooler）。在经人工复核的 44 题基准上做重复配对实验，并设一份只改版式、不改内容的对照语料：投毒把判定为正确的回答从 0.714 压到 0.555，且损害主要来自「证据丢失与拒答」，而不是编造错误陈述。作者用相对熵与运行期校验来定位被改段落。",
        "en": "Word-substitution poisoning of a cybersecurity RAG knowledge base built from MITRE ATT&CK and CAPEC lowers judged answer correctness from 0.714 to 0.555 on a reviewed 44-question benchmark, with damage coming mostly from lost evidence and refusals rather than false statements; relative entropy and runtime verification localize the edits.",
    },
    "2611.27215": {
        "zh": "商用 AI 生成音频检测器通常用买家无法查验的内部测试集来宣传效果；带私有标签的独立基准更可信。本文报告 Neural Defend 的 ARCAS 基础模型在 Podonos 音频深伪检测基准上的成绩：该榜单在同一个留出集上给商用检测 API 与开源检测器打分，样本为真实语音与当前 TTS、声音克隆系统生成的语音，以六种文件格式提供，标签只有 Podonos 掌握。2026 年 10 月 29 日的发布中，ARCAS 位列第一。",
        "en": "Neural Defend's ARCAS foundation models rank first on the Podonos independent audio deepfake leaderboard in its 29 October 2026 release, which scores commercial APIs and open-source detectors on one held-out set of real and synthesized speech across six file formats with labels held only by Podonos.",
    },
    "2611.26988": {
        "zh": "在信用证（LC）单据审核中，最终结论正确并不说明每一条要求都被审到了。本文因此逐条评估审核要求，并让每条要求「可执行」：由语言模型把信用证中对提单（BL）与商业发票（IV）的要求分解为原子条件与逻辑结构，再由确定性校验器取出指定证据、逐条计算结论，使每次检查都能与金标准编码比对、并追溯到留痕证据。由于 LC 记录涉密，作者只在本地数据上微调一个 9B 解析器。",
        "en": "Letter-of-credit examination is evaluated requirement by requirement: a language model decomposes bill-of-lading and commercial-invoice requirements into atomic conditions and logical structures, and a deterministic verifier retrieves the named evidence and computes each outcome, traceable to logged evidence, using an on-premises 9B parser fine-tuned on confidential records.",
    },
    "2611.26940": {
        "zh": "AI 系统正被部署到安全攸关场景，但既有安全框架多在定义、分类与治理风险，而非给出可在系统整个运行生命周期内持续估计、监测与调控风险的可实现模型。CENTRY 提出一个概率框架，从系统与环境的交互中持续做风险估计与监管，并把 AI 风险建模为来自三个内在源的合成：数据集、硬件可靠性，以及与运行环境相关的因素。",
        "en": "CENTRY is a probabilistic latent-state framework for continually estimating, monitoring, and regulating AI risk over a deployed system's lifetime from its interactions with the environment, modelling risk as arising from three intrinsic sources including datasets and hardware reliability.",
    },
    "2611.26914": {
        "zh": "把生成式智能体部署进企业临床流程，需要在交互延迟约束下同时守住多维安全与合规：不泄漏 HIPAA 保护的健康信息（PHI）、不越出执业范围、保证患者可读性、维护品牌一致性。同步调用云端 LLM 评审器会把网络与解码开销压在关键响应路径上。本文提出多级边缘分诊：把紧凑的一级筛查器与业务同机部署，先在边缘挡掉大部分请求。",
        "en": "Multi-Tier Edge Triage co-locates a compact Tier-1 safety screener with the application at the edge, keeping HIPAA PHI protection, scope-of-practice boundaries, patient-appropriate readability, and brand integrity off the synchronous cloud-LLM critical path.",
    },
    "2611.26805": {
        "zh": "用低秩适配器（LoRA）对基础模型做联邦微调，通常靠平均本地训练的适配器来汇总。在跨设备场景下，参与者数据异构且会异步加入退出，平均并不合适：本地适配器在置换意义下不可辨识，而在差异很大的数据上训练出的适配器求平均可能毫无信息量甚至不稳定。LEAN 用一个简单想法替代平均：服务器维护一个由秩一基对组成的「库」，参与者从中签出随机子集。",
        "en": "LEAN replaces adapter averaging in asynchronous cross-device federated fine-tuning with a server-side library of rank-1 basis pairs that participants check out in random subsets, avoiding the permutation non-identifiability and instability of averaging LoRA adapters trained on dissimilar data.",
    },
    "2611.26717": {
        "zh": "用大模型合成知识图谱这类关系型训练数据，通常一次吐一个结构化对象：每个对象自身合法，但对象之间的关系没有落地。本文研究另一条路线——「以模拟生成」：不去描述一个关系型产物，而是模拟一个能产出它的过程，并把产物当作该过程的因果记录。语言模型智能体提出意图，确定性裁判依据显式世界模型裁决结果，只有当某关系所代表的事件真的发生时才输出该关系，一致性因此成为构造性的。",
        "en": "Generation by simulation synthesizes CTI knowledge graphs by having language-model agents propose intent while a deterministic referee resolves outcomes against an explicit world model, so a relation is emitted only when the event it represents occurs, making coherence constructive rather than validated after the fact.",
    },
}

SUMM["2611.27947"] = {
    "zh": "生成式 AI 带来的变化不仅影响软工岗位数量，也改变「软件工程」本身长什么样；下一代工程师的技能与兴趣、老工程师是否还愿意留在这行，都成了问题。本文研究「用 AI 工具开发」与「传统开发」被感知到的差异，以及这些差异如何被编程年限调制：活动层面，工程师报告与同事讨论技术问题变少、分解变少、查文档变少、用调试器变少，而任务切换变多；体验层面则是深度专注感与对代码和设计的掌控感下降。作者称之为「技艺差异」，与之相对的是写码、重构、修缺陷这类核心产码活动，均值差异很小。这些差异随编程年限放大：在生成式 AI 之前就开始编程的工程师感知到的变化更大。",
    "en": "A survey of how development with AI tools is perceived to differ from traditional development finds reduced peer discussion, decomposition, documentation search, and debugger use, more task switching, and less deep focus and sense of control, while core code-production activities barely differ; the effects are amplified by years of programming experience.",
}

MERGE_NOTE = "2026-11-24 批次：补 24 篇双语简介（另补 2611.27947 供视频使用）。"


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
