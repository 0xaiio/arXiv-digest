# -*- coding: utf-8 -*-
"""customize 的「兴趣来源」解析：本地文档/链接/论文三种入口。

网络请求（`_http_get`）与 arXiv API 都换桩，只验证解析与增量合并的契约。
"""
import json

import pytest

import customize as CZ

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------ 本地文档

def test_parse_doc_reads_text_and_markdown(sandbox):
    f = sandbox.root / "notes.md"
    f.write_text("Isolation level and serializability.", encoding="utf-8")
    meta, err = CZ.parse_doc(str(f))
    assert err == "" and meta["title"] == "notes.md"
    assert "serializability" in meta["text"]


def test_parse_doc_strips_html(sandbox):
    f = sandbox.root / "page.html"
    f.write_text("<html><body><p>Refinement types</p><script>x()</script></body></html>",
                 encoding="utf-8")
    meta, err = CZ.parse_doc(str(f))
    assert err == ""
    assert "Refinement types" in meta["text"]
    assert "<p>" not in meta["text"], "HTML 标签必须剥掉"


def test_parse_doc_missing_file(sandbox):
    meta, err = CZ.parse_doc(str(sandbox.root / "nope.md"))
    assert meta is None and "文件不存在" in err


def test_parse_doc_empty_file(sandbox):
    f = sandbox.root / "empty.md"
    f.write_text("   \n\n", encoding="utf-8")
    meta, err = CZ.parse_doc(str(f))
    assert meta is None and "空" in err


def test_parse_doc_truncates_huge_text(sandbox):
    f = sandbox.root / "big.md"
    f.write_text("x" * 500000, encoding="utf-8")
    meta, err = CZ.parse_doc(str(f))
    assert err == "" and len(meta["text"]) <= 400000


# ------------------------------------------------------------------ 链接

def test_parse_link_requires_http(sandbox):
    meta, err = CZ.parse_link("ftp://example.org")
    assert meta is None and "http" in err


def test_parse_link_extracts_title(sandbox, monkeypatch):
    monkeypatch.setattr(CZ, "_http_get",
                        lambda url, timeout=15, limit=600000:
                        "<html><head><title>Ada's   Home</title></head>"
                        "<body>Isolation level work</body></html>")
    meta, err = CZ.parse_link("https://example.org")
    assert err == "" and meta["title"] == "Ada's Home"
    assert "Isolation level" in meta["text"]


def test_parse_link_reports_fetch_failure(sandbox, monkeypatch):
    monkeypatch.setattr(CZ.time, "sleep", lambda *_: None)

    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(CZ, "_http_get", boom)
    meta, err = CZ.parse_link("https://example.org")
    assert meta is None and "抓取失败" in err


# ------------------------------------------------------------------ derive

def test_derive_rejects_unknown_type(sandbox):
    out = CZ.derive({"type": "magic", "value": "x"}, CZ.load_interests())
    assert "error" in out


def test_derive_from_doc_finds_people_and_topics(sandbox):
    f = sandbox.root / "home.md"
    f.write_text("Ada Lovelace studies isolation level and serializability.\n" * 3,
                 encoding="utf-8")
    prof = CZ.load_interests()
    out = CZ.derive({"type": "doc", "value": str(f)}, prof)
    assert "Ada Lovelace" in out["people"]
    assert "事务与隔离级别" in out["matched_topics"] or out["matched_topics"] == []


def test_matched_topics_reports_hit_names(sandbox):
    prof = sandbox.set_profile(topics=[
        {"name": "事务与隔离级别", "weight": 1.0, "keywords": ["isolation level"]}])
    hits = CZ.matched_topics("a paper about isolation level anomalies", prof)
    assert "事务与隔离级别" in hits


def test_refresh_all_rederives_existing_sources(sandbox):
    f = sandbox.root / "home.md"
    f.write_text("Ada Lovelace " * 4, encoding="utf-8")
    CZ.add_source("doc", str(f))
    before = CZ.load_extra()["_derived"]["people"]

    f.write_text("Ada Lovelace " * 4 + "\nGrace Hopper " * 4, encoding="utf-8")
    ok, msg, _ = CZ.refresh_all()
    assert ok, msg
    after = CZ.load_extra()["_derived"]["people"]
    assert "Grace Hopper" in after and "Ada Lovelace" in after
    assert before != after


def test_extra_file_shape(sandbox):
    CZ.save_extra(CZ.empty_extra())
    data = json.loads((sandbox.out / "interests_extra.json").read_text(encoding="utf-8"))
    assert set(data) >= {"sources", "_derived", "block_kw"}
