# arXiv-digest

把 arXiv 的每日新论文，按**你自己的研究画像**排序，生成一个可交互的本地日报：
收藏、下载 PDF、就地展开摘要、Downvote 反馈，全部离线可用，点一次就当场学会你的口味。

> 默认初始化是**干净的**：clone 下来不会带上任何人的研究兴趣、分类偏好或本机路径。
> 作者本人那套完整设置作为**可选预设**放在 `presets/hengxin/`，需要时一条命令导入。

```
run_daily.py   →  抓取 → 推荐 → 抓作者单位 → 渲染日报 → 起本地服务
                     ↓
              http://127.0.0.1:8765/   今日推荐 + 兴趣扩展 + 分类详解
```

---

## 1. 它适合谁

| 你的情况 | 怎么用 |
| --- | --- |
| 盯 1–3 个方向的日常跟进（如 PL / 形式化 / 系统 / DB） | 把 `categories` 设成这几个分类，`topics` 写 3–6 个主题关键词；每天扫一遍推荐列表即可 |
| 想在主方向之外**顺带看看邻域**（避免信息茧房） | 主分类 + `expand_categories`：「兴趣扩展」区独立打分，不占你的推荐位 |
| 跨领域（比如做 ML 但关心系统 / 理论） | 主分类放 ML、扩展分类放系统与理论，两个区各自成篇 |
| 只想先看看长什么样 | `python tools/preset.py import hengxin` 导入作者的完整画像，跑一遍再改成自己的 |

不依赖任何云服务：抓取走 arXiv 官方 API（限流时自动降级 RSS），打分与页面全在本地。

## 2. 五分钟上手

```bash
git clone git@github.com:0xaiio/arXiv-digest.git
cd arXiv-digest

python run_daily.py            # 首次运行会自动生成 config.json / interests.json（干净模板）
```

跑完浏览器会自动打开 `http://127.0.0.1:8765/`。之后：

```bash
python run_daily.py --skip-fetch --skip-affil   # 复用已抓数据，只重算推荐 + 重渲染（秒级）
python server.py                                 # 只起服务（不重新抓取）
```

Windows 上也可以双击 `start_digest.bat`（自动找 `python`，端口读 `config.json`）。

> 需要 Python 3.9+，**运行期只用标准库**，不需要 `pip install`。
> 视频链路（可选）另需 Node 与 `edge-tts`，见 `docs/ARCHITECTURE.md`。

## 3. 目录结构

```
arXiv-digest/
├─ run_daily.py            # 一键流水线（抓取 → 推荐 → 单位 → 渲染 → 起服务）
├─ fetch_arxiv.py          # 主分类抓取（config.categories）
├─ fetch_expand.py         # 兴趣扩展抓取（config.expand_categories）
├─ fetch_rss.py            # 降级通道：API 限流时改抓分类 RSS，按短号增量合并
├─ fetch_affil.py          # 从 arXiv HTML 解析作者单位（带跨日缓存）
├─ recommend.py            # 打分与推荐（主题命中 / 熟悉作者 / 代表系统 / 负向词）
├─ profile.py              # 行为画像：收藏 / 下载 / Downvote → 主题倍率与关键词权重
├─ archive.py              # 归档层（SQLite）：判定「本期新增」、留档往期
├─ build_report.py         # 渲染日报 HTML/MD、收藏页、/profile、/archive
├─ server.py               # 本地服务（127.0.0.1:8765）：收藏 / 下载 / Downvote / 画像
├─ netroute.py             # 下载取数选路（直连 / 环境代理 / 本机代理）
├─ customize.py            # 可定制项读写：分类、下载目录、兴趣来源、画像主来源
├─ paperutil.py            # 命名、库文件、配置读写
│
├─ config.example.json     # 默认配置模板（机器无关）→ 首次运行生成 config.json
├─ interests.example.json  # 空白画像模板 → 首次运行生成 interests.json
├─ presets/                # 可选预设（示例画像），默认不生效
│   └─ hengxin/            #   作者本人那套：4 位主来源 / 14 主题 / 61 位熟悉作者
├─ docs/
│   ├─ CONFIG.md           # config.json 与 interests.json 每个字段的说明
│   ├─ ARCHITECTURE.md     # 流水线、打分公式、归档、并发模型、视频链路
│   └─ PRESETS.md          # 预设的导入 / 导出 / 自己造一份
├─ tools/                  # 辅助脚本与回归测试（见 §7）
└─ reel/                   # 可选：每期视频（Remotion 代码渲染 + Edge TTS 中文旁白）
```

**哪些是个人数据（默认不进版本库）**：`config.json`（含本机下载路径与你的分类）、
`interests.json`（你的画像）、`output/`（日报、收藏、下载记录、归档库）、`.secrets/`（凭据）。
只有模板 `*.example.json` 与预设 `presets/` 入库。

## 4. 配置与画像

两个文件，都在首次运行时自动生成：

- `config.json` — 抓什么、存哪里、每期推荐几条。`download_dir` 支持相对路径（默认 `papers/`）。
- `interests.json` — 画像种子：`topics`（主题 + 关键词）、`people`（熟悉作者）、
  `signature_systems`（代表系统）、`negative.keywords`（降权词）、`owners`（画像主来源）。

字段逐项说明见 **[docs/CONFIG.md](docs/CONFIG.md)**。
日常维护不必手改 JSON：打开 `/profile` 页就能改下载目录、增删分类、维护画像主来源、
点关键词屏蔽噪音词；改完点工具栏 **↻ 重算推荐** 立即生效。

## 5. 示例预设（可选）

`presets/` 里放的是「一整套现成设置」，**默认不加载**：

```bash
python tools/preset.py list                    # 看有哪些预设、各自包含什么
python tools/preset.py import hengxin          # 导入（本地已有同名文件时会拒绝）
python tools/preset.py import hengxin --force  # 覆盖导入：原文件先备份到 output/backup/<时间>/
python tools/preset.py export myown            # 反过来：把当前设置存成预设（可提交分享）
```

导入前**先把 `download_dir` 改成你自己的路径**。详见 [docs/PRESETS.md](docs/PRESETS.md)。

## 6. 页面里有什么

| 区域 | 说明 |
| --- | --- |
| 🎯 为你推荐 | 主分类里本期最相关的 N 篇（默认 14），带推荐理由与命中主题 |
| 🌱 兴趣扩展 | 主分类之外、与你画像相邻的论文（默认 10），用来打破茧房 |
| 📖 分类详解 | 本期全部新论文，按分类与日期排 |
| 工具栏 | 已收藏 / 已下载 / 已 Downvote 筛选、搜索、批量下载、往期回看 |
| `/favorites` | 收藏清单（可导出 Markdown） |
| `/profile` | 类别、下载目录、兴趣来源、画像主来源、主题权重 |
| `/archive` | 每期快照，按日期回看（日报只呈现**本期新增**，往期进这里） |

交互细节（Downvote 为什么是「变灰 + 删除线」、按钮为什么能并发、列表为什么不会跳）见
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 7. 质量闸门

改完代码建议跑一遍（除并发测试外都需要浏览器）：

```bash
python tools/concurrency_check.py    # 并发：下载中另一篇 Downvote 不被阻塞、批量并行
python tools/dv_unify_check.py       # 三个模块的 Downvote 视觉 / 行为一致
python tools/owner_ui_check.py       # /profile 画像主来源增删改（只用临时条目）
python tools/ui_file_check.py output/arxiv_digest_<日期>.html   # 本地 HTML 跨源交互
python tools/dl_button_check.py      # 真实点一次下载按钮
```

## 8. 常见问题

| 现象 | 处理 |
| --- | --- |
| 打开 8765 显示「尚无摘要页」 | 还没跑过流水线：`python run_daily.py` |
| 推荐区是空的 / 分数都很低 | 画像太空：在 `/profile` 补主题关键词，或导入一份预设先跑起来 |
| 下载按钮报错 | `python netroute.py` 看出口路由；服务在跑时看 `GET /api/net_route` |
| 分类改了但没出现新论文 | 需要重新抓取：`python run_daily.py`（删分类只影响下次抓取） |
| 想从头再来 | 删 `config.json` / `interests.json` / `output/`，再跑一次即按模板重建 |

## 9. 许可

目前未附开源许可（默认保留所有权利）。如需在他人项目中复用，欢迎先开 issue 讨论。

---

作者本人的实例：研究画像为数据库系统 / 分布式计算 / 形式化方法，那份完整设置就是
`presets/hengxin/`。
