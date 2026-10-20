# 术语表

按主题分组。每个术语给出**在本项目中的准确定义**（可能窄于通用含义），并指向详细文档。

---

## 一、论文与抓取

| 术语 | 定义 |
| --- | --- |
| **短号** | arXiv 论文的不带版本、不带前缀的编号，如 `2609.09742`。项目内**所有 JSON 的 key、所有接口的 `id`** 都用它。`paperutil.short_id()` 负责把 `arXiv:2609.09742v2`、PDF 链接等统一成短号 |
| **主分类**（`categories`） | 每日必抓的分类，「为你推荐」与「分类详解」的来源。**默认空**（不预设领域），在 `/profile` 里自选。见 [config.json](../reference/config.md) |
| **主类 / 子类**（`abc` / `def`） | 分类号的两段：`cs.DB` 的主类是 `cs`、子类是 `DB`。界面上两个联动下拉框分别对应这两段。9 个 archive（`quant-ph`、`hep-th`…）只有一段、没有点号。见 [arXiv 类别](../reference/categories.md) |
| **官方分类表** | `arxiv_cats.py` 里固化的 arXiv 分类快照（20 个 archive / 155 个分类），是校验、检索与扩展池推导的**唯一真源** |
| **拖拽排序** | `/profile` 里拖动类别标签改变 `config.json` 的 `categories` 顺序；该顺序 = 摘要页分类小节的顺序 |
| **扩展分类**（`expand_categories`） | 只用于「🌱 兴趣扩展」的邻域分类池。与主分类按短号**严格去重** |
| **累积池** | `raw.json` / `raw_expand.json`。RSS 降级时按短号并集合并，**只增不删**，所以会混着多个批次 |
| **本期新增** | 首次出现在本期的论文，由 `archive.db` 的 `seen(sid, first_date)` 判定。日报只渲染它 |
| **快照** | `output/archive/<YYYYMMDD>.{html,md}`，当期日报的副本，**只增不改** |
| **期号** | 形如 `20261017` 的日期字符串，标识一期日报 |

## 二、画像与打分

| 术语 | 定义 |
| --- | --- |
| **画像** | `interests.json`：主题、熟悉研究者、代表系统、降权词、画像主来源。它决定"谁排前面" |
| **画像主来源**（`owners[]`） | "我的画像来自哪些人/主页"的**说明性**条目。本身不参与打分；勾选 `people_linked` 才会把名字加进 `people` |
| **熟悉研究者**（`people[]`） | 作者名列表，命中一篇 **+10**（单项最高权重） |
| **代表系统**（`signature_systems[]`） | 系统/工具名，命中标题或摘要 **+6** |
| **主题**（`topics[]`） | 一组关键词 + 一个种子权重。是画像的主要结构 |
| **种子权重** | 你显式写在 `interests.topics[].weight` 的权重，默认 1.0 |
| **学习倍率** | 行为学习得到的方向性系数，存 `profile_state.topic_mult`，范围 `[0.25, 3.0]` |
| **主题实际权重** | `种子权重 × 学习倍率`。打分用的就是它；`/profile` 的 `themes[].weight` 是同一口径 |
| **主题原始分** | 一篇论文在某主题上的命中强度：`4×min(标题命中,4) + 0.8×min(摘要命中,15)`。不含权重 |
| **降权词**（`negative.keywords`） | 只降权不排除的无关热词，每个计 `weight×3`，最多 4 个 |
| **单篇惩罚**（`paper_bonus`） | Downvote 给该篇的固定 `-12`，与"方向级偏好"无关 |
| **兜底模式** | 严格阈值（推荐 ≥7 / 扩展 ≥9）一篇都不达标时，退化为按分数取前 N，并在卡片注明。`issue_core.json` 的 `mode` 字段记录是否发生 |
| **降级** | 抓取层面的备用通道：API 不可用时改抓 RSS。与"兜底"不是一回事 |

## 三、行为与反馈

| 术语 | 定义 |
| --- | --- |
| **行为**（action） | `favorite` / `unfavorite` / `download` / `pdf` / `abstract` / `downvote` / `undownvote`。各有权重，见 `behavior.actions` |
| **行为学习** | `profile.apply_event()` 把一次点击折算成主题倍率与关键词权重的增量 |
| **学习率** | `lr_topic`（默认 0.06）/ `lr_keyword`（默认 0.05），控制单次更新幅度 |
| **负向学习** | `downvote` 是否参与主题/关键词的**全局**更新。默认关闭，原因见[排序算法](../architecture/ranking.md) §5 |
| **曝光偏置** | "被推荐得多的主题也被 Downvote 得多"的系统性偏差。它是负向学习必须关闭的原因 |
| **乐观更新** | 点击后立即改 UI，请求在后台跑，失败再回滚。让界面点击零延迟 |
| **钉在原位** | Downvote 后卡片保持点击时的位次（`data-dvpos`）而不隐藏，便于撤销 |

## 四、兴趣来源

| 术语 | 定义 |
| --- | --- |
| **兴趣来源**（source） | 你贴进来的主页/论文/文档。解析出人名与专业实词作为画像增量，存放在 `output/interests_extra.json` |
| **来源类型** | `link`（网页）、`paper`（arXiv 论文）、`doc`（本地文档） |
| **派生增量**（`_derived`） | 全部来源汇总后的人名/关键词/命中主题，上限 60/60/10 |
| **「我的来源关注」** | 由派生关键词自动生成的**自定义主题**，权重固定 0.6。不是手写主题 |
| **屏蔽关键词** | 从来源增量中剔除某个词并触发重建；不影响手写主题关键词 |

## 五、运行时与网络

| 术语 | 定义 |
| --- | --- |
| **选路**（netroute） | 下载前探测哪条出口（直连/环境代理/本机代理）真能取到 `%PDF`，并缓存结果 900 秒 |
| **负缓存** | 全部出口都失败时缓存"无可用路由"45 秒，避免批量下载反复探测 |
| **库锁**（`_lib_lock`） | 只保护 `library.json` / `profile_state.json` 读-改-写，毫秒级；**网络 IO 绝不持它** |
| **单篇锁**（`dl_lock(sid)`） | 每篇论文一把：同一篇连点串行，不同篇并行 |
| **重建锁** | 保护 `/api/rebuild`，防止重复触发流水线 |
| **动态页** | `/favorites` `/profile` `/archive`，每次请求实时渲染（并重载模板模块） |
| **静态页** | 日报与归档快照，渲染一次即固定 |

## 六、数据文件

| 术语 | 定义 |
| --- | --- |
| **库文件**（`library.json`） | 收藏 / 下载 / Downvote 三个字典，key 均为短号 |
| **画像状态**（`profile_state.json`） | 学习到的聚合结果：`topic_mult` / `kw` / `paper_bonus` / `counts` |
| **行为流水**（`behavior.json`） | 最近 2000 条点击记录，仅用于审计与离线分析 |
| **前端索引**（`papers_index.json`） | 让浏览器用同一套公式重排分数所需的最小数据：`base` / `tv` / `toks` / `pen` / `weights` |
| **编辑性内容** | `summaries.json`（中文摘要）、`rec_notes.json`（推荐理由）、`highlights.json`（看点）、`themes.json`（主题归纳）。key 一律短号，可手工补 |
| **预设**（preset） | 一整套 `config.json` + `interests.json`，可用 `tools/preset.py` 导入导出 |

## 七、工程与文档

| 术语 | 定义 |
| --- | --- |
| **回归脚本** | `tools/*_check.py`，可独立运行、自带 setup/teardown 的验证脚本 |
| **探针** | `tools/ui_probe.py` 等开发期脚本，不属于发布闸门 |
| **发布闸门** | 提交前必须通过的五个回归，见[测试与回归](../contributing/testing.md) |
| **模板文件** | `*.example.json`，机器无关，被提交进仓库；首次运行据此生成本地文件 |

---

相关：[架构总览](../architecture/overview.md) · [interests.json](../reference/interests.md) ·
[数据文件](../reference/data-files.md) · [FAQ](faq.md)
