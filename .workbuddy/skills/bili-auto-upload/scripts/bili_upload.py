#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
arXiv 日报视频 → bilibili 自动投稿工具

设计原则
  1. 默认安全：upload / comment 默认 dry-run，只有显式 --exec 才产生对外副作用。
  2. 不伪造成功：verify 读不到稿件就如实报「未核实」，绝不把「没报错」当成「已发布」。
  3. cookie 绝不入库：启动即校验 .secrets/ 不在 git 版本控制内。
  4. 字段硬限制在生成侧就校验（title 80 / desc 250 / tag 200），不让 B站来报错。

子命令
  check    环境体检（biliup / ffmpeg / cookie / 产物）
  meta     生成投稿元数据 → output/bili_meta_<issue>.json
  cover    抽封面 → output/bili_cover_<issue>.jpg
  upload   投稿（默认 dry-run，--exec 真投）
  verify   对账读回：查 member 稿件列表确认 BV 号与状态
  comment  置顶评论稿（默认打印，--exec 发送并置顶）
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import io
import json
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 请求 B 站时绕开本机代理，避免回环/代理把请求拦成 502
os.environ.setdefault(
    "NO_PROXY", "bilibili.com,.bilibili.com,127.0.0.1,localhost"
)

from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]  # scripts → bili-auto-upload → skills → .workbuddy → arXiv

OUT = ROOT / "output"
SEC = ROOT / ".secrets"
COOKIE = SEC / "bili_cookies.json"
PAPERS = ROOT / "reel" / "src" / "papers.json"

TID = "171"  # 知识·野生技术协会
TITLE_MAX, DESC_MAX, TAG_MAX = 80, 250, 200
BASE_TAGS = ["arXiv", "论文速递", "计算机科学", "分布式系统", "数据库", "形式化方法", "论文解读"]

# member API 的稿件状态码：宁可给区间描述，也不猜错具体语义
STATE_TEXT = {
    "0": "已发布 / 开放浏览",
    "-2": "审核中",
    "-30": "审核不通过（需查看退回原因）",
    "-40": "定时发布中",
    "1": "仅自己可见",
}


def ok(msg: str) -> None:
    print(f"[ok]   {msg}")


def warn(msg: str) -> None:
    print(f"[warn] {msg}")


def bad(msg: str) -> None:
    print(f"[FAIL] {msg}")


def info(msg: str) -> None:
    print(f"       {msg}")


def _is_pe(p: str) -> bool:
    """是否是可执行的 Windows PE（MZ 头且非空）。

    winget 偶尔会在 %LOCALAPPDATA%\\Microsoft\\WinGet\\Links\\ 留下 0 字节的 biliup.exe 空壳
    （未开开发者模式时符号链接创建失败所致）。这种文件 shutil.which 照样能找到，
    但 CreateProcess 会报「不是此 OS 平台的有效应用」。所以命中 PATH 前必须验一遍。
    """
    try:
        with open(p, "rb") as fh:
            return fh.read(2) == b"MZ"
    except OSError:
        return False


def repair_winget_link() -> str | None:
    """修复 winget Links 目录下的 0 字节 biliup.exe 空壳。

    winget 未开「开发者模式」时创建符号链接失败，会在
    %LOCALAPPDATA%\\Microsoft\\WinGet\\Links\\biliup.exe 留下 0 字节文件；
    而该目录在用户 PATH 里优先级最高，于是 PowerShell 直接报
    「Program 'biliup.exe' failed to run: 不是此 OS 平台的有效应用」。
    这里只把真实二进制复制覆盖这一个空壳文件，不删除任何东西。
    """
    import shutil

    link = Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\biliup.exe"))
    good = find_biliup()
    if not link.exists() or not good or _is_pe(str(link)):
        return None
    if os.path.abspath(str(link)) == os.path.abspath(good):
        return None
    try:
        shutil.copy(good, link)
    except OSError as e:
        return f"空壳修复失败（可手动复制）：{e}"
    return f"已修复 PATH 上的 0 字节空壳 biliup.exe → {link}（用 {good} 覆盖）"


def find_biliup() -> str | None:
    """biliup 二进制：环境变量 > PATH > WinGet 包目录。

    winget 装完后会改用户 PATH，但已运行的 shell 读不到新 PATH，所以必须兜底到包目录。
    每一级都要过 _is_pe()，否则会拿到 Links 目录下的 0 字节空壳。
    """
    env = os.environ.get("BILIUP")
    if env and Path(env).is_file() and _is_pe(env):
        return env
    import shutil

    for name in ("biliup", "biliup.exe"):
        hit = shutil.which(name)
        if hit and _is_pe(hit):
            return hit
    base = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    for p in glob.glob(os.path.join(base, "ForgQi.biliup-rs*", "**", "biliup.exe"), recursive=True):
        if _is_pe(p):
            return p
    return None


def find_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    import shutil

    return shutil.which("ffmpeg")


def load_papers() -> dict:
    return json.loads(PAPERS.read_text(encoding="utf-8"))


def newest_video() -> Path | None:
    cands = sorted(OUT.glob("arxiv_weekly_*.mp4"))
    return cands[-1] if cands else None


def resolve_issue(date: str | None) -> tuple[str, Path | None, dict]:
    """返回 (issue, video_path, papers)。date 为空时先试当天，回退到最新一期。"""
    data = load_papers()
    issue = date or dt.datetime.now().strftime("%Y%m%d")
    video = OUT / f"arxiv_weekly_{issue}.mp4"
    if not video.is_file():
        nv = newest_video()
        if nv is None:
            return issue, None, data
        m = re.search(r"arxiv_weekly_(\d{8})\.mp4", nv.name)
        if m and not date:
            issue = data.get("issue") or m.group(1)
        video = nv
    return str(data.get("issue") or issue), video, data


def check_not_git_tracked(p: Path) -> bool:
    if not p.exists():
        return True
    try:
        r = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(p)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        return r.returncode != 0  # 返回非 0 = 未被跟踪，安全
    except Exception:
        return True


def build_desc(papers: list[dict]) -> tuple[str, int]:
    """在 250 字上限内塞进尽可能多的论文链接，余下的交给置顶评论。

    一条 `arxiv.org/abs/2610.00896` 加换行是 27 字符，10 条 270 字必然超限，
    所以这里做「能放几条放几条」，绝不为了塞满而截断 URL。
    """
    head = f"arXiv 日报重点论文 10 篇，每篇 20 秒中文讲解（背景 / 方法 / 结果）。"
    links = [f"arxiv.org/abs/{p['sid']}" for p in papers]
    n = len(links)
    while n > 0:
        body = "\n".join(links[:n])
        tail = "" if n == len(links) else f"\n…其余 {len(links) - n} 条见置顶评论"
        d = head + "\n" + body + tail
        if len(d) <= DESC_MAX:
            return d, n
        n -= 1
    return head[:DESC_MAX], 0


def build_title(issue: str) -> str:
    t = f"arXiv 日报 {issue}｜DB·分布式·形式化 Top10 速览"
    return t[:TITLE_MAX]


def build_tags(papers: list[dict]) -> str:
    tags = list(BASE_TAGS)
    s = ",".join(tags)
    if len(s) > TAG_MAX:
        while len(s) > TAG_MAX and len(tags) > 2:
            tags.pop()
            s = ",".join(tags)
    return s


def build_comment(papers: list[dict], issue: str) -> str:
    lines = [f"arXiv 日报 {issue} 期 · 论文链接清单"]
    for i, p in enumerate(papers, 1):
        title = p.get("title_en", "")
        if len(title) > 46:
            title = title[:45] + "…"
        lines.append(f"{i}. {title}")
        lines.append(f"   arxiv.org/abs/{p['sid']}")
    return "\n".join(lines)


def load_cookie_jar() -> dict[str, str]:
    """兼容三种 cookie 文件：dict（扁平 name→value）/ list-of-dict / Netscape 文本。

    另外要兼容 biliup-rs 的 LoginInfo 结构（tools/bili_tv_qr_login.py 写出的格式）：
        {"cookie_info": {"cookies": [{"name","value"}, ...], ...}, "sso": [...], "token_info": {...}}
    """
    raw = COOKIE.read_text(encoding="utf-8", errors="replace").strip()
    try:
        j = json.loads(raw)
    except Exception:
        jar = {}
        for line in raw.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                jar[parts[5]] = parts[6]
        return jar
    # biliup-rs LoginInfo：从 cookie_info.cookies 提取
    if isinstance(j, dict) and isinstance(j.get("cookie_info"), dict):
        jar = {}
        for it in j["cookie_info"].get("cookies", []):
            if isinstance(it, dict) and "name" in it and "value" in it:
                jar[str(it["name"])] = str(it["value"])
        if jar:
            return jar
    if isinstance(j, dict):
        return {str(k): str(v) for k, v in j.items()}
    jar = {}
    if isinstance(j, list):
        for it in j:
            if isinstance(it, dict) and "name" in it and "value" in it:
                jar[str(it["name"])] = str(it["value"])
    return jar


def cookie_header() -> str:
    jar = load_cookie_jar()
    return "; ".join(f"{k}={v}" for k, v in jar.items())


DPAPI_PREFIX = "DPAPI:"


# ---------------------------------------------------------------------------- cmd: check
def cmd_check(a: argparse.Namespace) -> int:
    print("== 环境体检 ==")
    exe = find_biliup()
    if exe:
        ok(f"biliup  → {exe}")
        try:
            r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30)
            info((r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr) else "")
        except Exception as e:
            warn(f"版本查询失败：{e}")
    else:
        bad("找不到 biliup。安装：winget install --id ForgQi.biliup-rs --exact")

    fix = repair_winget_link()
    if fix:
        warn(fix)

    ff = find_ffmpeg()
    ok(f"ffmpeg → {ff}") if ff else warn("无 ffmpeg（cover 命令会不可用）")

    if COOKIE.is_file():
        ok(f"cookie → {COOKIE}")
        if not check_not_git_tracked(COOKIE):
            bad("cookie 已被 git 跟踪！立即 git rm --cached 并加入 .gitignore")
        else:
            ok("cookie 未被 git 跟踪（安全）")
        jar = load_cookie_jar()
        info("关键字段：" + ", ".join(k for k in ("DedeUserID", "SESSDATA", "bili_jct") if k in jar) or "缺少关键字段")
        if not {"SESSDATA", "bili_jct"} <= set(jar):
            warn("cookie 缺 SESSDATA / bili_jct，投稿或评论会失败：biliup -u <路径> login")
    else:
        warn(f"未登录（无 {COOKIE}）。先跑：biliup -u \"{COOKIE}\" login")

    issue, video, data = resolve_issue(a.date)
    ok(f"期号 {issue} · 论文 {len(data.get('papers', []))} 篇")
    if video:
        ok(f"视频 → {video.name}（{video.stat().st_size / 1e6:.1f} MB）")
    else:
        bad("output/ 下没有 arxiv_weekly_*.mp4")

    try:
        import requests  # noqa: F401

        ok("requests 可用（verify / comment 需要）")
    except Exception:
        warn("requests 未安装：pip install requests")
    try:
        import bilibili_api  # noqa: F401

        ok("bilibili-api-python 可用（自动评论/置顶需要）")
    except Exception:
        warn("bilibili-api-python 未安装，comment --exec 将降级为「输出稿子」")
    return 0


# ---------------------------------------------------------------------------- cmd: meta
def cmd_meta(a: argparse.Namespace) -> int:
    issue, video, data = resolve_issue(a.date)
    papers = data.get("papers", [])
    desc, n_in = build_desc(papers)
    title = build_title(issue)
    tags = build_tags(papers)
    comment = build_comment(papers, issue)
    assert len(desc) <= DESC_MAX, "desc 超 250"
    assert len(title) <= TITLE_MAX, "title 超 80"
    meta = {
        "issue": issue,
        "video": str(video) if video else None,
        "title": title,
        "desc": desc,
        "tags": tags,
        "tid": TID,
        "copyright": "1",
        "cover": str(OUT / f"bili_cover_{issue}.jpg"),
        "links_in_desc": n_in,
        "links_total": len(papers),
    }
    p = OUT / f"bili_meta_{issue}.json"
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / f"bili_comment_{issue}.txt").write_text(comment, encoding="utf-8")
    ok(f"元数据 → {p.name}")
    info(f"标题({len(title)}字)：{title}")
    info(f"简介({len(desc)}字)：10 篇里塞进 {n_in} 条链接，其余 {len(papers) - n_in} 条走置顶评论")
    info(f"标签({len(tags)}字)：{tags}")
    info(f"评论稿 → bili_comment_{issue}.txt（{len(comment)} 字符）")
    return 0


# ---------------------------------------------------------------------------- cmd: cover
def cmd_cover(a: argparse.Namespace) -> int:
    issue, video, _ = resolve_issue(a.date)
    if not video:
        bad("没有视频，无法抽封面")
        return 1
    ff = find_ffmpeg()
    if not ff:
        bad("没有 ffmpeg")
        return 1
    out = OUT / f"bili_cover_{issue}.jpg"
    cmd = [ff, "-y", "-ss", "1", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if out.is_file():
        ok(f"封面 → {out.name}（{out.stat().st_size / 1024:.0f} KB）")
        return 0
    bad("抽帧失败：" + (r.stderr or "")[-400:])
    return 1


# ---------------------------------------------------------------------------- cmd: upload
def cmd_upload(a: argparse.Namespace) -> int:
    issue, video, _ = resolve_issue(a.date)
    if not video:
        bad("没有视频")
        return 1
    exe = find_biliup()
    if not exe:
        bad("没有 biliup")
        return 1
    if not COOKIE.is_file():
        if a.exec:
            bad(f"未登录：先跑 biliup -u \"{COOKIE}\" login")
            return 1
        warn(f"未登录（{COOKIE.name} 不存在）：dry-run 照常展示，真投前先扫码登录")
    mp = OUT / f"bili_meta_{issue}.json"
    if not mp.is_file():
        info("未找到元数据，先生成")
        cmd_meta(a)
    m = json.loads(mp.read_text(encoding="utf-8"))
    cover = Path(m["cover"])
    cmd = [
        exe, "-u", str(COOKIE), "upload", str(video),
        "--submit", "web",  # cookie 登录必须走 web 提交；默认 client 需要 token_info.access_token
        "--title", m["title"],
        "--tid", TID,
        "--tag", m["tags"],
        "--desc", m["desc"],
        "--copyright", "1",
    ]
    if cover.is_file():
        cmd += ["--cover", str(cover)]
    printable = subprocess.list2cmdline(cmd[:5]) + " --title … --tag … --desc … --copyright 1"
    print("== 投稿命令 ==")
    info(printable)
    info(f"视频 {Path(m['video']).name if m['video'] else '?'} / 封面 {cover.name if cover.is_file() else '无（B站自动生成）'}")
    if not a.exec:
        warn("dry-run：未真正投稿。加 --exec 才执行。")
        return 0

    ok("开始投稿（约需数分钟，取决于带宽）…")
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=3600)
    log = (r.stdout or "") + (r.stderr or "")
    tail = "\n".join(log.strip().splitlines()[-25:])
    print(tail)
    if r.returncode == 0:
        ok("投稿命令返回 0 —— 注意：返回 0 不等于已发布，必须再跑 verify 确认")
        return 0
    if "601" in log:
        bad("命中账号频控 code 601（您上传视频过快）。这是账号侧临时限流，"
            "等几分钟用同一条命令重投即可，**不要改参数硬刷**。")
    else:
        bad(f"投稿失败，退出码 {r.returncode}")
    return r.returncode or 1


# ---------------------------------------------------------------------------- cmd: verify
def cmd_verify(a: argparse.Namespace) -> int:
    try:
        import requests
    except Exception:
        bad("需要 requests：pip install requests")
        return 1
    if not COOKIE.is_file():
        bad("没有 cookie，无法查稿件")
        return 1
    issue, _, _ = resolve_issue(a.date)
    mp = OUT / f"bili_meta_{issue}.json"
    title_expect = json.loads(mp.read_text(encoding="utf-8"))["title"] if mp.is_file() else None

    sess = requests.Session()
    sess.trust_env = False
    url = "https://member.bilibili.com/x/web/archives?pn=1&ps=20"
    try:
        r = sess.get(
            url,
            headers={
                "Cookie": cookie_header(),
                "Referer": "https://member.bilibili.com/platform/upload-manager/article",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
            timeout=20,
        )
        j = r.json()
    except Exception as e:
        bad(f"查询失败：{e}")
        return 1
    if j.get("code") != 0:
        bad(f"member API 返回 code={j.get('code')} message={j.get('message')}（登录态可能已过期）")
        return 1
    rows = (j.get("data") or {}).get("arc_audits") or []
    print(f"== 对账读回（共 {len(rows)} 条近期稿件）==")
    now = dt.datetime.now().timestamp()
    hit = None
    for row in rows:
        arc = row.get("Archive") or {}
        t = arc.get("title", "")
        ct = arc.get("ctime") or 0
        if title_expect and t.startswith(title_expect[:20]):
            hit = arc
            break
    if hit:
        st = str(hit.get("state"))
        ok(f"找到稿件：{hit.get('title')}")
        info(f"BV 号  BV{hit.get('bvid','')}" if not str(hit.get("bvid", "")).startswith("BV") else f"BV 号  {hit.get('bvid')}")
        info(f"状态  {st} → {STATE_TEXT.get(st, '未知（请在创作中心确认）')}")
        info(f"链接  https://www.bilibili.com/video/{hit.get('bvid','')}")
        (OUT / f"bili_published_{issue}.json").write_text(
            json.dumps({"issue": issue, "bvid": hit.get("bvid"), "aid": hit.get("aid"), "state": st, "verified_at": now},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        ok(f"对账结果 → bili_published_{issue}.json")
        return 0
    bad("未在近期稿件中找到本期标题 —— 结论：**未核实**，可能仍在队列或投稿实际未成功，请到创作中心人工核对")
    return 1


# ---------------------------------------------------------------------------- cmd: comment
def cmd_comment(a: argparse.Namespace) -> int:
    issue, _, data = resolve_issue(a.date)
    papers = data.get("papers", [])
    txt = build_comment(papers, issue)
    p = OUT / f"bili_comment_{issue}.txt"
    p.write_text(txt, encoding="utf-8")
    print("== 置顶评论稿 ==")
    print(txt)
    print(f"---- 已写入 {p.name}（{len(txt)} 字符）----")
    if not a.exec:
        warn("dry-run：未发送。加 --exec 才真正发评论并置顶。")
        return 0
    pub = OUT / f"bili_published_{issue}.json"
    if not pub.is_file():
        bad("没有 bili_published_<issue>.json（BV 号未知）。先跑 verify 再评论。")
        return 1
    try:
        from bilibili_api import comment, Credential
    except Exception:
        bad("bilibili-api-python 未安装，无法自动发送。已输出稿件，请手动粘贴到评论区并置顶；"
            "或执行 pip install bilibili-api-python 后重试。")
        return 1
    pubj = json.loads(pub.read_text(encoding="utf-8"))
    oid = pubj.get("aid")
    if not oid:
        bad("稿件缺少 aid，无法评论")
        return 1
    jar = load_cookie_jar()
    if not {"SESSDATA", "bili_jct"} <= set(jar):
        bad("cookie 缺 SESSDATA / bili_jct，无法发送评论")
        return 1
    hdr = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0",
        "Referer": "https://www.bilibili.com/",
        "Cookie": cookie_header(),
    }
    csrf = jar["bili_jct"]
    try:
        # 防重复：先查自己的评论里有没有链接清单
        r = requests.get(
            "https://api.bilibili.com/x/v2/reply/main",
            params={"oid": int(oid), "type": 1, "mode": 3},
            headers=hdr, timeout=15,
        ).json()
        existing = (r.get("data") or {}).get("replies") or []
        mine = [
            c for c in existing
            if c.get("mid") and c["mid"] == int(jar.get("DedeUserID") or -1)
            and "论文链接清单" in c["content"]["message"]
        ]
        if mine:
            rid = mine[0]["rpid"]
            warn(f"评论已存在（rpid={rid}），跳过发送，直接置顶")
        else:
            r2 = requests.post(
                "https://api.bilibili.com/x/v2/reply/send",
                data={"oid": int(oid), "type": 1, "message": txt,
                      "csrf": csrf, "csrf_token": csrf},
                headers=hdr, timeout=15,
            ).json()
            if r2.get("code") != 0:
                bad(f"评论发送失败：{r2}")
                return 1
            rid = (r2.get("data") or {}).get("rpid")
        r3 = requests.post(
            "https://api.bilibili.com/x/v2/reply/top",
            data={"oid": int(oid), "rpid": rid, "type": 1,
                  "action": 1, "csrf": csrf, "csrf_token": csrf},
            headers=hdr, timeout=15,
        ).json()
        if r3.get("code") != 0:
            bad(f"评论已发送但置顶失败：{r3}（可手动置顶）")
            return 1
        ok(f"评论已发送并置顶（rpid={rid}）")
        return 0
    except Exception as e:
        bad(f"评论发送失败：{e}。稿件已留在 {p.name}，可手动粘贴。")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="arXiv 日报视频自动投稿 bilibili")
    ap.add_argument("cmd", choices=["check", "meta", "cover", "upload", "verify", "comment"])
    ap.add_argument("--date", "-d", default=None, help="期号 YYYYMMDD，默认当天")
    ap.add_argument("--exec", dest="exec", action="store_true", help="真正执行（对外副作用）")
    a = ap.parse_args()
    return {
        "check": cmd_check, "meta": cmd_meta, "cover": cmd_cover,
        "upload": cmd_upload, "verify": cmd_verify, "comment": cmd_comment,
    }[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
