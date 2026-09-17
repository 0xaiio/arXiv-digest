#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RSS 增量抓取：export.arxiv.org 的 Atom API 被限流（429/503）时的降级通道。

arXiv 的分类 RSS（https://arxiv.org/rss/<cat>）与主站不同域、不限流，
给出该分类最近一次公告日的全部条目（new = 主分类，cross = 交叉列表）。
本脚本把 RSS 条目解析成与 raw.json 相同的结构，**增量合并**进已有的
raw.json / raw_expand.json（按短号去重，绝不删除既有论文）。

用法：
  python fetch_rss.py            # 抓核心六类 + 扩展分类，增量合并
  python fetch_rss.py --dry      # 只统计，不写盘
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paperutil as pu  # noqa: E402

OUT = pu.OUT
RSS = "https://arxiv.org/rss/%s"
NS = {"dc": "http://purl.org/dc/elements/1.1/",
      "arxiv": "http://arxiv.org/schemas/atom"}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def get(cat, retries=3):
    url = RSS % cat
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "arxiv-digest-rss/1.0"})
            with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            sys.stderr.write("rss retry %s %d: %s\n" % (cat, i, e))
            time.sleep(3)
    return ""


def parse(xml_text, feed_cat):
    out = []
    if not xml_text:
        return out
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:  # noqa
        sys.stderr.write("rss parse error %s: %s\n" % (feed_cat, e))
        return out
    ch = root.find("channel")
    if ch is None:
        return out
    for it in ch.findall("item"):
        title = " ".join((it.findtext("title") or "").split())
        link = (it.findtext("link") or "").strip()
        sid = pu.short_id(link)
        if not sid:
            continue
        desc = " ".join((it.findtext("description") or "").split())
        m = re.split(r"Abstract\s*:", desc, maxsplit=1)
        abstract = m[1].strip() if len(m) > 1 else ""
        creator = (it.find("{http://purl.org/dc/elements/1.1/}creator").text
                   if it.find("{http://purl.org/dc/elements/1.1/}creator") is not None else "")
        authors = [a.strip() for a in (creator or "").split(",") if a.strip()]
        cats = [c.text.strip() for c in it.findall("category") if c.text]
        ann = it.find("arxiv:announce_type", NS)
        ann = (ann.text or "").strip() if ann is not None else ""
        primary = feed_cat if (ann == "new" or not cats) else cats[0]
        if primary not in cats:
            cats = [primary] + cats
        pd = it.findtext("pubDate") or ""
        try:
            published = parsedate_to_datetime(pd).astimezone(timezone.utc) \
                .strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            published = ""
        out.append({
            "id": "http://arxiv.org/abs/%s" % sid,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "published": published,
            "updated": published,
            "primary": primary,
            "cats": cats,
            "pdf": "https://arxiv.org/pdf/%s" % sid,
            "comment": "",
            "queried_cat": feed_cat,
            "_source": "rss",
        })
    return out


def load(path):
    if os.path.exists(path):
        try:
            d = json.load(open(path, encoding="utf-8"))
            if isinstance(d, dict) and d.get("papers"):
                return d
        except Exception:
            pass
    return None


def merge(doc, new_papers, label):
    """按短号去重合并；已有条目保持不变（RSS 只补缺失字段，不覆盖既有数据）。"""
    papers = doc.get("papers", []) if doc else []
    idx = {pu.short_id(p): p for p in papers}
    added, enriched = 0, 0
    for p in new_papers:
        sid = pu.short_id(p)
        old = idx.get(sid)
        if old is None:
            idx[sid] = p
            added += 1
        else:
            # 既有条目若来自恢复流程可能缺字段，RSS 只补空值
            touched = False
            for k in ("abstract", "authors", "comment"):
                if not old.get(k) and p.get(k):
                    old[k] = p[k]
                    touched = True
            if touched:
                enriched += 1
    papers = list(idx.values())
    papers.sort(key=lambda x: x.get("published", ""), reverse=True)

    days = [x["published"][:10] for x in papers if x.get("published")]
    newest = max(days) if days else ""
    window = int(pu.load_config().get("window_days", 3))
    if newest:
        cutoff = (datetime.strptime(newest, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                  - timedelta(days=window)).isoformat()
    else:
        cutoff = ""

    doc = doc or {}
    doc.update({
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "newest_seen": (newest + "T00:00:00Z") if newest else "",
        "cutoff": cutoff,
        "window_days": window,
        "total_before_filter": len(papers),
        "papers": papers,
    })
    print("  %-16s +%d 新增 / %d 补全 -> 共 %d 篇（newest=%s）"
          % (label, added, enriched, len(papers), newest))
    return doc, added


def main():
    dry = "--dry" in sys.argv
    cfg = pu.load_config()
    core_cats = cfg["categories"]
    exp_cats = [c for c in cfg.get("expand_categories", []) if c not in core_cats]

    raw_path = os.path.join(OUT, "raw.json")
    exp_path = os.path.join(OUT, "raw_expand.json")

    print("fetching RSS (core=%d, expand=%d) ..." % (len(core_cats), len(exp_cats)))
    core_new, exp_new = [], []
    for cat in core_cats:
        items = parse(get(cat), cat)
        print("  rss %-8s %2d 条" % (cat, len(items)))
        core_new.extend(items)
        time.sleep(0.6)
    seen_core = {pu.short_id(p) for p in core_new}
    for cat in exp_cats:
        items = parse(get(cat), cat)
        items = [p for p in items
                 if p["primary"] not in core_cats and pu.short_id(p) not in seen_core]
        print("  rss %-8s %2d 条" % (cat, len(items)))
        exp_new.extend(items)
        time.sleep(0.6)

    raw_doc = load(raw_path) or {"papers": []}
    exp_doc = load(exp_path) or {"papers": []}
    raw_doc, a1 = merge(raw_doc, core_new, "raw.json")
    exp_doc, a2 = merge(exp_doc, exp_new, "raw_expand.json")

    if dry:
        print("\n（干跑）未写盘；新增 %d 篇" % (a1 + a2))
        return
    for path, doc in ((raw_path, raw_doc), (exp_path, exp_doc)):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    print("written: raw.json / raw_expand.json")


if __name__ == "__main__":
    main()
