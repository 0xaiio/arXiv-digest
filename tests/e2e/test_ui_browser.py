# -*- coding: utf-8 -*-
"""端到端（浏览器）：真实点击，验证「用户看到的」而不是「接口返回的」。

这一层补的是前两层看不到的东西：内联 JS 是否执行、CSS 是否真的生效、
点击后的乐观更新是否即时。默认执行；以下情况自动跳过：

  * 没有 Edge（非 Windows 或未安装）；
  * 没有 websocket-client；
  * 设置了 SKIP_UI_E2E=1（例如 CI 环境）。

实现方式：`msedge --headless=new --remote-debugging-port` + CDP，不依赖 Selenium。
机械动作（导航 / evaluate / 点击）在 cdp.py 里，与分类选择器的用例共用一套。
"""
import time

import pytest

from cdp import browser, click, edge_exe  # noqa: F401

pytestmark = [pytest.mark.e2e, pytest.mark.ui]


def test_downvote_click_changes_visual_state(seeded, http, browser):
    """点一次 Downvote：卡片变灰 + 标题删除线 + 按钮文字变化；再点恢复。"""
    import build_report as B
    import recommend as R

    R.main()
    B.main()

    browser.goto(http.base + "/")
    assert browser.evaluate("document.querySelectorAll('.rec-card').length") >= 1

    sid = browser.evaluate("document.querySelector('.rec-card').dataset.sid")
    sel = "[data-sid='%s']" % sid

    def style(expr):
        return browser.evaluate(
            "(()=>{var e=document.querySelector(\"%s\");%s})()" % (sel, expr))

    click(browser, sel, "dv")
    time.sleep(0.6)

    assert style("return !!e.classList.contains('down')") is True
    assert style("return getComputedStyle(e).opacity") == "0.42"
    assert "line-through" in style(
        "return getComputedStyle(e.querySelector('.rec-t')).textDecorationLine")
    assert style("return e.querySelector('button[data-act=\"dv\"] .lb').textContent") == "已 Downvote"

    # 撤销
    click(browser, sel, "dv")
    time.sleep(0.6)
    assert style("return !!e.classList.contains('down')") is False
    assert float(style("return getComputedStyle(e).opacity")) > 0.9


def test_no_javascript_errors_on_load(seeded, http, browser):
    """首屏不应有 JS 异常（内联脚本被模板转义破坏时会静默失败）。"""
    import build_report as B
    import recommend as R

    R.main()
    B.main()

    browser.goto(http.base + "/")
    errors = browser.evaluate(
        "(()=>{try{return window.__jsErrors||[]}catch(e){return []}})()")
    assert errors == []


def test_abstract_en_and_ch_are_mutually_exclusive(seeded, http, browser):
    """两个摘要按钮：点 EN 只开 EN，点 CH 只开 CH，再点收起。

    这一条只能在浏览器里验：短号里的点会让 `#ab-<sid>` 选择器被解析成「id + 类」，
    静态检查看不出来，只有真点一次才知道选中的元素对不对。
    """
    import build_report as B
    import recommend as R

    seeded.write("abstracts_zh.json", {"2609.10001": "中文译文：研究事务的隔离级别。"})
    seeded.write("summaries.json",
                 {"2609.10001": {"en": "We study isolation levels.",
                                 "zh": "研究事务的隔离级别。"}})
    R.main()
    B.main()
    browser.goto(http.base + "/")

    def opened(which):
        return browser.evaluate(
            "!!document.querySelector('[id=\"%s2609.10001\"]').classList.contains('open')"
            % ("abz-" if which == "ch" else "ab-"))

    assert not opened("en") and not opened("ch"), "初始都收起"

    click(browser, "[data-sid='2609.10001']", "abs")
    time.sleep(0.4)
    assert opened("en") and not opened("ch")

    click(browser, "[data-sid='2609.10001']", "abszh")
    time.sleep(0.4)
    assert opened("ch") and not opened("en"), "两个版本互斥，不能同时展开"
    assert "中文译文" in browser.evaluate(
        "document.querySelector('[id=\"abz-2609.10001\"]').textContent")

    click(browser, "[data-sid='2609.10001']", "abszh")
    time.sleep(0.4)
    assert not opened("ch"), "再点一次收起"


def test_downloaded_button_opens_the_local_pdf(seeded, http, monkeypatch, browser):
    """已下载的按钮：tooltip 是「打开本地文件」，点它调用 /api/open，不再下载。

    这一条只能在浏览器里验：文字、tooltip、点击分支三者是分别实现的，
    任何一处漏改都会表现为「按钮写着已下载，点了又下载一遍」。
    """
    import build_report as B
    import paperutil as pu
    import recommend as R
    import server as S

    opened = []

    def fake_open(path):
        opened.append(path)
        return True, ""

    monkeypatch.setattr(S, "service_open", fake_open)

    seeded.download_dir.mkdir(parents=True, exist_ok=True)
    pdf = seeded.download_dir / "arXiv2026 2609.10001 Isolation Level.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    lib = pu.load_library()
    lib["downloads"]["2609.10001"] = {"path": str(pdf), "at": "now", "title": "T"}
    pu.save_library(lib)

    R.main()
    B.main()
    browser.goto(http.base + "/")

    btn = "document.querySelector(\"[data-sid='2609.10001'] button[data-act='dl']\")"
    assert browser.evaluate(btn + ".classList.contains('done')") is True
    assert browser.evaluate(btn + ".getAttribute('title')") == "打开本地文件"
    assert browser.evaluate(btn + ".querySelector('.lb').textContent") == "已下载"

    click(browser, "[data-sid='2609.10001']", "dl")
    time.sleep(0.8)

    assert opened == [str(pdf)], "点「已下载」应打开本地 PDF（/api/open）"
    assert browser.evaluate(btn + ".classList.contains('done')") is True, \
        "打开本地文件不该把按钮打回下载态"
    assert "下载中" not in browser.evaluate(btn + ".textContent")
    hits = browser.evaluate(
        "performance.getEntriesByType('resource').map(e=>e.name)")
    assert not [h for h in hits if "/api/download" in h], \
        "已下载的按钮不得再发下载请求"


def test_fresh_paper_keeps_download_semantics(seeded, http, browser):
    """没下载过的那篇仍是「下载」：状态是按篇判定的，不是全页一刀切。"""
    import build_report as B
    import recommend as R

    R.main()
    B.main()
    browser.goto(http.base + "/")

    btn = "document.querySelector(\"[data-sid='2609.10002'] button[data-act='dl']\")"
    assert browser.evaluate(btn + ".classList.contains('done')") is False
    assert browser.evaluate(btn + ".getAttribute('title')") == "下载 PDF 并自动收藏"
    assert browser.evaluate(btn + ".querySelector('.lb').textContent") == "下载"


def test_favorite_button_roundtrip_in_browser(seeded, http, browser):
    """点收藏 → 按钮变「已收藏」；再点 → 取消。"""
    import build_report as B
    import recommend as R

    R.main()
    B.main()
    browser.goto(http.base + "/")

    sel = "[data-sid='2609.10001']"
    click(browser, sel, "fav")
    time.sleep(0.6)
    assert browser.evaluate(
        "document.querySelector(\"%s button[data-act='fav']\").classList.contains('on')" % sel)
    label = browser.evaluate(
        "document.querySelector(\"%s button[data-act='fav'] .lb\").textContent" % sel)
    assert "已收藏" in label

    click(browser, sel, "fav")
    time.sleep(0.6)
    assert not browser.evaluate(
        "document.querySelector(\"%s button[data-act='fav']\").classList.contains('on')" % sel)
