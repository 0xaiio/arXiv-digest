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
