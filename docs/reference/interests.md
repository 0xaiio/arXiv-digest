# interests.json 参考

`interests.json` 就是"你的研究画像"。它由 `interests.example.json` 在首次运行时生成，
之后属于个人数据，不进版本库。

分工：`config.json` 决定**看哪些分类**（[见 config.md](config.md)），
`interests.json` 决定**在这些论文里谁排前面**。

---

## 一、顶层结构

```jsonc
{
  "owners":            [ /* 画像主来源：人 */ ],
  "topics":            [ /* 研究主题：关键词命中即加分 */ ],
  "people":            [ /* 熟悉研究者：作者名命中 +10/篇 */ ],
  "signature_systems": [ /* 代表系统：标题/摘要命中 +6 */ ],
  "negative":          { "weight": -1.0, "keywords": [ /* 降权词 */ ] },
  "behavior":          { /* 行为学习超参 */ }
}
```

所有字段都可以缺省——`customize.load_interests()` 与 `recommend.load_profile()` 都用 `.get()`
带默认值，不会因为少一个键而崩。`negative.weight` 缺失时按 `-1.0` 处理。

页面入口：`/profile`。改完点「↻ 重算推荐」即生效，不必重启服务。

## 二、`owners[]` — 画像主来源

摘要页头部「基于 A × B × C 的兴趣画像」就是从 `label`（缺失时用 `name`）拼出来的。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | ✅ | 姓名，唯一键。改名请走 `/profile` 的「编辑」（内部按原名定位） |
| `label` | string | | 头部展示的简称；留空回退 `name` |
| `site` | string | | 主页，必须是 `http(s)://`，卡片上以链接展示 |
| `affiliation` | string | | 机构 |
| `interests` | string | | 一句话研究兴趣 |
| `signature_topics` | string[] | | 代表方向，卡片最多显示 4 条 |
| `people_linked` | bool | | 是否同步计入 `people`（作者命中 +10/篇）。删除来源会一并撤销 |

约束：姓名必填、不可重名、`site` 必须 `http(s)`、**至少保留一条**（不能全删光）。

> `owners` 本身**不参与打分**——打分用的是 `people`。`owners` 是"画像的来源说明"，
> 勾了 `people_linked` 才会连带把名字加进 `people`。

## 三、`topics[]` — 主题

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `name` | string | 主题名。**它同时是行为学习倍率的 key**，改名等于换了一个新主题（旧倍率不再生效） |
| `weight` | number | 种子权重，默认 `1.0`。实际权重 = `weight × 学习倍率` |
| `keywords` | string[] | 关键词/短语，大小写不敏感 |

单篇贡献：

```
主题原始分 = 4 × min(标题命中数, 4) + 0.8 × min(摘要命中数, 15)
贡献       = 原始分 × 实际权重
```

> **顺序不变式**：`topics` 的顺序 = 前端重排用的权重索引顺序。代码里由
> `customize.effective_topics()` 统一拼接（原主题按原序 + 自动生成的「我的来源关注」），
> 不要在别处手工重排。

## 四、`people[]` 与 `signature_systems[]`

| 字段 | 匹配方式 | 分值 |
| --- | --- | --- |
| `people` | 大小写不敏感的**整名**匹配，作用于作者列表 | 每位 +10 |
| `signature_systems` | 词边界正则，作用于 `标题 + 摘要` | 每个 +6 |

人名写全名（`"Ada Lovelace"`）比写姓氏准；系统名建议用有辨识度的写法（`"RocksDB"`、`"IronFleet"`）。

## 五、`negative`

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `weight` | `-1.0` | 每个降权词扣 `weight × 3`，最多计 4 个（即最多 `-12`） |
| `keywords` | `[]` | 与你主线无关的热点词。**只降权不排除**，命中它的论文仍留在「分类详解」 |

## 六、`behavior` — 行为学习超参

```jsonc
"behavior": {
  "actions": { "favorite": 1.0, "unfavorite": -0.7, "download": 1.3,
               "pdf": 0.55, "abstract": 0.3, "downvote": -1.6, "undownvote": 0.9 },
  "lr_topic": 0.06,
  "lr_keyword": 0.05,
  "topic_range": [0.25, 3.0],
  "keyword_range": [-4.0, 4.0],
  "downvote_paper_penalty": -12.0,
  "learn_neg_topics": false,
  "learn_neg_keywords": false
}
```

| 字段 | 代码默认 | 说明 |
| --- | --- | --- |
| `actions` | 见上 | 各行为的"价值"，正数提升、负数反向。`download` 最强是刻意的：下载≈要读 |
| `lr_topic` | `0.06` | 每次行为对**主题倍率**的学习率 |
| `lr_keyword` | `0.05` | 每次行为对**关键词权重**的学习率 |
| `topic_range` | `[0.25, 3.0]` | 主题倍率上下限，防止一次误点把主题打死 |
| `keyword_range` | `[-4.0, 4.0]` | 关键词权重上下限 |
| `downvote_paper_penalty` | `-12.0` | 被 Downvote 论文的固定扣分 |
| `learn_neg_topics` | `false` | **负向行为是否参与主题倍率学习** |
| `learn_neg_keywords` | `false` | **负向行为是否参与关键词权重学习** |

> 作者的数据包（`presets/hengxin/`）里用 `lr_topic 0.15` / `lr_keyword 0.12`
> （学得更快，也更容易被误点带偏）。代码默认更保守。为什么负向学习默认关闭，见
> [排序与学习算法](../architecture/ranking.md) §5——那是一次真实故障的结论。

## 七、写入边界

`interests.json` 只由两处写：`/profile`（经 `customize.*`）与 `tools/preset.py import`。
两者都遵循"**只改目标键，其余原样保留**"：

- `add_owner` / `update_owner` / `remove_owner` 只动 `owners` 与 `people`；
- `add_category` / `set_download_dir` 写的是 `config.json`，不碰画像；
- 「兴趣来源」的解析结果不存在这里，而是 `output/interests_extra.json`
  （见[数据文件](data-files.md)），删除来源即可撤销。

> 模板 `interests.example.json` 的 `topics` / `owners` / `people` **一律为空**：
> 新装机器的 `/profile` 必须是真正的空状态，不能有任何人的方向，也不能有"示例主题"
> 这种会参与打分的假数据。格式示例写在模板的 `_comment` 里。

## 八、一个最小可用的画像

```jsonc
{
  "owners": [
    { "name": "Ada Lovelace", "label": "Ada", "site": "https://example.org",
      "affiliation": "Analytical Engine Lab", "interests": "程序化推理",
      "signature_topics": ["分析机", "符号运算"], "people_linked": true }
  ],
  "topics": [
    { "name": "程序化推理", "weight": 1.0, "keywords": ["symbolic computation", "analytical engine"] }
  ],
  "people": ["Ada Lovelace"],
  "signature_systems": ["Analytical Engine"],
  "negative": { "weight": -1.0, "keywords": [] }
}
```

这样配完跑一次推荐，至少有 3 条信号在起作用（主题关键词、熟悉作者 +10、代表系统 +6）。

---

相关：[config.json](config.md) · [排序与学习算法](../architecture/ranking.md) ·
[调优画像](../guide/profile-tuning.md) · [数据包（预设）](../guide/presets.md)
