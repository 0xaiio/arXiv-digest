#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出「待补写内容」的论文清单到 output/_pending.txt。

简介与摘要现在都是双语，缺口有三类，一次只导一类：

  中文简介（默认）  summaries.json 的 `zh` 为空
  英文简介 --en     summaries.json 的 `en` 为空（缺失时页面会用摘要开头兜底，
                    所以这是"补全质量"而不是"必须有"）
  中文摘要 --abs    abstracts_zh.json 里没有该短号的译文

格式：sid|分类|标题|摘要前 N 字符（英文原文），按推荐分数倒序。
用法：
  python tools/gen_pending.py            # 默认核心+扩展推荐池，前 620 字符
  python tools/gen_pending.py --all      # 全部核心论文（不限推荐位次）
  python tools/gen_pending.py --abs      # 缺中文摘要译文（--len 默认给全文长度）
  python tools/gen_pending.py --en       # 缺英文简介
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
    want_abs = "--abs" in args
    want_en = "--en" in args
    n = 1200 if want_abs else 620
    if "--len" in args:
        n = int(args[args.index("--len") + 1])

    summ = {}
    p = os.path.join(OUT, "summaries.json")
    if os.path.exists(p):
        try:
            summ = json.load(open(p, encoding="utf-8"))
        except Exception:
            summ = {}

    absz = {}
    pz = os.path.join(OUT, "abstracts_zh.json")
    if os.path.exists(pz):
        try:
            absz = json.load(open(pz, encoding="utf-8"))
        except Exception:
            absz = {}

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

    # 去重：同一篇可能同时出现在 raw.json 与 raw_expand.json（2026-09-18 踩到：
    # 15 行里只有 11 个不同 sid），不去重会让补写量被高估、且重复行误导分批。
    seen = set()
    uniq = []
    for t in pool:
        sid = pu.short_id(t[1])
        if sid in seen:
            continue
        seen.add(sid)
        uniq.append(t)

    def missing(x):
        """这一篇在**当前模式**下是否还缺内容。"""
        sid = pu.short_id(x)
        if want_abs:
            return not (absz.get(sid) or "").strip()
        en, zh = pu.split_bilingual(summ.get(sid) or "")
        return not en if want_en else not zh

    miss = [t for t in uniq if missing(t[1])]
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
    what = "中文摘要译文" if want_abs else ("英文简介" if want_en else "中文简介")
    have = len(absz) if want_abs else len(summ)
    print("pending(%s): %d 篇（池 %d 条/去重后 %d 篇，已有 %d）-> output/_pending.txt"
          % (what, len(miss), len(pool), len(uniq), have))


if __name__ == "__main__":
    main()
