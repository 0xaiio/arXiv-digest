#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch recent arXiv submissions for a set of cs.* categories and dump to JSON."""
import json
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paperutil as pu

_cfg = pu.load_config()
CATS = _cfg["categories"]
API = "http://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
WINDOW_DAYS = int(_cfg["window_days"])
MAX_RESULTS = int(_cfg.get("max_results_per_cat", 80))

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def fetch(cat, max_results=MAX_RESULTS):
    params = {
        "search_query": "cat:%s" % cat,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "arxiv-digest/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            sys.stderr.write("retry %s %s: %s\n" % (cat, attempt, e))
            time.sleep(4)
    return ""


def parse(xml_text, cat):
    out = []
    if not xml_text:
        return out
    root = ET.fromstring(xml_text)
    for e in root.findall("a:entry", NS):
        def t(p):
            n = e.find(p, NS)
            return (n.text or "").strip() if n is not None else ""
        published = t("a:published")
        cats = [c.get("term") for c in e.findall("a:category", NS)]
        prim = e.find("arxiv:primary_category", NS)
        pdf = ""
        for l in e.findall("a:link", NS):
            if l.get("title") == "pdf":
                pdf = l.get("href", "")
        out.append({
            "id": t("a:id"),
            "title": " ".join(t("a:title").split()),
            "abstract": " ".join(t("a:summary").split()),
            "authors": [a.find("a:name", NS).text.strip() for a in e.findall("a:author", NS)
                        if a.find("a:name", NS) is not None],
            "published": published,
            "updated": t("a:updated"),
            "primary": prim.get("term") if prim is not None else cat,
            "cats": cats,
            "pdf": pdf,
            "comment": " ".join(t("arxiv:comment").split()),
            "queried_cat": cat,
        })
    return out


def load_prev(path):
    """读既有累积池（raw.json 是只增不删的池子，不是「本次抓取结果」）。"""
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return []
    return d.get("papers") or [] if isinstance(d, dict) else []


def merge_pool(fresh, prev):
    """按短号把本次结果与既有池取并集，返回 (merged_list, added)。

    **为什么必须有这一步（2026-09-16 / 09-17 连续两次踩到）**：arXiv API 会整轮 429/503，
    六类里往往只有 1–2 类成功。此时本次结果「非空」→ run_daily 判定为有效 → 直接覆盖
    raw.json，未成功类别的论文被整批抹掉（09-17：416 篇被覆盖成 82 篇）。
    累积池语义下正确做法是并集合并：只增不删，新条目覆盖同短号的旧字段。
    """
    merged = {}
    for p in prev:
        merged[pu.short_id(p)] = p
    added = 0
    for p in fresh:
        k = pu.short_id(p)
        if k not in merged:
            added += 1
        merged[k] = p
    return list(merged.values()), added


def main():
    all_papers = {}
    for cat in CATS:
        sys.stderr.write("fetching %s ...\n" % cat)
        xml_text = fetch(cat)
        items = parse(xml_text, cat)
        for p in items:
            all_papers[p["id"]] = p
        time.sleep(3.5)

    papers = list(all_papers.values())
    if not papers:
        print(json.dumps({"error": "no data"}, ensure_ascii=False))
        return

    def dt(s):
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)

    newest = max(dt(p["published"]) for p in papers)
    cutoff = newest - timedelta(days=WINDOW_DAYS)
    recent = [p for p in papers if dt(p["published"]) >= cutoff]
    recent.sort(key=lambda p: dt(p["published"]), reverse=True)

    prev = load_prev(os.path.join(pu.OUT, "raw.json"))
    if prev:
        recent, added = merge_pool(recent, prev)
        recent.sort(key=lambda p: dt(p["published"]), reverse=True)
        sys.stderr.write("merge pool: %d 既有 + 本次 -> %d 篇（新增 %d）\n"
                         % (len(prev), len(recent), added))
    # 给每条补一份「抓取时所属分类」的快照字段。
    # 累积池里的老条目可能来自更早的版本或手工修复，未必带 primary —— 直接下标会
    # 让整轮抓取在 merge 之后崩掉（真实踩过：池子里有一条补录数据）。
    for p in recent:
        p["_primary"] = p.get("primary") or p.get("queried_cat") or ""
    print(json.dumps({
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "newest_seen": newest.isoformat(),
        "cutoff": cutoff.isoformat(),
        "window_days": WINDOW_DAYS,
        "categories": CATS,
        "total_before_filter": len(papers),
        "papers": recent,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
