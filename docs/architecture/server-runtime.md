# 服务运行时

`server.py` 是本地唯一的常驻进程：渲染页面、处理交互写入、下载 PDF。本文讲它的并发模型、
缓存、跨源兼容与出网策略——这几处是"页面卡住""收藏丢失""下载报错"的高发区。

代码分三层，本文按层讲：

| 层 | 文件 | 负责 |
| --- | --- | --- |
| 装配 | `server.py` | 解析请求、写 socket、启动进程、兼容门面 |
| HTTP 语义 | `routes.py` | 路由表、参数校验、`Reply`/`Request` |
| 业务用例 | `service.py` | 收藏 / 下载 / 学习 / 重建（不认识 HTTP） |

接口清单见 [HTTP API](../reference/http-api.md)，模块职责见[模块职责](modules.md)。

---

## 一、进程模型

| 项 | 值 | 说明 |
| --- | --- | --- |
| 服务器 | `ThreadingHTTPServer` | 每个请求一个线程；因为下载是长 IO，单线程会把整页堵死 |
| 绑定 | `127.0.0.1:<实际端口>` | **只监听回环**，无鉴权，不应暴露公网。起始端口取 `config.port`（默认 8765），被占用则自动向后顺延 |
| 工作目录 | 启动时 `os.chdir(HERE)` | 防御 `start /b` 不继承 cwd 的情况，避免读写别人的 `output/` |
| 浏览器 | 默认自动打开；`--no-open` / `config.open_browser=false` 关闭，`--open` 强制打开 | 定时任务里用 `--no-open`；无桌面环境下打不开只打印一行提示，不影响服务 |

### 端口：先探测、再顺延、最后落盘

选端口与开浏览器都不在 `server.py` 里自己实现，而是收在 `serveport.py`（`run_daily.py`
用同一份）：两处各写一遍的话，必然一处顺延、一处硬失败，表现为「双击能开、定时任务开不了」。

```
config.port(或 --port) ──▶ find_free_port(start, limit=20)
                              │  每个候选：connect 探测（有人监听？）→ bind 探测（能绑？）
                              ├─ 找到 ──▶ bind ──(被抢)──▶ 顺延重试一轮
                              └─ 20 个都不行 ──▶ 退出码 2 + 明确错误，不留半启动进程
                                        │
                                        ▼
                         serving http://127.0.0.1:<实际端口>
                         output/server.json = {port, url, pid, started_at}
```

两个刻意的设计：

- **connect 探测是主判据**。Windows 的 `SO_REUSEADDR` 语义允许第二个 socket 绑上已被监听
  的端口（端口劫持），只看 bind 会把「已被占用」误判成「可用」；反过来 TIME_WAIT 的遗留
  连接不应答 connect，所以「刚 Ctrl-C 完立刻重启」不会被误判成占用；
- **实际端口要落盘**。`run_daily.py` 后台拉起服务后只能靠 HTTP 轮询（看不到子进程 stdout），
  服务若又顺延了一次，轮询旧端口就会白等到超时 —— 它先按 `serveport.find_free_port` 选好
  端口用 `--port` 传下来，再以 `output/server.json` 兜底对账。

**页面必须跟着端口走**。这一层容易漏：日报是静态文件（`Reply.file` 直发字节，不能重渲染），
而 JS 里的 `APIPORT` 是渲染当时的 `config.port`。所以有两条改写路径：

| 页面 | 端口来源 | 谁负责 |
| --- | --- | --- |
| `/`、`/archive/<日期>`、`/files/*.html` | 静态文件里烘焙的值 | `routes._static_html()` 读盘后就地改写 `APIPORT=<实际端口>`（端口一致时仍走延迟读盘） |
| `/favorites`、`/profile`、`/archive` | 每次渲染 | `paperutil.effective_port()`：运行期实际端口 > `config.port` > 8765 |

不改写的话，顺延之后收藏 / 下载 / Downvote 会打到旧端口 —— 表象是「点了没反应」（乐观
更新被回滚），而 `/api/ping` 却是通的，非常难查。

## 二、路由：一张表，而不是 if 链

```python
@get("/api/ping")
def ping(req):
    return Reply.json({"ok": True})
```

- 匹配：**精确优先、前缀次之**，所以 `/archive` 不会被 `/archive/` 抢走；
- 处理器只做 HTTP 语义（取参数、校验、拼响应），业务动作一律 `req.api.xxx(...)`；
- `routes.table()` 返回全部路由，测试用它断言「路由没被误删」，文档也据此维护。

`server._Runtime` 是路由层能看到的**能力白名单**（`ALLOWED`）。每次访问都回查
`server` 模块，因此：

```python
server.download_pdf = stub      # 桩化立即生效
```

这一点被 `tools/concurrency_check.py` 与多个集成测试依赖——若改成 import 期绑定，
那些回归会真的去下载 PDF。反过来，路由层摸不到白名单外的属性（`rt.Handler` 直接
`AttributeError`），避免慢慢长成「什么地方都能捞一把」的大泥球。

## 三、锁：两级 + 两个专用锁

共享文件必须串行读-改-写，但**网络 IO 绝不能占着锁**。锁定义在 `service.py`，
`server.LIB_LOCK` 是同一个对象（拆层后两把锁就等于没锁）。

| 锁 | 保护范围 | 粒度 |
| --- | --- | --- |
| `LIB_LOCK` | `library.json` / `profile_state.json` 的读-改-写 | 毫秒级 |
| `dl_lock(sid)` | 某**一篇**论文的下载（防同一篇连点写坏同名 `.part`） | 一次网络下载 |
| `PaperIndex._lock` | 论文索引缓存的刷新（双重检查） | 一次大 JSON 解析 |
| `_rebuild_lock` | `/api/rebuild`（重跑 recommend + build_report） | 数十秒 |

铁律：**任何网络 IO 都不许在 `LIB_LOCK` 内**。

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
| `/`（日报） | **静态文件** `arxiv_digest_<日期>.html` | 当期快照，必须与 `output/archive/` 完全一致；发出去时按实际端口改写 `APIPORT` |
| `/favorites` | 每次请求渲染 | 收藏随时变，静态文件会过期 |
| `/profile` | 每次请求渲染 | 画像与配置随时变 |
| `/archive` | 每次请求渲染 | 新期次不断加入 |
| `/archive/<日期>` | 静态快照 | 归档只增不改；同样按实际端口改写 `APIPORT` |

动态页渲染时会 `digest_module()`：惰性导入 `build_report`，并**按需 reload**（收敛到一处、
加锁）。原来三个页面路由各自 `importlib.reload`，重复且无锁——两个请求同时 reload 会互相打架。

现在 reload 只为「代码改动」服务：**模板改动不需要它**，因为 `read_template()` 按 mtime 缓存，
文件一变下次渲染就重新读盘。端口同理：占位符在渲染时替换（`render_js()`），取值来自
`paperutil.effective_port()`（运行期实际端口优先）——所以「服务顺延」不会把页面指回旧端口，
而「改 `config.port` 后重启」也能立刻生效（`_JS_CACHE` 按端口分键，不会钉住旧值）。

## 五、跨源与 `file://` 兼容

日报是自包含 HTML，可以脱离服务直接双击打开，但收藏/下载仍需服务。两条支撑：

1. **响应头**：所有响应带 `Access-Control-Allow-Origin: *`，`OPTIONS` 返回 `204`；
2. **前端改写**：页面打开时若 `location.protocol === 'file:'`，把 `APIBASE` 与站内链接改写成
   `http://127.0.0.1:<port>` 的绝对地址（端口来自页面内联的 `APIPORT`，渲染时写入，静态页
   由 `routes._static_html()` 按实际端口改写）。

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
run_daily.py ──▶ server_alive(config.port)? ──是──▶ 复用（打印 URL）
                       │否
                       ▼
              find_free_port(config.port)  ──无可用端口─▶ 打印原因，不拉起
                       │找到（可能是 8766）
                       ▼
    cmd /c start /d <项目根> /b python server.py --no-open --port <空闲端口>
                       │
                       ▼
        轮询 /api/ping 直到就绪（最多 15s；失败则回读 output/server.json 对账）
```

- **必须 `start /d`**：`start /b` 不继承 `Popen(cwd=...)`，项目搬家后子进程会以旧目录为 cwd，
  继续读写旧的 `output/`（真实踩过）；
- 服务日志追加到 `output/server.log`，其中 `serving <url>` 那一行是权威地址；
- `server.py --serve`（前台阻塞）只用于"想让终端窗口承载服务"的场景；这条路会按
  `open_browser` 决定是否开浏览器。

## 八、失败模式速查

| 现象 | 最可能的原因 | 处置 |
| --- | --- | --- |
| `curl 127.0.0.1:8765` 返回 502 | 环境代理劫持了回环 | 加 `--noproxy '*'` |
| 打开 8765 是别的程序 / 打不开 | 端口被占用后已顺延 | 看启动日志的 `serving <url>` 或 `output/server.json` 的 `port` |
| 启动即退出（退出码 2） | 起始端口起连续 20 个都不可用 | 改用 `--port` 指定空闲段，或腾出端口 |
| 浏览器没弹出来 | 无桌面环境 / 没装默认浏览器 / 配置关了 | 手动访问日志里的地址；这是非致命提示 |
| 收藏/下载点了没反应 | 服务没起，或页面以 `file://` 打开但服务离线 | 先 `/api/ping`（顺延后要用实际端口） |
| 收藏记录丢失 | 并发写覆盖（旧版本） | 现版本由 `_lib_lock` 保护；若复现请提 issue 并附日志 |
| 下载报"未找到论文元数据" | 该篇已不在当前池（过期收藏） | 重新跑一次流水线再下载 |
| 动态页一直显示旧内容 | 服务进程缓存了旧模块 | 现版本每次请求 reload；若仍复现请重启服务 |
| `/api/rebuild` 一直失败 | recommend 或 build_report 报错 | 手动跑这两个脚本看 stderr |

---

相关：[HTTP API](../reference/http-api.md) · [架构总览](overview.md) ·
[故障排查](../operations/troubleshooting.md) · [模块职责](modules.md)
