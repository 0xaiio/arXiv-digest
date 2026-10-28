# -*- coding: utf-8 -*-
"""按钮语义（`build_report.dl_btn` / `arx_link` / `acts`）。

这两处都属于「文字说一件事、点击做另一件事」的高危区，而且只有静态标记能提前
暴露它：
  * 下载按钮一旦进入已下载态，点击必须变成**打开本地文件**；
  * arXiv 入口必须说清是去站外看论文页，不能让人误以为是「存 PDF」。
"""
import re

import build_report as B


# ---------------------------------------------------------------- 下载按钮

def test_download_button_means_download_before_downloading():
    html = B.dl_btn("2609.10001", False)
    assert 'class="btn dl"' in html, "未下载时不能带 done 态"
    assert ">下载<" in html
    assert 'title="下载 PDF 并自动收藏"' in html
    assert "打开本地文件" not in html


def test_downloaded_button_means_open_local_file():
    """已下载 = 打开本地文件：文字、tooltip、图标、done 态四者必须一致。

    2026-10-28 用户报告的问题是「按钮写着已下载，点了却仍然在下载」——
    只改 label 而不改 title / 点击分支时就是这个表现。
    """
    html = B.dl_btn("2609.10001", True)
    assert "btn dl done" in html
    assert ">已下载<" in html
    assert 'title="打开本地文件"' in html
    assert 'aria-label="打开本地文件"' in html, "tooltip 也要给读屏器一份"
    assert ">下载<" not in html.replace(">已下载<", "")


def test_acts_uses_the_library_download_state(monkeypatch):
    """已下载状态来自 library.json（DOWNLOADS），不是前端猜的。"""
    monkeypatch.setattr(B, "DOWNLOADS", {"2609.10001": "/papers/a.pdf"})
    done = B.acts("2609.10001")
    fresh = B.acts("2609.10002")
    assert "btn dl done" in done and ">已下载<" in done
    assert "btn dl done" not in fresh and ">下载<" in fresh


def test_acts_accepts_a_full_id(monkeypatch):
    """传 `arXiv:2609.10001v2` 也要命中已下载态（页面各处入参不统一）。"""
    monkeypatch.setattr(B, "DOWNLOADS", {"2609.10001": "/papers/a.pdf"})
    assert "btn dl done" in B.acts("arXiv:2609.10001v2")


# ---------------------------------------------------------------- arXiv 入口

def test_arxiv_button_targets_the_abs_page_with_brand():
    """去 arXiv 的按钮：目标是 /abs/ 页面、带字标与外链箭头、tooltip 说清去向。"""
    html = B.arx_link("2609.10001")
    assert 'href="https://arxiv.org/abs/2609.10001"' in html, \
        "打开的是 arXiv 论文页（摘要页），不是 /pdf/ 文件"
    assert 'class="arx-wm"' in html and ">arXiv<" in html, "品牌字标是识别入口的关键"
    assert 'class="ext"' in html, "外链箭头表达「会离开本站」"
    assert "在 arXiv 上打开论文页" in html
    assert 'target="_blank"' in html and 'rel="noopener"' in html


def test_arxiv_button_does_not_claim_to_be_a_pdf_save():
    """不能再出现裸「PDF」文案：那是左边「下载」的语义。"""
    html = B.arx_link("2609.10001")
    assert not re.search(r">\s*PDF\s*<", html)


def test_acts_keeps_the_arxiv_link_per_card(monkeypatch):
    monkeypatch.setattr(B, "DOWNLOADS", {})
    html = B.acts("2609.10002")
    assert 'href="https://arxiv.org/abs/2609.10002"' in html
    assert html.count("<button") == 5, "收藏/下载/两个摘要/Downvote 共 5 个按钮"
