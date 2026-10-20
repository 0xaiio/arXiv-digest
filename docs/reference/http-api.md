# HTTP API 参考

本地服务（默认 `http://127.0.0.1:8765`）负责页面渲染与所有交互写操作。它是**单机服务**：
只监听 `127.0.0.1`，没有鉴权，不应暴露到公网。

实现分三层：`routes.py`（路径 → 处理函数、`Reply`/`Request`）、`service.py`（业务动作）、
`server.py`（解析与写 socket）。并发与锁的细节见[服务运行时](../architecture/server-runtime.md)，
模块职责见[模块职责](../architecture/modules.md)。

**路由清单可以程序化导出**：

```python
import routes
print(routes.table())      # {'get': [...], 'get_prefix': [...], 'post': [...]}
```

测试 `tests/unit/test_routes.py` 用它断言「路由没被误删」——新增接口时同步更新那份清单。

---

## 一、通用约定

| 项 | 约定 |
| --- | --- |
| 内容类型 | 请求与响应均为 `application/json; charset=utf-8`（页面路由除外） |
| 跨源 | 所有响应带 `Access-Control-Allow-Origin: *`，因此 `file://` 打开的日报也能调用 |
| 预检 | 支持 `OPTIONS`，返回 `204` |
| 请求体 | POST 一律 JSON 对象；字段缺失时按下文标注的默认值处理 |
| 成功 | `{"ok": true, ...}`，HTTP `200` |
| 参数不合法 | `{"ok": false, "msg": "..."}`，HTTP `400` |
| 未知接口 | `{"ok": false, "msg": "未知接口 <path>"}`，HTTP `404` |
| 内部异常 | `{"ok": false, "msg": "服务端异常：..."}`，HTTP `500`，同时把 traceback 打到服务进程 stderr |
| 论文标识 | 所有 `id` 字段都接受完整 arXiv 号或短号，服务端统一规范化（如 `arXiv:2609.09742v2` → `2609.09742`） |

## 二、页面路由（GET）

| 路由 | 返回 | 说明 |
| --- | --- | --- |
| `/`、`/index.html`、`/digest` | HTML | 最新一期日报。可用 `?f=arxiv_digest_<日期>.html` 指定某一期 |
| `/favorites` | HTML | 收藏清单，每次请求按 `library.json` **动态渲染**（模板改动立即生效） |
| `/profile` | HTML | 画像与设置页，每次请求动态渲染 |
| `/archive` | HTML | 存档总览（数据来自 `archive.db` + `output/archive/`） |
| `/archive/<YYYYMMDD>` | HTML | 某一期快照；日期格式非法 → `400`，无该期 → `404` |
| `/files/<name>` | 文件 | `output/` 下的静态文件（`basename` 处理后拼接，不可穿越目录） |

`/` 在还没有任何日报时返回 `404`，正文为 `尚无摘要页，请先运行 run_daily.py`。

## 三、只读接口（GET）

### `GET /api/ping`

健康检查，用于脚本判断服务是否在线。

```json
{ "ok": true }
```

### `GET /api/state`

一次取齐页面初始化所需的全部状态。

```json
{
  "favorites": ["2609.09742"],
  "downloads": { "2609.09742": "D:/papers/arXiv2026 2609.09742 Foo.pdf" },
  "downvotes": ["2609.10462"],
  "download_dir": "papers",
  "categories": ["cs.DB", "cs.DC"],
  "category_names": { "cs.DB": "数据库", "cs.DC": "分布式计算" },
  "profile": {
    "topics": ["事务与隔离级别", "一致性模型"],
    "weights": [1.32, 0.87],
    "kw": { "linearizability": 0.45, "blockchain": -2.1 },
    "pens": { "2609.10462": -12.0 }
  }
}
```

- `favorites` / `downvotes` 是短号数组；`downloads` 是 `短号 → 本地绝对路径`；
- `profile.topics` 与 `profile.weights` **按下标一一对应**（顺序即权重索引，前端靠它重排）；
- `profile.kw` 只包含绝对值 > 0.05 的关键词权重，避免响应过大。

### `GET /api/customize`

画像页的完整数据：定制项 + 画像视图。

```json
{
  "categories": ["cs.DB"],
  "category_names": { "cs.DB": "数据库" },
  "download_dir": "papers",
  "sources": [ { "sid": "s1759...", "type": "link", "value": "https://...", "note": "", "derived": { } } ],
  "derived": { "people": [], "keywords": [], "matched_topics": [] },
  "blocked_keywords": [],
  "updated_at": "2026-10-17 09:12:04",
  "profile": {
    "owners": [ { "name": "...", "label": "...", "site": "...", "affiliation": "...",
                  "interests": "...", "signature_topics": [], "people_linked": true } ],
    "themes": [ { "name": "...", "seed": 1.0, "mult": 1.32, "weight": 1.32,
                  "nkw": 12, "keywords": ["..."], "custom": false } ],
    "people": ["..."],
    "systems": ["..."],
    "negative": ["blockchain"],
    "counts": { "favorite": 12, "download": 30 },
    "downvoted": ["2609.10462"],
    "updated_at": "2026-10-17 09:12:04"
  }
}
```

`themes[].weight = seed × mult`。**`themes` 的顺序即权重索引顺序**，前端不要重排。

### `GET /api/profile`

`/api/state` 里 `profile` 字段的内容（单独取用）。

### `GET /api/library`

原样返回 `output/library.json`（`favorites` / `downloads` / `downvotes` 三个对象）。
字段含义见 [数据文件](data-files.md)。

### `GET /api/datapacks`

可用数据包 + 本机个人数据清单。**只返回"形状"，不返回包内容**——包的标题与描述
往往就是作者的类别选择与研究方向，属于要隔离的内容（见
[私人数据隔离](../architecture/data-isolation.md)）。

```json
{
  "packs": [
    { "name": "hengxin",
      "files": ["config.json", "interests.json"],
      "groups": { "core": ["config.json", "interests.json"] },
      "bytes": 17866 }
  ],
  "state": {
    "files": {
      "library.json": { "group": "usage", "exists": true, "bytes": 189712,
                        "updated_at": "2026-10-20 10:44:05" }
    },
    "has_personal_data": true
  },
  "groups": ["core", "usage", "learning", "notes"],
  "defaults": ["core", "usage", "notes"]
}
```

`state.files` **不含绝对路径**（接口输出会进浏览器，路径属本机信息）；
要排障看路径用 `python paths.py`。

### `GET /api/archive/days`

```json
  "issues": [ { "date": "20261017", "n_new": 164, "n_rec": 14, "n_exp": 10 } ],
  "dates": ["20261017", "20261016"],
  "stats": { "issues": 33, "papers": 4310, "db": "...", "archive_dir": "..." }
}
```

### `GET /api/net_route`

下载路由诊断。`/api/download` 失败时先看这里。

```json
{
  "ok": true,
  "route": "http://127.0.0.1:7890",
  "proxy": "http://127.0.0.1:7890",
  "cache": ".../output/netroute.json",
  "cands": 7,
  "last_failure": null
}
```

`ok=false` 表示当前没有可用出口；`cands` 是候选路由数；`last_failure` 是上一次失败的摘要。

## 四、写接口（POST）

### 收藏 / Downvote

| 接口 | 请求体 | 响应 | 副作用 |
| --- | --- | --- | --- |
| `POST /api/favorite` | `{"id": "<短号>", "note": "可选备注"}` | `{ok, favorited: true, id, profile}` | 写入 `library.favorites`；**自动撤销该篇的 Downvote**；正向学习 |
| `POST /api/unfavorite` | `{"id": "..."}` | `{ok, favorited: false, id, profile}` | 从收藏中移除；反向学习（较弱） |
| `POST /api/downvote` | `{"id": "..."}` | `{ok, downvoted: true, id, profile}` | 写入 `library.downvotes`；该篇画像惩罚 -12 |
| `POST /api/undownvote` | `{"id": "..."}` | `{ok, downvoted: false, id, profile}` | 撤销惩罚与灰化 |

`POST /api/favorite`、`/api/downvote` 缺少 `id` 时返回 `400 {"ok": false, "msg": "缺少 id"}`。

### `POST /api/event`

记录非写库的弱信号（页面上的 Abstract / PDF / 打开）。

```json
{ "id": "2609.09742", "action": "abstract" }
```

`action` 必须是 `abstract` | `pdf` | `open` | `expand` 之一，否则 `400`。
响应：`{ok, id, action, profile}`。

### `POST /api/download`

```json
{ "id": "2609.09742", "force": false }
```

响应：

```json
{ "ok": true, "msg": "", "path": "papers/arXiv2026 2609.09742 Foo.pdf",
  "id": "2609.09742", "favorited": true, "profile": { } }
```

- 成功后写入 `library.downloads` 并**自动收藏**；
- 文件已存在时视为成功（除非 `force=true` 重新下载）；
- 失败时 `ok=false`，`msg` 为**面向人的中文原因**（如"未找到论文元数据"/网络错误摘要）。
  路由层面的排查看 [`GET /api/net_route`](#get-apinet_route)；
- 并发语义：**只持有该篇的下载锁**，因此一篇正在下载不影响另一篇的操作。

### `POST /api/download_all`

```json
{ "ids": ["2609.09742", "2609.10462"], "force": false }
```

响应：

```json
{ "ok": true, "n_ok": 1,
  "results": [ { "id": "2609.09742", "ok": true, "path": "...", "msg": "" },
               { "id": "2609.10462", "ok": false, "path": "",  "msg": "..." } ],
  "profile": { } }
```

最多 `DL_WORKERS = 3` 路并发；`results` 的顺序与请求 `ids` 一致。单项失败不影响其它项。

### 画像与配置

| 接口 | 请求体 | 说明 |
| --- | --- | --- |
| `POST /api/owner` | `{"op":"add", "name":..., "label":..., "site":..., "affiliation":..., "interests":..., "signature_topics":[...], "link_person":true}`<br>`{"op":"update", "orig":"<原名>", ...}`<br>`{"op":"remove", "name":"..."}` | 画像主来源增删改。`update` 用 `orig` 定位、可改名；`link_person` 控制是否同步计入熟悉研究者 |
| `POST /api/category` | `{"op":"add", "cat":"cs.PL", "name":"可选"}`<br>`{"op":"add_many", "cats":["cs.LG","cs.IR"]}`<br>`{"op":"remove", "cat":"cs.PL"}`<br>`{"op":"reorder", "order":["cs.PL","cs.DB"]}`<br>`{"op":"set", "cats":[...], "allow_empty":false}` | 类别增删改排序（详见下方）。**新增分类需要重新抓取**才会出现该分类论文 |
| `POST /api/config` | `{"download_dir": "D:/papers"}` | 修改下载目录（唯一真源）。相对路径解析到项目根 |
| `POST /api/source` | `{"op":"add", "type":"link\|paper\|doc", "value":"...", "note":""}`<br>`{"op":"remove", "sid":"s1759..."}`<br>`{"op":"refresh"}`<br>`{"op":"block", "kw":"..."}` / `{"op":"unblock", "kw":"..."}` | 兴趣来源与来源关键词屏蔽。`refresh` 重解析全部来源 |

除 `/api/category`、`/api/config` 外，上述接口统一返回：

```json
{ "ok": true, "msg": "", "info": null, "state": { /* 与 GET /api/customize 同结构 */ } }
```

前端拿到 `state` 后重画整块区域，不需要额外再发一次 GET。

### `POST /api/category`

类别是**有序列表**（顺序 = 摘要页分类小节顺序），因此除了增删还有排序与整体替换。

| `op` | 请求体 | 行为 / 错误 |
| --- | --- | --- |
| `add` | `{"cat":"cs.PL","name":"可选中文名"}` | 校验 → 去重 → 追加到末尾。非法或重复返回 `ok:false` 与原因 |
| `add_many` | `{"cats":["cs.LG","cs.IR"]}` | 多选下拉一次提交。**部分成功**：合法的照加，非法/重复的逐条回报（`info.added` / `info.duplicates` / `info.invalid`） |
| `remove` | `{"cat":"cs.PL"}` | 删除一个；只剩一个时拒绝（`至少要保留一个分类`） |
| `reorder` | `{"order":["cs.PL","cs.DB"]}` | 拖拽排序。`order` 必须是当前集合的**一个排列**，少一项/多一项/重名都会被拒绝且不改动配置 |
| `set` | `{"cats":[...],"allow_empty":false}` | 整体替换（导入、清空重建）。默认不允许替换成空数组 |

校验规则（大小写、点号、是否在官方表内、近邻纠错）见 [arXiv 类别](categories.md#validation)。
响应同样带完整 `state`，其中 `state.category_meta` 是前端渲染标签用的有序元数据：

```json
{
  "ok": true, "msg": "已添加 2 个分类：cs.LG、cs.IR",
  "info": {"added": ["cs.LG", "cs.IR"], "duplicates": [], "invalid": []},
  "state": {
    "categories": ["cs.DB", "cs.LG", "cs.IR"],
    "category_meta": [
      {"cat": "cs.DB", "name": "数据库", "archive": "cs", "known": true},
      {"cat": "cs.LEGACY", "name": "", "archive": "cs", "known": false}
    ]
  }
}
```

`known:false` 表示该分类不在官方表内（手改过 `config.json`，或 arXiv 下线了它）——
界面把标签标成警告色，但**不会**替你删掉。

### `GET /api/arxiv_categories`

arXiv 官方分类全表，是 `/profile` 两个联动下拉框的数据源（页面渲染时也会内嵌同一份 JSON，
所以即使这个接口不可用，下拉框仍能工作）。

```json
{
  "version": "2026-10",
  "source": "https://arxiv.org/category_taxonomy",
  "total": 155,
  "archives": [
    {"id": "cs", "en": "Computer Science", "zh": "计算机科学", "single": false,
     "categories": [{"id": "cs.AI", "en": "Artificial Intelligence", "zh": "人工智能"}]},
    {"id": "quant-ph", "en": "Quantum Physics", "zh": "量子物理", "single": true,
     "categories": [{"id": "quant-ph", "en": "Quantum Physics", "zh": "量子物理"}]}
  ]
}
```

`single:true` 的 archive 只有唯一分类且无点号（`quant-ph` / `hep-th` / `gr-qc` 等 9 个）。

### `POST /api/preset`

导入 / 导出数据包。**导入语义全部在 `datapack.import_pack`**，接口只做参数归一化与状态码。

| 请求体 | 行为 | 响应 |
| --- | --- | --- |
| `{"op":"import","name":"hengxin"}` | 导入 `presets/hengxin/` 的 core + usage + notes | `{ok, msg, report, state}` |
| `{"op":"import","name":"hengxin","force":true}` | 允许覆盖本机 `config.json` / `interests.json`（先备份到 `output/backup/<时间>/`） | 同上 |
| `{"op":"import","name":"hengxin","groups":["core"]}` | 只导入指定分组（`groups` 也可传逗号分隔字符串） | 同上 |
| `{"op":"export","name":"mine","groups":["core"]}` | 把本机运行态导出成包（界面不提供入口，留给脚本） | 同上 |

- 成功 `200`；**任何一个文件被拒绝就返回 `400`**（`ok:false`），`msg` 里带逐文件原因，
  例如「本机已有不同内容（加 --force 覆盖，会先备份）」；
- `core` 文件若仍是模板初值（与 `*.example.json` 一致），无需 `force` 直接替换——
  否则新用户点「导入」永远失败；
- 包名非法（含 `/`、`..`、以 `.` 开头）→ `400`，不触碰任何文件；
- `report` 是逐文件结果：`[{file, group, action, reason, bytes}]`，
  `action ∈ {written, replaced, merged, skipped, refused}`；
- 导入成功后界面应刷新（`state` 已是最新），摘要页仍需 `POST /api/rebuild` 才会重排。

```json
{
  "ok": true,
  "msg": "已处理 2 个文件",
  "report": [
    {"file": "config.json", "group": "core", "action": "replaced",
     "reason": "--force 覆盖（已备份）", "bytes": 993},
    {"file": "interests.json", "group": "core", "action": "skipped",
     "reason": "内容与本机一致", "bytes": 16873}
  ],
  "state": { "categories": ["cs.DB"], "profile": { } }
}
```

### `POST /api/rebuild`

重跑 `recommend.py` + `build_report.py`（**不重新抓取**），用于改完画像后立即生效。

```json
{ "ok": true, "msg": "已重算", "state": { } }
```

内部有重建锁，重复点击不会并发出两个流水线。

### `POST /api/open` / `POST /api/open_folder`

| 接口 | 请求体 | 行为 |
| --- | --- | --- |
| `POST /api/open` | `{"id": "..."}` | 用系统默认程序打开已下载的 PDF；文件不存在 → `{ok:false, msg:"文件不存在：<path>"}` |
| `POST /api/open_folder` | `{"dir": "可选"}` | 打开下载目录（不存在则创建） |

这两个接口只在**本机桌面环境**有意义；无 GUI 的环境里 `os.startfile` 会抛异常并退化为
`explorer` 调用，最终可能返回成功但什么也没发生。

## 五、用脚本调用示例

```bash
# 收藏一篇
curl --noproxy '*' -X POST http://127.0.0.1:8765/api/favorite \
     -H 'Content-Type: application/json' -d '{"id":"2609.09742"}'

# 批量下载
curl --noproxy '*' -X POST http://127.0.0.1:8765/api/download_all \
     -H 'Content-Type: application/json' \
     -d '{"ids":["2609.09742","2609.10462"]}'

# 导出当期推荐短号
curl --noproxy '*' http://127.0.0.1:8765/api/library
```

> `--noproxy '*'` 不能省：部分环境把 `127.0.0.1` 也交给 HTTP 代理，会被拦成 `502`。

## 六、兼容性与变更策略

- 新增字段是**兼容变更**，可以直接发；前端按需读取；
- 删除字段、改字段语义、改状态码属于**破坏性变更**，会同时更新本页与
  [CHANGELOG](https://github.com/0xaiio/arXiv-digest/blob/main/CHANGELOG.md)；
- 本项目不承诺跨版本 API 稳定性（它是单机工具，前端与后端总是一起更新）。

---

相关：[服务运行时](../architecture/server-runtime.md) · [数据文件](data-files.md) ·
[config.json](config.md)
