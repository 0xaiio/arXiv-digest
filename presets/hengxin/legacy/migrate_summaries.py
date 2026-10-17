#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性迁移：把 output/summaries.json 的 key 从「<分类>#<序号>」换成稳定的 arXiv 短号。

背景：build_report.py 里 `key = "<cat>#<序号>"` 是按「抓取当日分类内时间倒序」现算的，
     每天抓取窗口不同 => 同一 key 会指向不同论文，中文摘要会错配。
     本脚本用旧版 md（含 `sid` **[Title]…` 行）重建 sid -> 摘要 的映射，之后永久稳定。

幂等：已全部是短号 key 时直接退出。
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paperutil as pu

OUT = pu.OUT
SUM = os.path.join(OUT, "summaries.json")

SID_RE = re.compile(r"^\s*-\s+`([0-9]{4}\.[0-9]{4,5})(v\d+)?`\s+\*\*")
CAT_RE = re.compile(r"^###\s+(cs\.[A-Z]{2}|math\.[A-Z]{2})\b")
SKIP_RE = re.compile(r"^\s+-\s+\*\*(看点|推荐理由)[：:]")


def main():
    summaries = json.load(open(SUM, encoding="utf-8"))
    if all(re.fullmatch(r"[0-9]{4}\.[0-9]{4,5}", k) for k in summaries):
        print("already migrated (%d)" % len(summaries))
        return

    # 只用「今天之前」的 md：今天的 md 本身是用错配的 key 渲染的，不能当迁移依据
    import datetime
    today = datetime.date.today().strftime("%Y%m%d")
    mds = sorted(f for f in os.listdir(OUT)
                 if f.startswith("arxiv_digest_") and f.endswith(".md")
                 and not f.endswith(today + ".md"))
    if not mds:
        raise SystemExit("no digest md to migrate from")

    new = {}
    # 1) 直接从 md 抽取 sid -> 摘要（最可靠）
    cur_sid = None
    for name in mds:
        text = open(os.path.join(OUT, name), encoding="utf-8").read()
        for line in text.splitlines():
            m = SID_RE.match(line)
            if m:
                cur_sid = m.group(1)
                continue
            if cur_sid and line.startswith("  - ") and not SKIP_RE.match(line):
                body = line.strip()[2:].strip()
                if body and cur_sid not in new:
                    new[cur_sid] = body
                cur_sid = None
                continue
            if line.strip() and not line.startswith("  "):
                cur_sid = cur_sid if line.startswith("- `") else None

    # 2) 兜底：按 md 中的顺序把 "<cat>#<i>" 映射到 sid
    for name in mds:
        text = open(os.path.join(OUT, name), encoding="utf-8").read()
        cat, i = None, 0
        for line in text.splitlines():
            m = CAT_RE.match(line)
            if m:
                cat, i = m.group(1), 0
                continue
            m = SID_RE.match(line)
            if m and cat:
                i += 1
                k = "%s#%d" % (cat, i)
                if k in summaries and m.group(1) not in new:
                    new[m.group(1)] = summaries[k].strip()
                continue
            if line.startswith("## ") or line.startswith("# "):
                cat = None

    kept = {k: v for k, v in summaries.items()
            if re.fullmatch(r"[0-9]{4}\.[0-9]{4,5}", k)}
    kept.update(new)

    shutil.copyfile(SUM, SUM + ".bak")
    json.dump(kept, open(SUM, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("migrated %d -> %d sid-keyed summaries (backup: summaries.json.bak)"
          % (len(new), len(kept)))
    print("unmapped old keys:",
          len([k for k in summaries if "#" in k]) - len(new))


if __name__ == "__main__":
    main()
