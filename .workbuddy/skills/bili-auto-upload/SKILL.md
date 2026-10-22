---
name: bili-auto-upload
description: 把本地生成的视频（如 arXiv 日报解读短片）连同标题、简介、标签、封面自动投稿到 bilibili（B站），并做投稿后对账读回。当用户说「把视频发到 B站」「自动投稿 bilibili」「上传 weekly 视频到 B站」「B站发布」时使用。依赖命令行投稿工具 biliup / biliup-rs，登录态用 cookie 文件，cookie 绝不入 git。
agent_created: true
---

# 视频自动投稿 bilibili

## 先说清一件事：官方 API 这条路走不通

bilibili 开放平台（`openhome.bilibili.com`）的投稿接口 `ARC_BASE` 要求 **企业资质 + 应用审核 + 实名认证**，
官方文档明确写着「暂未开通个人开发者的申请入驻」。所以个人或课题组只能走命令行投稿工具这条路。

本项目选定 **biliup-rs**（Rust 单文件二进制，MIT，扫码登录，支持多 P / 线路选择 / 并发 / 定时发布）：

```powershell
winget install --id ForgQi.biliup-rs --exact     # v0.2.4
```
或下载 `biliupR-v0.2.4-x86_64-windows.zip`。

**只对可比对的几条路负责**：bilibili-api-python（`video_uploader`）也能传，但遇验证码风控要人工过，
不如 biliup 稳，所以只作为「自动发评论 / 置顶」的补充依赖。

## 一次性准备（每个账号只做一次）

**首选：TV 通道扫码（无需终端）**

```powershell
python -X utf8 tools/bili_tv_qr_login.py --wait 280
# 生成 output/bili_qr_tv.png → B站 App 扫码并点「确认登录」→ 自动写 .secrets/bili_cookies.json
```

**为什么不能用 `biliup login`**：① 需要 TTY（无人值守/沙箱里直接拒绝）；② 只在进程正常退出时才落盘，
扫码后 Ctrl-C / 关窗 = 白扫；③ 最重要的——**biliup 的提交通道走 App 接口，必须要 `token_info.access_token`**。
普通 Web 扫码（cookie/info）换不来 access_token，手写 cookie 文件会在启动时的 SSO 交换环节收到
`-400 请求错误`。TV 通道（`passport-tv-login`，appkey `4409e2ce8ffd12b8`）一次返回
access_token + refresh_token + cookie_info，正好是 biliup 的 `LoginInfo` 结构。

**cookie = 完整登录凭据**，等同账号密码。放在 `.secrets/`（已被 `.gitignore` 覆盖）；
不要把 cookie 文件路径、SESSDATA、bili_jct 写进任何日志、提交或发给第三方的话术里。

## 平台字段硬限制（超了必失败）

| 字段 | 限制 | 本项目取值 |
|---|---|---|
| `title` | ≤ 80 字 | `arXiv 日报 20261002｜DB·分布式·形式化 Top10 速览` |
| `desc` | ≤ 250 字 | 引导语 + 尽可能多的论文短链 + 「其余见置顶评论」 |
| `tag` | 逗号分隔，总长 < 200 | `arXiv,论文速递,分布式系统,数据库,形式化方法,论文解读,计算机科学` |
| `tid` | 分区 id | `171` = 知识·野生技术协会 |
| `copyright` | 1 自制 / 2 转载（转载必填 source） | `1` |
| `--dtime` | 定时发布，需距今 > 4 小时 | 一般不设；要定时再显式给 |

**为什么「10 篇论文链接」放不进简介**：`arxiv.org/abs/2610.00896` 一条 26 字符，10 条就是 270 字，
超过 250 字上限。所以脚本按「优先塞满简介 → 剩余走置顶评论」的策略输出，不会硬截断到丢链接。

## 「可点击链接」的正确打开方式

MP4 容器本身**不能承载超链接** —— 这一点要在画面里对用户说明白，不能假装视频能点。
真正可点击的位置只有三处：

1. **视频简介区**（B站会把 URL 渲染成可点链接）—— 主阵地，脚本自动生成。
2. **置顶评论** —— 承接简介放不下的部分，用 bilibili-api-python 发并置顶。
3. **视频画面内的链接文字** —— 只是给人看 / 手输用的，`PaperReel.tsx` 每行出处有这行。

画面上那句「可点击链接见视频简介」就是为此服务的引导。

## 命令

脚本：`scripts/bili_upload.py`（位于本仓库 `.workbuddy/skills/bili-auto-upload/scripts/`，用 `python <路径>` 调用即可）。

```powershell
python bili_upload.py check                     # 环境体检：biliup / ffmpeg / cookie / 产物
python bili_upload.py meta                      # 生成投稿元数据 → output/bili_meta_<date>.json
python bili_upload.py cover                     # ffmpeg 抽封面 → output/bili_cover_<date>.jpg
python bili_upload.py upload                    # dry-run：只打印将执行的命令，不真投
python bili_upload.py upload --exec             # 真投稿
python bili_upload.py verify                    # 对账：查 member 稿件列表，确认 BV 号与状态
python bili_upload.py comment                   # 打印将发的置顶评论稿
python bili_upload.py comment --exec            # 发评论并置顶（纯 requests，含防重复）
```

评论/对账已改为纯 `requests` 实现（不再依赖 bilibili-api-python——v17 缺 `set_comment_top`，
且列表接口在我们的代理环境不稳定）。评论带防重复：先查自己名下有没有「论文链接清单」，
有就直接置顶不重发。

默认 `--date` 取当天；可对历史期补投 `--date 20261002`。

## 流程编排

```
check → meta → cover → upload (先 dry-run 核对) → upload --exec → verify → comment --exec → collect
```

每一步都可独立重跑，`upload` 默认 dry-run 是**故意的** —— 对外发布不可逆，默认值必须安全。

## 合集（season）管理 —— arXiv-daily

**规则（用户硬要求）**：所有 arXiv-daily 视频——已上传的 + 未来每次投稿的——都归入 B站合集「arXiv-daily」。

B站里合集叫 **season**，接口在 `member.bilibili.com/x2/creative/web/season/*`。管理脚本独立于 `bili_upload.py`：

```
python tools/bili_collection.py videos        # 列出 member 稿件中「arXiv 日报」前缀视频（只读）
python tools/bili_collection.py collections   # 列出已有合集（只读）
python tools/bili_collection.py cover         # 生成封面 PNG→JPG 并上传图床，打印 URL
python tools/bili_collection.py sync          # dry-run：预览将新建/挂载哪些视频
python tools/bili_collection.py sync --exec   # 建合集(若不存在)+ 挂载所有未挂载的匹配视频
```

`create` / `add` / `sync` 默认 dry-run，**必须 `--exec` 才真正写 B站**。脚本幂等：`sync` 只补未挂载的视频，已挂载的自动跳过，可每次投稿后无脑重跑。

**已建合集（2026-10-17）**：`season_id=9343347`，默认小节「正片」`section_id=10455435`，封面 `https://archive.biliimg.com/bfs/archive/acbddc1265c5c8ddac0c07d53545fd4fede505b8.jpg`。截至 2026-10-22 已挂 6 期（20261002/1006/1009/1014/1020/1022）。

**判重与校验（2026-10-22 修正，务必照此）**：
- **真值看稿件详情**：`x/web-interface/view?aid=<aid>` 的 `data.season_id`（或 `data.ugc_season.id`）等于 `9343347` 才算已挂载。member 的 `seasons` 列表是 CDN 缓存快照，会漏新条目。
- **`code 20080` 是整批级拒绝**：批次里只要有一条已在合集，服务端就回 20080 且**整批都不挂**。批量时不能当成功，要逐条重投（脚本已实现）。曾因此静默丢稿：`sync` 报成功但 `BV1yQn16oEb3` 的 `season_id` 一直是 `None`。
- **挂完必须回读校验**：`view` 接口也有缓存（数十秒），所以重试 5 次×3s；仍不归属就非零退出。

**两个接口坑（2026-10-17 实测）**：
- 封面上传 `POST /x/vu/web/cover/up`：**不是 multipart**，必须 `Content-Type: application/x-www-form-urlencoded`，正文 `csrf` + `cover=data:image/jpeg;base64,<bytes>`（带 data URI 前缀），URL 带 `ts=毫秒时间戳`。用 multipart 的 `file` 字段会报 `-400 请求错误`。
- 建合集 `POST /x2/creative/web/season/add` 必填 `cover`（图床 URL）、`csrf`，且**触发人工审核**（state -6，通常很快过）；默认自动生成「正片」小节。
- 加视频 `POST /x2/creative/web/season/section/episodes/add?csrf=...` 需 `sectionId` + 每集 `aid`/`cid`（cid 取自 `x/web-interface/view?aid=`）。

**未来自动投稿**：自动化 `af055043`（prompt v9）在 `bili_upload.py verify` 成功后追加 `python tools/bili_collection.py sync --exec`，把新视频挂进合集。

## 已知坑

- **`-400 请求错误`（秒退，连视频都没传）** = cookie 文件缺 `token_info.access_token`。
  biliup 提交走 App 接口，Web 扫码换不来 token → 用 `tools/bili_tv_qr_login.py` 重新登录即可。
- **`code 601 您上传视频过快`** = 账号侧临时频控，不是脚本 bug。等几分钟原命令重投即可，
  **不要改参数硬刷**。新号 / 小号（默认 `bili_数字` 用户名）频控更严，两条之间留间隔。
- winget 安装后可能留下 0 字节的 `WinGet\Links\biliup.exe` 空壳导致 PowerShell 报
  「不是此 OS 平台的有效应用」；脚本已内置 `_is_pe()` 校验 + `repair_winget_link()` 自愈。
- 封面不传也可以，B站会自动生成；但抽帧封面可控性更好，建议传。
- 非官方对接会随 B站接口变更失效。失效时先看 `biliup upload` 的原始报错，再查
  `SocialSisterYi/bilibili-API-collect` 社区文档。
- 跑 `upload --exec` 是**对外不可逆动作**：不确定就停在 dry-run，或先 `--dtime` 定时给自己留撤回窗口。

## 安全边界

- cookie 文件路径默认落在项目 `.secrets/`，脚本启动时校验它不在 git 版本控制内，若已入库会直接报错提示。
- 任何命令都不得 `git add` cookie 文件、不得把 SESSDATA / bili_jct 打进日志。
- `verify` 只读不写；`comment --exec` 会向稿件追加一条评论，属于对外写操作，需显式 `--exec`。
