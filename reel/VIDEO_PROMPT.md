# arXiv Weekly 论文解读视频 · 制作提示词（v2.1：10 篇 · 20s/篇 + 中文语音讲解）

> 适用范围：定时任务 `af055043`（arXiv cs.\* 论文日报）的「额外制作视频」步骤。
> 与「AI 周报速递」这类新闻短视频的关键差别：**论文不能被 3 秒带过**。
> 一条新闻可以只播标题，一篇论文至少要交代「背景 → 方法 → 结果」。
> v2 相对 v1 的两处实质改动：**单篇 12s → 20s**、**从无音轨 → 中文语音讲解**。
> v2.1（2026-10-02）：**篇数 5 → 10**，构成改为「🎯 为你推荐前 8 + 🌱 兴趣扩展前 2」。

## 0. 目标与硬规格

| 项 | 值 |
|---|---|
| 分辨率 / 帧率 | **1920×1080 / 30fps**，H.264 + AAC |
| 时长 | 片头 **5s** + **每篇 20s** + 片尾 **5s**；10 篇 = **210.60s（6318 帧）** |
| 音轨 | **中文语音讲解**（Edge TTS），每段一条独立 mp3，起始帧与画面段严格对齐 |
| 篇数 | **10 篇** = `recommend.json` 按匹配度排序的**本期推荐前 8**（`--top 8`）+ **兴趣扩展前 2**（`--expand 2`） |
| 渲染方式 | **Remotion 代码渲染**（`reel/` 工程），不用文生视频模型 |

**为什么必须用代码渲染而不是文生视频**：

1. 论文英文原题、arXiv 号、中文要点必须**逐字准确**；生成式视频模型无法保证文字正确，学术论文视频一旦把编号或术语渲染错，整条片子失去价值。
2. 时长、帧率、每段的入场时机必须**精确可控**（要写成不变量进校验）。
3. 这是**每周重复执行**的流水线产物，必须是确定性的、可回归的，而不是每次抽样碰运气。

**为什么「论文 20s」是下限**：三条要点要在屏幕上读完并理解，中文阅读约需 6–8 字/秒；一条 30 字要点留给观众的时间不应少于 8 秒。
20s 的分法是：0–3s 识别信息（类别 / 编号 / 原题 / 作者），4.1s / 7.1s / 10.1s 三条要点依次出现，
最后一条要点在切走前仍有约 10 秒停留，配合 16–18.5s 的旁白，阅读与听讲互不抢资源。

**时长随篇数自动伸缩**：`DURATION = INTRO(150) + N*PAPER(600) + XFADE(18) + OUTRO(150)`。
5 篇 = 3318 帧 / 110.60s，10 篇 = **6318 帧 / 210.60s**。`check_video_av.py` 从 `papers.json` 读篇数，无需硬编码。
唯一需要人工兜底的是**片尾的 arXiv 号清单**：10 个号单行排版会超过 1920px 被裁切，
`PaperReel.tsx` 已按 `SID_PER_ROW = 5` 折行。

## 1. 数据准备（一切事实来自本地产物，禁止凭空生成）

1. 先完成日报流水线（抓取 → 推荐 → 渲染 → 确保 8765 在线）。
2. 生成数据：`python tools/gen_video_data.py --top 8 --expand 2` → `reel/src/papers.json`。
   **注意 `--top` 默认 8、`--expand` 默认 2，两个参数都要显式写**：
   `--top 8 --expand 2` → 10 篇（本规格）；`--top 5 --expand 0` → 5 篇（旧规格）；
   只写 `--top 5` 不写 `--expand` 会**误得 7 篇**，切勿如此。
   字段来源：`recommend.json`（排名 / 分数 / 题名 / 作者）、`issue_core.json`（期号 / 统计 / 回溯窗口）、
   `affiliations.json`（单位）、`summaries.json`（中文摘要）。
3. **必须为每篇人工撰写 `output/video_notes.json`**（10 篇 = 10 个短号条目 + `_intro` / `_outro`）：

   ```json
   {
     "_intro": { "narration": "……（≤ 20 字）" },
     "_outro": { "narration": "……（≤ 20 字）" },
     "2609.32972": {
       "kw": ["Multi-Paxos", "Raft", "RoundTick"],
       "narration": "……（口播稿，约 75–90 字）",
       "bullets": [
         {"tag": "背景", "text": "……（≤80 汉字）"},
         {"tag": "方法", "text": "……"},
         {"tag": "结果", "text": "……"}
       ]
     }
   }
   ```

   - **画面要点**（`bullets`）：三条，标签固定 `背景 / 方法 / 结果`；每条 ≤ 80 汉字，必须**能追溯到英文摘要**，摘要没说的不要写。
   - **口播稿**（`narration`）：另写一段，见第 2 节——**严禁把 `bullets` 原句串起来**。
   - `kw` 取**在中文文案里真实出现过**的英文技术词（2–4 个），用于强调色高亮；不要编造高亮词。
   - 语义归属拿不准时，用中性标签 `要点 1 / 要点 2 / 要点 3`，不要硬套「方法 / 结论」。
   - 缺 notes 时生成器会退化成「英文摘要首句」——**那种产物不可交付**，必须先补 notes。
4. 再跑一次 `gen_video_data.py` 使 notes 生效（每次改 `video_notes.json` 后都要重跑）。

## 2. 语音讲解（TTS）

### 2.1 技术方案

**Edge TTS**（免费、中文自然度高），默认音色 **`zh-CN-YunxiNeural`**（阳光男声，偏轻松活泼）。
备选：`zh-CN-XiaoxiaoNeural`（温暖女声）、`zh-CN-XiaoyiNeural`（更活泼）。
脚本：`tools/gen_narration.py`；依赖装在 WorkBuddy **默认 venv** 里：

```bash
python -m pip install edge-tts imageio-ffmpeg
python -X utf8 tools/gen_narration.py
```

产出：`reel/public/audio/{intro,p1..p10,outro}.mp3` + `reel/src/audio.json`（每段时长与语速）。

**响度归一化**：Edge TTS 原始输出偏轻（整段 mean_volume 实测 ≈ −27dB，笔记本扬声器上要调大音量才听清）。
合成后脚本用 ffmpeg `loudnorm` 统一归一到 **−16 LUFS / 峰值 −1.5 dBTP**（网络视频通用响度），
归一化后每段 mean_volume ≈ −18dB；失败则保留原始音频并告警，不阻断流程。

**瞬时故障重试**：Edge TTS 会偶发 `NoAudioReceived`（服务端抽风，与稿件内容无关）。
篇数 5 → 10 后单轮要打 **12 次**接口，命中概率显著上升；`run_synth()` 已内置 3 次重试（1.5s / 3s 退避）。
三次仍失败才整轮报错——此时如实报告「本轮未产出旁白」，不要伪造产物。

### 2.2 稿件写作准则（这是质量的核心）

- **口语化转述，不是朗读幻灯片**。屏幕上写「服务实现解耦」，嘴里要说「而且完全不碰服务内部实现」。
- **可以补充画面没写的连接与评价**：「换句话说」「值得注意的是」「作者的思路很取巧」「这个结论有点反直觉」。
- 数字与符号一律改成口语读法：`N=5` →「N 等于五」、`5%→100%` →「百分之五飙到百分之百」、`24 字节` →「二十四字节」。
  脚本里的 `to_speech()` 会自动做这层转换，但**人工撰稿时直接写口语更自然**。
- **长度**：每篇 **75–90 字**；脚本计数含标点，实测 **96–120 字**时刚好贴合 18.6s 目标；片头 / 片尾 **≤ 20 字**。
  基准：`zh-CN-YunxiNeural` 约 4.8 字/秒，语速调整被限制在 `-12% ~ +25%`。
  写超了脚本会一路加到 `+25%` 上限并打印 `[warn] 超出 X 秒`——**那是必须回头精简稿件的信号**，
  不要靠加速掩盖（10 篇里通常有 3–4 篇会写超，写完先看 `[warn]` 再定稿）。
- **语气**：轻松活泼、自然流畅，**不用正式播音腔**；可以设问（「结果怎么样？」）、可以用口语词（「反过来」「一口气」）。

### 2.3 音画同步机制

- **画面主控，音频服从画面**：每段画面长度固定（片头 150f / 每篇 600f / 片尾 150f），
  音频只会比所在的段**短**（脚本用 `SEGMENT_BUDGET_SEC = {intro: 4.2, paper: 19.0, outro: 4.2}` 硬性约束，
  并为交叉淡出留 ~0.8s 余量）。因此不存在「音频撑长分段」或跨段累积漂移。
- Remotion 侧 `<Voice id start>` 把 mp3 放在各段起始帧，首尾各做 5 / 10 帧淡入淡出避免爆音。
- **片尾旁白提前 30 帧（1s）进入**（`OUTRO_LEAD`）：最后一篇讲完到片尾开场之间本来会留下 ~3s 空档，
  观感像卡住了；让片尾的话叠在最后一张卡的淡出上（标准 voice lead-in），空档降到 ~1s。
- 脚本先以常速合成一次测出基准时长，再解析地把语速贴到 `SEGMENT_TARGET_SEC`
  （每篇 18.6s），只在 `-12% ~ +25%` 区间内调整；仍超预算才继续加速并打印 `[warn] 超出 X 秒`。
- **缺 generated audio 时静默降级**：`audio.json` 的 `enabled=false` 会让 `reel/src/PaperReel.tsx` 跳过全部音轨，
  仍渲染出无旁白版本，不会构建失败。

## 3. 视觉与动效规范

- **配色**：背景纯深色 `#05070A`，正文 `#FFFFFF`，要点正文 `#E6EDF5`，次级 `#C3CEDA`，弱化 `#7C8896`；
  强调色**只用一种** `#00D4FF`（类别、arXiv 号、关键词、匹配度徽章、时间线节点、要点标签芯片）。
- **字体**：系统栈 `'Segoe UI','Microsoft YaHei','PingFang SC'`；等宽 `'Cascadia Mono','Consolas'`。
  不使用 `@remotion/google-fonts`（渲染期不联网）。
- **片头 5s（150f）**：kicker `ARXIV · CS.* DIGEST`（等宽、字距 8、强调色）淡入 →
  主标题 `arXiv Weekly`（156px/900）以 spring（`damping 13 / mass 0.9 / stiffness 92`）从上方 **−280px 弹入** →
  强调色进度条随同一 spring 展开到 560px → 期号与区间（delay 34f）、三项统计（delay 52f）依次上浮。
- **每篇 20s（600f）**，元素错峰从左侧 −56px spring 滑入，**delays 按 20s 节奏放宽**：

  | 元素 | delay（帧 @30fps） | 出现时刻 |
  |---|---|---|
  | meta 行（类别 / arXiv 号 / 匹配度） | 6 | 0.2s |
  | 英文原题 | 26 | 0.9s |
  | 作者 | 62 | 2.1s |
  | 🏛 单位 | 82 | 2.7s |
  | 分隔线（淡入区间 96→122） | — | 3.2→4.1s |
  | 要点 1 / 2 / 3 | 124 / 214 / 304 | 4.1 / 7.1 / 10.1s |
  | 页脚 `arxiv.org/abs/<sid>` | 430 | 14.3s |

  - 右上巨型序号水印（200px/900，白 4.5% 透明；**`right` 必须 ≥ 132**，否则被右边缘裁切）；序号 `01`–`10` 随篇数自增
  - **英文原题**（52px/800）——真实可核实，不做机器翻译
  - 作者（含 `等 N 人`）+ `🏛` 单位（最多 2 家 + `等 N 家单位`）
  - 分隔线 + 三条中文要点（标签芯片 + 31px 正文，关键词染强调色）
  - 页脚 `arxiv.org/abs/<sid>`
- **左侧竖向时间线**（y 250→880）：底线 + 渐变进度线随播放上行；当前节点用 spring
  （`damping 11 / stiffness 190`）弹亮并带 26px 光晕，已播节点半亮，未播为描边；左侧标 `01`–`10`
  （间距按 `(RAIL_BOT - RAIL_TOP) / (N - 1)` 自适应，10 篇时约 70px，不会挤在一起）。
- **转场**：相邻段落 18 帧交叉淡入淡出，**禁止硬切**；片头/片尾同样与正文交叉淡入淡出。
- **片尾 5s（150f）**：`关注获取更多`（112px/900）呼吸动画
  `scale = 1 + 0.032·sin(2π·t/2.4)`、光晕 `20 + 12·sin(2π·t/2.4)`，周期 2.4s；
  下方给出更新节奏（每周二 / 周五 23:10）与本片 **10 个 arXiv 号（按 `SID_PER_ROW = 5` 折成两行）**。
- **实现禁令**：禁用 CSS `transition` / `animation`，一律 `useCurrentFrame()` + `interpolate` / `spring`
  并带 `extrapolateLeft/Right: "clamp"`。

## 4. 渲染与交付

```bash
# 解释器必须是默认 venv（edge-tts 装在那里）
set PY="python"

%PY% -X utf8 tools/gen_video_data.py --top 8 --expand 2  # -> reel/src/papers.json（10 篇）
%PY% -X utf8 tools/gen_narration.py                      # -> reel/public/audio/*.mp3 + reel/src/audio.json

cd reel
npm install --registry=https://registry.npmmirror.com --no-audit --no-fund   # 仅首次，约 250 包
npm run compositions                                                          # 确认 30fps/1920x1080/帧数（10 篇应为 6318）
npm run still  -- --frame=200                                                 # 抽静帧看版面（可选）
npm run render                                                                # -> out/arxiv-weekly.mp4
npx --no-install remotion ffprobe out/arxiv-weekly.mp4                        # 权威校验：时长 / 分辨率 / 音轨

cd ..
%PY% -X utf8 tools/check_video_av.py reel/out/arxiv-weekly.mp4                # A/V 质量闸门（必须全绿）
```

- Chrome Headless Shell 下载失败时，加 `--browser-executable "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"`。
- 渲染完成后重命名到 `output/arxiv_weekly_<YYYYMMDD>.mp4`，在 `present_files` 中排在日报 HTML 之后、Markdown 之前。
- `reel/public/audio/` 是生成物，已在 `.gitignore` 中忽略；`reel/src/audio.json` 入库（含 `enabled:false` 基线，保证干净检出也能构建）。
- **渲染前必须先跑 `gen_narration.py`**：实测「清单写着 enabled=true 但 mp3 不存在」会让渲染
  `Error while downloading http://localhost:3000/public/audio/xxx.mp3: 404` **硬失败（exit 1）**，
  不是静默降级。所以入库清单刻意保持 `enabled:false`，跑完生成脚本才会翻成 `true`。
- 10 篇的渲染耗时约为 5 篇的 2 倍（实测 ≈ 4–5 分钟），属正常。

## 5. 质量闸门（不达标就不交付视频，只交付日报）

- [ ] **10 篇**中文要点齐全（3 条/篇），英文原题与 arXiv 号**逐字正确**。
- [ ] 每篇都有**独立的口播稿**，且不是 `bullets` 原句的拼接（这一步靠人工撰写，脚本不做质量判断）。
- [ ] `gen_narration.py` 无 `[warn] 超出`——每段音频都装进了预算；每段 mean ≈ −18dB（归一化生效）。
- [ ] `npm run compositions` 显示 `30  1920x1080  6318`（10 篇时），帧数误差 ≤ 1 帧。
- [ ] `remotion ffprobe` 显示 **210.6s** 且**存在 audio 流**（aac / 48kHz / stereo）。
- [ ] `tools/check_video_av.py` **全绿**：时长偏差 ≤0.25s；片头 / **10 篇** / 片尾每段都检出人声
      （mean_volume > −40dB）、语音起点在该段开头 2s 内；无 >3s 静音空洞。
      这是「音画是否同步、口播是否清晰、总时长是否达标」的机器判据，FAIL 必须修复后重渲。
- [ ] 抽 3 张静帧（片头 / 第 3 篇左右 / 片尾）肉眼确认无文字溢出、无重叠、无残留占位；
      **片尾两行 arXiv 号必须完整可读**（这是 10 篇规格新增的版面风险点）。
- [ ] 依赖未装或渲染失败：如实报告「本轮未产出视频」并给原因，**不要伪造产物**。

## 6. 已知边界

- **无背景音乐**：BGM 涉及版权，当前版本只有人声。
- 成片约 3.5 分钟、体积约 25–30 MB（5 篇时约 13.9 MB）；若嫌长，把 `--top` / `--expand` 调回 5 / 0 即恢复旧规格。
- Edge TTS 依赖外网端点；不通时 `gen_narration.py` 会失败，此时应报告「本轮未产出旁白」并退化为无声版本，
  或改用 Windows SAPI / 本地模型（`--voice` 参数留了口子，但需自行实现 provider）。
