# -*- coding: utf-8 -*-
"""server.download_pdf：真·落盘路径（只把网络取数换掉）。

这段代码是「点了下载没反应」的历史高发区：目录不存在、同名文件已存在、
取数失败、写入失败，每种都要给出**能照着做**的中文提示。
"""
import os

import pytest

import paperutil as pu
import server as S

pytestmark = pytest.mark.unit

PDF = b"%PDF-1.4 fake body"


@pytest.fixture()
def cfg(sandbox):
    d = sandbox.root / "papers"
    sandbox.set_config(download_dir=str(d))
    return {"download_dir": str(d)}


@pytest.fixture()
def papers(make_paper):
    return {"2609.10001": make_paper("2609.10001", "Isolation Level Selection",
                                     published="2026-10-14T00:00:00Z")}


def test_download_writes_file_and_cleans_part(sandbox, cfg, papers, monkeypatch):
    monkeypatch.setattr(S.NR, "fetch_first",
                        lambda urls, timeout=90: (PDF, "直连", urls[0]))
    ok, msg, path = S.download_pdf("2609.10001", papers, cfg)
    assert ok
    assert open(path, "rb").read() == PDF
    assert "arXiv2026 2609.10001 Isolation Level Selection.pdf" == os.path.basename(path)
    assert not os.path.exists(path + ".part")


def test_download_skips_existing_file(sandbox, cfg, papers, monkeypatch):
    target = os.path.join(cfg["download_dir"], pu.build_filename(
        "2609.10001", papers["2609.10001"]["title"], "2026"))
    os.makedirs(cfg["download_dir"], exist_ok=True)
    open(target, "wb").write(b"already here")

    called = []
    monkeypatch.setattr(S.NR, "fetch_first",
                        lambda *a, **k: called.append(1) or (PDF, "直连", ""))
    ok, msg, path = S.download_pdf("2609.10001", papers, cfg)
    assert ok and "已存在" in msg
    assert called == [], "已存在时不应再发网络请求"


def test_download_force_redownloads(sandbox, cfg, papers, monkeypatch):
    target = os.path.join(cfg["download_dir"], pu.build_filename(
        "2609.10001", papers["2609.10001"]["title"], "2026"))
    os.makedirs(cfg["download_dir"], exist_ok=True)
    open(target, "wb").write(b"old")

    monkeypatch.setattr(S.NR, "fetch_first", lambda *a, **k: (PDF, "直连", ""))
    ok, msg, path = S.download_pdf("2609.10001", papers, cfg, force=True)
    assert ok and open(path, "rb").read() == PDF


def test_download_unknown_paper(cfg):
    ok, msg, path = S.download_pdf("2609.99999", {}, cfg)
    assert not ok and path == "" and "未找到论文元数据" in msg


def test_download_falls_back_to_library(sandbox, cfg, monkeypatch):
    """历史收藏可能已不在当前池里：元数据要从 library.json 兜底。"""
    lib = pu.load_library()
    lib["favorites"]["2609.10001"] = {"id": "2609.10001", "title": "From Library",
                                      "published": "2026-10-14T00:00:00Z"}
    pu.save_library(lib)

    monkeypatch.setattr(S.NR, "fetch_first", lambda *a, **k: (PDF, "直连", ""))
    ok, _, path = S.download_pdf("2609.10001", {}, cfg)
    assert ok and "From Library" in path


def test_download_reports_route_failure(cfg, papers, monkeypatch):
    def boom(*a, **k):
        raise S.NR.RouteError("全部不可用")

    monkeypatch.setattr(S.NR, "fetch_first", boom)
    monkeypatch.setattr(S.NR, "last_failure", lambda: {"detail": "TLS 被掐断"})
    ok, msg, _ = S.download_pdf("2609.10001", papers, cfg)
    assert not ok
    assert "所有网络路由都不通" in msg
    assert "/api/net_route" in msg, "错误提示必须指向诊断入口"


def test_download_reports_generic_failure(cfg, papers, monkeypatch):
    monkeypatch.setattr(S.NR, "fetch_first",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("disk full")))
    ok, msg, _ = S.download_pdf("2609.10001", papers, cfg)
    assert not ok and "下载失败" in msg and "disk full" in msg
