#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把周报数据整理成 Remotion 需要的分段数据与中文旁白稿。

与日报视频的分工完全一致：
    日报  `gen_video_data.py`  读 recommend.json  → reel/src/papers.json（10 篇 × 20s）
    周报  本脚本              读 trend_archive/*.json → reel/src/trend.json
                              （1 段词云 + 7 段主题 + 1 段增长 × 20s）

为什么旁白是**模板生成**而不是手写：周报讲的是数字（篇数、占比、倍数），
每个数字都能从 JSON 里取到，模板句不会说错；日报要讲论文贡献，才必须人工/模型写。
任何一段旁白都能追溯到 `trend_archive/<期号>.json` 里的字段。

「最接近的三项工作」那三句小字默认由 `trend_analysis.brief_note()` 从标题里的
词典术语生成。想更准确时，把 `{"<sid>": "<一句中文>"}` 写进
`output/trend_related_notes.json`，脚本会用它覆盖自动结果（周报自动化就是这么做的）。

用法::

    python tools/gen_trend_video_data.py                 # 最新一期
    python tools/gen_trend_video_data.py -d 20261115 --k 7
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

# 7 个主题 + 1 段词云 + 1 段增长 = 9 段 × 20s + 片头尾 10s ≈ 190.6s，
# 越过「成片 ≥ 3 分钟」的下限。段长必须锁死 20s（与日报的 PAPER 一致），
# 靠段数凑时长，不能改节奏。
TOPICS_DEFAULT = 7
SEGMENT_SEC = 20
MIN_SECONDS = 180
MAX_TOPICS = 9


def estimate_seconds(n_segments: int) -> float:
    """成片时长的估算值（片头 5s + 每段 20s + 片尾 5s，另加 0.6s 转场）。"""
    return 10 + n_segments * SEGMENT_SEC + 0.6 if n_segments else 0.0


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
    """词云段 + 占比最高的 k 个主题簇 + 一段「增长」。"""
    clusters = sorted(data.get("clusters") or [], key=lambda c: -c.get("size", 0))[:k]
    # 每段都必须带 sid：gen_narration 用它去 trend_notes.json 里取旁白，
    # 缺了就退回 "第 N 个方向" 这种占位句，配音会整段错位（2026-11-16 踩过）。
    segs = [{"kind": "cloud", "rank": 1, "sid": "te1",
             "words": (data.get("cloud") or [])[:28]}]
    for i, c in enumerate(clusters, start=1):
        samples = []
        for s in (c.get("samples") or [])[:3]:
            samples.append({
                "sid": s.get("sid") or "",
                "title": s.get("title") or "",
                "short": s.get("short") or (s.get("title") or "")[:18],
                "note": s.get("note") or "",
            })
        segs.append({
            "kind": "topic",
            "rank": i,
            "sid": "t%d" % i,
            "label": c.get("label") or "主题",
            "terms": list(c.get("terms") or [])[:5],
            "term_weights": list(c.get("term_weights") or [])[:5],
            "count": c.get("size") or 0,
            "share": c.get("share") or 0.0,
            "samples": samples,
            # 兼容旧版只显示一篇的字段
            "sample": samples[0] if samples else {"sid": "", "title": ""},
        })
    growth = (data.get("growth_up") or [])[:4]
    segs.append({"kind": "growth", "rank": len(clusters) + 1,
                 "sid": "t%d" % (len(clusters) + 1), "items": growth})
    return segs


def apply_overrides(segs: list[dict], overrides: dict) -> int:
    """用人工/模型写好的说明覆盖自动结果，返回覆盖条数。"""
    n = 0
    for seg in segs:
        if seg.get("kind") != "topic":
            continue
        for s in seg.get("samples") or []:
            note = (overrides.get(s.get("sid") or "") or "").strip()
            if note and note != s.get("note"):
                s["note"] = note
                n += 1
    return n


def _pct(share: float) -> int:
    return int(round((share or 0) * 100))


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))


def _clip(text: str, n: int) -> str:
    """口播用的硬截断：不加省略号（念出来会变成「点点点」），英文按词边界切。"""
    text = (text or "").strip()
    if len(text) <= n:
        return text
    cut = text[:n]
    if " " in cut and not _has_cjk(cut):
        cut = cut.rsplit(" ", 1)[0]
    return cut


def _clip_tags(note: str, n: int) -> str:
    """按「 · 」整段丢弃，避免把「KV 缓存」截成「KV」。"""
    parts = [p.strip() for p in (note or "").split("·") if p.strip()]
    out = ""
    for part in parts:
        nxt = part if not out else out + " · " + part
        if len(nxt) > n:
            break
        out = nxt
    return out or (parts[0] if parts else "")


def _terms_text(terms: list[str], n: int = 2) -> str:
    picked = [t for t in (terms or []) if t][:n]
    return "、".join(picked) if picked else "暂无"


def build_notes(data: dict, segs: list[dict]) -> dict:
    """每段一句中文旁白，字数控制在 85–120 字（20 秒段的舒适区间）。"""
    notes = {}
    # 片头只有 5 秒（≈20 字）：窗口、篇数、分类数都在画面上，旁白不重复念数字，
    # 否则音频会压进第一个主题段，变成两段叠着说。
    notes["_intro"] = {"narration": "这一周，计算机科学在往哪走？"}

    cloud = next((s for s in segs if s["kind"] == "cloud"), {"rank": 1, "words": []})
    top_words = [w.get("text") or "" for w in cloud.get("words", [])[:5]]
    if top_words:
        notes["te%d" % cloud["rank"]] = {
            # 词云段要撑满 20 秒：太短会在段尾留 >3s 静音，被 A/V 闸门判失败。
            "narration": "先看高频词。字号越大，本周出现的论文越多：%s。"
                         "这些词横跨多个方向，说明热度并不集中在一处，而是分散在几条线上。"
                         % "、".join(top_words)
        }
    else:
        notes["te%d" % cloud["rank"]] = {
            "narration": "先看高频词。本周的术语分布比较分散，没有单个词占据明显优势。"
        }

    topics = [s for s in segs if s["kind"] == "topic"]
    for i, s in enumerate(topics):
        works = []
        for p in (s.get("samples") or [])[:3]:
            name = _clip(p.get("short") or "", 18)
            # 只剥明显的虚词尾巴；a / A 不能剥，会把 "Paper 1 A" 削成 "Paper 1"
            name = re.sub(r"\s+(?:the|of|for|is|and|with)$", "", name, flags=re.I)
            note = p.get("note") or ""
            # 纯英文说明不念：中文 TTS 读半句英文会打断节奏，画面里仍然显示。
            note = _clip_tags(note, 14) if _has_cjk(note) else ""
            if name and note:
                works.append("%s，%s" % (name, note))
            elif name or note:
                works.append(name or note)
        tail = ("三项最接近：" + "；".join(works) + "。") if works else ""
        head = "第%d个方向%s，%d 篇占 %d%%。" % (
            i + 1, s["label"], s.get("count") or 0, _pct(s.get("share") or 0))
        terms = _terms_text(s.get("terms"), 1)
        if terms and terms != "暂无":
            head += "代表词%s。" % terms
        text = head + tail
        if len(text) > 120:      # 20 秒段的硬预算：超了先砍代表词，再砍标点空转
            text = (head.replace("代表词%s。" % terms, "") + tail) if terms else text
        notes["t%d" % s["rank"]] = {"narration": text}

    growth = next((x for x in segs if x["kind"] == "growth"), {"rank": len(segs), "items": []})
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


def _cat_zh(cat: str) -> str:
    """分类中文名：直接读 trend_analysis 的表，避免两处维护。"""
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)      # 以 tools/ 为 sys.path[0] 运行时也能导入根模块
        import trend_analysis as TA
        return TA.CAT_ZH.get(cat, cat)
    except Exception:
        return cat


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成周报视频的分段数据与旁白稿")
    ap.add_argument("-d", "--date", help="期号 YYYYMMDD；默认最新一期")
    ap.add_argument("--k", type=int, default=TOPICS_DEFAULT,
                    help="主题段数（默认 7；+词云 +增长 = 9 段，成片 ≥ 3 分钟）")
    ap.add_argument("--data", default=None, help="周报 JSON；默认 trend_archive/<期号>.json")
    ap.add_argument("--out", default=os.path.join(REEL, "trend.json"))
    ap.add_argument("--notes", default=os.path.join(OUT, "trend_notes.json"))
    ap.add_argument("--related-notes", default=os.path.join(OUT, "trend_related_notes.json"),
                    help="可选：{sid: 一句中文说明}，覆盖自动生成的代表论文说明")
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

    segs = pick_segments(data, max(1, min(MAX_TOPICS, args.k)))
    overrides = load(args.related_notes, {}) or {}
    covered = apply_overrides(segs, overrides) if isinstance(overrides, dict) else 0

    cats = []
    for c in (data.get("categories") or [])[:6]:
        cats.append({"cat": c.get("cat") or "", "count": c.get("count") or 0,
                     "share": c.get("share") or 0.0,
                     "name": _cat_zh(c.get("cat") or "")})

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
        "categories": cats,
        "cloud": (data.get("cloud") or [])[:32],
        "segments": segs,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with io.open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)

    notes = build_notes(data, segs)
    with io.open(args.notes, "w", encoding="utf-8") as fh:
        json.dump(notes, fh, ensure_ascii=False, indent=1)

    est = estimate_seconds(len(segs))
    print("[ok] %s" % args.out)
    print("     %s ｜ %d 段（1 词云 + %d 主题 + 1 增长）｜ 成片约 %.1f 秒（下限 %d 秒）"
          % (doc["issue"], len(segs), len(segs) - 2, est, MIN_SECONDS))
    if est < MIN_SECONDS:
        # 主题簇不够时不缩短段长（会破坏与日报一致的节奏），而是明确报警：
        # 这种期次按 A/V 闸门的段数核对会直接失败，不会带着 150 秒的片子投出去。
        print("[warn] 成片约 %.1f 秒，低于 %d 秒下限：本期可用的主题簇只有 %d 个。"
              " 先看 trend_archive/%s.json 的 clusters 数量。"
              % (est, MIN_SECONDS, len(segs) - 2, doc["issue"]), file=sys.stderr)
    if covered:
        print("     代表论文说明：%d 条来自 %s" % (covered, os.path.basename(args.related_notes)))
    else:
        print("[warn] 没有 %s，代表论文说明使用词典自动生成（可能中英混排）"
              % os.path.basename(args.related_notes), file=sys.stderr)
    for s in segs:
        if s["kind"] == "cloud":
            print("     #%d %-18s %s" % (s["rank"], "本周高频词",
                                         "、".join(w["text"] for w in s["words"][:6])))
        elif s["kind"] == "topic":
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
