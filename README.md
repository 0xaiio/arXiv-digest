# arXiv cs.* 论文日报（个性化推荐 / 收藏 / 下载）

> **独立仓库**：本项目原寄生在私有仓库 `0xaiio/coworkers` 的 `git-paper/arXiv` 子目录，
> 2026-10-17 抽成独立公开仓库 **`0xaiio/arXiv-digest`**（`git filter-repo` 保留全部 17 条
> 相关提交历史）。权威工作目录：`D:/code-repo/arXiv-digest`。
> **每次提交后自动 push**（`.git/hooks/post-commit`），见文末「仓库与自动推送」。

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
| `tools/dv_unify_check.py` | **Downvote 一致性回归**：在三个模块各真点一次，断言 opacity / 删除线 / 不隐藏 / 不位移 / 可撤销三处一致 |
| `tools/concurrency_check.py` | **并发回归**：桩化下载，断言「下载中另一篇 Downvote 不被阻塞」+ 批量并行 + 单篇仍串行 |
| `tools/owner_ui_check.py` | **画像主来源回归**：在 `/profile` 真点「新增 → 编辑（含改名）→ 删除」，只用临时条目，结束即清理 |

`customize.py` 是「类别 / 下载目录 / 兴趣来源 / 画像主来源（owners）」四个可定制项的唯一读写层，
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
| `POST /api/owner` | **画像主来源**增删改（`op=add/update/remove`） |
| `/api/net_route` | **下载路由诊断**：当前选中的路由、候选数、上次失败摘要（下载报错时先看这里） |

## 交互：Downvote 语义与动作并发

### Downvote 在三个模块表现一致

「为你推荐」「兴趣扩展」「分类详解」（以及重点论文块、收藏列表）的 Downvote **只有一个实现**：
**变灰 + 标题删除线，卡片不消失、不挪位，再点一次即可撤销。**

- 视觉只有一处来源：`build_report.py` 的 CSS 中
  `.rec-card.down, .plist li.item.down, .hl.down, .fav-item.down` 共用一组规则
  （`opacity:.42` + 标题 `text-decoration:line-through`）；三类容器都靠同一个
  `setDv()` 加 `.down` 类 —— 不存在第二套样式或第二段逻辑。
- 「为你推荐 / 兴趣扩展」列表的 `data-limit`（14 / 10）只约束**未 Downvote** 的推荐条数。
  Downvote 的卡片额外保留：点击时把当时的位次记进 `data-dvpos`，重排时「钉」回原处，
  因此它既不消失也不跳到别处，误点可当场撤销。
- 改动前这两处是把卡片 `hidden` 掉（分类详解却是变灰划线），既不一致，也让按下即消失、
  无从撤销。

### 按钮动作并发执行

不同论文的下载与 Downvote 现在可以同时进行（此前一篇 PDF 下载期间，全站按钮像是失灵）：

| 层 | 机制 |
| --- | --- |
| 前端 | **乐观更新**：点下即改按钮 / 卡片状态，请求在后台跑，失败回滚；**重排合并**：`queueResort()` 在 30ms 内只执行一次，连点不再反复重排整屏 |
| 服务端 | **两级锁**：`_lib_lock` 只保护 `library.json` / `profile_state.json` 的读-改-写（毫秒级）；下载走每篇论文独立的 `_dl_locks`，网络取数**不持库锁** |
| 批量下载 | `/api/download_all` 用 `DL_WORKERS=3` 线程池并发，总耗时 ≈ 单篇而非 N 倍；同一篇连点两次仍串行，避免交叉写同名 `.part` |

根因：`/api/download` 原先整段包在一把全局锁里（含最长 90s 的网络取数），
于是任意一次下载都会把收藏 / Downvote / Abstract 的请求排在后面。

回归命令（需服务在线）：

```powershell
python tools/concurrency_check.py   # 下载中另一篇 Downvote 不被阻塞 / 批量并行 / 单篇仍串行
python tools/dv_unify_check.py      # 三处 opacity 与删除线取值相同、不隐藏、不位移、可撤销
```

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

## 画像主来源（`/profile` 可增删改）

「画像主来源」= `interests.json` 的 `owners`：画像页顶部那几张卡片，同时决定摘要页顶部
「基于 A × B × C 的兴趣画像」这行文案。此前只能手改 JSON，现在可在 `/profile` 里
**新增 / 编辑 / 删除**（`POST /api/owner`，`op=add|update|remove`）。

| 字段 | 说明 |
| --- | --- |
| `name` | 姓名，唯一键；改名用 `update` + `orig`（原姓名）定位 |
| `label` | 摘要页头部显示的简称；留空回退到 `name` |
| `site` / `affiliation` | 主页与机构，卡片展示 |
| `interests` / `signature_topics` | 研究兴趣一句话 + 代表方向（每行一条，卡片列前 4 条） |
| `people_linked` | 是否同步计入「熟悉研究者」（该作者出现在论文作者里即 +10 分/篇） |

- 校验：姓名必填、不可重名；`site` 必须 `http(s)://` 开头；**至少保留一条** owner。
- 写回时只动 `owners` / `people` 两个键，`interests.json` 其余内容与键序原样保留。
- 删除 owner 时，若它是 `people_linked` 加进 `people` 的，会把该名字一并撤掉
  （不会误删你手写的熟悉研究者）；改名同理替换。
- 改动后点工具栏 **↻ 重算推荐**（= `recommend.py` + `build_report.py`）：摘要页头部文案
  由 `_source_labels()` 在渲染期生成，作者加成也在 `recommend.py` 里重算。
- 端到端实测（2026-10-17）：用 Constantin Enea 走完「新增 → 改名/改单位 + 取消联动 →
  删除 → 再添加」全链路（HTTP 与页面真实点击双重验证），最终保留该条
  （`label = Constantin Enea`，`people_linked = true`）。

## 配置与数据

- `config.json` — 类别、时间窗、推荐条数、端口、PDF 下载目录。
  下载目录当前为 `D:\git-papers\arXiv`（**带 s**，1700+ 篇既有文库，写入只增量、同名跳过，绝不覆盖或删除）。
- `interests.json` — 静态兴趣画像（主题 / 熟悉研究者 / 代表系统 / 负向词 / 学习超参），
  以及**画像主来源** `owners`（在 `/profile` 页增删改，写入走 `POST /api/owner`）。
- `output/` — 运行产物（抓取结果、评分、日报、收藏记录、行为画像）。**不入库**。
  - `output/archive.db` — 归档库（SQLite，stdlib）；`output/archive/` — 每期日报快照。**只增不改**。
- `.workbuddy/memory/` — WorkBuddy 工作区记忆（含定时任务执行记录）。**不入库**。

## 维护要点

- 编辑性内容（中文摘要、推荐理由）外置在 `output/*.json`，**key 统一用 arXiv 短号**（如 `2609.09742`）。
- `interests.json` 入库且是画像种子（含 `owners`）：批量改之前先备份；单条改动走 `/profile`
  或 `POST /api/owner`，别手改 `people` 与 `owners` 的对应关系（联动标记在 `people_linked`）。
- 抓取失败时 `run_daily.py` 会保留上一期 feed 而不覆盖；坏输出另存 `*.bad_<时间戳>`。
- 改动 `server.py` / `build_report.py` 后必须重启服务进程，否则跑的还是旧代码。
- `server.py` 的并发约定：**任何网络 IO 都不得在 `_lib_lock` 内进行**（否则下载会串行化整个页面）；
  写 `library.json` 一律 `with _lib_lock:`，下载取数一律 `with dl_lock(sid):`。
- 新增「只呈现本期」逻辑后，若某天日报为空，属正常（arXiv 无新公告）——页面会给出提示，
  往期内容到 `/archive` 看。补历史：`python tools/backfill_archive.py`（`--dry` 只报告）。
- 依赖：运行期仅 Python 标准库；`tools/ui_file_check.py` 与 `tools/dl_button_check.py`
  需要 websocket-client（用
  `C:\Users\hfwei\.workbuddy\binaries\python\envs\default\Scripts\python.exe` 跑），
  `tools/ui_probe.py` 等旧探针另需 Playwright。
- **下载报错先查路由**：`python netroute.py`。本机出口代理会掐断 arXiv 的 TLS 流，
  属环境问题而非代码问题；`netroute.py` 已自动绕开，若仍失败再查代理是否整体不可用。

## 仓库与自动推送

| 项 | 值 |
| --- | --- |
| 远程 | `git@github.com:0xaiio/arXiv-digest.git`（**public**） |
| 分支 | `main` |
| 本地权威目录 | `D:/code-repo/arXiv-digest` |
| 历史 | 由 `git filter-repo --subdirectory-filter git-paper/arXiv` 从 `0xaiio/coworkers` 抽出，保留 17 条相关提交（作者 / 日期 / 信息原样） |

**自动推送**：`.git/hooks/post-commit` 在每次提交后异步执行 `git push origin <当前分支>`。
设计成「不阻塞、不阻断」——推送失败只打印一行提示（例如离线），提交本身不受影响，
下次提交会一并把未推的提交带上去。手动补推：`git push`。

**不放进仓库的东西**（见 `.gitignore`，这个仓库是公开的）：

| 类别 | 内容 |
| --- | --- |
| 运行产物 | `output/`（日报、评分、`archive.db`、`library.json`、抓取缓存）、`*.log`、`*.bad_*` |
| 个人数据 | 下载记录、行为画像、库文件副本（含本机绝对路径） |
| 凭据 | `.secrets/`（B 站 cookie）、`cookies.json`、`**/*cookie*.json`、token / 密钥 |
| 依赖与渲染 | `reel/node_modules/`、`reel/out/`、`reel/public/audio/` |
| 本机状态 | `.workbuddy/memory/`（会话记忆）、探针截图 `tools/ui_*.png` |

新机器上重建可运行环境：`git clone` 后只需补 `output/`（跑一次 `python run_daily.py` 自动生成）、
`reel/node_modules`（`cd reel && npm ci`）——代码、配置、画像种子（`interests.json`）、
`config.json` 都在仓库里。
