# 模块职责

18 个 Python 模块全部在项目根目录（为什么不做包化拆分，见[目录职责](../meta/structure.md)§4）。
本文是「改代码前的索引」：每个模块负责什么、对外暴露什么、依赖谁。
渲染层的版面在 `templates/`，不在 `.py` 里。

整体数据流见[架构总览](overview.md)，评分公式见[排序与学习](ranking.md)。

---

## 一、总表

| 层 | 模块 | 行数 | 一句话职责 | 依赖 |
| --- | --- | --- | --- | --- |
| 基础 | `paths.py` | ~150 | **路径的唯一权威定义** + `python paths.py` 诊断 | 仅标准库 |
| 基础 | `paperutil.py` | ~170 | 配置读写、库文件、短号与文件名、论文索引 | `paths` |
| 基础 | `netroute.py` | ~400 | 下载取数选路（直连/环境代理/本机代理）与失败摘要 | `paths` |
| 领域 | `textscan.py` | ~175 | 纯文本信号：去标签、人名、专业实词、主题命中 | `profile` |
| 领域 | `fetchsrc.py` | ~170 | 来源取数适配：arXiv / 网页 / 本地文档 → `(meta, err)` | `paperutil`、`textscan` |
| 领域 | `profile.py` | ~260 | 行为学习：把点击折算成主题倍率/关键词权重/单篇惩罚 | `paperutil`、`paths` |
| 领域 | `archive.py` | ~320 | SQLite 归档：判「本期新增」、期次索引、快照路径 | `paperutil`、`paths` |
| 应用 | `customize.py` | ~620 | 可定制项读写：分类、下载目录、兴趣来源、画像主来源、合并视图 | `paperutil` `paths` `textscan` `fetchsrc` |
| 应用 | `scoring.py` | ~100 | **纯打分函数**：特征拆解与合成分（无 IO、无全局状态） | `profile` |
| 应用 | `recommend.py` | ~250 | 打分编排、阈值选取、本期隔离、前端索引 | `scoring` `paperutil` `profile` `archive` |
| 应用 | `fetch_arxiv.py` | ~160 | 主分类抓取 → `raw.json` | `paperutil` |
| 应用 | `fetch_expand.py` | ~180 | 扩展分类抓取 → `raw_expand.json` | `paperutil` |
| 应用 | `fetch_rss.py` | ~200 | 限流降级：分类 RSS 增量合并 | `paperutil` |
| 应用 | `fetch_affil.py` | ~360 | 从 arXiv HTML/ar5iv 抽作者单位（跨日缓存） | `paperutil` `paths` |
| 渲染 | `build_report.py` | ~800 | 渲染日报/收藏/画像/存档页；**版面在 `templates/`** | `paperutil` `paths`、惰性 `customize`/`archive` |
| 接口 | `service.py` | ~300 | 业务用例：收藏/下载/画像学习/重建（**不认识 HTTP**） | `paperutil` `profile` `netroute` `paths` |
| 接口 | `routes.py` | ~440 | HTTP 语义：路由表 + `Reply`/`Request`（业务委托给 `api`） | 仅标准库 |
| 接口 | `server.py` | ~250 | 进程装配：Handler 分发、写 socket、启动服务 | 以上全部 |
| 编排 | `run_daily.py` | ~195 | 六个阶段 + 确保服务在线 | 子进程调用其它脚本 |

## 二、依赖方向

```
                    run_daily.py ──(subprocess)──▶ fetch_* / recommend / build_report / server
                                                              │
  ┌───────────────────────────────────────────────────────────┴────────────────┐
  │                                                                           │
  ▼                                                                           ▼
server.py ──▶ routes.py ──▶ (api 命名空间) ──▶ service.py ──▶ netroute.py    build_report.py
  │                       │                        │              ▲                │
  │                       └──▶ customize.py ───────┘              │                │
  │                                 │  │                          │                │
  │                    ┌────────────┘  └──────────┐               │                │
  │                    ▼                          ▼               │                │
  │              textscan.py                fetchsrc.py           │                │
  │                    │                          │               │                │
  │                    ▼                          ▼               │                │
  │              profile.py ◀──惰性──▶ customize  │               │                │
  │                    │                          │               │                │
  │                    ▼                          ▼               │                │
  │              scoring.py                    paperutil.py ◀──────┘────────────────┘
  │                    ▲                          ▲
  │              recommend.py ──▶ archive.py ────┘
  │
  └──▶ paths.py（所有模块的路径来源，最底层）
```

规则：

- **`paths` 不 import 任何业务模块**；它只做字符串计算，不做 IO（见下文「为什么单独一层」）。
- **`paperutil` 不 import 业务模块**；例外仅 `paths`。
- `customize` ↔ `profile` 存在**循环依赖**，用函数内 `import` 打破
  （`customize.profile_view()` 里 `import profile`，`profile.seed_weights()` 里 `import customize`）。
- `profile` ↔ `recommend` 同理（学习时需要主题正则，打分时需要画像）。
- **`service` 不 import `server` / `routes`**，`routes` 不 import `service` ——
  两边只通过 `req.api` 的**属性名**耦合（白名单见 `server._Runtime.ALLOWED`）。
  这样既没有循环依赖，又能让外部替换 `server.download_pdf` 立即生效。

## 三、基础层

### `paths.py`（路径唯一来源）

| 能力 | 关键函数 / 常量 | 说明 |
| --- | --- | --- |
| 根目录 | `ROOT` `under_root(*parts)` | 所有路径相对它解析 |
| 目录 | `output_dir()` `archive_dir()` | 运行产物统一在 `output/`（一条 `.gitignore` 兜住） |
| 个人配置 | `config_path()` `interests_path()` + `*_example()` | 放仓库根，用户直接编辑；缺文件时按 `*.example.json` 生成 |
| 运行产物 | `library_path()` `profile_state_path()` `archive_db_path()` `netroute_cache_path()` `affiliations_path()` `interests_extra_path()` | 均在 `output/` 下 |
| 诊断 | `snapshot()` `main()` | `python paths.py` 列出全部路径并标出是否已生成 |

**为什么单独一层**：这些路径原先散落在 10 个模块里各自 `os.path.join(HERE, ...)`。
不是「不好看」，而是真出过事故——新增模块时忘了跟随重定向约定，测试把真实
`raw.json` 与 `affiliations.json` 覆盖了（见[测试与回归](../contributing/testing.md)§四）。
现在新增数据文件只需在这里加一行。

各模块仍保留同名常量（`OUT`、`CONFIG_PATH`…）**但从这里取值**，
所以「按模块属性 monkeypatch 重定向」的测试约定照旧可用。

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
| 取数 | `build_opener()` `make_request()` `fetch_first()` | 统一 opener，绕过被注入的坏代理 |
| 诊断 | `friendly()` `last_failure()` `forget()` | 面向人的错误摘要，供 `/api/download` 与 `/api/net_route` 使用 |

## 四、领域层

### `textscan.py`（纯文本 → 结构化信号）

| 能力 | 函数 | 说明 |
| --- | --- | --- |
| 去标签 | `strip_html()` | 丢 `script/style`，块级标签换行；坏 HTML 也返回已读内容 |
| 人名 | `extract_people()` | 只收「重复出现的 First Last」，排除 `The Paper` 这类噪音配对 |
| 实词 | `extract_keywords()` | 分层：连字符术语 > 标题长词 > 标题词 > 正文重复 |
| 主题 | `matched_topics()` | 该来源强化了哪些现有主题 |

**只做字符串变换**：不读文件、不联网、不碰配置文件。所以「哪个词该进画像」这类
调参问题可以用字符串字面量直接测。

### `fetchsrc.py`（来源取数适配）

| 能力 | 函数 | 说明 |
| --- | --- | --- |
| arXiv | `parse_paper()` | `id_list` 查询，标题折行归一，收集作者 |
| 网页 | `parse_link()` | 标题取 `<title>`，正文去标签，超长截断 |
| 本地 | `parse_doc()` | 文本类直接读，`.html` 去标签，`.pdf` 走 pypdf |
| 分派 | `parse()` `PARSERS` | 新增来源类型 = 在表里加一行 |

三种来源返回**同一结构** `(meta, err)`，上层不必关心类型差异。
网络取数通过 `_get` 参数注入，单测既不联网也不依赖调用方的模块状态。

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

## 五、应用层

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

`effective_*` 是**唯一**把「手写画像 + 来源增量 + 自定义主题」合并的地方。任何模块要主题列表
都必须调它，否则前端重排会拿错权重下标。

`strip_html` / `extract_*` / `parse_*` 在这里是 **re-export + 注入型包装**
（`parse_link` 把自己的 `_http_get` 传下去），所以
`monkeypatch.setattr(customize, "_http_get", ...)` 这类历史用法继续有效。

### `scoring.py`（纯打分）

| 能力 | 函数 | 说明 |
| --- | --- | --- |
| 关键词正则 | `_rx()` `_norm()` | 空格/连字符/下划线等价；空词永不匹配 |
| 主题命中 | `topic_hits()` | 返回 `(tv, detail)`：紧凑下标 + 可解释明细 |
| 静态分 | `base_score()` | 熟悉作者 / 代表系统 / 负向词（有封顶） |
| 特征 | `features()` | 把上面拼成 `{tv, base, toks, detail, fam, sys, neg_hits}` |
| 合成 | `score()` | `base + pen + Σ(raw×weight) + Σ(关键词权重)` |

公式里的魔数已提取为命名常量（`TITLE_HIT_W` 等），文档与代码可逐项对照。
无 IO、无全局状态，因此单测覆盖到 100%。

### `recommend.py`（打分编排）

| 能力 | 函数 | 说明 |
| --- | --- | --- |
| 画像载入 | `load_profile()` | 返回 `(prof, topics, neg_weight, neg_rx)`，全部带默认值 |
| 打分 | `features()` `score()` | **re-export 自 `scoring`**，保持旧调用点可用 |
| 主流程 | `main()` | 本期隔离 → 打分 → 阈值选取（含兜底）→ 写六个产物 |

### `fetch_*.py`

`fetch_arxiv` / `fetch_expand` / `fetch_rss` / `fetch_affil` 各自独立可跑，
共用 `paperutil` 的池合并与配置。抓取池是**累积**语义（只并集、不删除），
`fetch_rss` 是 429/503 时的降级通道。

## 六、渲染层

### `build_report.py`

| 函数 | 产出 |
| --- | --- |
| `read_template()` | 按 mtime 缓存读 `templates/<name>`（改版面不用重启） |
| `build_card()` `build_pool_cards()` `build_sections()` | 单卡片 / 池列表 / 三个板块 |
| `build_html()` `build_md()` | `arxiv_digest_<日期>.html` / `.md` |
| `build_favorites()` | `favorites.html` |
| `build_profile_page()` | `/profile` 页面 |
| `build_archive_page()` | `archive.html`（`/archive`） |
| `main()` | 串起上面全部 + 归档 |

**版面在 `templates/`**：`style.css`、`app.js`、`page.html`、`favorites.html`、
`profile.html`、`archive.html`。它们原先是模块内 1400 行的三引号字符串，
`%` 格式化会吃掉内联 JS 里的反斜杠（历史事故：`join('\n')` 被解析成真换行，
整段脚本语法错误，页面正常但所有按钮失效）。现在模板是独立文件，可单独 lint、单独 diff。

端口占位符 `__APIPORT__` 在**渲染时**替换（`render_js()`），所以改 `config.port`
后重新生成页面即生效，不必重启服务。

## 七、接口层

### `service.py`（业务用例，不认识 HTTP）

| 分组 | 函数 / 类 | 说明 |
| --- | --- | --- |
| 并发 | `LIB_LOCK` `dl_lock(sid)` `DL_WORKERS` | 库锁只护内存读改写；每篇下载一把锁 |
| 索引 | `PaperIndex` `papers()` `reset_papers()` | 60 秒 TTL + 双重检查，`reset()` 供重建后调用 |
| 下载 | `download_pdf()` `download_one()` `download_many()` | 取数不持库锁；批量 3 路并发、结果保序 |
| 库操作 | `add_favorite()` `record_download()` | **不自己取元数据**，由调用方传入 |
| 画像 | `profile_snapshot()` `learn()` | 学习失败只写 stderr，不打挂请求 |
| 重建 | `rebuild_digest()` | 依次跑 `recommend.py` / `build_report.py`，带超时与错误摘要 |
| 杂项 | `latest_digest()` `ensure_dir()` `quiet_remove()` `open_path()` | 纯工具，收参数不读全局 |

**为什么要这一层**：这些逻辑原先内联在 `do_POST` 的 if 链里，与 `self._json()` 缠在一起
——想验证「下载一篇时另一篇的 Downvote 不被阻塞」必须起真 HTTP 服务，于是并发回归
只能写成独立脚本（`tools/concurrency_check.py`），进不了 pytest。

`download_one` / `download_many` 的 `download_fn` / `learn_fn` 是**注入点**：
路由层传 `api.download_pdf` / `api.learn`，所以外部替换（桩化）对批量下载同样生效。

### `routes.py`（HTTP 语义）

| 能力 | 说明 |
| --- | --- |
| 注册 | `@get` `@get_prefix` `@post` 三个装饰器 |
| 匹配 | `resolve_get()` 精确优先、前缀次之（`/archive` 不会被 `/archive/` 抢走） |
| 数据 | `Request`（`path/query/body/api` + `sid()/arg()/q()/op()`） |
| 响应 | `Reply.json/text/html/file()`；`file` 只带路径，由 Handler 读盘 |
| 清单 | `table()` 返回全部路由，供文档生成与「路由完整性」测试 |

新增接口 = 加一个装饰器函数，**不改 Handler、不改已有路由**。
业务动作全部委托给 `req.api`，因此处理器可以脱离网络单测。

### `server.py`（进程装配）

| 区域 | 内容 |
| --- | --- |
| 分发 | `Handler.do_GET/do_POST`：解析 → `routes.resolve_*` → `_reply()` |
| 运行时 | `_Runtime`：路由层能看到的**白名单**能力，每次访问回查本模块（桩化生效） |
| 兼容门面 | `download_pdf` `papers` `learn` `add_favorite` `LIB_LOCK` … 全部 re-export |
| 缓存 | `digest_module(reload=True)`：惰性加载 `build_report`，reload 收敛到一处并加锁 |
| 启动 | `main()`：读 `config.port`，绑定 `127.0.0.1`，`--no-open` 时不弹浏览器 |

接口清单见 [HTTP API](../reference/http-api.md)。

## 八、编排层

### `run_daily.py`

`run(script, capture, keep_previous)` 是唯一的子进程封装：捕获 stdout → 校验 payload →
写文件或保留旧文件。`ensure_server()` 用 `cmd /c start /d <dir> /b` 脱离进程树启动服务
（`/b` 不继承 cwd，必须显式 `/d`，否则服务会读写错误的 `output/`）。

## 九、按"我要改什么"定位

| 任务 | 该看哪个模块 | 风险提示 |
| --- | --- | --- |
| 打分不准 | `scoring.py` 的 `topic_hits()` / `score()` | 改公式必须同步前端 `rescore()`，否则首屏与点击后排序不一致 |
| 推荐数突然为 0 | `profile.py` 的 `apply_event()` + `output/profile_state.json` | 先看 [ranking.md](ranking.md) §5 的排查协议 |
| 页面样式/交互 | `templates/style.css`、`templates/app.js` | 三个模块共用一组 `.down` 规则，别各写一份；改完不用重启 |
| 页面结构/文案 | `templates/*.html` + `build_report.build_html()` 的占位符字典 | 占位符名字两边必须对齐，缺键会 `KeyError` |
| 新增接口 | `routes.py`（装饰器 + handler）+ 前端 `api()` | 记得在 [http-api.md](../reference/http-api.md) 登记 |
| 新增业务动作 | `service.py` + `routes.py` 里一行调用 | 不要在 routes 里写业务规则 |
| 新增数据文件 | `paths.py` 一行 + `conftest._OUT_OWNERS`（如果是模块级常量） | 漏登记会让测试写坏真实数据 |
| 抓取解析 | `fetch_arxiv.py` 的字段映射 | 保持 `papers[]` 字段契约，否则 `recommend` 会缺字段 |
| 兴趣来源解析 | `fetchsrc.py`（取数）+ `textscan.py`（抽词） | 两者都可脱离网络/文件单测 |
| 下载失败 | `netroute.py` | 先 `python netroute.py` 再改代码 |
| 归档漏判/重复 | `archive.py` 的 `filter_issues()` | 不要手工删 `seen` 行 |

---

相关：[架构总览](overview.md) · [服务运行时](server-runtime.md) ·
[开发指南](../contributing/development.md) · [目录职责](../meta/structure.md)
