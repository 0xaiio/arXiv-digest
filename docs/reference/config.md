# config.json 参考

`config.json` 管"抓什么、存哪里、每期几条"。它由 `config.example.json` 在**首次运行**时自动生成，
之后就是你的个人数据，不进版本库（`.gitignore` 已排除）。

画像相关的配置在另一个文件：[interests.json](interests.md)。

---

## 一、文件的位置与生成规则

| 项 | 值 |
| --- | --- |
| 路径 | 项目根 `config.json` |
| 模板 | `config.example.json`（机器无关，**不要改这个文件**） |
| 生成时机 | `paperutil.load_config()` 首次调用且目标文件不存在时 |
| 覆盖规则 | 文件已存在则**完全以你的文件为准**，不会被模板覆盖 |
| 缺字段 | 回落到代码内 `DEFAULT_CONFIG`（与模板略有差异，见下表注） |
| 页面上改 | `/profile` →「arXiv 类别」「下载目录」 |

生成时会打印一行提示：

```
[init] 已按 config.example.json 生成 config.json。请按需修改 categories（跟踪的分类）与 download_dir（PDF 保存目录）。
```

## 二、字段

| 字段 | 类型 | 模板默认 | 说明 |
| --- | --- | --- | --- |
| `download_dir` | string | `"papers"` | PDF 保存目录。**唯一真源**——页面显示、下载、`/api/open` 都读它。相对路径相对项目根，绝对路径原样使用；不存在会自动创建 |
| `categories` | string[] | `["cs.AI","cs.CL","cs.LG","cs.SE"]` | **主分类**：每日必抓，「为你推荐」与「分类详解」都来自这里 |
| `category_names` | object | 见模板 | 分类中文名，只影响显示。未命中时 `customize` 内置词典兜底，仍无则显示分类号 |
| `window_days` | int | `3` | 抓最近几天的公告。arXiv 每工作日 20:00 ET 公告一次，3 天可覆盖周末 |
| `max_results_per_cat` | int | `80` | 每个主分类单次最多抓多少条 |
| `top_recommend` | int | `14` | 「为你推荐」显示条数（同时也是候选池上限） |
| `top_expand` | int | `10` | 「兴趣扩展」显示条数 |
| `expand_categories` | string[] | 15 个（见模板） | **扩展分类池**：只用于「兴趣扩展」区，不进入主推荐 |
| `expand_window_days` | int | `3` | 扩展抓取的时间窗 |
| `expand_max_results` | int | `600` | 扩展抓取的全局上限（所有扩展分类合计，防止请求过大） |
| `affil_targets` | int | `60` | 每期最多解析多少篇的作者单位（约 3 秒/篇，很慢；`--skip-affil` 可整步跳过） |
| `port` | int | `8765` | 本地服务端口。`server.py`、`start_digest.bat`、`run_daily.py` 都读这里 |

> 注：代码内 `DEFAULT_CONFIG` 只包含最小集（`download_dir`/`categories`/`window_days`/
> `max_results_per_cat`/`top_recommend`/`port`），其余字段由模板提供。**以模板为准**；
> 若你手写了一个只含部分字段的 `config.json`，缺失项走代码默认值。

## 三、两类分类的分工

```
config.categories          → fetch_arxiv.py  → raw.json        → 「🎯 为你推荐」+「📖 分类详解」
config.expand_categories   → fetch_expand.py → raw_expand.json → 「🌱 兴趣扩展」
```

两条链路在 `recommend.py` 里按**短号严格去重**：出现在主分类 feed 里的论文不会再进扩展区。
所以同一篇论文不会同时出现在两个板块。

选择建议：

| 你的情况 | `categories` | `expand_categories` |
| --- | --- | --- |
| 只盯 1–2 个方向 | 就填这 1–2 个 | 留空或填几个相邻分类 |
| 主方向 + 邻域视野 | 主方向 2–4 个 | 邻域 10–20 个（默认 15 个就够） |
| 跨领域（如 ML + 系统） | 两边各取 2–3 个 | 其余作为第三层扩展 |

## 四、改配置之后会发生什么

| 改动 | 需要做什么 | 为什么 |
| --- | --- | --- |
| `categories` 新增分类 | **重新抓取**（`python run_daily.py`） | 本地没有该分类的历史数据 |
| `categories` 删除分类 | 下次抓取生效 | 已抓到的数据仍留在 `output/` 里，本期页面不会立刻变化 |
| `expand_categories` 任意改 | 重新抓取 | 扩展池来自独立抓取 |
| `top_recommend` / `top_expand` | 重渲染（`--skip-fetch --skip-affil`） | 只是显示条数 |
| `download_dir` | 立即生效 | 每次下载都重新读配置 |
| `port` | 重启服务 | 端口在进程启动时绑定 |
| `window_days` | 重新抓取 | 影响抓取窗口 |
| `affil_targets` | 重新抓取单位（`fetch_affil.py`） | 每期解析上限 |

## 五、手工编辑示例

```jsonc
{
  "download_dir": "D:/papers/arxiv",     // 绝对路径；相对路径写 "papers"
  "categories": ["cs.PL", "cs.LO", "cs.SE"],
  "category_names": { "cs.PL": "编程语言", "cs.LO": "逻辑" },
  "window_days": 3,
  "max_results_per_cat": 80,
  "top_recommend": 12,
  "top_expand": 8,
  "expand_categories": ["cs.DB", "cs.DC", "cs.FL", "cs.DS", "math.LO"],
  "expand_window_days": 3,
  "expand_max_results": 400,
  "affil_targets": 40,
  "port": 8765
}
```

> JSON 不支持注释。上面用 `//` 只是为了说明，实际文件里请去掉。

## 六、相关环境变量

| 变量 | 作用 |
| --- | --- |
| `ARXIV_DL_PROXY` | 强制指定下载 PDF 使用的代理（如 `http://127.0.0.1:7890`），跳过自动选路。见[服务运行时](../architecture/server-runtime.md) |

端口、下载目录、代理都优先走配置文件；这个变量只在自动探测失败时作为强力手段使用。

---

相关：[interests.json](interests.md) · [数据文件](data-files.md) · [预设](../guide/presets.md) ·
[命令行](cli.md)
