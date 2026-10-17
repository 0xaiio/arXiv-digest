# 预设：导入一份现成设置

预设 = 一整套 `config.json` + `interests.json`（可含 `meta.json` 说明与 `legacy/` 历史脚本）。
仓库里只放**作者自愿公开**的预设，**默认不加载**——你 clone 下来得到的始终是干净模板。

## 目录约定

```
presets/
└─ hengxin/
   ├─ meta.json        # 可选：{ "title", "description", "exported_at" }，用于 list 展示
   ├─ README.md        # 可选：这份预设的来历与注意事项
   ├─ config.json      # 可选：分类、下载目录、推荐条数
   ├─ interests.json   # 可选：画像（主题 / 熟悉作者 / 代表系统 / 降权词 / 主来源）
   └─ legacy/          # 可选：该预设配套的一次性脚本，正常运行不需要
```

只要目录里至少有一个 `config.json` 或 `interests.json`，`tools/preset.py list` 就能发现它。

## 命令

```bash
python tools/preset.py list                     # 列出预设 + 摘要
python tools/preset.py import hengxin           # 导入（本地已有同名文件 → 拒绝并提示）
python tools/preset.py import hengxin --force   # 覆盖导入：先备份到 output/backup/<时间>/
python tools/preset.py export myown             # 把当前 config.json / interests.json 存成预设
```

导入后的生效方式：

```bash
python run_daily.py --skip-fetch --skip-affil   # 重算 + 重渲染（首次用请去掉 --skip-fetch）
python server.py                                 # 重启服务，页面才会读到新画像
```

`/profile` 的页面数据是每次请求实时读文件的，所以只改画像不必重启；但**摘要页**是上次
渲染的静态文件，必须重跑 `build_report.py`（或点页面上的「↻ 重算推荐」）。

## 导入前必改的三件事

1. **`download_dir`**：预设里是别人机器上的路径（例如 `D:/papers`）。
   导入后到 `/profile` → 「下载目录」改成你自己的，或先编辑 `presets/<名字>/config.json`。
2. **`categories`**：作者追的分类不等于你的方向。换成你自己每天要看的 2–6 个分类。
3. **`interests.json` 会被整体替换**：你之前调好的主题关键词会没掉（`output/profile_state.json`
   里的行为学习记录**不会**被重置）。想保留现状先 `python tools/preset.py export myown`。

## 仓库自带的预设

| 预设 | 内容 | 适合谁 |
| --- | --- | --- |
| `hengxin` | 数据库系统 / 分布式计算 / 形式化方法：4 位画像主来源、14 个主题、61 位熟悉研究者、22 个代表系统；6 个主分类 + 18 个扩展分类 | 想看看「一份调了半年的画像长什么样」，或方向相近想直接起步 |

`hengxin` 里的 `legacy/` 是作者当年用过的一次性脚本（补摘要、迁移 key、改下载目录），
只作参考，正常运行用不到。

## 自己造一份预设

1. 在 `/profile` 里把画像调舒服，跑几期；
2. `python tools/preset.py export <你的名字>`；
3. 编辑 `presets/<你的名字>/meta.json`（标题 / 一句话描述）与 `README.md`；
4. **确认里面没有隐私**（本机路径、单位、个人邮箱等），再提交。

> 提示：`config.json` 里通常带本机下载路径。分享前请把 `download_dir` 改成中性值
> （例如 `"papers"`），别人导入后再各自改成自己的。
