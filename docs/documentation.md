# arXiv-digest 文档中心

这里是全部文档的入口。文档按**用途**分层，每篇只负责一件事：需要背景去"概念"，
需要步骤去"指南"，需要精确取值去"参考"。跨主题的内容一律用链接而不是复制。

> 首次使用？直接看 [安装](getting-started/installation.md) → [快速开始](getting-started/quickstart.md)。
> 想先弄清它是怎么算分的？跳到 [排序与学习算法](architecture/ranking.md)。

---

## 一、文档地图

文档按用途分成六层，对应六种提问方式。先看下表定位，再点进去：

| 我想…… | 去哪一类 | 典型文档 |
| --- | --- | --- |
| 从头跑起来 | 教程（Tutorial） | [安装](getting-started/installation.md) · [快速开始](getting-started/quickstart.md) |
| 完成一件具体的事 | 指南（How-to） | [日常使用](guide/daily-workflow.md) · [调画像](guide/profile-tuning.md) · [预设](guide/presets.md) · [视频与投稿](guide/video-pipeline.md) |
| 查一个字段/参数/接口 | 参考（Reference） | [命令行](reference/cli.md) · [HTTP API](reference/http-api.md) · [config.json](reference/config.md) · [arXiv 类别](reference/categories.md) · [interests.json](reference/interests.md) · [数据文件](reference/data-files.md) |
| 理解为什么这样设计 | 概念（Explanation） | [架构总览](architecture/overview.md) · [模块职责](architecture/modules.md) · [排序算法](architecture/ranking.md) · [服务运行时](architecture/server-runtime.md) |
| 出问题了 / 想改代码 | 运维与开发 | [故障排查](operations/troubleshooting.md) · [开发指南](contributing/development.md) · [测试与回归](contributing/testing.md) |
| 名词看不懂 | 元信息 | [术语表](meta/glossary.md) · [FAQ](meta/faq.md) · [目录职责](meta/structure.md) |

## 二、教程：从零到第一份日报

| 文档 | 内容 | 读完你能 |
| --- | --- | --- |
| [installation.md](getting-started/installation.md) | 环境要求、克隆、目录就位、首次初始化发生了什么、如何验证装好了 | 在本机得到一个能跑的干净实例 |
| [quickstart.md](getting-started/quickstart.md) | 10 分钟走完「跑流水线 → 读日报 → 收藏/下载/Downvote → 改画像 → 看效果」 | 完整体验一次推荐闭环 |

## 三、指南：按任务查

| 文档 | 解决的问题 |
| --- | --- |
| [daily-workflow.md](guide/daily-workflow.md) | 每天怎么用：三个板块怎么读、工具栏筛选、批量下载、往期回看、导出 |
| [profile-tuning.md](guide/profile-tuning.md) | 推荐不准怎么调：主题、熟悉作者、降权词、兴趣来源、反馈的边际效果 |
| [presets.md](guide/presets.md) | 一整套设置怎么搬：`tools/preset.py` 的 list / import / export，以及分享前的隐私检查 |
| [video-pipeline.md](guide/video-pipeline.md) | 可选模块：把当期日报渲染成带中文旁白的视频并投稿到 B 站 |

## 四、参考：精确取值

| 文档 | 覆盖范围 |
| --- | --- |
| [cli.md](reference/cli.md) | 所有可执行入口（根目录 6 个脚本 + `tools/` 常用脚本）的参数、默认值、产物 |
| [http-api.md](reference/http-api.md) | 本地服务的全部页面路由与 JSON 接口，含请求体、响应字段、错误约定 |
| [config.md](reference/config.md) | `config.json` 每个字段的含义、默认值、影响范围 |
| [categories.md](reference/categories.md) | 官方分类表（20 个主类 / 155 个分类）从哪来、两级联动下拉怎么用、校验规则、顺序如何影响页面 |
| [interests.md](reference/interests.md) | `interests.json` 的结构：主来源、主题、熟悉作者、代表系统、降权词、行为超参 |
| [data-files.md](reference/data-files.md) | `output/` 下每个文件的用途与结构，`archive.db` 的三张表，`library.json` 的字段 |

## 五、概念：实现与取舍

| 文档 | 讲什么 |
| --- | --- |
| [overview.md](architecture/overview.md) | 端到端数据流：抓取 → 增量判定 → 打分 → 渲染 → 归档，以及每一步失败时的降级 |
| [modules.md](architecture/modules.md) | 14 个 Python 模块的职责、依赖方向、谁调用谁（改代码前先看这里） |
| [ranking.md](architecture/ranking.md) | 打分公式逐项拆解、行为学习更新式、为什么负向学习默认关闭 |
| [server-runtime.md](architecture/server-runtime.md) | 两级锁、单篇下载锁、论文索引缓存、CORS、`file://` 兼容、下载选路 |

## 六、开发与运维

| 文档 | 用途 |
| --- | --- |
| [development.md](contributing/development.md) | 本地开发约定、改完什么必须重启、调试手法、提交前检查 |
| [testing.md](contributing/testing.md) | 四层测试结构（666 用例 / 90% 覆盖）、覆盖范围、运行方式、沙箱隔离、如何新增 |
| [troubleshooting.md](operations/troubleshooting.md) | 症状 → 诊断命令 → 根因 → 修复，覆盖抓取/推荐/下载/服务/视频/投稿 |

## 七、元信息

| 文档 | 用途 |
| --- | --- |
| [structure.md](meta/structure.md) | 每个目录与顶层文件为什么在那里，以及为什么没有采用 `src/` 布局 |
| [faq.md](meta/faq.md) | 概念型问题（和故障排查互补：这里回答"该不该/为什么"，那里回答"报错了怎么办"） |
| [glossary.md](meta/glossary.md) | 本期新增、画像、种子权重、倍率、短号、主类/子类等术语的准确定义 |

---

## 八、阅读约定

- **路径**：文中所有路径默认相对项目根目录（`arXiv-digest/`）。文档之间的链接一律用相对路径，可在本地直接跳转。
- **命令**：Linux/macOS 的 `python` 在 Windows 上可能是 `py -3`；两者等价。
- **占位符**：`<日期>` 指 `YYYYMMDD`，`<短号>` 指不带版本号的 arXiv 编号（如 `2609.09742`），见[术语表](meta/glossary.md)。
- **版本**：文档描述的是当前 `main` 分支的行为。接口或字段有破坏性改动时，会同时更新对应参考页与
  [CHANGELOG](https://github.com/0xaiio/arXiv-digest/blob/main/CHANGELOG.md)。
- **发现文档与代码不一致**：以代码为准，并提 issue 或直接改文档——文档错误按缺陷处理，参见
  [贡献指南](https://github.com/0xaiio/arXiv-digest/blob/main/CONTRIBUTING.md)。

## 九、贡献文档

新增文档请先回答三个问题：它属于上面哪一类？它和已有文档的边界在哪？读者看完能做什么？

- 一个主题一个文件，文件名用小写连字符（`profile-tuning.md`）；
- 放在对应子目录，不要平铺在 `docs/` 根下；
- 新文档必须被本页与 [README](https://github.com/0xaiio/arXiv-digest#readme) 索引收录，否则视为不可达；
- 写完后自查所有相对链接指向真实文件（详见 [开发指南](contributing/development.md)）。
