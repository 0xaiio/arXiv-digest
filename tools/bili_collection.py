#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
arXiv-daily 视频 → B站 合集(season) 管理工具

合集在 B站 API 里叫 season。本工具负责：
  - 把已上传 + 将来上传的「arXiv 日报」视频归入名为 "arXiv-daily" 的合集。
  - 合集不存在时新建（建合集会触发人工审核，state -6）。

安全原则（与 bili_upload.py 一致）
  1. 默认只读 / dry-run：create / add / sync 必须显式 --exec 才产生对外副作用。
  2. 幂等：sync 会跳过已在合集内的视频，重复运行不会重复挂载。
  3. cookie 绝不入库。

关于 20080「当前稿件已存在在合集中」
  它是**整批级**拒绝：批次里只要有一条已在合集，整批都不挂。所以 add_episodes
  收到 20080 不能当整批成功，必须逐条重投；挂载完再用稿件详情（view 接口）
  回读校验，避免「报了成功其实没挂上」。

子命令
  videos       列出 member 稿件中匹配「arXiv 日报」前缀的视频（只读）
  collections  列出已有合集（只读）
  cover        生成本地封面 PNG 并上传到 B站图床，打印 URL（写图床，低风险）
  create       新建合集 "arXiv-daily"（需 --exec；会先生成并上传封面）
  add          把匹配视频加入合集（需 --exec；自动跳过已存在的，挂完回读校验）
  sync         create(若不存在) + add 所有未加入的匹配视频（需 --exec）

依赖：requests、PIL（仅 cover 需要）
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 绕开本机代理，避免回环/代理把请求拦成 502
import os

os.environ.setdefault("NO_PROXY", "bilibili.com,.bilibili.com,127.0.0.1,localhost")

from pathlib import Path

import requests

HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent  # tools → arXiv
SEC = ROOT / ".secrets"
COOKIE = SEC / "bili_cookies.json"
OUT = ROOT / "output"

COLLECTION_NAME = "arXiv-daily"
TITLE_PREFIX = "arXiv 日报"
COLLECTION_DESC = (
    "arXiv 日报视频合集：每期精选 DB·分布式·形式化方向 Top10 论文，"
    "20 秒中文速览（背景/方法/结果）。定期更新，欢迎追更。"
)

# ---------------------------------------------------------------- 日志
def ok(m): print(f"[ok]   {m}")
def warn(m): print(f"[warn] {m}")
def bad(m): print(f"[FAIL] {m}")
def info(m): print(f"       {m}")


def _is_pe(p):  # 占位，保持风格一致（本脚本不依赖 biliup）
    return Path(p).is_file()


# ---------------------------------------------------------------- cookie
def load_jar() -> dict:
    """兼容 biliup-rs LoginInfo 与扁平 dict。"""
    raw = COOKIE.read_text(encoding="utf-8", errors="replace").strip()
    j = json.loads(raw)
    if isinstance(j, dict) and isinstance(j.get("cookie_info"), dict):
        return {str(it["name"]): str(it["value"])
                for it in j["cookie_info"].get("cookies", []) if isinstance(it, dict)}
    if isinstance(j, dict):
        return {str(k): str(v) for k, v in j.items()}
    jar = {}
    if isinstance(j, list):
        for it in j:
            if isinstance(it, dict) and "name" in it:
                jar[str(it["name"])] = str(it["value"])
    return jar


def session() -> requests.Session:
    jar = load_jar()
    s = requests.Session()
    s.trust_env = False
    s.headers.update({
        "Cookie": "; ".join(f"{k}={v}" for k, v in jar.items()),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://member.bilibili.com/",
    })
    return s, jar


# ---------------------------------------------------------------- API
def list_archives(s: requests.Session) -> list:
    """翻页取全部稿件，返回 Archive 列表。"""
    out = []
    for pn in range(1, 8):
        r = s.get("https://member.bilibili.com/x/web/archives",
                  params={"pn": pn, "ps": 50}, timeout=20)
        j = r.json()
        if j.get("code") != 0:
            bad(f"member API 返回 code={j.get('code')} {j.get('message')}")
            break
        rows = (j.get("data") or {}).get("arc_audits") or []
        if not rows:
            break
        for row in rows:
            arc = row.get("Archive") or {}
            out.append(arc)
        if len(rows) < 50:
            break
    return out


def filter_arxiv(archives: list) -> list:
    return [a for a in archives if (a.get("title") or "").startswith(TITLE_PREFIX)]


def list_collections(s: requests.Session) -> list:
    r = s.get("https://member.bilibili.com/x2/creative/web/seasons",
              params={"pn": 1, "ps": 30}, timeout=20)
    j = r.json()
    if j.get("code") != 0:
        bad(f"seasons API code={j.get('code')} {j.get('message')}")
        return []
    return (j.get("data") or {}).get("seasons") or []


def find_collection(s: requests.Session, name: str):
    for sn in list_collections(s):
        if (sn.get("season") or {}).get("title", "").strip() == name:
            return sn
    return None


def collection_aids(sn: dict) -> set:
    return {int(ep["aid"]) for ep in (sn.get("part_episodes") or []) if ep.get("aid")}


def default_section_id(sn: dict):
    secs = (sn.get("sections") or {}).get("sections") or []
    if not secs:
        return None
    # 优先名为「正片」的小节
    for sec in secs:
        if (sec.get("title") or "") == "正片":
            return int(sec["id"])
    return int(secs[0]["id"])


def view_info(s: requests.Session, aid: int):
    """稿件详情（含 cid 与所属合集），失败返回 None。"""
    try:
        r = s.get("https://api.bilibili.com/x/web-interface/view",
                  params={"aid": aid}, timeout=20)
        j = r.json()
    except Exception:
        return None
    if j.get("code") != 0:
        return None
    return j.get("data") or None


def get_cid(s: requests.Session, aid: int) -> int | None:
    d = view_info(s, aid) or {}
    return d.get("cid")


def make_cover() -> Path:
    from PIL import Image, ImageDraw

    W, H = 1146, 717
    img = Image.new("RGB", (W, H), (17, 24, 39))
    d = ImageDraw.Draw(img)
    # 渐变感：画几层半透明矩形（简单近似）
    for i in range(0, W, 6):
        shade = int(17 + (i / W) * 20)
        d.rectangle([i, 0, i + 6, H], fill=(shade, shade + 8, shade + 24))
    try:
        fnt_big = ImageDraw.ImageFont.truetype("arial.ttf", 150)
        fnt_sm = ImageDraw.ImageFont.truetype("arial.ttf", 40)
    except Exception:
        fnt_big = ImageDraw.ImageFont.load_default()
        fnt_sm = ImageDraw.ImageFont.load_default()
    d.text((90, 250), "arXiv-daily", font=fnt_big, fill=(255, 255, 255))
    d.text((95, 430), "Daily arXiv Paper Reels", font=fnt_sm, fill=(148, 163, 184))
    d.text((95, 490), "DB . Distributed . Formal Methods  Top10", font=fnt_sm, fill=(148, 163, 184))
    p = OUT / "arxiv_daily_cover.jpg"
    p.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(p, "JPEG", quality=92)
    return p


def upload_cover(s: requests.Session, jar: dict, path: Path) -> str | None:
    import base64
    import time

    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    data_uri = "data:image/jpeg;base64," + b64
    r = s.post("https://member.bilibili.com/x/vu/web/cover/up",
               params={"ts": int(time.time() * 1000)},
               data={"csrf": jar.get("bili_jct"), "cover": data_uri},
               timeout=30)
    j = r.json()
    if j.get("code") != 0:
        bad(f"封面上传失败 code={j.get('code')} {j.get('message')}")
        return None
    url = (j.get("data") or {}).get("url")
    if url:
        ok(f"封面上传成功：{url}")
    return url


def create_collection(s: requests.Session, jar: dict, title: str, desc: str,
                      cover_url: str) -> int | None:
    csrf = jar.get("bili_jct")
    r = s.post("https://member.bilibili.com/x2/creative/web/season/add",
               data={"title": title, "desc": desc, "cover": cover_url,
                     "season_price": "0", "csrf": csrf},
               timeout=30)
    j = r.json()
    if j.get("code") != 0:
        bad(f"建合集失败 code={j.get('code')} {j.get('message')}")
        return None
    sid = j.get("data")
    ok(f"合集已创建：season_id={sid}（进入人工审核，state -6，审核通过后公开）")
    return sid


def season_of(s: requests.Session, aid: int):
    """回读稿件自身信息，返回它当前所属的合集 id（不在任何合集中返回 None）。

    这是**绕过合集列表缓存**的唯一可靠判据：member 的 seasons 接口给的是缓存快照，
    刚挂完或刚建完合集时可能看不到新条目；而稿件详情里的 season_id / ugc_season
    直接反映服务端真实归属。
    """
    d = view_info(s, aid) or {}
    sid = d.get("season_id") or ((d.get("ugc_season") or {}).get("id"))
    try:
        return int(sid) if sid else None
    except (TypeError, ValueError):
        return None


def _post_episodes(s: requests.Session, jar: dict, section_id: int, eps: list):
    """调一次挂载接口，返回 (code, message)。"""
    csrf = jar.get("bili_jct")
    r = s.post("https://member.bilibili.com/x2/creative/web/season/section/episodes/add",
               params={"csrf": csrf},
               json={"sectionId": section_id, "episodes": eps},
               headers={"Content-Type": "application/json"},
               timeout=30)
    j = r.json()
    return j.get("code"), j.get("message")



def add_episodes(s: requests.Session, jar: dict, section_id: int, eps: list) -> bool:
    """把一批视频挂进合集小节。

    20080「当前稿件已存在在合集中」是**整批级别**的拒绝，不是逐条报告：
    只要批次里有一条已在合集里，服务端就回 20080、整批都不挂。
    因此这里不能把 20080 当整批成功，而要逐条重投，让真正缺的那几条仍能挂上。
    """
    if not eps:
        return True
    code, msg = _post_episodes(s, jar, section_id, eps)
    if code == 0:
        ok(f"已挂载 {len(eps)} 个视频到 section {section_id}")
        return True
    if code != 20080:
        bad(f"挂载视频失败 code={code} {msg}")
        return False
    if len(eps) == 1:
        # 单条还回 20080 = 这一条确实已在合集里，幂等成功。
        info(f"视频已在合集中（20080，幂等跳过）：{eps[0].get('title')}")
        return True
    warn(f"批次里有视频已在合集中（20080），整批被拒；改为逐条重投 {len(eps)} 条")
    all_ok = True
    for ep in eps:
        c, m = _post_episodes(s, jar, section_id, [ep])
        if c == 0:
            ok(f"已挂载：{ep.get('title')}")
        elif c == 20080:
            info(f"已在合集中，跳过：{ep.get('title')}")
        else:
            bad(f"挂载失败 code={c} {m} | {ep.get('title')}")
            all_ok = False
    return all_ok


def verify_membership(s: requests.Session, season_id: int, eps: list) -> list:
    """挂载后回读校验（单次）：返回仍未归属该合集的条目。"""
    if not season_id:
        return []
    return [e for e in eps if season_of(s, int(e["aid"])) != season_id]


# 稿件详情接口也有 CDN 缓存：刚挂完立刻回读可能还看不到归属，
# 实测有数十秒级延迟，所以校验要重试而不是一次定生死。
VERIFY_ATTEMPTS = 5
VERIFY_DELAY_SEC = 3.0


def _sleep(seconds: float) -> None:  # 便于测试打桩
    time.sleep(seconds)


def verify_membership_settled(s: requests.Session, season_id: int, eps: list,
                              attempts: int = 0, delay: float = None) -> list:
    """回读校验，容忍缓存延迟：多轮重试后返回仍然缺失的条目。"""
    if not season_id or not eps:
        return []
    attempts = attempts or VERIFY_ATTEMPTS
    delay = VERIFY_DELAY_SEC if delay is None else delay
    missing = list(eps)
    for i in range(attempts):
        missing = verify_membership(s, season_id, eps)
        if not missing:
            return []
        if i < attempts - 1:
            _sleep(delay)
    return missing


def plan_episodes(s: requests.Session, arcs: list, have: set, season_id: int) -> list:
    """算出真正需要挂载的条目。

    先用合集列表快照 `have` 做快路跳过，再用稿件详情二次核对——
    列表有缓存，会出现「快照里没有、实际已在合集」的条目（每轮重复重投的根源）。
    """
    out = []
    for arc in arcs:
        aid = int(arc.get("aid") or 0)
        if not aid:
            continue
        if aid in have:
            info(f"已存在，跳过：{arc.get('bvid')} {arc.get('title')}")
            continue
        d = view_info(s, aid) or {}
        sid = d.get("season_id") or ((d.get("ugc_season") or {}).get("id"))
        try:
            real = int(sid) if sid else None
        except (TypeError, ValueError):
            real = None
        if season_id and real == season_id:
            info(f"已在合集中（按稿件信息核对），跳过：{arc.get('bvid')} {arc.get('title')}")
            continue
        cid = d.get("cid")
        if not cid:
            warn(f"取不到 cid，跳过：{arc.get('bvid')}")
            continue
        out.append({"title": arc.get("title"), "aid": aid, "cid": cid, "charging_pay": 0})
    return out


def season_id_of(sn: dict) -> int:
    """合集对象里的 season id（与 section id 不是一回事）。"""
    try:
        return int((sn.get("season") or {}).get("id") or 0)
    except (TypeError, ValueError):
        return 0



def cmd_videos(a):
    s, _ = session()
    arcs = filter_arxiv(list_archives(s))
    print(f"== 匹配「{TITLE_PREFIX}」的稿件共 {len(arcs)} 个 ==")
    for a in arcs:
        st = a.get("state")
        print(f"  bvid={a.get('bvid')} aid={a.get('aid')} state={st} | {a.get('title')}")
    return 0


def cmd_collections(a):
    s, _ = session()
    sns = list_collections(s)
    print(f"== 已有合集 {len(sns)} 个 ==")
    for sn in sns:
        sv = sn.get("season") or {}
        print(f"  id={sv.get('id')} ep={sv.get('ep_num')} state={sv.get('state')} | {sv.get('title')}")
    return 0


def cmd_cover(a):
    s, jar = session()
    p = make_cover()
    ok(f"本地封面 → {p}")
    url = upload_cover(s, jar, p)
    if url:
        info(f"图床 URL：{url}")
    return 0 if url else 1


def cmd_create(a):
    s, jar = session()
    if find_collection(s, COLLECTION_NAME):
        warn(f"合集「{COLLECTION_NAME}」已存在，跳过创建；建议改用 add / sync。")
        return 0
    if not a.exec:
        warn("dry-run：未真正创建。加 --exec 才执行。")
        return 0
    p = make_cover()
    url = upload_cover(s, jar, p)
    if not url:
        return 1
    sid = create_collection(s, jar, COLLECTION_NAME, COLLECTION_DESC, url)
    return 0 if sid else 1


def _finish_add(s, season_id: int, section_id: int, jar: dict, eps: list, do_exec: bool) -> int:
    """dry-run 预览 / 执行 + 回读校验，cmd_add 与 cmd_sync 共用。"""
    if not eps:
        ok("没有需要新增挂载的视频。")
        return 0
    print(f"== 待挂载 {len(eps)} 个视频到合集「{COLLECTION_NAME}」==")
    for e in eps:
        print(f"  aid={e['aid']} cid={e['cid']} | {e['title']}")
    if not do_exec:
        warn("dry-run：未真正挂载。加 --exec 才执行。")
        return 0
    added = add_episodes(s, jar, section_id, eps)
    missing = verify_membership_settled(s, season_id, eps)
    if missing:
        for e in missing:
            bad(f"仍不在合集 season {season_id} 内：{e['title']}（aid={e['aid']}）")
        return 1
    ok(f"回读校验通过：{len(eps)} 个视频均已在合集 season {season_id} 内")
    return 0 if added else 1


def cmd_add(a):
    s, jar = session()
    sn = find_collection(s, COLLECTION_NAME)
    if not sn:
        bad(f"未找到合集「{COLLECTION_NAME}」。先跑 create --exec。")
        return 1
    section_id = default_section_id(sn)
    if not section_id:
        bad("合集没有可用小节（section）。")
        return 1
    season_id = season_id_of(sn)
    eps = plan_episodes(s, filter_arxiv(list_archives(s)),
                        collection_aids(sn), season_id)
    return _finish_add(s, season_id, section_id, jar, eps, a.exec)


def find_collection_by_id(s: requests.Session, sid: int):
    for sn in list_collections(s):
        if (sn.get("season") or {}).get("id") == sid:
            return sn
    return None


def cmd_sync(a):
    s, jar = session()
    sn = find_collection(s, COLLECTION_NAME)
    if not sn:
        if not a.exec:
            warn("dry-run：将新建合集「arXiv-daily」并挂载匹配视频。加 --exec 才执行。")
        else:
            p = make_cover()
            url = upload_cover(s, jar, p)
            if not url:
                return 1
            new_id = create_collection(s, jar, COLLECTION_NAME, COLLECTION_DESC, url)
            if not new_id:
                return 1
            # 创建后重新取回（含自动生成的「正片」小节），最多重试 2 次
            for _ in range(3):
                sn = find_collection_by_id(s, new_id)
                if sn:
                    break
            if not sn:
                bad("创建后未能查到合集（含小节），挂载中止。请稍后手动 add。")
                return 1
    section_id = default_section_id(sn) if sn else None
    if a.exec and not section_id:
        bad("合集没有可用小节（section）。")
        return 1
    season_id = season_id_of(sn) if sn else 0
    eps = plan_episodes(s, filter_arxiv(list_archives(s)),
                        collection_aids(sn) if sn else set(), season_id)
    return _finish_add(s, season_id, section_id or 0, jar, eps, a.exec)


def main():
    ap = argparse.ArgumentParser(description="arXiv-daily → B站合集管理")
    ap.add_argument("cmd", choices=["videos", "collections", "cover", "create", "add", "sync"])
    ap.add_argument("--exec", dest="exec", action="store_true", help="真正执行（对外副作用）")
    a = ap.parse_args()
    if not COOKIE.is_file():
        bad(f"未找到 cookie：{COOKIE}")
        return 1
    return {
        "videos": cmd_videos, "collections": cmd_collections, "cover": cmd_cover,
        "create": cmd_create, "add": cmd_add, "sync": cmd_sync,
    }[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
