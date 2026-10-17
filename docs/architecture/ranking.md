# 排序与学习算法

本文是"分数为什么是这个数"的权威说明。字段定义见 [interests.json](../reference/interests.md)，
代码在 `recommend.py`（打分）与 `profile.py`（学习）。

---

## 一、可调信号一览

| 信号 | 来源 | 强度 | 是否随行为变化 |
| --- | --- | --- | --- |
| 主题关键词命中 | `interests.topics[].keywords` | 4 / 1.6 / 0.8（见下） | ✅（乘学习倍率） |
| 熟悉研究者 | `interests.people[]` + `owners[].people_linked` | +10 / 人 | ❌ |
| 代表系统 | `interests.signature_systems[]` | +6 / 个 | ❌ |
| 降权词 | `interests.negative` | `weight × 3` / 个，最多 4 个 | ❌ |
| 关键词权重 | `profile_state.kw` | 逐词累加，范围 ±4 | ✅ |
| 单篇惩罚 | `profile_state.paper_bonus` | -12（Downvote） | ✅ |

## 二、公式

```
score = base + Σ(主题原始分 × 主题实际权重) + Σ(实词权重) + 单篇惩罚

base        = 10 × 熟悉作者命中数
            +  6 × 代表系统命中数
            + negative.weight × 3 × min(降权词命中数, 4)

主题原始分   = 4 × min(标题命中该主题关键词数, 4)
            + 0.8 × min(摘要命中数, 15)

主题实际权重 = 种子权重(interests.topics[].weight) × 学习倍率(profile_state.topic_mult)

单篇惩罚     = paper_bonus[短号]（Downvote 后 -12，撤销后 0）
```

几个刻意的取舍：

| 设计 | 理由 |
| --- | --- |
| 标题权重是摘要的 5 倍（4 vs 0.8） | 标题命中基本等于方向对口；摘要里出现关键词噪音大得多 |
| 标题最多计 4 个、摘要最多 15 个 | 封顶防"关键词堆砌"的论文靠数量刷分 |
| 熟悉作者 +10 是单项最高 | 跟着人读是最高信噪比的策略 |
| 降权词最多计 4 个 | 避免一篇堆满无关热词的论文被过度惩罚到消失 |
| 主题分再乘权重 | 让"次要方向"的论文不会因为关键词命中多而挤掉主方向 |

## 三、算一遍

假设画像里两个主题：`T1 = 事务与隔离级别`（种子权重 1.5）、`T2 = 一致性模型`（种子权重 0.8），
学习倍率都还是 1.0；`people` 命中 1 位；无代表系统、无降权词命中。

某篇论文：

- T1 命中标题 2 个关键词、摘要 5 个；
- T2 命中标题 1 个、摘要 3 个；
- 抽取出的实词在 `kw` 里的权重和为 `+0.9`；
- 未被 Downvote。

```
raw(T1) = 4×min(2,4) + 0.8×min(5,15) = 8.0 + 4.0  = 12.0
raw(T2) = 4×min(1,4) + 0.8×min(3,15) = 4.0 + 2.4  =  6.4

base    = 10×1 + 6×0 + (-1.0)×3×0    = 10.0

score   = 10.0 + 12.0×1.5 + 6.4×0.8 + 0.9 + 0
        = 10.0 + 18.0 + 5.12 + 0.9
        = 34.02  →  显示 34.0
```

同一篇若被 Downvote：`34.02 - 12 = 22.02`。它不会消失，但通常已跌出前列。

## 四、入选规则

| 板块 | 阈值 | 数量上限 |
| --- | --- | --- |
| 🎯 为你推荐 | `score ≥ 7` | `config.top_recommend`（默认 14） |
| 🌱 兴趣扩展 | `score ≥ 9` | `config.top_expand`（默认 10） |

扩展区阈值更严（9 > 7），因为它的目的是"补充视野"而不是"多给几篇"。

**兜底**：严格阈值下**一篇都不达标**时（典型是刚初始化、画像还很薄），退化为按分数取前 N，
并在卡片上标注"画像尚未命中，先按分数兜底"，`issue_core.json` 的 `mode` 字段会记录这次降级。

```python
# 逻辑示意（recommend.main）
core = [p for p in scored if p.score >= 7][:top_n]
if not core and scored:                     # 只在结果为空时触发
    core = sorted(scored)[:top_n]
    mode = "fallback"
```

它只在结果为 0 时生效，因此**不会稀释已经调好的画像**。

## 五、行为学习：一次性点击改多少

`profile.apply_event(sid, action)` 的更新式：

```
主题倍率 += lr_topic × action_weight × clamp(strength, 0.3, 2.5)
    其中 strength = min(4, 标题命中数) × 0.6 + min(8, 摘要命中数) × 0.1
    结果 clamp 到 topic_range（默认 [0.25, 3.0]）

关键词权重 += lr_keyword × action_weight
    只更新该篇抽出的实词（最多 45 个），结果 clamp 到 keyword_range（默认 [-4, 4]）
```

`action_weight` 见 `behavior.actions`（下载 1.3 / 收藏 1.0 / 打开 PDF 0.55 / 展开摘要 0.3）。

接着上面的例子，点一次**收藏**（`w = 1.0`，`lr_topic = 0.06`）：

```
strength(T1) = min(4,2)×0.6 + min(8,5)×0.1 = 1.2 + 0.5 = 1.7
倍率增量     = 0.06 × 1.0 × 1.7 = 0.102
T1 倍率      = 1.0 → 1.102   （下次打分 T1 贡献从 18.0 变成 19.84）
关键词       += 0.05 × 1.0 = +0.05 / 词
```

注意 `clamp(..., 0.3, 2.5)`：命中很少的论文也至少推进 0.3（"我点了说明有点相关"），
命中很多的论文最多推进 2.5（防刷）。

### 为什么负向学习默认关闭

`downvote` / `undownvote` 的语义是"**这一篇**不要"。默认配置下它们**只**写
`paper_bonus[sid] = -12`，不碰主题倍率与关键词权重（`learn_neg_topics` / `learn_neg_keywords` 均为 `false`）。

如果打开会怎样——这是一次真实故障：

| 环节 | 现象 |
| --- | --- |
| 机制 | 单次 Downvote 会三重惩罚：论文级 -12、主题倍率扣分、以及该篇 45 个 token 各扣 `0.12×1.6 ≈ -0.192` |
| 放大 | **曝光偏置**：推荐得越多的主题，被 Downvote 的绝对次数也越多 |
| 结果 | 五个主研究方向的倍率全部触底到 0.25；`distributed`、`data` 这类领域通用词累积到 -3 以下 |
| 症状 | 当期新增 164 篇，**没有一篇够到 7 分**，日报几乎空白 |

顺着这个链条看，Downvote 惩罚"主题"在语义上就是错的：它表达的是"这篇"，不是"这个方向"。
方向级偏好应该用主题的 `weight` 显式表达（见[调优画像](../guide/profile-tuning.md)）。

## 六、排查"推荐突然变差"

三步分离"内容弱"与"画像坏"：

1. **看全池 Top10**：`output/scores.json` 里分数最高的十篇是否仍然正常（如 30+ 分）。
   - 全池正常 + 当期全低 → **画像问题**；
   - 全池也低 → 抓取或关键词配置问题。
2. **看倍率**：`python profile.py`，主题倍率是否大面积为 1.0 以下、是否触底 0.25。
3. **中性基线对照**：把主题倍率全置 1、关键词映射置空，重算当期分数并与现状对比。
   曾实测（同一期 164 篇）达到 ≥7 分的篇数：

   | 配置 | ≥7 分篇数 |
   | --- | --- |
   | 现状（已污染） | 0 |
   | 只清空关键词权重 | 10 |
   | 只把主题倍率归 1 | 3 |
   | **两者都归位** | **35** |

结论：两者叠加才会让推荐器"死"，单看一项容易误判。

修复协议（保留你的显式意图）：备份 `profile_state.json` → 删除**负向**关键词（保留正向）→
`topic_mult` 归 1.0 → **保留** `paper_bonus` 里的全部 -12 → 重跑 `recommend.py` 与 `build_report.py`。

## 七、前端重排用的是同一套公式

点击收藏 / Downvote 后页面不刷新就要重排，所以浏览器里有一份等价实现：

| 数据 | 从哪来 |
| --- | --- |
| `base`（静态分） | `papers_index.json` 的 `papers[短号].base` |
| `tv`（各主题原始分） | `papers[短号].tv = [[主题下标, 原始分], ...]` |
| 权重序列 | `papers_index.json` 的 `weights[]`（顺序 = `topics` 顺序） |
| 实词权重 | `kw{}` |
| 单篇惩罚 | `pens{}` |

所以**改打分公式必须同时改两处**（`recommend.score()` 与 `build_report.py` 内的 `rescore()`），
否则会出现"首屏排序与点击后排序不一致"这种极难发现的 bug。

## 八、可复现性

`output/scores.json` 是每次 `recommend.py` 的全池分数快照，`issue_stats.json` 记录当期规模与
是否降级。想复现某个历史结论，用同一份 `raw*.json` + `interests.json` + `profile_state.json`
重跑 `recommend.py` 即可（这三份都是文件，不依赖时间）。

---

相关：[interests.json](../reference/interests.md) · [调优画像](../guide/profile-tuning.md) ·
[模块职责](modules.md) · [数据文件](../reference/data-files.md)
