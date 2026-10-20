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

组合示例：

```bash
python run_daily.py --skip-fetch --skip-affil      # 只推荐 + 渲染，通常几秒
python run_daily.py --no-serve                     # 只出文件
```

失败行为：抓取步骤若未产出有效数据，会保留上一期文件（坏输出另存 `*.bad_<时间戳>`）；
若连历史数据都没有，则跳过推荐与渲染并直接返回，不会把已有日报清空。

`categories` 为空（通用版首次运行）时**不抓取任何东西**：打印「尚未选择任何 arXiv 分类」
与两条下一步（去 `/profile` 选，或用 `--categories`），并在未加 `--no-serve` 时把本地服务拉起来，
好让引导页可访问。

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
| `server.py` | `--no-open` 不自动开浏览器 | 启动 `http://127.0.0.1:<port>`（端口取 `config.json`） |
| `profile.py` | 无 | 打印主题倍率、关键词两端极值、被 Downvote 的论文 |
| `netroute.py` | `--forget` 清缓存重探；`--quick` 只列候选不探测 | 打印下载路由诊断结论 |
| `arxiv_cats.py` | 无 | 打印 20 个 archive / 155 个分类的概览，并自检每个分类号是否符合格式规则 |
| `paths.py` | 无 | 列出全部数据文件路径并标出是否已生成 |

## 二、维护与工具脚本（`tools/`）

### 配置与画像

| 脚本 | 参数 | 说明 |
| --- | --- | --- |
| `preset.py` | `list` / `import <名字> [--force]` / `export <名字>` | 预设的查看、导入（默认拒绝覆盖，`--force` 先备份）、导出。`import hengxin` 会带进来那套 6 分类个人示例配置 |

### 内容补全

| 脚本 | 参数 | 说明 |
| --- | --- | --- |
| `gen_pending.py` | `--limit N` 只取前 N 条；`--all` 不按本期过滤；`--len N` 摘要截取长度（默认 620） | 导出「缺中文摘要」清单到 `output/_pending.txt`，格式 `sid\|分类\|标题\|摘要片段`，按分数倒序 |

补充的中文摘要写回 `output/summaries.json`（key 为 arXiv 短号，value 是**纯字符串**），
然后重跑 `recommend.py` 与 `build_report.py`。

### 视频

| 脚本 | 参数 | 说明 |
| --- | --- | --- |
| `gen_video_data.py` | `--top 8`（推荐篇数）、`--expand 2`（扩展篇数）、`--out <路径>` | 生成 `reel/src/papers.json`；口播稿优先取 `output/video_notes.json` |
| `gen_narration.py` | `--voice`（默认 `zh-CN-YunxiNeural`）、`--papers`、`--notes`、`--outdir`、`--audio-json`、`--no-tts` | 合成每段旁白，写 `reel/public/audio/*.mp3` 并把 `reel/src/audio.json` 的 `enabled` 置 `true` |
| `check_video_av.py` | `<video.mp4>`、`--papers N`（默认从 `papers.json` 读） | A/V 质量闸门：总时长、音轨、逐段人声起点、段内静音 |

完整流程见 [视频与投稿](../guide/video-pipeline.md)。

### B 站

| 脚本 | 参数 | 说明 |
| --- | --- | --- |
| `bili_tv_qr_login.py` | `--wait <秒>` | TV 通道扫码登录，写 `.secrets/bili_cookies.json`（**推荐**） |
| `bili_qr_login.py` | `--wait <秒>` | Web 通道扫码（拿不到 App `access_token`，仅排错用） |
| `bili_collection.py` | `videos` / `collections`（只读）；`cover` / `create` / `add` / `sync`（默认 dry-run，需 `--exec`） | 管理合集 `arXiv-daily`；`sync` 幂等，只补未挂载（`code 20080` 视为已挂载成功） |
| `bili_upload.py` | 在 `.workbuddy/skills/bili-auto-upload/scripts/`；子命令 `check/meta/cover/upload/verify/comment`，`-d <期号>`，`--exec` 才真正执行 | 投稿与投稿后对账 |

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
| `dl_button_check.py` | 是（Edge CDP） | 真实点一次下载按钮，断言 toast 与按钮态 |
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
若由调度器每天拉起，先确认端口未被上一轮的残留进程占用。

---

相关：[HTTP API](http-api.md) · [config.json](config.md) · [架构总览](../architecture/overview.md)
