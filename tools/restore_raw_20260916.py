#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性修复：2026-09-16 fetch_arxiv 六类中只有 cs.SE 成功，其余五类 429，
因 run_daily「部分成功即视为有效」而把 281 篇的累积池覆盖成 58 篇（全 cs.SE），
且未触发 RSS 降级。本脚本把上一期备份的池子与本轮新抓到的条目按短号合并回来。

只增不删：以备份为底，本轮条目为补充，generated_at 设为今天（期号来源）。
"""
import json
import os
import shutil
import sys
from datetime import timedelta, timezone

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import paperutil as pu  # noqa: E402

OUT = pu.OUT
BAK = os.path.join(OUT, "raw.json.bak_20260915_115653")
CUR = os.path.join(OUT, "raw.json")


def main():
    base = json.load(open(BAK, encoding="utf-8"))
    cur = json.load(open(CUR, encoding="utf-8"))
    idx = {pu.short_id(p): p for p in base["papers"]}
    added = 0
    for p in cur["papers"]:
        sid = pu.short_id(p)
        if sid not in idx:
            idx[sid] = p
            added += 1
        else:
            for k in ("abstract", "authors", "comment"):
                if not idx[sid].get(k) and p.get(k):
                    idx[sid][k] = p[k]
    papers = list(idx.values())
    papers.sort(key=lambda x: x.get("published", ""), reverse=True)
    days = [x["published"][:10] for x in papers if x.get("published")]
    newest = max(days) if days else ""

    ts = pu._now() if hasattr(pu, "_now") else None
    now = ts or __import__("datetime").datetime.now(
        timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()

    shutil.copy2(CUR, CUR + ".bak_20260916_partial")
    base["papers"] = papers
    base["generated_at"] = str(now)
    base["newest_seen"] = (newest + "T00:00:00Z") if newest else ""
    base["total_before_filter"] = len(papers)
    base.pop("_recovered_from", None)
    base["_restored_from"] = "raw.json.bak_20260915_115653"
    with open(CUR + ".tmp", "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=1)
    os.replace(CUR + ".tmp", CUR)
    print("restored: %d (backup) + %d (this run) -> %d papers, newest=%s, generated_at=%s"
          % (len(base and json.load(open(BAK, encoding='utf-8'))["papers"]), added, len(papers), newest, now))


if __name__ == "__main__":
    main()
