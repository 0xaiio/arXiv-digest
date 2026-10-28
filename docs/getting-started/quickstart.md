# 快速开始

10 分钟走完一次完整闭环：**跑流水线 → 读日报 → 用反馈改画像 → 看见排序变化**。
每一步都给出"应该看到什么"，方便判断是否成功。

前置：已完成 [安装](installation.md)（`git clone` + Python 3.9+）。

---

## 步骤 0 · 先选分类（通用版必做一步）

本工具**不预设任何领域**。第一次克隆打开时 `categories` 是空的，你有三种选法：

```bash
python run_daily.py --categories cs.DB,cs.DC      # ① 命令行一次配好，然后自动开始抓取
python run_daily.py --preset hengxin              # ② 导入一份现成数据包（含类别 + 画像）
```

③ 或者跑一次 `python run_daily.py`，它会提示你还没选分类、并把服务拉起来，然后到
`http://127.0.0.1:8765/profile` →「🗂 arXiv 类别」：
先选主类 `abc`（如 `cs`），再选子类 `def`（如 `DB`），两个下拉框都能搜索、都能多选；
标签可拖拽排序、可删除。选好后再跑一次 `python run_daily.py`。

> 想直接看一份现成的六分类配置（数据库 / 分布式 / 形式化方法）：
> 到 `/profile` →「📦 数据包」点「导入」，或 `python tools/preset.py import hengxin`；
> 导入后同样要重跑一次。数据包**默认不加载**，所以你现在看到的是干净的界面。
>
> 分类的完整说明见 [arXiv 类别](../reference/categories.md)。

## 步骤 1 · 跑第一次流水线（约 1–3 分钟）

```bash
python run_daily.py
```

首次运行会生成干净的 `config.json` / `interests.json`，按你选的分类抓取并打分，最后把服务拉起来。

预期输出（节选，顺序可能略有不同）：

```
[categories] 已设置 2 个分类：cs.DB、cs.DC
[init] 已按 config.example.json 生成 config.json。categories 默认为空：请在 /profile 的「arXiv 类别」面板里自选，
       或 `python run_daily.py --categories cs.DB,cs.DC` 指定；download_dir（PDF 保存目录）也可在那里改。
$ .../fetch_arxiv.py
[ok] fetch_arxiv.py -> raw.json (1834221 bytes)
$ .../fetch_expand.py
[ok] fetch_expand.py -> raw_expand.json (5420188 bytes)
$ .../recommend.py
[issue 20261017] strict | pool 412/1180 -> new 164/221
core 164 -> rec 14 | expand pool 221 -> rec 10
  C   23.4 2609.09742 cs.DB    ...
$ .../fetch_affil.py
$ .../build_report.py
.../output/arxiv_digest_20261017.html
[archive] issue 20261017: 164 papers, 14 recs, 10 exps -> .../output/archive.db
digest online: http://127.0.0.1:8765
```

> **地址以打印结果为准**：默认端口 8765，若它已被别的程序占用，服务会自动向后顺延
> （8766、8767…）并在这个位置打印实际地址；页面里的接口端口会一起改写，无需手工干预。
> 想固定在某个端口，改 `config.json` 的 `port` 或启动时加 `--port`。

**检查点**

| 检查项 | 命令 / 位置 | 期望 |
| --- | --- | --- |
| 服务在线 | `curl --noproxy '*' http://127.0.0.1:8765/api/ping` | `{"ok": true}`（端口若被顺延，换成实际端口） |
| 实际端口 | `output/server.json` 的 `port` 字段 | 与启动日志里 `serving ...` 那一行一致 |
| 日报落盘 | `ls output/arxiv_digest_*.html` | 有一个 `arxiv_digest_<今天>.html` |
| 归档登记 | 打开 `/archive` | 今天这一期在列表里 |

如果推荐数是 0 或明显偏少：这是**画像还很薄**的正常表现，走完步骤 4 就会改善。原理见
[排序与学习算法](../architecture/ranking.md)。

## 步骤 2 · 读日报的三个板块

打开 `http://127.0.0.1:8765/`：

| 板块 | 来源 | 数量 | 用途 |
| --- | --- | --- | --- |
| 🎯 为你推荐 | `config.categories` 主分类 | `top_recommend`（默认 14） | 今天最值得看的一屏 |
| 🌱 兴趣扩展 | `config.expand_categories` 邻域分类 | `top_expand`（默认 10） | 打破信息茧房，独立打分、不占推荐位 |
| 📖 分类详解 | 本期全部新增论文 | 全部 | 按分类与日期浏览，可能有推荐没覆盖到的好文章 |

每张卡片上有：编号、标题、作者（命中"熟悉研究者"的人名会高亮）、评分、命中主题、推荐理由、
**双语简介（上行英文、下行中文）**，以及按钮 **收藏 / 下载 / Abstract (EN) / Abstract (CH) / arXiv ↗ / Downvote**。

**试试这个**：点一次 `Abstract (EN)`，英文原文摘要就地展开；再点 `Abstract (CH)`，切换到它的
中文译文（两个版本互斥展开，译文缺失时会提示去哪里补）。这两次点击同样会回传服务端，
作为弱正向信号。

`arXiv ↗` 是去站外（arXiv 上的论文页，新标签页），按钮上的红色 arXiv 字标与外链箭头就是
这个意思——要把 PDF 存到本地，用左边的 `下载`。

## 步骤 3 · 体验交互（收藏 / 下载 / Downvote）

1. 点某篇的 **收藏** → 按钮变成 `已收藏 ★`，左侧工具栏的"已收藏"计数 +1；
2. 点 **下载** → 按钮短暂显示"下载中…"，成功后冒出一条 toast，PDF 落到 `config.download_dir`
   （默认 `./papers`），同时**自动收藏**，按钮变为 `已下载`；
3. 再点一次 **已下载** → 用系统默认阅读器打开本地 PDF（tooltip 会显示"打开本地文件"），
   不会重新下载；
4. 点 **Downvote** → 该卡片当场变灰 + 标题加删除线，**留在原位**（不消失，方便纠错），
   排名里它被钉在原来的位次上；
5. 再点一次 **已 Downvote** → 恢复原状。

三个板块（为你推荐 / 兴趣扩展 / 分类详解）的 Downvote 表现完全一致，因为它们共用同一个
`setDv()` 与同一组 CSS。设计细节见 [服务运行时](../architecture/server-runtime.md)。

> 下载失败？先看 `python netroute.py` 的输出，再对照
> [故障排查](../operations/troubleshooting.md) 第 4 节。多数是出网路由问题，与代码无关。

## 步骤 4 · 改画像，立刻看到差别

打开 `http://127.0.0.1:8765/profile`（工具栏的 ⚙ 也能进）：

1. **arXiv 类别**：两个联动下拉框（先主类 `abc` 再子类 `def`，可搜索、可多选），选好的分类以标签呈现，
   **拖动标签即可调整顺序**（顺序 = 摘要页分类小节的顺序），点 × 删除。建议只留真正每天要看的 2–6 个。
   新增后需要重抓才会出现该分类的论文；
2. **画像主来源**：点"新增"，填姓名、主页、机构、研究方向。勾选"同时计入熟悉研究者"时，
   该作者的论文每篇 +10 分；
3. **主题与关键词**：给每个主题维护关键词列表。命中标题每个 +4（最多算 4 个），
   命中摘要每个 +0.8（最多 15 个），再乘该主题的种子权重；
4. **兴趣来源**：贴个人主页、某篇论文或本地文档，系统会从中抽出人名与专业实词，
   汇总成主题「我的来源关注」（权重 0.6）。

改完点工具栏的 **↻ 重算推荐**。它会在后台重跑推荐并重渲染页面，几十秒后刷新即可看到新排序。

**检查点**：把某个主题的 `weight` 从 1.0 提到 2.0，重算后该主题论文应明显上浮；
把某个无关热点词加进 `negative.keywords`，命中它的论文应下沉但**仍留在分类详解里**。

## 步骤 5 · 用数据包试跑（可选）

不想从零调画像，可以先导入一份调了半年的真实设置：

```bash
python tools/preset.py list              # 看有哪些、各自包含什么
python run_daily.py --preset hengxin     # 导入 + 重跑（一条命令）
```

或者只导入、再看它跟本机差在哪：

```bash
python tools/preset.py show hengxin      # 逐文件：新增 / 一致 / 需 --force
python tools/preset.py import hengxin    # 等价于 /profile →「📦 数据包」→ 导入
python run_daily.py --skip-fetch --skip-affil
```

两条安全规则，避免"试一下就丢了原来的设置"：

- 本机已经有 `config.json` / `interests.json` 且内容不同时，导入会**拒绝**，不加 `--force` 不会动你的文件；
- 加 `--force` 会先备份到 `output/backup/<时间>/`，再覆盖。

导入后**先**把 `download_dir` 改成你自己的目录（分享出来的包已中性化为 `papers/`）。
详见 [数据包（预设）](../guide/presets.md)。

想事先留一份自己的：`python tools/preset.py export myown --with-usage --with-notes`。

## 步骤 6 · 交付与日常

```bash
python run_daily.py --skip-fetch --skip-affil   # 只重算+重渲染，秒级
python server.py                                 # 只起服务
```

- 每天固定时间跑 `run_daily.py` 即可（Windows 任务计划 / cron / 任意调度器）；
- 日报只呈现**本期新增**，往期进 `/archive`；
- 收藏清单在 `/favorites`，可一键导出 `favorites.md`。

---

## 接下来读什么

| 你关心的事 | 文档 |
| --- | --- |
| 每天怎么高效使用这个页面 | [日常使用](../guide/daily-workflow.md) |
| 怎么把推荐调准 | [调优画像](../guide/profile-tuning.md) |
| 分数到底怎么算的 | [排序与学习算法](../architecture/ranking.md) |
| 接口能不能被脚本调用 | [HTTP API](../reference/http-api.md) |
| 想改代码 | [模块职责](../architecture/modules.md) → [开发指南](../contributing/development.md) |
