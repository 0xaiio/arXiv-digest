# 预设：导入一份现成设置

预设（preset）= 一整套 `config.json` + `interests.json`（可附带 `meta.json` 说明、`README.md`、
`legacy/` 历史脚本）。仓库里只放**作者自愿公开**的预设，**默认不加载**——
你 clone 下来得到的始终是干净模板。

---

## 一、目录约定

```
presets/
└─ hengxin/
   ├─ meta.json        # 可选：{ "title", "description", "exported_at" }，用于 list 展示
   ├─ README.md        # 可选：这份预设的来历与注意事项
   ├─ config.json      # 可选：分类、下载目录、推荐条数
   ├─ interests.json   # 可选：画像（主题 / 熟悉作者 / 代表系统 / 降权词 / 主来源）
   └─ legacy/          # 可选：该预设配套的一次性脚本，正常运行不需要
```

只要目录里至少存在 `config.json` 或 `interests.json`，`tools/preset.py list` 就能发现它。

## 二、命令

```bash
python tools/preset.py list                     # 列出预设 + 摘要（含包含哪些文件）
python tools/preset.py import hengxin           # 导入；本地已有同名文件 → 拒绝并提示
python tools/preset.py import hengxin --force   # 覆盖导入：先备份到 output/backup/<时间>/
python tools/preset.py export myown             # 反向：把当前设置存成预设（可提交分享）
```

导入后的生效方式：

```bash
python run_daily.py --skip-fetch --skip-affil   # 重算 + 重渲染（首次使用请去掉 --skip-fetch）
```

分工要清楚：`/profile` 的数据是**每次请求实时读文件**，改画像不必重启服务；
**摘要页是上次渲染的静态文件**，必须重跑 `build_report.py` 或点页面上的「↻ 重算推荐」。

## 三、导入前必改的三件事

1. **`download_dir`**：预设里是别人机器上的路径。导入后到 `/profile` →「下载目录」改成你自己的，
   或先编辑 `presets/<名字>/config.json`。相对路径（`papers`）解析到项目根下。
2. **`categories`**：作者追的分类不等于你的方向。到 `/profile` →「🗂 arXiv 类别」换成你每天真要看的 2–6 个
   （两个联动下拉框 + 可拖拽标签，见 [arXiv 类别](../reference/categories.md)）。
3. **`interests.json` 会被整体替换**：你之前调好的主题关键词会没掉。
   `output/profile_state.json`（行为学习记录）**不会**被重置——导入后你的历史点击仍在起作用，
   可能与新画像叠加。想干净重来就先删掉它。

> 怕丢现状？导入前先 `python tools/preset.py export myown`。

## 四、仓库自带的预设

| 预设 | 内容 | 适合谁 |
| --- | --- | --- |
| `hengxin` | 数据库系统 / 分布式计算 / 形式化方法：4 位画像主来源、14 个主题、61 位熟悉研究者、22 个代表系统；**6 个主分类（cs.DB / cs.DC / cs.FL / cs.LO / cs.PL / cs.SE）+ 18 个扩展分类** | 想看看"调了半年的画像长什么样"，或方向相近想直接起步 |

`hengxin/legacy/` 是作者当年用过的一次性脚本（补摘要、迁移 key、改下载目录），只作参考，
正常运行用不到；`migrate_download_dir.py` 已改为从环境变量读路径，不再硬编码本机目录。

## 五、自己造一份预设

1. 在 `/profile` 里把画像调舒服，跑几期，让行为学习把倍率练出来；
2. `python tools/preset.py export <你的名字>`；
3. 编辑 `presets/<你的名字>/meta.json`（标题 / 一句话描述）与 `README.md`；
4. **确认里面没有隐私**，再提交。

分享前的隐私检查（逐项过一遍）：

| 检查项 | 为什么 |
| --- | --- |
| `config.json` 的 `download_dir` | 常含本机绝对路径与用户名，改成 `papers` |
| `interests.json` 的 `owners[].site` / `affiliation` | 公开主页可以，但要确认你愿意公开 |
| 任何 `output/` 内容 | 已整体被忽略，不要 `git add -f` 强加 |
| `.secrets/`、`*cookie*.json` | 登录凭据，永不入库 |
| 备注 / `note` 字段 | 可能含个人邮箱、内部项目名 |

## 六、预设与"个人数据"的关系

| 文件 | 是否入库 | 说明 |
| --- | --- | --- |
| `config.example.json` / `interests.example.json` | ✅ | 模板，机器无关 |
| `presets/<名字>/config.json` / `interests.json` | ✅（自愿） | 别人可导入的成品设置 |
| `config.json` / `interests.json` | ❌（`.gitignore`） | 你的本地个人数据 |
| `output/`、`.secrets/` | ❌ | 运行产物与凭据 |

设计意图：仓库里只提交**模板**与**别人自愿公开的预设**，任何人 clone 下来都是干净的；
想参考一份真实画像时又能一条命令导入。

---

相关：[config.json 参考](../reference/config.md) · [interests.json 参考](../reference/interests.md) ·
[目录职责](../meta/structure.md) · [FAQ](../meta/faq.md)
