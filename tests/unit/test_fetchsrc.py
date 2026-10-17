# -*- coding: utf-8 -*-
"""fetchsrc：把来源标识变成 (meta, err)。

取数通过 ``_get`` 注入，所以这些用例既不联网，也不依赖调用方的模块状态；
同一个 ``_get`` 注入点也让「parse_paper 重试 3 次」这类分支可以被穷举。
"""
import pytest

import customize as CZ
import fetchsrc as FS

pytestmark = pytest.mark.unit


ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Isolation Level Selection
       for Serializable Transactions</title>
    <summary>We study isolation levels.</summary>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
  </entry>
</feed>"""

ATOM_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""


# ------------------------------------------------------------------ 编号识别

@pytest.mark.parametrize("value, ok", [
    ("2609.01234", True),
    ("2609.0123", True),          # 新式短号允许 4 位流水号
    ("cs/0701001", True),
    ("2609.012", False),          # 只有 3 位数字
    ("hello", False),
    ("", False),
])
def test_is_arxiv_id(value, ok):
    assert FS.is_arxiv_id(value) is ok


# ------------------------------------------------------------------ parse_paper

def test_parse_paper_normalises_title_and_collects_authors():
    seen = []

    def fake_get(url, timeout=25):
        seen.append(url)
        return ATOM

    meta, err = FS.parse_paper("2609.01234v2", _get=fake_get)
    assert err == ""
    assert meta["sid"] == "2609.01234"
    assert meta["title"] == "Isolation Level Selection for Serializable Transactions"
    assert meta["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert "Isolation Level Selection" in meta["text"]
    assert "id_list=2609.01234" in seen[0]


def test_parse_paper_rejects_unrecognised_id_without_http():
    def boom(*a, **k):
        raise AssertionError("编号不合法时不该发起请求")

    meta, err = FS.parse_paper("not-an-id", _get=boom)
    assert meta is None and "无法识别" in err


def test_parse_paper_reports_missing_entry():
    meta, err = FS.parse_paper("2609.01234", _get=lambda url, timeout=25: ATOM_EMPTY)
    assert meta is None and "未返回该编号" in err


def test_parse_paper_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(FS.time, "sleep", lambda *_: None)
    calls = []

    def flaky(url, timeout=25):
        calls.append(1)
        if len(calls) < 3:
            raise OSError("temporary")
        return ATOM

    meta, err = FS.parse_paper("2609.01234", _get=flaky)
    assert err == "" and meta["sid"] == "2609.01234"
    assert len(calls) == 3


def test_parse_paper_gives_up_after_three_attempts(monkeypatch):
    monkeypatch.setattr(FS.time, "sleep", lambda *_: None)
    calls = []

    def always_fail(url, timeout=25):
        calls.append(1)
        raise OSError("down")

    meta, err = FS.parse_paper("2609.01234", _get=always_fail)
    assert meta is None and "抓取失败" in err
    assert len(calls) == 3, "必须试满 3 次再放弃"


def test_parse_paper_default_get_is_module_level(monkeypatch):
    """默认取数函数来自本模块，patch fetchsrc._http_get 生效。"""
    monkeypatch.setattr(FS, "_http_get", lambda url, timeout=25: ATOM)
    meta, err = FS.parse_paper("2609.01234")
    assert err == "" and meta["title"].startswith("Isolation Level")


# ------------------------------------------------------------------ parse_link

@pytest.mark.parametrize("value", ["ftp://example.org", "example.org", "", "  "])
def test_parse_link_requires_http(value):
    meta, err = FS.parse_link(value)
    assert meta is None and "http" in err


def test_parse_link_extracts_title_and_text():
    html = ("<html><head><title>Ada's   Home</title></head>"
            "<body><script>bad()</script><p>Isolation level work</p></body></html>")
    meta, err = FS.parse_link("https://example.org", _get=lambda url, timeout=18: html)
    assert err == ""
    assert meta["title"] == "Ada's Home"
    assert "Isolation level" in meta["text"]
    assert "bad()" not in meta["text"]


def test_parse_link_falls_back_to_url_as_title():
    meta, _ = FS.parse_link("https://example.org",
                            _get=lambda url, timeout=18: "<html>no title</html>")
    assert meta["title"] == "https://example.org"


def test_parse_link_truncates_huge_pages():
    big = "<html><body>" + ("x" * (FS.MAX_TEXT + 5000)) + "</body></html>"
    meta, _ = FS.parse_link("https://example.org",
                            _get=lambda url, timeout=18: big)
    assert len(meta["text"]) <= FS.MAX_TEXT


def test_parse_link_retries_once_then_reports_failure(monkeypatch):
    monkeypatch.setattr(FS.time, "sleep", lambda *_: None)
    calls = []

    def boom(url, timeout=18):
        calls.append(1)
        raise OSError("connection refused")

    meta, err = FS.parse_link("https://example.org", _get=boom)
    assert meta is None and "抓取失败" in err
    assert len(calls) == 2


def test_parse_link_succeeds_on_second_attempt(monkeypatch):
    monkeypatch.setattr(FS.time, "sleep", lambda *_: None)
    calls = []

    def flaky(url, timeout=18):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("reset")
        return "<title>OK</title>"

    meta, err = FS.parse_link("https://example.org", _get=flaky)
    assert err == "" and meta["title"] == "OK"


# ------------------------------------------------------------------ parse_doc

def test_parse_doc_reads_plain_text(sandbox):
    f = sandbox.root / "home.md"
    f.write_text("Isolation level and serializability.\n", encoding="utf-8")
    meta, err = FS.parse_doc(str(f))
    assert err == "" and meta["title"] == "home.md"
    assert "serializability" in meta["text"]


def test_parse_doc_strips_html(sandbox):
    f = sandbox.root / "home.html"
    f.write_text("<html><body><p>Hello</p><script>x</script></body></html>",
                 encoding="utf-8")
    meta, err = FS.parse_doc(str(f))
    assert err == "" and "Hello" in meta["text"] and "x" not in meta["text"]


def test_parse_doc_accepts_windows_separators(sandbox):
    f = sandbox.root / "win.txt"
    f.write_text("text", encoding="utf-8")
    meta, err = FS.parse_doc(str(f).replace("/", "\\"))
    assert err == "" and meta["title"] == "win.txt"


def test_parse_doc_strips_surrounding_quotes(sandbox):
    f = sandbox.root / "q.txt"
    f.write_text("text", encoding="utf-8")
    assert FS.parse_doc('"%s"' % f)[1] == ""


def test_parse_doc_reports_missing_file(sandbox):
    meta, err = FS.parse_doc(str(sandbox.root / "nope.txt"))
    assert meta is None and "文件不存在" in err


def test_parse_doc_reports_empty_file(sandbox):
    f = sandbox.root / "empty.txt"
    f.write_text("   \n", encoding="utf-8")
    meta, err = FS.parse_doc(str(f))
    assert meta is None and "为空" in err


def test_parse_doc_pdf_without_pypdf_gives_actionable_hint(sandbox, monkeypatch):
    f = sandbox.root / "paper.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(FS, "_read_pdf", lambda path: None)
    meta, err = FS.parse_doc(str(f))
    assert meta is None and "pypdf" in err


def test_parse_doc_pdf_uses_extracted_text(sandbox, monkeypatch):
    f = sandbox.root / "paper.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(FS, "_read_pdf", lambda path: "extracted body")
    meta, err = FS.parse_doc(str(f))
    assert err == "" and meta["text"] == "extracted body"


# ------------------------------------------------------------------ 分派

def test_parse_dispatches_by_type(monkeypatch):
    monkeypatch.setattr(FS, "_http_get", lambda url, timeout=25: ATOM)
    assert FS.parse("paper", "2609.01234")[1] == ""
    assert FS.parse("link", "https://example.org")[0] is not None


def test_parse_rejects_unknown_type():
    meta, err = FS.parse("magic", "x")
    assert meta is None and "未知来源类型" in err


def test_parsers_table_covers_every_source_type():
    """新增来源类型必须在 PARSERS 登记，否则 customize.derive 会静默失败。"""
    assert set(FS.PARSERS) == {"paper", "link", "doc"}


# ------------------------------------------------------------------ 兼容门面

def test_customize_wrappers_use_its_own_http_get(monkeypatch):
    """patch customize._http_get 必须影响 customize.parse_link（历史用法）。"""
    monkeypatch.setattr(CZ, "_http_get",
                        lambda url, timeout=15, limit=600000: "<title>Patched</title>")
    meta, err = CZ.parse_link("https://example.org")
    assert err == "" and meta["title"] == "Patched"


def test_customize_reexports_fetchsrc_symbols():
    for name in ("parse_paper", "parse_link", "parse_doc", "_read_pdf",
                 "TEXT_EXT", "UA", "SSL_CTX", "ARXIV_API", "NS"):
        assert hasattr(CZ, name), name
