# -*- coding: utf-8 -*-
"""2026-11-23 批次：本期 24 篇待补论文的双语简介（summaries.json）。

- summaries.json 的 value 为 {"en","zh"}；已存在且完整的不覆盖。
- key 一律 arXiv 短号。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")

SUMM = {
    "2611.25066": {
        "zh": "DVBench 是首个面向真实 UVM 设计验证智能体的端到端基准：既有基准把验证拆成互不耦合的子任务，偏离真实工作流。DVBench 含 9 个功能域、5 个难度等级的 95 个任务，要求智能体独立完成从特性清单、测试计划、参考模型到最终 testbench 的全流程，并按编译、覆盖率、缺陷检出评最终产物，同时评中间产物。评测前沿 LLM 与智能体框架，最好成绩仍远未饱和。",
        "en": "DVBench is the first end-to-end benchmark for real-world UVM design verification agents, with 95 tasks across 9 functional domains and 5 difficulty levels that require the full verification workflow and grade both final testbenches (compilation, coverage, bug detection) and intermediate artifacts.",
    },
    "2611.26588": {
        "zh": "「通过的回归只说明设计在 scoreboard 检查范围内与参考模型一致，不说明满足规格」。本文提出 Verify the Verifier：让基于 LLM 的异常交叉检查器在回归通过后，拿波形轨迹对照规格找「scoreboard 逃逸」。向四款 OpenTitan IP 注入 564 个缺陷，其中 68 个为候选逃逸（非等价、被测试覆盖却通过），框架确认 41 个确属逃逸，并给出在缺陷版失败、原版通过的断言。",
        "en": "Verify the Verifier introduces an LLM-based anomaly cross-checker that examines a passing regression's traces against the specification, confirming 41 of 68 candidate scoreboard escapes among 564 injected bugs in four OpenTitan IPs with assertions failing on buggy designs and proven on originals.",
    },
    "2611.24979": {
        "zh": "PLC 长期运行但源码常常丢失，而每个输入输出都被持续记录。本文问：LLM 能否仅凭 I/O 轨迹恢复可执行的 IEC 61131-3 结构化文本程序，以及恢复结果如何验证？作者构建「生成—重放—反馈」流水线：LLM 从轨迹压缩摘要写出候选程序，逐扫描周期执行并与记录比对，失配处回传再改，最多三轮。结果先在两款独立开源 PLC 运行时上校验，排除执行环境造成的假差异。",
        "en": "Trace2ST recovers executable IEC 61131-3 Structured Text programs from I/O traces alone via a generate-replay-feedback pipeline that replays candidates one scan cycle at a time and returns mismatching trace segments for at most three revisions, validated against two independent open-source PLC runtimes.",
    },
    "2611.26333": {
        "zh": "海洋工程数值仿真建模依赖专家经验，而代码能跑通并不等于模型与结果满足工程要求。OceanCoder 以 Qwen3-8B 为底座：用可扩展数据流水线产出覆盖 12 类工程任务的 12000 条已验证 SFT 样本；三层验证框架分别核对输入是否合工程参数与任务约束、必需仿真分析是否完成、输出是否工程上合理，并把结果转成分级奖励驱动 GRPO。同时构建该领域首个自动化建模基准。",
        "en": "OceanCoder is a Qwen3-8B-based model for automated simulation modelling in ocean engineering, trained on 12,000 verified SFT examples across 12 task categories and steered by a three-layer verification framework whose graded outcomes feed GRPO rewards, plus the first benchmark for the domain.",
    },
    "2611.25542": {
        "zh": "对既有燃料物流信息系统做作者自评式再评估：把从源码重建的基线 R0 与修订版 SQL Server 系统 R1 在 12 个场景下对比。R1 在受控测试中改善数据集成与报表准确性，并新增库存移动记录、自动告警与恢复控制；集成缺陷率由 R0 的 2.90%–3.46% 降到 R1 的 0.14%–0.49%。但全国周需求预测上，所选方法未显著优于「上年同期均值」，过程与中断仿真的收益也依赖建模假设。",
        "en": "An author-led re-evaluation compares a reconstructed source-derived baseline with a revised SQL Server fuel-logistics system across twelve scenarios, reporting integration defect rates falling from 2.90-3.46% to 0.14-0.49% while weekly demand forecasting did not significantly beat the previous-year mean.",
    },
    "2611.26311": {
        "zh": "既有编码智能体几乎都被直接告知目标（需求、原型或演示）。本文反过来问：智能体能否只靠「使用」来理解一个陌生软件并把它重建出来？在 SWE-Recreation 中，智能体只见渲染像素、仅通过指针与键盘操作，无 DOM、源码、日志或后端。基准含 54 个真实应用（28 个网站、26 个 Android 应用）与 1446 条隐藏需求；五个前沿系统最高仅 0.530 加权保真度、22.9% 需求完全复现。",
        "en": "SWE-Recreation benchmarks agents that see only rendered pixels and interact via pointer and keyboard to rebuild 54 real applications against 1,446 hidden requirements, where five frontier systems reach at most 0.530 weighted fidelity and 22.9% fully reproduced requirements.",
    },
    "2611.26312": {
        "zh": "静态分析器便宜且广泛部署，其告警可作为安全代码生成的反馈信号。既有做法把分析器塞进迭代修复环，代价高且难以隔离报告本身的作用。本文改为在生成过程中给提示：一旦告警就回滚，把发现以代码注释（Comment）或用户消息（Steering）注入。三个模型、三个 Python 基准上，生成期引导只需基线的 0.9–1.9 倍输出 token（迭代法最高 24.1 倍）；DeepSeek-V4.1-flash 在 RiskyPy 上把「功能且安全」比例从 52.5% 提到 64.4%。",
        "en": "Two strategies inject static-analyzer findings during generation (as a code comment or a user-message steering hint) after rolling back, reaching 0.9-1.9 times baseline output tokens versus up to 24.1 times for iterative repair, and lifting functional-and-secure programs from 52.5% to 64.4% in one setting.",
    },
    "2611.25078": {
        "zh": "长上下文解码中 HBM 容量决定并发度。稀疏注意力模型自带 indexer，每步用 indexer cache 给全部历史条目打分。作者发现一旦主 KV 下沉到主机内存，indexer cache 就成了新瓶颈：1M token 下占单请求 HBM 的 63%（Qwen）与 75%（V4.1）。Twindex 只在 HBM 留紧凑副本、全量放主机内存，由副本粗选出候选集，再用模型自身 indexer 在主机侧原行上精选 top-k；不改权重、兼容 CUDA 图，1M token 下并发分别提升 1.78/1.62/3.03 倍。",
        "en": "Twindex keeps only a compact learned copy of the indexer cache in HBM and the full cache in host memory, using coarse-to-fine selection to fit 1.78x, 1.62x and 3.03x as many 1M-token requests as KV offloading alone, without changing model weights.",
    },
    "2611.24990": {
        "zh": "流畅回答不等于可验证回答。本文问单卡消费级 GPU 上的小型开放模型能否从 SEC 文件中抽数，并给出机器可查的证据（页码 + 含该数字的逐字引用）。Filing-Evidence 含 45 家美国公司 90 份 10-K/10-Q 上的 1000 道题，答案取自 inline XBRL。十个 7–21B 模型在单张 RTX 4090 上评测：带可查证据的准确率 17.1%–82.7%（最好 Qwen3.5-9B 84.5%）；但每千题仍有 16–167 个错误值通过全部检查，其中 57% 是量纲/单位错误。",
        "en": "Filing-Evidence benchmarks small open models on 1,000 questions over 90 SEC filings requiring page-and-verbatim-quote evidence, finding accuracy from 17.1% to 82.7% (best 84.5%) while 16-167 wrong values per 1,000 still pass every automated check.",
    },
    "2611.25790": {
        "zh": "CyberGym 以「PoC 使漏洞版崩溃、修复版不崩」判漏洞复现成功，但这要求任务材料自洽且 PoC 真命中目标缺陷。本文对全部 1507 个任务做材料审计、对一次完整 GLM-5.3 Level-1 运行的最终 PoC 做身份评估：338 个任务（22.4%）被标为不一致，最大类是覆盖不一致（205）与描述/补丁共同指向另一缺陷（110）；1286 次差分通过中 89 个判定非目标、10 个证据不足，要求命中目标后通过率显著下降。",
        "en": "A material audit of all 1,507 CyberGym tasks labels 338 (22.4%) inconsistent, and PoC identity assessment over 1,286 differential passes finds 89 non-target and 10 insufficient-evidence verdicts, lowering the pass rate once a target hit is required.",
    },
    "2611.26451": {
        "zh": "star-M 张量代数把矩阵 SVD 的最优压缩保证推广到高阶张量：t-SVDM-I 用一组可逆变换加逐切片截断 SVD 计算，自适应的 t-SVDM-II 可按误差容限定各切片秩。既有实现仅限共享内存，难以支撑现代大规模数据。本文给出 t-SVDM-I/II 的首个分布式内存实现并推广到 N 阶张量，用异步非阻塞通信做数据重分布，128 节点（6144 核）上并行效率不低于 70%。",
        "en": "StarMPI-SVD provides the first distributed-memory implementations of t-SVDM-I and t-SVDM-II generalized to N-way tensors, using asynchronous non-blocking redistribution to sustain at least 70% parallel efficiency on up to 128 nodes (6,144 cores).",
    },
    "2611.25394": {
        "zh": "复用开源代码中的漏洞会随编译进入已部署二进制，定位需做源码到二进制的函数匹配；而按同样构建配置重编译源码通常不可得，反编译结果又与源码差异过大。本文提出「行为包含」性质：编译改变代码但基本保留行为。SBIND 据此反编译二进制，用「行为路径」（入口到出口的规范化操作序列）表示函数并按序对齐源码路径，从而检出 1-day 漏洞，而不比较代码文本。",
        "en": "SBIND decompiles a binary and checks behavioral containment instead of comparing code, representing functions as behavioral paths of normalized operations aligned in order between source and binary, enabling 1-day vulnerability detection without matching build configurations.",
    },
    "2611.26435": {
        "zh": "LLM 智能体的多轮程序上下文不断增长，服务受 KV cache 容量限制。既有压缩多等缓存跨过大阈值后一次性摘要大段历史，且常与被服务请求争抢算力与显存。Aggron 改为每轮都摘要、且只选择性压缩 KV cache 的特定部分，使摘要请求保持轻量、精度不降；当请求队列出现队头阻塞时，从独立的「摘要队列」发起这些请求，从而在不牺牲吞吐的前提下摊平压缩成本。",
        "en": "Aggron summarizes agentic requests at every turn while selectively compressing only certain parts of the KV cache, launching lightweight summarization requests from a separate queue during head-of-line stalls to preserve accuracy without competing with served requests.",
    },
    "2611.25912": {
        "zh": "合并分支时版本控制系统要算最近公共祖先（merge base），而提交图不是树而是任意有向无环图；无公共祖先时甚至要遍历整图，数百万顶点需数十秒，用户可感知。本文指出提交图存在额外结构——支撑分支（supporting branches），抽取后可对图做预处理显著加速查询；若去掉支撑分支能把图分解为有界规模的连通分量，则可进一步给出更强的复杂度保证。",
        "en": "Exploits the extra structure of supporting branches in the version-control commit graph to preprocess it and substantially accelerate lowest-common-ancestor (merge base) queries, with stronger guarantees when removing supporting branches decomposes the graph into bounded-size components.",
    },
    "2611.26313": {
        "zh": "强化学习要满足时序安全约束（形式规约），既有做法把逻辑公式转成自动机做状态增广与奖励塑形，但这假定自动机构造可行且可处理，实际只适用于小规约与 LTL。Actor-Predictor 不显式构造自动机，而是学习逻辑进度的代理表示：预测器持续估计部分轨迹后续是否满足规约，其特征作为 actor 的辅助输入，用 GRPO 与 RWR 优化。理论证明预测足够准确时该表示等价于自动机状态；网格世界与 Isaac Lab 机器人任务上优于自动机基线。",
        "en": "Actor-Predictor learns a surrogate representation of logic progress instead of constructing automata, feeding a predictor's features to an actor optimized with GRPO and RWR, and proves the representation is equivalent to automaton state under sufficient predictive accuracy.",
    },
    "2611.25599": {
        "zh": "自主智能体可执行任意 shell 命令，可能造成未授权网络请求或对文件、进程、权限的持久改动。既有防护要么靠 LLM 监控（无可证明保证），要么是无状态策略层（抓不到多步数据流与策略语言未建模的副作用，如 Python 脚本内发起的网络调用）。Tether 在临时隔离沙箱里执行每个待执行动作，从系统调用推断抽象动作语义，再用 Lean 4 内嵌 DSL 写的有状态策略裁决，合规才放行。",
        "en": "Tether executes each proposed agent action in an ephemeral isolated sandbox, infers abstract action semantics from observed system calls, and enforces stateful security policies written in an embedded Lean 4 DSL so that multi-step data flows and unmodeled side effects are captured.",
    },
    "2611.25071": {
        "zh": "FinVeriQA 是面向 SEC 文件与实时行情数据的开源多智能体金融问答原型，核心主张是「让合适的组件做合适的事」：紧凑的类型化决策模型 Laya 负责路由与筛掉投资建议类请求（路由 0.85 对 Mistral-7B 的 0.52），所有数字交由 Python 计算（100% 对 29% 正确率），检索与工具负责取证，Mistral-7B 只写带引用的答案，代码校验器核对引用 ID 存在、数字与算稿一致，整条流水线经 MCP 服务器暴露；接入实时报价把价格误差从 210% 降到 0.00%。",
        "en": "FinVeriQA is an open-source multi-agent financial QA prototype over SEC filings and live market data in which a typed-decision router handles routing (0.85 vs 0.52), Python computes every number (100% vs 29%), and a code validator checks cited IDs and numeric consistency, exposed through an MCP server.",
    },
    "2611.26094": {
        "zh": "CAN 总线缺乏内置安全机制，伪装攻击通过模仿正常通信注入恶意报文，传统入侵检测难以识别。既有基于图的检测多用浅层嵌入、把表示学习与分类解耦，未能充分利用结构与信号级信息。PhantoMasq 把 CAN 流量建成消息序列图，叠加由信号行为导出的轻量统计特征，将检测表述为图级分类并用图卷积网络求解，在 ROAD 数据集上按防泄漏协议评测。",
        "en": "PhantoMasq models CAN traffic as message sequence graphs enriched with lightweight signal-derived statistical features and solves masquerade-attack detection as graph-level classification with graph convolutional networks on the ROAD dataset.",
    },
    "2611.25303": {
        "zh": "本文为多项式向量场常微分方程的可达性计算结果提供证明格式与检查器，地位类似 SAT 求解的 UNSAT 证明检查，但因 ODE 的数值本性而更棘手。证明用微分动态逻辑 dL 表达，可由 KeYmaeraX 等符号定理证明器独立核验，且能由基于 Taylor 模型的算法自然生成。本文证明这类证明是完备的：只要某（可能不可信的）算法用 Taylor 模型正确算出了近似，就能自动生成并在 dL 证明演算中通过检查。",
        "en": "Introduces a proof format and checker, expressed in differential dynamic logic and checkable by KeYmaeraX, for certifying ODE reachability computations, and proves completeness: any correctly computed Taylor-model approximation admits an automatically generated, checkable proof.",
    },
    "2611.25724": {
        "zh": "红外小目标尺寸小、纹理弱、边界模糊，且类目标背景结构会在多个尺度产生显著响应，仅靠响应强度不足以可靠判别。VBE-UNet 主张「先验证再增强」：反事实背景解释刻画局部目标证据，联合证据验证整合跨尺度支持与基于扰动的贡献核验，据此引导特征重组；得到的可靠性估计再驱动选择性特征精修，强化目标响应、抑制无支撑的背景激活。在 IRSTD-1K、NUDT-SIRST、NUAA-SIRST 上验证。",
        "en": "VBE-UNet verifies before enhancing: counterfactual background explanation and joint evidence verification (cross-scale support plus perturbation-based contribution checks) produce reliability estimates that guide selective feature refinement for infrared small target detection.",
    },
    "2611.25927": {
        "zh": "潜空间世界模型能预测动作序列的后果，但在测试时靠递归 rollout 比较候选方案代价高昂。Fast-JEPA 重组预测计算以支撑低代价的动作序列搜索：先构造目标导向的计划引导搜索，再直接预测完整候选的结果用于比较，从而在精修阶段免除递归状态展开。PushT、Reacher、Cube、TwoRoom 上平均成功率 96.50%，规划比 INTACT 快 2.41 倍；另提出 DynaGoal 基准评测动态分布外、执行截止期与受控响应延迟下的表现。",
        "en": "Fast-JEPA reorganizes latent world-model prediction to score complete candidate action sequences directly instead of recursively rolling out states, reaching 96.50% average success with 2.41x faster planning than INTACT, and introduces the DynaGoal benchmark.",
    },
    "2611.25325": {
        "zh": "当代 AI 智能体由「固定语言模型 + 通用计算设备」耦合而成。本文证明这种耦合使安全性不可判定：给定某个危险程序，没有任何算法能预测智能体会不会运行一个语义等价的程序；护栏、黑白名单与认证只能给出不完美的安全方案。在有限约束（有界上下文、取值与运行时间）下安全可判定但仍不可行——即便智能体描述已知，问题也是 PSPACE 完全的；此外安全性不是组合性质：各自可证安全的智能体组合后仍可能产生不安全行为。",
        "en": "Shows that coupling a fixed language model with a general computing device makes agent safety undecidable, that under finite constraints the problem remains PSPACE-complete even with a known agent description, and that safety is not compositional across agents.",
    },
    "2611.25583": {
        "zh": "LLM 智能体依赖持久记忆规划工具调用，因而面临记忆漂移：一条对抗性或误导性记忆会改变执行路径与最终结果。本文研究在线记忆漂移检测，需估计每条被检索记忆对潜在漂移的因果贡献。两个难点：内容级特征（困惑度、检索相关性）不足以支撑因果归因；逐条记忆反事实重放下游执行在线开销过高。DriftGuard 用两阶段框架把离线因果监督与在线估计解耦，先用成对反事实重放构造因果监督，再在服务时低成本估计。",
        "en": "DriftGuard detects memory drift online by decoupling offline causal supervision, built from repeated paired counterfactual replays, from a cheap online estimator of each retrieved memory's causal contribution to potential drift, avoiding the prohibitive cost of counterfactual replay at serving time.",
    },
    "2611.25582": {
        "zh": "RAG 系统的有效设计随任务与领域而变，开发需大量工程迭代。AutoRAGBench 是首个评测 LLM 智能体能否在开放代码空间从零开发 RAG 系统的基准，含 9 个开发任务；每个任务不给起手代码与既定策略，智能体在单张 H800、六小时预算内分析数据、实现流水线并依实验反馈迭代改进。评测九种智能体配置，既看最终系统效果也分析开发轨迹。",
        "en": "AutoRAGBench evaluates how well LLM agents build RAG systems from scratch in an open code space across nine tasks, under a six-hour budget on a single H800 GPU with no starter code, analyzing both resulting system effectiveness and development trajectories across nine agent configurations.",
    },
}

MERGE_NOTE = "2026-11-23 批次：补 24 篇双语简介。"


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
