# -*- coding: utf-8 -*-
"""兼容门面契约：重构不得改动的对外符号。

为什么值得单独一个文件
----------------------
这次重构把 server 拆成 service + routes、把 customize 拆出 textscan/fetchsrc、
把模板移出 build_report。判断「没有破坏性变更」不能靠肉眼，而要靠一份**清单**：
下面每个名字都被 tools/、定时自动化脚本或既有用户脚本引用过。

清单只增不减：真要删除某个符号，必须先在这个文件里显式删掉一行，让评审看见。
"""
import pytest

import build_report as B
import customize as CZ
import recommend as R
import server as S
import service as SV

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------ server

SERVER_SYMBOLS = [
    "Handler", "main",
    # 业务函数（tools/concurrency_check.py 与集成测试会替换它们）
    "download_pdf", "papers", "learn", "add_favorite", "record_download",
    "download_many", "rebuild_digest", "profile_snapshot", "latest_digest",
    "dl_lock", "ensure_dir", "service_open", "digest_module",
    # 常量与被替换的模块对象
    "OUT", "LIB_LOCK", "DL_WORKERS", "NR", "CZ", "pu", "os", "subprocess",
]


@pytest.mark.parametrize("name", SERVER_SYMBOLS)
def test_server_keeps_public_symbols(name):
    assert hasattr(S, name), "server.%s 被移除了（属于破坏性变更）" % name


def test_server_lib_lock_is_the_service_lock():
    """库锁必须只有一个实例，否则拆层后两把锁各锁各的 = 等于没锁。"""
    assert S.LIB_LOCK is SV.LIB_LOCK
    assert S._lib_lock is SV.LIB_LOCK


def test_server_download_pdf_delegates_to_service():
    assert S.download_pdf is SV.download_pdf


def test_server_latest_digest_uses_module_out(sandbox):
    """latest_digest 必须读 server.OUT（可被重定向），而不是 paths 里的死值。"""
    f = sandbox.out / "arxiv_digest_20260101.html"
    f.write_text("x", encoding="utf-8")
    assert S.latest_digest() == str(f)


def test_server_handler_is_importable_by_http_server():
    from http.server import ThreadingHTTPServer

    srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
    srv.server_close()


# ------------------------------------------------------------------ customize

CUSTOMIZE_SYMBOLS = [
    # 配置 / 类别
    "load_interests", "categories", "category_label", "add_category",
    "remove_category", "download_dir", "set_download_dir",
    # 兴趣来源
    "load_extra", "save_extra", "add_source", "remove_source", "refresh_all",
    "block_keyword", "derive", "rebuild", "view", "snapshot", "profile_view",
    "sources_view",
    # 画像主来源
    "owners", "owners_view", "add_owner", "update_owner", "remove_owner",
    # 来源解析（原在 customize 内实现，现由 fetchsrc 提供）
    "parse_paper", "parse_link", "parse_doc", "_read_pdf", "_http_get",
    "strip_html", "extract_people", "extract_keywords", "matched_topics",
    # 常量
    "INTERESTS", "INTERESTS_EXAMPLE", "EXTRA_PATH", "TEXT_EXT", "UA",
    "SSL_CTX", "ARXIV_API", "NS", "CUSTOM_TOPIC",
]


@pytest.mark.parametrize("name", CUSTOMIZE_SYMBOLS)
def test_customize_keeps_public_symbols(name):
    assert hasattr(CZ, name), "customize.%s 被移除了（属于破坏性变更）" % name


# ------------------------------------------------------------------ recommend

@pytest.mark.parametrize("name", ["short_id", "load_profile", "features", "score",
                                  "_rx", "_norm", "main", "OUT"])
def test_recommend_keeps_public_symbols(name):
    assert hasattr(R, name), "recommend.%s 被移除了（属于破坏性变更）" % name


# ------------------------------------------------------------------ build_report

@pytest.mark.parametrize("name", [
    "main", "load", "build_html", "build_favorites", "build_profile_page",
    "build_archive_page", "build_md", "cat_name", "read_template",
    "CSS", "JS", "PAGE", "FAV_PAGE", "PROFILE_PAGE", "ARCHIVE_PAGE",
])
def test_build_report_keeps_public_symbols(name):
    assert hasattr(B, name), "build_report.%s 被移除了（属于破坏性变更）" % name


def test_templates_are_loaded_from_disk():
    """模板必须是文件（不是内联字符串），且内容非空。"""
    import os

    for name in ("style.css", "app.js", "page.html", "favorites.html",
                 "profile.html", "archive.html"):
        path = os.path.join(B._TEMPLATE_DIR, name)
        assert os.path.isfile(path), path
        assert os.path.getsize(path) > 100, path


def test_template_variables_are_wired_to_files():
    assert "/* CSS" in B.CSS or ":root" in B.CSS
    assert "var PD=" in B.JS
    assert "<!DOCTYPE html>" in B.PAGE
    assert "<!DOCTYPE html>" in B.PROFILE_PAGE
    assert "<!DOCTYPE html>" in B.FAV_PAGE
    assert "<!DOCTYPE html>" in B.ARCHIVE_PAGE


def test_api_port_is_substituted_at_render_time(sandbox):
    """JS 里的 __APIPORT__ 在**渲染时**替换成当前 config.port。

    改为渲染时替换（原来在模块加载时）之后，改端口 / 换测试端口只要重新生成
    页面就生效，不必重启服务进程 —— 否则页面里的 APIBASE 会指到旧端口，
    请求失败后乐观更新被回滚，看起来就像「点了没反应」。
    """
    assert "__APIPORT__" in B.JS, "模板文件里保留占位符"
    sandbox.set_config(port=9876)
    assert "APIPORT=9876" in B.render_js()
    assert "__APIPORT__" not in B.render_js()


def test_render_js_follows_port_changes(sandbox):
    """改端口后必须拿到新端口（缓存不能把旧值钉住）。"""
    sandbox.set_config(port=9877)
    assert "APIPORT=9877" in B.render_js()
    sandbox.set_config(port=9878)
    assert "APIPORT=9878" in B.render_js()


def test_read_template_caches_by_mtime(sandbox):
    """同一 mtime 命中缓存（返回同一对象），不做重复读盘。"""
    B._TEMPLATE_CACHE.pop("style.css", None)
    before = B.read_template("style.css")
    assert B.read_template("style.css") is before


def test_missing_template_reports_actionable_error(monkeypatch):
    monkeypatch.setattr(B, "_TEMPLATE_DIR", "/definitely/not/here")
    B._TEMPLATE_CACHE.clear()
    with pytest.raises(SystemExit) as ei:
        B.read_template("page.html")
    assert "模板文件缺失" in str(ei.value)
