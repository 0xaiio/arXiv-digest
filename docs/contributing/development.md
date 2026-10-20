# 开发指南

面向想改代码或加功能的人。测试怎么跑见[测试与回归](testing.md)，
"为什么这样设计"见[架构总览](../architecture/overview.md)。

---

## 一、本地开发环境

**必需**：Python 3.9+（运行期只用标准库）。

**跑测试**：`python -m pip install -r requirements-dev.txt`（pytest / pytest-cov /
websocket-client），详见[测试与回归](testing.md)。

**可选**：

| 场景 | 依赖 |
| --- | --- |
| 跑浏览器回归 | Microsoft Edge（用 CDP 无头驱动，无需 Selenium） |
| 跑视频链路 | Node 18+、`cd reel && npm ci`、`pip install edge-tts imageio-ffmpeg` |
| 编辑页面模板 | 无（模板在 `templates/`，按 mtime 自动重读） |

不需要虚拟环境也能跑；建议还是建一个，避免把 `edge-tts` 等装进全局。

## 二、代码风格与约定

项目没有引入 linter 配置（刻意保持零依赖），但有几条硬约定：

| 约定 | 原因 |
| --- | --- |
| 只用标准库（主流程） | `clone` 即用，不需要 `pip install`；新增依赖前请先讨论 |
| 文件编码 `utf-8`，源文件头写 `# -*- coding: utf-8 -*-` | 与既有文件一致；Windows 上避免默认 GBK |
| 写 JSON 用"临时文件 + `os.replace`" | 崩溃时不留下半个文件 |
| 面向用户的错误信息用中文、说人话 | `friendly()` / `msg` 字段都遵循这条 |
| 注释解释"为什么"，不复述"做了什么" | 本项目的注释主要用于记录踩过的坑 |

命名与结构：

- 模块级常量用 `UPPER_SNAKE`（`OUT`、`LIB_PATH`、`DL_WORKERS`）；
- 私有函数前缀 `_`（`_download_one`、`_record_download`）；
- 入口脚本末尾统一 `if __name__ == "__main__": main()`；
- 每个脚本头部 docstring 写"用法 + 为什么存在"，这是本项目文档的第一现场。

## 三、改完什么必须重启 / 重跑

这是最容易踩的坑：页面看起来没变，其实跑的是旧代码。

| 改动 | 必须做什么 |
| --- | --- |
| `server.py` / `routes.py` / `service.py` | **重启服务**（进程内代码不会热更新） |
| `recommend.py` | 重跑 `python recommend.py`（服务不缓存它，但页面读的是产物） |
| `templates/*`（版面 / CSS / JS） | **刷新即可**（`read_template()` 按 mtime 重读）；日报是静态文件，要看到效果需重跑 `build_report.py` |
| `build_report.py` 渲染逻辑 | `/favorites`、`/profile`、`/archive` 会 `reload` 该模块，**刷新即可**；日报需重跑 |
| `config.json` 的 `port` | 重新生成页面即可（端口在渲染时替换）；服务自身要换端口仍需重启 |
| `paperutil.py` / `customize.py` / `profile.py` | 重启服务 + 重跑相关阶段 |
| `datapack.py` | 重启服务（它被 `server`/`routes` 导入）；CLI 直接生效 |
| `presets/<名字>/` 里的文件 | **什么都不用做**：运行期不读它，只有显式导入才生效 |
| `interests.json` / `config.json` | 点「↻ 重算推荐」或 `--skip-fetch --skip-affil` |

一条命令完成"重算 + 重渲染"：

```bash
python run_daily.py --skip-fetch --skip-affil
```

## 四、调试手法

### 1. 先看产物，再看代码

几乎所有问题都能从文件看出来：

```bash
python profile.py                        # 画像倍率、关键词极值、被 Downvote 的
python -c "import archive; print(archive.stats())"
cat output/issue_stats.json              # 当期规模 + 是否走了兜底
```

`output/scores.json` 是全池打分快照，判断"内容弱"还是"画像坏"的第一手证据
（方法见[排序算法](../architecture/ranking.md) §6）。

### 2. 内联 JS 出错：把 `<script>` 提出来做语法检查

页面渲染正常但按钮"没反应"，常见原因是内联 JS 有语法错误。手法：

```bash
python - <<'PY'
import re
h = open('output/arxiv_digest.html', encoding='utf-8').read()
for i, b in enumerate(re.findall(r'<script>(.*?)</script>', h, re.S)):
    open('output/_blk%d.js' % i, 'w', encoding='utf-8').write(b)
PY
for f in output/_blk*.js; do node --check "$f"; done
```

比在浏览器控制台里猜快得多。**已知陷阱**：`build_report.py` 的页面模板用 `%` 格式化，
内联 JS 里写 `'\n'` 会被 Python 先解析成真换行，导致整段脚本语法错误——模板里必须写 `\\n`。

### 3. 服务端问题看日志

```bash
tail -f output/server.log        # 服务 stdout/stderr
```

`traceback` 会打在这里；`/api/*` 的异常也会返回 `msg` 给前端。

### 4. 下载问题先看路由

```bash
python netroute.py               # 结论：可用路由 = ...
python netroute.py --forget      # 清缓存重探
```

## 五、提交前检查清单

```bash
# 1) 语法
python -m py_compile *.py tools/*.py

# 2) 主闸门：pytest 套件（551 用例 / 89% 覆盖）
python -m pytest -m "not ui"        # 快速：单元 + 集成 + 端到端，约 50s
python -m pytest --cov              # 全量 + 覆盖率门槛（85%）

# 3) 交付前补跑黑盒验收（真下载 / 真点按钮）
python tools/concurrency_check.py
python tools/dv_unify_check.py

# 4) 仓库卫生
git status --short
git diff --cached | grep -iE 'cookie|token|secret|password'    # 应为空
```

**绝不能提交**：`output/`、`.secrets/`、`config.json`、`interests.json`、任何 cookie / token。
它们都在 `.gitignore` 里，如果 `git status` 出现了，说明忽略了规则被改了——先修规则，不要 `add -f`。

## 六、加一个新功能的推荐路径

以"加一个画像信号（例如'讨厌的系统名'）"为例：

1. **数据结构**：在 `interests.json` 加字段，同步更新 `interests.example.json`；
2. **读写层**：若需要页面可改，在 `customize.py` 加 `add/update/remove`（只改目标键）；
3. **打分**：`recommend.features()` 产出该信号，`score()` 计入；
4. **前端**：若要在浏览器重排中生效，需把该信号放进 `papers_index.json` 并改 `rescore()`；
5. **页面**：`build_report.build_profile_page()` 加渲染，`server.py` 加接口（如需要）；
6. **文档**：更新 [interests.md](../reference/interests.md) 与 [ranking.md](../architecture/ranking.md)；
7. **回归**：至少跑一次 `--skip-fetch` 重算，确认没有让推荐数归零。

## 七、目录与文档的对应关系

新增文件前先看[目录职责](../meta/structure.md)：根目录只放**主流程模块**，
一次性/维护脚本放 `tools/`，文档放 `docs/<类别>/`。每个新文档必须被
[文档中心](../documentation.md) 与 [README](https://github.com/0xaiio/arXiv-digest#readme) 收录。

---

相关：[测试与回归](testing.md) · [贡献指南](https://github.com/0xaiio/arXiv-digest/blob/main/CONTRIBUTING.md) ·
[目录职责](../meta/structure.md) · [模块职责](../architecture/modules.md)
