# -*- coding: utf-8 -*-
"""bili_collection：合集挂载的幂等性与「20080 是整批级拒绝」语义。

背景（2026-10-22 实测踩坑）：
  - member 的 seasons 列表接口给的是缓存快照，刚挂完/刚建完合集时看不到新条目，
    本地判重会误把「其实已在合集」的视频当成待挂载（每轮重复重投）。
  - 更严重的是 20080「当前稿件已存在在合集中」是**整批级**拒绝：批次里只要有一条
    已在合集，服务端就回 20080 且整批都不挂。曾把 20080 当整批成功，
    结果 20261022 期视频静默没挂上（BV1yQn16oEb3 的 season_id 为 None）。
判据一律以稿件详情（view 接口的 season_id / ugc_season.id）为准，并挂完回读校验。
"""
import pytest

import tools.bili_collection as BC

pytestmark = pytest.mark.unit

EP1 = {"title": "arXiv 日报 20261020｜测试", "aid": 117470761457336,
       "cid": 42887023270, "charging_pay": 0}
EP2 = {"title": "arXiv 日报 20261022｜测试", "aid": 117482807430140,
       "cid": 42946858674, "charging_pay": 0}


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _Session:
    """post 按队列回 payload；get 按 url+params 回 payload。"""

    def __init__(self, post_payloads=None, get_payloads=None):
        self.post_payloads = list(post_payloads or [])
        self.get_payloads = get_payloads or {}
        self.posts = []
        self.gets = []

    def post(self, url, **kw):
        self.posts.append((url, kw))
        payload = self.post_payloads.pop(0) if len(self.post_payloads) > 1 else \
            (self.post_payloads[0] if self.post_payloads else {"code": 0})
        return _Resp(payload)

    def get(self, url, **kw):
        aid = (kw.get("params") or {}).get("aid")
        self.gets.append((url, aid))
        return _Resp(self.get_payloads.get(aid, {"code": -400, "message": "no stub"}))


BATCH_20080 = [{"code": 20080, "message": "当前稿件已存在在合集中"},
               {"code": 0, "message": "0"}]


def test_add_episodes_success(capsys):
    s = _Session([{"code": 0, "message": "0"}])
    assert BC.add_episodes(s, {"bili_jct": "x"}, 10455435, [EP1]) is True
    assert len(s.posts) == 1
    assert "已挂载 1 个视频" in capsys.readouterr().out


def test_single_episode_20080_is_idempotent_success(capsys):
    """单条重投还回 20080 → 这一条确实已在合集，幂等成功。"""
    s = _Session([{"code": 20080, "message": "当前稿件已存在在合集中"}])
    assert BC.add_episodes(s, {"bili_jct": "x"}, 10455435, [EP1]) is True
    out = capsys.readouterr().out
    assert "幂等跳过" in out
    assert "[FAIL]" not in out


def test_batch_20080_falls_back_to_per_episode(capsys):
    """整批 20080 后必须逐条重投：已在的跳过，缺的补上。"""
    s = _Session([{"code": 20080, "message": "当前稿件已存在在合集中"},
                  {"code": 20080, "message": "当前稿件已存在在合集中"},
                  {"code": 0, "message": "0"}])
    assert BC.add_episodes(s, {"bili_jct": "x"}, 10455435, [EP1, EP2]) is True
    assert len(s.posts) == 3
    sent = [kw["json"]["episodes"] for _, kw in s.posts]
    assert [len(x) for x in sent] == [2, 1, 1]
    assert sent[1][0]["aid"] == EP1["aid"] and sent[2][0]["aid"] == EP2["aid"]
    out = capsys.readouterr().out
    assert "整批被拒" in out and "[FAIL]" not in out


def test_batch_20080_with_real_failure_is_failure(capsys):
    """逐条重投里出现真错误 → 整体失败。"""
    s = _Session([{"code": 20080, "message": "当前稿件已存在在合集中"},
                  {"code": 20080, "message": "当前稿件已存在在合集中"},
                  {"code": -400, "message": "请求错误"}])
    assert BC.add_episodes(s, {"bili_jct": "x"}, 10455435, [EP1, EP2]) is False
    assert "-400" in capsys.readouterr().out


def test_add_episodes_other_error_is_failure(capsys):
    s = _Session([{"code": -400, "message": "请求错误"}])
    assert BC.add_episodes(s, {"bili_jct": "x"}, 10455435, [EP1]) is False
    out = capsys.readouterr().out
    assert "[FAIL]" in out and "-400" in out


def test_add_episodes_empty_is_noop():
    s = _Session([{"code": 0}])
    assert BC.add_episodes(s, {}, 1, []) is True
    assert s.posts == []


def test_season_of_reads_season_id():
    s = _Session(get_payloads={1: {"code": 0, "data": {"season_id": 9343347}}})
    assert BC.season_of(s, 1) == 9343347


def test_season_of_falls_back_to_ugc_season():
    s = _Session(get_payloads={1: {"code": 0, "data": {"ugc_season": {"id": 9343347}}}})
    assert BC.season_of(s, 1) == 9343347


def test_season_of_none_when_not_in_any_season():
    s = _Session(get_payloads={1: {"code": 0, "data": {"season_id": None, "ugc_season": None}}})
    assert BC.season_of(s, 1) is None


def test_season_of_none_on_api_error_or_exception():
    s = _Session(get_payloads={1: {"code": -404, "message": "啥都木有"}})
    assert BC.season_of(s, 1) is None
    assert BC.season_of(None, 1) is None  # 异常路径（s.get 抛错）不能炸


def test_verify_membership_lists_missing():
    s = _Session(get_payloads={
        EP1["aid"]: {"code": 0, "data": {"season_id": 9343347}},
        EP2["aid"]: {"code": 0, "data": {"season_id": None}},
    })
    assert BC.verify_membership(s, 9343347, [EP1, EP2]) == [EP2]


def test_verify_membership_skips_check_without_season_id():
    s = _Session()
    assert BC.verify_membership(s, 0, [EP1, EP2]) == []
    assert s.gets == []


class _SeqSession:
    """get 按调用次序依次返回 payload（模拟缓存逐渐刷新）。"""

    def __init__(self, payload_seq):
        self.seq = list(payload_seq)
        self.n = 0

    def get(self, url, **kw):
        self.n += 1
        payload = self.seq.pop(0) if len(self.seq) > 1 else self.seq[0]
        return _Resp(payload)


def test_verify_settled_retries_until_visible(monkeypatch):
    """首次回读还看不到归属（CDN 缓存），重试后看到 → 视为通过。"""
    sleeps = []
    monkeypatch.setattr(BC, "_sleep", lambda s: sleeps.append(s))
    s = _SeqSession([{"code": 0, "data": {"season_id": None}},
                     {"code": 0, "data": {"season_id": 9343347}}])
    assert BC.verify_membership_settled(s, 9343347, [EP1]) == []
    assert s.n == 2
    assert sleeps == [BC.VERIFY_DELAY_SEC]


def test_verify_settled_reports_missing_after_all_attempts(monkeypatch):
    """重试到头仍看不到 → 如实报缺失（真没挂上，下一轮 sync 会补）。"""
    monkeypatch.setattr(BC, "_sleep", lambda s: None)
    s = _SeqSession([{"code": 0, "data": {"season_id": None}}])
    assert BC.verify_membership_settled(s, 9343347, [EP1], attempts=3) == [EP1]
    assert s.n == 3


def test_verify_settled_noop_without_season_or_eps(monkeypatch):
    monkeypatch.setattr(BC, "_sleep", lambda s: None)
    s = _SeqSession([{"code": 0, "data": {}}])
    assert BC.verify_membership_settled(s, 0, [EP1]) == []
    assert BC.verify_membership_settled(s, 9343347, []) == []
    assert s.n == 0


def test_plan_episodes_skips_cached_and_server_side_membership(capsys):
    """缓存命中的不查接口；缓存里没有但服务端已在合集的也不再重投。"""
    arcs = [{"aid": EP1["aid"], "bvid": "BV1", "title": "已缓存"},
            {"aid": EP2["aid"], "bvid": "BV2", "title": "服务端已在"},
            {"aid": 999, "bvid": "BV3", "title": "真·待挂载"}]
    s = _Session(get_payloads={
        EP2["aid"]: {"code": 0, "data": {"season_id": 9343347}},
        999: {"code": 0, "data": {"season_id": None, "cid": 12345}},
    })
    eps = BC.plan_episodes(s, arcs, {EP1["aid"]}, 9343347)
    assert [e["aid"] for e in eps] == [999]
    assert eps[0]["cid"] == 12345
    assert [aid for _, aid in s.gets] == [EP2["aid"], 999]  # 缓存命中那条不查
    out = capsys.readouterr().out
    assert "按稿件信息核对" in out


def test_plan_episodes_skips_when_cid_missing(capsys):
    s = _Session(get_payloads={1: {"code": 0, "data": {"season_id": None}}})
    assert BC.plan_episodes(s, [{"aid": 1, "bvid": "BV1", "title": "t"}], set(), 9343347) == []
    assert "取不到 cid" in capsys.readouterr().out


def test_collection_aids_reads_part_episodes():
    sn = {"part_episodes": [{"aid": 1}, {"aid": 2}, {"aid": None}]}
    assert BC.collection_aids(sn) == {1, 2}


def test_default_section_prefers_main_section():
    sn = {"sections": {"sections": [{"id": 7, "title": "预告"},
                                    {"id": 10455435, "title": "正片"}]}}
    assert BC.default_section_id(sn) == 10455435


def test_season_id_of_reads_season_object():
    assert BC.season_id_of({"season": {"id": 9343347}}) == 9343347
    assert BC.season_id_of({}) == 0
