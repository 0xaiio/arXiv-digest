# 数据包（预设）：导入一份现成设置

**数据包**（旧称「预设」）= 某个人的一整套设置与使用数据，收在 `presets/<名字>/` 里，
全部是 JSON 文本。它**默认不加载**：你 clone 下来得到的始终是干净模板，包只有在你
点名导入之后才会写进本机运行态。

设计与取舍见 [私人数据隔离](../architecture/data-isolation.md)；本文只讲怎么用。

---

## 一、目录与文件契约

```
presets/
└─ hengxin/
   ├─ manifest.json        # 清单：schema 版本 / 分组 / 每个文件的字节数与 sha256
   ├─ config.json          # core：类别、下载目录、推荐条数
   ├─ interests.json       # core：画像（主题 / 熟悉作者 / 代表系统 / 降权词 / 主来源）
   ├─ library.json         # usage（可选）：收藏 / 下载记录 / Downvote
   ├─ profile_state.json   # learning（可选）：行为学习的聚合结果
   ├─ behavior.json        # learning（可选）：行为流水
   ├─ summaries.json       # notes（可选）：中文摘要
   ├─ rec_notes.json       # notes（可选）：推荐理由
   ├─ highlights.json      # notes（可选）：看点
   ├─ README.md            # 人读的说明（界面刻意不渲染包内容，这里是唯一入口）
   └─ legacy/              # 该包配套的一次性脚本（可选，不参与导入）
```

只要目录里至少有一个已知文件，`tools/preset.py list` 就能发现它。`manifest.json` 缺失也能导入，
只是不做 `sha256` 校验（旧版包兼容）。

四个分组决定了**导入时怎么处理冲突**：

| 分组 | 文件 | 导入语义 | 默认 |
| --- | --- | --- | --- |
| `core` | `config.json`、`interests.json` | 整文件替换；**本机已有不同内容时拒绝**，需 `--force` | ✅ |
| `usage` | `library.json` | **并集**，同名条目保留本机（本机路径才有效） | ✅ |
| `notes` | `summaries.json`、`rec_notes.json`、`highlights.json` | **并集**，同名条目保留本机 | ✅ |
| `learning` | `profile_state.json`、`behavior.json` | 覆盖（先备份）；它是本机训练出来的结果 | ❌ |

## 二、三个入口，同一套语义

### 1) 命令行

```bash
python tools/preset.py list                  # 有哪些包、标题、文件清单、体积
python tools/preset.py show hengxin          # 逐文件对比本机：新增 / 一致 / 需 --force
python tools/preset.py import hengxin        # 导入（core + usage + notes）
python tools/preset.py import hengxin --force        # 覆盖本机配置（先备份到 output/backup/<时间>/）
python tools/preset.py import hengxin --with-learning   # 连行为学习一起导入
python tools/preset.py import hengxin --dry-run       # 只预演，不写盘
python tools/preset.py status                # 本机有哪些个人数据、多大、何时更新
```

`--groups core,usage` 可以直接指定分组；`--with-usage` / `--with-notes` 在默认分组上追加。

### 2) 启动参数

```bash
python run_daily.py --preset hengxin     # 先导入，再抓取 / 推荐 / 渲染
python server.py --preset hengxin        # 先导入，再起服务
start_digest.bat hengxin                 # Windows 双击场景（第二个参数写 force 则允许覆盖）
```

- 导入发生在其它动作**之前**；`--preset` 先于 `--categories`，所以
  `--preset hengxin --categories cs.LG` = 「用这份画像，但类别只看 cs.LG」。
- 导入失败**不阻断启动**（名字打错、本机已有不同配置都会继续跑），原因会打印在终端；
  让服务起来，才能从界面排查。

### 3) 界面一键导入

`/profile` →「📦 数据包」→ 每个包一行 →「导入」。

面板只显示**包名 + 文件清单 + 体积 + 分组**，不显示标题与描述——那句描述往往就是作者的
类别选择与研究方向。想了解内容就打开 `presets/<名字>/README.md`，或导入。

导入成功后页面会自动刷新（主来源卡片是服务端首屏渲染的）；接着点一次工具栏的
**↻ 重算推荐**，摘要页才会按新画像重排。

> 界面导入等价于 `POST /api/preset {"op":"import","name":"hengxin"}`，见
> [HTTP API](../reference/http-api.md)。

## 三、导入时到底发生了什么

| 情况 | 结果 |
| --- | --- |
| 本机没有该文件 | 写入 |
| 本机已有且内容一致 | `skipped`（幂等，重复导入不会重复写） |
| `core` 本机文件**仍是模板初值**（与 `*.example.json` 一致） | 直接替换（无需 `--force`）——新用户第一次打开页面就会生成它，那不是"用户的设置" |
| `core` 本机已有**用户改过**的不同内容 | `refused`，提示加 `--force`；**本机文件一个字节都不动** |
| `core` 加 `--force` | 先备份到 `output/backup/<时间>/`，再覆盖；备份失败则不覆盖 |
| `usage` / `notes` 本机已有条目 | 保留本机的，只补进包内多出来的条目 |
| `learning` 未显式请求 | 不导入 |
| 包内 JSON 坏了 / `sha256` 不符 | 该文件 `refused`，其余照常；绝不写入半份数据 |
| `manifest.json` 的 `schema` 高于本程序 | 整包拒绝，提示升级程序 |

**为什么 `core` 不合并？** 画像没有"合并"的语义——两个主题列表相加等于什么都不准。
静默覆盖会让你丢掉调了半年的设置，所以默认把决定权交给你（`--force`）。

**为什么模板初值可以直接替换？** 新用户第一次打开 `/profile` 就会生成空的
`config.json` / `interests.json`。如果把它们也算作"已有内容"，界面上那个「导入」按钮
对**目标用户**永远报错，只能退回命令行——那"一键导入"就没有意义了。
判据很严：**与 `*.example.json` 完全一致（忽略 `_comment`）**才算初值；
你改过任何一项（类别、下载目录、主题……）都会回到"默认拒绝"。

**端口不会被导入覆盖。** `config.json` 的 `port` 是"这台机器上服务监听哪"，不是
"某个人的设置"：导入时一律保留本机值，也不参与"是否仍是模板初值"的判定。
否则导入一个包会把服务悄悄挪到别人的端口上，界面就再也连不上了。

**为什么 `usage` 只并集？** 收藏是"我读过什么"，并集永不破坏；覆盖会删掉你刚积累的记录。
同名条目保留本机，是因为 `downloads[].path` 是绝对路径，别人的路径在你机器上必然失效。

## 四、导出一份包

```bash
python tools/preset.py export myown                    # 默认只导出 core
python tools/preset.py export myown --with-usage --with-notes
python tools/preset.py export myown --keep-paths       # 保留绝对路径（只建议本机备份用）
```

导出默认只含 `core`，是为了让"随手 export 一下然后提交"这个动作**默认安全**。
`sanitize`（默认开）会把：

- `config.json.download_dir` 的绝对路径改成中性的 `papers`；
- `library.json` 里所有 `path` 裁剪成文件名。

导出后还会扫一遍整包，若仍有形似绝对路径的字符串会逐条警告，并在 `manifest.json` 记
`sanitized`。包内的高敏文件（`library.json` 等）已被 `.gitignore` 按路径排除，
**不会**因为放在 `presets/` 下就被提交。

## 五、仓库自带的数据包

| 名字 | 内容 | 适合谁 |
| --- | --- | --- |
| `hengxin` | 数据库系统 / 分布式计算 / 形式化方法方向：4 位画像主来源、14 个主题、61 位熟悉研究者、22 个代表系统；6 个主分类 + 18 个扩展分类（`download_dir` 已中性化为 `papers/`） | 想看看"调了半年的画像长什么样"，或方向相近想直接起步 |

`hengxin/legacy/` 是作者当年用过的一次性脚本（补摘要、迁移 key、改下载目录），只作参考。

## 六、自己造一份

1. 在 `/profile` 里把画像调舒服，跑几期，让行为学习把倍率练出来；
2. `python tools/preset.py export <你的名字>`；
3. 编辑 `presets/<你的名字>/README.md`（`manifest.json` 的标题与描述可用 `--title` / `--desc` 给）；
4. 跑一遍 `python tools/preset.py show <你的名字>`，确认"与本机的关系"符合预期；
5. **确认里面没有隐私**，再提交。

分享前的隐私检查（逐项过一遍）：

| 检查项 | 为什么 |
| --- | --- |
| `config.json` 的 `download_dir` | 常含本机绝对路径与用户名；`export` 默认已改成 `papers` |
| `library.json` 的 `downloads[].path` | 同上；默认只在 `--with-usage` 时导出，且裁剪为文件名 |
| `interests.json` 的 `owners[].site` / `affiliation` | 公开主页可以，但要确认你愿意公开 |
| `summaries.json` / `rec_notes.json` | 你的读书笔记，可能含内部项目名或未发表想法 |
| 任何 `output/` 内容 | 已整体被忽略，不要 `git add -f` 强加 |
| `.secrets/`、`*cookie*.json` | 登录凭据，永不入库 |

## 七、数据包与"个人数据"的关系

| 位置 | 是否入库 | 说明 |
| --- | --- | --- |
| `*.example.json` | ✅ | 模板，机器无关，内容全空 |
| `presets/<名字>/{config,interests}.json` + `manifest.json` | ✅（自愿） | 别人可导入的成品设置 |
| `presets/<名字>/{library,behavior,profile_state}.json` | ❌ | 阅读史与行为流水，`.gitignore` 按文件名排除 |
| `config.json` / `interests.json` | ❌ | 你本机的运行态 |
| `output/`、`.secrets/` | ❌ | 运行产物与凭据 |

设计意图：仓库里只提交**模板**与**别人自愿公开的数据包**，任何人 clone 下来都是干净的；
想参考一份真实画像时又能一条命令导入，且导入默认不会破坏你已有的数据。

---

相关：[私人数据隔离](../architecture/data-isolation.md) · [config.json 参考](../reference/config.md) ·
[interests.json 参考](../reference/interests.md) · [命令行](../reference/cli.md) ·
[目录职责](../meta/structure.md) · [FAQ](../meta/faq.md)
