#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性迁移：从旧版 arxiv_digest_20260910.md 中抽取「看点」与「跨领域主题」，
生成 output/highlights.json / output/themes.json（key 全部换成稳定的 arXiv 短号）。"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paperutil as pu

OUT = pu.OUT
md_path = os.path.join(OUT, "arxiv_digest_20260910.md")
if not os.path.exists(md_path):
    raise SystemExit("missing " + md_path)

d = json.load(open(os.path.join(OUT, "raw.json"), encoding="utf-8"))
groups = collections.defaultdict(list)
for p in d["papers"]:
    k = p["primary"] if p["primary"] in d["categories"] else p["queried_cat"]
    groups[k].append(p)
for k in groups:
    groups[k].sort(key=lambda p: p["published"], reverse=True)

key2sid, title2sid = {}, {}
for cat in d["categories"]:
    for i, p in enumerate(groups.get(cat, []), 1):
        key2sid["%s#%d" % (cat, i)] = pu.short_id(p)
        title2sid[p["title"].strip()] = pu.short_id(p)

text = open(md_path, encoding="utf-8").read()

# --- highlights: 「- **[Title](url)**」 后紧跟 「- **看点：** xxx」
highlights = {}
cur_title = None
for line in text.splitlines():
    m = re.match(r"- \*\*\[(.+?)\]\(", line)
    if m:
        cur_title = m.group(1).strip()
        continue
    m = re.match(r"\s+- \*\*看点：\*\*\s*(.+)", line)
    if m and cur_title and cur_title in title2sid:
        highlights[title2sid[cur_title]] = m.group(1).strip()
        cur_title = None

# --- themes
themes = []
for blk in text.split("### ")[1:]:
    lines = blk.splitlines()
    name = lines[0].strip()
    if not name or name.startswith("cs."):
        continue
    desc, refs = "", []
    for ln in lines[1:]:
        if ln.startswith("相关论文："):
            refs = [x for x in re.findall(r"`([^`]+)`", ln)]
        elif ln.strip() and not ln.startswith("- ") and not ln.startswith("**"):
            desc = (desc + " " + ln.strip()).strip()
    if not refs or not desc:
        continue
    themes.append({"name": name, "desc": desc,
                   "refs": [key2sid.get(r, r) for r in refs]})

json.dump(highlights, open(os.path.join(OUT, "highlights.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
json.dump(themes, open(os.path.join(OUT, "themes.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("highlights:", len(highlights), "themes:", len(themes))
for t in themes:
    print(" -", t["name"], t["refs"][:4])
