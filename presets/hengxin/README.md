# 预设：Hengxin Wei 的科研画像（示例）

这是**作者本人**正在用的一套设置，作为「一份真实可跑的画像长什么样」的参考。
它**不会**在默认初始化时生效——仓库默认给你的是干净模板（`config.example.json` /
`interests.example.json`），只有你显式导入才会覆盖本地设置。

## 里面有什么

| 文件 | 内容 |
| --- | --- |
| `config.json` | 6 个主分类（cs.DB / cs.DC / cs.FL / cs.LO / cs.PL / cs.SE）+ 18 个扩展分类 + 推荐条数等 |
| `interests.json` | 4 位画像主来源（本人 / Alexey Gotsman / Hagit Attiya / Constantin Enea）、14 个研究主题（含关键词）、61 位熟悉研究者、22 个代表系统、降权词 |
| `legacy/` | 当年一次性用过的迁移/种子脚本（把论文摘要与看点写进 `output/*.json`）。**正常运行不需要**，留作参考 |

## 怎么用

```bash
python tools/preset.py list                 # 看有哪些预设
python tools/preset.py import hengxin       # 导入（本地已存在同名文件时会拒绝，需 --force）
python tools/preset.py import hengxin --force   # 覆盖导入：先把原文件备份到 output/backup/<时间>/
```

导入后：

```bash
python run_daily.py --skip-fetch --skip-affil   # 用已有数据重算（首次用请去掉 --skip-fetch）
python server.py                                # 重启服务，页面才会读到新画像
```

## 导入前必改

1. `config.json` 的 `download_dir`：预设里给的是中性的 `papers/`，**改成你自己的目录**，
   也可以在 `/profile` 页的「下载目录」里改。
2. `config.json` 的 `categories`：作者只追数据库 / 分布式 / 形式化，别的方向请替换成自己的。
3. 导入是**整体覆盖**：你之前调好的主题与行为学习（`output/profile_state.json`）不会被重置，
   但 `interests.json` 里的主题关键词会被这份预设替换。想保留现状就先
   `python tools/preset.py export myown` 存一份。

## 关于隐私

这份预设来自作者本人的公开学术画像（研究兴趣、对标学者、常读作者），随仓库一起公开是为了
让新用户有个可参照的样例。**你自己的 `config.json` / `interests.json` 默认不会进版本库**
（`.gitignore` 已排除），除非你主动 `export` 成预设并提交。
