# 变更记录

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
本项目尚未打版本号，因此以**日期**作为节标题；日期为提交日期（Asia/Shanghai）。

分类：`新增` / `变更` / `修复` / `文档` / `移除`。

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
- 新增 [文档中心](docs/README.md)（按"我要做什么"定位）与根 [README](README.md) 的完整索引；
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
