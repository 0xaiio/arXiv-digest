# 架构与实现要点

面向想改代码 / 想搞清楚「为什么这样设计」的人。字段级的配置说明见 [CONFIG.md](CONFIG.md)。

## 一、流水线

`run_daily.py` 串起六步，任一步失败都保留上一期产物，不会把已有日报清空：

```
fetch_arxiv.py     → output/raw.json          主分类，最近 window_days 天
fetch_expand.py    → output/raw_expand.json   扩展分类（兴趣扩展用）
        ↓  失败就降到 RSS（fetch_rss.py，按短号增量合并，绝不删条目）
recommend.py       → recommend.json / expand.json / papers_index.json
fetch_affil.py     → output/affils.json       作者单位（arXiv API 不提供，抓 HTML，很慢）
build_report.py    → arxiv_digest_<日期>.html/.md + favorites/archive 页 + 当归档
ensure_server()    → 127.0.0.1:8765（已在跑就复用）
```

常用开关：`--skip-fetch`（复用已抓数据）、`--skip-affil`（跳过最慢的一步）、
`--no-serve`（只出文件不起服务）。

## 二、打分

```
score = base + Σ(主题原始分 × 主题权重) + Σ(学习到的关键词权重) + 单篇惩罚

base        = 10 × 命中的熟悉作者数
            +  6 × 命中的代表系统数
            + negative.weight × 3 × min(降权词命中数, 4)
主题原始分   = 4 × min(标题命中关键词数, 4) + 0.8 × min(摘要命中数, 15)
主题权重     = 种子权重(interests.json) × 行为学习倍率(profile_state.json)
单篇惩罚     = Downvote 的 -12（可在 /profile 撤销）
```

- 入选阈值：主推荐 **≥ 7**，兴趣扩展 **≥ 9**（扩展区更严，避免噪音挤占视线）。
- **兜底**：若严格阈值一篇都不达标（典型是刚初始化、画像还很薄），退化为「按分数取前 N」，
  并在每张卡片注明「画像尚未命中，先按分数兜底」。只在严格结果为 0 时触发，
  不影响已经把画像调好的用户。
- 前端点收藏 / 下载 / Downvote 后会用同一套公式在浏览器里重算分数（`papers_index.json`
  里带着每篇的 `base / tv / toks / pen`），所以排序变化不需要刷新页面。

## 三、只呈现「本期新增」

`raw.json` / `raw_expand.json` 是**累积池**（RSS 降级按短号合并，永不删条目）。
直接全池打分会导致前几天的高分论文天天重复出现，因此：

- `archive.py` 的 `seen(sid, first_date)` 记录每篇首次出现的期次，日报只渲染本期；
- 首次启用（DB 为空）不会把整个池子当新增，而是按提交日回填，避免第二天全部消失；
- 当期 HTML/MD 另存 `output/archive/<日期>.{html,md}`（**只增不改**），`/archive` 按日期回看；
- 同日重复跑是幂等的：`seen` 里首次期次就是本期的仍算本期，不会把页面清空。

## 四、行为学习

`profile.apply_event(sid, action)` 把每次点击折算成对画像的增量：

| 行为 | 效果 |
| --- | --- |
| 收藏 / 下载 / 展开摘要 / 打开 PDF | 提升该篇命中主题的倍率与关键词权重 |
| 取消收藏 | 反向学习（较弱） |
| Downvote | 该篇固定 -12；**默认不改写全局主题权重** |

为什么默认关掉负向学习（`learn_neg_topics / learn_neg_keywords = false`）：
曝光偏置会让「被推荐得多 → 被 Downvote 得多 → 主题权重被打到 0.25 下限」，
最终把你自己的研究方向压死（真实踩过坑，症状是推荐数突然归零）。
需要更强的负向学习可以自己在 `interests.json` 的 `behavior` 里打开。

## 五、页面与交互

单页 HTML（`build_report.py` 里内联 CSS + JS，无构建步骤、无外部依赖）：

- **Downvote 的视觉只有一处来源**：`.rec-card.down, .plist li.item.down, .hl.down, .fav-item.down`
  共用 `opacity .42` + 标题 `line-through`；三个模块（为你推荐 / 兴趣扩展 / 分类详解）
  都走同一个 `setDv()`。卡片**不隐藏**，而是钉在点击时的位次（`data-dvpos`）上，可再点一次撤销。
- **乐观更新**：点下即改按钮与卡片状态，请求在后台跑，失败回滚；重排由 `queueResort()`
  合并到 30ms 内一次，连点不会反复重排整屏。
- **视口稳定**：重排前记住当前可见论文的位置，重排后还原，避免「点一下跳回顶部」。
- 本地 HTML 用 `file://` 打开时，`APIBASE` 会把 `/api/*` 与站内链接改写成
  `http://127.0.0.1:8765` 的绝对地址（服务端 CORS `*`），所以离线文件也能点。

## 六、服务端并发

`server.py` 是 `ThreadingHTTPServer`，共享文件必须串行读-改-写，而网络下载**不能**占着库锁：

| 锁 | 覆盖范围 |
| --- | --- |
| `_lib_lock` | 仅 `library.json` / `profile_state.json` 的读-改-写（毫秒级） |
| `dl_lock(sid)` | 每篇论文一把：同一篇连点两次串行，不同篇并行 |
| `_papers_lock` | 论文索引缓存的刷新（双重检查，避免并发重复解析大 JSON） |

`/api/download_all` 用 `DL_WORKERS=3` 线程池并发。铁律：**任何网络 IO 都不许在 `_lib_lock` 内**，
否则一次下载就会把整页的收藏 / Downvote 全卡住（这是早期版本的真实故障）。

## 七、下载取数（为什么需要选路）

下载由本地服务进程发起。很多环境里同时存在多种出口，且只有一种能真正取到 arXiv：

| 出口 | 典型表现 |
| --- | --- |
| 直连 | `WinError 10054` 连接被重置 |
| 环境注入的 `HTTP(S)_PROXY` | CONNECT 成功但 TLS 流被掐断（`UNEXPECTED_EOF_WHILE_READING`） |
| 本机代理端口（如 7890） | 正常取到 `%PDF` |

`netroute.py` 按「`ARXIV_DL_PROXY` → 直连 → 环境代理 → 本机常见代理端口 → 其它在监听端口」
逐个探测，命中后写缓存；全不通时 45 秒内走负缓存，避免批量下载反复探测。
排错：`python netroute.py`，或服务在跑时 `GET /api/net_route`。

## 八、视频链路（可选）

`reel/` 是 Remotion 工程（1920×1080、30fps，代码渲染，不用生成式视频）：

```bash
python tools/gen_video_data.py --top 8 --expand 2   # 选片 + 生成 bullets/口播稿
python tools/gen_narration.py                        # Edge TTS 中文旁白（语速自适应）
cd reel && npm ci && npx remotion render src/index.ts PaperReel out/arxiv-weekly.mp4
python tools/check_video_av.py                       # A/V 闸门：时长、逐段人声、静音检测
```

依赖：Node 18+、`pip install edge-tts imageio-ffmpeg`。渲染前确认 `reel/src/audio.json`
的 `enabled=true`（入库基线是 `false`，否则会渲出无旁白版）。

## 九、初始化与预设

```
首次运行（文件缺失）              按需导入（显式命令）
config.example.json  ──生成──▶ config.json   ◀──复制──  presets/<名字>/config.json
interests.example.json ─生成─▶ interests.json ◀──复制──  presets/<名字>/interests.json
```

设计意图：仓库里只提交**模板**与**别人自愿公开的预设**；`config.json` / `interests.json`
属于个人数据（含本机路径与画像），默认被 `.gitignore` 排除。这样别人 clone 下来是干净的，
而想参考一份真实画像时又能一条命令导入（`tools/preset.py`）。

## 十、常见扩展点

| 想做什么 | 改哪里 |
| --- | --- |
| 加一个画像字段（比如「讨厌的系统名」） | `interests.json` 加字段 → `recommend.features()` 参与打分 → `/profile` 里加渲染 |
| 加一个分类 | `/profile` 或 `config.json` 的 `categories`，然后重抓；中文名走 `category_names` |
| 改 Downvote 的视觉 | `build_report.py` 里 `.rec-card.down` 那一组 CSS（一处改，三处生效） |
| 加一个页面 | `build_report.py` 的页面模板 + `server.py` 的 `do_GET` 路由 |
| 换推荐规则 | `recommend.py` 的 `features()` / `score()`；改完跑 `python recommend.py && python build_report.py` |

**改完必须重启服务**（`server.py` / `build_report.py` 的模板会被重新加载，但 `recommend.py`
的打分逻辑由流水线进程执行，服务进程不缓存它）。
