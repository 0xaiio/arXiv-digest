# -*- coding: utf-8 -*-
"""paths：路径唯一来源的一致性契约。

这层没有业务逻辑，但它一旦漂移，后果是「测试写坏真实数据」那一类事故，
所以断言的重点是**所有模块看到的路径都来自同一处**。
"""
import os

import pytest

import archive as AR
import customize as CZ
import fetch_affil as FA
import netroute as NR
import paperutil as pu
import paths
import profile as PF
import service
import server as S

pytestmark = pytest.mark.unit


def test_root_is_this_project():
    assert os.path.exists(os.path.join(paths.ROOT, "paths.py"))
    assert os.path.exists(os.path.join(paths.ROOT, "server.py"))


def test_under_root_joins_relative_to_root():
    assert paths.under_root("docs") == os.path.join(paths.ROOT, "docs")
    assert paths.under_root("a", "b.txt") == os.path.join(paths.ROOT, "a", "b.txt")


def test_output_lives_under_root():
    assert paths.output_dir() == os.path.join(paths.ROOT, "output")


@pytest.mark.parametrize("fn, name", [
    (paths.config_path, "config.json"),
    (paths.interests_path, "interests.json"),
    (paths.library_path, "library.json"),
    (paths.profile_state_path, "profile_state.json"),
    (paths.behavior_path, "behavior.json"),
    (paths.archive_db_path, "archive.db"),
    (paths.netroute_cache_path, "netroute.json"),
    (paths.affiliations_path, "affiliations.json"),
    (paths.interests_extra_path, "interests_extra.json"),
])
def test_each_getter_points_at_its_filename(fn, name):
    assert os.path.basename(fn()) == name
    assert fn().startswith(paths.ROOT)


def test_runtime_files_are_under_output():
    """运行产物统一在 output/（这样一条 .gitignore 规则就能兜住）。"""
    for fn in (paths.library_path, paths.profile_state_path, paths.behavior_path,
               paths.archive_db_path, paths.archive_dir, paths.netroute_cache_path,
               paths.affiliations_path, paths.interests_extra_path):
        assert fn() == os.path.join(paths.output_dir(), os.path.basename(fn()))


def test_personal_configs_stay_out_of_output():
    """config.json / interests.json 属个人配置，放在仓库根由用户直接编辑。"""
    for p in (paths.config_path(), paths.interests_path()):
        assert os.path.dirname(p) == paths.ROOT


def test_modules_agree_with_paths_module():
    """各模块的常量必须与 paths 完全一致（否则就是有人又自己拼了路径）。"""
    assert pu.OUT == paths.OUT
    assert pu.CONFIG_PATH == paths.CONFIG_PATH
    assert pu.LIB_PATH == paths.LIB_PATH
    assert CZ.INTERESTS == paths.INTERESTS
    assert CZ.INTERESTS_EXAMPLE == paths.INTERESTS_EXAMPLE
    assert CZ.EXTRA_PATH == paths.INTERESTS_EXTRA_PATH
    assert PF.PROFILE_PATH == paths.PROFILE_STATE_PATH
    assert PF.BEHAVIOR_PATH == paths.BEHAVIOR_PATH
    assert AR.DB_PATH == paths.ARCHIVE_DB_PATH
    assert AR.ARCHIVE_DIR == paths.ARCHIVE_DIR
    assert NR.CACHE_PATH == paths.NETROUTE_CACHE_PATH
    assert FA.AFF_PATH == paths.AFFILIATIONS_PATH


def test_derived_modules_share_paperutil_out():
    """历史上每个模块都写 `OUT = pu.OUT` —— 现在这条链的源头仍是同一个人。"""
    for mod in (PF, AR, FA, S):
        assert mod.OUT == pu.OUT == paths.OUT


def test_snapshot_covers_every_public_path():
    snap = paths.snapshot()
    assert snap["ROOT"] == paths.ROOT
    for name in ("OUT", "CONFIG_PATH", "INTERESTS", "LIB_PATH", "PROFILE_STATE_PATH",
                 "BEHAVIOR_PATH", "ARCHIVE_DB_PATH", "ARCHIVE_DIR",
                 "NETROUTE_CACHE_PATH", "AFFILIATIONS_PATH", "INTERESTS_EXTRA_PATH"):
        assert name in snap and snap[name]


def test_snapshot_is_a_copy_not_the_module_state():
    """诊断输出必须能随便改，不能反过来影响真实常量。"""
    snap = paths.snapshot()
    snap["OUT"] = "/nowhere"
    assert paths.OUT != "/nowhere"


def test_paper_index_loader_follows_paperutil_out(sandbox):
    """缓存底层必须走 pu.load_papers（它读 pu.OUT），否则重定向后读错目录。"""
    assert service.PAPER_INDEX._loader is pu.load_papers


def test_cli_lists_every_path_with_existence_mark(capsys):
    """``python paths.py`` 是排障入口：必须一次列出全部路径并标出是否已生成。"""
    assert paths.main() == 0
    out = capsys.readouterr().out
    assert "项目根" in out
    for name in ("OUT", "CONFIG_PATH", "LIB_PATH", "ARCHIVE_DB_PATH"):
        assert name in out
    assert "OK " in out, "已存在的路径要标 OK"
    assert "尚未生成" in out, "要提示 -- 的含义"
