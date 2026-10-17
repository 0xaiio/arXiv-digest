# -*- coding: utf-8 -*-
"""service：业务用例层（收藏 / 下载 / 画像 / 重建）。

这一层原先内联在 Handler 的 if 链里，只能通过真 HTTP 服务验证。
拆出来后可以直接调，并且「外部替换」的语义也能在这里钉住 ——
tools/concurrency_check.py 就是靠替换 server.download_pdf 来桩化的。
"""
import threading
import time

import pytest

import paperutil as pu
import service as SV

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------ PaperIndex

def test_paper_index_loads_once_within_ttl():
    calls = []

    def loader():
        calls.append(1)
        return {"2609.1": {"title": "T"}}

    idx = SV.PaperIndex(loader=loader, ttl=60)
    assert idx.get()["2609.1"]["title"] == "T"
    idx.get()
    idx.get()
    assert len(calls) == 1


def test_paper_index_force_always_reloads():
    calls = []
    idx = SV.PaperIndex(loader=lambda: calls.append(1) or {}, ttl=60)
    idx.get()
    idx.get(force=True)
    assert len(calls) == 2


def test_paper_index_reloads_after_ttl():
    calls = []
    idx = SV.PaperIndex(loader=lambda: calls.append(1) or {}, ttl=0)
    idx.get()
    time.sleep(0.01)
    idx.get()
    assert len(calls) == 2


def test_paper_index_reset_forces_next_reload():
    calls = []
    idx = SV.PaperIndex(loader=lambda: calls.append(1) or {}, ttl=60)
    idx.get()
    idx.reset()
    idx.get()
    assert len(calls) == 2


def test_paper_index_is_thread_safe():
    """并发进来只应有一次真正解析（双重检查）。"""
    calls = []
    started = threading.Event()

    def slow_loader():
        calls.append(1)
        started.set()
        time.sleep(0.05)
        return {"a": 1}

    idx = SV.PaperIndex(loader=slow_loader, ttl=60)
    out = []
    threads = [threading.Thread(target=lambda: out.append(idx.get()))
               for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1
    assert all(v == {"a": 1} for v in out)


def test_module_level_index_uses_paperutil_loader():
    assert SV.PAPER_INDEX._loader is pu.load_papers


# ------------------------------------------------------------------ latest_digest

def test_latest_digest_picks_newest_date(sandbox):
    for name in ("arxiv_digest_20261001.html", "arxiv_digest_20261015.html",
                 "arxiv_digest_20261009.html", "notes.html"):
        (sandbox.out / name).write_text("x", encoding="utf-8")
    got = SV.latest_digest(str(sandbox.out))
    assert got.endswith("arxiv_digest_20261015.html")


def test_latest_digest_returns_none_when_empty(sandbox):
    assert SV.latest_digest(str(sandbox.out)) is None


def test_latest_digest_tolerates_missing_dir(sandbox):
    assert SV.latest_digest(str(sandbox.root / "nope")) is None


# ------------------------------------------------------------------ 下载与落库

def test_download_one_uses_injected_download_fn(sandbox):
    calls = []
    learned = []

    def fake_dl(sid, papers, cfg):
        calls.append(sid)
        return True, "ok", "/tmp/%s.pdf" % sid

    r = SV.download_one("2609.00001", {"download_dir": "p"},
                        {"2609.00001": {"title": "T"}},
                        download_fn=fake_dl,
                        learn_fn=lambda sid, act, paper=None: learned.append(act))
    assert r == {"id": "2609.00001", "ok": True, "msg": "ok",
                 "path": "/tmp/2609.00001.pdf"}
    assert calls == ["2609.00001"] and learned == ["download"]
    assert pu.load_library()["favorites"]["2609.00001"]["title"] == "T"


def test_download_one_skips_records_on_failure(sandbox):
    r = SV.download_one("2609.00002", {"download_dir": "p"}, {},
                        download_fn=lambda *a: (False, "boom", ""))
    assert r["ok"] is False
    assert "2609.00002" not in pu.load_library()["favorites"]


def test_download_many_keeps_request_order(sandbox):
    def fake_dl(sid, papers, cfg):
        time.sleep(0.01 * (5 - int(sid[-1])))   # 后面的更快完成
        return True, "", "/p/%s.pdf" % sid

    ids = ["2609.00005", "2609.00001", "2609.00003"]
    res = SV.download_many(ids, {"download_dir": "p"}, {}, download_fn=fake_dl)
    assert [r["id"] for r in res] == ids


def test_download_many_runs_in_parallel(sandbox):
    def slow(sid, papers, cfg):
        time.sleep(0.15)
        return True, "", "/p/%s.pdf" % sid

    t0 = time.time()
    SV.download_many(["2609.00001", "2609.00002", "2609.00003"],
                     {"download_dir": "p"}, {}, workers=3, download_fn=slow)
    assert time.time() - t0 < 0.40, "三篇应并行（串行需 0.45s）"


def test_same_paper_download_is_serialised(sandbox):
    """同一篇并发两次必须串行（否则会争抢同名 .part）。"""
    active = {"now": 0, "peak": 0}
    guard = threading.Lock()

    def slow(sid, papers, cfg):
        with guard:
            active["now"] += 1
            active["peak"] = max(active["peak"], active["now"])
        time.sleep(0.12)
        with guard:
            active["now"] -= 1
        return True, "", "/p/x.pdf"

    ths = [threading.Thread(target=lambda: SV.download_one(
        "2609.00009", {"download_dir": "p"}, {}, download_fn=slow))
        for _ in range(2)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    assert active["peak"] == 1


def test_record_download_marks_favorite_and_downloaded(sandbox):
    SV.record_download("2609.00001", "/p/x.pdf", "A Title")
    lib = pu.load_library()
    assert lib["downloads"]["2609.00001"]["path"] == "/p/x.pdf"
    assert lib["favorites"]["2609.00001"]["downloaded"] is True
    assert lib["favorites"]["2609.00001"]["path"] == "/p/x.pdf"


def test_record_download_without_title_still_favorites(sandbox):
    SV.record_download("2609.00002", "/p/y.pdf")
    assert "2609.00002" in pu.load_library()["favorites"]


# ------------------------------------------------------------------ 画像

def test_profile_snapshot_shape(sandbox):
    snap = SV.profile_snapshot()
    assert set(snap) == {"topics", "weights", "kw", "pens"}
    assert isinstance(snap["topics"], list) and isinstance(snap["kw"], dict)


def test_learn_swallows_errors(sandbox, monkeypatch):
    """学习失败不能把整个请求打挂（它只是画像的旁路）。"""
    def boom(*a, **k):
        raise RuntimeError("bad state")

    monkeypatch.setattr(SV.PF, "apply_event", boom)
    SV.learn("2609.00001", "favorite")     # 不抛异常即通过


# ------------------------------------------------------------------ 重建

class _Result:
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def test_rebuild_runs_steps_in_order(sandbox, monkeypatch):
    seen = []
    monkeypatch.setattr(SV.subprocess, "run",
                        lambda cmd, **kw: (seen.append(cmd[1]), _Result())[1])
    ok, msg = SV.rebuild_digest(root=str(sandbox.root))
    assert ok and "已重算" in msg
    assert [s.split("\\")[-1].split("/")[-1] for s in seen] == ["recommend.py", "build_report.py"]


def test_rebuild_resets_paper_index(sandbox, monkeypatch):
    monkeypatch.setattr(SV.subprocess, "run", lambda cmd, **kw: _Result())
    calls = []
    monkeypatch.setattr(SV, "reset_papers", lambda: calls.append(1))
    SV.rebuild_digest(root=str(sandbox.root))
    assert calls == [1]


def test_rebuild_stops_on_nonzero_exit(sandbox, monkeypatch):
    monkeypatch.setattr(SV.subprocess, "run",
                        lambda cmd, **kw: _Result(rc=1, err="Traceback: boom"))
    ok, msg = SV.rebuild_digest(root=str(sandbox.root))
    assert not ok and "recommend.py 失败" in msg and "boom" in msg


def test_rebuild_reports_timeout(sandbox, monkeypatch):
    def timeout(cmd, **kw):
        raise SV.subprocess.TimeoutExpired(cmd, kw.get("timeout"))

    monkeypatch.setattr(SV.subprocess, "run", timeout)
    ok, msg = SV.rebuild_digest(root=str(sandbox.root), timeout=5)
    assert not ok and "超时" in msg


def test_rebuild_reports_spawn_failure(sandbox, monkeypatch):
    def boom(cmd, **kw):
        raise OSError("no such file")

    monkeypatch.setattr(SV.subprocess, "run", boom)
    ok, msg = SV.rebuild_digest(root=str(sandbox.root))
    assert not ok and "启动失败" in msg


# ------------------------------------------------------------------ 其它

def test_open_path_reports_missing_file(sandbox):
    ok, msg = SV.open_path(str(sandbox.root / "nope.pdf"))
    assert not ok and "不存在" in msg


def test_quiet_remove_ignores_missing(sandbox):
    SV.quiet_remove(str(sandbox.root / "nope"))     # 不抛异常即通过


def test_ensure_dir_creates_nested(sandbox):
    d = sandbox.root / "a" / "b" / "c"
    SV.ensure_dir(str(d))
    assert d.is_dir()
