# 视频与投稿（可选）

把当期日报渲染成一段带中文旁白的横屏视频，并可自动投稿到 B 站。**整条链路是可选的**——
不装任何额外依赖也不影响日报本身。

视频用 **Remotion 代码渲染**（React 组件逐帧生成），不是生成式视频：画面内容、出现顺序、
时长都由数据决定，可复现、可校对。旁白用 **Edge TTS** 合成，画面与音频分段对齐。

---

## 一、链路总览

```
output/recommend.json ─┐
output/issue_core.json ├─▶ tools/gen_video_data.py  ──▶ reel/src/papers.json
output/summaries.json  │      （选片 + bullets + 口播稿）
output/video_notes.json┘
                                     │
                                     ▼
                          tools/gen_narration.py ──▶ reel/public/audio/*.mp3 + reel/src/audio.json
                                     │
                                     ▼
                     cd reel && npx remotion render ... ──▶ reel/out/arxiv-weekly.mp4
                                     │
                                     ▼
                          tools/check_video_av.py ──▶ 通过 / 报错
                                     │
                                     ▼
            .workbuddy/skills/bili-auto-upload/scripts/bili_upload.py ──▶ BV 号
                                     │
                                     ▼
                          tools/bili_collection.py sync ──▶ 归入合集
```

## 二、依赖

| 依赖 | 用途 | 安装 |
| --- | --- | --- |
| Node 18+ | Remotion 渲染 | 系统安装 |
| `reel/node_modules` | Remotion 与 React | `cd reel && npm ci` |
| `edge-tts` | 中文旁白合成 | `pip install -U edge-tts` |
| `imageio-ffmpeg` | 提供 ffmpeg/ffprobe 二进制 | `pip install imageio-ffmpeg` |
| `biliup-rs` | 上传视频到 B 站 | `winget install --id ForgQi.biliup-rs --exact` |

规格固定为 1920×1080 / 30fps；结构是 5 秒片头 + 每篇 20 秒 + 5 秒片尾，
10 篇时成片约 210 秒。

## 三、生成数据与文案

```bash
python tools/gen_video_data.py --top 8 --expand 2
```

- `--top 8`：取「为你推荐」前 8 篇；`--expand 2`：追加「兴趣扩展」前 2 篇（短号去重）。
  默认值就是 8 / 2，共 10 篇；
- 输出 `reel/src/papers.json`，包含标题（英文原题，不做机器翻译）、作者、分类、评分、
  中文摘要与画面要点；
- **文案优先取 `output/video_notes.json`**：那里可以按短号写人工解读，把"画面 bullets"
  与"口播 narration"分开。没有人工稿时，从中文摘要自动切分要点（中性编号标签，
  不做"方法/结论"之类的语义断言）。

要写人工口播稿，按这个结构：

```jsonc
{
  "_intro":  { "narration": "片头口播，约 20 字" },
  "_outro":  { "narration": "片尾口播，约 20 字" },
  "2610.17697": {
    "bullets":   ["画面上的三条要点", "每条尽量短", "必须能在摘要里找到依据"],
    "narration": "口播稿，长度见下方约束"
  }
}
```

**口播字数上限**是硬约束：每段音频必须短于对应的 20 秒画面，否则会被质量闸门拦下。
经验做法是先按 `0.9 × 150 字` 落笔，跑一轮再按实测语速修正——不同篇目（英文词、数字多少）
语速差异可达 20%。

## 四、合成旁白

```bash
python tools/gen_narration.py                    # 生成全部音轨 + 更新 reel/src/audio.json
python tools/gen_narration.py --no-tts           # 只生成稿件，不调用 TTS（先审稿）
python tools/gen_narration.py --voice zh-CN-YunxiNeural
```

要点：

- 每段一条独立音轨，与画面分段严格对齐；语速自适应，输出前做 loudnorm（-16 LUFS）；
- **渲染前必须确认 `reel/src/audio.json` 的 `enabled` 为 `true`**。该文件入库基线是 `false`
  （否则新克隆的仓库渲染会因找不到 mp3 而 404 失败），生成音频后脚本会自动置 `true`；
- 若 TTS 报 `403 WSServerHandshakeError`：先升级 `edge-tts`（旧版本签名被服务端拒绝），
  再怀疑网络。

## 五、渲染

```bash
cd reel
npx remotion render src/index.ts PaperReel out/arxiv-weekly.mp4
```

路径是**相对 `reel/` 目录**的（在 `reel/` 下写 `out/arxiv-weekly.mp4`）。
渲染前建议抽帧核对版面，特别是要点是否完整进场：

```bash
npx remotion still src/index.ts PaperReel out/f1.png --frame=660
```

抽帧要取**段落末尾**（要点在段内 4–10 秒陆续入场），取段首会误判成"要点缺失"。

## 六、质量闸门

```bash
python tools/check_video_av.py reel/out/arxiv-weekly.mp4
```

它检查四件事：

| 检查 | 失败含义 |
| --- | --- |
| 总时长 | 与「片头 + 20×篇数 + 片尾」的预期不符 |
| 音轨存在且非静音 | `audio.json` 没开，或 TTS 没跑 |
| 逐段人声起点 | 某段旁白起始与画面不同步 |
| 段内静音 > 3 秒 | 口播太短，片尾会残留静音 |

## 七、投稿到 B 站

投稿脚本在 `.workbuddy/skills/bili-auto-upload/scripts/bili_upload.py`，**默认 dry-run**，
只有加 `--exec` 才产生对外副作用：

```bash
python .../bili_upload.py check    -d <期号>          # 检查环境、登录态、视频文件
python .../bili_upload.py meta     -d <期号>          # 生成标题/简介/标签，人工审
python .../bili_upload.py cover    -d <期号>          # 生成封面
python .../bili_upload.py upload   -d <期号>          # 预览命令（不执行）
python .../bili_upload.py upload   -d <期号> --exec   # 真正投稿
python .../bili_upload.py verify   -d <期号>          # 读回 BV 号，确认 state=0
python .../bili_upload.py comment  -d <期号> --exec   # 发并置顶论文链接清单
```

约束与经验：

- **登录必须走 TV 通道扫码**：`python tools/bili_tv_qr_login.py --wait 280`，二维码在
  `output/bili_qr_tv.png`。普通 Web 扫码拿不到 App 接口需要的 `access_token`，会以 `-400` 失败；
- cookie 等同账号密码，落在 `.secrets/bili_cookies.json`（`.gitignore` 已覆盖），
  **绝不写进日志、提交或外发**；
- 标题 ≤ 80 字、简介 ≤ 250 字、标签总长 < 200；`--tid 171`（知识·野生技术协会）、
  `--copyright 1`（自制）；
- 报 `code 601 您上传视频过快` 是账号侧频控：冷却几分钟用原命令重投，**不要改参数硬刷**。

## 八、归入合集

```bash
python tools/bili_collection.py sync --exec
```

把本期视频挂进 B 站合集 `arXiv-daily`（幂等：只补未挂载的，已挂载的跳过）。
`videos` / `collections` 子命令是只读查询；`create` / `add` / `sync` 不带 `--exec` 时只打印计划。

> 合集列表接口有短暂缓存：刚挂载完立刻重跑 `sync`，本地判重可能仍看不到新条目，
> 于是再发一次挂载请求，B 站返回 `code 20080 当前稿件已存在在合集中`。
> 这不代表失败——脚本已把 20080 按**幂等成功**处理；稿件仍在审核（cid 未生成）时会先
> `取不到 cid，跳过`，等转码完成后再跑一次即可。

## 九、典型问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 成片没有旁白 | `reel/src/audio.json` 的 `enabled` 仍是 `false` | 重跑 `gen_narration.py`，确认置 `true` 后重新渲染 |
| 渲染报 404 | 引用了 `reel/public/audio/*.mp3` 但文件不存在 | 同上 |
| 闸门报「段内静音 > 3s」 | 该段口播太短 | 补写 `video_notes.json` 的 `narration` |
| 闸门报「总时长不符」 | 篇数与 `--top/--expand` 不符（如只写 `--top 5`） | 显式写全 `--top 8 --expand 2` |
| 上传 `-400 请求错误` | 用 Web cookie 冒充 App 登录态 | 走 TV 扫码重新登录 |

---

相关：[命令行参考](../reference/cli.md) · [模块职责](../architecture/modules.md) ·
[故障排查](../operations/troubleshooting.md)
