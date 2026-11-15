#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把周报数据整理成 Remotion 需要的分段数据与中文旁白稿。

与日报视频的分工完全一致：
    日报  `gen_video_data.py`  读 recommend.json  → reel/src/papers.json（10 篇 × 20s）
    周报  本脚本              读 trend_archive/*.json → reel/src/trend.json（6 主题 + 1 增长 × 20s）

为什么旁白是**模板生成**而不是手写：周报讲的是数字（篇数、占比、倍数），
每个数字都能从 JSON 里取到，模板句不会说错；日报要讲论文贡献，才必须人工/模型写。
任何一段旁白都能追溯到 `trend_archive/<期号>.json` 里的字段。

用法::

    python tools/gen_trend_video_data.py                 # 最新一期
    python tools/gen_trend_video_data.py -d 20261115 --k 6
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
ARCHIVE = os.path.join(OUT, "trend_archive")
REEL = os.path.join(ROOT, "reel", "src")

TOPICS_DEFAULT = 6     # 主题段数（+1 段增长 = 总段数）
SEGMENT_SEC = 20       # 与 PaperReel 的 PAPER 常量保持一致


def load(path, default):
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def latest_issue() -> str | None:
    files = sorted(glob.glob(os.path.join(ARCHIVE, "*.json")))
    if not files:
        return None
    m = re.search(r"(\d{8})\.json$", os.path.basename(files[-1]))
    return m.group(1) if m else None


def pick_segments(data: dict, k: int) -> list[dict]:
    """取占比最高的 k 个主题簇，再接一段「增长」。"""
    clusters = sorted(data.get("clusters") or [], key=lambda c: -c.get("size", 0))[:k]
    segs = []
    for i, c in enumerate(clusters, start=1):
        sample = (c.get("samples") or [{}])[0]
        segs.append({
            "kind": "topic",
            "rank": i,
            "label": c.get("label") or "主题",
            "terms": (c.get("terms") or [])[:5],
            "count": c.get("size") or 0,
            "share": c.get("share") or 0.0,
            "sample": {"sid": sample.get("sid") or "", "title": sample.get("title") or ""},
        })
    growth = (data.get("growth_up") or [])[:4]
    segs.append({"kind": "growth", "rank": len(segs) + 1, "items": growth})
    return segs


def _pct(share: float) -> int:
    return int(round((share or 0) * 100))


def build_notes(data: dict, segs: list[dict]) -> dict:
    """每段一句中文旁白，字数控制在 85–115 字（20 秒段的舒适区间）。"""
    notes = {}
    total = data.get("total") or 0
    cats = len(data.get("categories") or [])
    win = data.get("window") or {}
    start, end = win.get("start", ""), win.get("end", "")
    # 片头只有 5 秒（≈20 字）：窗口、篇数、分类数都在画面上，旁白不重复念数字，
    # 否则音频会压进第一个主题段，变成两段叠着说。
    notes["_intro"] = {"narration": "这一周，计算机科学在往哪走？"}
    for i, s in enumerate([x for x in segs if x["kind"] == "topic"]):
        terms = "、".join(s["terms"][:3]) or "暂无"
        leader = "第一个" if i == 0 else ("第二个" if i == 1 else "第 %d 个" % (i + 1))
        notes["t%d" % s["rank"]] = {
            "narration": "%s方向是%s。本周 %d 篇，占全部论文的 %d%%。系统聚出的代表词是%s。"
                         "与它最接近的工作，画面右侧能看到标题与编号。"
                         % (leader, s["label"], s["count"], _pct(s["share"]), terms)
        }
    growth = next((x for x in segs if x["kind"] == "growth"), {"items": []})
    if growth["items"]:
        first = growth["items"][0]
        extra = "；".join("%s 是 %.2f 倍" % (g["key"], g["ratio"])
                         for g in growth["items"][1:3])
        tail = ("另外，%s。" % extra) if extra else ""
        notes["t%d" % growth["rank"]] = {
            "narration": "再看异常增长。按总量缩放后，本周涨得最快的是 %s，出现 %d 篇，"
                         "是一周均值的 %.2f 倍。%s这是份额变化，不是绝对数量的偶然波动。"
                         % (first["key"], first["cur"], first["ratio"], tail)
        }
    else:
        notes["t%d" % growth["rank"]] = {
            "narration": "最后看异常增长。本周没有达到门槛的方向：所有主题的份额"
                         "与上周相比都在正常波动范围内，没有值得单独点出的突变。"
        }
    notes["_outro"] = {"narration": "每周日上午十点更新，我们下周见。"}
    return notes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成周报视频的分段数据与旁白稿")
    ap.add_argument("-d", "--date", help="期号 YYYYMMDD；默认最新一期")
    ap.add_argument("--k", type=int, default=TOPICS_DEFAULT, help="主题段数（默认 6）")
    ap.add_argument("--data", default=None, help="周报 JSON；默认 trend_archive/<期号>.json")
    ap.add_argument("--out", default=os.path.join(REEL, "trend.json"))
    ap.add_argument("--notes", default=os.path.join(OUT, "trend_notes.json"))
    args = ap.parse_args(argv)

    issue = (args.date or "").strip() or latest_issue()
    if not issue:
        print("[err] 找不到周报数据：先跑 trend_report.py", file=sys.stderr)
        return 2
    path = args.data or os.path.join(ARCHIVE, "%s.json" % issue)
    data = load(path, None)
    if not data:
        print("[err] 读不到 %s" % path, file=sys.stderr)
        return 2

    segs = pick_segments(data, max(1, args.k))
    doc = {
        "issue": data.get("issue") or issue,
        "window": data.get("window") or {},
        "generated": data.get("generated_at") or "",
        "stats": {
            "total": data.get("total") or 0,
            "cats": len(data.get("categories") or []),
            "clusters": len(data.get("clusters") or []),
            "growth": len(data.get("growth_up") or []),
        },
        "segments": segs,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with io.open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)

    notes = build_notes(data, segs)
    with io.open(args.notes, "w", encoding="utf-8") as fh:
        json.dump(notes, fh, ensure_ascii=False, indent=1)

    print("[ok] %s" % args.out)
    print("     %s ｜ %d 段（%d 主题 + 1 增长）｜ 成片约 %.1f 秒"
          % (doc["issue"], len(segs), len(segs) - 1, 5 + len(segs) * SEGMENT_SEC + 5))
    for s in segs:
        if s["kind"] == "topic":
            print("     #%d %-18s %4d 篇 %5.1f%%  %s"
                  % (s["rank"], s["label"], s["count"], s["share"] * 100,
                     "、".join(s["terms"][:4])))
        else:
            keys = "、".join("%s×%.2f" % (g["key"], g["ratio"]) for g in s["items"]) or "无显著增长"
            print("     #%d %-18s %s" % (s["rank"], "异常增长", keys))
    print("[ok] 旁白稿 %s（%d 段）" % (args.notes, len(notes) - 2 + 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
