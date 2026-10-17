# 服务运行时

`server.py` 是本地唯一的常驻进程：渲染页面、处理交互写入、下载 PDF。本文讲它的并发模型、
缓存、跨源兼容与出网策略——这几处是"页面卡住""收藏丢失""下载报错"的高发区。

接口清单见 [HTTP API](../reference/http-api.md)。

---

## 一、进程模型

| 项 | 值 | 说明 |
| --- | --- | --- |
| 服务器 | `ThreadingHTTPServer` | 每个请求一个线程；因为下载是长 IO，单线程会把整页堵死 |
| 绑定 | `127.0.0.1:<config.port>` | **只监听回环**，无鉴权，不应暴露公网 |
| 工作目录 | 启动时 `os.chdir(HERE)` | 防御 `start /b` 不继承 cwd 的情况，避免读写别人的 `output/` |
| 浏览器 | 默认自动打开，`--no-open` 关闭 | 定时任务里用 `--no-open` |

## 二、锁：两级 + 两个专用锁

共享文件必须串行读-改-写，但**网络 IO 绝不能占着锁**。

| 锁 | 保护范围 | 粒度 |
| --- | --- | --- |
| `_lib_lock` | `library.json` / `profile_state.json` 的读-改-写 | 毫秒级 |
| `dl_lock(sid)` | 某**一篇**论文的下载（防同一篇连点写坏同名 `.part`） | 一次网络下载 |
| `_papers_lock` | 论文索引缓存的刷新（双重检查） | 一次大 JSON 解析 |
| `_rebuild_lock` | `/api/rebuild`（重跑 recommend + build_report） | 数十秒 |

铁律：**任何网络 IO 都不许在 `_lib_lock` 内**。

早期版本用一把全局锁把整个 `/api/download` 包住（含最长 90 秒的取数），结果是"点一篇下载，
整页的收藏 / Downvote 全部排队，界面像死了一样"。拆分后的实测（`tools/concurrency_check.py`，
桩化 2 秒下载）：

| 场景 | 拆锁前 | 拆锁后 |
| --- | --- | --- |
| 下载进行中 → 另一篇 Downvote | 等满 2.00 s | **0.014 s** |
| 批量下载 3 篇 | 6.0 s（串行） | **2.05 s**（`DL_WORKERS=3`） |
| 同一篇并发下载两次 | 4.0 s | 4.02 s（仍串行，符合预期） |

## 三、论文索引缓存

每次请求都需要"短号 → 论文元数据"的映射，而两个池合计可达 20 MB+。

```python
def papers(force=False):
    if force or now - cache["ts"] > 60:      # 60 秒 TTL
        with _papers_lock:                    # 双重检查：只让一个线程解析
            if force or time.time() - cache["ts"] > 60:
                cache["data"] = pu.load_papers()
```

- TTL 60 秒：重跑流水线后最多一分钟自然生效；`/api/rebuild` 会主动把 `ts` 置 0；
- 双重检查的理由：并发下载线程同时要索引，否则每个线程各解析一份 20 MB JSON。

## 四、静态页 vs 动态页

| 页面 | 生成方式 | 为什么要这样 |
| --- | --- | --- |
| `/`（日报） | **静态文件** `arxiv_digest_<日期>.html` | 当期快照，必须与 `output/archive/` 完全一致 |
| `/favorites` | 每次请求渲染 | 收藏随时变，静态文件会过期 |
| `/profile` | 每次请求渲染 | 画像与配置随时变 |
| `/archive` | 每次请求渲染 | 新期次不断加入 |
| `/archive/<日期>` | 静态快照 | 归档只增不改 |

动态页每次都做 `importlib.reload(build_report)`：否则改了模板后，服务进程里缓存的旧模块会
一直吐旧 HTML，只有重启才生效。代价是每次多一次模块重载（毫秒级），换来"改模板不用重启"。

## 五、跨源与 `file://` 兼容

日报是自包含 HTML，可以脱离服务直接双击打开，但收藏/下载仍需服务。两条支撑：

1. **响应头**：所有响应带 `Access-Control-Allow-Origin: *`，`OPTIONS` 返回 `204`；
2. **前端改写**：页面打开时若 `location.protocol === 'file:'`，把 `APIBASE` 与站内链接改写成
   `http://127.0.0.1:<port>` 的绝对地址（端口从 `papers_index.json` 或页面内联变量取得）。

安全说明：`*` 在这个场景是可接受的——服务只监听回环、只操作本机数据；它带来的风险是
**同一台机器上的任意网页都能调你的本地接口**（例如恶意页面替你批量 Downvote）。
不共享机器的话影响可忽略；在意的话可以把 CORS 收窄到 `file://` 与 `127.0.0.1`。

## 六、下载取数：为什么要选路

下载由**服务进程**发起（不是浏览器）。很多环境里同时存在多种出口，只有一种真能拿到 arXiv：

| 出口 | 典型表现 |
| --- | --- |
| 直连 | `WinError 10054` 连接被重置 |
| 环境注入的 `HTTP(S)_PROXY` | CONNECT 成功但 TLS 流被掐断（`UNEXPECTED_EOF_WHILE_READING`） |
| 本机代理端口（如 7890） | 正常拿到 `%PDF` 头 |

`netroute.py` 的候选顺序与策略：

```
ARXIV_DL_PROXY（人工强制）
  → 直连
  → 环境变量代理
  → 本机常见代理端口（在监听的那些）
  → 其它在监听端口
```

- 命中后写 `output/netroute.json`，**TTL 900 秒**内直接复用；
- 全部失败时写**负缓存 45 秒**，避免批量下载时每次都重探一遍；
- 校验方式是读响应头的 `%PDF` 与长度，不是"能连上就算通"；
- 排错：`python netroute.py`（`--forget` 清缓存、`--quick` 只看候选），
  或服务在线时 `GET /api/net_route`。

另一个与"代理"相关的坑**不在下载里**：部分环境的代理会把 `127.0.0.1` 也劫持，
导致 `curl http://127.0.0.1:8765` 返回 `502`。所有本地探测都必须 `--noproxy '*'`
（`run_daily.server_alive()` 里用空 `ProxyHandler` 实现同样效果）。

## 七、服务生命周期

```
run_daily.py ──▶ server_alive()? ──是──▶ 复用（打印 URL）
                       │否
                       ▼
              cmd /c start /d <项目根> /b python server.py --no-open
                       │
                       ▼
              轮询 /api/ping 直到就绪（最多 15s）
```

- **必须 `start /d`**：`start /b` 不继承 `Popen(cwd=...)`，项目搬家后子进程会以旧目录为 cwd，
  继续读写旧的 `output/`（真实踩过）；
- 服务日志追加到 `output/server.log`；
- `server.py --serve`（前台阻塞）只用于"想让终端窗口承载服务"的场景。

## 八、失败模式速查

| 现象 | 最可能的原因 | 处置 |
| --- | --- | --- |
| `curl 127.0.0.1:8765` 返回 502 | 环境代理劫持了回环 | 加 `--noproxy '*'` |
| 端口被占用（`Address already in use`） | 上一个进程还在 | 结束占用进程后重启（见[故障排查](../operations/troubleshooting.md)） |
| 收藏/下载点了没反应 | 服务没起，或页面以 `file://` 打开但服务离线 | 先 `/api/ping` |
| 收藏记录丢失 | 并发写覆盖（旧版本） | 现版本由 `_lib_lock` 保护；若复现请提 issue 并附日志 |
| 下载报"未找到论文元数据" | 该篇已不在当前池（过期收藏） | 重新跑一次流水线再下载 |
| 动态页一直显示旧内容 | 服务进程缓存了旧模块 | 现版本每次请求 reload；若仍复现请重启服务 |
| `/api/rebuild` 一直失败 | recommend 或 build_report 报错 | 手动跑这两个脚本看 stderr |

---

相关：[HTTP API](../reference/http-api.md) · [架构总览](overview.md) ·
[故障排查](../operations/troubleshooting.md) · [模块职责](modules.md)
