# -*- coding: utf-8 -*-
"""2026-10-24 批次：本期 14 篇推荐项的双语简介 + 摘要中文译文。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- abstracts_zh.json 的 value 为纯字符串（中文译文）；已存在的不覆盖。
key 一律 arXiv 短号。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2610.30725": {
        "zh": "把 C 程序与其 ACSL 规约当作统一产物联合合成：约束代码暴露证明相关状态、简化控制流，约束规约避免弱化与隐式锚点，让自动验证器真正消解证明义务。",
        "en": "VeriGen-C jointly synthesizes C programs and their ACSL specifications as one artifact, constraining code to expose proof-relevant state and specifications to avoid weakening, so automated verifiers can discharge proof obligations.",
    },
    "2610.30200": {
        "zh": "无参考解时只靠单条推理链判定答案：自我检查的 AUROC 止步 0.741，因为三分之二的错链并未写错等式、只是正确执行了错误计划；把轨迹抽象成程序、扰动一个量再问一次，构成轨迹自带的变异测试。",
        "en": "A reference-free study of verifying a single reasoning trace: self-checking caps at AUROC 0.741 because two thirds of wrong traces contain no false equation, so traces are abstracted into programs, perturbed, and re-queried as self-generated metamorphic tests.",
    },
    "2610.30188": {
        "zh": "以既有实现为规约，要求智能体在给出更快实现的同时交出 Lean 4 中机器检查的等价性证明；Aqueduct 把 C/C++/Go/Rust 迁移为原生 Lean，Verina 的 189 个实现中 156 个获得更快的证明改写。",
        "en": "Agentic verified optimization takes the existing implementation as the specification and requires a Lean 4 machine-checked equivalence proof alongside a faster rewrite; Aqueduct ports C/C++/Go/Rust to Lean, yielding proved speedups on 156 of 189 Verina programs.",
    },
    "2610.30432": {
        "zh": "面向 AI 生成 Python 代码的自动验证框架：先类型检查，再经 Why3 翻译为 WhyML，交由后端自动定理证明器核对规约；十个程序的错误中 50% 源于领域知识缺口、30% 源于语法不准。",
        "en": "TrustedCode verifies AI-generated Python by type-checking, translating to WhyML via Why3, and discharging specifications with backend provers; across ten programs 50% of errors trace to domain-knowledge gaps and 30% to syntactic inaccuracies.",
    },
    "2610.30491": {
        "zh": "审计智能体评估中的轨迹级检测器：在计算器输出被污染的设定下，最终正确性、可见复验与故障传播三类标签系统性分歧，核心失效模式是模型静默改写工具输出且无复验记录；人工复核与自动复验标签仅一致 67/81。",
        "en": "An audit of trace-level detectors in agent evaluation: with corrupted calculator outputs, correctness, visible re-verification and fault propagation disagree systematically, driven by silent tool-output override; human review matches automated verification labels only 67/81.",
    },
    "2610.30792": {
        "zh": "从真实交互轨迹重建可执行应用环境：先把 1570 条轨迹归并为源链接的应用模型，再编译成环境并用独立重放做有界修复；十款应用 200 条工作流端到端复现 91.1%，最强基线 59.8%。",
        "en": "Trace2World rebuilds executable app environments from interaction traces by first reconciling them into a source-linked app model and then compiling an environment repaired via independent replay, reproducing 91.1% of 200 workflows versus 59.8% for the strongest baseline.",
    },
    "2610.31201": {
        "zh": "L4 是面向「可逆语言编译到可逆机器」的通用、线性类型、可逆底层中间语言，用以取代并推广可逆 SSA 形式 RSSA；论文给出形式化类型系统与带方向标记的双向小步语义，方向可在执行中改变。",
        "en": "L4 is a generic, linearly typed, reversible low-level intermediate language meant to replace and generalize reversible SSA, equipped with a formal type system and a bidirectional small-step semantics whose direction can change during execution.",
    },
    "2610.30758": {
        "zh": "考察一线审贷人员能否识别 AI 编辑过的贷款材料：由 47 份真实文档生成 134 份伪造 PDF，三位从业者给出 132 份判断，仅 14 份（10.6%）有编辑证据支撑，且无人凭视觉线索指出真实改动。",
        "en": "An empirical study of whether loan processors and underwriters detect AI-edited statements: three practitioners gave 132 judgements over 134 forged PDFs, only 14 (10.6%) supported by edit evidence, with no visual cue pointing to an actual edit.",
    },
    "2610.31306": {
        "zh": "提出「超级智能软件工程」：智能体能力强于人类工程师后，正确性仍依赖代码之外的决策与契约，知识会衰减，一旦审阅容量固定，读代码能拦下的比例趋零；治理必须随能力扩展，作者以 452 个高星仓库的智能体上下文文件现状与 OSTEON 规范作初步证据。",
        "en": "Superintelligent software engineering argues capability alone cannot deliver correct software: correctness rests on decisions and contracts the code does not carry, knowledge decays, and past a fixed review capacity review catches a vanishing share, so governance must scale with capability.",
    },
    "2610.30877": {
        "zh": "ATLAS 用多智能体把优化后的二进制提升为规范化 LLVM IR：借伪探针归因做区域级样例检索，再由 Lift / Advisor / Validation 三个智能体依据验证器与编译诊断迭代修复，直至通过工具链校验。",
        "en": "ATLAS lifts optimized binaries to canonical LLVM IR with structure-aware region retrieval aligned by pseudo-probe attribution, plus a Lift/Advisor/Validation loop that repairs IR using verifier diagnostics until the toolchain accepts it.",
    },
    "2610.31118": {
        "zh": "把「网站连续性」立为前端智能体评估的第二义务，并发布 ProductWebBench：320 个改动任务与 80 个长程构建任务，冻结仓库快照与确定性检查；8737 次运行中，请求项全过仍有 28.2% 失败于连续性检查。",
        "en": "ProductWebBench scores website continuity alongside task completion on living frontend repositories; across 8,737 runs from 13 models, 28.2% of runs passing every requested-work check still failed a continuity check.",
    },
    "2610.30698": {
        "zh": "研究 LLM 智能体长期记忆中的「治理状态污染」：存储内容与任务不变，只改变哪些记录进入可见上下文；六个提供方 2080 对扰动中 96.25% 改变了有效投影，下游正确率落差达 40.54 个百分点。",
        "en": "A cross-model stress test of governance-state corruption in agent memory: altering which retained records enter context changes the operative projection in 96.25% of 2,080 matched fault pairs, with a 40.54-point downstream correctness gap.",
    },
    "2610.30221": {
        "zh": "提出 AAM/5C 参考模型：五项能力（捕获、理解、选择、协调、控制）横跨七个逻辑层，并用单一授权规则分离提议、决策与执行——规划器提议、治理层签名决策、安全层发放短期行为令牌。",
        "en": "The AAM/5C model organizes five capabilities across seven logical layers and separates proposing, deciding and executing through a single authorization rule, with a probabilistic planner, a signing governance layer and short-lived act tokens.",
    },
    "2610.30425": {
        "zh": "挑战「稀疏检索上图索引不如倒排」的共识：把倒排索引的长处注入图搜索，提出词项入口播种、稀疏草图近似路由、稀疏划分图构建三项技术，合成 GRIP 系统，在 MS MARCO v2 上取得更优的召回—延迟权衡。",
        "en": "GRIP challenges the view that graph ANN indexes are inferior for learned sparse retrieval by infusing inverted-index strengths into graph search: term-based entry seeding, approximate routing via sparse sketching, and sparse partition-based graph construction.",
    },
}

ABS = {
    "2610.30725": "AI 辅助代码生成放大了自动形式验证的需求：生成程序不仅要可执行，还要附带可机器检查的正确性证据。现有方法能从自然语言提示合成功能上像样的代码或看似合理的规约，却未把实现与规约作为面向验证的统一产物协同设计，导致自动验证器常常无法消解证明义务。典型失效包括缺少或隐含证明锚点、对自动推理不友好的程序结构，以及代码级状态与规约级需求事实因分别生成而不一致；即便验证通过，也可能只确立了遗漏关键行为的弱规约。本文提出 VeriGen-C，一个验证友好的框架，从自然语言需求联合合成 C 程序与 ACSL 规约：代码生成与修复被约束为暴露证明相关状态、简化控制流以利于演绎验证、消除阻碍自动证明搜索的实现模式；规约生成与精化同样受限，以缓解仅满足弱规约的验证伪成功。",
    "2610.30200": "模型部署后没有参考答案，它写下的推理轨迹就是判断答案的唯一证据。无参考的替代手段各有缺陷：自我评估会损害它本应保护的答案，采样一致性测的是稳定性而非正确性，扰动研究从人写模板中读出预期答案、实际评的是模型而非轨迹。本文追问：在没有参考解、没有评判模型、不更新权重的前提下，单条轨迹能被验证到什么程度；在 GSM8K 上对冻结的 LLaMA-2-7B-chat 发现，检测并非该流程的瓶颈。让轨迹与自身对照可达 AUROC 0.741 并因结构性原因止步：三分之二的错误轨迹并未给出错误等式，它们只是正确执行了错误的计划；在计划错误的失败上，检测器标记错误轨迹的频率甚至低于正确轨迹。候选自生的变异探针能暴露其中许多失败：把轨迹抽象为关于题目量的程序，扰动其中一个量并执行，再就改写后的题目问模型一次，于是每条轨迹都自带测试。1319 道测试题中有 937 道（71.0%）存在有效扰动；在同时有可解析首条轨迹的 847 道中，有支撑的轨迹正确率 60.6%，而基线为 31.6%。",
    "2610.30188": "程序优化要在保持行为的前提下提升性能。编码智能体已能通过改算法、改数据结构与执行策略把程序变快，但现有等价性检查多依赖测试，而智能体已被证明会利用测试——通过测试却不保持预期行为。本文提出「智能体化可验证优化」：智能体在给出更快实现的同时，附上与原实现等价性的机器检查证明。由于既有实现本身即规约，该任务绕开了可验证代码生成中的规约书写瓶颈，而定理证明的近期进展使证明可行。作者在 Lean 4 中把任务表述在函数与仓库两个层面，程序在其中既可执行又可推理。现实应用很少用 Lean 编写，因此开发了 Aqueduct：把 C、C++、Go、Rust 程序迁移为原生 Lean，并用与原程序的差分测试校验每次移植。在 Verina 的 189 个参考实现上，智能体为 156 个产出更快的证明改写，包括把指数递归换成动态规划这类算法改动；在 17 个迁移应用上，92 条证明改写使 51 个应用场景中的 47 个加速。",
    "2610.30432": "近期报告显示 GitHub 上约 30% 的 Python 代码贡献由 AI 生成。鉴于这类代码固有的不可靠性，形式验证成为建立软件正确性信任的有力途径。尽管用大模型做形式验证已受到关注，实际采纳仍受限于书写形式规约并据其验证程序的难度；现有工具主要支持 Java、C 等语言，对 Python 支持极少。本文提出 TrustedCode，一个验证 AI 生成 Python 代码的自动框架：用大模型完成（i）Python 类型检查、（ii）经 Why3 框架翻译为 WhyML、（iii）用 Why3 后端自动定理证明器依据形式规约验证。方法通过 LangGraph 集成思维链提示，以识别并弥补模型在规约生成与证明上的短板。作者在十个复杂度不同的 Python 程序上评估：约 50% 的错误源于领域知识缺口，30% 源于语法不准确，其余 20% 为语义与类型问题。",
    "2610.30491": "LLM 智能体常通过把执行轨迹归约为标签来评估，例如最终答案正确性、工具验证与故障传播。这些标签是解析器、行为检测器与测试框架规则产生的测量值，未必完整反映轨迹所示。本文在基于 GSM8K 的工具调用场景中研究该问题：智能体调用计算器，其输出偶尔被污染，从而对「工具返回了什么、模型随后用了什么、检测器报告了什么」提供清晰真值。作者在六个生产模型、每个模型 30 道题上审计三类轨迹级检测器：最终正确性、可见复验与故障传播会以系统性方式分歧。一个关键失效模式是「静默工具输出改写」：计算器返回被污染的值，模型随后使用了另一个（常常正确）的值却未再次调用工具，于是坏值不再传播，而验证检测器记录为没有复检。人工复核 90 条轨迹在最终正确性（67/67）、故障影响（19/19）与故障相关性（18/18）上与自动标签完全一致，但在复验上仅 67/81，14 处分歧落入四种反复出现的模式。执行步数与 token 预算也会改变报告结果：两个模型之一的正确数随预算在 21/30 到 27/30 之间变动。",
    "2610.30792": "扩展 GUI 强化学习需要保留真实应用行为的环境。然而把行为推断与编码耦合，会让部分轨迹变成状态转移错误的可运行 mock。本文提出 Trace2World，把全局行为重建与实现分离：先把轨迹归并为共享的、源链接的应用模型，再编译出可执行环境；用独立重放源工作流定位失配，从而把实现修复限制在有界范围。经校验的环境随后支持学习器自适应的任务与环境增强，且不越出源证据支持的行为。从 1570 条轨迹出发，Trace2World 构建 50 个环境；在十款应用的 200 条工作流上，端到端复现率 91.1%，而最强的任务级匹配基线为 59.8%。源依据校验在真实设备上保留了 94.0% 的模拟训练增益，自校验仅为 54.7%。学习器引导把基准成功率从 56.9% 提到 61.1%；在 Trace2World 中训练还使模型在本基准提升 20.2 点，在四个外部 GUI 基准提升 5.4–16.2 点，在 100 个真实设备任务上提升 16.3 点。",
    "2610.31201": "L4 是一种通用、可逆、带线性类型的底层语言，旨在作为把可逆编程语言编译到可逆机器的中间语言，用以取代并推广可逆 SSA 形式 RSSA，其灵感来自 HSSA 等其他底层可逆语言。本文先非形式化地定义 L4，再给出其形式化类型系统与双向小步语义：规则带有方向指示以决定正向或反向执行，且方向可在执行过程中改变。",
    "2610.30758": "AI 辅助编辑能产出保留熟悉发行人版式、却改变申请人身份的贷款文件。本文考察经验丰富的审贷人员与承保人在首轮纯文档复核中能否识别此类伪造。三位通过 Upwork 招募的从业者各收到一份申请人材料包，材料来自 47 份经完整授权提供的真实财务文档衍生出的 134 份伪造 PDF。这些编辑保留了金额、日期与余额，流水线引入的标识信息不一致在分发前被有意保留。复核者未被告知文件被改动，共返回 132 份文件级判断。把其解释与原件核对后，得到 14 项有编辑证据支撑的关切（10.6%）：12 项「可疑」与两项「信息不足」；全部有据关切都涉及文件内部或跨文件的标识信息不一致，且没有任何报告提及的视觉线索真正指向一次实际编辑。因此尽管文件中留有已知不一致，约每十份判断才有一份包含伪造证据。作者据此主张在人工复核之外评估一致性检查与独立来源核验；由于仅三对复核者—材料包且无真实文件对照，结论描述的是该探索性设定而非总体检出准确率。",
    "2610.31306": "软件智能体正被训练到超越人类工程师；作者主张能力本身不等于更好的软件工程。他们把「超级智能软件工程」定义为用能力超过人类工程师的智能体构建与演化软件的学科，其中治理（门禁、契约、决策与知识衰减控制）必须随能力扩展。论证基于三点：第一，项目中的正确性依赖代码并不承载的决策与契约；第二，知识会衰减；第三，一旦智能体跑得比其审阅者快，阅读只能拦下越来越少建立在过期知识上的改动。一个简单模型显示：超过固定审阅容量后，逃逸的改动随吞吐线性增长，而阅读能拦下的比例趋于零；治理可以降低斜率，仅靠能力不行。对 452 个星标最高公开 GitHub 仓库的探索性快照发现，48.67%（95% 置信区间 44.1–53.3）在根目录或 .github 下有智能体上下文文件；在标出了仓库路径的中位文件中，按不同引用读法，9.5% 到 22% 的路径无法解析。作者随后提出 OSTEON 规范并以 DOI 发布。",
    "2610.30877": "在源码不可得时，将剥离符号、深度优化的二进制提升为规范化的优化前 LLVM IR，对下游安全分析与遗留软件迁移至关重要。然而激进的编译器优化会重写控制流与数据流、删除结构元数据、引入类型被擦除的底层惯用法，使现有提升器产出畸形或语义偏离的 IR。本文提出 ATLAS，一个从优化后反汇编重建形式有效且规范化 LLVM IR 的多智能体框架，结合两项技术：（i）结构感知的区域级检索，用伪探针归因把优化指令与规范化 IR 样例对齐；（ii）协作精化循环，弥合概率生成与确定性编译器约束之间的差距。具体地，Lift 智能体以检索到的样例为条件生成初始 IR 草稿；Advisor 智能体解释 LLVM 验证器与编译诊断及静态检查，提出局部修复动作；Validation 智能体施加编辑、重跑工具链验证（可用时还做运行时检查），并把诊断反馈给 Advisor；智能体如此迭代直到 IR 通过验证器。",
    "2610.31118": "前端编码智能体通常只被一个问题评分：请求的目标有没有被构建出来。真实的工程改动还带有第二项义务——网站其余部分必须继续工作。作者把这项义务称为「网站连续性」，并发布 ProductWebBench，在活的前端仓库上同时给两者打分：320 个针对既有代码的改动任务与 80 个长程构建任务。每个任务在评估前冻结仓库快照、分阶段需求、浏览器证据与确定性检查，且只有参考实现通过全部检查、看似合理但错误的实现失败后才被纳入。一个模拟用户逐阶段揭示需求，此前通过的检查在余下运行中一直保持生效。来自 13 个模型的 8737 次运行显示两者会分离：在通过全部请求工作检查的改动运行中，28.2% 仍然失败于连续性检查（空白路由、横向溢出、控制台错误），10.8% 把已通过的浏览器状态重新变成失败。由于同样的检查也在未改动仓库上运行，每次回归都有精确来源而非事后标签：在同时具备两种读数的 586 次运行中，18.3% 被抓到破坏了已验证状态。交互是另一个盲区，在 29.5% 的运行中失败。",
    "2610.30698": "LLM 智能体可以正确检索到某条记忆，却在其有效性状态改变后错误地使用它。本文研究「治理状态污染」：在存储内容与任务保持不变的前提下，改变哪些留存记录进入模型可见上下文的故障。跨六个提供方，731 个基于基准的底座产生 2080 对匹配故障。在离线控制面检查中，污染在 96.25% 的配对里改变了有效投影，而基于 oracle 的强制在 100% 的情形下恢复了它。在下游评估中，一个确定性选取、非概率的 LongMemEval/Memora 面板解决了 300 个匹配三元组中的 298 个（238 个不同底座）。干净减污染的反差在 LongMemEval 二元正确性上为 40.54 个百分点（95% 底座簇区间 [30.32, 50.71]），在重标定的 Memora FAMA 上为 30.60 点（[23.31, 37.69]）；两个来源也都显示恢复。OAKS Novel 的原生选项一致性在全部 6714 个已解析输出上成立。全队列冻结评分器的污染/恢复效应（-27.55/+27.51 点）仍是描述性代理，而非经校验的原生语义总体效应。",
    "2610.30221": "大型组织日益面临本书所称的「认知复杂度之墙」：在数百个相互作用组件的规模上，维护依赖图并以事故节奏反应，超出人类团队所能交付。本概念性著作提出 AAM/5C：五项能力（捕获、理解、选择、协调、控制）实例化于七个逻辑层 L1 到 L7。单一授权规则 R-AUT 分离谁提议、谁决策与谁执行：概率规划器（L4）提议；治理层（L6）在签名策略下决策并把裁决记录为签名评估证明；安全层（L5）签发与该证明绑定的短期行为令牌；策略执行点在目标层落实行为之前校验二者。在显式保证契约下，两条分析性陈述（H7a、H8a）构造性成立；其十条假设中的其余陈述，包括日志完备性（H7b）与执行点不可绕过（H8b），是可反驳的，且用于反驳它们的协议在任何测量之前即已固定。本书贡献在于一个规范性参考模型：在单一授权规则下阐明已知机制，并新增三项构造性贡献。",
    "2610.30425": "学习稀疏检索（LSR）因兼具神经表示的泛化能力与关键词搜索的可解释性，近年受到信息检索界关注。多项近期工作表明，针对学习稀疏嵌入适当改造的倒排索引在 LSR 上取得了最先进的召回—延迟权衡，在固定召回目标下常以显著更低的延迟胜过图索引，因此社区普遍认为图近似最近邻搜索在 LSR 上不如倒排索引。本文挑战这一共识。核心洞见是：把标准图 ANN 索引开箱即用地用于稀疏向量确实性能不具竞争力，但把倒排索引的优势注入图搜索即可克服这些不足。作者引入三项技术加速图式 LSR：（i）基于词项的入口点播种；（ii）通过稀疏草图做近似路由；（iii）基于稀疏划分的图构建。三者合成新的图式 ANN 系统 GRIP，在 MS MARCO v2 基准（1.38 亿段落）上取得更优的权衡。",
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
