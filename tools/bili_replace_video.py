#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把已发布稿件的视频源换成新渲染的成片（保留 BV 号与评论）。

B站没有公开的「换源」API：`/x/vu/web/edit` 只能改元数据，官方文档明确写
「不允许更改视频本身」。创作中心网页端的「更换视频」走的是同一路径，但把
`videos[].filename` 指向新上传的文件、`cid` 仍用原来的分 P —— 服务端据此重转码。
本脚本复刻这条链路：

1. 用 `bilibili_api.video_uploader` 上传分 P（`_upload_page` 只上传、不投稿），
   拿到新的 filename；
2. 上传封面拿到新 URL；
3. POST `/x/vu/web/edit`，videos = [{filename: 新, cid: 旧, ...}]；
4. 轮询公开 view 接口，确认时长变了才算成功。

默认 dry-run；`--exec` 才真的改线上稿件。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".workbuddy" / "skills" / "bili-auto-upload" / "scripts"))
import bili_upload as B  # noqa: E402

from bilibili_api import video_uploader as V  # noqa: E402
from bilibili_api.utils.network import Credential  # noqa: E402
from bilibili_api.utils.picture import Picture  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def session(jar: dict) -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.headers.update({
        "User-Agent": UA,
        "Referer": "https://member.bilibili.com/platform/upload-manager/article",
    })
    s.cookies.update(jar)
    return s


def public_view(bvid: str) -> dict:
    """公开接口要带 Referer，否则 B 站风控直接 412。"""
    r = requests.get("https://api.bilibili.com/x/web-interface/view",
                     params={"bvid": bvid}, timeout=20,
                     headers={"User-Agent": UA,
                              "Referer": "https://www.bilibili.com/video/%s" % bvid})
    r.raise_for_status()
    return r.json()


def part_info(bvid: str) -> dict:
    r = requests.get("https://api.bilibili.com/x/player/pagelist",
                     params={"bvid": bvid}, timeout=20,
                     headers={"User-Agent": UA,
                              "Referer": "https://www.bilibili.com/video/%s" % bvid})
    r.raise_for_status()
    return (r.json().get("data") or [{}])[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="替换已发布稿件的视频源（保留 BV 号）")
    ap.add_argument("-d", "--date", default="20261115")
    ap.add_argument("--exec", action="store_true", help="真正修改线上稿件")
    ap.add_argument("--cid-mode", choices=["old", "new"], default="old",
                    help="videos[].cid 用旧分 P（默认）还是新上传的 cid")
    args = ap.parse_args(argv)

    meta = json.loads((ROOT / "output" / ("bili_trend_meta_%s.json" % args.date))
                      .read_text(encoding="utf-8"))
    pub = json.loads((ROOT / "output" / ("bili_trend_published_%s.json" % args.date))
                     .read_text(encoding="utf-8"))
    bvid = pub["bvid"]

    view = public_view(bvid)
    if view.get("code") != 0:
        print("[err] 读不到稿件：%s" % view.get("message"))
        return 2
    data = view["data"]
    aid = data["aid"]
    old_cid = data["pages"][0]["cid"]
    old_part = part_info(bvid).get("part") or Path(meta["video"]).stem
    print("稿件 %s · aid=%s · 当前时长 %ss · cid=%s" % (bvid, aid, data["duration"], old_cid))
    print("目标标题：%s" % meta["title"])
    print("新视频：%s（%.1f MB）"
          % (Path(meta["video"]).name, Path(meta["video"]).stat().st_size / 1024 / 1024))

    if not args.exec:
        print("\n[dry-run] 将执行：上传分P → 上传封面 → POST /x/vu/web/edit")
        print("          videos=[{filename:<新上传>, cid:%s}]" % (old_cid if args.cid_mode == "old" else "<新>"))
        return 0

    jar = B.load_cookie_jar()
    cred = Credential.from_cookies(jar)
    csrf = jar.get("bili_jct") or ""
    if not csrf:
        print("[err] cookie 里没有 bili_jct")
        return 2

    # 1) 封面
    print("\n[1/3] 上传封面 …")
    cover_url = asyncio.run(V.upload_cover(Picture().from_file(meta["cover"]), cred))
    print("      cover:", cover_url)

    # 2) 视频分 P（只上传，不投稿）
    print("[2/3] 上传视频分 P …（按带宽，约 1–3 分钟）")
    page = V.VideoUploaderPage(meta["video"], (meta.get("title") or "1")[:80], "")
    up_meta = {
        "title": meta["title"], "copyright": 1, "tid": int(meta["tid"]),
        "tag": meta["tags"], "desc": meta["desc"], "desc_format_id": 0,
        "dynamic": "", "interactive": 0, "no_reprint": 0,
        "subtitle": {"open": 0, "lan": ""}, "dolby": 0, "lossless_music": 0,
    }
    uploader = V.VideoUploader([page], up_meta, cred,
                               cover=Picture().from_file(meta["cover"]))
    # _upload_page 直接读 self.line["os"]；不传线路会 NoneType 崩。
    uploader.line = V.LINES_INFO[V.Lines.BDA2.value]
    res = asyncio.run(uploader._upload_page(page))
    print("      filename:", res.get("filename"), " new_cid:", res.get("cid"))

    # 3) 编辑稿件（换源）
    print("[3/3] 提交换源 …")
    payload = {
        "aid": aid,
        "copyright": 1,
        "videos": [{
            "filename": res["filename"],
            "title": (old_part or "1")[:80],
            "desc": "",
            "cid": old_cid if args.cid_mode == "old" else res.get("cid"),
        }],
        "title": meta["title"],
        "desc": meta["desc"],
        "cover": cover_url,
        "tag": meta["tags"],
        "tid": int(meta["tid"]),
        "desc_format_id": 0,
        "dynamic": "",
        "interactive": 0,
        "subtitle": {"open": 0, "lan": ""},
        "no_reprint": 0,
        "open_elec": 0,
    }
    # 先留一份旧的元数据，万一换源失败/需要回滚，标题封面还能还原
    backup = ROOT / "output" / ("bili_trend_backup_%s.json" % args.date)
    backup.write_text(json.dumps({
        "title": data.get("title"), "desc": data.get("desc"),
        "cover": data.get("pic"), "tag": data.get("tname"),
        "cid": old_cid, "duration": data.get("duration"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("      旧元数据备份 →", backup.name)

    s = session(jar)
    r = s.post("https://member.bilibili.com/x/vu/web/edit",
               params={"csrf": csrf}, json=payload, timeout=60)
    print("      HTTP", r.status_code, (r.text or "")[:300])
    try:
        body = r.json()
    except Exception:
        body = {}
    if body.get("code") not in (0, None):
        print("[err] 换源被拒：code=%s %s" % (body.get("code"), body.get("message")))
        return 1

    # 4) 轮询时长
    print("      等待转码（最多 10 分钟）…")
    for i in range(40):
        time.sleep(15)
        v = public_view(bvid).get("data") or {}
        dur = v.get("duration")
        state = (v.get("stat") or {}).get("now_rank")
        print("      +%ds 时长 %ss  state=%s" % ((i + 1) * 15, dur, v.get("state")))
        if dur and dur >= 180:
            print("[ok] 新成片已生效：%ss" % dur)
            return 0
    print("[warn] 10 分钟内未看到时长变化，去创作中心确认是否在转码")
    return 3


if __name__ == "__main__":
    sys.exit(main())
