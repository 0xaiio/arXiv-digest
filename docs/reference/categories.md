# arXiv 类别

本工具**不预设任何研究领域**：抓哪些分类由你在 `/profile` 的「🗂 arXiv 类别」面板里决定。
这一页说明分类从哪来、怎么选、怎么校验、顺序怎么生效。

---

## 一、分类表从哪来

官方真源是 <https://arxiv.org/category_taxonomy>，项目把它固化成一份 Python 常量表：
**`arxiv_cats.py`**。

| 项 | 值 |
| --- | --- |
| 快照版本 | `arxiv_cats.TAXONOMY_VERSION`（当前 `2026-10`） |
| 规模 | 20 个 archive（主类）+ 155 个分类 |
| 结构 | `abc` = archive（`cs` / `math` / `physics` / `stat` / `quant-ph` …），`def` = archive 内的分类后缀（`DB` / `LO` / `stat-mech`） |
| 单段分类 | 9 个 archive 只有唯一分类且与 archive 同名（`gr-qc`、`hep-ex`、`hep-lat`、`hep-ph`、`hep-th`、`math-ph`、`nucl-ex`、`nucl-th`、`quant-ph`），它们**没有点号** |

分类是**数据而不是代码逻辑**：arXiv 增删分类时只改 `arxiv_cats.py` 里的 `_ARCHIVES`，
界面、校验、扩展池推导会一起跟上。

自检：

```bash
python arxiv_cats.py       # 打印 20 个 archive / 155 个分类，并校验每个分类号都符合格式规则
```

## 二、界面上怎么选

`/profile` →「🗂 arXiv 类别」面板，三个入口并存：

| 入口 | 交互 | 适合 |
| --- | --- | --- |
| ① 主类 abc + ② 子类 def | 两个**联动**下拉框：先勾主类，第二级只剩该 archive 的分类；两个框都有搜索框（分类号 / 英文名 / 中文名）；**都可多选**，勾完点「+ 加入类别列表」一次提交 | 浏览式选择（推荐） |
| 已选标签 | 每个分类一个标签，显示 `abc.def` + 中文名；标签左侧圆点是**拖拽手柄**，拖动即排序；右侧 × 删除 | 排序与清理 |
| 手动输入 | 直接敲分类号，边打边校验（合法变绿并显示中文名，非法变红并说明原因） | 明确知道要加哪个分类 |

几个刻意的设计：

- **多选**：勾 3 个只发 1 个请求（`POST /api/category {op:"add_many"}`），不是 3 个；
- **已加入的项在下拉里禁用**并标「已在列表」，避免重复点击；
- **非法分类不会被静默修正**：`CS.DB` 会被告知「区分大小写，正确写法是 cs.DB」，`cs.ZZ` 会被告知不是官方分类（有近邻时才给「你是不是指 …」）；
- **手改坏的历史配置不会被丢弃**：`config.json` 里出现官方表没有的分类时，标签变黄并给出提示，删除由你决定。

## 三、校验规则 {#validation}

校验的**唯一入口**是 `arxiv_cats.validate()`（服务端），前端 `checkCat()` 用同一套规则做即时反馈。
判定顺序：

| 顺序 | 输入 | 结论 |
| --- | --- | --- |
| 1 | 空 / 全空白 | `分类不能为空` |
| 2 | 大小写写错（`CS.DB`、`cs.db`） | `arXiv 分类区分大小写，正确写法是 cs.DB` |
| 3 | 不符合 `^[a-z][a-z-]*(\.[A-Za-z][A-Za-z-]*)?$` | 说明正确格式（`abc.def` 或单段归档） |
| 4 | 只写了主类（`cs`、`physics`） | `cs 是主类（archive），还需要选择子类，例如 cs.AI` |
| 5 | 主类不存在（`csdb`、`css.DB`） | `不是 arXiv 官方分类：…`，主类写错时提示 20 个 archive 之一 |
| 6 | 主类对、后缀不存在（`cs.DBB`） | 给出近邻建议（按**后缀段**相似度，`cs.ZZ` 不会被硬凑成 `cs.SY`） |
| 7 | 在官方表内 | 通过 |

格式规则的两个易错点：

- 主类段**必须小写**（`cs`、`cond-mat`、`q-bio`）；
- 后缀段**大小写混合**是合法的（`cs.DB`、`cond-mat.stat-mech`、`physics.acc-ph`）。

## 四、顺序即页面顺序

`config.json` 的 `categories` 是**有序数组**：

```
categories: ["cs.PL", "cs.DB"]  →  摘要页分类小节的顺序也是 cs.PL → cs.DB
```

拖拽排序后点摘要页的「↻ 重算推荐」，顺序立刻反映到页面（`build_report` 渲染时按 config 顺序重排抓取快照，
快照里多出来的分类追加在后，不会被丢掉）。

## 五、与「兴趣扩展」的关系

`expand_categories` 留空时，扩展池由所选分类**自动推导**：取同一 archive 内的兄弟分类。
所以选 `cs.DB` 得到其余 39 个 `cs.*`；选 `math.LO` 得到其余 `math.*`；跨 archive 混选则取并集。

单类 archive（`quant-ph` 等 9 个）没有兄弟分类，扩展池为空 —— 「🌱 兴趣扩展」本轮不显示内容，
属正常现象。想要扩展内容就手填 `expand_categories`。

## 六、示例配置

仓库里的 `presets/hengxin/` 是**一位使用者**的配置（数据库 / 分布式 / 形式化方法方向，
6 个主分类 + 18 个扩展分类）。它只是**示例**，默认不加载：

```bash
python tools/preset.py list
python tools/preset.py import hengxin --force     # 先备份你的本地配置
```

首次 clone 打开的 `config.json` 里 `categories` 是**空数组**，页面上不会出现任何分类标签。

---

相关：[config.json](config.md) · [HTTP API](http-api.md) · [预设](../guide/presets.md) ·
[调优画像](../guide/profile-tuning.md)
