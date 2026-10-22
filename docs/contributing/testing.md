# 测试与回归

项目有一套 **pytest 测试套件**：825 个用例，覆盖单元 / 集成 / 端到端 / 浏览器四层，
行覆盖率 **91%**（门槛 85%），全量跑完约 80 秒（本机实测）。

运行期仍然**零第三方依赖**——测试依赖只在 `requirements-dev.txt` 里。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest                 # 825 passed
python -m pytest --cov           # 附带覆盖率，低于 85% 直接失败
```

---

## 一、分层与目录

```
tests/
├─ conftest.py                 # 沙箱隔离（所有路径常量重定向）+ 数据工厂 + HTTP 客户端
├─ unit/                       # 680 个：纯函数与单模块，不联网、不起服务
│  ├─ test_paths.py            #   ★ 路径唯一来源：各模块常量必须与 paths 一致
│  ├─ test_arxiv_cats.py       #   ★ 官方分类表自洽性、校验七分支、纠错、邻域推导
│  ├─ test_paperutil.py        #   短号归一、文件名、配置与库文件读写
│  ├─ test_datapack.py         #   ★ 数据包：名称校验、覆盖/合并/拒绝、清单哈希、导出中性化
│  ├─ test_scoring.py          #   ★ 打分常量、特征拆解、数值算例（100% 覆盖）
│  ├─ test_textscan.py         #   ★ HTML 去标签、人名、实词分层、主题命中
│  ├─ test_fetchsrc.py         #   ★ arXiv/网页/文档 取数适配（_get 注入，不联网）
│  ├─ test_customize.py        #   分类（校验/批量/排序/整体替换）/ 下载目录 / 主来源 / 合并视图
│  ├─ test_customize_sources.py#   兴趣来源解析（本地文档 / 链接 / derive）
│  ├─ test_profile.py          #   行为学习状态机、上下限裁剪、负向开关
│  ├─ test_archive.py          #   本期新增判定、bootstrap、同日幂等、期次读写
│  ├─ test_recommend.py        #   打分公式逐项（含数值算例）、关键词正则
│  ├─ test_fetch_parsers.py    #   Atom/RSS 解析、并集合并、单位清洗
│  ├─ test_fetch_mains.py      #   三个抓取脚本的 main()（网络换桩）
│  ├─ test_fetch_affil.py      #   单位抽取边界 + targets + 缓存 + main()
│  ├─ test_netroute.py         #   候选顺序、错误文案、缓存读写
│  ├─ test_netroute_probe.py   #   探测 / 负缓存 / fetch_first 多 URL 回退
│  ├─ test_netroute_net.py     #   opener / 请求头 / 本机端口枚举
│  ├─ test_serveport.py        #   ★ 端口校验/占用探测/顺延/端口改写/浏览器开关/运行期信息
│  ├─ test_service.py          #   ★ PaperIndex TTL/并发、注入点、批量保序、重建
│  ├─ test_routes.py           #   ★ 路由表完整性、精确优先、Runtime 白名单、参数校验
│  ├─ test_server_download.py  #   download_pdf 落盘的全部分支
│  ├─ test_server_startup.py   #   ★ 启动：端口顺延、日志、server.json、浏览器开关与失败兜底
│  ├─ test_run_daily_helpers.py#   子进程封装 run() 与服务拉起
│  ├─ test_compat_facade.py    #   ★ 兼容门面：重构不得移除的对外符号清单
│  └─ test_sandbox_isolation.py#   ★ 测试自身的回归：不许写进真实 output/
├─ integration/                # 91 个：多模块协作，会起真实 HTTP 服务
│  ├─ test_pipeline.py         #   抓取池 → 推荐 → 渲染 → 归档 的产物契约；分类顺序 → 页面小节顺序
│  ├─ test_server_api.py       #   全部路由：状态码、副作用、CORS、目录穿越
│  ├─ test_datapack_api.py     #   ★ 数据包接口 + 「首屏不泄漏」边界（接口/页面只出现包名）
│  └─ test_run_daily.py        #   编排顺序、开关语义、RSS 降级、未选类别时的引导路径
└─ e2e/                        # 24 个：完整用户链路
   ├─ test_user_journey.py     #   阅读 → 收藏 → 下载 → Downvote → 分数变化 → 撤销
   ├─ test_ui_browser.py       #   真实 Edge 点击：变灰、删除线、按钮文字、无 JS 报错
   ├─ test_category_picker_ui.py #  类别选择器：联动/搜索/多选/拖拽排序/即时校验/引导页
   └─ cdp.py                   #   上面两个共用的小底座（Edge + CDP，不依赖 Selenium）
```

★ = 这次重构新增或改写的用例：**每一层都补了对应测试**，不是只补单元层。

四层各管一件事，不重叠：

| 层 | 回答的问题 | 速度 | 依赖 |
| --- | --- | --- | --- |
| unit | 这个函数的**契约**对不对（含边界） | 15 s | 无 |
| integration | 模块**拼起来**还对不对（文件、状态码、副作用） | ~25 s | 本地端口 |
| e2e | 用户**能不能用**（完整一天的操作） | ~5 s | 本地端口 |
| ui | 用户**看到**的是不是对的（CSS/JS 真的生效、拖拽真的能排） | ~20 s | Edge + CDP |

## 二、测试范围

### 核心模块（16 个，全覆盖）

`arxiv_cats` · `paperutil` · `datapack` · `customize` · `profile` · `archive` · `recommend` ·
`build_report` · `server` · `serveport` · `run_daily` · `netroute` · `fetch_arxiv` · `fetch_expand` ·
`fetch_rss` · `fetch_affil`

### 关键业务流程

| 流程 | 覆盖用例 |
| --- | --- |
| 首次安装 | `test_fresh_install_has_no_personal_traces`（含三层页面渲染）、`test_pack_in_presets_is_not_loaded_automatically`、`test_config_is_seeded_from_example_on_first_use`、`test_shipped_example_has_no_personal_categories`、`test_interests_file_is_created_from_example` |
| 数据包导入/导出 | `test_datapack.py`（32 个：名称校验/覆盖与合并/清单哈希/中性化/往返）、`test_datapack_api.py`（13 个：接口状态码 + 「首屏只出现包名」边界） |
| 选择分类（通用版） | `test_arxiv_cats.py`（54 个：表自洽/校验/纠错/检索/邻域）、`test_add_categories_bulk_partial_success`、`test_reorder_rejects_missing_extra_and_duplicate`、`test_digest_sections_follow_config_category_order` |
| 类别选择器 UI | `test_category_picker_ui.py`（15 个：联动/搜索/多选/拖拽落点/即时校验/引导页） |
| 抓取 → 推荐 → 渲染 → 归档 | `test_pipeline_writes_all_expected_artifacts` 等 18 个 |
| 只呈现本期新增 | `test_issue_core_only_contains_this_issue`、`test_previous_issue_is_excluded_next_day`、`test_same_day_rerun_is_idempotent` |
| API 限流降级 | `test_partial_fetch_failure_triggers_rss_fallback`、`test_rss_merges_into_both_pools`、`test_merge_pool_is_union_and_never_drops` |
| 行为学习 | `test_favorite_raises_topic_mult_and_keyword_weights`、`test_downvote_only_penalizes_that_paper`、`test_undownvote_clears_penalty` |
| 下载与收藏 | `test_download_writes_file_and_cleans_part`、`test_download_skips_existing_file`、`test_favorite_then_downvote_then_favorite` |
| 画像主来源增删改 | `test_owner_crud_over_http`、`test_update_owner_rename_moves_people_entry`、`test_remove_owner_unlinks_and_refuses_last` |
| 交互一致性 | `test_downvote_click_changes_visual_state`（真点，断言 `opacity .42` + 删除线） |
| 归档只增不改 | `test_archive_journey_can_look_back`（哈希比对） |
| 启动与端口顺延 | `test_serveport.py`（50 个：端口解析/占用探测/顺延上限/端口耗尽/页面端口改写/浏览器开关/`server.json` 往返）、`test_server_startup.py`（16 个：真占端口后顺延、绑定被抢重试、日志给实际地址、`--port` 覆盖、浏览器失败不影响启动） |

### 边界与负面路径

不是「正常路径能跑通」就够，以下每条都有专门用例：

| 类别 | 例子 |
| --- | --- |
| 输入畸形 | 非法 XML、坏 JSON、空文件、超长文本、纯数字单位、大小写错的分类（`CS.DB`）、不存在的分类（`cs.ZZ`）、只写了主类的分类（`physics`） |
| 缺文件 | 无 `config.json` / `interests.json` / 无抓取数据 / 无 `archive.db` |
| 空结果 | 抓取返回 `{"error": ...}`、推荐全部不达标（兜底）、无收藏 |
| 并发与幂等 | 同篇重复下载、同日重跑流水线、`mark_seen` 只记首次期次 |
| 越界 | 主题倍率 `[0.25, 3.0]`、关键词 `[-4, 4]`、降权词最多计 4 个、单位最多 12 条、端口 `0`/`65536`/非数字 |
| 启动失败 | 连续 20 个端口不可用（退出码 2）、绑定被抢、无桌面环境开浏览器抛错、`server.json` 不可写 |
| 错误码 | `400` 缺 id / 非法 action / 非法日期，`404` 未知接口与目录穿越，`500` 服务端异常 |
| 隐私 | 首次初始化生成的配置里不得出现任何真实人名/本机路径 |

## 三、覆盖率

门槛写在 `.coveragerc`（`fail_under = 85`），`pytest --cov` 不达标直接非零退出。

| 模块 | 行覆盖率 | 说明 |
| --- | --- | --- |
| `scoring.py` | 100% | 纯函数，无 IO 无全局状态 |
| `arxiv_cats.py` | 99% | 只剩 `__main__` 的 `raise SystemExit` 那一行 |
| `paths.py` | 98% | 除 `main()` 的少量输出分支外全覆盖 |
| `serveport.py` | 98% | 只剩真实 `webbrowser` 调用与极少数 OSError 分支 |
| `textscan.py` | 98% | 未覆盖的是 HTML 解析器的极端容错分支 |
| `customize.py` | 96% | |
| `archive.py` | 95% | |
| `paperutil.py` | 95% | |
| `routes.py` | 93% | 未覆盖的是页面渲染异常时的兜底分支 |
| `server.py` | 94% | 未覆盖的是真实 `serve_forever` 循环与部分异常兜底 |
| `service.py` | 93% | 未覆盖的是真实下载的成功路径（真网络） |
| `recommend.py` | 91% | |
| `run_daily.py` | 89% | 未覆盖的是 `--serve` 前台阻塞与 `main` 的 CLI 尾部 |
| `fetch_rss.py` | 88% | |
| `profile.py` | 87% | |
| `server.py` | 87% | 未覆盖的是 `main()` 的 `serve_forever` 与几个异常兜底 |
| `build_report.py` | 87% | 未覆盖的是少数渲染分支与 `main()` 的 CLI 尾部 |
| `netroute.py` | 86% | 未覆盖的是真实探测计时分支与日志输出 |
| `fetch_arxiv.py` | 84% | 未覆盖的是 `fetch()` 的重试循环（真网络） |
| `fetch_expand.py` | 81% | 同 `fetch_arxiv` |
| `fetchsrc.py` | 79% | 未覆盖的是 `_http_get` 真实网络与 PDF 解析 |
| `fetch_affil.py` | 78% | 未覆盖的是 `fetch_html`（真网络）与部分清洗分支 |
| **合计** | **90%** | 19 个模块，3514 条可执行语句 |

**为什么不是 100%**：剩下的是「只在真实网络/真实浏览器交互里才走到」的分支。
把它们用 mock 强行走一遍只会增加假信心，不如老实标出来。若要逐行看：

```bash
python -m pytest --cov --cov-report=html     # 报告在 output/coverage/index.html
python -m pytest --cov --cov-report=term-missing   # 直接列出未覆盖行号
```

## 四、运行方式

### 全部

```bash
python -m pytest
```

### 按层 / 按标记

```bash
python -m pytest -m unit                 # 只跑单元（13s，改纯函数时最常用）
python -m pytest -m integration          # 集成（起真实 HTTP 服务）
python -m pytest -m e2e                  # 端到端
python -m pytest -m "not ui"             # 跳过浏览器层（无 GUI 环境）
```

### 单文件 / 单用例

```bash
python -m pytest tests/unit/test_recommend.py -v
python -m pytest tests/unit/test_recommend.py::test_score_is_base_plus_weighted_topics_plus_keywords
python -m pytest -k "downvote and not ui"
```

### 覆盖率

```bash
python -m pytest --cov                     # 终端 + 门槛检查
python -m pytest --cov --cov-report=html   # 另出 output/coverage/index.html
```

### 浏览器层

`tests/e2e/test_ui_browser.py` 用 Edge 的 CDP 无头驱动（不依赖 Selenium），
以下情况**自动跳过**，不算失败：

| 条件 | 行为 |
| --- | --- |
| 没有 Edge（非 Windows / 未安装） | `skip` |
| 没有 `websocket-client` | `skip` |
| 环境变量 `SKIP_UI_E2E=1` | `skip`（CI 建议值） |

### CI 建议

```yaml
- run: python -m pip install -r requirements-dev.txt
- run: python -m py_compile *.py tools/*.py
- run: python -m pytest -m "not ui" --cov      # 无 GUI 环境
```

## 五、沙箱：为什么测试不会碰你的真实数据

每个用例都在 `tmp_pytest/<tag>-<随机后缀>/` 下工作（`_fresh_dir()` 用 `tempfile.mkdtemp`，
**不能用 `tag-pid-序号`**：沙箱禁删、目录会跨轮次累积，pid 一旦复用就会继承上一轮的残留），
`conftest.py` 把 **10 个模块**的路径常量逐个重定向过去：

```
paperutil.OUT / CONFIG_PATH / LIB_PATH      customize.INTERESTS / EXTRA_PATH
profile.OUT / PROFILE_PATH / BEHAVIOR_PATH  archive.OUT / DB_PATH / ARCHIVE_DIR
recommend.OUT  build_report.OUT  run_daily.OUT  server.OUT  netroute.OUT / CACHE_PATH
fetch_rss.OUT  fetch_affil.OUT / AFF_PATH    datapack.PACKS
```

> `datapack.PACKS` 也要重定向：真实 `presets/` 里就有作者本人的画像，
> 读错了会让"新装是干净的"这类用例失效（测出来永远是"有数据"）。

三条硬性设计，每一条都是踩过坑之后加的：

1. **不用 `tmp_path`/`tmpdir`**：本机沙箱对删除是累积计数拦截的，pytest 启动时会
   `rmtree` basetemp、收尾会清理 numbered dirs，整条命令会被拒。因此 `pytest.ini` 里
   `-p no:tmpdir -p no:cacheprovider`，沙箱目录**从不删除**，且已 gitignore。
2. **隔离断言**（`conftest.assert_isolated`）：每次建沙箱后检查上述常量是否都落在
   本用例目录内，漏一个立刻失败。
3. **自动发现**（`tests/unit/test_sandbox_isolation.py`）：扫描源码里所有
   `OUT = pu.OUT`，若某模块没登记进 `_OUT_OWNERS` 就报错——新加模块忘了重定向会被
   当场拦住，而不是等某天发现真实 `output/` 被测试写坏。

> 这不是假想的风险：`fetch_rss.OUT` 与 `fetch_affil.AFF_PATH` 曾被漏掉，
> 测试真的重写了作者的 `raw.json` 与 `affiliations.json`。前者靠 git 无关的元数据修复，
> 后者用备份恢复。上面第 2、3 条就是这件事的产物。

## 六、写断言的几条约定

| 约定 | 理由 |
| --- | --- |
| 断言**行为**与**产物**，不断言私有实现细节 | 重构不该导致大面积红灯 |
| 数值断言给容差（`pytest.approx`） | 浮点累加顺序会变 |
| 断言里写清「期望 vs 实测」 | `assert penalized < base - 6, "…（%s -> %s）"` 比裸 assert 好排查 |
| 时间、网络、随机都必须可控 | 一律 `monkeypatch`，不写 `sleep(3)` |
| 一个用例只证明一件事 | 失败时能直接定位 |
| 新发现的缺陷：先补回归用例，再修 | 保证同一坑不踩第二次 |

## 七、失败怎么读

```
FAILED tests/unit/test_x.py::test_y - AssertionError: 权重翻倍后分数必须明显上升（19.2 -> 19.2）
```

顺序：① 看断言后的中文说明 → ② 判断是「测试期望错」还是「代码行为错」→
③ 若是代码错，先补一条最小回归，再改代码 → ④ 全量重跑。

| 常见现象 | 含义 |
| --- | --- |
| `assert 0.42 == 1` 之类 | 页面 CSS/JS 没生效，或被模板转义破坏 |
| `KeyError` / `FileNotFoundError` | 产物契约变了（字段改名、文件没生成） |
| `Timeout` / `ConnectionRefused` | 服务没起来；检查是否端口被占 |
| `skip: 未找到 Edge` | 浏览器层跳过，不是失败 |

## 八、与 `tools/*_check.py` 的关系

两套东西并存，职责不同：

| | `tests/`（pytest） | `tools/*_check.py` |
| --- | --- | --- |
| 目的 | 开发期回归，快速定位 | 发布前的**黑盒**验收（真下载、真点按钮） |
| 数据 | 沙箱，绝不碰真实数据 | 必要时读写真实 `output/` |
| 粒度 | 函数 / 接口 / 流程 | 整页交互 |
| 何时跑 | 每次改代码 | 发版或交付前 |

`tools/concurrency_check.py` 与 pytest 里的并发断言有重叠，但前者是端到端的进程内实测，
建议两者都保留。清单见 [命令行参考](../reference/cli.md#回归测试)。

## 九、新增测试放哪一层

```
只涉及一个函数、能纯内存验证？           → unit/
需要多个模块 + 文件读写 / HTTP 服务？     → integration/
模拟一次真实用户操作直到看到结果？        → e2e/
需要判断「像素/CSS/JS 是否生效」？        → e2e/ + @pytest.mark.ui
```

加用例时的三件事：

1. 用 `sandbox` / `bare_sandbox` / `seeded` 之一拿隔离环境，别自己建临时目录；
2. 联网/开窗/子进程一律 `monkeypatch`；
3. 在本文「测试范围」表里补一行（否则新能力就是文档盲区）。

## 十、重构时怎么保证「没改行为」

拆模块、移文件、改内部结构时，测试要能回答「对外行为变了吗」。这次重构用了三条手段：

| 手段 | 具体做法 | 挡住的失败 |
| --- | --- | --- |
| **兼容门面清单** | `tests/unit/test_compat_facade.py` 逐一断言旧符号仍可导入（`server.download_pdf`、`customize.parse_link`、`build_report.PAGE`…） | 「拆分时顺手把一个名字搬走了」，tools / 自动化脚本静默失效 |
| **逐字节等价** | 模板外置后，用 `git show HEAD:build_report.py` 取出原三引号字符串，与 `templates/*` 逐字节比对 | 搬运时丢了一个 `%%` 或改了一个换行 |
| **桩化契约** | `test_runtime_forwards_dynamically_so_patching_works` 断言「替换 `server.download_pdf` 后路由层立刻看到新对象」 | 改成 import 期绑定，导致并发回归真的去下载 PDF |

清单**只增不减**：真要删某个符号，必须先显式删掉清单里的一行，让评审看见。

## 十一、保持全绿

红线：**主分支上 `python -m pytest` 必须始终 825 passed、覆盖率 ≥ 85%。**

改代码时的最小自查表：

| 改了什么 | 至少跑 |
| --- | --- |
| 纯函数 / 解析逻辑 | `pytest -m unit` |
| 打分公式 | `pytest tests/unit/test_recommend.py tests/integration/test_pipeline.py` |
| 接口 / 服务端 | `pytest -m integration` |
| 页面模板 / CSS / JS | `pytest -m e2e`（含浏览器层） |
| 流水线编排 | `pytest tests/integration/test_run_daily.py` |
| 准备提交 | `pytest --cov` 全量 |

失败优先怀疑自己的改动，而不是先改测试期望——除非能说明「旧期望本身写错了」
（本项目里两种情况都真实发生过，见 [CHANGELOG](https://github.com/0xaiio/arXiv-digest/blob/main/CHANGELOG.md)）。

---

相关：[开发指南](development.md) · [故障排查](../operations/troubleshooting.md) ·
[命令行参考](../reference/cli.md)
