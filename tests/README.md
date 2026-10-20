# tests — 测试套件

完整说明（分层、覆盖范围、覆盖率、沙箱设计、失败排查）在
**[docs/contributing/testing.md](../docs/contributing/testing.md)**，这里只放最短上手路径。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest                 # 全量：666 passed，约 67s
python -m pytest -m unit         # 只跑单元，约 15s
python -m pytest --cov           # 覆盖率（门槛 85%，当前 90%）
```

## 分层速查

| 目录 | 标记 | 验证什么 |
| --- | --- | --- |
| `unit/` | `@pytest.mark.unit` | 纯函数与单模块，不联网、不起服务 |
| `integration/` | `@pytest.mark.integration` | 多模块协作产物契约、全部 HTTP 路由、编排与降级 |
| `e2e/` | `@pytest.mark.e2e` | 完整用户链路；`@pytest.mark.ui` 需要 Edge（缺失自动 skip） |

## 重构相关的四个文件

| 文件 | 作用 |
| --- | --- |
| `unit/test_compat_facade.py` | **兼容门面清单**：重构不得移除的对外符号，只增不减 |
| `unit/test_paths.py` | 各模块路径常量必须与 `paths.py` 一致 |
| `unit/test_routes.py` | 路由表完整性 + 精确优先 + `Runtime` 白名单 + 桩化契约 |
| `unit/test_service.py` | `PaperIndex` TTL/并发、注入点、批量保序、重建分支 |
| `unit/test_arxiv_cats.py` | 官方分类表自洽（格式/唯一/归属）、校验七分支、纠错、邻域推导 |

## 约定

- 每个用例都在 `tmp_pytest/` 下的独立沙箱里跑，**不会**碰真实的 `output/`、
  `config.json`、`interests.json`；`conftest.py` 用断言保证这一点；
- 联网、开窗、子进程一律 `monkeypatch`；
- 新增模块若把 `OUT` 固化在模块级，必须登记到 `conftest._OUT_OWNERS`，
  否则 `test_sandbox_isolation.py` 会失败；
- 浏览器层用 `dispatchEvent` 而不是 `element.click()`：headless Edge 下后者对
  「被 data-limit 隐藏或刚被 DocumentFragment 重排过」的按钮有时不冒泡到 document；
- 两个浏览器用例文件共用 `e2e/cdp.py` 的导航/点击底座，别再各写一份。
