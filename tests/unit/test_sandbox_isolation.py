# -*- coding: utf-8 -*-
"""测试基础设施自身的回归：**任何测试都不许写进真实的 output/ 与个人数据**。

这条用例存在的理由：`fetch_rss.OUT` 曾在 import 时被固化成真实路径而漏掉重定向，
测试把用户的真实抓取池重写了一遍。因此隔离不是「约定」，而是被断言检查的不变量。
"""
import pytest

import conftest as C
import paperutil as pu

pytestmark = pytest.mark.unit


def test_all_modules_are_redirected_into_the_sandbox(sandbox):
    """每个持 OUT 的模块都必须被重定向（漏一个就会污染真实数据）。"""
    C.assert_isolated(sandbox)          # 内部会给出具体是哪个模块哪个属性


def test_real_project_paths_are_untouched(sandbox):
    real_out = C.ROOT / "output"
    assert str(pu.OUT).startswith(str(sandbox.root))
    assert str(pu.OUT) != str(real_out)

    # 写库只落在沙箱
    lib = pu.load_library()
    lib["favorites"]["2609.99999"] = {"id": "2609.99999", "title": "sandbox only"}
    pu.save_library(lib)
    assert (sandbox.out / "library.json").exists()


def test_every_out_owner_is_registered():
    """新增模块若把 OUT 固化在模块级，必须登记到 _OUT_OWNERS，否则隔离检查会漏。"""
    names = {m.__name__ for m in C._OUT_OWNERS}
    expected = {"paperutil", "profile", "archive", "recommend", "build_report",
                "run_daily", "server", "netroute", "fetch_rss", "fetch_affil"}
    assert expected <= names


def test_every_module_level_out_copy_is_registered():
    """自动发现：源码中形如 `OUT = pu.OUT` 的模块必须全部登记。

    这条比人工清单可靠 —— 新加一个模块忘了重定向，这里会直接失败，
    而不是等到某天发现真实 output/ 被测试写坏。
    """
    import re

    root = C.ROOT
    declared = set()
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"^OUT\s*=\s*pu\.OUT", text, re.M):
            declared.add(path.stem)

    registered = {m.__name__ for m in C._OUT_OWNERS}
    missing = declared - registered
    assert not missing, "这些模块把 OUT 固化在模块级却未登记到 _OUT_OWNERS：%s" % missing


def test_sandbox_dirs_are_unique_per_test(sandbox, bare_sandbox):
    assert sandbox.root != bare_sandbox.root
    assert sandbox.out != bare_sandbox.out
