# 数据文件参考

`output/` 是**运行产物目录**：所有抓取缓存、打分结果、渲染页面、收藏记录、归档库都在这里。
它整体被 `.gitignore` 排除——删掉不会丢代码，但会丢历史与收藏。

本文是该目录的字段级说明。想了解它们如何产生，看[架构总览](../architecture/overview.md)。

---

## 一、目录一览

```
output/
├─ raw.json / raw_expand.json        # 累积抓取池
├─ recommend.json / expand.json      # 当期推荐 / 扩展（数组）
├─ issue_core.json / issue_expand.json
├─ issue_stats.json                  # 当期统计
├─ papers_index.json                 # 前端重排用的索引（含每篇 base/tv/toks/pen）
├─ scores.json                       # 全池打分（排查用）
├─ affiliations.json                 # 作者单位（跨日累积）
├─ summaries.json / rec_notes.json / highlights.json / themes.json
├─ library.json                      # 收藏 / 下载 / Downvote
├─ profile_state.json                # 行为学习状态
├─ behavior.json                     # 行为流水（最近 2000 条）
├─ interests_extra.json              # 兴趣来源的解析增量
├─ netroute.json                     # 下载路由缓存
├─ kw_df.json                        # 关键词文档频率（来源关键词抽取用）
├─ archive.db                        # SQLite：本期新增判定 + 期次索引
├─ archive/<YYYYMMDD>.{html,md}      # 每期快照（只增不改）
├─ arxiv_digest_<YYYYMMDD>.{html,md} # 当期日报
├─ favorites.html / archive.html     # 收藏页 / 存档页
├─ backup/<时间>/                    # 导入预设时的旧配置备份
├─ server.log                        # 服务日志
└─ _*.json / *.bad_<时间戳>          # 临时与坏输出留档（可安全删除）
```

## 二、抓取池

| 文件 | 顶层结构 | 说明 |
| --- | --- | --- |
| `raw.json` | `{generated_at, newest_seen, cutoff, window_days, categories, total_before_filter, papers[]}` | 主分类 feed，**累积池**：只并集不删除。注意 `categories` 是**抓取时的快照**；页面分类小节的顺序以 `config.json` 为准（`build_report` 渲染时重排） |
| `raw_expand.json` | 同上，`categories` 为扩展分类 | 扩展 feed，体量通常远大于主池 |

单篇论文对象的关键字段（`paper`）：

| 字段 | 说明 |
| --- | --- |
| `id` / `arxivid` | arXiv 完整号（可能带版本） |
| `title` / `abstract` | 标题与摘要（摘要会截断到 1400 字符进页面） |
| `authors[]` | 作者列表 |
| `published` / `updated` | 首次提交日 / 最后更新日（`YYYY-MM-DD`） |
| `primary` | 主分类（如 `cs.DB`）；RSS 通道可能只有 `queried_cat` |
| `cats[]` | 全部分类 |
| `pdf` | PDF 链接；缺失时按短号拼 `https://arxiv.org/pdf/<短号>` |
| `comment` | 作者备注（版本信息、会议录用等） |

> `newest_seen` 是本期抓到的最新提交日，用于给「本期新增」的判定做基准；
> `cutoff` 是时间窗起点。

## 三、打分结果

| 文件 | 结构 | 用途 |
| --- | --- | --- |
| `recommend.json` | 数组，长度 = `top_recommend` | 「为你推荐」的内容（已按分数降序） |
| `expand.json` | 数组，长度 = `top_expand` | 「兴趣扩展」的内容 |
| `recommend_candidates.json` | 数组 | 过了阈值但没进前列的候选（排查"为什么它没上榜"） |
| `issue_core.json` / `issue_expand.json` | `{issue_date, mode, generated_at, newest_seen, window_days, categories, pool_size, papers[]}` | 本期新增的完整清单（`mode` 标识是否走了兜底） |
| `issue_stats.json` | `{issue_date, mode, pool_core, pool_expand, new_core, new_expand}` | 当期规模统计，页面头部与视频脚本都用它 |
| `papers_index.json` | `{topics[], weights[], seeds[], kw{}, pens{}, papers{}, expand_ids[]}` | **前端重排的核心**：每篇带 `base` / `tv` / `toks` / `pen`，浏览器用同一套公式重算分数 |
| `scores.json` | 数组（全池） | 全部论文的分数快照，排查"推荐突然变差"时先看它的 Top10 |

推荐项（`recommend.json` 的元素）字段：

```jsonc
{
  "id": "2609.09742",
  "title": "...",
  "authors": ["..."],            // 最多 6 位
  "primary": "cs.DB",
  "cats": ["cs.DB", "cs.LO"],
  "published": "2026-09-09",
  "abstract": "...",             // ≤1400 字符
  "summary": "中文摘要（若已补）",
  "score": 23.4,
  "topics": ["事务与隔离级别"],   // 命中的主题名，最多 4 个
  "topic_detail": [ { "topic": "...", "raw": 12.0, "title_hits": 2, "abstract_hits": 5 } ],
  "familiar_authors": ["..."],   // 命中的熟悉研究者
  "systems": ["..."],            // 命中的代表系统
  "tv": [[0, 12.0]],             // [主题下标, 原始分]，下标对应 topics 顺序
  "base": 20.0,                  // 不含主题权重的静态分
  "toks": ["linearizability"],   // 参与关键词加权的实词
  "pen": 0.0,                    // 单篇惩罚（Downvote 后为 -12）
  "pdf": "https://arxiv.org/pdf/2609.09742"
}
```

## 四、编辑性内容（可手工补）

| 文件 | 结构 | 说明 |
| --- | --- | --- |
| `summaries.json` | `{"<短号>": "中文摘要"}` | **value 必须是纯字符串**。写成对象会让渲染端报 `AttributeError` |
| `rec_notes.json` | `{"<短号>": "推荐理由"}` | 覆盖默认的"命中：xxx"文案 |
| `highlights.json` | `{"<短号>": "一句话看点"}` | 重点论文块用 |
| `themes.json` | 数组 | 当期主题归纳 |
| `video_notes.json` | `{"_intro": {...}, "_outro": {...}, "<短号>": {"bullets": [], "narration": ""}}` | 视频画面要点与口播稿 |

这些文件的 key **一律用 arXiv 短号**（不带版本、不带分类前缀）。补完后要重跑
`recommend.py`（重新读它们）与 `build_report.py`（重新渲染）。

## 五、`library.json`

```jsonc
{
  "favorites": {
    "2609.10462": {
      "added_at": "2026-09-10 21:27:21",
      "id": "2609.10462",
      "title": "...", "authors": ["..."], "abstract": "...",
      "primary": "cs.LO", "cats": ["cs.LO"], "published": "2026-09-09",
      "pdf": "...", "comment": "...",
      "downloaded": true,                 // 已下载时才有
      "path": "D:/papers/...pdf",         // 已下载时才有
      "note": "可选备注"
    }
  },
  "downloads": {
    "2609.10347": { "path": "D:/papers/arXiv2026 2609.10347 CertiFlash....pdf",
                    "at": "2026-09-10 21:29:37", "title": "..." }
  },
  "downvotes": {
    "2609.08508": { "title": "...", "at": "2026-09-11 11:54:32" }
  }
}
```

规则：

- 三个字典都以**短号**为 key；
- `downloads[..].path` 是**绝对路径**，换机器后需要手动改或重新下载；
- 收藏与 Downvote 互斥：收藏会清掉同号 Downvote，Downvote 不会自动取消收藏；
- 写入是"读-改-写 + 临时文件 + `os.replace`"，由服务端 `_lib_lock` 串行保护。

## 六、`profile_state.json` 与 `behavior.json`

`profile_state.json`（行为学习的**聚合**结果）：

| 字段 | 结构 | 说明 |
| --- | --- | --- |
| `topic_mult` | `{主题名: 倍率}` | 初值 1.0，范围 `[0.25, 3.0]` |
| `kw` | `{关键词: 权重}` | 范围 `[-4.0, 4.0]` |
| `paper_bonus` | `{短号: -12.0}` | Downvote 的单篇惩罚 |
| `counts` | `{行为: 次数}` | 累计计数 |
| `updated_at` | string | 最后更新时间 |

`behavior.json` 是**流水**（数组，只保留最近 2000 条）：

```jsonc
[ { "id": "2609.09742", "action": "download", "at": "2026-10-17 08:31:02",
    "topics": ["事务与隔离级别"] } ]
```

用途：审计"为什么画像变了"，或离线分析自己的阅读习惯。删掉它不影响打分。

## 七、`interests_extra.json`

「兴趣来源」的解析增量，与手写画像分离存放：

```jsonc
{
  "sources": [ { "sid": "s1759...", "type": "link", "value": "https://...",
                 "note": "", "added_at": "...", "derived": { "people": [], "keywords": [], "matched_topics": [] } } ],
  "_derived": { "people": [], "keywords": [], "matched_topics": [] },
  "block_kw": ["被屏蔽的来源关键词"],
  "updated_at": "..."
}
```

`_derived` 是全部来源的汇总（去重后人名 ≤60、关键词 ≤60），在打分时被当作
「我的来源关注」主题与追加的 `people`。删除某个来源 → `rebuild()` 会重算 `_derived`。

## 八、`archive.db`（SQLite）

| 表 | 主键 | 字段 | 用途 |
| --- | --- | --- | --- |
| `seen` | `sid` | `sid, first_date, first_at` | **本期新增的唯一判据**：某篇首次出现在哪一期 |
| `issues` | `date` | `date(YYYYMMDD), generated_at, newest_seen, n_new, n_core, n_rec, n_exp, html, md, created_at` | 期次索引 |
| `issue_papers` | `(date, sid)` | `date, sid, pool(core/expand/archive), is_new, prim, title, authors, published, score, tier, summary, note, topics, affil, pdf` | 每期每篇的存档行 |

索引：`idx_ip_date(date)`、`idx_ip_sid(sid)`。

两个容易踩的点：

1. **不要手工删除 `seen` 里的行**来"让论文重新出现"——下次运行会把它们全部当新增；
2. `issues.date` 是 `YYYYMMDD` 字符串，不是日期类型。

## 九、归档快照

`output/archive/<YYYYMMDD>.{html,md}` 是当期日报的**副本**，只会新增、不会被后续重跑改写。
`/archive` 与 `/archive/<日期>` 读的就是它。补跑历史可以用 `tools/backfill_archive.py`。

## 十、可安全删除的临时文件

| 模式 | 含义 |
| --- | --- |
| `_*.json` | 一次性探针 / 中间产物（如 `_pending.txt`、`_new_summaries_*.json`） |
| `*.bad_<时间戳>` | 抓取失败时保留的坏输出，供排查 |
| `*.bak_<时间戳>` | 手动备份（`affiliations.json.bak_*`、`profile_state.bak_*`） |
| `__pycache__/` | Python 字节码 |

**不要**删：`raw*.json`（累积池）、`library.json`、`archive.db`、`archive/`、
`profile_state.json`、`summaries.json`、`rec_notes.json`。

## 十一、PDF 文件的命名

下载目录由 `config.download_dir` 决定，文件名由 `paperutil.build_filename()` 生成：

```
arXiv<年> <短号> <去标点标题>.pdf
例：arXiv2026 2609.10347 CertiFlash A Formal Verification Framework for Flash Translation Layers.pdf
```

标题里的标点会被清理、空格保留。同名文件已存在时**跳过**（除非 `force=true`），
所以下载是幂等的，不会覆盖你手动改过的文件。

---

相关：[架构总览](../architecture/overview.md) · [HTTP API](http-api.md) · [config.json](config.md)
