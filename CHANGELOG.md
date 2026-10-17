# 变更记录

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
本项目尚未打版本号，因此以**日期**作为节标题；日期为提交日期（Asia/Shanghai）。

分类：`新增` / `变更` / `修复` / `文档` / `移除`。

---

## [未发布]

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

[未发布]: https://github.com/0xaiio/arXiv-digest/commits/main
