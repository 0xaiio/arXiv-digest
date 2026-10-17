# 贡献指南

感谢愿意改进这个项目。它是**单人维护的本地工具**，因此协作流程尽量轻，但有三条不可让步的底线：
不引入运行期依赖、不提交个人数据、不破坏"日报只呈现本期新增"的语义。

---

## 一、开始之前

| 想做什么 | 先读 |
| --- | --- |
| 报告 bug | [故障排查](docs/operations/troubleshooting.md)（很多问题在那里已有结论） |
| 提功能建议 | [FAQ](docs/meta/faq.md)（先看是否已有明确取舍） |
| 改代码 | [开发指南](docs/contributing/development.md) |
| 写文档 | [文档中心](docs/documentation.md) 的"贡献文档"一节 |

## 二、报告问题

请尽量包含：

1. 复现步骤（命令 + 期望 + 实际）；
2. 环境（操作系统、Python 版本）；
3. 相关输出：`stderr`、`output/server.log` 末尾；
4. 涉及推荐时附 `output/issue_stats.json` 与 `output/scores.json` 的 Top10 分数；
5. 涉及下载时附 `python netroute.py` 的结论。

**不要附**：`config.json` / `interests.json` 的完整内容（可能含本机路径）、任何 cookie 或 token。
需要提供画像时，请把 `owners[].site`、路径等敏感字段替换掉。

## 三、提 PR

### 流程

```bash
git checkout -b feat/short-description
# 改代码 + 改文档（两者必须同批提交）
python -m py_compile *.py tools/*.py
python tools/concurrency_check.py
git commit -m "feat: 一句话说明"
git push -u origin feat/short-description
```

### 要求

| 要求 | 说明 |
| --- | --- |
| **一个 PR 一件事** | 修 bug 与重构请分开，便于审查与回滚 |
| **必须跑对应回归** | 动了并发跑 `concurrency_check`；动了页面跑 `dv_unify_check` / `ui_file_check`；动了 `/profile` 跑 `owner_ui_check` |
| **同步文档** | 改接口 / 字段 / 命令 / 语义，必须一起改对应参考页并把新文档登记进 [docs/documentation](docs/documentation.md) 与 [README](README.md) |
| **不新增运行期依赖** | 主流程只用标准库；确实需要时先在 issue 里讨论 |
| **注释写"为什么"** | 项目里的注释主要用于记录踩过的坑，复述代码的注释会被要求删除 |
| **面向用户的文案用中文** | 错误信息、toast、按钮文字保持中文且说人话 |

### 提交信息

用 Conventional Commits 前缀（历史提交已混用中英文，保持可读即可）：

```
feat:     新增能力
fix:      修复缺陷
docs:     仅文档
refactor: 不改变行为的结构调整
chore:    构建 / 忽略规则 / 脚本
```

正文写清**根因**与**影响面**，不要只写"修复了一个 bug"。

## 四、红线

以下改动会被直接拒绝：

| 红线 | 原因 |
| --- | --- |
| 提交 `output/`、`config.json`、`interests.json`、`.secrets/`、cookie / token | 个人数据与凭据，仓库是公开的 |
| 用 `git add -f` 绕过 `.gitignore` | 同上 |
| 让网络 IO 持有 `_lib_lock` | 会把整页交互卡死（历史故障，见[服务运行时](docs/architecture/server-runtime.md)） |
| 打开 `learn_neg_topics` / `learn_neg_keywords` 的默认值 | 会让推荐器随曝光偏置整体失效（见[排序算法](docs/architecture/ranking.md)§5） |
| 让 Downvote 的卡片消失（而非变灰划线） | 误点无法撤销 |
| 让 `summaries.json` 的 value 变成对象 | 会让渲染端 `AttributeError` |
| 引入需要联网的 CDN / 前端构建步骤 | 破坏"单文件离线可用" |

## 五、要写文档的话

- 一个主题一个文件，放在 `docs/<类别>/`，不要平铺在 `docs/` 根下；
- 文档内链接一律用**相对路径**，保证本地可跳转；
- 新文档必须被 [文档中心](docs/documentation.md) 与 [README](README.md) 的索引收录；
- 示例中不要出现真实人名、真实本机路径——用中性占位（`Ada Lovelace`、`./papers`）。

## 六、许可

项目当前未附开源许可（默认保留所有权利）。提交 PR 即表示你同意以相同条件提供你的贡献；
若计划大规模复用，请先开 issue 讨论许可问题。

---

相关：[开发指南](docs/contributing/development.md) · [测试与回归](docs/contributing/testing.md) ·
[目录职责](docs/meta/structure.md)
