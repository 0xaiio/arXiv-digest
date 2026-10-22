# 私人数据隔离与数据包

> 一句话：**代码、模板、某人的私人数据三者分离**。新用户 clone 下来看到的永远是空界面；
> 任何人的配置与使用数据都以纯 JSON 文本收在一个目录里，只能**显式导入**，不会被自动读取。

本文回答四个问题：现状为什么不够、数据怎么分层、包长什么样、导入导出与启动参数的行为契约。

---

## 一、现状审计：隔离是"命名约定"，不是"结构保证"

`main` 分支（本文写作时的 `arXiv-category`）里，个人数据已经不进版本库：

| 位置 | 是否入库 | 内容 |
| --- | --- | --- |
| `config.example.json` / `interests.example.json` | ✅ | 模板 |
| `presets/hengxin/` | ✅ | 作者自愿公开的一份示例画像（`config.json` + `interests.json`） |
| `config.json` / `interests.json` | ❌ `.gitignore` | 类别、下载目录、画像 |
| `output/library.json` 等 | ❌ `output/` 整体忽略 | 收藏、下载记录、Downvote、行为学习、编辑性笔记 |
| `.secrets/` | ❌ | 凭据 |

也就是说，"新用户看不到作者的数据"目前**只由 `.gitignore` 的命名约定保证**。逐条看它的缺口：

1. **使用数据不在任何"可迁移单元"里。** `tools/preset.py export` 只复制 `config.json` 与
   `interests.json`。换一台机器，收藏（可能上千篇）、下载记录、Downvote、行为学习全部留在原地，
   与新写的 `export` 名字（"导出一套设置"）不符。
2. **没有结构边界，只有目录约定。** 数据与代码同处一个目录树，是否泄漏取决于"有没有人
   `git add -f`""会不会把整个文件夹打包发人"。一旦发生，事后无法从代码层面拦住。
3. **首启动不是"空界面"。** `interests.example.json` 自带一个"示例主题（请替换成你的研究方向）"
   与 5 个关键词；它会被复制成 `interests.json`、参与打分、并出现在 `/profile` 的主题列表里。
   它不是作者的数据，但也不是用户的数据——是一段"假数据"。
4. **导入不在启动路径上。** 想用一份现成设置，必须手工三步：跑 `tools/preset.py import`、
   再跑 `run_daily.py`、再重启 `server.py`。没有 `--preset`，也没有界面入口。

结论：需要把"私人数据"从一个**位置约定**升级为一个**有契约、有清单、有测试**的显式对象。

---

## 二、目标与非目标

### 目标

| # | 目标 | 可验收的形式 |
| --- | --- | --- |
| G1 | 首次 clone 启动后，界面只呈现空状态与功能入口 | `/` 是欢迎页；`/profile` 无主题、无主来源、无类别；`/favorites` 是空态；页面 HTML 不含任何私人字符串 |
| G2 | 私人数据以纯文本 JSON 管理，多文件时收在一个目录 | 每个包 = `presets/<名字>/` 下的一组 `.json` + `manifest.json` |
| G3 | 私人数据可作为**启动参数**一键导入 | `python run_daily.py --preset <名字>`、`python server.py --preset <名字>`、`start_digest.bat <名字>` |
| G4 | 也可在**启动后**从界面一键导入 | `/profile` →「📦 数据包」→ 导入按钮 → `POST /api/preset` |
| G5 | 导入**永不静默摧毁**本机数据 | 收藏/下载/Downvote 只并集；覆盖类操作先备份且需显式授权 |
| G6 | 界面不暴露包**内容** | 面板只渲染包名、文件清单、体积；不渲染标题、描述、分类、主题、人名 |
| G7 | 隔离可被测试断言 | `tests/unit/test_datapack.py` + e2e `test_fresh_install_has_no_personal_traces` 扩展 |

### 非目标

- **不**把运行态搬到 `~/.arxiv-digest/`（见 §八 备选方案）。
- **不**做云同步、多用户账号、权限系统：单机单用户，localhost 服务。
- **不**保证包跨大版本兼容（用 `schema` 版本号显式拒绝，而不是猜）。
- **不**把包做成二进制（zip/sqlite）：`git diff` 必须能看懂一份画像改了什么。

---

## 三、数据分层：模板 / 数据包 / 运行态

```
┌─ 模板（入库，机器无关） ─────────────────────────────┐
│ config.example.json   interests.example.json         │
│ 角色：首次运行时复制成运行态文件的**空骨架**           │
└──────────────────────────────────────────────────────┘
┌─ 数据包（文本，入库或本地均可） ────────────────────┐
│ presets/<名字>/manifest.json + *.json + README.md     │
│ 角色：某个人一整套设置与使用数据的**可迁移单元**       │
│ 生命周期：只在 import 时被读取；运行期完全不参与       │
└──────────────────────────────────────────────────────┘
┌─ 运行态（不入库，本机专属） ───────────────────────┐
│ config.json  interests.json  output/library.json …   │
│ 角色：**当前使用者**的数据，随使用逐步积累             │
└──────────────────────────────────────────────────────┘
```

三条硬规则：

1. **运行态永不读 `presets/`。** 唯一例外是 `/api/datapacks` 与 `/profile` 的导入面板，
   它们只读目录结构与文件大小（`os.stat`），**不解析包内的 JSON 内容**。
2. **模板永不包含真人数据。** 模板里的 `categories`、`owners`、`topics`、`people` 一律为空数组。
3. **包永不自动生效。** 没有"启动时自动发现并加载"的路径；必须点名（`--preset <名字>`）或点击。

### 数据分类与隐私等级

| 分组 | 文件 | 内容 | 隐私 | 跨机器语义 |
| --- | --- | --- | --- | --- |
| `core` | `config.json`、`interests.json` | 类别选择、下载目录、推荐参数、画像 | 中（画像即研究方向） | 强（可直接用） |
| `usage` | `library.json` | 收藏 / 下载记录 / Downvote | 高（阅读史 + 本机绝对路径） | 弱（路径失效，清单有价值） |
| `learning` | `profile_state.json`、`behavior.json` | 行为学习聚合与流水 | 高（逐条点击行为） | 弱（是本机训练的产物） |
| `notes` | `summaries.json`、`abstracts_zh.json`、`rec_notes.json`、`highlights.json` | 双语简介、摘要的中文译文、推荐理由、看点 | 中（编辑性内容） | 中（按 arXiv 短号，可直接用） |

分组不只是为了"选择性导出"，更是**导入语义的分界线**：`usage` / `notes` 是并集合并，
`core` 是整文件替换，`learning` 是唯一"覆盖本机学习结果"的动作，因此默认不导入。

---

## 四、格式选型：为什么是"JSON 文本 + 一个目录 + 一份清单"

### 4.1 为什么不用单个大 JSON

单文件看起来最简单，但有四个具体问题：

1. **生命周期不同。** `config.json` 改一次类别、`library.json` 每次点击都变。合在一起后，
   任何一次收藏都会重写整包，`git diff` 里画像与收藏混在一起。
2. **隐私等级不同。** 画像可以公开（作者已经公开了），阅读史不该。同文件就无法分级忽略。
3. **写入放大与损坏面。** 一次写入要序列化全部数据（含上千条收藏）；写坏 = 全丢。
   分开后 `library.json` 坏了不影响画像。
4. **与既有代码结构冲突。** `paperutil.load_library()`、`PF.load()`、`CZ.load_interests()`
   各自读一个文件，合包意味着改造全部读写路径，收益为零、风险很高。

### 4.2 为什么不用 zip / sqlite

- zip/bin：`git diff` 不可读，评审看不见"这份画像改了什么"；对文本工具（grep、diff、编辑器）不友好。
- sqlite：`library.json` 已经是 JSON 且带并发写保护；引入数据库只为打包没有收益，还会带来
  schema 迁移负担。

### 4.3 为什么是"一个目录 + `manifest.json`"

- **目录 = 分发单位。** 复制/删除/压缩/上传都是一个目录操作，不会漏文件。
- **`manifest.json` = 契约与完整性。** 记录 `schema`、导出时间、分组、每个文件的字节数与
  `sha256`。导入时据此做两件事：拒绝未来版本（`schema > 1`）、发现被手改坏的文件。
- **`README.md` = 人读的说明。** 界面刻意不渲染包内容，README 是"想了解这个包"的唯一入口。

### 4.4 包内目录结构

```
presets/
└─ hengxin/
   ├─ manifest.json        # 必需（导出时自动生成；缺它仍可导入，但只做最宽松的校验）
   ├─ config.json          # core
   ├─ interests.json       # core
   ├─ library.json         # usage（可选；.gitignore 已排除，不会误提交）
   ├─ profile_state.json   # learning（可选，同上）
   ├─ behavior.json        # learning（可选，同上）
   ├─ summaries.json       # notes（可选，同上）：双语简介
   ├─ abstracts_zh.json    # notes（可选，同上）：摘要的中文译文
   ├─ README.md            # 人读说明
   └─ legacy/              # 该包配套的一次性脚本（可选，不参与导入）
```

`.gitignore` 对包内的高敏文件做了**文件级**排除，因此"同一个目录里既有可公开的画像、
又有不该公开的阅读史"是被结构允许的，而不是靠人记得别提交。

`manifest.json` 示例：

```json
{
  "schema": 1,
  "name": "hengxin",
  "title": "一份数据库 / 分布式 / 形式化方向的完整画像",
  "description": "由作者导出，供方向相近的人直接起步；导入前请先改下载目录。",
  "exported_at": "2026-10-20 14:02:11",
  "app": "arxiv-digest",
  "groups": ["core"],
  "sanitized": true,
  "files": [
    {"name": "config.json", "group": "core", "bytes": 812,
     "sha256": "9f2c…"}
  ]
}
```

> `title` / `description` 只给命令行 `list` / `show` 看，**不进入网页**（见 §六）。

---

## 五、模块与接口

新增一个根模块 `datapack.py`（业务逻辑），`tools/preset.py` 退化为命令行外壳。
之所以不叫 `preset.py`：仓库里已有 `tools/preset.py`，同名会让人分不清哪个是库、哪个是命令。

### 5.1 `paths.py`

```python
def packs_dir():          # 数据包根目录
    return under_root("presets")
PACKS = packs_dir()
```

与其它路径一样，只回答"在哪"，不做 IO；纳入 `snapshot()` 与 `python paths.py` 的输出。
`datapack.PACKS` 是它的模块级副本，测试通过 monkeypatch 重定向（见 `tests/conftest.py`）。

### 5.2 `datapack.py` 对外契约

| 函数 | 签名 | 职责 |
| --- | --- | --- |
| `valid_name(name)` | `str -> bool` | 包名合法性：非空、不以 `.` 开头、不含 `/`、`\`、`..` |
| `pack_path(name)` | `str -> str` | 包目录绝对路径；非法名抛 `ValueError` |
| `list_packs()` | `-> [dict]` | 扫描目录，返回 `{name, path, files, groups, bytes, title, description, exported_at, schema, has_manifest}` |
| `manifest(name)` | `-> dict` | 读 `manifest.json`，缺失时回落 `meta.json`（旧版兼容） |
| `targets()` | `-> {文件名: 本机路径}` | **在调用时**从 `paperutil` / `customize` / `profile` 的模块常量解析，保证测试重定向生效 |
| `state()` | `-> dict` | 本机个人数据清单：`{file: {exists, bytes, group, updated_at}}`，**不含绝对路径** |
| `import_pack(name, groups=None, force=False, dry_run=False)` | `-> (ok, msg, report)` | 导入 |
| `export_pack(name, groups=None, sanitize=True)` | `-> (ok, msg, report)` | 导出 |
| `scan_paths(obj)` | `-> [str]` | 在 JSON 对象里找形似绝对路径的字符串（导出前的自检） |

`report` 是逐文件的结果列表，`action ∈ {written, replaced, merged, skipped, refused}`，
外加 `reason` 与 `added` 计数。CLI 打印它，HTTP 原样返回，界面据 `ok` 决定 toast。

### 5.3 导入语义（核心）

默认导入分组 `core + usage + notes`。`learning` 需显式 `--with-learning`。

| 分组 | 本机文件不存在 | 本机是模板初值 | 本机已存在且内容相同 | 本机已存在且用户改过 |
| --- | --- | --- | --- | --- |
| `core` | 写入 | 直接替换（无需 `--force`） | `skipped`（幂等） | 无 `--force` → `refused`；有 → 备份后 `replaced` |
| `usage` | 写入 | — | 并集（全等，`skipped`） | **并集合并**，同名条目保留本机的（本机路径才有效） |
| `notes` | 写入 | — | 并集（全等，`skipped`） | 并集合并，同名条目保留本机的 |
| `learning` | 写入 | — | 覆盖 | 备份后覆盖（显式请求即授权） |

四条设计理由：

- **`core` 必须拒绝而不是合并。** 画像没有"合并"的语义（两个主题列表相加等于什么都不准），
  静默覆盖会让用户丢掉调了半年的设置；因此默认拒绝，把决定权交给 `--force`。
- **"模板初值"是唯一的例外，且判据很严。** 新用户第一次打开页面就会生成空的
  `config.json` / `interests.json`。若把它当作"已有内容"，界面上的一键导入对**目标用户**
  永远失败——"一键"就失去意义。判据是**与 `*.example.json` 完全一致（忽略 `_comment`）**；
  用户改过任何一项（类别、下载目录、主题……）都会回到"默认拒绝"。
- **`port` 既不参与判定，也不会被覆盖。** 它是"这台机器上服务监听哪"，属于基础设施而非
  个人设置；跟着别人的包改端口，会让界面再也连不上。
- **`usage` 只能并集。** 收藏是"我读过什么"，并集永不破坏；覆盖会删掉本机刚积累的记录。
  同名条目保留本机，是因为 `downloads[].path` 是绝对路径，别人的路径在本机一定失效。
- **`learning` 默认不导入。** 它是本机行为训练出来的结果，跨机器语义弱；且它是唯一会
  "覆盖"的文件，因此宁可少做一步。

`ok` 的判据：没有任何 `refused`。部分成功（比如 core 被拒但 usage 合并了）返回 `ok=False`
并逐条列出，界面据此提示"已合并收藏，但配置未覆盖，请用命令行加 `--force`"。

### 5.4 导出语义

- 默认只导出 `core`；`--with-usage` / `--with-learning` / `--with-notes` 逐个打开。
  默认关掉高敏分组，是为了让"随手 export 一下然后提交"这个动作**默认安全**。
- `sanitize=True`（默认）时：`config.json.download_dir` 改为中性的 `papers`；
  `library.json` 里所有 `downloads[].path` / `favorites[].path` 只保留文件名。
  `--keep-paths` 关闭该行为（仅用于本机备份）。
- 导出后扫描全包，若仍存在形似绝对路径的字符串（例如画像里的主页链接之外的路径），
  在输出里逐条警告，并在 `manifest.json` 记 `sanitized: true/false`。
- `manifest.json` 的 `files[].sha256` 在导出时计算，导入时校验。手改包内 JSON 后如果不更新
  清单，导入会**拒绝该文件**并提示"重新导出或删掉 manifest.json"——这是刻意的：宁可不导，
  也不要把半改坏的数据写进运行态。

---

## 六、隔离边界：界面只暴露"形状"

这是本设计里最容易被忽略、也最需要写死的一条。

| 层 | 允许 | 禁止 |
| --- | --- | --- |
| `/profile` 的「📦 数据包」面板 | 包名、文件清单、体积、分组标签、"导入"按钮 | 包的 `title` / `description`、类别、主题、人名、关键词 |
| `GET /api/datapacks` | `{name, files, groups, bytes}` + 本机状态 `{file, exists, bytes, group}` | 同上 + 本机绝对路径 |
| 命令行 `tools/preset.py list/show` | 全部（含标题、描述、逐文件差异） | — |
| 渲染后的任何页面 | — | `presets/` 下的任何 JSON 内容 |

理由：包名与文件清单是"这里有一份可选数据"，而描述里的"数据库系统 / 分布式计算 / 形式化方法"
就是作者的**类别选择与画像方向**，正是要隔离的东西。想了解内容有两条正当路径：读
`presets/<名字>/README.md`，或导入。命令行不设限，因为它是使用者主动发起的、看得见的动作。

`tests/e2e/test_user_journey.py::test_fresh_install_has_no_personal_traces` 会渲染
`/`、`/profile`、`/favorites` 三个页面，断言其中不出现包里的人名、研究方向词与本机路径。

---

## 七、入口：启动参数与一键导入

### 7.1 启动参数

```bash
python run_daily.py --preset hengxin        # 先导入，再抓取/推荐/渲染
python server.py --preset hengxin           # 先导入，再起服务
start_digest.bat hengxin                    # 同上（Windows 双击场景）
```

行为约定：

- 导入在**其它动作之前**执行。`run_daily.py` 里 `--preset` 先于 `--categories`，
  因此 `--preset hengxin --categories cs.LG` 是"导入画像 + 用 cs.LG 覆盖类别"。
- 导入失败**不阻断启动**：打印逐文件报告，继续跑。理由：用户可能只是名字打错，
  或本机已有配置想保留；让服务起来才能从界面排查。
- 已在运行的服务不会被重启。`--preset` 只影响本次进程；界面导入走 HTTP 接口，两者互不依赖。

### 7.2 界面一键导入

`/profile` →「📦 数据包」→ 每个包一行 →「导入」。

```
POST /api/preset  {"op":"import","name":"hengxin"}          # 默认分组
POST /api/preset  {"op":"import","name":"hengxin","force":true}
GET  /api/datapacks
```

导入成功后页面刷新（`location.reload()`），因为主来源卡片是**服务端首屏渲染**的；
之后仍需点一次「↻ 重算推荐」才会重排摘要页（摘要是静态文件，不随接口变化）。

---

## 八、备选方案与取舍

| 方案 | 优点 | 为什么不选 |
| --- | --- | --- |
| 把运行态搬到 `~/.arxiv-digest/` | 代码目录绝对干净；`git clean -xdf` 不伤数据；分享目录零风险 | 破坏"绿色目录"直觉；1700+ 篇个人文库与 `output/` 的所有文档、脚本、测试都要改路径；收益（防打包泄漏）可以用"包 + 忽略规则"低成本达到 |
| 一个大 JSON 包 | 单文件好传 | 见 §4.1：生命周期、隐私等级、写入放大、改造面都不合适 |
| 启动时自动扫描 `presets/` 并合并 | "零操作"体验 | 直接违反 G1/G6：任何人的数据都会在首启动时进入界面；且无法解释"为什么我的画像多了一个主题" |
| 导入即覆盖全部文件 | 语义简单 | 一次误操作就清空用户积累的收藏与调好的画像 |
| 用 zimport/zip 打包 | 体积小 | 不可 diff、不可 grep，评审看不见改动 |

---

## 九、失败模式与降级

| 场景 | 行为 |
| --- | --- |
| 包名含 `../`、绝对路径、以 `.` 开头 | 拒绝，`ok=False`，不触碰任何文件 |
| `manifest.json` 的 `schema` > 1 | 拒绝整包，提示"包来自更新的版本" |
| 某文件 `sha256` 与清单不符 | 拒绝该文件，其余照常；提示重新导出或删除清单 |
| 包内 JSON 解析失败 | 拒绝该文件（不写入半份数据），报告原因 |
| 导入时写盘失败（权限/磁盘） | 该文件 `refused`，其余继续；`ok=False` |
| 备份目录写不进去 | 该覆盖动作降级为 `refused`（**不允许无备份覆盖**） |
| 服务未启动时点界面导入 | 前端已提示"本地服务未启动"，引导 `start_digest.bat` |
| `--preset` 名字不存在 | 打印可用包列表，继续启动 |

---

## 十、验收标准

实现完成后，下列断言必须成立（前七条已落成自动化测试）：

1. 裸沙箱（无 `config.json` / `interests.json` / `output/`）下：
   `/` 返回 200 且是欢迎页；`/api/state` 的四个集合全空、`download_dir == "papers"`；
   `/favorites` 出现空态文案；`/profile` 不含任何主题与主来源。
2. 裸沙箱的 `interests.json` 由模板生成后 `topics == []`、`people == []`、`owners == []`。
3. 把一个含人名与研究方向描述的包放进 `presets/`：`/profile` 与 `/api/datapacks`
   的输出里**不出现**这些人名与描述词，只出现包名。
4. `import_pack` 对已存在且**被用户改过**的 `config.json` 默认拒绝；`force=True` 时先备份再覆盖；
   若本机文件仍是模板初值（与 `*.example.json` 一致），则直接替换——否则一键导入对目标用户失效。
5. `import_pack` 对 `library.json` 只做并集：本机已有条目一条不少，包内新条目全部进入。
6. 同一包连续导入两次，第二次全部 `skipped`（幂等）。
7. `export_pack` 默认不含 `library.json`；开 `--with-usage` 后绝对路径被裁剪为文件名。
8. 文档：`docs/documentation.md` 与 `mkdocs.yml` 收录本文；`python -m mkdocs build --strict`
   通过（无断链）。
9. 整机验收：`python tools/fresh_clone_check.py` 通过（复制整棵源码树 → 起真服务 →
   引导页 / 空画像 / 空收藏 / 空状态 / 包视图只有形状 / 无私人痕迹 / 模板初值上一键导入成功）。

---

## 十一、迁移说明

对已有用户（包括作者本人）：

- 运行态文件位置**不变**：`config.json`、`interests.json`、`output/` 都留在原处，无需迁移。
- 想在另一台机器上恢复：`python tools/preset.py export myown --with-usage --with-notes`
  （在旧机器）→ 拷贝 `presets/myown/`（在新机器）→ `python run_daily.py --preset myown`。
- 已经存在的 `presets/<名字>/meta.json` 继续可读；下次 `export` 会同时补出 `manifest.json`。
- `interests.example.json` 清空了示例主题。已有 `interests.json` 的用户不受影响（不会被重写）；
  仍带着"示例主题"的旧文件在摘要页头部会被过滤（沿用既有逻辑）。

---

相关：[预设（数据包）指南](../guide/presets.md) · [数据文件参考](../reference/data-files.md) ·
[模块职责](modules.md) · [目录职责](../meta/structure.md)
