# 架构总览

面向"想搞清楚它怎么运转、为什么这样设计"的读者。逐模块的职责见
[模块职责](modules.md)，打分算法见[排序与学习算法](ranking.md)，
服务端并发与网络细节见[服务运行时](server-runtime.md)。

---

## 一、一句话架构

一个**无服务端依赖的本地应用**：Python 标准库做抓取/打分/渲染，产物是自包含 HTML；
本地 `http.server` 只负责交互写入（收藏、下载、反馈）与动态页面。

```
                                     ┌───────────────────────────┐
  arXiv API ──┐                      │  output/ (本地数据)        │
              ├─▶ fetch_arxiv.py ───▶│  raw.json                 │
  arXiv RSS ──┘   fetch_expand.py    │  raw_expand.json          │
                  fetch_rss.py       └───────────┬───────────────┘
                                                 │
                                    recommend.py │（打分 + 本期新增隔离）
                                                 ▼
                                     ┌───────────────────────────┐
                                     │ recommend.json            │
                                     │ expand.json               │
                                     │ papers_index.json         │
                                     └───────────┬───────────────┘
                                                 │
                    fetch_affil.py ──▶ affiliations.json
                                                 │
                                  build_report.py│（内联 CSS/JS，无构建步骤）
                                                 ▼
                     arxiv_digest_<日期>.html/.md  +  favorites.html  +  archive.html
                                                 │
                                                 ▼
                              server.py (127.0.0.1:8765) ──▶ 浏览器
                                                 ▲
                                                 │ POST /api/*（收藏/下载/Downvote）
                                          profile.py（行为学习）
```

## 二、流水线的六个阶段

`run_daily.py` 是唯一的编排者，按顺序调用下列脚本，**每个脚本都是可独立运行的进程**：

| # | 阶段 | 脚本 | 输入 | 输出 | 失败时 |
| --- | --- | --- | --- | --- | --- |
| 1 | 主分类抓取 | `fetch_arxiv.py` | `config.categories`、`window_days` | `raw.json` | 保留上一期；坏输出另存 `*.bad_<时间戳>` |
| 2 | 扩展抓取 | `fetch_expand.py` | `config.expand_categories`（留空 → `arxiv_cats.neighbors(categories)`） | `raw_expand.json` | 同上 |
| 2b | 降级通道 | `fetch_rss.py` | 分类 RSS | 增量合并进上面两个池 | 静默失败，下游继续用旧池 |
| 3 | 打分与选取 | `recommend.py` | 两个池 + `interests.json` + `profile_state.json` + `archive.db` | `recommend.json` / `expand.json` / `papers_index.json` / `issue_*.json` | 中止（无数据无法渲染） |
| 4 | 作者单位 | `fetch_affil.py` | 本期推荐 + 扩展 | `affiliations.json` | 跳过该步，页面不显示单位 |
| 5 | 渲染 | `build_report.py` | 上面全部 + `summaries.json` 等 | 当期 HTML/MD + 收藏页 + 存档页 + 归档 | 记录异常，不回滚已生成文件 |
| 6 | 确保服务 | `ensure_server()` | `config.port` | 后台进程 | 打印 URL，不阻塞 |

关键设计：**阶段间只通过文件通信**。没有内存中的长生命周期对象，因此任何一步都可以单独重跑，
也可以在浏览器里点「↻ 重算推荐」只重跑 3 与 5。

## 三、抓取失败的三层防线

arXiv API 会出现 `429`（限流）与 `503`（维护），一条数据链路必须有降级路径：

| 层 | 行为 | 判据 |
| --- | --- | --- |
| 1 | 单个分类重试 | `fetch_arxiv.py` 内部按分类重试 |
| 2 | **RSS 降级** | 只要主抓取与扩展抓取**有一路**没拿到有效数据，就触发 `fetch_rss.py` |
| 3 | **保留旧池** | 新输出无效时不覆盖已有 `raw.json`，把坏输出另存供排查 |

第 2 层的条件必须是 `not (ok1 and ok2)` 而不是 `not ok1 or not ok2` 的朴素写法——
历史故障（当时跟踪的是六个 cs 分类）：六个里只有 `cs.SE` 成功，`ok1=True` 让降级没触发，累积池从 281 篇被覆盖成 58 篇，
其余五个分类当天的论文直接丢失。**宁可多抓一次 RSS，也不能丢一天的论文。**

`raw.json` / `raw_expand.json` 是**累积池**：RSS 合并按短号做并集，**只增不删**。
这带来一个副作用：池子里混着历史批次，直接全池打分会让旧论文天天上榜——由下一节解决。

## 四、只呈现「本期新增」

`archive.py` 用 SQLite 的 `seen(sid, first_date)` 记录每篇论文**首次出现的期次**：

```
本期新增 = 池中的论文 whose seen.first_date == 本期期号（或从未见过）
```

- **首次启用**（DB 为空）不会把整个池子都当新增，而是按提交日回填基准，避免第二天全部消失；
- **同日重复跑幂等**：`seen` 里首次期次就是本期的仍算本期，页面不会被清空；
- 核心与扩展**一次过滤**，两边不会重叠；
- 每期快照另存 `output/archive/<日期>.{html,md}`（**只增不改**），`/archive` 按日期回看。

这是"日报"而不是"排行榜"的关键机制：今天的页面只回答"今天有什么新东西"。

## 五、分层与依赖方向

```
        ┌──────────────────────────────────────────────────────────────┐
 入口层 │ run_daily.py  server.py  tools/*（维护、测试、视频、投稿）      │
        └───────────────┬──────────────────────────────────────────────┘
        ┌───────────────▼──────────────────────────────────────────────┐
 接口层 │ routes.py（HTTP 语义：路由表 / Reply / Request）               │
        │ service.py（业务用例：收藏 / 下载 / 学习 / 重建）              │
        └───────────────┬──────────────────────────────────────────────┘
        ┌───────────────▼──────────────────────────────────────────────┐
 应用层 │ scoring.py（纯打分）    recommend.py（打分编排）               │
        │ customize.py（定制读写） profile.py（学习） archive.py（归档）  │
        └───────────────┬──────────────────────────────────────────────┘
        ┌───────────────▼──────────────────────────────────────────────┐
 领域层 │ textscan.py（文本→信号）  fetchsrc.py（来源取数适配）          │
        │ build_report.py + templates/（渲染）                          │
        └───────────────┬──────────────────────────────────────────────┘
        ┌───────────────▼──────────────────────────────────────────────┐
 基础层 │ paths.py（路径唯一来源） paperutil.py（配置/库/命名）          │
        │ netroute.py（下载选路）                                       │
        └──────────────────────────────────────────────────────────────┘
```

依赖只向下。三处刻意保留的「非常规」：

- `customize` ↔ `profile` 有**循环依赖**，用函数内 `import`（延迟导入）打破
  —— 代价是不能在模块顶层使用对方；
- `service` **不 import** `server`/`routes`，`routes` 也**不 import** `service`：
  两边只通过 `req.api` 的属性名耦合（白名单 `_Runtime.ALLOWED`）。这样既无循环，
  又能让「替换 `server.download_pdf` 为桩」立即生效（并发回归依赖这点）；
- `paths` 不做 IO、不缓存，只算字符串 —— 缓存会让「测试改了路径却拿到旧值」重新出现，
  而那正是它要消灭的问题。

## 六、初始化与预设

```
首次运行（文件缺失）                    按需导入（显式命令）
config.example.json  ──生成──▶ config.json   ◀──复制──  presets/<名字>/config.json
interests.example.json ─生成─▶ interests.json ◀──复制──  presets/<名字>/interests.json
```

设计意图：仓库只提交**模板**与**别人自愿公开的预设**；`config.json` / `interests.json`
属于个人数据（含本机路径与画像），被 `.gitignore` 排除。别人 clone 下来是干净的，
想参考一份真实画像时一条命令导入。细节见[预设](../guide/presets.md)。

## 七、渲染：为什么是单文件 HTML

| 选择 | 原因 |
| --- | --- |
| 内联 CSS/JS | 无构建步骤、无 CDN 依赖，`file://` 双击即可打开 |
| 服务端渲染 + 前端重排 | 首屏不需要请求接口；点击后浏览器用 `papers_index.json` 内嵌的数据本地重算分数 |
| 同一套公式前后端各实现一次 | 重排必须即时，不能等一次往返；两侧共享 `tv`/`base`/`toks`/`pen` 字段，公式见[排序](ranking.md) |
| 静态文件 + 动态页并存 | 日报是当期快照（可归档）；收藏页 / 画像页 / 存档页每次请求实时渲染 |

`API` 基址在页面里根据打开方式自动切换：`http://127.0.0.1:8765` 打开时用相对路径，
`file://` 打开时改写成绝对地址，服务端用 `Access-Control-Allow-Origin: *` 放行。

## 八、常见扩展点

| 想做什么 | 改哪里 | 注意 |
| --- | --- | --- |
| 加一个画像信号（如"讨厌的系统名"） | `interests.json` 加字段 → `recommend.features()` 参与打分 → `/profile` 加渲染 | 同步更新 [interests.md](../reference/interests.md) |
| 加一个分类 | `/profile` 的「🗂 arXiv 类别」或 `config.categories` | 需要重新抓取；分类合法性由 `arxiv_cats.validate()` 判定 |
| 改 Downvote 的视觉 | `build_report.py` 里 `.rec-card.down` 那一组 CSS | 一处改，三个模块同时生效 |
| 加一个页面 | `build_report.py` 的模板函数 + `server.py` 的 `do_GET` 路由 | 记得把路径加进 `docs` 与 `README` |
| 换推荐规则 | `recommend.features()` / `score()` | 改完 `python recommend.py && python build_report.py` 验证 |
| 换数据源（如 OpenReview） | 写一个新的 `fetch_*.py`，输出同结构的 feed | 保持 `papers[]` 字段契约 |

改完代码后的重启规则见[开发指南](../contributing/development.md)。

---

相关：[模块职责](modules.md) · [排序与学习算法](ranking.md) · [服务运行时](server-runtime.md) ·
[数据文件](../reference/data-files.md)
