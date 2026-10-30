# -*- coding: utf-8 -*-
"""2026-10-30 批次：本期 24 篇推荐项（核心 14 + 兴趣扩展 10）的双语简介 + 摘要中文译文。

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
    "2610.38174": {
        "zh": "EasyProver 用「递归智能体 + 隔离上下文 + 异步搜索 + 并行 tactic 探测 + 弹性 elaboration 服务」搭建 Lean 证明系统，不额外训练即用现成前沿模型证明 PutnamBench 669/672、IMO 2026 全部六道形式化题、NTP4VC 597/600 条验证条件与 VERINA 全部 189 个任务（证明或反证）。因这批基准已接近饱和，作者另建 Aegis：把竞赛编程题改造成针对真实实现、带实现级义务的验证任务——写安全 Rust 解、经 Aeneas 转 Lean、生成规约、再由内核检查的证明或反证打标签，产出 2045 对差分验证的 Rust-Lean 程序与 11533 条候选规约。",
        "en": "EasyProver composes recursive agents with isolated contexts, asynchronous search, parallel tactic probing and an elastic elaboration service; with an off-the-shelf frontier model and no extra training it proves 669/672 PutnamBench problems, all six IMO 2026 formalizations, 597/600 NTP4VC verification conditions and all 189 VERINA tasks, and the authors add Aegis, which turns competitive-programming problems into implementation-level verification tasks carrying fixed-width arithmetic, explicit failure, generated loops and casts.",
    },
    "2610.39723": {
        "zh": "加权编程（把数学模型或优化问题写成以半环为参数的命令式程序，再用最弱前置条件演算分析）被扩展了两件事：可数非确定性与用户定义的加性奖励，参数从半环放宽到 module，从而能推理概率程序的期望资源消耗与组合博弈的最优得分。技术难点在于：可数非确定性会破坏程序语义常用的连续性，使任意 module 上的 wp 演算失去可靠性；论文给出 wp 式变换器相对操作语义可靠的充分条件，并据此给出概率程序验证的机械化基础。",
        "en": "Weighted programming is extended with countable nondeterminism and user-defined additive rewards by parameterizing programs over modules rather than semirings, enabling reasoning about expected resource consumption and optimal game scores; because countable nondeterminism breaks the continuity properties that wp calculi rely on, the paper isolates conditions under which the transformer is sound with respect to an operational semantics and builds mechanized foundations for probabilistic program verification.",
    },
    "2610.40538": {
        "zh": "Lean 的高阶表达力（高阶函数、归纳数据类型、用户自定义抽象）让「把证明义务翻译成一阶 SMT 查询、再从求解器证书重建内核检查证明」变得困难。crush 用去函数化（defunctionalization）把函数值及其应用编码进一阶逻辑，对支持的高阶片段形式化该翻译并证明其可靠性；同时暴露元编程接口，使他人无需改动翻译流水线即可扩展 Lean→SMT 翻译与证明重建。它既能当 tactic 用，也能作为第三方自动化系统的后端；在四个覆盖验证与通用证明自动化的用例上，crush 消解的义务与重建的内核检查证明都多于竞争后端。",
        "en": "crush is an extensible SMT-backed automation framework for Lean that uses defunctionalization to encode higher-order function values and their applications into first-order logic, proves the translation sound for a supported fragment, and exposes metaprogramming interfaces for extending both translation and proof reconstruction; used as a tactic and as a backend for third-party automation, it discharges more obligations and reconstructs more kernel-checked proofs than competing backends across four use cases.",
    },
    "2610.39017": {
        "zh": "共识与一致性协议上线前通常经过严格证明与形式验证，但生产环境中频繁发生的「协议修改」几乎得不到同等严格性，成为安全缺口。DistOptimize 把手写修改换成自动优化：把学术语言中的吞吐优化迁移到生产框架，重写的正确性在 Rocq 中证明，应用过程由标定加 ILP 搜索空间导航自动完成。在基础分布式协议与 AWS 实际使用的协议上，吞吐最高提升 4 倍，时延最多增加 0.3ms。",
        "en": "DistOptimize replaces error-prone manual protocol modification with an automatic optimizer that ports throughput optimizations from academic languages to production frameworks, proves each rewrite correct in Rocq, and applies them by combining calibration with ILP-based search-space navigation, improving throughput by up to 4x at a latency cost of at most 0.3ms on both textbook and AWS production protocols.",
    },
    "2610.39066": {
        "zh": "自动校验 AI 生成的安全补丁，难点在于「不再崩溃 + 既有测试通过」并不足以说明漏洞被真正修好且没引入回归。DeepDiff 做回归自由性差分检查：用不触发崩溃但覆盖受影响代码路径的输入，把候选补丁与原脆弱程序对比执行——正确补丁应当既消除触发崩溃又保持既有行为。为此作者基于 CyberGym 的开源内存安全漏洞构建了正确/错误补丁候选数据集，比较了纯神经判别器与「动态分析 + 神经」混合方案，并探索了若干非触发测试输入的生成路径。",
        "en": "DeepDiff checks regression-freedom differentially: candidate patches are executed against the original vulnerable program on non-crashing inputs that reach the affected paths, so a correct patch must both remove the triggering crash and preserve intended behavior; the paper contributes a dataset of correct and incorrect patch candidates for CyberGym memory-safety vulnerabilities and compares a purely neural checker with a hybrid of dynamic analysis and neural techniques.",
    },
    "2610.39380": {
        "zh": "AI 基础设施按层设计，分层让它可管理，却也提前排除了「必须软硬件同改才成立」的优化空间。Formulaic 把工作拆开：智能体写「表述」——一族程序及其正确性条件，数学求解器在表述内优化，验证与测量检查其假设与结果；智能体从计算图逐级走向芯片，每步都是模板。芯片侧用 wall relaxation，通过给约束软件的硬件上限定价来搜索设计空间。这是分项研究而非端到端打通的一步：在 NVIDIA GB10 上，智能体写的模板已能跑完整的 Qwen3-8B。",
        "en": "Formulaic splits the work between an agent that writes a formulation, a mathematical solver that optimizes within it, and verification plus measurement that check its assumptions; the agent refines step by step from computation graph toward chip, wall relaxation searches hardware by pricing the limits that bind software, and on NVIDIA GB10 agent-written templates run a complete Qwen3-8B workload.",
    },
    "2610.40287": {
        "zh": "在算力受电力约束的当下，「每 token 能耗」决定数据中心能服务多少 token，而时延目标又限定每个用户多快拿到结果。投机解码靠一次前向复用权重读出来验证多个草稿 token，但每个草稿 token 无论是否被接受都要验证，所以真实节能幅度取决于接受率。论文在生产条件（SGLang、开启 CUDA graphs）下测量，发现接受率随目标模型的注意力族、起草方案与文本类型显著变化：所有被评估的起草器在对话上比代码接受更少，在所有受训起草器上低资源语言（罗曼什语）比英语接受更少。",
        "en": "An energy accounting of speculative decoding under latency targets: because every drafted token must be verified whether accepted or not, the achievable saving is governed by acceptance rate, which the authors measure under production conditions (SGLang with CUDA graphs) and show varies by attention family, drafting scheme and text domain, with every evaluated drafter accepting fewer tokens on conversation than on code and fewer on Romansh than on English.",
    },
    "2610.38130": {
        "zh": "传统动态不变式检测器只能从固定模板库提议不变式，表达力受限。作者让 LLM 参与提议，发现选对提示与上下文后既提升表达力又降低推断成本；但表达力带来新风险——LLM 提议的不变式在求值时可能执行任意代码，产生副作用甚至死循环。对策是一套插桩策略：包裹每个候选、每线程同时只求值一个不变式，使嵌套求值不会无限互相触发；对非嵌套挂起用停顿监控加递增时间预算重试；由于无法事先证明候选无副作用，再用 delta debugging 定位。",
        "en": "Template-free dynamic invariant detection lets an LLM propose invariants alongside template-derived ones, improving expressiveness while lowering inference cost; because an LLM-proposed invariant may execute arbitrary code during evaluation, the paper contributes instrumentation that wraps each candidate, evaluates one invariant per thread at a time, monitors runs for stalls with a growing time budget, and uses delta debugging to localize side effects.",
    },
    "2610.39491": {
        "zh": "据作者所知，这是首个全自动的 QSP（量子信号处理）哈密顿量模拟验证框架。它利用算法结构：哈密顿量写成 Pauli 串的加权和，经块编码嵌入更大的酉算子，再由 QSP 变成时间演化算子。验证器用带辅助位索引电路块的符号 Pauli 和语义，证明「全零辅助位块与目标哈密顿量成比例」并自动推断次归一化因子；再抽取 QSP 层实现的多项式变换并认证其近似误差。正是这种结构感知抽象带来可扩展性：组合后的宏展开规模约 152 万门，但块编码只需验证一次，QSP 层通过抽象接口检查，无需展开 oracle 调用。",
        "en": "The first fully automated verification framework for QSP-based Hamiltonian simulation uses a symbolic Pauli-sum semantics for ancilla-indexed circuit blocks to prove the all-zero ancilla block proportional to the target Hamiltonian while inferring the subnormalization factor, then extracts and certifies the polynomial implemented by the QSP layer; the structure-aware abstraction certifies the block encoding once and checks QSP through its abstract interface, keeping a roughly 1.52-million-gate macro expansion tractable.",
    },
    "2610.38214": {
        "zh": "编码智能体通常拿到端到端行为规约（测试、输入输出样例），但「要给多少条、给哪些，才能让智能体产出开发者想要的程序」无法先验判定：智能体先承诺一个结构（数据类型、模块、函数的分解），结构固定了一类候选程序，行为规约再在其中选一个。对一种结构足够的测试，对另一种可能严重欠定，需要不同边界或指数级更多样例；而结构由智能体选定，开发者不得不从数千行生成代码里反推规约是否完备。Skeleton Coding 让开发者用高层类代码格式共同指定结构，从而把规约完备性变成可判定的事。",
        "en": "Skeleton Coding argues that how many behavioral specifications a developer must supply cannot be decided a priori because the agent first commits to a structure that fixes a class of candidate programs; developers therefore co-specify the structure in a high-level code-like format, making specification completeness checkable instead of something reverse-engineered from thousands of generated lines.",
    },
    "2610.38438": {
        "zh": "LLM 常被系统提示词塑造成特定角色（导师、面试官、代表组织行事的智能体），但在与真实且可能带对抗意图的用户多轮交互中，它们究竟能多好地守住角色规约，研究不足。作者提出「用户行为 fuzzing」——在合理用户行为空间里做引导式搜索，寻找能让模型违反角色规约的对话；RoleFUZZER 把软件测试的覆盖率引导 fuzzing 迁移过来，用「用户交互类型分类 × 角色规约（即受压的是什么）」交叉的覆盖网格指导场景构造，并在导师、财务顾问、AI 面试官、对抗性角色扮演、受组织政策约束的 web agent 五种规约上评测。",
        "en": "RoleFUZZER operationalizes user-behaviour fuzzing by adapting coverage-guided fuzzing from software testing: scenarios are steered by a coverage grid crossing a grounded taxonomy of user interaction types with the role specification under pressure, and models are evaluated across five specifications including tutor, financial advisor, AI interviewer, antagonistic roleplay character and a web agent bound by organizational policy.",
    },
    "2610.39504": {
        "zh": "静态可达性给出的「不可达」判决会直接把一条发现从人工复核中移除，风险很高。SourceLens 把 Semgrep 发现映射到 Python 调用图（边取自 Joern 代码属性图里连接的调用），再用真实执行核对这类负判决：在 asciinema 上被判不可达的 123 个函数中，项目自带集成脚本执行了 86 个、作者全部运行执行了 113 个；Sublist3r 的 24 个里有 19 个被执行。缺失的调用多经值传递（类、函数作为参数）或根本没有调用表达式（with 块、属性读取）；在 asciinema 中仅 4 条缺失边就让 113 个被执行函数里的 50 个变为可达。最新版 Joern 给出相同判决。",
        "en": "SourceLens checks Joern-based negative reachability verdicts against execution by mapping Semgrep findings onto a Python call graph whose edges come from Joern's code property graph: of 123 functions judged unreachable in asciinema, the project's own integration script executes 86 and all runs execute 113, with missing calls passing through values or lacking call expressions such as with blocks and property reads, and four missing edges alone make 50 of the 113 reachable.",
    },
    "2610.39981": {
        "zh": "大规模科学工作流跑在分布式 HPC 资源上，导致「数据产品怎么产生的、为什么同样的执行会给出不同结果」难以解释。现有系统要么只管分布式执行、要么只管溯源管理，很少把细粒度溯源当作数据产物的内在属性。TRACEs 把数据血缘与执行上下文直接嵌入每个生成的数据产物，使溯源与编排解耦：既把「以产物为中心」的溯源从本地容器推广到分布式工作流，又保持与既有工作流管理系统的兼容。在跨多台 HPC 节点的七阶段大肠杆菌变异检测工作流上，分布式执行下溯源完整性达 100%，中间存储减少约 59%。",
        "en": "TRACEs embeds data lineage and execution context directly into every generated artifact, decoupling provenance from orchestration so artifact-centric provenance generalizes from local container runs to distributed workflows while staying compatible with existing management systems; on a seven-stage E. coli variant-calling workflow across HPC nodes it reports 100% provenance completeness and about 59% less intermediate storage.",
    },
    "2610.38337": {
        "zh": "优化、重构等任务要求保持组件行为，因此需要评估功能相似性的手段：形式化证明功能等价无法扩展、也不量化相似程度；机器学习近似在存在细微语义差异时容易失灵。差分模糊测试可扩展地在语义层面做程序对比，但通常要人工为每对程序构造合适的输入生成器。DIFUZZI 用 LLM 合成输入生成器并迭代验证与修复，把这步自动化，从而让差分模糊测试更易推广；工具与演示视频已公开。",
        "en": "DIFUZZI automates the main obstacle to differential fuzzing, namely hand-building input generators suited to each program pair, by having an LLM synthesize generators that are iteratively validated and repaired, making semantic differencing of programs practical for functional-similarity assessment in optimization and refactoring tasks.",
    },
    # ---------------- 兴趣扩展 ----------------
    "2610.39354": {
        "zh": "问的是：整数上是否存在一种拓扑，其连通子集恰好就是连续整数集合。主结果对每个整数格 Z^n（n>0）给出构造，Z 的情形作为推论得到。论文证明「由坐标和奇偶性确定的邻域构成基」，且拓扑连通性与「经单位格步的有限路径可达」完全一致；同时给出演绎审计，以及该论证与 Lean 4 + Mathlib 形式化之间的对应，包括空集处理与整数区间的独立形式刻画。构造与数学结果源自 Dan Marcus 提出、1970 年由克利夫兰州立大学小组解决的 Problem 5712，本文的贡献是详细阐述与形式验证报告。",
        "en": "A construction of a topology on every integer lattice Z^n whose connected subsets are exactly the sets of consecutive integers, proved by showing that neighborhoods determined by the parity of the coordinate sum form a basis and that topological connectedness coincides with reachability by finite unit lattice steps, together with a Lean 4 and Mathlib formalization and a deductive audit of the 1970 solution to Problem 5712.",
    },
    "2610.38616": {
        "zh": "序维护（order maintenance）要求数据结构在插入删除下维护序列并回答「两者谁在前」。论文给出一个由已发表组件拼成的算法，每次操作最坏情况常数时间，并在 Lean 4 中完整验证。算法是一个深嵌入 Lean 的随机存取机程序，解释器对每条指令计数：证明它对每个查询的回答与简单参考规约一致、每次操作步数不超过固定上界（与元素个数和历史无关）、t 次操作后已计算的值不超过 O(log t) 位（故可在该字长的机器上原样运行）。一条保步数精确的验证翻译把高层证明接到机器程序上，因此解释器是唯一需要信任的代价模型；未经验证的原生实现用于展示实际开销。",
        "en": "An order-maintenance algorithm assembled from published components runs every operation in worst-case constant time and is verified in Lean 4: the program is a random-access machine deeply embedded in Lean whose interpreter counts instructions, with proofs that answers match a reference specification, that each operation takes a fixed number of steps independent of size and history, and that computed values stay within O(log t) bits after t operations.",
    },
    "2610.39926": {
        "zh": "域泛化语义分割要求训练时完全接触不到目标域数据，却要在未见域上做准确稠密预测。现有方法靠数据多样化、不变性学习或直接用基础模型提升迁移性，但往往难以同时压制域敏感干扰与保留细粒度空间线索。SIFR 是频域感知的双流框架，把「谱建模」当作统一原则同时调控融合与解码两个阶段：不做冻结 CLIP 与 DINOv2 特征的直接拼接，而是做谱引导的不变融合以滤除域敏感响应、保留互补的语义与结构信息；解码侧再加谱解码精化模块，用基于低频统计的归一化与自适应频域选择稳定多尺度解码器特征。",
        "en": "SIFR is a frequency-aware dual-stream framework for domain generalized semantic segmentation that treats spectral modeling as a single principle governing both stages: spectral-guided invariant fusion filters domain-sensitive responses while keeping complementary semantic and structural cues from frozen CLIP and DINOv2, and a spectral decoder refinement module stabilizes multi-scale decoder features via low-frequency-statistics normalization and adaptive frequency selection.",
    },
    "2610.38245": {
        "zh": "逆合成规划要从可购买的起始原料找到通往目标分子的路线；在预测反应上做搜索能把目标连到可用原料，但一条不可行的反应就能让整条路线作废，而「搜索结束后再评估路线质量」无法纠正搜索过程中犯的错。VGR 把反应验证当作 AND/OR 搜索中的一个决策动作：验证结果表示为二元判决，查询由搜索结构调度，已获判决用于排除反应或调整搜索优先级；并定义「已验证可解率」为找到被验证器逐步接受的完整路线的目标比例。在 Retro190 上，把验证结果反馈进搜索使已验证可解率从 51.1% 升到 62.6%；受控实验显示「更早验证」与「立即优先被接受的反应」各自都有效，但两者叠加反而更差。",
        "en": "Verification-Guided Reflow incorporates reaction verification as a decision action inside AND/OR search, scheduling verification queries from the search structure and using binary verdicts to exclude reactions or reorder priorities; on Retro190 this raises verified solvability from 51.1% to 62.6%, and controlled experiments show earlier verification and immediate prioritization each help while combining them hurts.",
    },
    "2610.39735": {
        "zh": "论文为一类「协同的参数化变换系统」建立形式语义，以 Transformer 为范式起点但刻意抽离其具体数学实例。表示向量同时获得外延指称与有序内涵解释，参数结构则获得相对的、第二层解释，用来确定参数性质如何被保持、替换或组合；由此得到「变换概念」——数值作用与性质层映射相协调的参数化变换。作者进一步区分这类系统共有的代数-语义内核与架构特有的功能组织，使同一抽象系统类型可有不同数学实例与机械实现；框架应用于注意力头与残差连接，给出的语义解释只依赖共享内核与局部功能组织，因而可推广。",
        "en": "A formal semantics for coordinated systems of parameterized transformations, taking the Transformer as paradigm while abstracting its mathematics: representational vectors receive extensional reference and ordered intensional interpretations, parameter structures receive relative second-level interpretations governing preservation, replacement and combination of argument properties, yielding transforming concepts and separating a shared algebraic-semantic core from architecture-specific functional organization, applied to attention heads and residual connections.",
    },
    "2610.39454": {
        "zh": "运行期规划（如边行动边重规划机器人）需要规划器读懂用户写的 PDDL——持续动作、数值资源、时间窗、连续变化——快速作答，且只给出经过验证的计划。专用规划器在 PDDL 的单个片段上很强，但在覆盖范围、时延以及「失败意味着什么」上各不相同。Kairos 按任务语义做剖析，决定五个引擎（接地启发式搜索、压缩与 snap-action 时序搜索、混合动力学的时间步、提升搜索）中哪些适用，并在统一时间与内存预算下调度；每个候选计划都由独立于规划器变换的验证器检查，「不可解」只在「搜索穷尽即证明不可解」的搜索真正耗尽空间时才报告。在九个比较套件的 1756 个任务上评测。",
        "en": "Kairos profiles each planning task to select among five heterogeneous engines (grounded heuristic search, compressed and snap-action temporal search, time steps for hybrid dynamics, lifted search) and schedules them under one time and memory budget, validating every candidate plan with a checker independent of the planner's transformations and reporting unsolvable only when a proof-by-exhaustion search exhausts its space, across 1,756 tasks from nine comparative suites.",
    },
    "2610.39007": {
        "zh": "模拟与混合系统的开发依赖大量领域知识，而这些知识既难以写成形式规约，也无法直接被机器学习利用。论文提出混合分析/监控方法：用带区间操作的正则表达式在信号中定位感兴趣区域，用经典信号处理提取有语义的特征，再用半监督学习推断区分正常与故障行为的复杂关系；从正常行为数据学到的关系可自动用于同一系统或其变体上的错误行为检测。在电压调节器上的实验显示了检测非期望行为的有效性。",
        "en": "A hybrid specification-plus-data approach monitors real-valued signals by using interval-annotated regular expressions to locate regions of interest, classical signal processing to extract semantically meaningful features, and semi-supervised learning to infer relationships separating correct from faulty behavior, with the learned relations transferring to detect undesired behavior in the same system or its variants, demonstrated on a voltage regulator.",
    },
    "2610.38697": {
        "zh": "SatOps-Decision 面向卫星通信在轨操作的低延迟决策，据作者所知是「Jev 风格通用判别式决策模型」在卫星操作上的首次应用，配套基准也是该方向首个。学习得到的打分器是一个本地适配的 Laya 编码器加其原生决策头，单次前向即可在给定的候选操作答案中做出选择。基准由撰写的操作契约、受控状态变化与独立校验的标签可审计地构成，主准确率比较统一用 1024 条留出问题。本地打分器中位时延 90.3ms，对比 Qwen3.5-0.8B 生成 493.9ms、OneJev1.6-0.8B 388.4ms（5.47×/4.30×），平均原始准确率 85.3%。",
        "en": "SatOps-Decision applies Jev-style general-purpose discriminative decision models to satellite operations for the first time: a locally adapted Laya encoder with its native decision head selects among supplied operational answers in one forward pass, achieving 90.3ms median latency versus 493.9ms and 388.4ms for two 0.8B generative baselines (5.47x and 4.30x speedups) at 85.3% mean raw accuracy on an auditable benchmark with independently checked labels.",
    },
    "2610.40551": {
        "zh": "随着 AI 数学能力提升，有意义的基准正从大学题目与奥赛转向研究级数学。Ramanujan Challenge 由数论研究级问题构成，含未发表结果与开放猜想：它给出数学常数的具体公式（可数值校验正确性），而证明可能需要非显然的数学。本文分析该挑战的提交，量化不同 AI 模型、计算机代数系统与形式工具的相对成功率，既发现与官方解答概念上不同的正确提交，也发现一个已发表开放猜想的证明。评审提交本身暴露了第二个挑战——大规模可靠判定复杂证明，因此作者提出 AI 辅助评审流水线，分别处理自然语言证明、CAS 代码与 Lean 形式化，评估语义与逻辑正确性，相比传统一次性 LLM 判分降低了误判。",
        "en": "An analysis of Ramanujan Challenge submissions, a research-level number-theory benchmark with unpublished results and open conjectures, measuring the relative success of AI models, computer algebra systems and formal tools, reporting correct submissions conceptually distinct from official solutions and a proof of a published open conjecture, and introducing an AI-assisted evaluation pipeline over natural-language proofs, CAS code and Lean formalizations that reduces misjudgment relative to one-shot LLM grading.",
    },
    "2610.39191": {
        "zh": "产后抑郁（PPD）是美国孕产妇死亡的首要原因，而筛查、识别与治疗都存在明显缺口，根源之一是现有早期诊断与后续监测干预手段的局限。融合交互界面与连续可穿戴生物传感器的移动技术，有望增强临床决策并改善 PPD 照护。本文讨论构建此类系统时需要处理的研究方向：用户体验设计、围产期阶段的传感精度、临床集成与互操作、接受与采纳、隐私与伦理，并以「以女性及其体验为中心」的可穿戴设备为落点，梳理 HCI、包容性生理计算与女性健康交叉处的挑战与机会。",
        "en": "A human-centered discussion of wearable biosensors for early detection and continuous monitoring of postpartum depression, the leading cause of maternal mortality in the United States, laying out research directions in user experience design, sensing accuracy across perinatal stages, clinical integration and interoperability, acceptance and adoption, and privacy and ethics at the intersection of HCI, inclusive physiological computing and women's health.",
    },
}

ABS = {
    "2610.38174": "本文提出 EasyProver：一个由递归智能体、隔离上下文、异步搜索、并行 tactic 探测与弹性 elaboration 服务构成的 Lean 证明系统。使用现成前沿模型且不做额外训练，它证明 PutnamBench 672 题中的 669 题、IMO 2026 全部六个形式化题，并以证明或反证解决 NTP4VC 的 597/600 条验证条件与 VERINA 全部 189 个任务。由于这些基准已接近饱和，作者另提出 Aegis：把竞赛编程题转换为针对真实实现的更难验证任务——流水线写出安全 Rust 解、用 Aeneas 翻译为 Lean、生成规约，并为每条冻结陈述打上内核检查的证明或反证标签，产出 2045 对经差分验证的 Rust-Lean 程序与 11533 条候选规约。与手写基准不同，这些任务带有来自定宽算术、显式失败、生成的循环、类型转换与函数化变异的实现级义务。",
    "2610.39723": "加权编程是 Batz 等人提出的框架：把数学模型或优化问题描述为以半环为参数的命令式程序，再用最弱前置条件演算等程序验证技术分析，应用包括概率程序的期望结果推理与在线算法的竞争分析。本文对加权编程做两项扩展：（1）可数非确定性；（2）用户定义的加性奖励，程序参数化到 module 而非半环。由此可推理概率程序的期望资源消耗与组合博弈的最优得分。技术挑战在于：同时含（1）与（2）、且定义在任意 module 上的 wp 演算可能不可靠——众所周知，程序语义中常用的连续性在出现可数非确定性时会失效。论文研究了 wp 式变换器相对操作语义可靠的充分条件。",
    "2610.40538": "Lean 的高表达力支持高阶函数、归纳数据类型与用户自定义抽象，这使把证明义务翻译为一阶可满足性模理论（SMT）查询并重建内核检查证明变得困难。本文提出 crush：一个面向 Lean 的可扩展 SMT 后端证明自动化框架。为弥合 Lean 高阶构造与求解器一阶逻辑之间的差距，crush 用去函数化编码函数值及其应用，并对所支持的高阶片段形式化该翻译、证明其可靠性。此外，crush 提供元编程接口，使他人可在不修改翻译流水线的前提下扩展 Lean→SMT 翻译与从求解器证书重建 Lean 证明。crush 既实现为 tactic，也实现为其他第三方自动化系统的后端；在四个针对验证与通用证明自动化的用例上，crush 消解的义务多于竞争后端，重建的内核检查证明也更多。",
    "2610.39017": "分布式共识与一致性协议难以推理，却是云的基础，因此部署前通常要经过严格证明与形式验证；而生产环境中频繁发生的协议修改很少获得同等严格性，可能危及安全。本文通过为分布式协议提供自动优化器 DistOptimize，消除手工修改带来的安全违规风险。DistOptimize 把学术语言中的吞吐优化迁移到生产所用框架，在 Rocq 中验证重写的正确性，并通过标定与基于 ILP 的搜索空间导航自动施加这些重写。应用于基础分布式协议与 AWS 实际使用的协议，吞吐最高提升 4 倍，时延最多增加 0.3ms。",
    "2610.39066": "自动校验 AI 生成的安全补丁仍是显著挑战：消除已报告的崩溃并通过既有测试套件，都不足以让人相信补丁在修复底层漏洞的同时没有引入回归。本文提出 DeepDiff：一种回归自由性检查技术，用不触发崩溃、但覆盖受影响代码路径的输入，把候选补丁与原脆弱程序做差分评估。回归自由性的预期是：正确补丁应消除触发漏洞的崩溃，同时在非崩溃输入上保持原有行为。为支撑该评估，作者引入一个针对 CyberGym 开源内存安全漏洞的正确与错误补丁候选数据集，并探索了到达被修补代码的非触发测试输入生成方法、纯神经回归自由性检查器，以及结合动态分析与神经技术的混合方案；实验结果证明了其有效性。",
    "2610.39380": "AI 基础设施——训练与服务 AI 模型的芯片与软件——是分层设计的。分层让系统可管理，却也固定了优化器能考虑的选择：需要软硬件同改才能取得的收益，在优化开始前就被排除在表述之外。语言模型智能体使重新审视这些边界成为可能，但智能体的提议本身无法证明设计正确或最优。本文提出 Formulaic：智能体写表述，数学求解器在表述内优化，验证与测量检查其假设与结果；智能体从计算图逐级向芯片精化，每一步都是模板——一族程序及其正确性条件。wall relaxation 通过为约束软件的硬件上限定价来搜索芯片。本文以若干独立研究而非一次端到端运行迈出第一步；在 NVIDIA GB10 上，智能体写的模板可运行完整的 Qwen3-8B 负载。",
    "2610.40287": "大模型服务受设施电力限制：「每 token 能耗」决定数据中心能服务多少 token，而时延目标限定每个用户多快拿到结果。解码阶段每个生成的 token 都要从内存读一遍全部权重；批处理把这次读取摊到多个用户，却不使任何单个用户更快。投机解码可以：起草器提出若干未来 token，目标模型用一次前向验证它们，复用同一次权重读取。由于每个草稿 token 无论是否被接受都必须验证，投机解码节省的能耗取决于有多少草稿 token 被接受。这一节省很难确定：它随目标模型的注意力族、起草方案与所服务文本变化；所有被评估的起草器在对话上比在代码上接受更少，在所有受训起草器上低资源语言罗曼什语比英语接受更少。本文在生产服务条件（SGLang、开启 CUDA graphs）下测量投机解码。",
    "2610.38130": "动态不变式检测器提议方法前后条件等不变式，并排除运行时不成立的那些。传统检测器从固定模板库提议不变式，限制了表达力。大语言模型可以替代或补充模板派生不变式来提议；作者发现选对提示与上下文后，这一思路既能提升不变式表达力，又能降低推断成本。更强表达力带来复杂性：LLM 提议的不变式在求值时可能执行任意代码，造成副作用或死循环。本文的插桩策略缓解这些问题：包裹每个候选并让每线程一次只求值一个不变式，使嵌套求值不会无限互相触发；对非嵌套挂起，监控每次运行的停顿并在递增时间预算下重试；由于无法事先证明候选无副作用，采用 delta debugging 定位。",
    "2610.39491": "本文提出（据作者所知）首个面向基于 QSP 的哈密顿量模拟的全自动验证框架。框架利用模拟算法的结构：哈密顿量以 Pauli 串的加权和给出，经块编码嵌入更大的酉算子，再由量子信号处理（QSP）变换为时间演化算子。借助面向带辅助位索引电路块的符号 Pauli 和语义，验证器证明那个特定的全零辅助位块与目标哈密顿量成比例，并自动推断次归一化因子；随后通过抽取 QSP 层实现的多项式变换并认证其近似误差来验证 QSP 层。这种结构感知抽象对可扩展性至关重要：组合已验证的块编码与 QSP 包装后，估计宏展开规模约 152 万门；验证器只认证块编码一次，并通过抽象接口检查 QSP 层，无需展开 oracle 调用。",
    "2610.38214": "编码智能体通常拿到端到端行为规约（测试与输入输出样例），要求其产出的代码满足这些规约。但开发者需要提供多少条、提供哪些规约，才能让智能体产出其想要的程序？本文认为这无法先验判定，因为它取决于实现的结构，而结构留给智能体决定。智能体先承诺一个结构——分解为数据类型、模块与函数——这固定了一类候选程序；行为规约再在该类中选出程序。对一种结构足够的测试，对另一种结构可能严重欠定，需要不同边界或指数级更多样例。由于结构由智能体选定，开发者不逆向工程数千行生成代码就无法确认规约完备。为此作者提出 Skeleton Coding：开发者以高层、类代码格式共同指定结构。",
    "2610.38438": "大语言模型常通过系统提示词被塑造为特定角色，如导师、面试官或代表组织行事的智能体，提示词规定了它们应如何行为。但在与真实且可能带问题的用户进行多轮交互时，模型实际能在多大程度上遵守这些角色规约，研究不足。为此本文提出「用户行为 fuzzing」：在合理用户行为上做引导式搜索，以找出能让模型违反角色规约的行为；并实现 RoleFUZZER，把软件测试中的覆盖率引导 fuzzing 迁移过来以操作化该搜索。RoleFUZZER 依据用户行为覆盖网格构造场景，该网格把用户交互类型的接地分类与被测模型的角色规约（即受压的是什么）交叉。作者用 RoleFUZZER 在五种角色规约上评估多个 LLM，包括导师、财务顾问、AI 面试官、对抗性角色扮演角色与受组织政策约束的 web 智能体。",
    "2610.39504": "可达性的否定判决会把一条发现从人工复核中移除。本文用执行来核验这类判决。流水线 SourceLens 把 Semgrep 发现映射到 Python 程序的调用图，其边取自 Joern 在代码属性图中连接的调用。作者在覆盖率下运行 PyCG 宏基准中两个命令行程序（基准的手工调用图与 Joern 不一致），并记录函数之间的实际调用。在这些边上，asciinema 有 123 个函数从程序入口不可达；而项目自带的集成脚本执行了其中 86 个，作者的全部运行执行了 113 个。在 Sublist3r 中，24 个里有 19 个被执行。最新版 Joern 给出相同判决。缺失的调用经由值传递（如作为参数传递的类与函数），或根本没有调用表达式（如 with 块与属性读取）。在 asciinema 中，仅 4 条缺失边就使 113 个被执行函数中的 50 个变为可达。手工调用图同样缺少观测到的调用，在 asciinema 中许多是属性读取与 with 块。",
    "2610.39981": "大规模科学工作流运行在分布式 HPC 资源上，这使「科学数据产品如何生成、为什么相似的工作流执行会给出很不同的结果」难以解释。现有系统通常只关注分布式工作流执行或只关注溯源管理，很少把细粒度溯源当作分布式科学数据产物的内在属性。本文提出 TRACEs（面向高级容器化执行的可追踪运行时）：一种面向分布式容器化科学工作流的溯源架构，把数据血缘与执行上下文直接嵌入每个生成的数据产物。通过将溯源与工作流编排解耦，TRACEs 把以产物为中心的溯源从本地容器运行推广到分布式工作流，同时保持与既有工作流管理系统的兼容。作者在一个跨多台 HPC 节点的七阶段大肠杆菌变异检测工作流上评估 TRACEs，结果显示分布式执行下溯源完整性达 100%，中间存储约减少 59%。",
    "2610.38337": "优化与重构等软件工程任务追求保持组件行为，因而需要评估功能相似性的方法。已有研究探索过证明功能等价的形式化方法，以及用机器学习近似的方法；前者无法扩展、也不量化相似程度，后者在存在细微语义差异时表现不佳。差分模糊测试为在语义层面比较程序提供了可扩展途径，但应用它往往需要大量人工为特定程序对构造合适的输入生成器。为应对这一挑战，本文提出 DIFUZZI，其中包含一个基于 LLM 的生成器合成步骤，该步骤经迭代验证与修复。通过自动化这一步，DIFUZZI 为差分模糊测试的更广泛应用铺平道路。",
    "2610.39354": "本文考察整数上是否存在一种拓扑，使其连通子集恰为连续整数集合。主结果对每个整数格 Z^n（n>0）给出构造，Z 的答案作为推论得到。作者证明由坐标和的奇偶性确定的邻域构成基，且拓扑连通性与「经单位格步的有限路径可达」完全一致。文中还给出演绎审计，以及该论证与 Lean 4 及 Mathlib 中验证之间的对应，包括空集情形与整数区间的独立形式刻画。该构造与数学结果源自 Dan Marcus 提出、1970 年由克利夫兰州立大学小组解决的 Problem 5712；本文贡献详细阐述与形式验证报告。",
    "2610.38616": "序维护要求一个数据结构在插入与删除下维护元素序列，并回答两个元素谁在前。本文给出一个由已发表组件拼成的算法，每次操作最坏情况常数时间，并在 Lean 4 中验证。算法是一个深嵌入 Lean 的随机存取机程序，其解释器对每条指令计数。作者证明该程序对每个查询的回答与一个简单参考规约一致；每次操作至多需要固定步数，与元素个数和历史无关；且在 t 次操作后，它已计算出的任何值都不超过 O(log t) 位，因此可在字长为该规模的机器上原样运行。一条精确保留步数的验证翻译把高层证明与机器程序连接起来，因此解释器是唯一需要信任的代价模型。一个未经验证的原生实现展示了该算法的实际开销。",
    "2610.39926": "域泛化语义分割之所以困难，是因为它要求在训练时完全不接触目标域数据的情况下，对未见域做准确稠密预测。现有方法通过数据多样化、不变性学习或直接使用基础模型提升迁移性，但往往难以同时压制域敏感干扰与保留细粒度空间线索。本文提出 SIFR：一个频域感知的双流框架，在融合与解码两个阶段同时应对域偏移。SIFR 以谱建模作为统一原则，同时调控异构先验交互与稠密解码器精化。它不做冻结 CLIP 与 DINOv2 特征的直接融合，而是执行谱引导的不变融合，滤除域敏感响应，同时保留互补的语义与结构信息。此外，SIFR 引入谱解码精化模块，通过基于低频统计的归一化与自适应频域选择来稳定多尺度解码器特征。",
    "2610.38245": "逆合成规划寻求从可购买起始原料到目标分子的合成路线。在预测反应上搜索可以把目标连到可用原料，但一条不可行的反应会使得到的路线作废。仅在搜索结束后评估路线质量，无法纠正搜索过程中犯的错误。本文引入 Verification-Guided Reflow（VGR），把反应验证作为 AND/OR 搜索中的一个决策动作：验证结果表示为二元判决，查询由搜索结构调度，获得的判决用于排除反应或调整搜索优先级。作者把「已验证可解率」定义为：找到一条被验证器逐步接受的完整路线的目标所占比例。在 Retro190 上，把验证结果反馈进搜索使已验证可解率相对「无反馈的路线评估」从 51.1% 提升到 62.6%。进一步受控实验显示，更早验证与立即优先被接受的反应各自都能改善路线发现，但两者结合反而更差。",
    "2610.39735": "本文为一类一般的协调参数化变换系统建立形式语义，以 Transformer 为范式起点，但抽离其特定数学实例。表示向量同时获得外延指称与有序内涵解释；参数结构获得相对的、第二层解释，用以确定参数性质如何被保持、替换或组合。由此得到「变换概念」：一种数值作用与相应性质层映射相协调的参数化变换。随后作者区分这类系统共同的代数-语义内核与其架构特有的功能组织，从而使同一抽象系统类型可有不同数学实例与机械实现。该框架应用于注意力头与残差连接，给出的语义解释只依赖共享的代数-语义内核及其局部功能组织，因而可推广。",
    "2610.39454": "运行期规划——例如边行动边重规划的机器人——需要规划器能读懂用户书写的 PDDL（持续动作、数值资源、时间窗、连续变化），快速作答，并只给出经过验证的计划。专用规划器在 PDDL 的各个片段上很强，但它们在覆盖范围、时延以及失败含义上各不相同。本文研究：能否依据每个任务的语义选择异构引擎，从而在 STRIPS 到 PDDL+ 的范围内获得较广覆盖，同时与专用规划器保持竞争力，并明确每个答案的保证。Kairos 对每个任务做剖析，决定五个引擎中哪些适用（接地启发式搜索、压缩与 snap-action 时序搜索、混合动力学的时间步、提升搜索），并在统一的时间与内存预算下调度它们。每个候选计划都由独立于规划器变换的验证器检查；只有当「搜索穷尽即为证明不可解」的搜索真正耗尽空间时，才报告不可解。在九个比较套件的 1756 个任务上，Kairos 求解了其中大多数。",
    "2610.39007": "开发模拟与混合系统需要大量领域知识，而这些知识难以在形式规约中表述；若不加额外努力，这些领域知识对机器学习方法也不可用。本文提出一种用于分析与监控实值信号的混合方法，把基于规约的技术与数据驱动技术结合起来：用带区间操作的正则表达式识别信号中的感兴趣区域，用经典信号处理方法提取有语义的特征，并用半监督机器学习推断区分正确与故障行为的复杂关系。从正常行为数据学到的关系，可自动检测同一系统或其变体中的错误行为。作者在电压调节器上评估该方法，展示了检测非期望系统行为的有效性。",
    "2610.38697": "本文提出 SatOps-Decision：一种面向卫星通信操作低延迟决策的方法。据作者所知，这是 Jev 风格通用判别式决策模型在卫星操作上的首次应用，配套基准也是该方向首个。学习得到的打分器是一个本地适配的 Laya 编码器及其原生决策头，在单次前向中从给定的操作答案中做出选择。该基准通过可审计的构建方式，把撰写的操作契约、受控状态变化与独立校验的标签结合起来。评估优先关注完整请求时延与原始决策准确率；所有主要准确率比较使用同一组 1024 条留出问题，与训练和开发数据分离。SatOps-Decision 的本地打分器中位时延为每次决策 90.3ms，而 Qwen3.5-0.8B 生成为 493.9ms、OneJev1.6-0.8B 为 388.4ms，按实测 FP32/MPS 实现的中位请求时间计分别快 5.47 倍与 4.30 倍。其平均原始准确率为 85.3%。",
    "2610.40551": "随着 AI 数学能力迅速提升，有意义的基准正从大学水平题目与数学奥赛转向研究级数学。Ramanujan Challenge 是一个由数论研究级问题构成的基准，其中包含未发表结果与开放猜想：它给出数学常数的具体公式，其正确性可数值校验，而证明可能需要非显然的数学。本文分析该挑战的提交，测度不同 AI 模型、计算机代数系统（CAS）与形式工具的相对成功率。作者发现了一些与官方解答在概念上不同的正确提交，以及一个已发表开放猜想的证明。评估这些提交还暴露了第二个挑战：大规模可靠地判定复杂证明。为此作者提出一个 AI 辅助评估流水线，面向自然语言证明、CAS 代码与 Lean 形式化，评估其语义与逻辑正确性；与传统一次性 LLM 判分相比，该流水线降低了误判。",
    "2610.39191": "产后抑郁（PPD）是美国孕产妇死亡的首要原因，但在 PPD 的筛查、识别与治疗方面仍存在显著缺口。一个主要挑战源自现有早期 PPD 诊断及后续监测与干预方法的局限。融合交互界面与连续可穿戴生物传感器的移动技术，在增强临床决策与改善 PPD 照护方面具有很大潜力。要有效开发此类系统，存在若干值得投入的研究方向：用户体验设计、围产期阶段的传感精度、临床集成与互操作、接受与采纳，以及隐私与伦理。本文聚焦以女性及其体验为中心的可穿戴设备，讨论 HCI、包容性生理计算与女性健康交叉处的这些挑战与机会。",
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
