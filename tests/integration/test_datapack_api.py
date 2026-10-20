# -*- coding: utf-8 -*-
"""集成：数据包的 HTTP 面与「首屏不泄漏」边界。

两个关注点：

  1. 接口形状与状态码：GET /api/datapacks、POST /api/preset（成功 200 / 拒绝 400）；
  2. **隔离**：接口与 /profile 页面只暴露包的名称与文件清单，绝不暴露包内内容
     （标题、描述、画像里的人名）。这条边界是需求的核心，因此用真实服务断言。
"""
import pytest

import customize as CZ
import datapack as DP
import paperutil as pu

pytestmark = pytest.mark.integration

SECRET = {
    "title": "魏恒峰的科研画像",
    "description": "数据库系统 / 分布式计算 / 形式化方法方向",
}


def _make_pack(sandbox, name="demo", with_profile=True):
    files = {"config.json": {"categories": ["cs.PL"], "download_dir": "papers"}}
    if with_profile:
        files["interests.json"] = {
            "owners": [{"name": "Alexey Gotsman", "affiliation": "IMDEA"}],
            "topics": [{"name": "事务与隔离级别", "weight": 1.5,
                        "keywords": ["isolation level", "serializability"]}],
            "people": ["Hagit Attiya"],
        }
    sandbox.make_pack(name, files,
                      manifest=dict(SECRET, schema=1, groups=["core"]))
    return name


# ---------------------------------------------------------------- 接口形状

def test_datapacks_lists_shape_only(sandbox, http):
    _make_pack(sandbox)
    code, d = http.get_json("/api/datapacks")
    assert code == 200
    assert [p["name"] for p in d["packs"]] == ["demo"]
    p = d["packs"][0]
    assert set(p) == {"name", "files", "groups", "bytes"}
    assert d["state"]["has_personal_data"] is True      # 沙箱里有模板 config
    assert "title" not in p and "description" not in p
    body = repr(d)
    for leak in ("魏恒峰", "Gotsman", "数据库系统"):
        assert leak not in body


def test_datapacks_on_clean_machine_has_no_packs(sandbox, http):
    code, d = http.get_json("/api/datapacks")
    assert code == 200 and d["packs"] == []
    assert d["state"]["files"]["library.json"]["exists"] is False
    assert d["state"]["files"]["profile_state.json"]["exists"] is False


# ---------------------------------------------------------------- 导入

def test_preset_import_via_http_writes_core(sandbox, http):
    """force 路径：覆盖本机已有内容（先备份），响应带回最新状态。"""
    _make_pack(sandbox)
    code, d = http.post("/api/preset", {"op": "import", "name": "demo", "force": True})
    assert code == 200 and d["ok"], d.get("msg")
    assert CZ.categories() == ["cs.PL"]
    assert d["state"]["categories"] == ["cs.PL"], "响应里带最新状态，界面据此刷新"
    # 画像也进来了：主来源出现在 state.profile 里
    assert [o["name"] for o in d["state"]["profile"]["owners"]] == ["Alexey Gotsman"]


def test_preset_import_refuses_without_force(sandbox, http):
    sandbox.set_config(categories=["cs.LG"])     # 用户改过 → 模板初值保护不再适用
    _make_pack(sandbox)
    before = CZ.categories()
    code, d = http.post("/api/preset", {"op": "import", "name": "demo"})
    assert code == 400 and d["ok"] is False
    assert "force" in d["msg"]
    assert CZ.categories() == before


def test_preset_import_replaces_pristine_template(sandbox, http):
    """新装机器（模板初值，只有端口被测试改过）上，「导入」必须能直接生效。

    这是**目标用户**的主路径：第一次打开页面就会生成空模板，如果那也算"已有内容"，
    界面上的一键导入永远报错。端口不参与"初值"判定，见 datapack._is_pristine。
    """
    _make_pack(sandbox)
    code, d = http.post("/api/preset", {"op": "import", "name": "demo"})
    assert code == 200 and d["ok"], d.get("msg")
    assert CZ.categories() == ["cs.PL"]


def test_preset_import_unknown_name_is_400(sandbox, http):
    code, d = http.post("/api/preset", {"op": "import", "name": "nope"})
    assert code == 400 and d["ok"] is False and "找不到" in d["msg"]


def test_preset_import_rejects_path_traversal(sandbox, http):
    code, d = http.post("/api/preset", {"op": "import", "name": "../etc"})
    assert code == 400 and d["ok"] is False


def test_preset_import_without_name_is_400(sandbox, http):
    code, d = http.post("/api/preset", {"op": "import"})
    assert code == 400 and "名称" in d["msg"]


def test_preset_unknown_op_is_400(sandbox, http):
    code, d = http.post("/api/preset", {"op": "sync", "name": "demo"})
    assert code == 400 and "未知操作" in d["msg"]


def test_preset_export_via_http_writes_pack(sandbox, http):
    code, d = http.post("/api/preset", {"op": "export", "name": "mine",
                                        "groups": ["core"]})
    assert code == 200 and d["ok"], d.get("msg")
    assert (sandbox.packs / "mine" / "config.json").exists()
    assert DP.manifest("mine")["_source"] == "manifest.json"


# ---------------------------------------------------------------- 页面边界

def test_profile_lists_pack_but_not_its_contents(sandbox, http):
    _make_pack(sandbox)
    code, page = http.get("/profile")
    assert code == 200
    assert "数据包（可选）" in page
    assert 'data-import-pack="demo"' in page
    assert "config.json" in page
    for leak in ("魏恒峰", "Gotsman", "数据库系统", "事务与隔离级别", "IMDEA"):
        assert leak not in page, "画像页不得出现包内内容：%s" % leak


def test_profile_is_clean_before_any_import(sandbox, http):
    """新装机器（模板为空）的画像页：没有主来源、没有主题、没有类别标签。"""
    code, page = http.get("/profile")
    assert code == 200
    assert "还没有画像主来源" in page
    assert "还没有选择任何类别" in page
    assert "干净状态" in page
    for leak in ("Gotsman", "Attiya", "Enea", "魏恒峰", "git-papers"):
        assert leak not in page


def test_favorites_page_is_empty_state(sandbox, http):
    code, page = http.get("/favorites")
    assert code == 200
    assert "还没有收藏" in page


def test_state_api_is_empty_on_clean_machine(sandbox, http):
    code, d = http.get_json("/api/state")
    assert code == 200
    assert d["favorites"] == [] and d["downloads"] == {} and d["downvotes"] == []
    assert d["categories"] == []
    assert d["download_dir"] == "papers"
    assert d["profile"]["topics"] == []
