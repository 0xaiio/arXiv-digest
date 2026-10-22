# 安装

目标：在本机得到一个**能跑、且不含任何他人数据**的实例。全程约 3 分钟。

后续步骤见 [快速开始](quickstart.md)；只想先看看它长什么样，可以跳到那里的"用数据包试跑"。

---

## 一、环境要求

| 项 | 要求 | 说明 |
| --- | --- | --- |
| Python | 3.9+ | 运行期**只用标准库**，不需要 `pip install` |
| 操作系统 | Windows / Linux / macOS | 下载与"打开文件"用到 Windows 的 `os.startfile`，其它平台会退化为 `explorer`/无操作，不影响抓取与渲染 |
| 磁盘 | 代码 < 2 MB；`output/` 随期数增长（长期使用可达数百 MB） | 抓取池约 25 MB，之外还有归档快照与页面；PDF 体积另计 |
| 网络 | 能访问 `arxiv.org` 与 `export.arxiv.org` | API 限流时自动降级到分类 RSS，见[架构总览](../architecture/overview.md) |

可选能力另需依赖，不装也不影响主流程：

| 能力 | 额外依赖 | 见 |
| --- | --- | --- |
| 视频渲染 | Node 18+、`npm ci`（在 `reel/` 内） | [视频与投稿](../guide/video-pipeline.md) |
| 中文旁白 | `pip install edge-tts imageio-ffmpeg` | 同上 |
| B 站投稿 | `biliup-rs` + 扫码登录得到的 cookie | 同上 |
| 跑测试套件 | `pip install -r requirements-dev.txt`（pytest / pytest-cov / websocket-client） | [测试与回归](../contributing/testing.md) |
| 浏览器层测试 | Microsoft Edge（用 CDP 无头驱动；缺失时自动跳过） | [测试与回归](../contributing/testing.md) |

## 二、获取代码

```bash
git clone git@github.com:0xaiio/arXiv-digest.git
cd arXiv-digest
```

没有配置 SSH 就用 HTTPS：

```bash
git clone https://github.com/0xaiio/arXiv-digest.git
```

仓库里**只有代码、模板与数据包**。以下内容被 `.gitignore` 排除，克隆后不存在——这是刻意的：

| 不存在的东西 | 从哪来 |
| --- | --- |
| `config.json`（你的分类、下载目录） | 首次运行按 `config.example.json` 自动生成（**分类默认为空**，要你自己选） |
| `interests.json`（你的画像） | 首次运行按 `interests.example.json` 自动生成（**主题默认为空**） |
| `output/`（日报、归档库、收藏、行为记录） | 首次运行流水线时创建 |
| `.secrets/`（B 站 cookie 等凭据） | 只有你要用投稿功能时才需要自己准备 |
| `reel/node_modules/` | 只有你要渲染视频时才 `cd reel && npm ci` |

`presets/<名字>/` 是**数据包**：别人的整套设置与使用数据（纯 JSON），`clone` 后会存在，
但**运行时不会被读取**——只有 `--preset`、`tools/preset.py import` 或界面上的「导入」才生效。
所以"仓库里有 `presets/hengxin/`"不等于"界面里能看到作者的画像"。
两者的分层见 [私人数据隔离](../architecture/data-isolation.md)。

目录职责的完整说明见 [目录职责](../meta/structure.md)。

## 三、首次初始化

直接跑一次流水线，初始化是**隐式**的：

```bash
python run_daily.py
```

第一次运行会依次发生：

1. `paperutil.load_config()` 发现没有 `config.json`，从 `config.example.json` 复制一份，并打印
   `[init] 已按 config.example.json 生成 config.json…`；
2. `customize.load_interests()` 同样从 `interests.example.json` 生成 `interests.json`；
3. **检查是否已选分类**：`categories` 默认为空（本工具不预设任何领域），此时脚本会提示
   「尚未选择任何 arXiv 分类」并只把本地服务拉起来，不会抓取任何东西。
   去 `http://127.0.0.1:8765/profile` 的「🗂 arXiv 类别」面板选好（或在命令里加
   `--categories cs.DB,cs.DC`），再跑一次即可。想让一份现成设置替你选：
   `python run_daily.py --preset <名字>`。详见 [arXiv 类别](../reference/categories.md)；
4. 抓取主分类与扩展分类，写入 `output/raw.json` 与 `output/raw_expand.json`；
5. 打分、抓作者单位（较慢）、渲染日报，并把当期快照写进 `output/archive/` 与 `output/archive.db`；
6. 检查 `http://127.0.0.1:<port>/api/ping`，服务没在线就在后台拉起 `server.py`。

生成的两个文件从此属于**你的个人数据**，不会被提交（见 [config.md](../reference/config.md) 与
[interests.md](../reference/interests.md)）。

> 初始化规则只有一条：**文件不存在才生成**。文件存在时完全以你的内容为准，缺字段回落到代码内默认值，
> 不会被模板覆盖。

## 四、验证安装

```bash
# 1) 服务是否在线（应返回 {"ok": true}）
curl --noproxy '*' http://127.0.0.1:8765/api/ping

# 2) 当期日报是否生成
ls output/arxiv_digest_*.html | tail -1

# 3) 归档是否登记
python -c "import archive; print(archive.stats())"
```

浏览器打开 `http://127.0.0.1:8765/`（默认端口；若被占用，服务会顺延，实际地址见启动日志或
`output/server.json` 的 `port`）：已选分类并抓取过 → 三个板块（🎯 为你推荐、🌱 兴趣扩展、📖 分类详解）；
还没选分类 → 一张「选择要跟踪的 arXiv 分类」的引导页，点按钮直达 `/profile`。
若页面提示"尚无摘要页"，说明流水线还没成功跑完，按 [故障排查](../operations/troubleshooting.md) 第 1 节处理。

## 五、日常启动方式

| 方式 | 命令 | 适用 |
| --- | --- | --- |
| 完整流水线 | `python run_daily.py` | 每天一次（或交给定时任务）；只打印地址，不开浏览器 |
| 只重算+重渲染 | `python run_daily.py --skip-fetch --skip-affil` | 改了画像/分类，想立刻看到结果（秒级） |
| 只起服务 | `python server.py` | 补看昨天的日报，不重新抓取；启动后自动开浏览器 |
| 起服务但不开浏览器 | `python server.py --no-open` | 定时任务 / 无桌面环境；等价于 `config.json` 里 `"open_browser": false` |
| 指定起始端口 | `python server.py --port 9000` | 想避开某段端口；仍被占用时会继续顺延 |
| 带数据包启动 | `python run_daily.py --preset <名字>` / `python server.py --preset <名字>` | 先把 `presets/<名字>/` 导入本机，再跑/再起 |
| Windows 双击 | `start_digest.bat`（加参数 `hengxin` 则同时导入数据包） | 自动找 `python`/`py -3`，端口读 `config.json`，启动后自动开浏览器 |

**端口不需要手工避让**：默认 8765，被占用会自动向后顺延（最多 20 个），启动日志里会打印
`serving http://127.0.0.1:<实际端口>`，同时写入 `output/server.json`。要把服务固定在某个端口，
改 `config.json` 的 `port` 或加 `--port`；确实没有可用端口时进程以退出码 2 明确报错，不会半启动。
细节见[服务运行时](../architecture/server-runtime.md)。

## 六、卸载与重置

| 目的 | 操作 |
| --- | --- |
| 恢复出厂设置 | 删除 `config.json`、`interests.json`、`output/`，重跑 `run_daily.py` |
| 只重置画像（保留抓取数据与收藏） | 删除 `output/profile_state.json`（行为学习记录） |
| 只重置归档判定 | 删除 `output/archive.db`；注意下次运行会把整个池子当作新增重新判定 |
| 完全卸载 | 删除整个项目目录即可——不写注册表、不装系统服务 |

> 删除前请确认：`output/library.json` 里有你的收藏与下载记录，`output/archive.db` 里有往期索引。
> 想保留就把它们先拷出来，或者干脆导成一个数据包：
> `python tools/preset.py export backup --with-usage --with-learning --with-notes`。
> 重置不会碰 `presets/` 下的数据包（它们不在运行态里）。

---

下一步 → [快速开始](quickstart.md) · 想先理解推荐是怎么算的 → [排序与学习算法](../architecture/ranking.md)
