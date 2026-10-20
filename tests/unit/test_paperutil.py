# -*- coding: utf-8 -*-
"""paperutil：标识规范化、文件名、配置与库文件的读写契约。"""
import json
import re

import pytest

import paperutil as pu

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------ 标识

@pytest.mark.parametrize("raw, expect", [
    ("2609.09742", "2609.09742"),
    ("2609.09742v2", "2609.09742"),
    ("arXiv:2609.09742v2", "2609.09742"),
    ("arXiv:2609.09742", "2609.09742"),
    ("http://arxiv.org/abs/2609.09742v3", "2609.09742"),
    ("https://arxiv.org/pdf/2609.09742", "2609.09742"),
    ("  2609.09742  ", "2609.09742"),
])
def test_short_id_normalizes_all_forms(raw, expect):
    """接口与库文件的 key 都靠它统一；带 arXiv: 前缀是前端/脚本常见的输入形态。"""
    assert pu.short_id(raw) == expect


def test_short_id_accepts_paper_dict(make_paper):
    p = make_paper("2609.12345")
    assert pu.short_id(p) == "2609.12345"


def test_short_id_of_garbage_is_stable():
    """不认识的输入不应抛异常（调用方拿它当 key 用）。"""
    assert pu.short_id("") == ""
    assert pu.short_id("not-an-id") == "not-an-id"


# ------------------------------------------------------------------ 文件名

def test_build_filename_layout():
    got = pu.build_filename("2609.09742v2", "Isolation Level: A Study!", year="2026")
    assert got == "arXiv2026 2609.09742 Isolation Level A Study.pdf"


def test_build_filename_keeps_inner_punctuation_free():
    got = pu.build_filename("2609.00001", "CRDTs & (In)Consistency?", year="2025")
    assert "&" not in got and "(" not in got and "?" not in got
    assert got.endswith(".pdf")


def test_clean_title_truncates_on_word_boundary():
    long_title = " ".join(["verification"] * 40)
    got = pu.clean_title(long_title, maxlen=60)
    assert len(got) <= 60
    assert not got.endswith(" ")
    assert "verif" in got


def test_clean_title_strips_quotes_and_trailing_dot():
    assert pu.clean_title("‘Consensus’ “Revisited”.") == "Consensus Revisited"


# ------------------------------------------------------------------ 配置

def test_config_is_seeded_from_example_on_first_use(bare_sandbox):
    cfg = pu.load_config()
    assert bare_sandbox.cfg.exists(), "首次读取应生成 config.json"
    assert cfg["download_dir"] == "papers"
    # 通用版：默认**不预设任何类别**，由用户在 /profile 里自选
    assert cfg["categories"] == []
    assert cfg["expand_categories"] == [], "留空 = 自动取同 archive 的兄弟分类"
    # 模板里的可选字段也应带上
    assert cfg["top_expand"] == 10


def test_shipped_example_has_no_personal_categories():
    """仓库里的模板不得夹带任何人的分类偏好（六分类示例只存在于 presets/）。"""
    import json as _json
    import os

    import paths
    with open(os.path.join(paths.ROOT, "config.example.json"), encoding="utf-8") as f:
        d = _json.load(f)
    assert d["categories"] == []
    assert d["category_names"] == {}


def test_categories_key_is_coerced_to_list(sandbox):
    sandbox.cfg.write_text(json.dumps({"categories": "cs.DB"}), encoding="utf-8")
    assert pu.load_config()["categories"] == [], "手改坏的类型不能让下游炸掉"


def test_existing_config_wins_and_missing_keys_fall_back(sandbox):
    sandbox.cfg.write_text(json.dumps({"categories": ["cs.PL"]}), encoding="utf-8")
    cfg = pu.load_config()
    assert cfg["categories"] == ["cs.PL"], "用户文件必须优先于模板"
    assert cfg["top_recommend"] == 14, "缺失字段回落代码默认值"
    assert cfg["port"] == 8765


def test_corrupt_config_does_not_crash(sandbox):
    sandbox.cfg.write_text("{ this is not json", encoding="utf-8")
    cfg = pu.load_config()
    assert cfg["port"] == 8765 and cfg["download_dir"] == "papers"


# ------------------------------------------------------------------ 库文件

def test_library_defaults_when_missing(sandbox):
    lib = pu.load_library()
    assert lib == {"favorites": {}, "downloads": {}, "downvotes": {}}


def test_library_roundtrip_is_atomic(sandbox):
    lib = pu.load_library()
    lib["favorites"]["2609.09742"] = {"id": "2609.09742", "title": "T"}
    pu.save_library(lib)

    again = pu.load_library()
    assert again["favorites"]["2609.09742"]["title"] == "T"
    assert not (sandbox.out / "library.json.tmp").exists(), "不应留下临时文件"


def test_library_fills_missing_sections(sandbox):
    sandbox.write("library.json", {"favorites": {"a": {}}})
    lib = pu.load_library()
    assert set(lib) == {"favorites", "downloads", "downvotes"}
    assert lib["downloads"] == {}


def test_corrupt_library_returns_empty(sandbox):
    sandbox.write("library.json", {"favorites": "oops"})
    (sandbox.out / "library.json").write_text("null", encoding="utf-8")
    assert pu.load_library()["favorites"] == {}


# ------------------------------------------------------------------ 论文索引

def test_load_papers_merges_two_pools(sandbox, pool):
    core, exp = pool()
    sandbox.write("raw.json", core)
    sandbox.write("raw_expand.json", exp)
    idx = pu.load_papers()
    assert set(idx) == {"2609.10001", "2609.10002", "2609.10003",
                        "2610.20001", "2610.20002"}


def test_load_papers_first_pool_wins_on_duplicate(sandbox, make_paper):
    a = make_paper("2609.00001", title="core version")
    b = make_paper("2609.00001", title="expand version")
    sandbox.write("raw.json", {"papers": [a]})
    sandbox.write("raw_expand.json", {"papers": [b]})
    assert pu.load_papers()["2609.00001"]["title"] == "core version"


def test_load_papers_skips_corrupt_files(sandbox, make_paper):
    sandbox.write("raw.json", {"papers": [make_paper("2609.00001")]})
    (sandbox.out / "raw_expand.json").write_text("{broken", encoding="utf-8")
    assert list(pu.load_papers()) == ["2609.00001"]


def test_paper_meta_maps_fields(make_paper):
    p = make_paper("2609.00001", title="T", primary="", queried_cat="cs.LO")
    meta = pu.paper_meta(p)
    assert meta["id"] == "2609.00001"
    assert meta["primary"] == "cs.LO", "primary 缺失时回落到 queried_cat"


def test_now_str_format():
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", pu.now_str())
