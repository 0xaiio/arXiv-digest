#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把旧下载目录（D:/git-paper/arXiv）里已下载的论文迁移到新目录
（D:/git-papers/arXiv）。

安全约束（严格遵守）：
  1. 源目录、目标目录下**任何**已有文件都不删除、不覆盖。
  2. 目标目录非空 —— 只做「增量合并」，遇到同名文件一律保留双方、跳过并告警。
  3. 迁移 = 同盘 rename（原子），随后逐文件核对 size + sha256，校验不过则回滚该文件。
  4. 全程留 manifest，写到 output/download_migration_<ts>.json 供审计。

用法：
  python tools/migrate_download_dir.py            # 干跑，只报告
  python tools/migrate_download_dir.py --apply    # 实际执行
"""

import os
import sys
import json
import time
import hashlib
import shutil

OLD = r"D:\git-paper\arXiv"
NEW = r"D:\git-papers\arXiv"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    apply = "--apply" in sys.argv

    if not os.path.isdir(OLD):
        print("源目录不存在：%s" % OLD)
        return 2
    if not os.path.isdir(NEW):
        print("目标目录不存在：%s" % NEW)
        return 2

    olds = sorted(os.listdir(OLD))
    newset = set(os.listdir(NEW))
    print("源 %s ：%d 个条目" % (OLD, len(olds)))
    print("目标 %s ：%d 个条目（迁移前）" % (NEW, len(newset)))
    print("模式：%s" % ("APPLY（实际执行）" if apply else "DRY-RUN（仅报告）"))
    print("-" * 72)

    moved, skipped, failed, planned = [], [], [], []
    for f in olds:
        src = os.path.join(OLD, f)
        if os.path.isdir(src):
            skipped.append({"name": f, "reason": "源目录中的子目录，跳过"})
            print("[SKIP-DIR] %s" % f)
            continue
        dst = os.path.join(NEW, f)
        if os.path.exists(dst):
            same = (
                os.path.getsize(src) == os.path.getsize(dst)
                and sha256(src) == sha256(dst)
            )
            skipped.append(
                {"name": f, "reason": "目标已同名文件" + ("（内容相同）" if same else "（内容不同）")}
            )
            print("[SKIP-COLLIDE] %s" % f)
            continue
        planned.append(f)
        if not apply:
            print("[PLAN] %-72s %d B" % (f[:72], os.path.getsize(src)))
            continue

        s_before = os.path.getsize(src)
        h_before = sha256(src)
        try:
            os.rename(src, dst)  # 同盘 => 原子
            s_after = os.path.getsize(dst)
            h_after = sha256(dst)
            if s_after == s_before and h_after == h_before:
                moved.append({"name": f, "size": s_after, "sha256": h_after})
                print("[MOVED] %-72s %d B verified" % (f[:72], s_after))
            else:
                # 校验失败：搬回去，绝不留下半个文件
                os.rename(dst, src)
                failed.append({"name": f, "reason": "校验不一致，已回滚"})
                print("[FAIL-VERIFY] %s 已回滚" % f)
        except Exception as e:  # noqa: BLE001
            failed.append({"name": f, "reason": str(e)})
            print("[FAIL] %s : %s" % (f, e))

    print("-" * 72)
    print("计划迁移 %d | 已迁移 %d | 跳过 %d | 失败 %d"
          % (len(planned), len(moved), len(skipped), len(failed)))

    # 迁移后：确认目标目录「原有文件一个不少」
    after = os.listdir(NEW)
    missing = sorted(newset - set(after))
    print("目标目录迁移后条目：%d（迁移前 %d）" % (len(after), len(newset)))
    print("目标目录原有文件丢失检查：%s" % ("全部完好" if not missing else missing))

    if apply:
        os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
        man = os.path.join(
            ROOT, "output", "download_migration_%s.json" % time.strftime("%Y%m%d_%H%M%S")
        )
        with open(man, "w", encoding="utf-8") as fp:
            json.dump(
                {
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "old": OLD,
                    "new": NEW,
                    "moved": moved,
                    "skipped": skipped,
                    "failed": failed,
                    "new_dir_before": len(newset),
                    "new_dir_after": len(after),
                    "missing_pre_existing": missing,
                },
                fp,
                ensure_ascii=False,
                indent=1,
            )
        print("manifest: %s" % man)

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
