# arXiv-digest

把 arXiv 的每日新论文按**你自己的研究画像**排序，生成一份可交互的本地日报：收藏、下载 PDF、
就地展开摘要、Downvote 反馈——全部离线可用，点一次就当场学会你的口味。

> 默认初始化是干净的：clone 下来不带任何人的研究兴趣、分类偏好、收藏记录或本机路径。
> 任何人的整套设置都以**数据包**（`presets/<名字>/`，纯 JSON）单独存放，
> 用 `python run_daily.py --preset hengxin` 或到 `/profile` 一键导入才生效。
> 为什么要这样分层，见[私人数据隔离](architecture/data-isolation.md)。

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } __快速开始__

    ---

    三条命令跑起来，10 分钟走完完整闭环。

    [:octicons-arrow-right-24: 安装](getting-started/installation.md)
    [:octicons-arrow-right-24: 快速开始](getting-started/quickstart.md)

-   :material-chart-line:{ .lg .middle } __可解释的打分__

    ---

    主题命中 / 熟悉作者 / 代表系统 / 降权词逐项可拆。

    [:octicons-arrow-right-24: 排序与学习算法](architecture/ranking.md)

-   :material-brain:{ .lg .middle } __会学习的画像__

    ---

    收藏 / 下载 / Downvote 实时改写你的兴趣画像。

    [:octicons-arrow-right-24: 调优画像](guide/profile-tuning.md)

-   :material-book-open-page-variant:{ .lg .middle } __完整文档__

    ---

    六层文档体系，按用途定位。

    [:octicons-arrow-right-24: 文档中心](documentation.md)

</div>

---

## 一句话说清它是什么

```text
抓取 arXiv  →  打分排序  →  渲染单文件 HTML  →  本地服务提供交互
             (画像 + 行为学习)                    (收藏 / 下载 / 反馈 → 改写画像)
```

## 核心特性

| 特性 | 说明 |
| --- | --- |
| **分类自由选** | 官方 155 个分类（20 个 archive）任选：两级联动下拉、搜索、多选、标签拖拽排序；不限 `cs.*` |
| **两层推荐** | 「为你推荐」（主分类，阈值 ≥7）与「兴趣扩展」（邻域分类，阈值 ≥9）互不重叠，前者求准、后者破茧 |
| **只呈现本期新增** | SQLite `seen` 表判定首次出现期次，往期进 `/archive` 按日期回看 |
| **可解释的打分** | 主题命中 / 熟悉作者 / 代表系统 / 降权词 / 关键词权重逐项可拆 |
| **会学习的画像** | 收藏 +1.0、下载 +1.3、展开摘要 +0.3、Downvote 单篇 -12；主题倍率与关键词权重实时更新 |
| **交互零等待** | 乐观更新 + 30ms 合并重排；下载期间其它论文的反馈照常响应 |
| **离线单文件 HTML** | 内联 CSS/JS、无 CDN、无构建步骤；`file://` 双击也能读 |
| **零运行期依赖** | 只用 Python 标准库，`clone` 即跑 |
| **启动不挑端口** | 默认 `127.0.0.1:8765`，被占用自动顺延并在日志里报出实际地址；启动后自动开浏览器，可开关 |
| **可选视频链路** | Remotion 代码渲染 + Edge TTS 中文旁白 + A/V 质量闸门 + B 站投稿 |
| **测试兜底** | 795 个用例分四层，行覆盖率 91%，全部在沙箱里跑 |

## 快速上手

```bash
git clone git@github.com:0xaiio/arXiv-digest.git
cd arXiv-digest
python run_daily.py          # 首次运行自动生成干净的 config.json / interests.json
```

跑完终端会打印 `digest online: http://127.0.0.1:8765`（默认端口被占用时自动顺延，
以打印的地址为准；`run_daily.py` 只打印不开浏览器）。之后：

```bash
python run_daily.py --skip-fetch --skip-affil   # 改完画像/模板，秒级重算重渲染
python server.py                                 # 只起服务，不重新抓取（会开浏览器）
python server.py --no-open                        # 起服务但不开浏览器
python run_daily.py --preset hengxin             # 导入一份现成数据包（可选）
```

Windows 可双击 `start_digest.bat`（带参数 `start_digest.bat hengxin` 则同时导入数据包）。
完整步骤见[快速开始](getting-started/quickstart.md)。

## 文档导航

- **教程**：[安装](getting-started/installation.md) · [快速开始](getting-started/quickstart.md)
- **指南**：[日常使用](guide/daily-workflow.md) · [调优画像](guide/profile-tuning.md) · [数据包（预设）](guide/presets.md) · [视频与投稿](guide/video-pipeline.md)
- **参考**：[命令行](reference/cli.md) · [HTTP API](reference/http-api.md) · [config.json](reference/config.md) · [interests.json](reference/interests.md) · [数据文件](reference/data-files.md)
- **概念**：[架构总览](architecture/overview.md) · [私人数据隔离](architecture/data-isolation.md) · [模块职责](architecture/modules.md) · [排序算法](architecture/ranking.md) · [服务运行时](architecture/server-runtime.md)
- **开发与运维**：[开发指南](contributing/development.md) · [测试与回归](contributing/testing.md) · [故障排查](operations/troubleshooting.md)
- **元信息**：[目录职责](meta/structure.md) · [FAQ](meta/faq.md) · [术语表](meta/glossary.md)

---

本项目为个人工具，不隶属于 arXiv 或 Cornell University。论文元数据的版权归原作者所有。
