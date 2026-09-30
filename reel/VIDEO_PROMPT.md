# arXiv Weekly 论文解读视频 · 制作提示词（v1）

> 适用范围：定时任务 `af055043`（arXiv cs.\* 论文日报）的第 9 步「额外制作视频」。
> 与「AI 周报速递」这类新闻短视频的关键差别：**论文不能被 3 秒带过**。
> 一条新闻可以只播标题，一篇论文至少要交代「背景 → 方法 → 结果」，因此单篇给足 12 秒。

## 0. 目标与硬规格

| 项 | 值 |
|---|---|
| 分辨率 / 帧率 | **1920×1080 / 30fps**，H.264 |
| 时长 | 片头 3s + **每篇 12s** + 片尾 3s；5 篇 = **66s**（1994 帧） |
| 音轨 | 默认无（BGM 涉版权，需要时另行确认） |
| 篇数 | 5 篇，取自 `recommend.json` 按匹配度排序的本期推荐前 5 |
| 渲染方式 | **Remotion 代码渲染**（`reel/` 工程），不用文生视频模型 |

**为什么必须用代码渲染而不是文生视频**：

1. 论文英文原题、arXiv 号、中文要点必须**逐字准确**；生成式视频模型无法保证文字正确，学术论文视频一旦把编号或术语渲染错，整条片子失去价值。
2. 时长、帧率、每段的入场时机必须**精确可控**（要写成不变量进测试/校验）。
3. 这是**每周重复执行**的流水线产物，必须是确定性的、可回归的，而不是每次抽样碰运气。

## 1. 数据准备（一切事实来自本地产物，禁止凭空生成）

1. 先完成日报流水线（抓取 → 推荐 → 渲染 → 确保 8765 在线）。
2. 生成数据：`python tools/gen_video_data.py --top 5` → `reel/src/papers.json`。
   字段来源：`recommend.json`（排名 / 分数 / 题名 / 作者）、`issue_core.json`（期号 / 统计 / 回溯窗口）、
   `affiliations.json`（单位）、`summaries.json`（中文摘要）。
3. **必须为每篇人工撰写 `output/video_notes.json`**：

   ```json
   {
     "2609.32972": {
       "kw": ["Multi-Paxos", "Raft", "RoundTick"],
       "bullets": [
         {"tag": "背景", "text": "……（≤62 汉字）"},
         {"tag": "方法", "text": "……"},
         {"tag": "结果", "text": "……"}
       ]
     }
   }
   ```

   - 三条要点标签固定 `背景 / 方法 / 结果`；每条 ≤ 62 汉字，必须**能追溯到英文摘要**，摘要没说的不要写。
   - `kw` 取**在中文文案里真实出现过**的英文技术词（2–4 个），用于强调色高亮；不要编造高亮词。
   - 语义归属拿不准时，用中性标签 `要点 1 / 要点 2 / 要点 3`，不要硬套「方法 / 结论」。
   - 缺 notes 时生成器会退化成「英文摘要首句」——**那种产物不可交付**，必须先补 notes。
4. 再跑一次 `gen_video_data.py` 使 notes 生效。

## 2. 视觉与动效规范

- **配色**：背景纯深色 `#05070A`，正文 `#FFFFFF`，要点正文 `#E6EDF5`，次级 `#C3CEDA`，弱化 `#7C8896`；
  强调色**只用一种** `#00D4FF`（类别、arXiv 号、关键词、匹配度徽章、时间线节点、要点标签芯片）。
- **字体**：系统栈 `'Segoe UI','Microsoft YaHei','PingFang SC'`；等宽 `'Cascadia Mono','Consolas'`。
  不使用 `@remotion/google-fonts`（渲染期不联网）。
- **片头 3s（90f）**：kicker `ARXIV · CS.* DIGEST`（等宽、字距 8、强调色）淡入 →
  主标题 `arXiv Weekly`（156px/900）以 spring（`damping 13 / mass 0.9 / stiffness 92`）从上方 **−280px 弹入** →
  强调色进度条随同一 spring 展开到 560px → 期号与区间、三项统计（本期新增 / 推荐 / 兴趣扩展）依次上浮。
- **每篇 12s（360f）**，元素错峰从左侧 −56px spring 滑入（delay 帧：meta 2、原题 10、作者 26、单位 34、要点 52/66/80、页脚 100）：
  - 右上巨型序号水印（240px/900，白 4.5% 透明）
  - meta 行：`cs.DC | arXiv:2609.32972` + 右侧 `匹配度 30.6` 描边徽章
  - **英文原题**（52px/800）——真实可核实，不做机器翻译
  - 作者（含 `等 N 人`）+ `🏛` 单位（最多 2 家 + `等 N 家单位`）
  - 分隔线 + 三条中文要点（标签芯片 + 31px 正文，关键词染强调色）
  - 页脚 `arxiv.org/abs/<sid>`
- **左侧竖向时间线**（y 250→880）：底线 + 渐变进度线随播放上行；当前节点用 spring
  （`damping 11 / stiffness 190`）弹亮并带 26px 光晕，已播节点半亮，未播为描边；左侧标 `01`–`05`。
- **转场**：相邻段落 14 帧交叉淡入淡出，**禁止硬切**；片头/片尾同样与正文交叉淡入淡出。
- **片尾 3s（90f）**：`关注获取更多`（112px/900）呼吸动画
  `scale = 1 + 0.032·sin(2π·t/2.4)`、光晕 `20 + 12·sin(2π·t/2.4)`，周期 2.4s；
  下方给出更新节奏（每周二 / 周五 23:10）与本片 5 个 arXiv 号。
- **实现禁令**：禁用 CSS `transition` / `animation`，一律 `useCurrentFrame()` + `interpolate` / `spring`
  并带 `extrapolateLeft/Right: "clamp"`。

## 3. 渲染与交付

```bash
cd reel
npm install --registry=https://registry.npmmirror.com --no-audit --no-fund   # 仅首次，约 250 包
npm run compositions                                                          # 先确认 30fps/1920x1080/帧数
npm run still  -- --frame=200                                                 # 抽静帧看版面（可选）
npm run render                                                                # -> out/arxiv-weekly.mp4
```

- Chrome Headless Shell 下载失败时，加 `--browser-executable "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"`。
- 渲染完成后重命名到 `output/arxiv_weekly_<YYYYMMDD>.mp4`，在 `present_files` 中排在日报 HTML 之后、Markdown 之前。

## 4. 质量闸门（不达标就不交付视频，只交付日报）

- [ ] 5 篇中文要点齐全（3 条/篇），英文原题与 arXiv 号**逐字正确**。
- [ ] `npm run compositions` 显示 `30  1920x1080  1994`（5 篇时），帧数误差 ≤ 1 帧。
- [ ] 抽 3 张静帧（片头 / 第 3 篇 / 片尾）肉眼确认无文字溢出、无重叠、无残留占位。
- [ ] 依赖未装或渲染失败：如实报告「本轮未产出视频」并给原因，**不要伪造产物**。
