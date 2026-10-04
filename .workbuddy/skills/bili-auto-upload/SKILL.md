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

```powershell
mkdir -p "D:/code-repo/coworkers/git-paper/arXiv/.secrets"
biliup -u "D:/code-repo/coworkers/git-paper/arXiv/.secrets/bili_cookies.json" login
```

- `-u` **必须显式给固定路径**。不给的话 cookie 会写进「当前工作目录」的 `cookies.json`，
  下次换个目录跑脚本就找不到登录态了 —— 这是最常见的翻车点。
- 手机 B 站 App 扫码后**必须点「确认登录」**，只扫不确认不算数。
- **cookie = 完整登录凭据**，等同账号密码。放在 `.secrets/` 并确保已进 `.gitignore`；
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

脚本：`scripts/bili_upload.py`（项目 git 根 `D:/code-repo/coworkers` 下的 `git-paper/arXiv/.workbuddy/skills/bili-auto-upload/scripts/`）。

```powershell
python bili_upload.py check                     # 环境体检：biliup / ffmpeg / cookie / 产物
python bili_upload.py meta                      # 生成投稿元数据 → output/bili_meta_<date>.json
python bili_upload.py cover                     # ffmpeg 抽封面 → output/bili_cover_<date>.jpg
python bili_upload.py upload                    # dry-run：只打印将执行的命令，不真投
python bili_upload.py upload --exec             # 真投稿
python bili_upload.py verify                    # 对账：查 member 稿件列表，确认 BV 号与状态
python bili_upload.py comment                   # 打印将发的置顶评论稿
python bili_upload.py comment --exec            # 发评论并置顶（需 bilibili-api-python）
```

默认 `--date` 取当天；可对历史期补投 `--date 20261002`。

## 流程编排

```
check → meta → cover → upload (先 dry-run 核对) → upload --exec → verify → comment --exec
```

每一步都可独立重跑，`upload` 默认 dry-run 是**故意的** —— 对外发布不可逆，默认值必须安全。

## 已知坑

- **`code 601 您上传视频过快`** = 账号侧临时频控，不是脚本 bug。等几分钟原命令重投即可，
  **不要改参数硬刷**。新号 / 小号（默认 `bili_数字` 用户名）频控更严，两条之间留间隔。
- 封面不传也可以，B站会自动生成；但抽帧封面可控性更好，建议传。
- 非官方对接会随 B站接口变更失效。失效时先看 `biliup upload` 的原始报错，再查
  `SocialSisterYi/bilibili-API-collect` 社区文档。
- 跑 `upload --exec` 是**对外不可逆动作**：不确定就停在 dry-run，或先 `--dtime` 定时给自己留撤回窗口。

## 安全边界

- cookie 文件路径默认落在项目 `.secrets/`，脚本启动时校验它不在 git 版本控制内，若已入库会直接报错提示。
- 任何命令都不得 `git add` cookie 文件、不得把 SESSDATA / bili_jct 打进日志。
- `verify` 只读不写；`comment --exec` 会向稿件追加一条评论，属于对外写操作，需显式 `--exec`。
