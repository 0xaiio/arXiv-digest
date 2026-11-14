#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一期的成品按日期归档到 `output/episodes/<YYYYMMDD>/`。

为什么需要
----------
定时任务每跑一次就覆盖同名文件：`reel/src/papers.json`、`output/video_notes.json`、
`reel/src/audio.json`、`reel/public/audio/*.mp3` 都不带期号 —— 第二天一跑，
第一天「讲了哪 10 篇、配了什么解说、用了什么音频」的证据就没了。
`output/` 里已经积了 `video_notes.json.bak_20261114`、`video_notes.prev_20261030.json`
这类手工备份，就是这件事反复发生的证据。

归档规则
--------
1. **目录**：`output/episodes/<YYYYMMDD>/`，每期一个，跨日互不覆盖；
2. **同期重跑**：内容相同 → 跳过；内容变了 → 旧文件移到 `<date>/history/<时间>/`，
   绝不删除（重渲染、改标题都留痕，能回答「上一版是什么样」）；
3. **跨期累积库不归档**：`summaries.json` 是 900+ 条的共享库，不属于任何一期；
4. **共享文件先验期号**：`papers.json` / `video_notes.json` / `audio.*` 以
   `papers.json` 的 `issue` 为锚，期号不匹配就跳过 —— 宁可不存，也不把今天的数据
   塞进昨天的文件夹；
5. **写清单**：每次归档写 `MANIFEST.json`（大小 / sha256 / 来源 / 缺失项 / 历史版本），
   便于事后核对「这一期到底存了什么」。

用法::

    python tools/snapshot_episode.py                  # 最新一期
    python tools/snapshot_episode.py -d 20261114
    python tools/snapshot_episode.py -d 20261114 --link   # 同盘硬链接，不额外占空间
    python tools/snapshot_episode.py --skip-video         # 只存文案与元数据
    python tools/snapshot_episode.py --json

退出码：0 已归档（含「全部已是最新」）/ 2 没有任何可归档的产物。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
EPISODES = OUT / "episodes"
REEL = ROOT / "reel"

# 单期必备产物：缺了也照样归档（流水线可能只跑到一半），但会在清单里记一笔。
REQUIRED = ("digest.html", "video.mp4")

# 与期次一一对应、文件名已带期号的产物：直接映射到目录内的短名。
DATED = (
    ("digest.html", "arxiv_digest_%s.html"),
    ("digest.md", "arxiv_digest_%s.md"),
    ("video.mp4", "arxiv_weekly_%s.mp4"),
    ("meta.json", "bili_meta_%s.json"),
    ("cover.jpg", "bili_cover_%s.jpg"),
    ("cover.json", "bili_cover_%s.json"),
    ("comment.txt", "bili_comment_%s.txt"),
    ("published.json", "bili_published_%s.json"),
)

# 不带期号、每次运行都会被覆盖的共享产物 —— 正是本脚本要抢救的部分。
# 不带期号、每次运行都会被覆盖的共享产物 —— 正是本脚本要抢救的部分。
# 注意：路径在 build_plan() 里按当前的 REEL/OUT 现算，不在导入时固化，
# 否则测试把根目录指到沙箱后仍然会读到真实 output/。
SHARED_NAMES = ("papers.json", "video_notes.json", "audio.json")


def _shared_paths():
    return (
        ("papers.json", REEL / "src" / "papers.json"),
        ("video_notes.json", OUT / "video_notes.json"),
        ("audio.json", REEL / "src" / "audio.json"),
    )


# ---------------------------------------------------------------- 基础工具
def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def latest_issue() -> str | None:
    """没有显式 `-d` 时，从已有产物里推最新一期。

    三种产物都要看：流水线可能停在渲染前（只有 meta）或停在投稿前（只有视频）。
    """
    best, best_mtime = None, -1.0
    for pattern in ("arxiv_weekly_*.mp4", "arxiv_digest_*.html", "bili_meta_*.json"):
        for p in OUT.glob(pattern):
            m = re.search(r"(\d{8})", p.name)
            if not m:
                continue
            if p.stat().st_mtime > best_mtime:
                best, best_mtime = m.group(1), p.stat().st_mtime
    return best


def normalize_issue(text: str) -> str:
    digits = re.sub(r"\D", "", str(text or ""))
    return digits


# ---------------------------------------------------------------- 归档计划
def build_plan(issue: str, skip_video: bool = False):
    """算出 `[(源文件, 目录内相对路径)]`，并说明哪些没找到 / 被跳过。"""
    items, missing, skipped = [], [], []
    for dest_name, pattern in DATED:
        if skip_video and dest_name == "video.mp4":
            skipped.append("video.mp4：--skip-video")
            continue
        src = OUT / (pattern % issue)
        if src.is_file():
            items.append((src, dest_name))
        elif dest_name in REQUIRED:
            missing.append(dest_name)

    papers = REEL / "src" / "papers.json"
    data = read_json(papers) if papers.is_file() else None
    if not data:
        skipped.append("papers.json / video_notes.json / audio：没有当期论文数据")
        return items, missing, skipped
    owner = str(data.get("issue") or "")
    if owner != issue:
        # 关键防错：共享文件是「当前那一期」的，不能塞进别的日期。
        skipped.append("papers.json / video_notes.json / audio：数据期号是 %s，与 %s 不符"
                       % (owner or "未知", issue))
        return items, missing, skipped

    for dest_name, src in _shared_paths():
        if src.is_file():
            items.append((src, dest_name))
        else:
            skipped.append("%s：源文件不存在" % dest_name)
    audio_dir = REEL / "public" / "audio"
    if audio_dir.is_dir():
        for mp3 in sorted(audio_dir.glob("*.mp3")):
            items.append((mp3, "audio/" + mp3.name))
    else:
        skipped.append("audio/：目录不存在")
    return items, missing, skipped


# ---------------------------------------------------------------- 落盘
def _place(src: Path, dest: Path, ep_dir: Path, stamp: str, link: bool,
           history: list[str]) -> str:
    """把 src 放到 dest；同路径不同内容时先把旧版本收进 history。"""
    if dest.is_file():
        if sha256(dest) == sha256(src):
            return "same"
        rel = dest.relative_to(ep_dir)
        old = ep_dir / "history" / stamp / rel
        old.parent.mkdir(parents=True, exist_ok=True)
        os.replace(dest, old)
        history.append(str(old.relative_to(ep_dir)).replace("\\", "/"))

    dest.parent.mkdir(parents=True, exist_ok=True)
    if link:
        try:
            os.link(src, dest)
            return "linked"
        except OSError:
            pass  # 跨卷 / 文件系统不支持硬链接 → 退回复制
    shutil.copy2(src, dest)
    return "copied"


def snapshot(issue: str, skip_video: bool = False, link: bool = False,
             dry_run: bool = False) -> dict:
    ep_dir = EPISODES / issue
    items, missing, skipped = build_plan(issue, skip_video=skip_video)
    if not items:
        return {"issue": issue, "ok": False, "reason": "没有任何可归档的产物",
                "missing": missing, "skipped": skipped, "files": [], "history": []}

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    files, history, actions = [], [], {}
    for src, rel in items:
        dest = ep_dir / rel
        if dry_run:
            actions[rel] = "would-copy"
            continue
        action = _place(src, dest, ep_dir, stamp, link, history)
        actions[rel] = action
        if action != "same":
            files.append({
                "name": rel,
                "bytes": dest.stat().st_size,
                "sha256": sha256(dest),
                "source": str(src.relative_to(ROOT)).replace("\\", "/"),
            })

    manifest_path = ep_dir / "MANIFEST.json"
    prev = read_json(manifest_path) if manifest_path.is_file() else None
    changed = bool(files) or (prev is None)
    revision = int((prev or {}).get("revision") or 0) + (1 if changed else 0)
    manifest = {
        "issue": issue,
        "snapshot_at": dt.datetime.now().isoformat(timespec="seconds"),
        "revision": max(1, revision),
        "files": files if changed else (prev or {}).get("files", []),
        "missing": missing,
        "skipped": skipped,
        "history": sorted(set(((prev or {}).get("history") or []) + history)),
    }
    if not dry_run:
        ep_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    return {
        "issue": issue, "ok": True, "dir": str(ep_dir),
        "copied": files, "actions": actions, "missing": missing,
        "skipped": skipped, "manifest": manifest,
    }


# ---------------------------------------------------------------- 入口
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="把一期的成品按日期归档到 output/episodes/")
    ap.add_argument("-d", "--date", help="期号 YYYYMMDD；默认取最新一期")
    ap.add_argument("--skip-video", action="store_true", help="不归档 mp4（省空间）")
    ap.add_argument("--link", action="store_true", help="同盘用硬链接代替复制")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不落盘")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    ap.add_argument("--quiet", action="store_true", help="只打印结论")
    args = ap.parse_args(argv)

    issue = normalize_issue(args.date) or latest_issue()
    if not issue:
        print("[FAIL] 找不到任何带期号的产物（arxiv_weekly_*.mp4 / bili_meta_*.json）",
              file=sys.stderr)
        return 2
    if not re.fullmatch(r"\d{8}", issue):
        print("[FAIL] 期号必须是 8 位数字：%s" % issue, file=sys.stderr)
        return 2

    res = snapshot(issue, skip_video=args.skip_video, link=args.link, dry_run=args.dry_run)
    if args.json:
        # JSON 模式只输出一个 JSON 文档：再追加一行摘要会让调用方解析失败。
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if res["ok"] else 2
    if res["ok"] and not args.quiet:
        print("== 归档 %s → %s ==" % (issue, res["dir"]))
        for name, action in sorted(res["actions"].items()):
            print("  %-16s %s" % (name, {"copied": "已复制", "linked": "硬链接",
                                         "same": "未变化", "would-copy": "将复制"}[action]))
        if res["missing"]:
            print("[warn] 缺少必备产物：%s" % "、".join(res["missing"]))
        for note in res["skipped"]:
            print("[skip] %s" % note)
    if not res["ok"]:
        print("[FAIL] %s：%s" % (issue, res["reason"]), file=sys.stderr)
        return 2

    changed = sum(1 for a in res["actions"].values() if a in ("copied", "linked"))
    if args.dry_run:
        print("[ok] 期号 %s · 计划归档 %d 个文件（未落盘）" % (issue, len(res["actions"])))
        return 0
    print("[ok] 期号 %s · %d 个文件（本次更新 %d）· 修订 %s"
          % (issue, len(res["manifest"]["files"]), changed,
             res["manifest"].get("revision")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
