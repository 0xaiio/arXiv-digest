#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把若干份 feed 快照按 arXiv 短号并集合并回累积池（raw.json / raw_expand.json）。

用途：arXiv API 整轮 429/503 时，run_daily 可能只拿到 1–2 个分类的结果就「有效」
     （papers 非空）并覆盖掉整个池子（2026-09-16、09-17 连续两次）。此时用本脚本
     把备份（或多份历史快照）与当前池子合并，恢复被抹掉的论文。

用法：
  python tools/merge_raw_pool.py raw.json output/raw.json.bak_xxx output/raw.json
  python tools/merge_raw_pool.py raw_expand.json a.json b.json c.json

约定：
  - 最后一个之前的参数都是 **输入**（可多份），合并结果写入 output/<第一个参数>。
  - 合并规则：按短号取并集，**只增不删**；后出现的输入覆盖先出现的同短号条目。
  - generated_at 设为当前时间（决定日报期号），其余头部字段取「条目数最多的那份」。
  - 合并前会先把现有目标文件备份为 `<target>.bak_<ts>`。
"""
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import paperutil as pu  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict) or not d.get("papers"):
        raise SystemExit("%s: 无 papers 字段，跳过合并" % path)
    return d


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    target_name = sys.argv[1]
    srcs = sys.argv[2:]
    target = os.path.join(pu.OUT, target_name)

    merged, order = {}, []
    head, head_n = {}, -1
    created = 0
    for s in srcs:
        p = s if os.path.isabs(s) or os.path.exists(s) else os.path.join(pu.OUT, s)
        d = load(p)
        if len(d["papers"]) > head_n:
            head, head_n = {k: v for k, v in d.items() if k != "papers"}, len(d["papers"])
        for it in d["papers"]:
            k = pu.short_id(it)
            if k not in merged:
                created += 1
                order.append(k)
            merged[k] = it
        print("  + %-46s %4d 篇 -> 累计 %d" % (os.path.basename(p), len(d["papers"]), len(merged)))

    papers = [merged[k] for k in order]
    if os.path.exists(target):
        shutil.copy2(target, "%s.bak_%s" % (target, time.strftime("%Y%m%d_%H%M%S")))

    head = dict(head)
    head["generated_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    head["total_before_filter"] = len(papers)
    head["merged_from"] = [os.path.basename(s) for s in srcs]
    head["papers"] = papers
    with open(target, "w", encoding="utf-8") as f:
        json.dump(head, f, ensure_ascii=False, indent=1)
    print("written: %s  (%d 篇，新增 %d)" % (target, len(papers), created))


if __name__ == "__main__":
    main()
