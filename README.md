# arXiv-digest

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Runtime deps](https://img.shields.io/badge/runtime-stdlib--only-brightgreen)](#环境与依赖)
[![Docs](https://img.shields.io/badge/docs-22%20pages-informational)](docs/README.md)
[![Tests](https://img.shields.io/badge/tests-551%20passed-success)](docs/contributing/testing.md)
[![Coverage](https://img.shields.io/badge/coverage-89%25-brightgreen)](docs/contributing/testing.md#三覆盖率)
[![Status](https://img.shields.io/badge/status-active-success)](#项目状态)

把 arXiv 的每日新论文按**你自己的研究画像**排序，生成一份可交互的本地日报：
收藏、下载 PDF、就地展开摘要、Downvote 反馈——全部离线可用，点一次就当场学会你的口味。

> **默认初始化是干净的**：clone 下来不带任何人的研究兴趣、分类偏好或本机路径。
> 想看一份调了半年的真实画像，用 `python tools/preset.py import hengxin` 按需导入。

```text
抓取 arXiv  →  打分排序  →  渲染单文件 HTML  →  本地服务提供交互
             (画像 + 行为学习)                    (收藏 / 下载 / 反馈 → 改写画像)
```

---

## 目录

- [特性](#特性)
- [快速开始](#快速开始)
- [界面一览](#界面一览)
- [文档索引](#文档索引)
- [项目结构](#项目结构)
- [配置与个人数据](#配置与个人数据)
- [质量闸门](#质量闸门)
- [环境与依赖](#环境与依赖)
- [贡献](#贡献)
- [项目状态](#项目状态)

## 特性

| 特性 | 说明 |
| --- | --- |
| **两层推荐** | 「🎯 为你推荐」（主分类，阈值 ≥7）与「🌱 兴趣扩展」（邻域分类，阈值 ≥9）互不重叠，前者求准、后者破茧 |
| **只呈现本期新增** | SQLite `seen` 表判定首次出现期次，往期进 `/archive` 按日期回看，不会天天重播旧论文 |
| **可解释的打分** | 主题命中 / 熟悉作者 / 代表系统 / 降权词 / 关键词权重逐项可拆，公式与算例见[排序算法](docs/architecture/ranking.md) |
| **会学习的画像** | 收藏 +1.0、下载 +1.3、展开摘要 +0.3、Downvote 单篇 -12；主题倍率与关键词权重实时更新 |
| **交互零等待** | 乐观更新 + 30ms 合并重排；下载期间其它论文的 Downvote / 收藏照常响应（[并发实测](docs/architecture/server-runtime.md)） |
| **离线单文件 HTML** | 内联 CSS/JS、无 CDN、无构建步骤；`file://` 双击也能读，服务在跑时还能交互 |
| **零运行期依赖** | 只用 Python 标准库，`clone` 即跑，不需要 `pip install` |
| **可选视频链路** | Remotion 代码渲染 + Edge TTS 中文旁白 + A/V 质量闸门 + B 站投稿（[指南](docs/guide/video-pipeline.md)） |
| **可导入的预设** | 一整套 `config.json` + `interests.json`，一条命令搬过来，分享前有隐私检查清单 |
| **测试兜底** | 551 个用例分四层（单元 / 集成 / 端到端 / 浏览器），行覆盖率 89%，全部在沙箱里跑，不碰真实数据 |

## 快速开始

```bash
git clone git@github.com:0xaiio/arXiv-digest.git
cd arXiv-digest
python run_daily.py          # 首次运行自动生成干净的 config.json / interests.json
```

跑完浏览器会打开 `http://127.0.0.1:8765/`。之后：

```bash
python run_daily.py --skip-fetch --skip-affil   # 改完画像/模板，秒级重算重渲染
python server.py                                 # 只起服务，不重新抓取
```

Windows 可双击 `start_digest.bat`（自动找 Python，端口读 `config.json`）。

**下一步**：跟着 [快速开始](docs/getting-started/quickstart.md) 走一遍 10 分钟的完整闭环，
或者先看 [安装](docs/getting-started/installation.md) 弄清初始化到底生成了什么。

## 界面一览

| 区域 | 内容 | 数量（默认） |
| --- | --- | --- |
| 🎯 为你推荐 | 主分类里本期最相关的论文，带评分、命中主题、推荐理由 | 14 |
| 🌱 兴趣扩展 | 主分类之外、与你画像相邻的论文，独立打分 | 10 |
| 📖 分类详解 | 本期全部新增论文，按分类与日期排列 | 全部 |
| 工具栏 | 已收藏 / 已下载 / 已 Downvote 筛选与搜索（作用于「分类详解」）、批量下载、重算推荐、往期回看 | — |
| `/favorites` | 收藏清单，可一键导出 `favorites.md` | — |
| `/profile` | 类别、下载目录、兴趣来源、画像主来源、主题权重 | — |
| `/archive` | 每期快照，按日期回看 | — |

## 文档索引

完整导航（按角色 / 按用途）见 **[文档中心](docs/README.md)**。下面按类别列出全部文档。

### 教程：从零跑起来

| 文档 | 内容 |
| --- | --- |
| [安装](docs/getting-started/installation.md) | 环境要求、克隆、首次初始化生成了什么、如何验证、卸载与重置 |
| [快速开始](docs/getting-started/quickstart.md) | 10 分钟闭环：跑流水线 → 读日报 → 交互 → 改画像 → 看效果 |

### 指南：按任务查

| 文档 | 解决的问题 |
| --- | --- |
| [日常使用](docs/guide/daily-workflow.md) | 三个板块怎么读、工具栏、五个按钮各自触发什么、收藏导出、往期回看、离线使用 |
| [调优画像](docs/guide/profile-tuning.md) | 推荐不准怎么调：起步配置、主题与降权词、兴趣来源、行为强度、画像漂移修复 |
| [预设](docs/guide/presets.md) | `tools/preset.py` 的 list / import / export，导入前必改项，分享前隐私检查 |
| [视频与投稿](docs/guide/video-pipeline.md) | 选片 → 口播稿 → TTS → Remotion 渲染 → A/V 闸门 → B 站投稿 → 归入合集 |

### 参考：精确取值

| 文档 | 覆盖范围 |
| --- | --- |
| [命令行](docs/reference/cli.md) | 所有入口脚本与 `tools/` 脚本的参数、默认值、产物、调度示例 |
| [HTTP API](docs/reference/http-api.md) | 页面路由 + 全部 JSON 接口，含请求体、响应字段、错误约定、调用示例 |
| [config.json](docs/reference/config.md) | 抓取、显示、端口等 13 个字段的默认值与影响范围 |
| [interests.json](docs/reference/interests.md) | 画像结构：主来源、主题、熟悉作者、代表系统、降权词、行为超参 |
| [数据文件](docs/reference/data-files.md) | `output/` 每个文件的用途与结构、`archive.db` 三张表、`library.json` 字段 |

### 概念：实现与取舍

| 文档 | 讲什么 |
| --- | --- |
| [架构总览](docs/architecture/overview.md) | 六阶段流水线、三层降级、本期新增判定、分层与依赖方向、扩展点 |
| [模块职责](docs/architecture/modules.md) | 13 个模块的职责、依赖图、关键函数、"我要改什么"定位表 |
| [排序与学习算法](docs/architecture/ranking.md) | 打分公式逐项拆解、数值算例、阈值与兜底、行为更新式、负向学习故障复盘 |
| [服务运行时](docs/architecture/server-runtime.md) | 两级锁、论文索引缓存、静态页 vs 动态页、CORS 与 `file://`、下载选路 |

### 开发与运维

| 文档 | 用途 |
| --- | --- |
| [开发指南](docs/contributing/development.md) | 代码约定、改完什么必须重启、调试手法、提交前检查清单、加功能的推荐路径 |
| [测试与回归](docs/contributing/testing.md) | 四层测试结构（551 用例）、覆盖范围、覆盖率与门槛、沙箱隔离、重构期等价性手段、如何新增 |
| [故障排查](docs/operations/troubleshooting.md) | 服务 / 抓取 / 推荐 / 下载 / 归档 / 摘要 / 视频 / 投稿 的"症状→诊断→修复" |

### 元信息

| 文档 | 用途 |
| --- | --- |
| [目录职责](docs/meta/structure.md) | 每个目录与顶层文件为什么在那里，以及为什么没有引入 `src/` 布局 |
| [FAQ](docs/meta/faq.md) | 概念型问题：定位、隐私、设计取舍、使用建议 |
| [术语表](docs/meta/glossary.md) | 本期新增、种子权重、学习倍率、短号、选路等术语的准确定义 |
| [贡献指南](CONTRIBUTING.md) | 提交 issue / PR 的流程与要求（根级文件，GitHub 自动识别） |
| [变更记录](CHANGELOG.md) | 按日期的功能与修复记录 |

## 项目结构

```text
arXiv-digest/
├─ 18 个主流程模块                # 抓取 / 打分 / 归档 / 渲染 / 服务 / 选路
│  ├─ 基础  paths.py paperutil.py netroute.py
│  ├─ 领域  textscan.py fetchsrc.py profile.py archive.py
│  ├─ 应用  customize.py scoring.py recommend.py fetch_*.py
│  ├─ 渲染  build_report.py
│  └─ 接口  service.py routes.py server.py
├─ templates/                    # 版面：style.css / app.js / 四个页面模板
├─ config.example.json          # 配置模板 → 首次运行生成 config.json（个人数据）
├─ interests.example.json       # 画像模板 → 首次运行生成 interests.json（个人数据）
├─ docs/                        # 文档（getting-started / guide / reference / architecture / …）
├─ tools/                       # 回归测试、数据维护、视频、投稿脚本
├─ tests/                       # pytest 套件：unit / integration / e2e（沙箱隔离）
├─ presets/                     # 可选预设（默认不加载）
├─ reel/                        # 可选视频工程（Remotion）
└─ output/                      # 运行产物（.gitignore，含归档库与收藏记录）
```

各模块的职责与依赖方向见 [模块职责](docs/architecture/modules.md)，
各目录的职责边界与"文件该放哪里"的决策树见 [目录职责](docs/meta/structure.md)。

## 配置与个人数据

两个文件在**首次运行**时自动生成，之后属于你的个人数据（`.gitignore` 已排除）：

| 文件 | 管什么 | 页面上改 |
| --- | --- | --- |
| `config.json` | 抓哪些分类、PDF 存哪、每期几条、端口 | `/profile` → 类别 / 下载目录 |
| `interests.json` | 主题、熟悉作者、代表系统、降权词、画像主来源 | `/profile` 各区块 |

日常维护不必手改 JSON。字段逐项说明见 [config.json](docs/reference/config.md) 与
[interests.json](docs/reference/interests.md)。

**绝不入库**：`output/`（日报与收藏记录）、`.secrets/`（B 站 cookie）、各类 `*cookie*.json` / token。

## 质量闸门

**主闸门是 pytest 套件**：551 个用例（单元 / 集成 / 端到端 / 浏览器），行覆盖率 89%，
门槛 85%。它们全部在 `tmp_pytest/` 沙箱里跑，**不会碰你的真实数据**。

```bash
python -m pip install -r requirements-dev.txt   # 只装测试工具，运行期仍然零依赖
python -m pytest                 # 551 passed，约 60s
python -m pytest -m unit         # 只跑单元，13s（改纯函数时用这个）
python -m pytest --cov           # 覆盖率，低于 85% 直接失败
```

`tools/*_check.py` 仍然保留，作为**发布前的黑盒验收**（真下载、真点按钮、必要时读写真实
`output/`），与 pytest 互补：

```bash
python tools/concurrency_check.py                              # 并发：下载不阻塞 Downvote、批量并行
python tools/dv_unify_check.py                                 # 三处 Downvote 的视觉/行为一致
python tools/owner_ui_check.py                                 # /profile 画像主来源增删改
python tools/ui_file_check.py output/arxiv_digest_<日期>.html   # 本地 HTML 跨源交互
python tools/dl_button_check.py                                # 真实点一次下载按钮
```

分层说明、覆盖范围、沙箱设计与失败排查见[测试与回归](docs/contributing/testing.md)。

## 环境与依赖

| 项 | 要求 |
| --- | --- |
| Python | 3.9+，**运行期只用标准库** |
| 网络 | 能访问 `arxiv.org` / `export.arxiv.org`（限流时自动降级 RSS） |
| 操作系统 | Windows / Linux / macOS（"打开文件"在非 Windows 上会退化为无操作） |
| 可选（功能） | Node 18+（视频）、`edge-tts` + `imageio-ffmpeg`（旁白）、`biliup-rs`（投稿） |
| 可选（测试） | `pip install -r requirements-dev.txt`（pytest / pytest-cov / websocket-client）；Edge 用于浏览器层 |

## 贡献

欢迎 issue 与 PR。开始之前请看 [贡献指南](CONTRIBUTING.md) 与
[开发指南](docs/contributing/development.md)——尤其是"改完什么必须重启"和"不要提交个人数据"两条。

最小流程：

```bash
git checkout -b feat/my-idea
python -m py_compile *.py tools/*.py
python tools/concurrency_check.py        # 无 GUI 也能跑
git commit -m "feat: ..." && git push
```

## 项目状态

- 主流程（抓取 / 推荐 / 归档 / 渲染 / 本地服务）稳定，日常在使用；
- 视频与 B 站投稿是可选的实验性附加链路，接口可能随平台变化；
- 有一个单机私有实例在长期运行（研究画像：数据库系统 / 分布式计算 / 形式化方法），
  那份设置以 `presets/hengxin/` 形式公开；
- **尚未附开源许可**（默认保留所有权利）。如需在他人项目中复用，欢迎先开 issue 讨论。

---

<sub>本项目为个人工具，不隶属于 arXiv 或 Cornell University。论文元数据的版权归原作者所有。</sub>
