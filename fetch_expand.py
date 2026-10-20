#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取「兴趣扩展」候选：用户主分类之外的相邻分类新论文。

「相邻」的定义不再写死成一串 cs.xx（那会让选了 math / q-bio 的用户拿到完全不相干
的扩展池）。默认取**同一 archive 内的兄弟分类**（见 arxiv_cats.neighbors）：
选 cs.DB → 扩展池是其余 cs.*；选 math.LO → 扩展池是其余 math.*。
config.json 的 `expand_categories` 非空时以它为准（显式覆盖优先）。

一次组合查询拿全部分类，写入 output/raw_expand.json（结构与 raw.json 一致，
但 queried_cat 记为 "expand"，primary 保留 arXiv 给出的主分类）。
"""
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import arxiv_cats  # noqa: E402
import paperutil as pu  # noqa: E402


def expand_pool(cfg):
    """扩展候选分类：显式配置优先，否则按 archive 推导兄弟分类。

    抽成函数而不是只留常量，是为了让「推导规则」可被单测直接验证，
    也避免 import 期就读一次配置（测试重定向配置路径后才生效）。
    """
    explicit = [c for c in (cfg.get("expand_categories") or []) if c]
    if explicit:
        return explicit
    return arxiv_cats.neighbors([c for c in (cfg.get("categories") or []) if c])


_cfg = pu.load_config()
EXPAND_CATS = expand_pool(_cfg)
CORE_CATS = set(_cfg["categories"])
API = "http://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
WINDOW_DAYS = int(_cfg.get("expand_window_days", _cfg.get("window_days", 3)))
MAX_RESULTS = int(_cfg.get("expand_max_results", 600))

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def build_query(cats, chunk=9):
    return ["(" + " OR ".join("cat:%s" % c for c in cats[i:i + chunk]) + ")"
            for i in range(0, len(cats), chunk)]


def fetch(query, start=0, max_results=MAX_RESULTS):
    params = {
        "search_query": query,
        "start": start,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "arxiv-digest/3.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            sys.stderr.write("retry %d (%s): %s\n" % (attempt, query[:40], e))
            time.sleep(4)
    return ""


def parse(xml_text):
    out = []
    if not xml_text:
        return out
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:  # noqa
        sys.stderr.write("parse error: %s\n" % e)
        return out
    for e in root.findall("a:entry", NS):
        def t(p):
            n = e.find(p, NS)
            return (n.text or "").strip() if n is not None else ""
        prim = e.find("arxiv:primary_category", NS)
        cats = [c.get("term") for c in e.findall("a:category", NS)]
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
            "published": t("a:published"),
            "updated": t("a:updated"),
            "primary": prim.get("term") if prim is not None else "",
            "cats": cats,
            "pdf": pdf,
            "comment": " ".join(t("arxiv:comment").split()),
            "queried_cat": "expand",
        })
    return out


def dt(s):
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def load_prev(path):
    """读既有累积池（raw_expand.json 同样是只增不删的池子）。"""
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return []
    return d.get("papers") or [] if isinstance(d, dict) else []


def merge_pool(fresh, prev):
    """按短号并集合并；只增不删（原因见 fetch_arxiv.py 同名函数的注释）。"""
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
    cats = [c for c in EXPAND_CATS if c not in CORE_CATS]
    seen, papers = set(), []
    for q in build_query(cats):
        sys.stderr.write("fetching expand: %s\n" % q[:80])
        for p in parse(fetch(q)):
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            papers.append(p)
        time.sleep(3.5)

    if not papers:
        print(json.dumps({"error": "no data"}, ensure_ascii=False))
        return

    # 时间窗与核心报告保持一致：优先复用 raw.json 的 newest_seen 作锚点
    anchor = None
    raw_path = os.path.join(pu.OUT, "raw.json")
    if os.path.exists(raw_path):
        try:
            raw = json.load(open(raw_path, encoding="utf-8"))
            anchor = dt(raw["newest_seen"])
        except Exception:
            anchor = None
    newest = max(dt(p["published"]) for p in papers)
    base = anchor or newest
    cutoff = base - timedelta(days=WINDOW_DAYS)
    recent = [p for p in papers if dt(p["published"]) >= cutoff]
    # 剔除主分类落在用户已跟踪分类里的（那些已经在主报告里了）
    recent = [p for p in recent if p["primary"] not in CORE_CATS]
    recent.sort(key=lambda p: dt(p["published"]), reverse=True)

    prev = load_prev(os.path.join(pu.OUT, "raw_expand.json"))
    if prev:
        recent, added = merge_pool(recent, prev)
        recent.sort(key=lambda p: dt(p["published"]), reverse=True)
        sys.stderr.write("merge pool: %d 既有 + 本次 -> %d 篇（新增 %d）\n"
                         % (len(prev), len(recent), added))

    print(json.dumps({
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "newest_seen": newest.isoformat(),
        "cutoff": cutoff.isoformat(),
        "window_days": WINDOW_DAYS,
        "categories": cats,
        "total_before_filter": len(papers),
        "papers": recent,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
