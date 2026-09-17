# arXiv cs.* 论文日报（个性化推荐 / 收藏 / 下载）

按个人研究画像（数据库系统 · 分布式计算 · 形式化方法）每日抓取 arXiv 新论文，
打分推荐并渲染成可交互的本地 HTML：Abstract 展开、收藏、下载 PDF、Downvote 反馈，
所有交互回传本地服务（127.0.0.1:8765）实时更新偏好权重。

**日报只呈现「本期新增」论文**：`raw.json` / `raw_expand.json` 是累积池（RSS 降级
通道按短号增量合并、永不删条目），若直接全池打分，前几天的高分论文会天天重复出现。
现在由 `archive.py` 的 `seen` 表切出本期新增，往期内容进存档，可在 `/archive` 按日期回看。

**日报有两种打开方式，都可用**：
1. 在线主入口 `http://127.0.0.1:8765/`（由本地服务同源提供，体验最佳）；
2. 交付的本地文件 `output/arxiv_digest_<日期>.html`，浏览器直接打开即可读、可下载留档。
   本地 HTML 里的 `fetch('/api/*')` 与站内链接（收藏 / 画像 / 存档 / 返回）会被 `APIBASE`
   改写为 `http://127.0.0.1:8765` 绝对地址（服务端带 CORS `*`），所以只要服务在线，
   按钮在本地 HTML 里同样能用。回归验证：`tools/ui_file_check.py`。

## 运行

```powershell
# 完整流水线：抓取 → 推荐 → 作者单位 → 渲染 → 确保本地服务在线
python .\run_daily.py

# 跳过作者单位抓取（该步约 3–5s/篇，耗时数分钟）
python .\run_daily.py --skip-affil

# 复用已有 raw.json / raw_expand.json，只重算推荐并渲染
python .\run_daily.py --skip-fetch --skip-affil

# 单独启动服务（不自动开浏览器）
python .\server.py --no-open
```

日常由 WorkBuddy 定时任务驱动（每天 11:30），也可双击 `start_digest.bat` 手动启动服务。

## 流水线

| 脚本 | 作用 |
| --- | --- |
| `fetch_arxiv.py` | 核心分类抓取（cs.DB / cs.DC / cs.FL / cs.LO / cs.PL / cs.SE）→ `output/raw.json` |
| `fetch_expand.py` | 相邻分类兴趣扩展抓取 → `output/raw_expand.json` |
| `fetch_rss.py` | **降级通道**：Atom API 被限流（429/503）时改抓分类 RSS 并增量合并 |
| `recommend.py` | 按画像打分，产出推荐 / 扩展 / 前端索引；**只对本期新增打分** |
| `fetch_affil.py` | 从 arXiv HTML 版解析作者单位（arXiv API 不提供），跨日缓存 |
| `archive.py` | **归档存储层**（SQLite）：`seen` 判定本期新增、`issues`/`issue_papers` 留档、快照复制 |
| `netroute.py` | **下载路由**：自动挑一条能真正取到 arXiv 的路（直连 / 环境代理 / 本机代理端口），跨进程缓存 |
| `build_report.py` | 渲染日报 HTML/MD、收藏页、`/profile` 与 `/archive` 页，并自动归档当期 |
| `server.py` | 本地服务（收藏 / 下载 / Downvote / 画像增删改 / 历史存档浏览） |
| `run_daily.py` | 一键编排上述步骤，并确保服务在线 |
| `tools/backfill_archive.py` | 把已有的 `arxiv_digest_<日期>.md/.html` 回填进 `archive.db` |
| `tools/ui_file_check.py` | **交付回归**：用 Edge CDP 以 `file://` 打开日报 HTML，断言跨源基址 / 链接改写 / 无报错 toast / 收藏点击往返 |
| `tools/dl_button_check.py` | **下载按钮回归**：真点一次下载按钮，断言 toast 与按钮态（只点已下载项，不写新文件） |

`customize.py` 是「类别 / 下载目录 / 兴趣来源」三个可定制项的唯一读写层，
`profile.py` 维护行为驱动的动态画像（主题倍率与关键词权重）。

## 页面

| 路径 | 说明 |
| --- | --- |
| `/` | 当期日报（**只含本期新增**；Abstract / 收藏 / 下载 / Downvote 全部可用） |
| `/favorites` | 收藏列表 |
| `/profile` | 兴趣画像与设置（增删类别 / 兴趣来源 / 下载目录） |
| `/archive` | **历史存档总览**：按日期列出往期日报（日期 / 周几 / 新增 / 推荐 / 扩展） |
| `/archive/<YYYYMMDD>` | 某一期的日报快照（当时那一版，交互按钮同样可用） |
| `/api/archive/days` | 存档日期与统计（JSON） |
| `/api/net_route` | **下载路由诊断**：当前选中的路由、候选数、上次失败摘要（下载报错时先看这里） |

## 下载取数：为什么要挑路由

`/api/download` 由本地服务进程发起出网请求。这台机器上同时存在三种出口，且**只有一种能取到 arXiv**：

| 出口 | 表现 |
| --- | --- |
| 直连 | 被拦 → `WinError 10054`（连接被重置） |
| 环境注入的 `HTTP(S)_PROXY` | 完成 CONNECT 后**掐断 TLS 流** → `SSL: UNEXPECTED_EOF_WHILE_READING` |
| 本机代理端口（如 `127.0.0.1:7890`） | 正常取到 `%PDF` |

所以「用默认 opener 直接 urlopen」必然失败 —— 这就是下载按钮报错的原因。
`netroute.py` 不写死端口：按「`ARXIV_DL_PROXY` 显式配置 → 直连 → 环境代理 →
本机常见代理端口 → 其它在监听端口」的顺序探测，命中后写入 `output/netroute.json`
缓存（跨进程有效），缓存失效或被写坏时自动重探；全不通时 45 秒内走负缓存，
避免批量下载反复探测。PDF 地址也有兜底：元数据 → `arxiv.org/pdf/<sid>` → `export.arxiv.org/pdf/<sid>`。

排错步骤：`python netroute.py`（打印候选与命中路由）→ `GET /api/net_route`（看运行中服务的选择）。

## 归档机制

- 判定：`archive.db` 的 `seen(sid, first_date)` 记录每篇论文首次出现的期次。
  短号**从未见过**或**首次期次就是本期**都算本期（后者保证同日重复跑
  `/profile` 的「重算推荐」结果稳定，不会把本期清空）。
- 首次启用（DB 为空）不会把整个累积池当新增：退化为按提交日判定，非本期的论文
  按其自身提交日一次性记为历史（写今天会导致它们第二天又变成新增）。
- 归档：`build_report.py` 每次渲染后把当期的 html/md 复制到 `output/archive/<日期>.html|.md`
  （**只增不改**），并把当期论文写入 `issue_papers`、把本期论文写进 `seen`。
- 主题归纳（`themes.json`）属编辑性内容：引用了往期论文的主题不再出现在当期页面，
  避免旧编号与失效锚点（往期副本留 `output/archive/<日期>.themes.json`）。

## 配置与数据

- `config.json` — 类别、时间窗、推荐条数、端口、PDF 下载目录。
  下载目录当前为 `D:\git-papers\arXiv`（**带 s**，1700+ 篇既有文库，写入只增量、同名跳过，绝不覆盖或删除）。
- `interests.json` — 静态兴趣画像（主题 / 熟悉研究者 / 代表系统 / 负向词 / 学习超参）。
- `output/` — 运行产物（抓取结果、评分、日报、收藏记录、行为画像）。**不入库**。
  - `output/archive.db` — 归档库（SQLite，stdlib）；`output/archive/` — 每期日报快照。**只增不改**。
- `.workbuddy/memory/` — WorkBuddy 工作区记忆（含定时任务执行记录）。**不入库**。

## 维护要点

- 编辑性内容（中文摘要、推荐理由）外置在 `output/*.json`，**key 统一用 arXiv 短号**（如 `2609.09742`）。
- 抓取失败时 `run_daily.py` 会保留上一期 feed 而不覆盖；坏输出另存 `*.bad_<时间戳>`。
- 改动 `server.py` / `build_report.py` 后必须重启服务进程，否则跑的还是旧代码。
- 新增「只呈现本期」逻辑后，若某天日报为空，属正常（arXiv 无新公告）——页面会给出提示，
  往期内容到 `/archive` 看。补历史：`python tools/backfill_archive.py`（`--dry` 只报告）。
- 依赖：运行期仅 Python 标准库；`tools/ui_file_check.py` 与 `tools/dl_button_check.py`
  需要 websocket-client（用
  `C:\Users\hfwei\.workbuddy\binaries\python\envs\default\Scripts\python.exe` 跑），
  `tools/ui_probe.py` 等旧探针另需 Playwright。
- **下载报错先查路由**：`python netroute.py`。本机出口代理会掐断 arXiv 的 TLS 流，
  属环境问题而非代码问题；`netroute.py` 已自动绕开，若仍失败再查代理是否整体不可用。
