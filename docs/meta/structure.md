# 目录职责

本文回答"某个文件为什么放在那里"，以及一个常被追问的设计问题：**为什么没有 `src/` 布局**。

---

## 一、顶层结构

```
arXiv-digest/
├─ README.md                  # 项目门面 + 完整文档索引
├─ CONTRIBUTING.md             # 贡献指南（GitHub 会自动在 issue/PR 页提示）
├─ CHANGELOG.md                # 变更记录（Keep a Changelog 风格）
├─ .gitignore                  # 公开仓库的忽略规则（个人数据与凭据）
│
├─ run_daily.py                # 主流程编排（唯一"一键"入口）
├─ fetch_arxiv.py              # 抓取：主分类
├─ fetch_expand.py             # 抓取：扩展分类
├─ fetch_rss.py                # 抓取：RSS 降级通道
├─ fetch_affil.py              # 抓取：作者单位
├─ fetchsrc.py                 # 兴趣来源取数适配（arXiv / 网页 / 文档）
├─ recommend.py                # 打分编排与本期隔离
├─ scoring.py                  # 纯打分函数（无 IO）
├─ textscan.py                 # 纯文本信号抽取（人名 / 实词 / 主题命中）
├─ profile.py                  # 行为学习
├─ archive.py                  # 归档（SQLite）
├─ build_report.py             # 渲染逻辑（版面在 templates/）
├─ server.py                   # 本地 HTTP 服务（进程装配与分发）
├─ routes.py                   # HTTP 语义（路由表 / Reply / Request）
├─ service.py                  # 业务用例（收藏 / 下载 / 学习 / 重建）
├─ datapack.py                 # 私人数据包：导入 / 导出 / 本机状态
├─ customize.py                # 可定制项读写（唯一入口）
├─ arxiv_cats.py               # arXiv 官方分类表 + 校验/检索/邻域（数据，不是逻辑）
├─ paperutil.py                # 配置 / 库文件 / 命名（基础层）
├─ netroute.py                 # 下载选路
├─ paths.py                    # 路径唯一来源（+ `python paths.py` 诊断）
│
├─ templates/                  # 版面：style.css / app.js / 四个页面模板
├─ config.example.json         # 配置模板 → 首次运行生成 config.json
├─ interests.example.json      # 画像模板 → 首次运行生成 interests.json
├─ start_digest.bat            # Windows 双击启动
│
├─ docs/                       # 全部文档（见 §3）
├─ tests/                      # pytest 套件：unit / integration / e2e（沙箱隔离）
├─ tools/                      # 辅助脚本：维护 / 回归验收 / 视频 / 投稿（见 §2）
├─ presets/<名字>/              # 数据包：一整套设置与使用数据（默认不加载，纯 JSON）
├─ reel/                       # 可选视频工程（Remotion）
└─ output/                     # 运行产物（.gitignore，见文档 reference/data-files.md）
```

### 为什么多了 `templates/` 与三层拆分

| 变化 | 理由 |
| --- | --- |
| `templates/` 独立 | 版面原先内联在 `build_report.py` 里，占了 1400 行；`%` 格式化会吃掉内联 JS 的反斜杠（曾导致整段脚本语法错误、所有按钮失效）。独立文件可单独 lint / diff，改完**不用重启** |
| `service.py` | 业务规则原先内联在 `do_POST` 的 if 链里，与 `self._json()` 缠绕，只能靠起真 HTTP 服务验证 |
| `routes.py` | 两个 130/170 行的 if 链违反开闭原则：加接口要改 Handler，且路由清单无法被程序读取 |
| `scoring.py` / `textscan.py` / `fetchsrc.py` | 把「纯计算」「文本处理」「网络取数」从既有模块里剥出来，各自可脱离网络/文件单测 |
| `paths.py` | 路径原先散落在 10 个模块；新增模块漏跟随约定曾导致测试写坏真实数据 |

## 二、`tools/` 的分工

`tools/` 按用途分四类，文件名以 `_check.py` 结尾的才是回归测试：

| 类别 | 文件 | 说明 |
| --- | --- | --- |
| **黑盒验收** | `concurrency_check.py` `dv_unify_check.py` `owner_ui_check.py` `ui_file_check.py` `dl_button_check.py` | 发布前的整页实测（可能读写真实 output/）；日常回归请用 `tests/`，见[测试与回归](../contributing/testing.md) |
| **开发探针** | `ui_probe.py` `ui_shots.py` `ui_final_check.py` `ui_check_v3.py` | 一次性验证与截图留档，非闸门 |
| **历史一次性脚本** | `restore_raw_20260916.py` `summaries_20260916.py` `summaries_20260918.py` `seed_notes_20260912.py` | 按日期命名的当期数据修复/补录脚本，保留作示例；新的一期不需要它们 |
| **内容与数据维护** | `gen_pending.py` `merge_raw_pool.py` `rebuild_raw_from_index.py` `backfill_archive.py` | 补摘要、修池子、回填归档 |
| **视频与投稿** | `gen_video_data.py` `gen_narration.py` `check_video_av.py` `bili_collection.py` `bili_tv_qr_login.py` `bili_qr_login.py` | 见[视频与投稿](../guide/video-pipeline.md) |
| **配置管理** | `preset.py` | 数据包的命令行外壳（list / show / import / export / status），语义在 `datapack.py` |

`bili_upload.py` 不在 `tools/`，而在 `.workbuddy/skills/bili-auto-upload/scripts/`——
它是可复用的技能脚本，被多个项目共享。

## 三、`docs/` 的组织

按"读者要做什么"分六层，**一个主题一个文件**：

| 目录 | 放什么 | 不该放什么 |
| --- | --- | --- |
| `getting-started/` | 安装、快速开始（有先后顺序的教程） | 参考细节、设计讨论 |
| `guide/` | 按任务组织的操作指南（日常使用、调画像、预设、视频） | 字段逐项列表 |
| `reference/` | 精确取值：CLI、HTTP API、两个配置、数据文件 | 长段解释、教程叙事 |
| `architecture/` | 概念与取舍：总览、模块、排序算法、服务运行时 | 操作步骤 |
| `contributing/` | 开发约定、测试与回归 | 用户向内容 |
| `operations/` | 故障排查 | 概念型问答（放 `meta/faq.md`） |
| `meta/` | 目录职责、FAQ、术语表 | 具体功能说明 |

导航入口是 [文档中心](../documentation.md)，同时被根 [README](https://github.com/0xaiio/arXiv-digest#readme) 完整索引。
**新增文档必须同时登记到这两处**，否则视为不可达。

## 四、为什么没有 `src/` 布局（以及为什么暂时不改）

Python 社区的 `src/<package>/` 布局适合"要发布到 PyPI、要被别人 import"的库。本项目不是：

| 事实 | 后果 |
| --- | --- |
| 它不是库，是**一组可独立运行的脚本** | `python build_report.py`、`python server.py` 是文档与自动化里的一等命令 |
| 模块之间是**平级单文件**，没有包命名空间 | 移入 `src/arxiv_digest/` 后每个 `import paperutil` 都要改成包内导入 |
| 26 个 `tools/*.py` 都靠 `sys.path.insert(0, ROOT)` + 顶层导入 | 包化后全部需要改成 `from arxiv_digest import ...`，且 ROOT 计算要重写 |
| 定时自动化与 B 站投稿脚本**已经引用固定路径** | `run_daily.py`、`tools/gen_video_data.py` 等路径一改即断 |
| 收益只有"目录看起来更规范" | 读者收益 ≈ 0；破坏风险 = 夜间流水线 + 已发布流程 |

所以当前选择是：**根目录 = 主流程模块**（18 个，一眼可数），把"非主流程"的东西全部推到
`tools/`、`templates/`、`presets/`、`reel/`、`docs/`。这条边界比目录名更重要。

**注意区分「拆模块」与「包化」**：这次重构把 `server.py` 拆成 `service` + `routes`、
把打分/文本/取数拆成独立模块——那是**单一职责**问题，拆完仍然是平级单文件，
`python server.py` 照样能跑，自动化路径没变。包化解决的是**命名空间**问题，
收益小、破坏面大。两者不是一回事，别用「既然要重构就顺便包化」把风险叠上去。

真要引入 `src/` 布局，正确姿势是一次性做完并同步更新自动化：

1. `mkdir -p src/arxiv_digest && git mv *.py src/arxiv_digest/`；
2. 包内导入改为相对导入（`from . import paperutil as pu`）；
3. 根目录保留**薄入口**（`run_daily.py` 只做 `from arxiv_digest.run_daily import main`）；
4. `tools/*` 改为 `sys.path.insert(0, os.path.join(ROOT, "src"))`；
5. 全量回归 + 更新本文与 [cli.md](../reference/cli.md)、自动化任务的工作目录与命令。

收益是命名空间干净，代价是入口多一层间接。**没有需求前不做。**

## 五、文件放哪里：决策树

```
它是主流程的一步吗？
├─ 是 → 放根目录，命名 fetch_*.py / recommend.py / build_report.py ...
└─ 否
   ├─ 它是给人看的说明？ → docs/<对应类别>/
   ├─ 它是一次性/维护脚本？ → tools/
   ├─ 它是一整套设置/使用数据？ → presets/<名字>/（纯 JSON，见[数据隔离](../architecture/data-isolation.md)）
   ├─ 它是视频工程的一部分？ → reel/
   └─ 它是运行产物？ → output/（不要提交）
```

## 六、命名约定

| 对象 | 约定 | 例子 |
| --- | --- | --- |
| 主流程模块 | 动词或名词单词，无前缀 | `recommend.py`、`archive.py` |
| 抓取脚本 | `fetch_<对象>.py` | `fetch_affil.py` |
| 工具脚本 | 描述性下划线名，测试以 `_check.py` 结尾 | `gen_pending.py`、`dv_unify_check.py` |
| 文档 | 小写连字符，`docs/<类别>/<主题>.md` | `docs/guide/profile-tuning.md` |
| 数据文件 | `output/<用途>.json`；临时文件以 `_` 开头 | `library.json`、`_pending.txt` |
| 归档快照 | `output/archive/<YYYYMMDD>.{html,md}` | `20261017.html` |

## 七、哪些东西永远不进仓库

| 类别 | 具体文件 | 为什么 |
| --- | --- | --- |
| 个人数据 | `config.json`、`interests.json` | 含本机路径与画像 |
| 运行产物 | `output/` 全部 | 体积大、含个人阅读记录 |
| 凭据 | `.secrets/`、`cookies.json`、`**/*cookie*.json`、`**/token.json` | 等同账号密码 |
| 依赖与渲染产物 | `node_modules/`、`reel/out/`、`reel/public/audio/` | 可由 `npm ci` / 脚本重建 |
| 本机状态 | `.workbuddy/memory/`、探针截图 | 会话记忆，对他人无意义 |

例外：`.workbuddy/skills/` 被保留（技能代码，有复用价值）。

---

相关：[架构总览](../architecture/overview.md) · [开发指南](../contributing/development.md) ·
[数据文件](../reference/data-files.md)
