# 配置与画像

两个文件都在**首次运行**时自动生成，生成后就是你的个人数据，不进版本库：

| 文件 | 从哪来 | 管什么 | 页面上怎么改 |
| --- | --- | --- | --- |
| `config.json` | `config.example.json` | 抓哪些分类、PDF 存哪、每期几条 | `/profile` → arXiv 类别 / 下载目录 |
| `interests.json` | `interests.example.json` | 画像：主题、熟悉作者、代表系统、降权词、画像主来源 | `/profile` 各区块；`tools/preset.py` |

初始化规则：文件**不存在**才生成；存在就完全以你的文件为准（缺字段走代码内默认值）。
想恢复出厂设置：删掉这两个文件（或整个 `output/`）再跑一次。

---

## 一、`config.json`

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `download_dir` | `papers` | PDF 保存目录。支持相对路径（相对项目根）与绝对路径；不存在会自动创建。**这是唯一真源**，页面上显示的路径也取自这里 |
| `categories` | `["cs.AI","cs.CL","cs.LG","cs.SE"]` | 主分类：每日必抓，「为你推荐」和「分类详解」都来自这里 |
| `category_names` | 见示例 | 分类的中文名（只影响显示）。留空自动匹配内置词典，仍无则显示分类号 |
| `window_days` | `3` | 抓最近几天的公告（arXiv 每工作日 20:00 ET 公告一次，3 天可覆盖周末） |
| `max_results_per_cat` | `80` | 每个主分类最多抓多少条 |
| `top_recommend` | `14` | 「为你推荐」显示条数，同时也是候选池上限 |
| `top_expand` | `10` | 「兴趣扩展」显示条数 |
| `expand_categories` | 15 个 | 扩展分类池：只用于「兴趣扩展」区，不进入主推荐打分 |
| `expand_window_days` | `3` | 扩展抓取的时间窗 |
| `expand_max_results` | `600` | 扩展抓取的全局上限（所有扩展分类合计） |
| `affil_targets` | `60` | 每期解析多少篇的作者单位（**很慢**，约 3s/篇；`--skip-affil` 可跳过） |
| `port` | `8765` | 本地服务端口（`server.py` 与 `start_digest.bat` 都读这里） |

改分类后需要**重新抓取**（`python run_daily.py`）才会出现新分类的论文；删分类只影响下次抓取，
已抓到的数据留在 `output/` 里。

## 二、`interests.json`

```jsonc
{
  "owners":     [ /* 画像主来源：显示在 /profile 与摘要页头部 */ ],
  "topics":     [ /* 研究主题：关键词命中即加分 */ ],
  "people":     [ /* 熟悉研究者：作者名命中 +10 分/篇 */ ],
  "signature_systems": [ /* 代表系统：标题/摘要命中 +6 分 */ ],
  "negative":   { "weight": -1.0, "keywords": [ /* 降权词 */ ] },
  "behavior":   { /* 行为学习的超参，一般不用改 */ }
}
```

### `owners[]` — 画像主来源

摘要页头部「基于 A × B × C 的兴趣画像」就是从这里来的（取 `label`，没有则取 `name`）。

| 字段 | 说明 |
| --- | --- |
| `name` | 姓名，唯一键（改名请走 `/profile` 的「编辑」，它会按原名定位） |
| `label` | 头部显示的简称，留空回退到 `name` |
| `site` / `affiliation` | 主页与机构，卡片展示 |
| `interests` | 一句话研究兴趣 |
| `signature_topics` | 代表方向（每行一条，卡片最多显示 4 条） |
| `people_linked` | 是否同步计入 `people`（作者命中 +10/篇）；删除该来源会一并撤销 |

### `topics[]` — 主题

| 字段 | 说明 |
| --- | --- |
| `name` | 主题名（显示用，也是行为学习倍率的 key） |
| `weight` | 种子权重，默认 1.0。越大越容易把该主题的论文顶上来 |
| `keywords` | 关键词/短语列表。命中标题每个 +4（最多算 4 个），命中摘要每个 +0.8（最多 15 个），再乘 `weight` |

> **顺序不变式**：`topics` 的顺序 = 前端重排用的权重索引顺序。代码里由
> `customize.effective_topics()` 统一拼接（原主题 + 「我的来源关注」自定义主题），
> 不要手工在别处重排。

### `people[]` / `signature_systems[]`

- `people`：姓名列表，**大小写不敏感的整名匹配**（例如 `"Ada Lovelace"` 命中作者列表即 +10）。
- `signature_systems`：系统/工具名，按词边界匹配标题或摘要，命中 +6。

### `negative`

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `weight` | `-1.0` | 每个降权词命中扣 `weight × 3`，最多算 4 个 |
| `keywords` | `[]` | 与你主线无关的热点词（只降权，不排除，仍会出现在分类详解里） |

### `behavior` — 行为学习

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `actions` | 见示例 | 各类行为的学习强度：`favorite 1.0` / `download 1.3` / `pdf 0.55` / `abstract 0.3` / `downvote -1.6` / `unfavorite -0.7`（负数表示该行为反向学习） |
| `lr_topic` / `lr_keyword` | `0.15` / `0.12` | 每次行为对主题倍率 / 关键词权重的学习率 |
| `topic_range` | `[0.25, 3.0]` | 主题倍率的上下限（防止一次误点把某个主题打死） |
| `keyword_range` | `[-4.0, 4.0]` | 关键词权重的上下限 |
| `downvote_paper_penalty` | `-12.0` | 被 Downvote 的单篇论文固定扣分 |
| `learn_neg_topics` / `learn_neg_keywords` | `false` | **负向行为是否参与全局学习**。默认关闭：Downvote 只惩罚这一篇，不改写你的主题画像（否则会被曝光偏置带偏，越推越偏） |

## 三、运行时产物（`output/`，不进版本库）

| 文件 | 说明 |
| --- | --- |
| `raw.json` / `raw_expand.json` | 累积抓取池：只并集不删除；RSS 降级时按短号增量合并 |
| `recommend.json` / `expand.json` / `papers_index.json` | 当期打分与前端索引 |
| `summaries.json` / `rec_notes.json` / `highlights.json` / `themes.json` | 编辑性内容（中文摘要、推荐理由、看点、主题归纳），可手工补 |
| `library.json` | 收藏 / 下载 / Downvote 记录 |
| `profile_state.json` | 行为学习得到的主題倍率、关键词权重、单篇惩罚 |
| `archive.db` + `archive/` | 归档：`seen` 判定「本期新增」，每期快照只增不改 |
| `interests_extra.json` | 「兴趣来源」解析出的增量（人名 / 关键词 / 命中主题） |
| `backup/` | 导入预设时自动备份的旧配置 |

## 四、环境变量

| 变量 | 作用 |
| --- | --- |
| `ARXIV_DL_PROXY` | 强制指定下载 PDF 的代理（如 `http://127.0.0.1:7890`），跳过自动探测 |

端口、代理、下载目录都可以按上面的配置文件改，不需要环境变量；`ARXIV_DL_PROXY` 只是
在自动探测失败时的强力手段（见 `docs/ARCHITECTURE.md` 的「下载取数」）。
