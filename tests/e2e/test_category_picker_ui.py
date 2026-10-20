# -*- coding: utf-8 -*-
"""端到端（浏览器）：/profile 的 arXiv 类别选择器。

这一层测的是「用户真的能操作」——接口层只能证明规则对，证明不了：
  * 两个下拉框是**联动**的（选 cs 之后第二级只剩 cs.*）；
  * 下拉支持**搜索**与**多选**（勾三个再一次加入）；
  * 标签能**拖拽排序**，而且拖完服务端真的记住了；
  * 手输非法分类时，输入框变红并给出可据以修正的提示。

拖拽用合成 DragEvent（``new DragEvent('dragstart', {dataTransfer})``）驱动：
与真实鼠标走同一条 dragstart/dragover/drop 事件链，断言的是我们自己的
事件委托与落点算法，而不是 Edge 的拖放实现。
"""
import time

import pytest

from cdp import browser, edge_exe, js_click  # noqa: F401

pytestmark = [pytest.mark.e2e, pytest.mark.ui]


def _page(browser, http):
    """打开 /profile 并确认分类表已注入（initPicker 在 DOMContentLoaded 同步执行）。"""
    browser.goto(http.base + "/profile")
    assert browser.evaluate("!!document.getElementById('taxdata')")


def _open_arch(browser):
    js_click(browser, "#cp-arch-btn")
    assert browser.evaluate("!document.getElementById('cp-arch-pop').hidden")


def _open_sub(browser):
    js_click(browser, "#cp-sub-btn")
    assert browser.evaluate("!document.getElementById('cp-sub-pop').hidden")


def _search(browser, box, text):
    browser.evaluate(
        "(()=>{var e=document.getElementById(%r);e.value=%r;"
        "e.dispatchEvent(new Event('input',{bubbles:true}));})()" % (box, text))
    time.sleep(0.1)


def _sub_ids(browser):
    return browser.evaluate(
        "Array.from(document.querySelectorAll('#cp-sub-list [data-sub]'))"
        ".map(function(e){return e.dataset.sub;})")


def _tags(browser):
    return browser.evaluate(
        "Array.from(document.querySelectorAll('#cat-list .cat-tag'))"
        ".map(function(e){return e.dataset.cat;})")


def test_two_level_dropdown_is_linked(sandbox, http, browser):
    """先选 abc，第二级只剩该 archive 的分类；换一个 abc，第二级跟着换。"""
    sandbox.set_config(categories=["cs.DB"])
    _page(browser, http)

    _open_arch(browser)
    js_click(browser, "[data-arch='math']")
    _open_sub(browser)

    ids = _sub_ids(browser)
    assert ids and all(i.startswith("math.") for i in ids), ids[:5]
    assert "cs.LG" not in ids

    # 切回 cs：第二级整体替换
    _open_arch(browser)
    js_click(browser, "[data-arch='math']")   # 取消 math
    js_click(browser, "[data-arch='cs']")
    _open_sub(browser)
    ids = _sub_ids(browser)
    # cs.DB 已在列表里 → 渲染成禁用的「已在列表」项，不参与勾选
    assert "cs.LG" in ids and "cs.PL" in ids
    assert "cs.DB" not in ids
    assert not any(i.startswith("math.") for i in ids)


def test_dropdown_search_filters_options(sandbox, http, browser):
    sandbox.set_config(categories=["cs.DB"])
    _page(browser, http)
    _open_sub(browser)

    # 中文名也能搜到；但 cs.DB 已加入 → 只以「已在列表」的禁用项形式出现
    _search(browser, "cp-sub-q", "数据库")
    assert _sub_ids(browser) == []
    assert "已在列表" in browser.evaluate(
        "document.getElementById('cp-sub-list').textContent")

    _search(browser, "cp-sub-q", "数理逻辑")
    assert _sub_ids(browser) == ["math.LO"]

    _search(browser, "cp-sub-q", "cond-mat")
    ids = _sub_ids(browser)
    assert ids and all(i.startswith("cond-mat.") for i in ids)

    _search(browser, "cp-sub-q", "zzz-nothing")
    assert _sub_ids(browser) == []
    assert "没有匹配的分类" in browser.evaluate(
        "document.getElementById('cp-sub-list').textContent")


def test_multi_select_adds_all_checked_categories(sandbox, http, browser):
    """多选：勾三个、点一次「加入」，三个都进 config.json。"""
    import customize as CZ

    sandbox.set_config(categories=["cs.DB"])
    _page(browser, http)
    _open_sub(browser)
    _search(browser, "cp-sub-q", "cs.")
    for cat in ("cs.LG", "cs.PL", "cs.SE"):
        js_click(browser, "[data-sub='%s']" % cat)

    assert browser.evaluate(
        "document.querySelectorAll('#cp-sub-list .cp-opt.on').length") == 3
    assert "已勾选 3 个子类" in browser.evaluate(
        "document.getElementById('cp-hint').textContent")

    js_click(browser, "#cp-add")
    time.sleep(0.8)
    assert CZ.categories() == ["cs.DB", "cs.LG", "cs.PL", "cs.SE"]
    assert _tags(browser) == ["cs.DB", "cs.LG", "cs.PL", "cs.SE"]
    # 已在列表里的选项被禁用，避免重复添加
    assert browser.evaluate(
        "document.querySelectorAll('#cp-sub-list .cp-opt.dis').length") >= 4


def test_existing_category_is_marked_and_not_selectable(sandbox, http, browser):
    sandbox.set_config(categories=["cs.DB"])
    _page(browser, http)
    _open_sub(browser)
    _search(browser, "cp-sub-q", "cs.DB")
    assert browser.evaluate(
        "document.querySelector('[data-sub=\"cs.DB\"]')") is None
    assert "已在列表" in browser.evaluate(
        "document.getElementById('cp-sub-list').textContent")


def test_tag_shows_id_and_chinese_name(sandbox, http, browser):
    sandbox.set_config(categories=["cs.DB", "quant-ph"])
    _page(browser, http)
    text = browser.evaluate(
        "Array.from(document.querySelectorAll('.cat-tag')).map(function(e){"
        "return e.dataset.cat+'|'+e.querySelector('.t-id').textContent+'|'"
        "+e.querySelector('.t-zh').textContent;})")
    assert text == ["cs.DB|cs.DB|数据库", "quant-ph|quant-ph|量子物理"]


def test_tags_are_draggable_with_visible_affordance(sandbox, http, browser):
    """UI 必须明确体现「可排序」：draggable + 拖柄 + 提示文案 + grab 光标。"""
    sandbox.set_config(categories=["cs.DB", "cs.LG", "cs.PL"])
    _page(browser, http)

    assert browser.evaluate(
        "Array.from(document.querySelectorAll('.cat-tag'))"
        ".every(function(e){return e.getAttribute('draggable')==='true';})")
    assert browser.evaluate("!!document.querySelector('.cat-tag .grip')")
    assert "拖动标签可调整顺序" in browser.evaluate(
        "document.querySelector('.cp-tip').textContent")
    assert browser.evaluate(
        "getComputedStyle(document.querySelector('.cat-tag')).cursor") == "grab"


def _drag(browser, src, dst, after=True):
    """用合成的 DragEvent 把 src 拖到 dst 的前/后半区。

    直接调 ``moveCard`` 是不行的：那样只能证明算法对，证明不了
    dragstart/dragover/drop 的绑定与落点判定（而后者才是用户按下去会发生的事）。
    """
    browser.evaluate("""
(()=>{
  var src=document.querySelector(".cat-tag[data-cat='%s']");
  var dst=document.querySelector(".cat-tag[data-cat='%s']");
  if(!src||!dst)throw new Error('tag not found');
  var dt=new DataTransfer();
  src.dispatchEvent(new DragEvent('dragstart',{bubbles:true,cancelable:true,dataTransfer:dt}));
  var r=dst.getBoundingClientRect();
  var x=%s ? r.right-2 : r.left+2;
  var opts={bubbles:true,cancelable:true,dataTransfer:dt,clientX:x,clientY:r.top+r.height/2};
  dst.dispatchEvent(new DragEvent('dragover',opts));
  dst.dispatchEvent(new DragEvent('drop',opts));
  src.dispatchEvent(new DragEvent('dragend',{bubbles:true,dataTransfer:dt}));
})()""" % (src, dst, "true" if after else "false"))


def test_drag_reorders_and_persists(sandbox, http, browser):
    """把第 1 个标签拖到第 3 个之后：DOM 顺序与 config.json 都要变。"""
    import customize as CZ

    sandbox.set_config(categories=["cs.DB", "cs.LG", "cs.PL"])
    _page(browser, http)
    assert _tags(browser) == ["cs.DB", "cs.LG", "cs.PL"]

    _drag(browser, "cs.DB", "cs.PL", after=True)
    time.sleep(0.8)

    assert _tags(browser) == ["cs.LG", "cs.PL", "cs.DB"]
    assert CZ.categories() == ["cs.LG", "cs.PL", "cs.DB"], "顺序必须落盘"


def test_drag_forward_inserts_before_target(sandbox, http, browser):
    """拖到目标前半区 = 插到它前面（落点判定不能只看「拖过了谁」）。"""
    import customize as CZ

    sandbox.set_config(categories=["cs.DB", "cs.LG", "cs.PL"])
    _page(browser, http)

    _drag(browser, "cs.PL", "cs.DB", after=False)
    time.sleep(0.8)

    assert _tags(browser) == ["cs.PL", "cs.DB", "cs.LG"]
    assert CZ.categories() == ["cs.PL", "cs.DB", "cs.LG"]


def test_drop_indicator_appears_while_dragging(sandbox, http, browser):
    """拖动过程中目标标签要出现落点竖线（.drop-l/.drop-r），否则用户看不出会插到哪。"""
    sandbox.set_config(categories=["cs.DB", "cs.LG"])
    _page(browser, http)
    browser.evaluate("""
(()=>{
  var src=document.querySelector(".cat-tag[data-cat='cs.DB']");
  var dst=document.querySelector(".cat-tag[data-cat='cs.LG']");
  var dt=new DataTransfer();
  src.dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer:dt}));
  var r=dst.getBoundingClientRect();
  dst.dispatchEvent(new DragEvent('dragover',{bubbles:true,cancelable:true,
    dataTransfer:dt,clientX:r.right-2,clientY:r.top+2}));
  window.__dragState={
    srcCls:src.className, dstCls:dst.className};
})()""")
    state = browser.evaluate("window.__dragState")
    assert "dragging" in state["srcCls"], "被拖的标签要变淡"
    assert "drop-r" in state["dstCls"], "后半区应显示右侧落点线"


def test_delete_tag_updates_config(sandbox, http, browser):
    """删除走的是同一个 data-del-cat 委托；确认框用 stub 掉（headless 无人点）。"""
    import customize as CZ

    sandbox.set_config(categories=["cs.DB", "cs.LG"])
    browser.goto(http.base + "/profile")
    browser.evaluate("window.confirm=function(){return true;}")
    js_click(browser, ".cat-tag[data-cat='cs.DB'] .t-x")
    time.sleep(0.8)
    assert CZ.categories() == ["cs.LG"]
    assert _tags(browser) == ["cs.LG"]


def test_manual_input_live_validation(sandbox, http, browser):
    """手输非法值：输入框变红 + 给出原因；合法值：变绿并显示中文名。"""
    sandbox.set_config(categories=["cs.DB"])
    _page(browser, http)

    _search(browser, "cat-value", "CS.DB")
    box = browser.evaluate(
        "(()=>{var e=document.getElementById('cat-valid');"
        "return {cls:e.className,txt:e.textContent,"
        "inp:document.getElementById('cat-value').className};})()")
    assert "err" in box["cls"] and "大小写" in box["txt"]
    assert "bad" in box["inp"]

    _search(browser, "cat-value", "cs.ZZ")
    assert "官方分类" in browser.evaluate(
        "document.getElementById('cat-valid').textContent")

    _search(browser, "cat-value", "math.LO")
    txt = browser.evaluate("document.getElementById('cat-valid').textContent")
    assert "✓ math.LO" in txt and "数理逻辑" in txt
    assert "good" in browser.evaluate(
        "document.getElementById('cat-value').className")


def test_manual_input_adds_valid_category(sandbox, http, browser):
    import customize as CZ

    sandbox.set_config(categories=["cs.DB"])
    _page(browser, http)
    _search(browser, "cat-value", "stat.ML")
    js_click(browser, "#cat-add")
    time.sleep(0.8)
    assert CZ.categories() == ["cs.DB", "stat.ML"]
    assert _tags(browser) == ["cs.DB", "stat.ML"]
    assert browser.evaluate("document.getElementById('cat-value').value") == ""


def test_unknown_category_from_hand_edited_config_is_flagged(sandbox, http, browser):
    """手改 config 塞进未知分类：标签标黄提示，但不静默删除用户数据。"""
    sandbox.set_config(categories=["cs.DB", "cs.LEGACY"])
    _page(browser, http)
    assert browser.evaluate(
        "!!document.querySelector('.cat-tag.unknown[data-cat=\"cs.LEGACY\"]')")
    assert "不在 arXiv 官方分类表中" in browser.evaluate(
        "document.querySelector('.cat-tag.unknown').title")


def test_profile_page_has_no_js_errors(sandbox, http, browser):
    sandbox.set_config(categories=["cs.DB"])
    browser.goto(http.base + "/profile")
    time.sleep(0.4)
    assert browser.evaluate(
        "(()=>{try{return window.__jsErrors||[]}catch(e){return []}})()") == []


def test_welcome_page_points_to_profile(sandbox, http, browser):
    """首次打开（未选类别）看到的是引导页，且能一键跳到 /profile。"""
    sandbox.set_config(categories=[])
    browser.goto(http.base + "/")
    assert "选择要跟踪的 arXiv 分类" in browser.evaluate(
        "document.querySelector('.wel-card h2').textContent")
    href = browser.evaluate("document.querySelector('.wel-cta').getAttribute('href')")
    assert href == "/profile"
