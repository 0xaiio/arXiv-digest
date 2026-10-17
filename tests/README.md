# tests — 测试套件

完整说明（分层、覆盖范围、覆盖率、沙箱设计、失败排查）在
**[docs/contributing/testing.md](../docs/contributing/testing.md)**，这里只放最短上手路径。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest                 # 全量：305 passed，约 43s
python -m pytest -m unit         # 只跑单元，13s
python -m pytest --cov           # 覆盖率（门槛 85%）
```

约定：

- 每个用例都在 `tmp_pytest/` 下的独立沙箱里跑，**不会**碰真实的 `output/`、
  `config.json`、`interests.json`；`conftest.py` 用断言保证这一点；
- 联网、开窗、子进程一律 `monkeypatch`；
- 新增模块若把 `OUT` 固化在模块级，必须登记到 `conftest._OUT_OWNERS`，
  否则 `test_sandbox_isolation.py` 会失败。
