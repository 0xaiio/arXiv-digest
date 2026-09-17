#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出「缺中文摘要」的论文清单到 output/_pending.txt。

格式：sid|分类|标题|摘要前 N 字符（英文原文），按推荐分数倒序。
用法：
  python tools/gen_pending.py            # 默认核心+扩展推荐池，前 620 字符
  python tools/gen_pending.py --all      # 全部核心论文（不限推荐位次）
  python tools/gen_pending.py --limit 80
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import paperutil as pu  # noqa: E402

OUT = pu.OUT


def main():
    args = sys.argv[1:]
    limit = 0
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    allp = "--all" in args
    n = 620
    if "--len" in args:
        n = int(args[args.index("--len") + 1])

    summ = {}
    p = os.path.join(OUT, "summaries.json")
    if os.path.exists(p):
        try:
            summ = json.load(open(p, encoding="utf-8"))
        except Exception:
            summ = {}

    pool = []
    for name in ("raw.json", "raw_expand.json"):
        fp = os.path.join(OUT, name)
        if not os.path.exists(fp):
            continue
        d = json.load(open(fp, encoding="utf-8"))
        for x in d.get("papers", []):
            pool.append((name, x))
    if not allp:
        keep = set()
        for name in ("recommend.json", "expand.json"):
            fp = os.path.join(OUT, name)
            if not os.path.exists(fp):
                continue
            try:
                for x in json.load(open(fp, encoding="utf-8")):
                    keep.add(pu.short_id(x))
            except Exception:
                pass
        pool = [t for t in pool if pu.short_id(t[1]) in keep]

    miss = [t for t in pool if pu.short_id(t[1]) not in summ or not summ.get(pu.short_id(t[1]))]
    if limit:
        miss = miss[:limit]

    lines = []
    for _, x in miss:
        sid = pu.short_id(x)
        lines.append("%s|%s|%s|%s" % (sid, x.get("primary", ""),
                                      " ".join((x.get("title") or "").split()),
                                      " ".join((x.get("abstract") or "").split())[:n]))
    with open(os.path.join(OUT, "_pending.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("pending: %d 篇（池 %d，已有摘要 %d）-> output/_pending.txt"
          % (len(miss), len(pool), len(summ)))


if __name__ == "__main__":
    main()
