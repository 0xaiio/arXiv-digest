# 命令行参考

项目没有安装步骤，所有入口都是"直接用 Python 跑一个脚本"。本文列出**每个可执行入口**的参数、
默认值与产物；具体用法见对应的指南页。

约定：

- 所有脚本都用 `python xxx.py` 运行；脚本内部用自身路径定位 `output/`，因此从别的目录调用也能工作（
  `server.py` 启动时还会把 cwd 固定到项目根）；
- `python` 在 Windows 上可能是 `py -3`，两者等价；
- 退出码 `0` = 成功；非 `0` 通常伴随 `stderr` 上的原因。

---

## 一、流水线入口

### `run_daily.py`

一键流水线：抓取 → 扩展抓取 → 推荐 → 作者单位 → 渲染 → 确保服务在线。

| 参数 | 作用 | 典型场景 |
| --- | --- | --- |
| （无） | 完整跑一遍 | 每天定时任务 |
| `--skip-fetch` | 复用已有 `output/raw.json` / `raw_expand.json`，跳过抓取 | 改了画像或模板，想秒级重算 |
| `--skip-affil` | 跳过作者单位抓取（约 3 秒/篇，是最慢的一步） | 赶时间、或不需要单位信息 |
| `--no-serve` | 只产出文件，不启动/不检查本地服务 | CI、服务器上只生成 HTML |
| `--serve` | 渲染完**前台**启动服务（阻塞） | 想让终端窗口承载服务进程 |
| `--categories cs.DB,cs.DC` | 先把跟踪的分类设为这几个（写入 `config.json`），再走正常流程 | 无 GUI 的机器、定时任务一次配好分类 |
| `--preset <名字>` | 先把 `presets/<名字>/` 这份数据包导入本机，再走正常流程 | 新机器恢复自己的设置，或试用别人公开的画像 |
| `--preset-force` | 允许 `--preset` 覆盖本机已有的 `config.json` / `interests.json`（先备份） | 确认要用包里的配置替换本机配置 |

组合示例：

```bash
python run_daily.py --skip-fetch --skip-affil      # 只推荐 + 渲染，通常几秒
python run_daily.py --no-serve                     # 只出文件
python run_daily.py --preset hengxin               # 导入数据包后再抓取
python run_daily.py --preset hengxin --categories cs.LG   # 用这份画像，但类别只看 cs.LG
```

`--preset` 先于 `--categories` 生效，因此后者可以覆盖前者带来的分类。
导入失败（名字不存在、本机已有不同配置）**不阻断**流水线，原因打印在终端。

失败行为：抓取步骤若未产出有效数据，会保留上一期文件（坏输出另存 `*.bad_<时间戳>`）；
若连历史数据都没有，则跳过推荐与渲染并直接返回，不会把已有日报清空。

`categories` 为空（通用版首次运行）时**不抓取任何东西**：打印「尚未选择任何 arXiv 分类」
与三条下一步（去 `/profile` 选、用 `--categories`、用 `--preset` 导入一份现成设置），
并在未加 `--no-serve` 时把本地服务拉起来，好让引导页可访问。

### 各阶段脚本（手动单独调用）

这些脚本一般由 `run_daily.py` 调用，但你也可以单独跑。**抓取类脚本把 JSON 打到 stdout**，
所以手动使用时需要自己重定向：

| 脚本 | 参数 | 产物 / 行为 |
| --- | --- | --- |
| `fetch_arxiv.py` | 无 | stdout 输出主分类 feed JSON → 通常 `> output/raw.json` |
| `fetch_expand.py` | 无 | stdout 输出扩展分类 feed → `> output/raw_expand.json`；`expand_categories` 留空时按同 archive 兄弟分类推导 |
| `fetch_rss.py` | `--dry` 只打印不写 | API 限流时的降级通道：抓分类 RSS，**按短号增量合并**进既有池 |
| `recommend.py` | 无 | `recommend.json` `expand.json` `papers_index.json` `issue_core.json` `issue_expand.json` `issue_stats.json` `scores.json` |
| `fetch_affil.py` | `--force` 重抓已缓存；`--max N` 本期最多解析 N 篇；`--only cs.DB,cs.DC` 只处理指定分类 | `output/affiliations.json`（跨日累积） |
| `build_report.py` | 无 | `arxiv_digest_<日期>.html/.md`、`favorites.html`、`archive.html`、`output/archive/<日期>.{html,md}`，并登记 `archive.db` |
| `server.py` | `--port <端口>` 指定**起始**端口；`--no-open` 不自动开浏览器；`--open` 强制开（覆盖配置）；`--preset <名字>` 启动前先导入数据包；`--preset-force` 允许覆盖 | 启动 `http://127.0.0.1:<port>`：默认取 `config.json` 的 `port`（8765），被占用时自动向后顺延并在日志打印实际地址 |
| `profile.py` | 无 | 打印主题倍率、关键词两端极值、被 Downvote 的论文 |
| `netroute.py` | `--forget` 清缓存重探；`--quick` 只列候选不探测 | 打印下载路由诊断结论 |
| `arxiv_cats.py` | 无 | 打印 20 个 archive / 155 个分类的概览，并自检每个分类号是否符合格式规则 |
| `paths.py` | 无 | 列出全部数据文件路径并标出是否已生成 |

## 二、维护与工具脚本（`tools/`）

### 配置与画像

| 脚本 | 参数 | 说明 |
| --- | --- | --- |
| `preset.py` | `list` / `show <名字>` / `import <名字>` / `export <名字>` / `status` | 数据包管理。`import` 默认导入 core + usage + notes，`--force` 才覆盖本机配置（先备份），`--with-learning` 加行为学习，`--dry-run` 只预演；`export` 默认只导出 core，`--with-usage/--with-learning/--with-notes` 扩展，`--keep-paths` 保留绝对路径。语义见 [数据包指南](../guide/presets.md) |
| `python paths.py` | 无 | 列出全部数据文件路径（含 `presets/`）并标出是否已生成 |

### 内容补全

| 脚本 | 参数 | 说明 |
| --- | --- | --- |
| `gen_pending.py` | `--limit N` 只取前 N 条；`--all` 不按本期过滤；`--len N` 摘要截取长度（默认 620，`--abs` 时 1200）；`--en` 改查「缺英文简介」；`--abs` 改查「缺中文摘要译文」 | 导出待补写清单到 `output/_pending.txt`，格式 `sid\|分类\|标题\|摘要片段`，按分数倒序 |

补写规则（key 一律 arXiv 短号），写完重跑 `recommend.py` 与 `build_report.py`：

- **简介**（`summaries.json`）：value 写 `{"en": "...", "zh": "..."}` —— 英文优先复用
  摘要里的原始句子（可适度微调），中文是它的对应译文；只写中文也没问题（英文缺失时
  页面会用摘要开头若干完整句子兜底）。旧的纯字符串 value 仍然可读：含汉字算中文、
  否则算英文。
- **摘要译文**（`abstracts_zh.json`）：value 是纯字符串，即英文完整摘要对应的中文译文，
  由「Abstract (CH)」按钮展示。

### 视频

| 脚本 | 参数 | 说明 |
| --- | --- | --- |
| `gen_video_data.py` | `--top 8`（推荐篇数）、`--expand 2`（扩展篇数）、`--out <路径>` | 生成 `reel/src/papers.json`；口播稿优先取 `output/video_notes.json` |
| `gen_narration.py` | `--voice`（默认 `zh-CN-YunxiNeural`）、`--papers`、`--notes`、`--outdir`、`--audio-json`、`--no-tts`、`--proxy` | 合成每段旁白，写 `reel/public/audio/*.mp3` 并把 `reel/src/audio.json` 的 `enabled` 置 `true`。出网路由默认自动（直连 → 环境代理 → 本机代理端口，逐条回退并记住成功的一条）；`--proxy` 可跳过探测直接指定 |
| `check_video_av.py` | `<video.mp4>`、`--papers N`（默认从 `papers.json` 读） | A/V 质量闸门：总时长、音轨、逐段人声起点、段内静音 |

完整流程见 [视频与投稿](../guide/video-pipeline.md)。

### B 站

| 脚本 | 参数 | 说明 |
| --- | --- | --- |
| `bili_tv_qr_login.py` | `--wait <秒>` | TV 通道扫码登录，写 `.secrets/bili_cookies.json`（**推荐**） |
| `bili_qr_login.py` | `--wait <秒>` | Web 通道扫码（拿不到 App `access_token`，仅排错用） |
| `bili_collection.py` | `videos` / `collections`（只读）；`cover` / `create` / `add` / `sync`（默认 dry-run，需 `--exec`） | 管理合集 `arXiv-daily`；`sync` 幂等，只补未挂载。判据用稿件详情的 `season_id`（绕过合集列表缓存），挂完回读校验。`code 20080` 是**整批级**拒绝，收到后逐条重投，不当整批成功 |
| `bili_upload.py` | 在 `.workbuddy/skills/bili-auto-upload/scripts/`；子命令 `check/meta/cover/upload/verify/comment`，`-d <期号>`，`--exec` 才真正执行；`--line <线路>` 指定上传线路（默认自动探测） | 投稿与投稿后对账。标题/标签由当期入选论文的分类推出（不再写死领域名） |

### 数据修复

| 脚本 | 用途 |
| --- | --- |
| `merge_raw_pool.py` | 把若干 feed 快照按短号**并集**合并回累积池（降级抓取把池子缩小后的补救） |
| `rebuild_raw_from_index.py` | 从 `output/papers_index.json` 反推重建 `raw.json` / `raw_expand.json` |
| `backfill_archive.py` | 把磁盘上已有的 `arxiv_digest_<日期>.md/.html` 回填进 `archive.db` |

### 回归测试 {#回归测试}

| 脚本 | 是否需要浏览器 | 验证什么 |
| --- | --- | --- |
| `concurrency_check.py` | 否（进程内起服务 + 桩化下载 + 临时库） | 下载中另一篇 Downvote 不被阻塞、批量并行、同一篇仍串行 |
| `dv_unify_check.py` | 是（Edge CDP） | 三处 Downvote 的 opacity / 删除线 / 不隐藏 / 可撤销 |
| `owner_ui_check.py` | 是（Edge CDP） | `/profile` 画像主来源的增删改（只用临时条目并清理） |
| `ui_file_check.py` | 是（Edge CDP） | 日报 HTML 以 `file://` 打开时的跨源交互与链接改写 |
| `dl_button_check.py` | 是（Edge CDP） | 真实点一次**已下载**论文的按钮：断言它是「打开本地文件」态（tooltip、done 类、toast 含「打开」），且期间没有再发 `/api/download`。副作用：会用系统阅读器打开一个 PDF |
| `fresh_clone_check.py` | 否（复制整棵源码树 + 真 HTTP，默认端口 8767） | **首次克隆验收**：引导页、空画像/空收藏、`/api/state` 全空、数据包视图只有形状、页面无私人痕迹、模板初值上一键导入成功 |
| `ui_probe.py` / `ui_shots.py` / `ui_final_check.py` / `ui_check_v3.py` | 是 | 开发期探针与截图留档，不属于发布闸门 |

跑法与结果解读见 [测试与回归](../contributing/testing.md)。

## 三、有定时需求的场景

```bash
# 每天 08:10 跑一次（Linux/macOS crontab）
10 8 * * * cd /path/to/arXiv-digest && python run_daily.py >> output/cron.log 2>&1
```

Windows 用任务计划程序，操作填 `python`，参数填 `run_daily.py`，
"起始于"填项目根目录（**必须**，否则相对路径会指向别处）。

注意：`run_daily.py` 结束时服务仍在后台运行（Windows 下用 `cmd /c start /b` 脱离进程树）。
它自己不会开浏览器（后台进程开浏览器是打扰），需要看页面就手动访问打印出来的地址。
端口被上一轮残留进程占用不会再导致失败：残留实例在线时直接复用，被别的程序占着则自动
顺延（`[port] 8765 已被占用，改用 8766`），最终地址以 `digest online: <url>` 为准，
也已写进 `output/server.json`。

---

相关：[HTTP API](http-api.md) · [config.json](config.md) · [架构总览](../architecture/overview.md)
