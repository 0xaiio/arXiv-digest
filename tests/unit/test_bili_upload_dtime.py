# -*- coding: utf-8 -*-
"""`bili_upload.py --dtime` 的解析回归。

背景：2026-11-27 把发布从「生产完即发」改为 22:00 定时。biliup 要求
`--dtime` 距提交 >4 小时，脚本必须提前拒绝过近的时刻，并把 `HH:MM`
正确换算成当天/次日的 10 位时间戳，否则流水线会在 dry-run 通过后真投失败。
"""
import datetime as dt
import importlib.util
import os

import pytest

pytestmark = pytest.mark.unit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, ".workbuddy", "skills", "bili-auto-upload", "scripts", "bili_upload.py")
TZ = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime(2026, 11, 27, 10, 0, tzinfo=TZ)


@pytest.fixture(scope="module")
def BU():
    spec = importlib.util.spec_from_file_location("bili_upload_dtime_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hhmm_same_day(BU):
    ts = BU.resolve_dtime("22:00", NOW)
    assert dt.datetime.fromtimestamp(ts, TZ) == dt.datetime(2026, 11, 27, 22, 0, tzinfo=TZ)


def test_hhmm_past_rolls_to_next_day(BU):
    ts = BU.resolve_dtime("09:00", NOW)
    assert dt.datetime.fromtimestamp(ts, TZ) == dt.datetime(2026, 11, 28, 9, 0, tzinfo=TZ)


def test_ten_digit_timestamp_passthrough(BU):
    ts = int(dt.datetime(2026, 11, 27, 22, 30, tzinfo=TZ).timestamp())
    assert BU.resolve_dtime(str(ts), NOW) == ts


def test_too_close_is_rejected(BU):
    with pytest.raises(ValueError, match="大于 4 小时"):
        BU.resolve_dtime("13:00", NOW)


def test_bad_format_is_rejected(BU):
    with pytest.raises(ValueError, match="HH:MM"):
        BU.resolve_dtime("22-00", NOW)
