#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验一期视频是否满足「标题公式 / 封面方案 / 选题约束」。

为什么要单独一个脚本
--------------------
这三条约束被违反时**不会报错**：B站照收稿，标题长度、封面尺寸都「合法」，
只是点击率悄悄变差。所以必须有一个发布前主动检查的关口，而不是靠人眼。

检查项（任一失败即退出码 1）
    标题  `{钩子 ≤18 字}｜arXiv 日报 #MMDD`，且钩子与 meta 记录一致
    封面  1146×717、由 Pillow 设计稿渲染（不是抽帧）、角标/钩子/篇数与本期一致
    选题  片数与本期论文数一致；同一 primary 最多 4 篇；至少 1 篇标题自带可读钩子

用法::

    python tools/verify_episode.py                    # 校验最新一期
    python tools/verify_episode.py --date 20261116    # 指定期号
    python tools/verify_episode.py --json             # 机器可读，便于定时任务落日志
    python tools/verify_episode.py --quiet            # 只输出失败项与结论

退出码：0 全部通过 / 1 有失败项 / 2 产物缺失（流水线还没跑到那一步）。

每天自动执行
------------
投稿流水线的自动化在 `meta → cover` 之后、`upload --exec` 之前调用本脚本
（不带参数即校验当期）；另外也可由系统计划任务每天跑一次 `--json` 落盘存档。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
PAPERS = ROOT / "reel" / "src" / "papers.json"
BILI_SCRIPT = ROOT / ".workbuddy" / "skills" / "bili-auto-upload" / "scripts" / "bili_upload.py"
GEN_SCRIPT = ROOT / "tools" / "gen_video_data.py"

# 标题必须严格是这个形状：钩子 + 固定后缀 + 4 位 MMDD。
TITLE_RE = re.compile(r"^.+｜arXiv 日报 #\d{4}$")


# ---------------------------------------------------------------- 基础设施
def load_module(path: Path, name: str):
    """按文件路径加载脚本（技能目录带连字符，不能当包 import）。"""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 %s" % path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def jpeg_size(path: Path) -> tuple[int, int]:
    """只读 JPEG 头拿宽高，不依赖 Pillow。

    校验脚本要比被校验的渲染器「更少依赖」：封面渲染需要 Pillow，
    但检查封面尺寸不该因为 Pillow 装没装而改变结论。
    """
    with open(path, "rb") as fh:
        if fh.read(2) != b"\xff\xd8":
            raise ValueError("不是 JPEG 文件")
        while True:
            byte = fh.read(1)
            if not byte:
                raise ValueError("找到文件尾也没见到 SOF 段")
            if byte != b"\xff":
                continue
            while byte == b"\xff":
                byte = fh.read(1)
            marker = byte[0]
            if marker == 0xD8 or 0xD0 <= marker <= 0xD7:
                continue
            length = int.from_bytes(fh.read(2), "big")
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                fh.read(1)  # 精度
                height = int.from_bytes(fh.read(2), "big")
                width = int.from_bytes(fh.read(2), "big")
                return width, height
            fh.seek(length - 2, 1)


def latest_issue() -> str | None:
    """`output/bili_meta_*.json` 里 mtime 最新的那一期。"""
    metas = sorted(OUT.glob("bili_meta_*.json"), key=lambda p: p.stat().st_mtime)
    if not metas:
        return None
    m = re.search(r"bili_meta_(\d{8})\.json$", metas[-1].name)
    return m.group(1) if m else None


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


class Report:
    """收集检查结果；文本与 JSON 两种呈现共用同一份数据。"""

    def __init__(self, issue: str | None):
        self.issue = issue
        self.items: list[dict] = []

    def add(self, name: str, ok: bool, detail: str, hint: str = "") -> None:
        # hint 只在失败时才有意义；通过了还带着「怎么修」会让 JSON 看起来像在报错。
        self.items.append({"check": name, "ok": bool(ok), "detail": detail,
                           "hint": "" if ok else hint})

    @property
    def failed(self) -> list[dict]:
        return [i for i in self.items if not i["ok"]]

    def to_json(self) -> str:
        return json.dumps(
            {"issue": self.issue, "ok": not self.failed, "checks": self.items},
            ensure_ascii=False, indent=1,
        )


# ---------------------------------------------------------------- 三项检查
def check_title(rep: Report, meta: dict, BU) -> None:
    title = str(meta.get("title") or "")
    hook = str(meta.get("hook") or "")
    rep.add("标题非空", bool(title.strip()), title or "（空）", "先跑 meta 生成标题")
    if not title:
        return
    rep.add("标题公式", bool(TITLE_RE.match(title)),
            title, "期望 `{钩子}｜arXiv 日报 #MMDD`，检查 build_title 是否被绕过")
    if not hook:
        hook = title.split("｜arXiv 日报 #")[0]
    rep.add("钩子长度", 1 <= len(hook) <= BU.HOOK_MAX,
            "%d 字（上限 %d）" % (len(hook), BU.HOOK_MAX), "把 hook 压到 18 字以内")
    rep.add("标题与钩子一致", title.startswith(hook),
            "钩子=%s" % (hook or "（空）"), "meta.hook 与 title 前缀不符")
    rep.add("标题总长", len(title) <= BU.TITLE_MAX,
            "%d 字（上限 %d）" % (len(title), BU.TITLE_MAX), "B站标题上限 80 字")


def check_cover(rep: Report, meta: dict, issue: str, BU) -> None:
    cover = Path(str(meta.get("cover") or (OUT / ("bili_cover_%s.jpg" % issue))))
    manifest_path = Path(str(meta.get("cover_manifest") or (OUT / ("bili_cover_%s.json" % issue))))
    if not cover.is_file():
        rep.add("封面文件", False, str(cover), "先跑 cover 生成封面")
        return
    try:
        width, height = jpeg_size(cover)
    except Exception as exc:  # 坏文件 / 不是 JPEG
        rep.add("封面尺寸", False, "读取失败：%s" % exc, "重新渲染封面")
        return
    rep.add("封面尺寸", (width, height) == (BU.COVER_W, BU.COVER_H),
            "%d×%d（期望 %d×%d）" % (width, height, BU.COVER_W, BU.COVER_H),
            "B站封面按 1146×717 渲染")

    manifest = read_json(manifest_path) if manifest_path.is_file() else None
    if not manifest:
        rep.add("封面设计稿", False, "缺少 %s" % manifest_path.name,
                "旧版抽帧封面没有设计清单，重跑 cover")
        return
    rep.add("封面设计稿", True, manifest_path.name)
    rep.add("封面非抽帧", manifest.get("renderer") == "pillow",
            "renderer=%s" % manifest.get("renderer"), "封面必须由 Pillow 设计稿渲染")
    rep.add("封面钩子一致", manifest.get("hook") == str(meta.get("hook") or ""),
            "封面=%s / 标题=%s" % (manifest.get("hook"), meta.get("hook")),
            "封面主文案与标题钩子必须同源")
    rep.add("封面角标", manifest.get("badge") == BU.issue_badge(issue),
            "%s（期望 %s）" % (manifest.get("badge"), BU.issue_badge(issue)),
            "角标应为 #MMDD")
    rep.add("封面篇数", int(manifest.get("count") or 0) == int(meta.get("links_total") or 0),
            "%s 篇（期望 %s）" % (manifest.get("count"), meta.get("links_total")),
            "封面篇数与本期论文数不符")


def check_selection(rep: Report, meta: dict, issue: str, GEN) -> None:
    path = PAPERS
    data = read_json(path) if path.is_file() else None
    if not data:
        rep.add("选题数据", False, str(path), "先跑 gen_video_data.py")
        return
    papers = data.get("papers") or []
    rep.add("选题数据", True, "%s（%d 篇）" % (path.name, len(papers)))
    rep.add("期号一致", str(data.get("issue") or "") == issue,
            "数据期号 %s / 校验期号 %s" % (data.get("issue"), issue),
            "papers.json 不是本期产物，重跑 gen_video_data.py")

    counts: dict[str, int] = {}
    for p in papers:
        cat = str(p.get("cat") or "（无分类）")
        counts[cat] = counts.get(cat, 0) + 1
    worst = max(counts.values()) if counts else 0
    over = {k: v for k, v in counts.items() if v > GEN.MAX_PER_PRIMARY}
    rep.add("单分类上限", not over,
            "最大 %d 篇（上限 %d）%s" % (worst, GEN.MAX_PER_PRIMARY,
                                        "" if not over else " 超出：%s" % over),
            "同一 primary 最多 4 篇，调整 gen_video_data 的选取")

    hooks = sum(1 for p in papers if p.get("title_hook") or GEN.has_readable_hook(p.get("title_en")))
    rep.add("至少一篇钩子", hooks >= 1, "%d 篇标题带钩子" % hooks,
            "换入一篇标题含数字/反直觉结论的论文")

    ranks = [int(p.get("rank") or 0) for p in papers]
    rep.add("篇序连续", ranks == list(range(1, len(papers) + 1)),
            "ranks=%s" % ranks, "papers.json 的 rank 应连续")
    if meta.get("links_total"):
        rep.add("篇数一致", len(papers) == int(meta["links_total"]),
                "papers=%d / meta=%s" % (len(papers), meta["links_total"]),
                "封面/简介按 meta 生成，两处必须同源")


# ---------------------------------------------------------------- 入口
def evaluate(issue: str) -> tuple[Report | None, int]:
    """跑完三项检查，返回 `(报告, 退出码)`；退出码 2 表示产物/依赖缺失。"""
    rep = Report(issue)
    meta_path = OUT / ("bili_meta_%s.json" % issue)
    meta = read_json(meta_path) if meta_path.is_file() else None
    if not meta:
        print("[FAIL] 缺少 %s —— 流水线尚未走到 meta 步骤" % meta_path.name, file=sys.stderr)
        return None, 2
    try:
        BU = load_module(BILI_SCRIPT, "bili_upload_verify")
        GEN = load_module(GEN_SCRIPT, "gen_video_data_verify")
    except Exception as exc:
        print("[FAIL] 无法加载校验依赖：%s" % exc, file=sys.stderr)
        return None, 2

    check_title(rep, meta, BU)
    check_cover(rep, meta, issue, BU)
    check_selection(rep, meta, issue, GEN)
    return rep, 0 if not rep.failed else 1


def emit_text(rep: Report, quiet: bool = False) -> None:
    if not quiet:
        print("== 校验 %s ==" % rep.issue)
        for it in rep.items:
            print("%s %-14s %s" % ("[ok]  " if it["ok"] else "[FAIL]",
                                   it["check"], it["detail"]))
            if not it["ok"] and it["hint"]:
                print("       → %s" % it["hint"])
    bad = rep.failed
    print("%s 期号 %s：%d/%d 项通过"
          % ("[PASS]" if not bad else "[FAIL]", rep.issue,
             len(rep.items) - len(bad), len(rep.items)))
    for it in bad:
        print("  - %s：%s" % (it["check"], it["detail"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="校验一期视频的标题 / 封面 / 选题约束")
    ap.add_argument("-d", "--date", help="期号 YYYYMMDD；默认取最新一期")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    ap.add_argument("--quiet", action="store_true", help="只输出结论与失败项")
    args = ap.parse_args(argv)

    issue = (args.date or "").strip() or latest_issue()
    if not issue:
        print("[FAIL] output/ 下没有任何 bili_meta_*.json", file=sys.stderr)
        return 2
    if not re.fullmatch(r"\d{8}", issue):
        print("[FAIL] 期号必须是 8 位数字：%s" % issue, file=sys.stderr)
        return 2

    rep, code = evaluate(issue)
    if rep is None:
        return code
    if args.json:
        print(rep.to_json())
    else:
        emit_text(rep, quiet=args.quiet)
    return code


if __name__ == "__main__":
    sys.exit(main())
