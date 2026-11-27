# 变更记录

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
本项目尚未打版本号，因此以**日期**作为节标题；日期为提交日期（Asia/Shanghai）。

分类：`新增` / `变更` / `修复` / `文档` / `移除`。

---

## 2026-11-27（发布时段改为 22:00 定时）

创作中心数据对比显示：上午档首日播放中位数约为 23 点档的 61%，封标点击率约为 1/4，
累计收藏率约为 1/5；完播率与首日互动率并未下降。故把发布从「生产完即发」改为
**09:40/10:00 照常生产（避开 arXiv 公告空窗期），22:00 定时发布**。

### 变更

- `bili_upload.py` 的 `upload` 新增 `--dtime`：接受 `HH:MM` 或 10 位时间戳，
  校验距提交 >4 小时；dry-run 输出显示实际定时时刻。
- 片尾文案与 `reel/VIDEO_PROMPT.md`：更新节奏由「10:15 前后」改为「22:00 前后」。
- 定时任务：日报（工作日 09:40）与周报（周日 10:00）只负责生产 + 定时投稿，
  评论置顶与合集挂载后置到 22:40 的后置任务（视频需公开后才能操作）。

### 说明

- `verify` 在定时状态下读到的是 `-40`（定时发布中），不是 `0`；这是投稿成功的正常态。
- 早间生产时间不变：arXiv 于美东 20:00 公告，折算北京时间冬令时 09:00 / 夏令时 08:00，
  09:40 起跑才能拿到当天批次；若改为 22:00 才抓取，会落进当日公告前的空窗期。

---

## 2026-11-16（周报成片重渲 + 换源，BV 不变）

改完代表词/相关工作/图表后重渲了 20261115 期整片，并用**换源**替代重新投稿：

- 成片 150.6s → **190.6s**（9 段：1 词云 + 7 主题 + 1 增长），20.9 MB；
- 新标题 `大语言模型占 14%｜arXiv 周报 #1115`，封面换成 `ARXIV WEEKLY / 7 个主题`；
- **BV1bfsW67Ewc 不变**，播放/点赞/收藏计数保留；cid 换成新分 P，旧置顶评论删除后重发。

### 新增

- `tools/bili_replace_video.py`：已发布稿件换源。B站没有公开的换源 API，
  但网页端「更换视频」等价于 `POST /x/vu/web/edit` 时把 `videos[].filename`
  指向新上传的分 P、`cid` 仍用旧的。脚本按这条链路实现：
  上传分 P（`video_uploader._upload_page`，不投稿）→ 上传封面 → 编辑 → 轮询时长确认。
  默认 dry-run，`--exec` 才改线上；旧元数据先备份到 `bili_trend_backup_<期号>.json`。

### 修复

- **分段的 sid 缺失**：`pick_segments` 重写时漏了 `sid`，`gen_narration` 只能按序号
  猜旁白，导致词云段配到「第 0 个方向」这类占位句。现在每段显式带 `te1` / `t1..tN`。
- **词云段旁白过短**：17.0s 的音频在 20s 段尾留 4.17s 静音，被 A/V 闸门判失败；
  补到 72 字 / 18.3s 后通过。
- **标题钩子被截断**：主题名 `大语言模型 / LLM 智能体` 有 19 字，撑爆 18 字额度，
  标题变成「…智能体占 …」；改为只取第一段 `大语言模型占 14%`。

### 测试

- 新增 2 个用例（每段必须有 sid、词云旁白要撑满段），总数 1037 → 1039。

---

## 2026-11-16（周报视频：代表词去重、三篇相关工作、图表化）

按「代表词质量 / 相关工作展示 / 数据可视化」三项要求改造周报视频。

### 代表词：从质心前 6 改成三级挑选

原实现直接取 TF-IDF 质心前 6，于是同一簇会并排出现 `agents`、`agent`、`agentic`，
以及 `weights`、`image`、`video`、`algorithm` 这类放之四海皆准的词。现在：

- **词形归并**：`lemma()` + 别名表把 agents/agent/agentic 收敛成一个概念；
- **宽泛词黑名单**：`BROAD_TERMS`（含用户点名的 weights / image / video / algorithm）
  不进独立位次，但仍可出现在短语里（`image segmentation`）；
- **三级来源**：策展短语（KV 缓存、混合专家、高斯泼溅…，簇内 ≥3 篇且 ≥3%）→
  arXiv 官方分类词（cs.DB→数据库、cs.CV→计算机视觉，`cs.LG`/`cs.AI` 这种大口袋除外）
  → 词典内的中文术语；
- **双重去重**：概念键 + 中文包含关系，有了 `KV 缓存` 就不会再出现 `缓存`。
- 新增 `term_cloud()`：全周词云数据，同样剔通用词、按词形归并。

### 相关工作：每段 3 篇 + 蓝色说明

- `analyze()` 的每个簇返回 **3 篇**代表作，每篇带 `short`（口播短名）与 `note`（≤24 字中文说明）；
- `TrendReel` 在每篇标题与 arXiv 号下方用蓝色 `#4F9DFF` 显示这句说明；
- 口播从「与它最接近的工作，画面右侧能看到标题与编号」改成
  「三项最接近：A，…；B，…；C，…」，三篇都念到；模板做 120 字预算，超了先砍「代表词」；
- 说明的取材优先级：`output/trend_related_notes.json`（人工/模型写，自动化会写 21 条）
  → `brief_note()` 的词典结果（只取标题术语，避免摘要里的偶然搭配）
  → 英文副标题兜底。词典结果不再拼「提出recursive capability co…」这种半英半中残句。

### 可视化：四类图表

- **片头**：本周前 6 个分类的水平柱状图（分类名用 arXiv 官方中文名）；
- **词云段（新增，20s）**：字号 = 文档频率，剔除通用词；
- **主题段**：环形图（该主题占比）+ 前四主题规模对比小柱图；
- **增长段**：柱长改为从 1.0 起算（原先四条都顶满，看不出差别）。

### 结构调整

`1 段词云 + 7 段主题 + 1 段增长 = 9 段`，仍是 190.6 秒 / 5718 帧，
`check_video_av.py --papers 9` 与「≥3 分钟」的门槛不变。周日自动化新增第 4 步：
写 `output/trend_related_notes.json` 并重跑生成，日志必须出现
「代表论文说明：21 条来自 trend_related_notes.json」。

### 测试与文档

- 新增 10 个分析用例（词形归并、宽泛词过滤、分类词优先、说明只用词典词、
  标签不嵌套、词云全中文、每簇三篇带说明）与 4 个视频数据用例
  （三篇相关工作、口播必须念全三篇、120 字预算、说明覆盖）。
- 用例总数 1025 → 1037，`python -m pytest` 为 1031 passed + 6 skipped。
- 文档：`weekly-trend.md` 重写视频章节（图表表、代表词三级规则、蓝色小字优先级）、
  `cli.md`、`data-files.md` 同步。

---

## 2026-11-16（周报视频时长下限提到 3 分钟）

周报成片原来 6 主题 + 1 增长 = 7 段 / 150.6 秒，不足 3 分钟。段长锁死 20 秒（与日报的
`PAPER` 常量同源，不为了凑时长改节奏），因此**通过增加段数**把成片拉到 190.6 秒。

### 变更

- `tools/gen_trend_video_data.py`：`TOPICS_DEFAULT` 6 → **8**（+1 段增长 = 9 段），
  新增 `MIN_SECONDS = 180` 与 `estimate_seconds()`；段数不足打 `[warn] ... 低于 180 秒下限`，
  不静默缩短段长。`TrendReel.tsx` 的 `DURATION` 本就由 `DATA.segments.length` 推导，无需改动。
- 周日 10:00 自动化：`--k 8`、`check_video_av.py --papers 9`（190.6s / 5718 帧），
  并把「成片不得短于 180 秒」写成硬约束——闸门不过不得投稿。
- 文档：`docs/guide/weekly-trend.md`（视频章节）、`docs/reference/cli.md`、
  `docs/reference/data-files.md` 同步段数与时长。
- 测试：`tests/unit/test_gen_trend_video_data.py` 新增 2 个用例（默认段数满足 3 分钟下限、
  短篇必须告警）。用例总数 1023 → 1025。

本次只改配置与脚本，**未重跑 20261115 期**，已发布的那条保持原样，下一次（2026-11-22 10:00）
起按 9 段生成。

---

## 2026-11-16（周报视频：复用日报的流程与视觉，投稿同一合集）

周报此前只有 HTML/Markdown，没有视频。这次把**日报视频的那一套**（分段数据 → Edge TTS
旁白 → Remotion 代码渲染 → A/V 闸门 → 投稿 → 合集）搬到周报上，视觉变量完全一致：
`#05070A` 底 + `#00D4FF` 强调色 + 微软雅黑 + 左侧竖向时间线 + 5s 片头 / 20s 每段 / 5s 片尾。

### 新增

- **`reel/src/TrendReel.tsx`**：新的 Remotion 合成，7 段（6 个主题 + 1 段异常增长），
  总长 150.6 秒 / 4518 帧。片头报「论文 / 分类 / 主题簇」，每个主题段给中文主题名、
  代表词、占比大字与代表论文；增长段给「方向 / 倍数 / 篇数」。
- **`tools/gen_trend_video_data.py`**：读 `trend_archive/<期号>.json` → `reel/src/trend.json`
  + `output/trend_notes.json`。旁白用**模板生成**：周报讲的全是数字，模板句不会说错；
  日报讲论文贡献，才必须人工写。
- **`bili_upload.py --kind trend`**：周报的标题/封面/评论/对账产物统一用 `bili_trend_*`
  前缀，与日报的同名文件互不覆盖（同一天可能两条视频都在）。
- `gen_narration.py` 支持 `--subdir` 与 `segments` 数据：周报音频落在
  `reel/public/audio_trend/`，不再和日报抢 `audio/` 目录。

### 变更

- 周日 10:00 的自动化加入完整视频链路：生成分段 → TTS → `npm run render:trend` →
  `check_video_av.py --papers 7` → `bili_upload --kind trend` 全套 → 合集 sync。

### 两个渲染期踩到的坑

1. **片头片尾旁白必须 ≤20 字**。5 秒窗口只能放约 20 字；第一版片头写了 96 字（14.9s），
   会整段压进第一个主题段，两段旁白叠着说。现在片头「这一周，计算机科学在往哪走？」（14 字）。
2. **周报的片尾不能提前 1 秒进**。日报提前是为了盖住末卡淡出；周报末段本来就有 2 秒余量，
   提前反而在结尾留下 3.07 秒静音，被 A/V 闸门判失败。`OUTRO_LEAD` 在周报里设为 0。

### 测试与文档

- 新增 `tests/unit/test_gen_trend_video_data.py`、`tests/unit/test_bili_trend.py`，17 个用例
  （分段选取与排序、数字口径、片头片尾字数、空增长兜底、路径隔离、标题/简介/标签/评论）。
  用例总数 1006 → 1023，`python -m pytest` 为 1017 passed + 6 skipped。
- 文档：`docs/guide/weekly-trend.md` 增加「周报视频」章节；`cli.md` 增加
  `gen_trend_video_data.py` 与 `--kind`；`data-files.md` 补充周报视频与 `bili_trend_*` 产物。

---

## 2026-11-15（新增 cs.* 周度趋势周报）

日报回答「今天哪几篇值得我看」，靠个人画像排序；它回答不了「这一周整个 cs 在往哪走」。
新增一条**独立的周报链路**：抓 `cs.*` 全量（约 3800 篇/周），做 TF-IDF + 球形 k-means，
输出「本周主题分布」与「异常增长方向」。**不挑文章、不逐篇翻译、不做个性化推荐**。

### 新增

- **`trend_analysis.py`**：纯计算层——切词（标题 ×2）、TF-IDF、球形 k-means（最远优先
  初始化、空簇补位、小簇归并）、增长检测。无 IO、无网络、无第三方依赖（沿用「运行期
  只用标准库」的承诺），3200 篇聚类约 2–3 秒。
- **`trend_report.py`**：编排层——分页抓取（500 条/请求、3 秒间隔）、缓存、渲染
  HTML/Markdown、归档、跨周基线累积。
- 产物：`output/arxiv_trend_<期号>.{html,md}`、`output/trend_archive/<期号>.{html,md,json}`、
  `output/trend_history.json`（最近 8 周基线）、`output/trend_raw_<期号>.json`（缓存）。
- 自动化：**每周日 10:00** 执行（工作日 09:40 的日报任务不受影响）。

### 三个实现中踩到的坑（都已修正，并在报告里写明口径）

1. **窗口必须回退 3 天**。arXiv API 只索引已公告论文；周日上午跑「最近 7 天」时，
   最近两三天还没公告，实测 2371 篇 vs 基线 4652 篇 —— 一屏全是「萎缩」的假信号。
   现在窗口 = 期号回退 3 天再取 7 天，两端都是完整周（3840 vs 4808）。
2. **增长要按总量缩放**。整周论文少 20% 时所有方向都会「下降」，直接比绝对数没有意义。
   改为「基线计数 × 本期总量 / 基线总量」得到期望值，再比份额。
3. **增长榜只能报正增长**。首跑把「跌得最少」的方向排到了增长第一（×0.70）。
   现在要求 z ≥ 1.5、倍数 ≥ 1.2、本周 ≥ 12 篇同时成立；不满足就明确写「没有异常」。

### 测试与文档

- 新增 `tests/unit/test_trend_analysis.py`、`tests/unit/test_trend_report.py`，共 29 个用例
  （聚类可分离性、TF-IDF 归一化、总量缩放、小簇归并、历史幂等、渲染转义、归档产物）。
  用例总数 977 → 1006，`python -m pytest` 为 1000 passed + 6 skipped。
- 新增 `docs/guide/weekly-trend.md`（口径、方法、产物、局限、排查），并同步
  `mkdocs.yml` 导航、文档中心、命令行参考、数据文件、模块职责（21 → 23 个模块）、
  README 特性表与测试计数。

---

## 2026-11-14（每期成品按日期归档，不再被覆盖）

定时任务每跑一次就覆盖同名文件：`reel/src/papers.json`、`output/video_notes.json`、
`reel/src/audio.json`、`reel/public/audio/*.mp3` 都不带期号 —— 第二天一跑，
「这一期讲了哪 10 篇、配了什么解说」的证据就没了（`output/` 里积的
`video_notes.json.bak_20261114` 这类手工备份，就是这件事反复发生的证据）。

### 新增

- **`tools/snapshot_episode.py`**：把整期成品归档到 `output/episodes/<YYYYMMDD>/`。
  内容：日报、视频、投稿元数据 / 封面 / 置顶评论稿 / 投稿回执，加上最容易被覆盖的
  `papers.json`、`video_notes.json`、`audio.json`、`audio/*.mp3`，以及
  `MANIFEST.json`（大小 / sha256 / 来源 / 缺失项 / 历史版本）。
- 归档规则：跨日不覆盖（每期一个目录）；**同期重跑不丢旧版**（内容变了就把旧文件
  移进 `<日期>/history/<时间>/`，只移动不删除）；共享文件先比对 `papers.json` 的
  `issue`，期号不符就跳过，宁可少存也不把今天的数据塞进昨天的目录。
- `--skip-video` / `--link`（同盘硬链接）/ `--dry-run` / `--json`，退出码 0/1 语义明确。

### 变更

- 自动化流程新增第 6 步：`comment` 之后跑一次归档，**且不受投稿成败影响** ——
  中途失败也要把已经生成的产物存下来，否则第二天的运行会把它覆盖掉。
- 回填历史：`output/episodes/` 下已生成 34 期目录，合计 539 MB。

### 测试与文档

- 新增 `tests/unit/test_snapshot_episode.py`（14 个用例），覆盖归档、幂等、
  历史版本、期号不符跳过、dry-run、JSON 输出。用例总数 963 → 977，
  `python -m pytest` 为 971 passed + 6 skipped。
- 同步 `docs/reference/cli.md`、`docs/guide/video-pipeline.md`、
  `docs/reference/data-files.md`。

---


## 2026-11-14（标题公式 / 封面设计稿 / 选题硬约束 / 发布前校验）

针对「内容生产流程」的四项改造。核心判断：这三件事被违反时**不会报错**——
B站照收稿，标题长度合法、封面尺寸合法，只是点击率悄悄变差。所以每一条都要落成
可机械校验的规则，而不是写作建议。

### 变更

- **标题公式**：`build_title` 由 `arXiv 日报 {期号}｜{分类} TopN 速览` 改为
  `{钩子 ≤18 字}｜arXiv 日报 #MMDD`。钩子优先取 `video_notes.json` 的 `hook`，
  缺失时退化为当期前两个领域名（`数据库·分布式`），退化的标题同样满足公式。
  期号改用 `#MMDD`：移动端信息流只显示前 20 来个字，完整日期会把钩子挤出可见区。
  超长按字符截断补 `…`；`meta` 里新增 `hook` 与 `cover_manifest` 两个字段。
- **封面**：不再用 `ffmpeg -ss 3.6` 抽视频帧（缩到信息流尺寸后字太小），改为 Pillow
  画 1146×717 设计稿：左上眉标 `ARXIV DAILY`、钩子两行大字（按像素折行，放不下先缩字号，
  不丢结论数字）、右上 `#MMDD` 角标、左下「N 篇论文 · 每篇 20 秒」与当期领域、
  右下低对比大数字。第二行明显短于第一行时（如「把 LLM 推理成本砍到 / 1/4」）用强调色绘制，
  否则短行看起来像排版算错了。每次渲染同时写 `bili_cover_<issue>.json` 设计清单。
- **选题两条硬约束**：`gen_video_data.py` 新增 `select_episode()`——同一 `primary`
  分类最多 4 篇；至少 1 篇标题自带可读钩子（数字/倍数/百分比/`without`/`provably` 等）。
  不满足时自动换片（换片也守分类上限），并把每篇的 `hook`、`title_hook` 写进
  `papers.json`；日志打印分类分布与钩子数。

### 新增

- **`tools/verify_episode.py`**：发布前闸门，校验标题公式（正则 + 钩子长度 + 与 meta 一致）、
  封面（1146×717、`renderer=pillow`、角标/钩子/篇数与本期一致）、选题（片数一致、
  单分类 ≤4、至少 1 篇钩子、rank 连续）。`-d/--date`、`--json`、`--quiet`，
  退出码 0/1/2；JPEG 尺寸用自己的 SOF 头解析，不依赖 Pillow——校验方要比被校验方依赖更少。
  流水线在 `cover` 之后、`upload --exec` 之前调用，每天随日报自动执行一次。

### 测试与文档

- 新增 `tests/unit/test_bili_cover.py`、`tests/unit/test_gen_video_select.py`、
  `tests/unit/test_verify_episode.py`，并改写 `tests/unit/test_bili_meta.py`
  （旧用例断言的是被替换掉的标题格式）。用例总数 915 → 963，
  `python -m pytest` 为 957 passed + 6 skipped。
- 同步 `SKILL.md`、`docs/guide/video-pipeline.md`、`docs/reference/cli.md`、
  README 徽章与测试计数。

---


把定时流水线从「每周一、三、五 23:10」改为「每周一至周五 09:40」，生产完成后**立即投稿**，
不再等到深夜。这次调整只动排期与对外文案，不改任何抓取 / 推荐 / 渲染逻辑。

### 变更

- **排期**：`rrule` 由 `BYDAY=MO,WE,FR;BYHOUR=23;BYMINUTE=10` 改为
  `BYDAY=MO,TU,WE,TH,FR;BYHOUR=9;BYMINUTE=40`。覆盖 arXiv 全部 5 个投稿窗口
  （原先只覆盖 3 个，周二、周四窗口从不单独成期）。
- **发布时刻**：实测流水线 17–44 分钟，09:40 起跑后稿件在 10:00–10:25 上线，
  较原来的 23:27–23:54 前移约 13 小时，并消除了「片尾写 23:10、实际 23:30+ 才上线」的错位。
- **片尾文案**：`reel/src/PaperReel.tsx` 与 `reel/VIDEO_PROMPT.md` 的更新节奏改为
  「每周一至周五 10:15 前后更新」（按流水线实测耗时定的可兑现承诺，宁可早于承诺也不晚）。

### 新增

- 自动化提示词加入**空批次守卫**：`output/issue_core.json` 的本期新增为 0
  （arXiv 节假日、公告延迟、周末无批次）时只更新日报，跳过视频与投稿，
  绝不重发上一期内容；新增少于 5 篇时照常出报并在汇报里标注「本期偏少」。
  改为每天运行后这条守卫是必需的 —— arXiv 每个工作日 20:00 ET 才公告一批，
  法定假日当天没有新批次。

### 文档

- 同步本文件；排期只在 `reel/src/PaperReel.tsx`、`reel/VIDEO_PROMPT.md` 与自动化配置中
  出现，其余文档未写到具体钟点，无需改动。

---

## 2026-11-12（start_digest.bat 支持按日期打开指定期次）

只改 `start_digest.bat` 一个脚本，**服务启动逻辑保持原样**（仍是前台
`%PY% server.py` + 数据包参数，端口取 `config.json` 并自动顺延）。新增可选的日期参数，
让「起服务」和「打开某一期日报」一次完成。

### 新增

- **日期参数** `YYYY-MM-DD`（或 `--date` / `--date=`）：打开「期次日期 ≤ 指定日期且最接近」
  的一份 HTML，**含指定当天**；不给日期则打开当前已生成的最新一期。
  旧用法 `start_digest.bat hengxin` / `hengxin force` 完全兼容，日期、包名、`force` 顺序无关。
- 候选与去重：根目录 `arxiv_digest_<YYYYMMDD>[_后缀].html` 与 `output/archive/<YYYYMMDD>.html`；
  同一期次有多份时按生成时间（mtime）取最新，mtime 相同优先根目录正式文件；
  `favorites.html` / `archive.html` / `_preview.html` 等非期次页面不参与。
- 日期校验用脚本**内嵌的 Python 帮助块**（不新增源文件）：严格 `YYYY-MM-DD` + 真实日历日期，
  闰年/大小月正确；批处理通过 `python -c` 抽取该块并读回 `KEY=VALUE`。
  参数非法、找不到符合条件的 HTML 时打印明确提示、**不打开任何文件**，服务照常启动。
- 服务侧改用 `--no-open`：浏览器只打开选定的这一份 HTML，避免冒出两个标签页；
  `config.json` 的 `open_browser=false` 仍然生效。

### 测试与文档

- 新增 `tests/unit/test_start_digest_bat.py`（66 个用例）：直接 exec 脚本内嵌帮助块测纯函数、
  进程内执行真实 `python -c` 引导串、以及 6 个真实 `cmd` 干跑（默认跳过，
  `RUN_BAT_CMD_E2E=1` 开启，与既有 `ui` 用例同样的做法）。用例总数 849 → 915，
  行覆盖率 90.81%（门槛 85%）。
- 同步 README、文档中心、命令行参考、快速开始 / 安装、数据包指南、私人数据隔离、
  服务运行时、config / data-files 参考、FAQ、故障排查、测试文档、`tests/README.md`、
  变更记录与测试计数徽章。

> 已知边界：打开的是静态 HTML，页内 `APIPORT` 是生成当时的端口；若端口顺延，
> 交互按钮需刷新或改用服务地址。已在各文档标注。
>
> 另：`tests/unit/test_service.py::test_download_many_runs_in_parallel` 是既有的
> wall-clock 计时断言（阈值 0.40s、串行 0.45s，余量仅 0.05s），本机负载高时偶发失败；
> 用 `--ignore=tests/unit/test_start_digest_bat.py` 跑基线同样能复现，与本次改动无关。

---

## 2026-10-28（补齐中文摘要 + arXiv 入口 + 已下载按钮语义）

三件事：把本期 77 篇论文的中文摘要译文与双语简介**全部补齐**；把「PDF」按钮改成
一眼可辨的 **arXiv ↗** 入口；把「已下载」按钮的点击语义从"再下载一次"改成
**打开本地 PDF**。

### 新增

- **`build_report.dl_btn()` / `arx_link()`**：按钮组件收敛为函数，推荐卡、分类条目、
  重点论文块与收藏页共用同一套标记。
  - `arx_link`：arXiv 入口改为打开 `https://arxiv.org/abs/<短号>` 论文页（标题链接仍是
    PDF 直链），按钮为红色 arXiv 字标 + 内联 SVG 外链箭头，tooltip/aria-label 均写明
    「在 arXiv 上打开论文页（新标签页）」。
  - `dl_btn`：已下载态的按钮带 `done` 类、`title`/`aria-label`「打开本地文件」、图标 📂；
    未下载态的 tooltip 是「下载 PDF 并自动收藏」。服务端渲染时就读
    `library.json.downloads`（新模块级 `DOWNLOADS` + `load_downloads()`），
    不再等前端 `/api/state` 回填——首屏不闪烁，禁 JS 也不出错。
- **前端**：`app.js` 点击分支按按钮自身 `done` 态二选一——已下载调 `/api/open` 并弹
  「正在打开本地文件」toast，未下载才走 `/api/download`；`setDl()` 同步换 tooltip /
  图标 / 文字。收藏页删除了与 `app.js` 重复的点击委托（曾导致同一次点击发两次请求）。
- **测试**：新增单元 `test_build_buttons.py`（6 条）、集成 2 条（服务端渲染的下载态与
  arXiv 入口）、浏览器端到端 2 条（真点「已下载」断言走 `/api/open` 且未发下载请求；
  未下载的仍是「下载」）。`tools/dl_button_check.py` 改为验证「已下载 → 打开本地文件」
  （副作用：会真开一个 PDF）。

### 变更

- **摘要保留全文**：`recommend.pack()` 不再把 `abstract` 截断到 1400 字符——那会让
  `Abstract (EN)` 在句子中途断掉，中文译文也无从对应"完整摘要"。
  当期 520 篇摘要中位 1517 字符、最长 1917 字符，JSON 增量可忽略。
- **数据**：本期（20261026）渲染集合 77 篇全部补齐中文摘要译文（`abstracts_zh.json`
  52 → 109 条）与双语简介；`Abstract (CH)` 不再出现"还没有译文"提示。

### 文档

- `daily-workflow`（按钮表：新增「已下载（再点）」行，PDF → arXiv ↗）、`quickstart`
  （按钮列表与交互步骤）、`http-api`（`/api/open` 与事件动作）、`profile-tuning` /
  `ranking`（0.55 权重的行为名）、`data-files`（摘要不截断）、`cli`（`dl_button_check`
  新语义）、`README`（按钮语义与文案）。

---

## 2026-10-22（简介双语 + 摘要拆成 EN / CH 两个版本）

此前「简介」的写法不统一：有的纯中文、有的纯英文，混在一屏里读起来要不断切换语感。
本次把它定成一条规则：**简介 = 摘要核心内容（非完整摘要）的双语版，英文在上、中文在下**，
英文优先复用摘要里的原始句子；**摘要**则拆成英文原文与中文译文两版，
`Abstract` 按钮改为 `Abstract (EN)`，右侧新增 `Abstract (CH)`。

### 新增

- **`abstracts_zh.json`**（`output/`，`{短号: 中文译文}`）：英文完整摘要对应的中文译文，
  由 `Abstract (CH)` 展示。属于 `notes` 分组（与简介同为编辑性内容，导入只做并集），
  `.gitignore` 按路径排除。
- **`summary_en`**：`recommend.json` / `papers_index.json` 的推荐项新增该字段；
  `summaries.json` 的 value 支持 `{"en": ..., "zh": ...}`，未写 `en` 时用
  `paperutil.en_excerpt()` 取摘要开头若干**完整句子**兜底（按 `.!?` 切句并避开 `et al.` 之类缩写）。
- **`paperutil.split_bilingual()` / `has_cjk()`**：单语 value 按是否含汉字自动归位，
  因此**历史单语文件不需要迁移**——含汉字算中文、否则算英文。
- **`tools/gen_pending.py` 的三个缺口模式**：默认缺中文简介、`--en` 缺英文简介、
  `--abs` 缺中文摘要译文（`--abs` 的摘要截取默认放宽到 1200 字符，因为要译全文）。

### 变更

- **两个摘要按钮互斥展开**（`app.js` 的 `toggleAbs`）：同时展开会把卡片撑成两倍高。
  选元素改用 `[id="ab-<短号>"]` 属性匹配——短号里的点会被 `#id` 选择器当成类选择器，
  旧实现用 `getElementById` 才没暴露这个问题；同时改为展开**全部**同名块
  （同一篇会同时出现在推荐卡 / 分类条目 / 高亮块）。
- **Markdown 导出同步双语**：`- EN …` 与 `- 中 …` 两行，顺序与页面一致。
- 页面说明（推荐区副标题、页脚）与收藏页 / 存档页文案同步为新按钮名。

### 文档

- `docs/reference/data-files.md`：目录一览、`recommend.json` 字段、第四节编辑性内容
  （双语结构 + 缺一侧的兜底行为）、不可删清单、包文件表；
- `docs/guide/daily-workflow.md`：卡片元素表新增「简介（两行）」，按钮表拆成 EN / CH 两行；
- `docs/getting-started/quickstart.md`、`docs/guide/profile-tuning.md`：按钮名与动作说明；
- `docs/reference/cli.md`：`gen_pending.py` 三个模式 + 补写规则（含旧单语写法仍可读）；
- `docs/operations/troleshooting.md`：第六节改为「简介 / 摘要译文缺失」，含三种缺口的诊断命令；
- `docs/meta/glossary.md`：新增「简介」「摘要译文」两个术语；
- `docs/meta/faq.md`、`docs/architecture/overview.md`、`docs/guide/presets.md`、
  `docs/architecture/data-isolation.md`：手工补写的原因、渲染输入、notes 分组文件清单；
- `.gitignore`：`/presets/*/abstracts_zh.json` 与简介一样按路径排除。

---

## 2026-10-22（合集挂载：20080 不是整批成功，判重改看稿件详情）

本期视频 `BV1yQn16oEb3` 的合集挂载一路报成功，实际**从未挂上**：
`tools/bili_collection.py sync --exec` 每轮把 20261020 与 20261022 一起作为「待挂载」提交，
服务端因 20261020 已在合集中返回 `code 20080`，脚本把这条当「幂等成功」直接 `return True`，
于是整批（含真正缺的 20261022）被静默丢弃。判据是稿件详情：
`x/web-interface/view?aid=117482807430140` 的 `season_id` 一直是 `None`，
而 20261020 的老稿是 `9343347`——**20080 是整批级拒绝，不是逐条报告**。

### 修复

- **`add_episodes()` 收到 20080 不再当整批成功**：仅在单条重投时视为幂等成功；
  批量时降级为**逐条重投**，已在的跳过、缺的补上，任一真错误（如 `-400`）即整体失败；
- **判重改看稿件详情**：新增 `season_of()` / `view_info()`，用 `data.season_id`
  （或 `data.ugc_season.id`）判断归属，绕过 member `seasons` 列表的缓存快照——
  这是「每轮重复重投同一批」的根因；
- **挂完回读校验**：新增 `verify_membership()` / `verify_membership_settled()`，
  `_finish_add()` 挂载后重新读每个 aid 的 `season_id`，仍不归属则打印
  `[FAIL] 仍不在合集 season … 内` 并以非零码退出，让自动化下一轮继续补；
  因稿件详情接口也有 CDN 缓存，校验重试 `VERIFY_ATTEMPTS=5` × `VERIFY_DELAY_SEC=3s`；
- **`plan_episodes()` 合并成一次请求**：原先 `season_of` 与 `get_cid` 各发一次
  `view` 请求，现在取一次 `view_info` 同时得到 `cid` 与归属；顺手删掉 `cmd_sync` 里
  从未使用的 `created_now`；
- **覆盖率分母收窄**：`tests/unit/test_bili_meta.py` 用 `importlib` 加载
  `.workbuddy/skills/bili-auto-upload/scripts/bili_upload.py` 之后，`source = .` 把这支
  438 行的技能脚本也纳入了统计（覆盖率 17%），整体从 91% 拖到 83.58%、`fail_under=85`
  直接失败。`.coveragerc` 的 `omit` 补上 `.workbuddy/*`——技能脚本不是应用代码。

### 变更

- 合集挂载现状（2026-10-22 核对）：`season_id=9343347` 内共 **6/6** 期，
  含本期 `BV1yQn16oEb3`（20261022）。

### 文档

- `docs/reference/cli.md`：`bili_collection.py` 一行改写——判重看 `season_id`、
  20080 是整批级拒绝、挂完回读校验；
- `docs/guide/video-pipeline.md`：第八节补「两个接口都不能只信自己的缓存/返回码」
  三条判据与本次踩坑记录；
- `docs/operations/troubleshooting.md`：B 站小节新增「回读 FAIL 但页面能看到」一行
  （手工核对用 `data.season_id`），并改正 20080 的旧解释；
- `.workbuddy/skills/bili-auto-upload/SKILL.md`：判重与校验规则、合集已挂 6 期；
- 用例数 795 → **825**，覆盖率 90.57%（`--cov` 实测）：`README.md`、`docs/index.md`、
  `docs/contributing/testing.md` 的数字同步；`docs/contributing/testing.md` 与
  `docs/meta/faq.md` 里过时的沙箱路径 `tmp_pytest/<tag>-<pid>-<seq>/` 改成
  `<tag>-<随机后缀>/`（`_fresh_dir()` 已改用 `mkdtemp`，pid 复用会继承残留目录）。

---

## 2026-10-22（语音合成的出网路由：能换路、会记住、失败可补跑）

定时任务在这一轮 TTS 上连撞两次硬失败：12 段旁白合成到第 3 段整轮 traceback，
而同一时刻**单跑**一次 `edge-tts` 却成功。定位结论是**路由**而不是服务：
`speech.platform.bing.com` 在本机被解析到 `198.18.0.104` 这类假 IP，TCP 能连上（0.0s）、
TLS 握手随即被掐断（`curl -v` 显示 `CONNECT ... 200` 之后 `SSL/TLS connection failed`）；
而经环境代理 `HTTP(S)_PROXY` 的同类请求可以通，且**同一代理也会按请求随机失败**（实测约 1/3）。
旧实现只有「同一路由重试 3 次」，撞上就是整轮失败。

### 新增

- **`gen_narration.py --proxy <url>`**：直接指定 TTS 出网代理，跳过自动探测；
- **路由回退**：`tts_proxy_candidates()` 复用 `netroute.candidates()` 的顺序
  （直连 → 环境代理 → 本机代理端口），逐条尝试；成功的一条记进 `_ROUTE`，供后续段落直接命中，
  不再每段重等直连的建连超时。候选数量上限 `TTS_MAX_ROUTES = 6`
  （`netroute` 末尾会追加"本机其它在监听端口"，实测那些是普通服务，返回 405/400 或直接断开，
  试到第 8 条只是空转）；
- **段级补跑**：`TTS_SEGMENT_ROUNDS = 3`。第一轮逐段合成，把失败的挑出来再补，
  补齐才算成功（`audio.json` 的 `enabled` 以**最后一轮**为准）；
- 新增 9 个单元测试（`tests/unit/test_gen_narration.py`）：候选顺序 / 记住成功路由 /
  建连失败换路 / 单次抽风不换路 / 全部失败抛出 / 单段失败不崩主流程 / 补跑成功即整体成功。

### 修复

- **单段合成失败不再让整轮 traceback**：`main()` 内逐段 try/except，失败记为 `[err]` 并继续，
  最终如实写 `enabled=false`（否则渲染会去引用一个不存在的 mp3）；
- **补跑后的成功判定**：初版用「第一轮是否失败」定 `ok`，导致第二轮补齐了仍报 `enabled=false`
  —— 该缺陷由新增用例抓出，已改为以最后一轮为准；
- **重试策略区分两类错误**：`NoAudioReceived` 属服务端抽风 → 同一路由内重试；
  建连失败（`ClientConnectorError` / TLS 被掐）→ 换路由，但**连续两次**才换
  （可用代理本身会按请求抽风，一次就换会丢掉好路由，落到无关的本地服务上）。

### 文档

- `docs/reference/cli.md`：`gen_narration.py` 补 `--proxy` 与自动路由说明；
- `docs/guide/video-pipeline.md`：新增「TTS 连接失败 = 路由问题」的判据与处理；
- `docs/operations/troubleshooting.md`：视频小节补 `ClientConnectorError` / `NoAudioReceived` 两行。

---

## 2026-10-20（启动体验：端口自动顺延 + 浏览器开关）

上一版启动是「端口被占就崩」：`server.py` 直接 `ThreadingHTTPServer(("127.0.0.1", port))`，
`Address already in use` 一抛就退出；`start_digest.bat` 更糟 —— 它先自己 `start "" http://…:8765`
再给服务传 `--no-open`，端口一旦被占，浏览器开到一个别人的页面上，窗口里只剩 traceback。
这次把「怎么暴露服务」抽成一层并补齐三条链路（直接启动 / 批量流水线 / 双击 bat）。

### 新增

- **`serveport.py`**（基础层，仅标准库）：端口解析与校验（`valid_port` / `configured_port`）、
  占用探测（`port_in_use` 走 connect、`can_bind` 走 bind）、顺延查找（`find_free_port`，
  默认最多 20 个候选、越过 65535 即停不绕回）、页面端口改写（`rewrite_api_port`）、
  浏览器开关（`browser_enabled` / `open_browser`）、运行期信息（`write_runtime_info` /
  `read_runtime_info` → `output/server.json`）；
- **`server.py --port <端口>`**：指定起始端口（优先于 `config.json`），被占用时照样顺延；
- **`server.py --open`**：配置里关了自动开浏览器时，临时强制打开（`--no-open` 仍可关）；
- **`config.json` 新字段 `open_browser`**（默认 `true`）：关掉后启动不再弹浏览器；
- **启动日志明确报出实际地址**：`serving http://127.0.0.1:8766` + 一行
  `port: 8766（8765 已被占用，已向后顺延；尝试过 8765–8766，共 2 个）`；
- **`output/server.json`**：`{port, url, pid, started_at}`，供 `run_daily.py` 与排障对账；
- 新增 75 个用例（50 单元 serveport + 16 单元 server 启动 + 5 路由静态页端口改写 +
  1 渲染端口 + 3 run_daily 端口顺延），总数 720 → 795。

### 变更

- **`run_daily.py`**：不再盲目轮询 `config.port`。先用同一份 `find_free_port` 选空闲端口，
  再以 `--port` 传给 `server.py`（保证「轮询的端口」＝「绑定的端口」）；服务若仍被抢而顺延，
  回读 `output/server.json` 对账，不再误报「服务没起来」；
- **`start_digest.bat`**：删掉自己拼 URL 与 `start ""` 的旧逻辑，改由 `server.py` 打印并打开
  真实地址（旧逻辑在端口顺延后会开到别人的页面上）；
- **`routes.py`**：新增 `_static_html()`。日报 / 归档快照 / `/files/*.html` 这类**静态**响应
  在发送时就地改写 `APIPORT=<实际端口>`（端口一致时仍走原来的延迟读盘，且不落盘、归档快照
  文件本身一字不改）；
- **`build_report.api_port()`** 改走 `paperutil.effective_port()`：动态页（`/favorites`、
  `/profile`、`/archive`）按**运行期实际端口**渲染，端口顺延后不会再指回旧端口；
- **`paperutil.py`**：新增 `RUNTIME_PORT` / `set_runtime_port()` / `effective_port()`
  （运行期端口 > `config.port` > 8765，非法值回落）。放在这里而不是 `build_report`，
  因为后者每个请求都可能被 reload，模块级变量留不住；
- 端口耗尽时进程以**退出码 2** 结束并打印尝试范围，不留半启动进程；绑定被抢（探测与 bind
  之间的竞态）自动顺延重试一轮。

### 文档

- README / 文档首页：特性表加「启动不挑端口」，快速开始改成「打印地址」而不是「浏览器会打开」；
- `docs/architecture/server-runtime.md`：新增「端口：先探测、再顺延、最后落盘」一节，
  说明 connect 探测为何是主判据（Windows `SO_REUSEADDR` 端口劫持）、静态/动态页两条
  端口改写路径、生命周期图与失败模式表同步；
- `docs/reference/config.md`（`port` 语义 + 新字段 `open_browser`）、`cli.md`（`--port` /
  `--open` / 顺延语义）、`troubleshooting.md`（1.3 端口被占用改成「会自动顺延」，
  新增 1.4 浏览器没自动打开）、`installation.md`、`quickstart.md`、`data-files.md`
  （`server.json`）、`modules.md`（新模块）、`contributing/testing.md`（用例数与覆盖率）。

### 修复

- 顺延后页面按钮失效的连带故障：页面 JS 里的 `APIPORT` 是渲染时烘焙的 `config.port`，
  不改写的话收藏 / 下载 / Downvote 会打到旧端口，而 `/api/ping` 却是通的 ——
  表象为「点了没反应」（乐观更新被回滚），极难定位。

## 2026-10-20（私人数据隔离：数据包与干净首启动）

把"个人数据不进版本库"从**命名约定**升级为**有契约、有清单、有测试**的显式对象：
模板 / 数据包 / 运行态三层分离，任何人的配置与使用数据都收在一个目录里，
只能显式导入。设计文档见 [docs/architecture/data-isolation.md](docs/architecture/data-isolation.md)。

### 新增

- **`datapack.py`**：数据包业务层。包发现（`list_packs`）、本机状态（`state`，不返回绝对路径）、
  导入（`import_pack`：覆盖 / 合并 / 拒绝 + 逐文件 `report`）、导出（`export_pack`：默认只导
  `core`，绝对路径中性化，写含 `sha256` 的 `manifest.json`）、隐私自检（`scan_paths`）；
- **四个数据分组**：`core`（配置与画像，整文件替换）· `usage`（收藏/下载/Downvote，只并集）·
  `learning`（行为学习，默认不导入）· `notes`（摘要与笔记，只并集）——按隐私等级与跨机器语义划分；
- **`--preset <名字>` 启动参数**：`run_daily.py`、`server.py`、`start_digest.bat` 均支持，
  导入发生在其它动作之前，失败不阻断启动；`--preset-force` 才允许覆盖本机配置（先备份）；
- **`POST /api/preset`**（`import` / `export`）与 **`GET /api/datapacks`**；
- **`/profile` 的「📦 数据包」面板**：只显示包名、文件清单、体积与分组，
  显示"本机现状（N 个类别 / M 个主题 / 收藏 K 篇）"，一个按钮导入；
- **`tools/preset.py` 重写**：`list` / `show <名字>`（逐文件差异）/ `import` / `export` / `status`，
  支持 `--groups`、`--with-usage`、`--with-learning`、`--with-notes`、`--dry-run`、`--keep-paths`；
- **`presets/hengxin/manifest.json`**：清单化这份示例包（schema 1 + 逐文件 sha256）；
- 新增 48 个用例（32 单元 + 14 集成 + 1 编排 + 1 e2e），总数 720。

### 变更

- **`core` 分组的"模板初值"例外**：本机 `config.json` / `interests.json` 若仍与
  `*.example.json` 完全一致（用户还没改过），导入时直接替换、无需 `--force`——
  否则新用户点「导入」永远报错，"一键"失去意义；只要改过任何一项就回到"默认拒绝"；
- **导入 `config.json` 时保留本机 `port`**：端口是这台机器的基础设施，不该被别人的包改掉；
  它也不参与"是否仍是模板初值"的判定；
- **首屏示例文案去掉与作者分类重合的暗示**：欢迎页的示例分类改为跨学科的 8 个
  （不再出现 cs.DB / cs.DC 等），类别输入框与提示改用 `cs.LG`；
- **`interests.example.json` 的 `topics` 改为空数组**：模板不再带"示例主题"，
  新用户首次打开画像页看到的是真正的空状态（原文的示例主题会进入打分并显示在主题列表里）；
- **`paths.py` 新增 `packs_dir()` / `PACKS`**，并把数据包根目录纳入 `python paths.py` 的诊断输出；
- **`.gitignore` 增加包内高敏文件的路径级排除**（`summaries/rec_notes/highlights`），
  `library/behavior/profile_state` 由既有的文件名规则覆盖——同一个包里可以同时放
  "可公开的画像"与"不该公开的阅读史"，而不靠人记得别提交；
- `build_report.build_profile_page()` 增加 `packs` 占位符；`server._Runtime.ALLOWED` 放行 `DP`；
- 数据包导入的拒绝返回 `400`，界面据 `ok` 弹出逐文件原因（不再静默）。

### 文档

- 新增 [私人数据隔离](docs/architecture/data-isolation.md)（现状审计 / 三层模型 / 格式选型 /
  导入语义 / 边界 / 备选方案 / 验收标准 / 迁移）；
- 重写 [预设（数据包）指南](docs/guide/presets.md)；更新 `README`、文档中心与 MkDocs 导航、
  `reference/{cli,http-api,data-files,config,interests}`、`architecture/modules`、
  `meta/{structure,faq}`、`getting-started/{installation,quickstart}`、`contributing/testing`。

---

## 2026-10-20（通用化：类别不再限定 cs.*）

从「arXiv cs.* 六分类摘要」扩展为**通用的 arXiv paper digest**：分类由用户自选，
支持官方全部 155 个分类。数据文件与既有接口保持兼容（`categories` 仍是字符串数组），
新增能力全部向下兼容。

### 新增

- **`arxiv_cats.py`**：arXiv 官方分类表（20 个 archive / 155 个分类，含中英文名），
  以及 `validate()` / `suggest()` / `search()` / `taxonomy()` / `neighbors()`。
  分类从「散落在三处硬编码」变为一份数据；`python arxiv_cats.py` 可自检；
- **`/profile` 的「🗂 arXiv 类别」选择器**：两个**联动**下拉框（先主类 `abc` 再子类 `def`），
  都支持搜索（分类号 / 英文名 / 中文名）与多选；选中的分类以标签呈现，**可拖拽排序**（带拖柄、
  落点竖线与 grab 光标）、可删除；另有手动输入框做**即时合法性校验**（变绿显示中文名 / 变红说明原因）；
- **`GET /api/arxiv_categories`**：分类表接口（页面同时内嵌同一份 JSON）；
- **`POST /api/category` 新增 `add_many` / `reorder` / `set`** 三个 op（批量添加、拖拽排序、整体替换）；
- **`run_daily.py --categories cs.DB,cs.DC`**：命令行一次配好分类（无 GUI 环境用）；
- **`templates/welcome.html`** + `build_report.build_welcome()`：未选分类时的引导页（替代原来的 404 文本）；
- 新增 115 个用例（666 总数），其中 `tests/unit/test_arxiv_cats.py`（54）与
  `tests/e2e/test_category_picker_ui.py`（15，真实 Edge + CDP，含拖拽）。

### 变更

- `config.example.json` 的 `categories` 改为**空数组**：本工具不再预设任何研究领域。
  首次 clone 打开 `/` 看到的是「先选分类」引导页，`/profile` 里没有任何分类标签；
  六个 cs 分类（cs.DB / cs.DC / cs.FL / cs.LO / cs.PL / cs.SE）保留在 `presets/hengxin/`
  作为**个人示例配置**，供 `tools/preset.py import hengxin` 按需导入；
- 分类合法性校验统一收敛到 `arxiv_cats.validate()`：格式（`abc.def` 或单段 `quant-ph`）、
  大小写（`CS.DB` → 提示正确写法）、是否在官方表内（`cs.ZZ` → 近邻纠错）、
  只写主类（`physics` → 提示需要子类）。`customize.add_category` 改用同一入口，
  并新增 `add_categories()` / `reorder_categories()` / `set_categories()` / `categories_view()`；
- `expand_categories` 留空时**自动推导**：取所选分类同 archive 的兄弟分类
  （选 `cs.DB` → 其余 `cs.*`；选 `math.LO` → 其余 `math.*`），不再写死一串 cs.xx；
- 摘要页与 Markdown 标题从 `arXiv cs.* 新论文摘要` 改为 `arXiv 新论文摘要`；
  「兴趣扩展」的说明文案从「六分类之外」改为「你跟踪的类别之外」；
- 分类小节的顺序 = `config.json` 里 `categories` 的顺序（拖拽排序后点「↻ 重算推荐」即生效）；
- `run_daily.py` 在 `categories` 为空时不抓取、只给引导并确保服务在线（不再静默跑空）；
- `tests/e2e/cdp.py`：浏览器用例的 Edge+CDP 底座从 `test_ui_browser.py` 抽出共用。

### 文档

- 新增 [arXiv 类别](docs/reference/categories.md)：分类表来源、界面交互、校验规则、顺序语义；
- 更新 README（特性/快速开始/界面一览/项目结构）、
  [config.json](docs/reference/config.md)、[HTTP API](docs/reference/http-api.md)、
  [快速开始](docs/getting-started/quickstart.md)、[安装](docs/getting-started/installation.md)、
  [模块职责](docs/architecture/modules.md)、[架构总览](docs/architecture/overview.md)、
  [FAQ](docs/meta/faq.md)、[术语表](docs/meta/glossary.md)、[目录职责](docs/meta/structure.md)、
  [预设](docs/guide/presets.md)、[测试与回归](docs/contributing/testing.md)、
  [文档中心](docs/documentation.md)；
- 覆盖率表按实测更新为 666 用例 / 90%，新增 `arxiv_cats.py`（99%）一行。

---

## 2026-10-17（全方位重构）

对外行为与接口**无破坏性变更**：全部 HTTP 路由、CLI 参数、数据文件格式保持不变。
验证方式见「文档」一节的兼容门面清单与逐字节比对。

### 新增

- **`paths.py`**：路径的唯一权威定义（原先散落在 10 个模块各写 `os.path.join(HERE, …)`）。
  附 `python paths.py` 诊断命令，一次列出全部路径并标出是否已生成；
- **`scoring.py`**：打分纯函数层（`_rx` / `topic_hits` / `base_score` / `features` / `score`）。
  公式里的魔数提取为命名常量（`TITLE_HIT_W` 等），文档与代码可逐项对照；覆盖率 100%；
- **`textscan.py`**：文本 → 结构化信号（`strip_html` / `extract_people` / `extract_keywords` /
  `matched_topics`），不读文件、不联网，可用字符串字面量直接测；
- **`fetchsrc.py`**：来源取数适配（arXiv / 网页 / 本地文档），统一返回 `(meta, err)`；
  网络取数通过 `_get` 注入，单测不联网；
- **`service.py`**：业务用例层（收藏 / 下载 / 画像学习 / 重建 / `PaperIndex`），不认识 HTTP；
- **`routes.py`**：HTTP 语义层（`@get` / `@get_prefix` / `@post` 路由表、`Request`、`Reply`、
  `table()` 清单）；
- **`templates/`**：`style.css` / `app.js` / `page.html` / `favorites.html` / `profile.html` /
  `archive.html`，从 `build_report.py` 的内联字符串移出；
- **`tests/unit/test_compat_facade.py`**：兼容门面清单，逐一断言旧符号仍可导入；
- 新增 246 个用例（551 总数），覆盖率 87% → **89%**。

### 变更

- `server.py` 从 637 行降到约 250 行：`do_GET` / `do_POST` 的两个 if 链改为路由表分发，
  处理器只做参数校验与响应拼装；`_Runtime` 以白名单暴露能力，且**每次访问回查本模块**，
  因此 `server.download_pdf = stub` 这类外部替换仍然生效（并发回归依赖这点）；
- 动态页的 `importlib.reload(build_report)` 从三处收敛到 `digest_module()` 一处并加锁；
- `build_report.py` 从 1679 行降到约 800 行（版面外置）；`read_template()` 按 mtime 缓存，
  **改模板不再需要重启服务**；
- 端口占位符 `__APIPORT__` 改为**渲染时**替换（`render_js()`），改 `config.port` 后重新生成
  页面即生效；
- `customize.py` 从 843 行降到约 620 行：文本处理与网络取数移出，原符号以
  **re-export + 注入型包装** 保留（`monkeypatch.setattr(customize, "_http_get", …)` 仍有效）；
- `recommend.py` 的 `features` / `score` / `_rx` 改为从 `scoring` re-export；
- `download_one` / `download_many` 增加 `download_fn` / `learn_fn` 注入点，批量下载与单篇
  下载的桩化行为保持一致。

### 修复

- **页面端口与服务端口不一致导致交互被回滚**：`live_server` 用随机端口，而页面里的
  `APIBASE` 仍取 `config.port`，前端请求失败后乐观更新回滚，表现为「点了按钮没反应」。
  改为 `live_server` 把实际端口写回 config，且端口在渲染时替换；
- **UI 回归的导航竞态**：`Page.navigate` 后 `location.href` 已变但 `document` 仍是上一份
  （`about:blank` 也是 `complete`），`goto()` 会提前返回、断言在旧文档上执行。改为在旧文档
  打标记、新文档里该标记必然不存在。

### 文档

- 重写 [模块职责](docs/architecture/modules.md)：18 个模块分五层，含依赖方向图与
  「我要改什么」定位表；
- 更新 [架构总览](docs/architecture/overview.md) 分层图、[服务运行时](docs/architecture/server-runtime.md)
  的路由表与锁清单、[目录职责](docs/meta/structure.md) 的目录树与「拆模块 ≠ 包化」说明；
- 更新 [测试与回归](docs/contributing/testing.md)：551 用例 / 89% 覆盖 / 分层清单，
  新增「重构时怎么保证没改行为」一节（兼容门面 / 逐字节等价 / 桩化契约）。

---

## 2026-10-17（测试套件）

### 新增

- **pytest 测试套件**：305 个用例分四层——`tests/unit`（234）、`tests/integration`（63）、
  `tests/e2e`（5）、浏览器层（3，Edge + CDP），行覆盖率 **87%**，门槛 85%（`.coveragerc`）；
- `tests/conftest.py`：沙箱隔离（10 个模块的路径常量重定向到 `tmp_pytest/`）+ 数据工厂
  （`make_paper` / `pool` / `seeded`）+ 真实 HTTP 客户端（`live_server` / `http`）；
- `tests/unit/test_sandbox_isolation.py`：测试**自身**的回归——隔离断言 + 自动发现未登记的
  `OUT = pu.OUT` 模块，防止再出现「测试写坏真实 output/」；
- `requirements-dev.txt`（pytest / pytest-cov / websocket-client）、`pytest.ini`、`.coveragerc`。

### 修复

测试过程中发现并修掉的三处真实缺陷：

- **多词关键词永不命中**（`recommend._rx`）：链式 `replace` 把 `[\s\-]` 里的 `\-` 再改一遍，
  产出的字符类变成 `[\\s[\\s\\-]?]`（`?` 字面化、`]` 提前闭合），`isolation level` 这类
  短语一次都匹配不上，表现为「分数普遍偏低」而不报错。改为按分隔符切词后拼装，并补回归；
- **`short_id` 不认 `arXiv:` 前缀与空白**：`arXiv:2609.09742v2` 会原样留下前缀，
  与库文件 key 对不上（接口文档却声称会归一化）。现在统一 strip + 去前缀 + 去版本；
- **单位判定把国家代码当美国州**（`fetch_affil`）：`Manchester, UK` / `Shanghai, CN`
  命中「城市, 两位代码」正则，整批英国/中国单位被丢弃。改为「有机构关键词时不按城市拒绝」；
- `fetch_arxiv.main()` 对累积池里缺 `primary` 的老条目 `KeyError`，导致整轮抓取在 merge 后崩掉；
- `customize._save_cfg_patch()` 用 `HERE/config.json` 而非 `paperutil.CONFIG_PATH` 写配置，
  重定向后出现「读 A 写 B」。

### 文档

- 重写 [测试与回归](docs/contributing/testing.md)：分层表、覆盖范围（核心模块 / 关键流程 /
  边界）、逐模块覆盖率、运行方式、沙箱三条硬性设计、断言约定、失败排查、「保持全绿」约定；
- 新增 [tests/README.md](tests/README.md)（最短上手路径）；
- README 的质量闸门改为「pytest 为主 + `tools/*_check.py` 为发布前黑盒验收」，补徽章与结构图。

---

## 2026-10-17

### 文档

- 重构为六层文档体系（`getting-started` / `guide` / `reference` / `architecture` /
  `contributing` / `operations` / `meta`），共 21 篇，每篇单一职责、相互用相对链接引用；
- 新增 [文档中心](docs/documentation.md)（按"我要做什么"定位）与根 [README](README.md) 的完整索引；
- 新增 [CONTRIBUTING.md](CONTRIBUTING.md)、[CHANGELOG.md](CHANGELOG.md)；
- 原 `docs/CONFIG.md` → [reference/config.md](docs/reference/config.md)（拆分出
  [reference/interests.md](docs/reference/interests.md)），
  `docs/ARCHITECTURE.md` → [architecture/overview.md](docs/architecture/overview.md)，
  `docs/PRESETS.md` → [guide/presets.md](docs/guide/presets.md)；
- 新增参考：[命令行](docs/reference/cli.md)、[HTTP API](docs/reference/http-api.md)、
  [数据文件](docs/reference/data-files.md)；新增概念：[模块职责](docs/architecture/modules.md)、
  [排序与学习算法](docs/architecture/ranking.md)、[服务运行时](docs/architecture/server-runtime.md)；
- 新增流程类：[日常使用](docs/guide/daily-workflow.md)、[调优画像](docs/guide/profile-tuning.md)、
  [视频与投稿](docs/guide/video-pipeline.md)、[开发指南](docs/contributing/development.md)、
  [测试与回归](docs/contributing/testing.md)、[故障排查](docs/operations/troubleshooting.md)；
- 新增元信息：[目录职责](docs/meta/structure.md)、[FAQ](docs/meta/faq.md)、
  [术语表](docs/meta/glossary.md)。

### 变更

- 文档不再平铺在 `docs/` 根目录，按用途分子目录；所有旧路径已迁移，无断链；
- README 改为"门面 + 完整文档索引"，技术细节下沉到 `docs/`。

---

## 2026-10-17（公开化重构）

### 变更

- 剥离个人数据：`config.json` / `interests.json` 不再入库，改由 `*.example.json` 首次运行生成；
  作者本人的设置转为可选预设 `presets/hengxin/`；
- 一次性脚本（补摘要、迁移 key、改下载目录等）移入 `presets/hengxin/legacy/`；
- 「画像主线」文案改为按 `interests.json` 主题现算，不再硬编码作者的研究方向；
- 启动脚本与工具中的本机 Python 路径改为自动探测；
- 新增 `tools/preset.py`（list / import / export），导入前自动备份到 `output/backup/<时间>/`。

### 新增

- 薄画像兜底：严格阈值一篇不达标时按分数取前 N 并标注，仅在该期为 0 时触发；
- `.gitignore` 按公开仓库重写：产物、个人数据、凭据、依赖、本机状态全部排除。

### 修复

- `recommend.load_profile()` 直接索引 `negative["weight"]`，新用户用模板时会 `KeyError`；
- `interests.example.json` 缺 `negative.weight` 字段。

### 文档

- 新增 `docs/CONFIG.md`、`docs/ARCHITECTURE.md`、`docs/PRESETS.md`（已于同日重构时迁移）。

---

## 2026-10-17（仓库独立）

### 变更

- 从 `0xaiio/coworkers` 的 `git-paper/arXiv` 子目录抽出为独立仓库 `0xaiio/arXiv-digest`，
  用 `git filter-repo --subdirectory-filter` 保留全部相关提交（作者 / 日期 / 信息原样）；
- 新增 `.gitignore`（公开仓库口径）与 `README` 的"仓库与自动推送"说明；
- 新增 `tools/git-hooks/post-commit`（提交后自动 `git push`，30s 超时、失败不阻断提交）
  与幂等安装脚本 `install.sh`。

---

## 2026-10-17（交互与并发）

### 变更

- **统一三个模块的 Downvote 表现**：为你推荐 / 兴趣扩展 / 分类详解（含重点论文块与收藏列表）
  共用一组 CSS（`opacity .42` + 标题删除线），共用同一个 `setDv()`；
- Downvote 后卡片**不再隐藏**，而是钉在点击时的位次（`data-dvpos`），可再点一次撤销；
- `data-limit` 只约束未 Downvote 的条数，灰色卡片额外保留；
- 前端收藏 / Downvote 改为**乐观更新**，重排由 `queueResort()` 在 30ms 内合并执行。

### 修复

- 服务端原用一把全局锁包住整个 `/api/download`（含最长 90s 网络取数），
  下载一篇期间所有收藏 / Downvote 请求排队。现拆为 `_lib_lock`（仅保护库文件读-改-写）
  与每篇论文独立的 `dl_lock(sid)`；
- `/api/download_all` 改为 `DL_WORKERS=3` 线程池并发。

### 测试

- 新增 `tools/concurrency_check.py`：下载中另一篇 Downvote 从 2.00s → 0.014s；
  批量 3 篇从 6.0s → 2.05s；同一篇并发仍串行；
- 新增 `tools/dv_unify_check.py`：三处 Downvote 的 opacity / 删除线 / 不隐藏 / 可撤销。

### 文档

- `README` 新增"交互：Downvote 语义与动作并发"，`server.py` 文档串与页面文案同步改写。

---

## 2026-10-17（画像主来源）

### 新增

- `/profile` 的「画像主来源」（`interests.json` 的 `owners`）支持**增 / 删 / 改**，
  新增 `POST /api/owner`（`op=add|update|remove`）；
- 支持改名（按原名定位）、`people_linked` 联动"熟悉研究者"（改名同步替换、删除一并撤销）；
- 摘要页头部「基于 A × B × C 的兴趣画像」改为渲染期生成，加人后重算即同步；
- 新增回归 `tools/owner_ui_check.py`（只用临时条目，结束即清理）。

### 修复

- 页面模板中内联 JS 写 `'\n'` 会被 Python 的 `%` 格式化先解析成真换行，
  导致整段脚本语法错误（表现为按钮"没反应"）；改为 `\\n`。

---

## 2026-10-17（B 站合集）

### 新增

- `tools/bili_collection.py`：B 站合集（season）管理，支持 `videos` / `collections` /
  `cover` / `create` / `add` / `sync`，默认 dry-run，`--exec` 才写；
- `sync` 幂等：只把未挂载的「arXiv 日报」视频加入合集「arXiv-daily」，已挂载的跳过。

---

## 2026-10-16

### 修复

- **推荐器整体失效**（当期新增 164 篇、0 篇达到推荐线）：
  根因是 Downvote 同时惩罚论文、主题倍率与 45 个 token，在曝光偏置下把五个主研究方向
  全部打到 0.25 下限，领域通用词（`distributed`、`data`）累积到 -3 以下；
- 新增 `profile.learn_neg_topics` / `learn_neg_keywords` 开关（**默认 false**），
  Downvote / 撤销只保留论文级 -12，全局学习仅由正向行为驱动。

### 文档

- 记录排查协议：先看全池 Top10 是否正常，用中性基线对照分离"内容弱"与"画像坏"。

---

## 2026-10-14

### 修复

- Edge TTS 报 `403 WSServerHandshakeError`：`edge-tts` 7.2.8 的签名被服务端拒绝，升级到 7.3.1 后恢复；
- 口播稿字数改为按实测语速反推上限（`0.9 × 1.25 × base_rate × 18.6`），取代凭感觉估字。

---

## 2026-10-05 ~ 10-10

### 新增

- B 站投稿端到端打通（`BV1mKH76UEc9`），`bili-auto-upload` 技能成型：
  `check` / `meta` / `cover` / `upload` / `verify` / `comment`，默认 dry-run；
- 投稿必须走 **TV 通道扫码**（Web 扫码拿不到 App 接口的 `access_token`，会以 `-400` 失败）。

### 修复

- WinGet 未开开发者模式时会留下 **0 字节的 `biliup.exe` 符号链接**，且它在 PATH 中优先级最高，
  导致"程序无法运行"；脚本改为探测包目录真实 exe 并自愈空壳；
- `reply/send` 接口下线，改用 `reply/add`；补 `-60 审核中` 状态；`12051` 幂等处理；
- Edge TTS 挂死加 45s 超时重试。

---

## 2026-09-30 ~ 10-03

### 新增

- 视频链路 v2：Remotion 代码渲染（1920×1080 / 30fps）+ Edge TTS 中文旁白 +
  `tools/check_video_av.py` 质量闸门（总时长 / 音轨 / 逐段人声起点 / 段内静音）；
- 视频从 5 篇扩到 **10 篇**（推荐 8 + 兴趣扩展 2），片头 5s + 每篇 20s + 片尾 5s。

---

## 2026-09-17 ~ 09-18

### 新增

- 项目首次入库：抓取、打分、渲染、本地服务、行为画像、归档；
- `tools/gen_pending.py` 按短号去重导出待补中文摘要清单（修掉重复条目高估数量的问题）。

---

## 更早（功能上线期）

- 归档层：`archive.db` 的 `seen` 表判定"本期新增"，日报不再重复播放旧论文；
- 抓取降级：API 限流时改抓分类 RSS，按短号**并集**合并进累积池；
- 下载选路：`netroute.py` 在直连 / 环境代理 / 本机代理之间自动挑一条能拿到 `%PDF` 的出口。

---
