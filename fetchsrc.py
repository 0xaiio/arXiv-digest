#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兴趣来源的「取数适配层」：把一个来源标识变成 ``(meta, err)``。

职责边界
--------
只负责**取回并抽取文本**，不认识画像、不认识来源条目结构、不写任何文件：

    parse_paper(value)   arXiv 短号/链接 → {title, text, authors, sid}
    parse_link(value)    任意网页        → {title, text}
    parse_doc(value)     本地文档        → {title, text}

三种来源的返回结构一致，上层（``customize.derive``）因此不必关心类型差异。

可测性设计
----------
网络取数通过参数 ``_get`` 注入：默认用本模块的 ``_http_get``，调用方可传入自己的
实现。这样单测既能 patch ``fetchsrc._http_get``，也能像以前一样 patch
``customize._http_get``（`customize` 的包装会把**它自己的**符号传进来），
两种写法都生效 —— 兼容既有测试，同时本模块不再依赖调用方的模块状态。
"""
import os
import re
import ssl
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import paperutil as pu
from textscan import strip_html

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) arxiv-digest/3.0"}

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

ARXIV_API = "http://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}

# 可按纯文本读取的扩展名；.pdf 走 pypdf
TEXT_EXT = {".txt", ".md", ".markdown", ".rst", ".html", ".htm", ".csv", ".tsv",
            ".json", ".bib", ".tex", ".xml", ".yaml", ".yml", ".log"}

MAX_TEXT = 400000          # 单个来源保留的最大字符数（防超大页面拖垮画像页）
ARXIV_RX = (re.compile(r"^[0-9]{4}\.[0-9]{4,5}$"),
            re.compile(r"^[a-z\-]+/\d{7}$"))


def _http_get(url, timeout=15, limit=600000):
    """取网页文本。优先 UTF-8，解不开再按 GBK（国内个人主页常见）。"""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
        raw = r.read(limit)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk", "replace")


def is_arxiv_id(sid):
    """短号格式校验（新式 2609.01234 / 旧式 cs/0701001）。"""
    return any(rx.match(sid or "") for rx in ARXIV_RX)


def parse_paper(value, _get=None):
    """arXiv 短号 / abs 链接 / pdf 链接 -> 元数据。"""
    get = _get or _http_get
    sid = pu.short_id(value)
    if not is_arxiv_id(sid):
        return None, "无法识别 arXiv 编号：%s" % value
    url = ARXIV_API + "?" + urllib.parse.urlencode({"id_list": sid, "max_results": 1})
    for attempt in range(3):
        try:
            root = ET.fromstring(get(url, timeout=25))
            e = root.find("a:entry", NS)
            if e is None:
                return None, "arXiv 未返回该编号：%s" % sid

            def t(path):
                node = e.find(path, NS)
                return (node.text or "").strip() if node is not None else ""

            authors = [a.find("a:name", NS).text.strip()
                       for a in e.findall("a:author", NS)
                       if a.find("a:name", NS) is not None]
            return {"title": " ".join(t("a:title").split()),
                    "text": " ".join([t("a:title"), t("a:summary"), " ".join(authors)]),
                    "authors": authors, "sid": sid}, ""
        except Exception as ex:  # noqa
            if attempt == 2:
                return None, "抓取失败：%s" % ex
            time.sleep(2)
    return None, "抓取失败"


def parse_link(value, _get=None):
    """任意网页 -> {title, text}。标题取 <title>，正文去标签。"""
    get = _get or _http_get
    url = (value or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return None, "链接需以 http:// 或 https:// 开头"
    for attempt in range(2):
        try:
            html = get(url, timeout=18)
            title = ""
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
            if m:
                title = " ".join(strip_html(m.group(1)).split())[:160]
            return {"title": title or url, "text": strip_html(html)[:MAX_TEXT]}, ""
        except Exception as ex:  # noqa
            if attempt == 1:
                return None, "抓取失败：%s" % ex
            time.sleep(1)
    return None, "抓取失败"


def _read_pdf(path):
    """PDF 正文（最多 12 页）。没装 pypdf/PyPDF2 时返回 None，由上层给安装提示。"""
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return None
    try:
        rd = PdfReader(path)
        return "\n".join((pg.extract_text() or "") for pg in rd.pages[:12])
    except Exception:
        return None


def parse_doc(value):
    """本地文档 -> {title, text}。支持纯文本类扩展名与 PDF。"""
    path = os.path.expanduser((value or "").strip().strip('"')).replace("\\", "/")
    if not os.path.isfile(path):
        return None, "文件不存在：%s" % path
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    try:
        if ext == ".pdf":
            text = _read_pdf(path)
            if text is None:
                return None, "需要 pypdf 才能解析 PDF（pip install pypdf），或改用 .txt/.md"
        elif ext in (".html", ".htm"):
            with open(path, encoding="utf-8", errors="replace") as f:
                text = strip_html(f.read())
        else:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
    except Exception as ex:  # noqa
        return None, "读取失败：%s" % ex
    if not text.strip():
        return None, "文件内容为空或无法提取文本"
    return {"title": name, "text": text[:MAX_TEXT]}, ""


# 类型 -> 解析器（新增来源类型只需在这里加一行）
PARSERS = {"paper": parse_paper, "link": parse_link, "doc": parse_doc}


def parse(typ, value):
    """按来源类型分派。未知类型返回 (None, 错误)。"""
    fn = PARSERS.get(typ)
    if not fn:
        return None, "未知来源类型 %s" % typ
    return fn(value)
