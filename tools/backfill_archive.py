#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 output/ 下已有的 arxiv_digest_<日期>.md/.html 回填进 archive.db。

功能上线（2026-09-14）之前的历史日报没有入库，只有磁盘上的 html/md 文件。
本脚本解析这些文件，补出「日期 -> 当期论文」的索引，于是 /archive 列表里
之前的每一天也能显示篇数与统计，点进去看的是当时那一版快照。

用法：
  python tools/backfill_archive.py            # 回填尚未入库的日期
  python tools/backfill_archive.py --dry      # 只报告，不写库
  python tools/backfill_archive.py --force    # 已有期次也覆盖（谨慎：会重写 issue_papers）
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import archive as AR  # noqa: E402
import paperutil as pu  # noqa: E402

OUT = pu.OUT

REC_RX = re.compile(r"^\d+\.\s+\*\*\[(?P<title>.*?)\]\((?P<pdf>.*?)\)\*\*\s+`(?P<sid>[^`]+)`\s*·\s*"
                    r"(?P<prim>[^·]+?)\s*·\s*(?P<pub>[^·]+?)(?:\s*·\s*(?P<score>[\d.]+)\s*分)?$")
CAT_RX = re.compile(r"^-\s+`(?P<sid>[^`]+)`\s+\*\*\[(?P<title>.*?)\]\((?P<pdf>.*?)\)\*\*\s*(?:—|--)\s*"
                    r"(?P<pub>[\d-]+)\s*·\s*(?P<authors>.*)$")
HEAD_RX = re.compile(r"共\s*(\d+)\s*篇")
COVER_RX = re.compile(r"^覆盖范围：(.+?)｜")


def parse_md(path):
    """返回 {recs:[...], papers:[...], n_total:int, cover:str}"""
    recs, papers, n_total, cover = [], [], 0, ""
    section = ""
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.rstrip("\n")
            if s.startswith("覆盖范围："):
                m = HEAD_RX.search(s)
                n_total = int(m.group(1)) if m else 0
                m2 = COVER_RX.search(s)
                cover = m2.group(1).strip() if m2 else ""
                continue
            if s.startswith("## "):
                section = s[3:].strip()
                continue
            if s.startswith("### "):
                section = "分类详解"
                m = re.match(r"^###\s+(\S+)\s", s)
                continue
            m = REC_RX.match(s)
            if m and ("推荐" in section or "扩展" in section or not section):
                recs.append({
                    "sid": m.group("sid"), "title": m.group("title"),
                    "pdf": m.group("pdf"), "primary": m.group("prim").strip(),
                    "published": m.group("pub").strip()[:10],
                    "score": float(m.group("score")) if m.group("score") else None,
                    "pool": "expand" if "扩展" in section else "core",
                })
                continue
            m = CAT_RX.match(s)
            if m:
                papers.append({
                    "sid": m.group("sid"), "title": m.group("title"), "pdf": m.group("pdf"),
                    "published": m.group("pub"), "authors": m.group("authors").strip(),
                    "pool": "core",
                })
    return {"recs": recs, "papers": papers, "n_total": n_total, "cover": cover}


def backfill(dry=False, force=False):
    known = {i["date"] for i in AR.list_issues()}
    mds = sorted(f for f in os.listdir(OUT)
                 if f.startswith("arxiv_digest_") and f.endswith(".md"))
    todo = []
    for f in mds:
        date = f[len("arxiv_digest_"):-len(".md")]
        if not (len(date) == 8 and date.isdigit()):
            continue
        if date in known and not force:
            print("skip %s（已入库）" % date)
            continue
        todo.append((date, f))

    if not todo:
        print("没有需要回填的日期。")
        return

    for date, f in todo:
        md_path = os.path.join(OUT, f)
        html_path = os.path.join(OUT, "arxiv_digest_%s.html" % date)
        info = parse_md(md_path)
        by_sid = {}
        for p in info["papers"]:
            by_sid[p["sid"]] = dict(p, is_new=1)
        for r in info["recs"]:
            cur = by_sid.get(r["sid"], {"sid": r["sid"], "title": r["title"],
                                        "pdf": r["pdf"], "primary": r["primary"],
                                        "published": r["published"], "authors": "",
                                        "pool": r["pool"], "is_new": 1})
            cur.update({"score": r["score"], "pool": r["pool"], "tier": "",
                        "title": r["title"], "primary": r["primary"],
                        "published": r["published"], "pdf": r["pdf"]})
            by_sid[r["sid"]] = cur
        n_papers = info["n_total"] or len(by_sid)
        n_rec = sum(1 for r in info["recs"] if r["pool"] == "core")
        n_exp = sum(1 for r in info["recs"] if r["pool"] == "expand")
        print("%s: 分类条目 %d / 推荐 %d / 扩展 %d / 头部计数 %d"
              % (date, len(info["papers"]), n_rec, n_exp, info["n_total"]))
        if dry:
            continue
        hname, mname = AR.archive_digest(date, html_path, md_path)
        AR.record_issue(date, html=hname, md=mname, generated_at="",
                        newest_seen=max([p["published"] for p in by_sid.values()] or [""]),
                        papers=list(by_sid.values()),
                        n_new=n_papers, n_core=n_papers, n_rec=n_rec, n_exp=n_exp)
        # 只把这些论文记为「已在 date 出现」；已有记录不覆盖（早先的日期更权威）
        AR.mark_seen(list(by_sid.keys()), date)

    print("\n完成：回填 %d 期%s" % (len(todo), "（干跑，未写库）" if dry else ""))
    print("stats:", AR.stats())


if __name__ == "__main__":
    backfill(dry="--dry" in sys.argv, force="--force" in sys.argv)
