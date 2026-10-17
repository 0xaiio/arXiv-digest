# 测试与回归

项目没有引入 pytest 等框架，回归测试就是一组**可独立运行的脚本**：
每个脚本自己起服务或起浏览器，断言失败时打印原因并以非 0 退出。

这个选择是刻意的——运行期零依赖，测试也就不该拖入依赖链。

---

## 一、清单

| 脚本 | 需要浏览器 | 需要服务在跑 | 耗时 | 验证什么 |
| --- | --- | --- | --- | --- |
| `tools/concurrency_check.py` | ❌ | ❌（自己起临时服务） | ~5 s | 下载中另一篇 Downvote 不被阻塞、批量并行、同一篇仍串行 |
| `tools/dv_unify_check.py` | ✅ Edge | ✅ 8765 | ~15 s | 三处 Downvote 的视觉/行为一致、可撤销、乐观更新 |
| `tools/owner_ui_check.py` | ✅ Edge | ✅ 8765 | ~15 s | `/profile` 画像主来源的增删改（只用临时条目） |
| `tools/ui_file_check.py` | ✅ Edge | ✅ 8765 | ~10 s | 日报以 `file://` 打开时的跨源交互、链接改写、无报错 toast |
| `tools/dl_button_check.py` | ✅ Edge | ✅ 8765 | ~10 s | 真实点一次下载按钮，断言 toast 与按钮态 |

> 浏览器类脚本用 Edge 的 CDP 接口无头驱动（`msedge.exe --headless=new --remote-debugging-port=...`），
> 不依赖 Selenium/Playwright。Edge 不在默认路径时需改脚本顶部的 `EDGE` 常量。

一次性探针 `ui_probe.py` / `ui_shots.py` / `ui_final_check.py` / `ui_check_v3.py` 是开发期留档，
不属于发布闸门，失败不代表代码坏了。

## 二、跑法

### 并发回归（无需浏览器，最推荐先跑）

```bash
python tools/concurrency_check.py
```

它**不碰真实数据**：进程内起一个 `ThreadingHTTPServer`、把 `download_pdf` 桩化成 2 秒延迟、
`library.json` 指向临时文件。断言三件事：

| 断言 | 期望 |
| --- | --- |
| 一篇下载进行中，另一篇 Downvote 的响应时间 | < 0.5 s（拆锁前是 2.0 s） |
| 批量下载 3 篇的总耗时 | ≈ 单篇耗时（并发），而不是 3 倍 |
| 同一篇并发下载两次 | 耗时 ≈ 2 倍（仍串行，说明单篇锁生效） |

端口默认 `8799`，可用环境变量 `CONC_PORT` 覆盖。

### 浏览器类回归

前置：服务在线、当期日报已生成。

```bash
# 服务没在跑就先起
python server.py --no-open &

python tools/dv_unify_check.py
python tools/owner_ui_check.py
python tools/ui_file_check.py output/arxiv_digest_20261017.html   # 传当期文件
python tools/dl_button_check.py
```

`ui_file_check.py` 的**位置参数是日报文件路径**；不带参数时按当天日期猜，跨天跑会 404。
`dl_button_check.py` 只点已经下载过的论文，不会写出新文件。

## 三、各脚本到底断言什么

### `dv_unify_check.py`

逐个真实点击三个模块里的一张卡片，检查 CSS 计算值与位次：

| 检查项 | 期望 |
| --- | --- |
| `opacity` | `0.42`（三个模块一致） |
| 标题 `text-decoration` | `line-through` |
| 是否被 `hidden` | 否（卡片不消失） |
| 点击后位次 | 不变（钉在原位） |
| 是否同步变灰 | 是（乐观更新，不等接口返回） |
| 再点一次撤销 | 恢复 `opacity: 1` 且无删除线 |

### `owner_ui_check.py`

在 `/profile` 上依次：新增 → 编辑（含改名）→ 删除，并断言表单清空、卡片更新、
旧卡片消失。**只使用临时条目**（如 `UI Test Owner`），结束时清理，不会污染真实画像。

### `ui_file_check.py`

用 `file://` 打开日报，断言：

- `APIBASE` 被改写成 `http://127.0.0.1:8765`；
- 站内链接变成绝对地址；
- 点收藏能往返（接口 200 且按钮状态正确）；
- 过程中没有 error 级 toast。

### `dl_button_check.py`

点一次下载按钮，断言出现成功 toast、按钮恢复可用、服务端返回了 `path`。

## 四、结果怎么读

成功时打印汇总行并以 `0` 退出，例如：

```
[1] 下载中 Downvote：0.014s  [ok]
[2] 批量 3 篇：2.05s  [ok]
[3] 同一篇并发：4.02s  [ok]
ALL PASS
```

失败时打印具体断言与实测值，例如：

```
[FAIL] rec: opacity=1 （期望 0.42）
```

常见失败原因：

| 现象 | 原因 |
| --- | --- |
| 浏览器类脚本连不上调试端口 | Edge 路径不对，或已有 Edge 进程占用同一 profile |
| `ui_file_check` 404 | 传的日报文件名不存在（按当天日期猜错了） |
| `dv_unify` 全部失败 | 服务没起（页面 JS 请求失败，卡片不变灰） |
| `owner_ui` 报告残留 | 上次异常中断留下了 `UI Test Owner`，手动在 `/profile` 删掉 |

## 五、加一个新回归

约定：

1. 放 `tools/`，文件名以 `_check.py` 结尾；
2. 顶部 docstring 写"为什么需要它"（贴一次真实故障最好）；
3. 自带 setup/teardown：**不要污染真实 `library.json` / `interests.json`**，
   要么用临时路径（参考 `concurrency_check.py`），要么只用临时条目并在结束时清理；
4. 失败打印可定位的信息（哪个断言、实测值、期望值），以非 0 退出；
5. 收尾清理临时文件与临时进程（服务、浏览器 profile）。

## 六、CI 建议

`concurrency_check.py` 是唯一能在无 GUI 环境跑的回归，适合放进 CI：

```yaml
- run: python -m py_compile *.py tools/*.py
- run: python tools/concurrency_check.py
```

浏览器类脚本需要 Windows + Edge，建议只在本机提交前手动跑。

---

相关：[开发指南](development.md) · [故障排查](../operations/troubleshooting.md) ·
[命令行参考](../reference/cli.md)
