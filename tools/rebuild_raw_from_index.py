#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 output/papers_index.json 抢救重建 output/raw.json / raw_expand.json。

背景：2026-09-12 一轮 arXiv API 全量 429，fetch_arxiv.py / fetch_expand.py 输出
{"error":"no data"}，run_daily.py 无保护地回写，把上一期真实数据清成了 22 字节。
papers_index.json（前端实时重排用，241 篇）保留了论文的 id/title/authors/
abstract/pdf/primary/cats/published，足以重建两份 feed。

用法：
  python tools/rebuild_raw_from_index.py            # 干跑，只报告
  python tools/rebuild_raw_from_index.py --apply    # 真正写盘（先备份现有文件）
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import paperutil as pu  # noqa: E402

OUT = pu.OUT
IDX = os.path.join(OUT, "papers_index.json")


def iso_day(d):
    """papers_index 里的 published 只到日，补成 arXiv 原始格式以便既有代码解析。"""
    return "%sT00:00:00Z" % d


def to_paper(p, queried_cat):
    sid = pu.short_id(p)
    return {
        "id": "http://arxiv.org/abs/%s" % sid,
        "title": p.get("title", ""),
        "abstract": p.get("abstract", ""),
        "authors": p.get("authors", []),
        "published": iso_day(p.get("published", "")),
        "updated": iso_day(p.get("published", "")),
        "primary": p.get("primary", ""),
        "cats": p.get("cats", []),
        "pdf": p.get("pdf", "") or ("https://arxiv.org/pdf/%s" % sid),
        "comment": "",
        "queried_cat": queried_cat,
    }


def dump(cfg, papers, queried_label, window_days):
    days = [p["published"][:10] for p in papers if p["published"]]
    newest = max(days) if days else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cutoff_dt = datetime.strptime(newest, "%Y-%m-%d").replace(tzinfo=timezone.utc) - \
        timedelta(days=int(window_days))
    return {
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "newest_seen": iso_day(newest),
        "cutoff": cutoff_dt.isoformat(),
        "window_days": int(window_days),
        "categories": cfg["categories"] if queried_label != "expand"
        else [c for c in cfg.get("expand_categories", []) if c not in cfg["categories"]],
        "total_before_filter": len(papers),
        "papers": sorted(papers, key=lambda p: p["published"], reverse=True),
        "_recovered_from": "papers_index.json",
    }


def main():
    apply = "--apply" in sys.argv
    cfg = pu.load_config()
    core_cats = set(cfg["categories"])
    idx = json.load(open(IDX, encoding="utf-8"))
    papers = idx.get("papers", [])
    expand_ids = set(idx.get("expand_ids", []))

    # 划分口径与 recommend.py 一致：在 expand_ids 里的属于「兴趣扩展」池
    core, exp = [], []
    for p in papers:
        sid = pu.short_id(p)
        if sid in expand_ids or (p.get("primary") not in core_cats and sid in expand_ids):
            exp.append(to_paper(p, "expand"))
        else:
            core.append(to_paper(p, p.get("primary") or cfg["categories"][0]))

    print("papers_index: %d 篇 -> 核心 %d / 扩展 %d" % (len(papers), len(core), len(exp)))
    plan = [("raw.json", dump(cfg, core, "core", cfg.get("window_days", 3))),
            ("raw_expand.json", dump(cfg, exp, "expand", cfg.get("expand_window_days",
                                                                 cfg.get("window_days", 3))))]
    for name, payload in plan:
        path = os.path.join(OUT, name)
        print("  %-16s %d 篇  (现有 %s)" % (name, len(payload["papers"]),
                                            "有效" if os.path.exists(path) and
                                            _ok(path) else "无效/缺失"))
        if not apply:
            continue
        if os.path.exists(path):
            bak = path + ".bad_%s" % time.strftime("%Y%m%d_%H%M%S")
            os.replace(path, bak)
            print("    备份现有文件 -> %s" % os.path.basename(bak))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print("    已写入 %s" % name)
    if not apply:
        print("\n（干跑）加 --apply 执行写盘")


def _ok(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
        return bool(d.get("papers")) and not d.get("error")
    except Exception:
        return False


if __name__ == "__main__":
    main()
