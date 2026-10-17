# -*- coding: utf-8 -*-
"""fetch_affil：单位抽取的判定边界（业务上「宁缺勿错」）。

这条链路的错误代价不对称：漏一个单位只是少一行信息，写错一个（把城市当机构）
会长期污染缓存与页面。所以这里的用例集中在「该拒绝的必须拒绝」。
"""
import json

import pytest

import fetch_affil as FA

pytestmark = pytest.mark.unit


HTML = """<html><body>
<div class="ltx_authors">
  <span class="ltx_personname">Ada Lovelace</span>
  <span class="ltx_affiliation">Analytical Engine Laboratory, London, UK</span>
  <span class="ltx_personname">Alan Turing</span>
  <span class="ltx_affiliation">University of Manchester, Manchester, UK</span>
</div>
<div class="ltx_abstract"><p>Abstract text</p></div>
</body></html>"""


def test_extract_units_from_latexml():
    out = FA.extract(HTML)
    assert len(out["units"]) == 2
    joined = " | ".join(out["units"])
    assert "Analytical Engine Laboratory" in joined
    assert "University of Manchester" in joined


def test_extract_returns_empty_without_author_block():
    assert FA.extract("<html><body><p>no authors</p></body></html>") == {"units": [],
                                                                        "by_author": {}}


def test_extract_rejects_city_only_affiliations():
    """城市/国家不是机构：宁可判为没找到，也不写进缓存。"""
    html = """<div class="ltx_authors">
      <span class="ltx_personname">Ada Lovelace</span>
      <span class="ltx_affiliation">Beijing, China</span>
    </div>"""
    assert FA.extract(html)["units"] == []


def test_extract_dedupes_repeated_units():
    html = """<div class="ltx_authors">
      <span class="ltx_personname">Ada Lovelace</span>
      <span class="ltx_affiliation">University of Oxford, UK</span>
      <span class="ltx_personname">Alan Turing</span>
      <span class="ltx_affiliation">University of Oxford</span>
    </div>"""
    units = FA.extract(html)["units"]
    assert len(units) == 1 and "Oxford" in units[0]


def test_extract_caps_at_twelve():
    spans = []
    for i in range(20):
        spans.append('<span class="ltx_personname">Person %d Name</span>' % i)
        spans.append('<span class="ltx_affiliation">Institute %d of Technology</span>' % i)
    html = '<div class="ltx_authors">%s</div>' % "".join(spans)
    assert len(FA.extract(html)["units"]) <= 12


def test_country_code_suffix_is_not_mistaken_for_us_state():
    """回归：`Manchester, UK` / `Shanghai, CN` 曾被「城市+两位代码」误判成城市丢弃。"""
    for s in ("University of Manchester, Manchester, UK",
              "Shanghai Jiao Tong University, Shanghai, CN",
              "Analytical Engine Laboratory, London, UK"):
        assert FA._looks_like_org(s), s
        assert FA._acceptable_affil(s), s

    # 没有机构关键词的「城市, 州」仍然要拒（真实数据里这类噪音很多）
    for s in ("Kelowna, BC", "Beijing, CA"):
        assert not FA._looks_like_org(s), s
        assert not FA._acceptable_affil(s), s


# ------------------------------------------------------------------ 目标选择

def test_targets_dedupes_and_caps(sandbox):
    recs = [{"id": "2609.10001"}, {"id": "2609.10002"}, {"id": "2609.10001"}]
    exp = [{"id": "2610.20001"}]
    sandbox.write("recommend.json", recs)
    sandbox.write("expand.json", exp)
    sandbox.write("highlights.json", {"2609.10003": "看点", "2610.20001": "dup"})

    ids = FA.targets({"affil_targets": 10})
    assert ids == ["2609.10001", "2609.10002", "2610.20001", "2609.10003"]


def test_targets_respects_limit(sandbox):
    sandbox.write("recommend.json", [{"id": "2609.1000%d" % i} for i in range(5)])
    assert len(FA.targets({"affil_targets": 2})) == 2


def test_targets_filters_invalid_ids(sandbox):
    sandbox.write("recommend.json", [{"id": "not-an-arxiv-id"}, {"id": ""},
                                     {"id": "2609.10001"}])
    assert FA.targets({}) == ["2609.10001"]


def test_targets_survives_corrupt_files(sandbox):
    (sandbox.out / "recommend.json").write_text("{broken", encoding="utf-8")
    assert FA.targets({}) == []


def test_cache_roundtrip(sandbox):
    FA.save_cache({"2609.10001": {"units": ["Lab"]}})
    assert FA.load_cache()["2609.10001"]["units"] == ["Lab"]
    data = json.loads((sandbox.out / "affiliations.json").read_text(encoding="utf-8"))
    assert "2609.10001" in data


def test_cache_tolerates_corrupt_file(sandbox):
    (sandbox.out / "affiliations.json").write_text("{oops", encoding="utf-8")
    assert FA.load_cache() == {}


# ------------------------------------------------------------------ 主流程

def _prepare_targets(sandbox, ids=("2609.10001", "2609.10002")):
    sandbox.set_config(affil_targets=10)
    sandbox.write("recommend.json", [{"id": i} for i in ids])


def test_main_fetches_and_caches(sandbox, monkeypatch, capsys):
    _prepare_targets(sandbox)
    monkeypatch.setattr(FA, "fetch_html", lambda sid: (HTML, "arxiv"))
    monkeypatch.setattr(FA.time, "sleep", lambda *_: None)
    monkeypatch.setattr(FA.sys, "argv", ["fetch_affil.py"])

    FA.main()
    cache = FA.load_cache()
    assert set(cache) == {"2609.10001", "2609.10002"}
    assert cache["2609.10001"]["units"], "抽到单位才写缓存"
    assert "2 ok, 0 failed" in capsys.readouterr().out


def test_main_skips_cached_targets(sandbox, monkeypatch, capsys):
    _prepare_targets(sandbox, ids=("2609.10001",))
    monkeypatch.setattr(FA, "fetch_html", lambda sid: (HTML, "arxiv"))
    monkeypatch.setattr(FA.time, "sleep", lambda *_: None)

    monkeypatch.setattr(FA.sys, "argv", ["fetch_affil.py"])
    FA.main()
    capsys.readouterr()

    called = []
    monkeypatch.setattr(FA, "fetch_html", lambda sid: called.append(sid) or ("", ""))
    FA.main()
    out = capsys.readouterr().out
    assert "nothing to do" in out
    assert called == [], "已缓存的不应再抓"


def test_main_force_refetches(sandbox, monkeypatch, capsys):
    _prepare_targets(sandbox, ids=("2609.10001",))
    monkeypatch.setattr(FA, "fetch_html", lambda sid: (HTML, "arxiv"))
    monkeypatch.setattr(FA.time, "sleep", lambda *_: None)
    monkeypatch.setattr(FA.sys, "argv", ["fetch_affil.py"])
    FA.main()
    capsys.readouterr()

    called = []
    monkeypatch.setattr(FA, "fetch_html", lambda sid: called.append(sid) or (HTML, "arxiv"))
    monkeypatch.setattr(FA.sys, "argv", ["fetch_affil.py", "--force"])
    FA.main()
    assert called == ["2609.10001"]


def test_main_only_accepts_ids_outside_targets(sandbox, monkeypatch, capsys):
    _prepare_targets(sandbox, ids=("2609.10001",))
    monkeypatch.setattr(FA, "fetch_html", lambda sid: (HTML, "arxiv"))
    monkeypatch.setattr(FA.time, "sleep", lambda *_: None)
    monkeypatch.setattr(FA.sys, "argv",
                        ["fetch_affil.py", "--only", "2609.77777"])

    FA.main()
    assert "2609.77777" in FA.load_cache()


def test_main_max_limits_work(sandbox, monkeypatch, capsys):
    _prepare_targets(sandbox, ids=("2609.10001", "2609.10002", "2609.10003"))
    monkeypatch.setattr(FA, "fetch_html", lambda sid: (HTML, "arxiv"))
    monkeypatch.setattr(FA.time, "sleep", lambda *_: None)
    monkeypatch.setattr(FA.sys, "argv", ["fetch_affil.py", "--max", "1"])

    FA.main()
    assert len(FA.load_cache()) == 1


def test_main_counts_failures_without_writing_cache(sandbox, monkeypatch, capsys):
    _prepare_targets(sandbox, ids=("2609.10001",))
    monkeypatch.setattr(FA, "fetch_html", lambda sid: ("", ""))
    monkeypatch.setattr(FA.time, "sleep", lambda *_: None)
    monkeypatch.setattr(FA.sys, "argv", ["fetch_affil.py"])

    FA.main()
    assert FA.load_cache() == {}
    assert "0 ok, 1 failed" in capsys.readouterr().out
