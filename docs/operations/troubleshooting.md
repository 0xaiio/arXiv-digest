# 故障排查

按"症状 → 诊断 → 修复"组织。每条都尽量给出**一条能立刻跑的命令**。
概念型问题（"该不该这样用"）看 [FAQ](../meta/faq.md)。

---

## 一、服务与页面

### 1.1 打开 8765 显示"尚无摘要页，请先运行 run_daily.py"

**诊断**

```bash
ls output/arxiv_digest_*.html | tail -1
```

没有输出 → 流水线从未成功渲染。

**修复**：`python run_daily.py`。若抓取阶段就失败，看 §2。

### 1.2 `curl http://127.0.0.1:8765/api/ping` 返回 502 或挂了很久

不是服务坏了，是**环境代理劫持了回环地址**。

**诊断**

```bash
curl --noproxy '*' -m 3 http://127.0.0.1:8765/api/ping
```

**修复**：所有本地请求都加 `--noproxy '*'`；Python 里用空 `ProxyHandler`：

```python
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
```

### 1.3 端口被占用

**症状**：打开 8765 是别的程序、或者本地服务在 8766 / 8767 上。

**现在的行为（2026-10-20 起）**：默认端口被占用时**不会**再报
`Address already in use` / `[WinError 10048]` 然后退出，而是自动向后顺延（最多 20 个），
并在启动日志里给出实际地址：

```
serving http://127.0.0.1:8766  (download_dir=...)
port: 8766（8765 已被占用，已向后顺延；尝试过 8765–8766，共 2 个）
```

**先确认实际端口**

```bash
python -c "import serveport;print(serveport.read_runtime_info('output/server.json'))"
```

同时页面里的接口端口会被自动改写（静态页发出去时改 `APIPORT`，动态页按运行期端口渲染），
所以顺延之后收藏 / 下载照常可用，**不需要手工改任何配置**。

**想查/腾出占用者**

```bash
# Windows PowerShell
Get-NetTCPConnection -LocalPort 8765 -State Listen | Select-Object OwningProcess
```

```bash
# Linux / macOS
lsof -i :8765
```

**想固定端口**：改 `config.json` 的 `port`，或启动时 `python server.py --port 9000`
（仍然被占用时会继续顺延）。20 个端口都不可用时进程以退出码 2 结束并打印尝试范围，
此时换一段端口即可。

### 1.4 启动后浏览器没有自动打开

**先判断是不是本来就该关着**（默认是开的）：

1. 启动参数带了 `--no-open`（`run_daily.py` 拉起的后台服务固定带它 —— 它只打印地址）；
2. `config.json` 里写了 `"open_browser": false`。

**症状**：日志里出现 `[browser] 未能自动打开浏览器，请手动访问 http://127.0.0.1:<端口>`。

这不是故障：无桌面环境（SSH、容器、Windows 服务）、没有默认浏览器、或系统拒绝拉起浏览器时，
只打印一行提示并继续提供服务，**不会让启动失败**。手动访问那个地址即可；想让提示消失就
`--no-open`。反过来，配置里关了但这次想开，用 `--open`（命令行优先于配置）。

### 1.5 改了模板，页面还是旧的

| 页面 | 是否需要重启 | 说明 |
| --- | --- | --- |
| `/favorites` `/profile` `/archive` | 不需要 | 每次请求 `importlib.reload(build_report)` |
| `/`（日报） | 不需要重启，但**需要重渲染** | 它是上次生成的静态文件 |

**修复**：`python build_report.py` 或点页面上的「↻ 重算推荐」。若连动态页都旧，重启服务。

### 1.6 导入数据包被拒绝 / 画像页看不到包

| 症状 | 根因 | 修复 |
| --- | --- | --- |
| `本机已有不同内容（加 --force 覆盖…）` | `core` 分组（`config.json` / `interests.json`）默认不覆盖 | 确认要用包里的设置：`python tools/preset.py import <名字> --force`（先备份到 `output/backup/<时间>/`）。只想用包的画像而不动配置：`--groups core` 前先 `export` 备份自己的 |
| `找不到数据包` / 面板是空的 | 包目录不含任何已知文件，或包名不在 `presets/` 下 | `python tools/preset.py list` 看能发现哪些；确认目录里有 `config.json` 或 `interests.json` |
| `与 manifest.json 记录的 sha256 不符` | 包被手改过，清单没更新 | 重新 `export`，或删掉该包的 `manifest.json`（放弃完整性校验） |
| `清单版本是 2，高于本程序支持的 1` | 包来自更新的版本 | 升级程序；不要手改 `schema` |
| 导入成功但摘要页没变 | 摘要是**静态文件** | 点「↻ 重算推荐」，或 `python run_daily.py --skip-fetch --skip-affil` |
| 导入后下载报"文件不存在" | 包里的 `downloads[].path` 是别人的机器路径 | 重新下载即可；`library` 的收藏记录不受影响 |

数据包的完整语义见[数据包（预设）](../guide/presets.md)，边界见
[私人数据隔离](../architecture/data-isolation.md)。

---

## 二、抓取

### 2.1 日志出现 `[fallback] arXiv API 部分/全部不可用，改用 RSS 增量抓取`

这是**正常降级**，不是错误。含义：主分类或扩展分类有一路没拿到有效数据，已改抓 RSS，
并按短号**增量合并**进累积池（不删任何条目）。

**该做什么**：确认当期页面是否仍有内容；若连续多天都走降级，检查网络或稍后重试。

### 2.2 累积池变小了

**症状**：`output/raw.json` 的 `papers` 数量比昨天少。

**诊断**

```bash
python -c "import json;d=json.load(open('output/raw.json',encoding='utf-8'));print(len(d['papers']))"
ls output/raw.json.bad_* 2>/dev/null | tail -3
```

**修复**：用备份/快照重新合并

```bash
python tools/merge_raw_pool.py        # 按短号并集合并回池
python tools/rebuild_raw_from_index.py  # 从 papers_index.json 抢救（最后手段）
```

根因通常是"部分成功被当成全部成功"——现版本已把降级条件改为 `not (ok1 and ok2)`。

### 2.3 抓取成功但页面空白

**诊断**：看 `output/issue_stats.json` 的 `new_core` / `new_expand`。

- 两个都是 0 → 这批论文**都已经在以前的期次出现过**（累积池的正常行为），不是 bug；
- 若确实是新批次却全是 0 → `archive.db` 的 `seen` 表异常，见 §5.1。

---

## 三、推荐

### 3.1 「为你推荐」是空的，或只有一两篇

两种截然不同的原因：

**诊断**

```bash
python -c "import json;d=json.load(open('output/issue_stats.json',encoding='utf-8'));print(d)"
python profile.py | head -20
```

| 情况 | 判据 | 修复 |
| --- | --- | --- |
| 画像太薄 | `mode` 显示走兜底，或主题倍率全是 1.0 且关键词很少 | 按[调优画像](../guide/profile-tuning.md)补 3–6 个主题 |
| 画像被污染 | 主题倍率大面积 < 0.5、多个触底 0.25 | 见 §3.2 |
| 当期论文确实少（周末/假日） | `new_core` 本身很小 | 正常现象，等下一个工作日 |

### 3.2 前几天正常，突然一片低分

**先做这一步判断"内容弱"还是"画像坏"**：看 `output/scores.json` 里全池最高分。

```bash
python -c "
import json;d=json.load(open('output/scores.json',encoding='utf-8'))
print('全池 Top10:', [round(x['score'],1) for x in sorted(d,key=lambda p:-p['score'])[:10]])"
```

- 全池 Top10 仍正常（30+）而**当期全低** → **画像坏了**；
- 全池也低 → 关键词配置或抓取问题。

**修复协议**（完整原理见[排序算法 §6](../architecture/ranking.md)）：

1. 备份 `output/profile_state.json`；
2. 删除其中**负向**关键词（保留正向）；
3. `topic_mult` 全部归 `1.0`；
4. **保留** `paper_bonus` 里的 -12（那是你"这篇不要"的明确表达）；
5. `python recommend.py && python build_report.py`。

### 3.3 排序与我的直觉不符

按信号强弱依次检查：

1. 是否命中**熟悉作者**（+10/人，最强）——`/profile` 的 `people` 列表；
2. 主题 `weight` 是否相差过大（>2.5 会压倒一切）；
3. 是否有**降权词**误伤（`negative.keywords` 命中一次就是 -3）；
4. 是否命中过少的关键词（`distributed`、`data` 这类词等于没筛）。

### 3.4 首屏排序与点一下之后的排序不一致

这说明**前后端两份打分实现不同步**。`recommend.score()` 与 `build_report.py` 的 `rescore()`
必须同步修改。属于代码缺陷，请提 issue。

---

## 四、下载

### 4.1 点下载报错

**先看路由**（不要先怀疑代码）

```bash
python netroute.py
```

| 输出 | 含义 | 处理 |
| --- | --- | --- |
| `结论：可用路由 = ...` | 有可用出口 | 问题在文件层，看 §4.2 |
| `结论：未找到可用路由` | 所有出口都拿不到 `%PDF` | 见下表 |

| 环境 | 典型错误 | 对策 |
| --- | --- | --- |
| 直连被重置 | `WinError 10054` | 挂代理，或 `ARXIV_DL_PROXY=http://127.0.0.1:<port>` |
| 环境代理掐断 TLS | `UNEXPECTED_EOF_WHILE_READING` | 同上；`netroute` 会自动跳过它 |
| 本机代理未启动 | 连接被拒 | 启动代理，或改 `ARXIV_DL_PROXY` |

强制指定出口：

```bash
ARXIV_DL_PROXY=http://127.0.0.1:7890 python run_daily.py
```

服务在线时也可以看 `GET /api/net_route` 的 `last_failure`。

### 4.2 报"未找到论文元数据"

该篇已不在当前池（例如是很久以前的收藏）。**修复**：跑一次 `run_daily.py` 让池子刷新；
或用 `/profile` 确认它是否还在推荐列表里。

### 4.3 下载成功但文件找不到

**诊断**

```bash
python -c "import paperutil as pu;print(pu.load_config()['download_dir'])"
python -c "import json;d=json.load(open('output/library.json',encoding='utf-8'));print(list(d['downloads'].items())[:3])"
```

`download_dir` 是相对路径时相对**项目根**。`library.downloads[].path` 记录的是下载时的绝对路径，
换机器/改目录后需要重新下载。

### 4.4 批量下载很慢 / 只成功一部分

- 并发上限 `DL_WORKERS = 3`（避免触发 arXiv 频控），3 篇 ≈ 单篇耗时；
- 单项失败不影响其它项，看 `/api/download_all` 响应里每条 `results[].msg`；
- 同一篇被连点两次会串行（单篇锁），这是预期行为。

---

## 五、归档与历史

### 5.1 往期内容重复出现在今天的日报里

**原因**：`seen` 表里没有这些论文，或被手工删除过。

**诊断**

```bash
python -c "
import archive
print(archive.stats())
print(archive.available_dates()[:5])"
```

**修复**：不要手工删 `seen` 行。正确做法是保留 `archive.db`，让判定自己收敛；
若历史期次从未入库（功能上线前的日报），用

```bash
python tools/backfill_archive.py
```

把磁盘上已有的 `arxiv_digest_<日期>.md/.html` 回填。

### 5.2 `/archive/<日期>` 返回 404

**诊断**：`output/archive/<日期>.html` 是否存在。归档只保存"渲染过"的期次；
补跑历史用 `tools/backfill_archive.py`。

### 5.3 今天重跑流水线，页面会清空吗

不会。`seen` 里首次期次等于本期的论文仍算本期（幂等）。但**换了系统日期**再跑（比如手动改时钟）
会让判定错位——避免这么做。

---

## 六、简介 / 摘要译文缺失

**症状**：卡片简介只有一行（说明双语里缺了一半）；点「Abstract (CH)」展开后看到
"还没有中文摘要译文"的提示。

**诊断**

```bash
python tools/gen_pending.py --limit 20        # 缺中文简介
python tools/gen_pending.py --en --limit 20   # 缺英文简介
python tools/gen_pending.py --abs --limit 20  # 缺中文摘要译文
```

**修复**：按清单补写对应文件（key 一律 arXiv 短号）：

```jsonc
// summaries.json：双语简介，英文优先复用摘要里的原始句子
{ "2609.09742": { "en": "We study isolation level ...", "zh": "研究事务的隔离级别……" } }

// abstracts_zh.json：英文完整摘要对应的中文译文
{ "2609.09742": "我们研究了……（完整摘要的译文）" }
```

三种写法都合法：双语对象、只写 `zh`、或旧的单语字符串（含汉字算中文、否则算英文）。
只有**写成了别的对象形状**（如 `{"title": "...", "summary": "..."}`）才会取不到内容——
`en` / `zh` 两个键都取不到时就等于没写。
补完重跑 `python recommend.py && python build_report.py`。

---

## 七、视频

| 症状 | 原因 | 修复 |
| --- | --- | --- |
| 成片没有旁白 | `reel/src/audio.json` 的 `enabled` 是 `false` | 重跑 `tools/gen_narration.py`，确认置 `true` 后重新渲染 |
| 渲染报 404 | 引用了不存在的 mp3 | 同上 |
| 闸门报「段内静音 > 3s」 | 该段口播太短 | 补写 `output/video_notes.json` 的 `narration` |
| 闸门报「总时长不符」 | 篇数与 `--top/--expand` 不符 | 显式写 `--top 8 --expand 2` |
| TTS 报 `403 WSServerHandshakeError` | `edge-tts` 版本过旧，签名被服务端拒绝 | `pip install -U edge-tts` 后重试 |
| TTS 报 `ClientConnectorError: Cannot connect to host speech.platform.bing.com` | **出网路由**问题，不是稿件问题：本机对该域名的直连被拦（DNS 常被解析到 `198.18.0.104` 这类假 IP，TCP 能连上但 TLS 握手被掐断），只有经代理才通 | 脚本已自动逐条回退路由（直连 → 环境代理 → 本机代理端口）并记住成功那条；仍失败时用 `--proxy` 显式指定，例如 `python tools/gen_narration.py --proxy http://127.0.0.1:7890`；先用 `curl -x <代理> -sv https://speech.platform.bing.com/` 确认 `CONNECT ... 200` 且 TLS 握手完成 |
| TTS 偶发 `NoAudioReceived` | 服务端瞬时抽风，与稿件无关 | 脚本会在**同一路由**内自动重试；连续失败才换路由 |

完整流程见[视频与投稿](../guide/video-pipeline.md)。

## 八、B 站投稿

| 错误 | 含义 | 处理 |
| --- | --- | --- |
| `-400 请求错误` | 用的是 Web 扫码 cookie，缺 App 接口的 `access_token` | 走 TV 通道扫码：`python tools/bili_tv_qr_login.py --wait 280` |
| `code 601 您上传视频过快` | 账号侧临时频控 | 冷却几分钟，用**原命令**重投，不要改参数 |
| 登录态失效 | cookie 过期 | 重新 TV 扫码；`biliup renew` 可验证 |
| 合集里没有新视频 | 没跑 `sync`，或稿件仍在审核（cid 未生成） | `python tools/bili_collection.py sync --exec`；等转码完成后重跑 |
| `sync` 报 `code 20080 当前稿件已存在在合集中` | 20080 是**整批级**拒绝：批次里只要有一条已在合集，整批都不挂（不是「整批都已挂好」） | 脚本已自动改为逐条重投，并在挂完后用稿件详情回读校验；仍报 `[FAIL] 仍不在合集` 就重跑 `sync --exec`（本轮真没挂上） |
| `sync` 报 `[FAIL] 仍不在合集 season ... 内` 但页面里能看到 | 稿件详情接口有 CDN 缓存，刚挂完数十秒内可能还读不到归属 | 脚本会重试 5 次×3s；要手工确认就看 `season_id`：`GET api.bilibili.com/x/web-interface/view?aid=<aid>` 的 `data.season_id` 等于 `9343347` 即为已挂载（`ugc_season` 同理） |
| 上传报 `error sending request ... tls handshake eof` | 上传线路（upos CDN）的 TLS 握手被出口拦断，**不是账号问题**，也未产生稿件 | 换一条线路重投：`--line bda2`（可选 `bda2/ws/qn/bldsa/tx/txa/bda/alia`），不会重复投稿 |

cookie 等同账号密码：只在 `.secrets/` 里，绝不进日志、提交或外发。

## 九、还是解决不了

收集这四样再提问/开 issue：

1. 完整命令与输出（含 `stderr`）；
2. `python netroute.py` 的结论（涉及下载时）；
3. `output/issue_stats.json` 与 `output/scores.json` 的 Top10（涉及推荐时）；
4. `output/server.log` 末尾 50 行（涉及服务时）。

> 提问前请先自查：`git status` 是否干净、服务是否在跑、报的是"没有结果"还是"报错"。
> 这三条能过滤掉一半问题。

---

相关：[FAQ](../meta/faq.md) · [命令行参考](../reference/cli.md) ·
[服务运行时](../architecture/server-runtime.md) · [排序算法](../architecture/ranking.md)
