# -*- coding: utf-8 -*-
"""端到端：把「一个用户的一天」跑通。

不是再测一遍函数，而是把四层串起来验证：
    数据 → 打分 → 渲染 → HTTP 交互 → 落库 → 再次打分是否反映用户意图
每个用例都从隔离目录开始，走真实的服务进程（ThreadingHTTPServer）与真实文件；
只有出网点（下载 PDF）被桩掉。
"""
import json

import pytest

import build_report as B
import customize as CZ
import paperutil as pu
import profile as PF
import recommend as R

pytestmark = pytest.mark.e2e


def _scores(sandbox):
    return {s["id"]: s["score"] for s in sandbox.read("scores.json")}


def test_full_journey_read_favorite_download_downvote(seeded, http, monkeypatch):
    """一天的主线：看首页 → 收藏 → 下载 → Downvote → 分数确实变了 → 撤销。"""
    import server as S

    R.main()
    B.main()

    # 1) 首页能打开，推荐里有强命中的那篇
    code, page = http.get("/")
    assert code == 200
    assert "Isolation Level Selection" in page
    base_score = _scores(seeded)["2609.10001"]
    assert base_score > 15

    # 2) 收藏 → 收藏页立刻能看到（每次请求动态渲染）
    code, d = http.post("/api/favorite", {"id": "2609.10001"})
    assert d["ok"]
    code, fav_page = http.get("/favorites")
    assert "Isolation Level Selection" in fav_page

    # 3) 下载（只桩掉取数）→ 自动收藏 + 记录绝对路径
    seeded.download_dir.mkdir(parents=True, exist_ok=True)
    pdf = seeded.download_dir / "arXiv2026 2609.10001 Isolation Level.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    monkeypatch.setattr(S, "download_pdf",
                        lambda sid, papers, cfg, force=False: (True, "", str(pdf)))

    code, d = http.post("/api/download", {"id": "2609.10001"})
    assert d["ok"] and d["favorited"]

    state = http.get_json("/api/state")[1]
    assert "2609.10001" in state["favorites"]
    assert state["downloads"]["2609.10001"] == str(pdf)

    # 4) 行为学习：下载把该主题倍率推高了，并留下流水
    st = PF.load()
    assert st["topic_mult"]["事务与隔离级别"] > 1.0
    assert st["counts"]["download"] == 1
    assert any(b["action"] == "download" for b in PF.load_behavior())

    # 5) Downvote → 写 -12；重建后同一篇分数显著下降
    code, d = http.post("/api/downvote", {"id": "2609.10001"})
    assert d["ok"]
    assert http.get_json("/api/profile")[1]["pens"]["2609.10001"] == -12.0

    R.main()
    penalized = _scores(seeded)["2609.10001"]
    assert penalized < base_score - 6, "惩罚应显著拉低分数（%s -> %s）" % (base_score, penalized)

    # 6) 撤销 Downvote → -12 消失，但学习到的权重仍在（分数不会退回原点）
    code, d = http.post("/api/undownvote", {"id": "2609.10001"})
    assert d["ok"]
    R.main()
    restored = _scores(seeded)["2609.10001"]
    assert restored == pytest.approx(penalized + 12.0, abs=0.1)
    assert restored > base_score, "收藏/下载带来的主题加权应当保留"


def test_journey_tune_profile_then_rebuild(seeded, http, monkeypatch):
    """改画像 → 点「↻ 重算推荐」 → 该篇分数随主题权重上升。"""
    import server as S

    R.main()
    before = _scores(seeded)["2609.10001"]

    prof = CZ.load_interests()
    prof["topics"][0]["weight"] = 3.0          # 1.5 → 3.0
    seeded.interests.write_text(json.dumps(prof, ensure_ascii=False), encoding="utf-8")

    class Done:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kw):
        R.main()
        B.main()
        return Done()

    monkeypatch.setattr(S.subprocess, "run", fake_run)
    code, d = http.post("/api/rebuild", {})
    assert d["ok"], d["msg"]

    after = _scores(seeded)["2609.10001"]
    assert after > before + 5, "权重翻倍后分数必须明显上升（%s -> %s）" % (before, after)


def test_archive_journey_can_look_back(seeded, http):
    """跑两期：往期仍可按日期回看，且快照只增不改。"""
    import hashlib

    R.main()
    B.main()
    snap = seeded.out / "archive" / "20261015.html"
    first_hash = hashlib.sha256(snap.read_bytes()).hexdigest()

    core = seeded.read("raw.json")
    core["papers"] = [{
        "id": "http://arxiv.org/abs/2610.40001v1",
        "title": "A Follow-up on Isolation Level",
        "abstract": "isolation level and serializability again",
        "authors": ["Ada Lovelace"], "published": "2026-10-16T00:00:00Z",
        "updated": "2026-10-16T00:00:00Z", "primary": "cs.DB", "cats": ["cs.DB"],
        "pdf": "https://arxiv.org/pdf/2610.40001", "comment": "",
        "queried_cat": "cs.DB"}]
    core["newest_seen"] = "2026-10-16"
    core["generated_at"] = "2026-10-16T08:00:00+08:00"
    seeded.write("raw.json", core)
    R.main()
    B.main()

    code, days = http.get_json("/api/archive/days")
    assert set(days["dates"]) >= {"20261015", "20261016"}

    code, old = http.get("/archive/20261015")
    assert code == 200 and "Isolation Level Selection" in old
    code, new = http.get("/archive/20261016")
    assert code == 200 and "A Follow-up on Isolation Level" in new
    assert hashlib.sha256(snap.read_bytes()).hexdigest() == first_hash, \
        "往期快照必须只增不改"


def test_fresh_install_has_no_personal_traces(bare_sandbox):
    """新克隆：没有任何配置文件时，第一次初始化必须干净且不报错。"""
    cfg = pu.load_config()
    prof = CZ.load_interests()

    assert cfg["download_dir"] == "papers"
    assert prof["owners"] == [], "不得带入任何人的画像主来源"
    assert prof["people"] == []

    text = (bare_sandbox.interests.read_text(encoding="utf-8")
            + bare_sandbox.cfg.read_text(encoding="utf-8"))
    for leak in ("魏恒峰", "Gotsman", "Attiya", "Enea", "git-papers"):
        assert leak not in text


def test_pipeline_without_fetch_data_fails_loudly(bare_sandbox):
    """没有抓取数据时必须明确失败，而不是渲染出一个空页面。"""
    with pytest.raises(SystemExit):
        R.main()
    with pytest.raises(SystemExit):
        B.main()
