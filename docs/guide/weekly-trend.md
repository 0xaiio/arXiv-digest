# 周度趋势报告

日报回答「今天哪几篇值得我看」，靠个人的研究画像排序；**周报回答「这一周整个 cs 在
往哪走」**，靠全量语料的分布与变化。两者互不替代：

| | 日报 | 周报 |
| --- | --- | --- |
| 输入 | 你选的几个分类 + 3 天窗口 | **`cs.*` 全量**（约 3200 篇/周） |
| 排序 | 个人画像打分 | 无排序，只做聚合 |
| 产出 | 十篇精选 + 双语摘要 | 主题分布 + 异常增长方向 |
| 依赖 | 兴趣配置、行为学习 | 不依赖任何个人数据 |

周报**不挑文章、不逐篇翻译、不做推荐**——那是日报的职责。它只回答两个问题：
本周的主题结构长什么样，哪些方向的论文数量异常偏离历史。

## 数据口径

- **窗口**：期号往前回退 3 天后取 7 天。例：`20261115`（周日）→ `2026-11-06 → 2026-11-12`。
- **为什么回退**：arXiv API 只索引**已公告**的论文。周日上午运行时，最近一次公告是
  周五 09:00（周四批次），周五到周日的投稿要等下周一才出现。若直接取「最近 7 天」，
  窗口里只有 4 天是完整的，与上一周的 7 天对比会得出「全领域萎缩」的假信号
  （2026-11-15 实测：2371 篇 vs 基线 4652 篇，差的那一半正是尚未公告的论文）。
- **过滤**：arXiv API `search_query=cat:cs.* AND submittedDate:[start TO end]`，
  按提交日期切窗口，而不是按公告批次——趋势看的是「这一周投了什么」。
- **字段**：只取 `id / title / abstract / categories / published`。作者、单位、
  PDF 链接一律不取：用不上，而且能把每次抓取的体积压到最小（约 4 MB/周）。
- **缓存**：抓取结果落在 `output/trend_raw_<期号>.json`，`--skip-fetch` 可直接复用。

## 方法

**1. 切词与加权**

标题词 ×2 + 摘要词 ×1。标题是作者对主题的自我标注，比摘要里的背景描述更有
区分度。停用词表包含英文功能词、学术套话（paper / method / results / novel …）
与 LaTeX 残留（`varepsilon` / `mathrm` …）。

**2. TF-IDF**

```
tf  = 1 + log(count)
idf = log((1 + N) / (1 + df)) + 1
向量做 L2 归一化 → 点积即余弦相似度
```

词表只保留 `df ∈ [3, 0.5N]` 的词：太少是噪声（拼写、罕见缩写），太多没有区分度
（每篇都出现的词）。按 `df` 降序取前 4000 个，排序带词名兜底，保证同一批数据
永远得到同一份词表。

**3. 球形 k-means**

簇数 `k = clamp(8, 20, round(sqrt(N/20)))`，3200 篇 → 13 簇。

- **最远优先初始化**：先取权重和最大的一篇（信息量最大），之后每次取「与已选中心
  最大相似度最小」的一篇。不用随机种子，报告可复现——否则「主题变了」和「这次
  初始点抽歪了」会混在一起。
- **空簇补位**：把离自己质心最远的点挪过去，保证每个方向都有代表。
- **小簇归并**：收敛后把 `< max(5, N/100)` 篇的碎片并进最近的大簇。周报要的是方向，
  不是「1 篇论文的主题」。

**4. 主题命名**

每个簇取质心权重最高的 5 个词作为代表词，再用一张约 60 条的高信号词表翻成中文
（`agent → 智能体`、`retrieval → 检索`），没收录的一律显示英文原词——宁可中英混排，
也不硬翻译出不像术语的中文名。两个簇代表词撞车时补第三个词区分。

**5. 异常增长**

本周文档频率 vs 历史周均值（最多 8 周基线）：

```
期望  = 基线计数 × 本期总篇数 / 基线周总篇数     ← 先按总量缩放
z     = (本周 - 期望) / max(标准差, sqrt(期望))
倍数  = 本周 / 期望
```

**必须先按总量缩放**：整周论文少了 20% 时，所有方向的绝对计数都会跟着降，
直接比绝对数会得出「全领域萎缩」；缩放后比的是**份额**，才对应「注意力往哪偏」。
2026-11-15 首跑就踩过这个坑（3,840 vs 基线 4,808，一屏全是"下降"）。

方差下限取 `sqrt(均值)`：计数型数据的波动本就随均值增长，否则小计数会虚高 z。
上榜要求**同时**满足「本周 ≥ 12 篇」「基线均值 ≥ 4 篇」「z ≥ 1.5」「倍数 ≥ 1.2」——
只用倍数会让 1→5 的噪声上榜，只用 z 会让小样本抖动看起来像趋势。少了最后两条，
整体下行的一周会把「跌得最少」的方向排到增长榜第一位（2026-11-15 首跑就踩到了）。
分类维度用更严的门槛（≥20 篇）。

> 首次运行没有历史时，会自动补抓上一周写入 `trend_history.json`，这样第一期就能
> 给出周环比，而不是等下周才有对比。补抓只发生一次，之后都走历史文件。

## 产物

| 路径 | 说明 |
| --- | --- |
| `output/arxiv_trend_<YYYYMMDD>.html` | 当期报告（主入口，浏览器直接打开） |
| `output/arxiv_trend_<YYYYMMDD>.md` | 同内容的 Markdown 版 |
| `output/trend_archive/<YYYYMMDD>.{html,md}` | 只增不改的快照 |
| `output/trend_archive/<YYYYMMDD>.json` | 报告数据（簇、增长、分类计数） |
| `output/trend_history.json` | 跨周累积的基线（最近 8 周的 cats / terms） |
| `output/trend_raw_<YYYYMMDD>.json` | 抓取缓存 |

命名与归档规范与日报一致：当期主文件在 `output/` 根，快照在专用归档目录，
周报既不进 `archive/`（那是日报的），也不进 `episodes/`（那是视频期次的）。

## 用法

```bash
python trend_report.py                      # 本周日（默认取最近的周日）
python trend_report.py -d 20261115          # 指定期号
python trend_report.py --skip-fetch         # 复用缓存，只重算与重渲染
python trend_report.py --no-bootstrap       # 首跑时不补抓上一周做基线
python trend_report.py --json               # 机器可读摘要
```

自动化在**每周日 10:00** 执行（见下），入口与手工命令一致。

## 自动化

周日的定时任务按下面这条链路执行，失败要停下来汇报，不要跳过：

1. `python trend_report.py`（默认本周日）；
2. 确认三个产物存在：`arxiv_trend_<期号>.html` / `.md`、`trend_archive/<期号>.json`；
3. 把关键数字写进汇报：窗口、总篇数、分类数、主题簇数、增长最快的前三个方向；
4. `git add -A` → commit（含期号）→ `git push`（`output/` 已被忽略，不会入库）。

## 周报视频

与日报视频**同一套流程、同一组视觉变量**（`#05070A` 底、`#00D4FF` 强调色、微软雅黑、
左侧竖向时间线、5s 片头 + 20s/段 + 5s 片尾），只是内容从「十篇论文」换成「八个主题 + 一段增长」。

**成片时长下限是 3 分钟（180 秒）。** 段长锁死 20 秒（与日报的节奏一致），时长靠段数凑：
8 段主题 + 1 段增长 = 9 段，合 190.6 秒 / 5718 帧。主题簇不足 8 个时 `gen_trend_video_data.py`
会打印 `[warn] ... 低于 180 秒下限`，这种期次交给 A/V 闸门（按 9 段核对）会直接失败，
不会带着 150 秒的短片上架。

| 阶段 | 命令 | 产物 |
| --- | --- | --- |
| 分段数据 | `python tools/gen_trend_video_data.py -d <期号>` | `reel/src/trend.json`、`output/trend_notes.json` |
| 口播合成 | `python tools/gen_narration.py --papers reel/src/trend.json --notes output/trend_notes.json --outdir reel/public/audio_trend --audio-json reel/src/trend_audio.json --subdir audio_trend` | `reel/public/audio_trend/*.mp3`、`reel/src/trend_audio.json` |
| 渲染 | `cd reel && npm run render:trend` | `reel/out/arxiv-trend.mp4` |
| 闸门 | `python tools/check_video_av.py output/arxiv_trend_<期号>.mp4 --papers 9` | 时长 190.6s / 5718 帧 |

`--papers 9` 是段数，不是篇数：A/V 闸门按 `150 + N×600 + 18 + 150` 帧核对称片长度。
9 段即 190.6 秒，同时满足「不少于 3 分钟」的时长要求；改段数必须同步这个参数，否则闸门必失败。

**旁白是模板生成的**，不是手写：周报讲的每个数字（篇数、占比、倍数）都能从
`trend_archive/<期号>.json` 取到，模板句不会说错；日报要讲论文贡献，才必须人工写。
片头片尾各只有 5 秒，旁白固定在 20 字以内——超了会压进相邻段，变成两段旁白叠着说。

**投稿**必须带 `--kind trend`，产物用 `bili_trend_*` 前缀，与日报的同名文件互不覆盖：

```bash
python .../bili_upload.py meta    --kind trend -d <期号>
python .../bili_upload.py cover   --kind trend -d <期号>
python .../bili_upload.py upload  --kind trend -d <期号> --exec
python .../bili_upload.py verify  --kind trend -d <期号>
python .../bili_upload.py comment --kind trend -d <期号> --exec
python tools/bili_collection.py sync --exec      # 与日报同一个合集
```

标题形如 `智能体 / 大模型占 14%｜arXiv 周报 #1115`；封面眉标 `ARXIV WEEKLY`、
副文案「8 个主题 · 每周日 10:00 更新」，尺寸仍是 1146×717。

## 局限

- **无监督结果**：簇是 TF-IDF 空间里的邻近关系，不等于作者自述的领域；主题名来自
  代表词映射，只用于快速浏览，不构成分类学。
- **分类计数按 primary 计**：跨类论文只算一次，所以 `cs.LG` 的计数不等于「提到机器
  学习的论文数」。要看跨类，用 `categories` 字段自行统计（`trend_archive/*.json` 里有）。
- **arXiv 节假日**会让某一周偏少（例如 2026-11-11 是 arXiv 假日），增长信号在
  节假日后的一周会整体偏高，读的时候要结合窗口。
- **基线不足**时（第一次运行、或历史被清空），增长表会显示提示而不是臆造数字。
- 纯标准库实现，3200 篇的聚类约 20–40 秒；规模再上一个量级需要换算法，而不是调参。

## 排查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `窗口内没有抓到任何论文` | 网络不通或 arXiv 限流 | 先 `curl --noproxy '*' http://export.arxiv.org/api/query?search_query=cat:cs.LG` 验证；确认已 unset 代理 |
| 增长表长期为空 | 基线周数不足，或本周计数没到门槛 | 看 `trend_history.json` 的 `weeks` 长度；门槛是「本周 ≥12 且基线均值 ≥4」 |
| 簇名很抽象（如 `类型 / 语义`） | 该簇代表词偏泛 | 看报告里的代表词与示例论文，必要时扩充 `trend_analysis.STOPWORDS` 或 `TERM_ZH` |
| 某周篇数明显偏低 | arXiv 节假日 | 正常，报告中会显示窗口，按窗口解读 |
