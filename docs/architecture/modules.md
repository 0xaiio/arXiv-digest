# 模块职责

13 个 Python 模块全部在项目根目录（为什么不做包化拆分，见[目录职责](../meta/structure.md)§4）。
本文是"改代码前的索引"：每个模块负责什么、对外暴露什么、依赖谁。

整体数据流见[架构总览](overview.md)。

---

## 一、总表

| 模块 | 行数量级 | 一句话职责 | 依赖 |
| --- | --- | --- | --- |
| `paperutil.py` | ~160 | 配置读写、库文件、短号与文件名、论文索引 | 仅标准库 |
| `netroute.py` | ~400 | 下载取数选路（直连/环境代理/本机代理）与失败摘要 | 仅标准库 |
| `customize.py` | ~840 | 可定制项读写：分类、下载目录、兴趣来源、画像主来源、合并视图 | `paperutil`、惰性 `profile` |
| `profile.py` | ~260 | 行为学习：把点击折算成主题倍率/关键词权重/单篇惩罚 | `paperutil`、惰性 `customize`/`recommend` |
| `archive.py` | ~320 | SQLite 归档：判「本期新增」、期次索引、快照路径 | `paperutil` |
| `fetch_arxiv.py` | ~160 | 主分类抓取 → `raw.json` | `paperutil` |
| `fetch_expand.py` | ~180 | 扩展分类抓取 → `raw_expand.json` | `paperutil` |
| `fetch_rss.py` | ~200 | 限流降级：分类 RSS 增量合并 | `paperutil` |
| `fetch_affil.py` | ~360 | 从 arXiv HTML/ar5iv 抽作者单位（跨日缓存） | `paperutil` |
| `recommend.py` | ~330 | 打分、阈值选取、本期隔离、前端索引 | `paperutil` `profile` `archive`、惰性 `customize` |
| `build_report.py` | ~1680 | 渲染日报 HTML/MD、收藏页、画像页、存档页 | `paperutil`、惰性 `customize`/`archive` |
| `server.py` | ~640 | 本地 HTTP 服务：页面 + JSON 接口 + 下载 | `paperutil` `customize` `profile` `netroute`、运行时重载 `build_report` |
| `run_daily.py` | ~195 | 编排六个阶段 + 确保服务在线 | 子进程调用其它脚本 |

## 二、依赖方向

```
run_daily.py ──(subprocess)──▶ fetch_*  recommend  build_report  server
                                             │           │
                        ┌────────────────────┘           │
                        ▼                                ▼
                   profile.py ◀──惰性──▶ customize.py ◀──┘
                        │                    │
                        └──────┬─────────────┘
                               ▼
                          paperutil.py
                               ▲
                          archive.py ──▶ recommend / build_report / server

server.py ──▶ netroute.py（下载取数）
```

规则：

- **`paperutil` 不 import 任何业务模块**，是唯一无条件可信的基础层；
- `customize` ↔ `profile` 存在**循环依赖**，用函数内 `import` 打破
  （`customize.profile_view()` 里 `import profile`，`profile.seed_weights()` 里 `import customize`）；
- `profile` ↔ `recommend` 同理（学习时需要主题正则，打分时需要画像）；
- 因此这两对模块**不能在顶层互相使用**，只能函数内调用。

## 三、基础层

### `paperutil.py`

| 能力 | 关键函数 / 常量 | 说明 |
| --- | --- | --- |
| 配置 | `load_config()` `CONFIG_PATH` `DEFAULT_CONFIG` `seed_from_example()` | 文件缺失时从 `*.example.json` 生成；缺字段回落默认 |
| 库文件 | `load_library()` `save_library()` `LIB_PATH` | 三个字典 `favorites/downloads/downvotes`，写入用临时文件 + `os.replace` |
| 标识 | `short_id()` | 兼容 `arXiv:2609.09742v2` / URL / 纯短号，统一成 `2609.09742` |
| 命名 | `build_filename()` | `arXiv<年> <短号> <去标点标题>.pdf` |
| 论文 | `paper_meta()` `load_papers()` | `load_papers()` 合并两个池，返回 `{短号: paper}` |
| 时间 | `now_str()` | 统一 `YYYY-MM-DD HH:MM:SS` |

### `netroute.py`

| 能力 | 关键函数 | 说明 |
| --- | --- | --- |
| 候选枚举 | `candidates()` | `ARXIV_DL_PROXY` → 直连 → 环境代理 → 本机常见端口 → 其它监听端口 |
| 探测 | `ensure_route()` | 命中后写 `output/netroute.json` 缓存（TTL 900s，全失败走 45s 负缓存） |
| 取数 | `build_opener()` `make_request()` | 统一 opener，绕过被注入的坏代理 |
| 诊断 | `friendly()` `last_failure()` `forget()` | 面向人的错误摘要，供 `/api/download` 与 `/api/net_route` 使用 |

## 四、业务层

### `customize.py`（可定制项的唯一读写层）

| 分组 | 函数 |
| --- | --- |
| 分类 | `categories()` `category_names()` `category_label()` `add_category()` `remove_category()` |
| 下载目录 | `download_dir()` `set_download_dir()` |
| 兴趣来源 | `add_source()` `remove_source()` `refresh_all()` `block_keyword()` `derive()` `rebuild()` |
| 画像主来源 | `owners()` `add_owner()` `update_owner()` `remove_owner()` `owners_view()` |
| 合并视图 | `effective_topics()` `effective_people()` `effective_systems()` `effective_seed_weights()` |
| 页面数据 | `snapshot()` `profile_view()` `view()` |

写文件的三条铁律（`add_owner` 系列）：只改目标键、保留其余内容与键序、写前校验
（姓名非空/不重名、`site` 必须 `http(s)`、至少保留一条 owner）。

`effective_*` 是**唯一**把"手写画像 + 来源增量 + 自定义主题"合并的地方。任何模块要主题列表
都必须调它，否则前端重排会拿错权重下标。

### `profile.py`（行为学习）

| 能力 | 函数 | 说明 |
| --- | --- | --- |
| 状态 | `load()` `save()` `PROFILE_PATH` | `topic_mult` / `kw` / `paper_bonus` / `counts` |
| 权重 | `seed_weights()` `weights()` `topic_names()` | 顺序与 `effective_topics()` **严格同序** |
| 特征 | `tokens()` `STOP` | 去停用词后取前 45 个实词 |
| 更新 | `apply_event()` | 唯一入口：接受 `sid` + `action`，返回 `(state, delta_info)` |
| 流水 | `load_behavior()` `save_behavior()` | 最近 2000 条，供审计 |

`apply_event()` 的负向分支（`downvote` / `undownvote`）默认**只写单篇惩罚**，跳过全局学习；
判定逻辑集中在 `learn_neg_topics` / `learn_neg_keywords` 两个开关，见 [ranking.md](ranking.md) §5。

### `archive.py`（归档）

| 能力 | 函数 | 说明 |
| --- | --- | --- |
| 建库 | `init()` `connect()` | `output/archive.db`，三张表 |
| 增量判定 | `known_sids()` `filter_new()` `filter_issues()` `mark_seen()` | `filter_issues()` 同时处理核心池与扩展池，并返回 `mode` |
| 期次 | `record_issue()` `list_issues()` `get_issue()` `latest_issue()` | `issues` / `issue_papers` 写入与查询 |
| 快照 | `archive_digest()` `snapshot_path()` `available_dates()` `stats()` | `output/archive/<日期>.{html,md}` |

### `recommend.py`（打分）

| 能力 | 函数 | 说明 |
| --- | --- | --- |
| 画像载入 | `load_profile()` | 返回 `(prof, topics, neg_weight, neg_rx)`，全部带默认值 |
| 特征 | `features()` | 拆出 `base`（静态）与 `tv`（随权重变化） |
| 打分 | `score()` | `base + Σ(raw×weight) + Σ(kw) + pen` |
| 主流程 | `main()` | 本期隔离 → 打分 → 阈值选取（含兜底）→ 写六个产物 |

## 五、入口层

### `build_report.py`（渲染）

| 函数 | 产出 |
| --- | --- |
| `build_card()` `build_pool_cards()` `build_sections()` | 单卡片 / 池列表 / 三个板块 |
| `build_html()` `build_md()` | `arxiv_digest_<日期>.html` / `.md` |
| `build_favorites()` | `favorites.html` |
| `build_profile_page()` | `/profile` 页面 |
| `build_archive_page()` | `archive.html`（`/archive`） |
| `main()` | 串起上面全部 + 归档 |

模板与 CSS/JS 都是模块内的字符串常量（`PAGE`、`PROFILE_PAGE` 等），用 `%` 格式化。
**改模板时的坑**：内联 JS 里的 `\n` 会被 Python 先解析成真换行，导致整段脚本语法错误——
在模板里要写 `\\n`。

### `server.py`（本地服务）

| 区域 | 内容 |
| --- | --- |
| 路由 | `do_GET`（页面 + 只读接口）、`do_POST`（写接口）、`do_OPTIONS`（CORS 预检） |
| 下载 | `download_pdf()`（单篇，走 `netroute`）、`_download_one()`（批量项）、`DL_WORKERS=3` |
| 并发 | `_lib_lock`、`dl_lock(sid)`、`_papers_lock`、`_rebuild_lock` |
| 缓存 | `papers(force=False)`：60 秒 TTL 的论文索引 |
| 动态渲染 | `/favorites` `/profile` `/archive` 每次都 `importlib.reload(build_report)` |

接口清单见 [HTTP API](../reference/http-api.md)。

### `run_daily.py`（编排）

`run(script, capture, keep_previous)` 是唯一的子进程封装：捕获 stdout → 校验 payload →
写文件或保留旧文件。`ensure_server()` 用 `cmd /c start /d <dir> /b` 脱离进程树启动服务
（`/b` 不继承 cwd，必须显式 `/d`，否则服务会读写错误的 `output/`）。

## 六、按"我要改什么"定位

| 任务 | 该看哪个模块 | 风险提示 |
| --- | --- | --- |
| 打分不准 | `recommend.py` 的 `features()` / `score()` | 改公式必须同步前端 `rescore()`，否则首屏与点击后排序不一致 |
| 推荐数突然为 0 | `profile.py` 的 `apply_event()` + `output/profile_state.json` | 先看 [ranking.md](ranking.md) §5 的排查协议 |
| 页面样式/交互 | `build_report.py` 的 CSS 常量与内联 JS | 三个模块共用一组 `.down` 规则，别各写一份 |
| 新增接口 | `server.py` 的 `do_GET`/`do_POST` + 前端 `api()` | 记得在 [http-api.md](../reference/http-api.md) 登记 |
| 抓取解析 | `fetch_arxiv.py` 的字段映射 | 保持 `papers[]` 字段契约，否则 `recommend` 会缺字段 |
| 下载失败 | `netroute.py` | 先 `python netroute.py` 再改代码 |
| 归档漏判/重复 | `archive.py` 的 `filter_issues()` | 不要手工删 `seen` 行 |

---

相关：[架构总览](overview.md) · [服务运行时](server-runtime.md) ·
[开发指南](../contributing/development.md) · [目录职责](../meta/structure.md)
