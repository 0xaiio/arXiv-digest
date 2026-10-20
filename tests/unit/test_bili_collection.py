# -*- coding: utf-8 -*-
"""bili_collection：合集挂载的幂等性。

背景：合集列表接口有短暂缓存，刚挂载完立刻重跑 sync 时本地判重看不到新条目，
会再发一次 add；服务端返回 20080「当前稿件已存在在合集中」。这属于**已成功**，
必须按成功处理，否则定时任务会把一次成功挂载误报为失败。
"""
import pytest

import tools.bili_collection as BC

pytestmark = pytest.mark.unit

EPS = [{"title": "arXiv 日报 20261020｜测试", "aid": 117470761457336,
        "cid": 42887023270, "charging_pay": 0}]


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, **kw):
        self.calls.append((url, kw))
        return _Resp(self.payload)


def test_add_episodes_success(capsys):
    s = _Session({"code": 0, "message": "0"})
    assert BC.add_episodes(s, {"bili_jct": "x"}, 10455435, EPS) is True
    assert len(s.calls) == 1
    assert "已挂载 1 个视频" in capsys.readouterr().out


def test_add_episodes_already_exists_is_success(capsys):
    """20080 = 已存在 → 幂等成功，不能当失败。"""
    s = _Session({"code": 20080, "message": "当前稿件已存在在合集中"})
    assert BC.add_episodes(s, {"bili_jct": "x"}, 10455435, EPS) is True
    out = capsys.readouterr().out
    assert "幂等跳过" in out
    assert "[FAIL]" not in out


def test_add_episodes_other_error_is_failure(capsys):
    s = _Session({"code": -400, "message": "请求错误"})
    assert BC.add_episodes(s, {"bili_jct": "x"}, 10455435, EPS) is False
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "-400" in out


def test_collection_aids_reads_part_episodes():
    sn = {"part_episodes": [{"aid": 1}, {"aid": 2}, {"aid": None}]}
    assert BC.collection_aids(sn) == {1, 2}


def test_default_section_prefers_main_section():
    sn = {"sections": {"sections": [{"id": 7, "title": "预告"},
                                    {"id": 10455435, "title": "正片"}]}}
    assert BC.default_section_id(sn) == 10455435
