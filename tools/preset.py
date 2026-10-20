#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据包（预设）命令行：list / show / import / export / status。

它只是 `datapack.py` 的外壳 —— 解析参数、排版输出、给退出码；业务语义（哪些文件、
怎么合并、何时拒绝）全在模块里，避免"命令行一套规则、接口另一套规则"。

用法
  python tools/preset.py list                      列出可用数据包
  python tools/preset.py show hengxin              看包内容与本机差异（会覆盖 / 合并 / 跳过）
  python tools/preset.py import hengxin            导入（默认 core + usage + notes）
  python tools/preset.py import hengxin --force    覆盖本机 config.json / interests.json（先备份）
  python tools/preset.py import hengxin --with-learning   连行为学习数据一起导入
  python tools/preset.py import hengxin --dry-run  只看会发生什么，不写盘
  python tools/preset.py export myown              把本机设置存成包（默认只导出 core）
  python tools/preset.py export myown --with-usage --with-notes
  python tools/preset.py export myown --keep-paths  保留本机绝对路径（仅供本机备份）
  python tools/preset.py status                    本机有哪些个人数据

导入后
  1) 重跑 `python run_daily.py --skip-fetch --skip-affil`（或点页面的「↻ 重算推荐」）
  2) `/profile` 的数据每次请求实时读文件，不必重启服务；摘要页是静态文件，必须重算
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import datapack as DP  # noqa: E402


def _kb(n):
    return "%.1f KB" % (n / 1024.0) if n >= 1024 else "%d B" % n


def _add_group_flags(p, dry_run=False):
    p.add_argument("--with-usage", action="store_true", help="含收藏 / 下载 / Downvote")
    p.add_argument("--with-learning", action="store_true", help="含行为学习（profile_state + behavior）")
    p.add_argument("--with-notes", action="store_true", help="含中文摘要 / 推荐理由 / 看点")
    p.add_argument("--groups", default="", help="直接指定分组，逗号分隔：core,usage,learning,notes")
    if dry_run:
        p.add_argument("--dry-run", action="store_true", help="只预演，不写盘")


def _groups(a):
    if a.groups:
        return [g.strip() for g in a.groups.replace("，", ",").split(",") if g.strip()]
    g = list(DP.DEFAULT_IMPORT) if a.cmd == "import" else list(DP.DEFAULT_EXPORT)
    if a.with_usage and "usage" not in g:
        g.append("usage")
    if a.with_learning and "learning" not in g:
        g.append("learning")
    if a.with_notes and "notes" not in g:
        g.append("notes")
    return g


# ---------------------------------------------------------------- 子命令

def cmd_list(_a):
    packs = DP.list_packs()
    if not packs:
        print("没有可用数据包。\n"
              "  · 把包放进 %s/<名字>/（至少含 config.json 或 interests.json），或\n"
              "  · 用 `python tools/preset.py export <名字>` 把当前设置存成一个包。" % DP.packs_dir())
        return 0
    print("可用数据包（放进 presets/ 即被发现，**默认不加载**）：\n")
    for p in packs:
        print("  %-14s %s" % (p["name"], p["title"] or "（无标题）"))
        if p["description"]:
            print("  %-14s %s" % ("", p["description"]))
        print("  %-14s 文件：%s（%s）"
              % ("", "、".join(p["files"]), _kb(p["bytes"])))
        print("  %-14s 分组：%s%s"
              % ("", "、".join(p["groups"]), "" if p["has_manifest"] else " ｜ 无 manifest.json（旧版包）"))
        print("  %-14s 导入：python tools/preset.py import %s" % ("", p["name"]))
        print()
    return 0


def cmd_show(a):
    try:
        d = DP.pack_path(a.name)
    except ValueError as e:
        print(e)
        return 2
    if not os.path.isdir(d):
        print("找不到数据包：%s" % a.name)
        return 2
    m = DP.manifest(a.name)
    print("数据包：%s\n  路径：%s" % (a.name, d))
    if m.get("title"):
        print("  标题：%s" % m["title"])
    if m.get("description"):
        print("  描述：%s" % m["description"])
    print("  清单：%s ｜ schema=%s ｜ 导出时间 %s"
          % ("有" if m.get("_source") == DP.MANIFEST else "无",
             m.get("schema"), m.get("exported_at") or "—"))
    rows = DP.compare_pack(a.name)
    print("\n  文件                    分组       大小      与本机的关系")
    for r in rows:
        rel = {"new": "本机没有 → 新增",
               "same": "内容一致 → 跳过",
               "pristine": "本机仍是模板初值 → 直接替换",
               "diff": "不同 → " + ("合并" if r["group"] in ("usage", "notes") else "需 --force")}[r["status"]]
        print("  %-22s %-9s %8s  %s" % (r["file"], r["group"], _kb(r["bytes"]), rel))
    print("\n  本机状态：%s" % _state_line())
    return 0


def _state_line():
    st = DP.state()["files"]
    have = [f for f, v in st.items() if v["exists"]]
    return "已有 " + "、".join(have) if have else "干净（没有任何个人数据）"


def cmd_import(a):
    groups = _groups(a)
    ok, msg, report = DP.import_pack(a.name, groups=groups, force=a.force,
                                     dry_run=a.dry_run)
    head = "预演（未写盘）" if a.dry_run else "导入结果"
    print("%s：%s\n" % (head, msg))
    for r in report:
        mark = {"written": "+", "replaced": "~", "merged": "∪",
                "skipped": "=", "refused": "×"}.get(r["action"], "?")
        print("  %s %-22s %-9s %s %s" % (mark, r["file"], r["group"],
                                         r["action"], r["reason"]))
    if not ok:
        print("\n提示：配置类文件（core）默认不覆盖。确认要用包里的设置，加 --force"
              "（会先备份到 output/backup/<时间>/）。")
        return 1
    print("\n下一步：python run_daily.py --skip-fetch --skip-affil"
          "（或点摘要页的「↻ 重算推荐」）")
    return 0


def cmd_export(a):
    groups = _groups(a)
    ok, msg, report = DP.export_pack(a.name, groups=groups, sanitize=not a.keep_paths,
                                     title=a.title, description=a.desc)
    print("%s：%s\n" % ("导出结果" if ok else "导出失败", msg))
    for r in report:
        print("  %-22s %-9s %s" % (r["file"], r["group"], r["action"]))
    if ok:
        print("\n提示：包内可能含个人画像（研究方向 / 对标学者）。提交到公开仓库前，"
              "先读一遍 %s/%s。" % (DP.packs_dir(), a.name))
    return 0 if ok else 1


def cmd_status(_a):
    st = DP.state()
    print("本机个人数据（与代码、模板分离；均不入版本库）：\n")
    print("  %-22s %-9s %-8s %-10s %s" % ("文件", "分组", "大小", "状态", "更新时间"))
    for f, v in st["files"].items():
        print("  %-22s %-9s %-8s %-10s %s"
              % (f, v["group"], _kb(v["bytes"]), "存在" if v["exists"] else "—",
                 v["updated_at"] or ""))
    print("\n  → %s" % ("已有个人数据" if st["has_personal_data"] else "干净：没有读取任何数据包"))
    return 0


def main():
    ap = argparse.ArgumentParser(description="数据包（预设）管理：list / show / import / export / status")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("list", help="列出可用数据包")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="看包内容与本机差异")
    p.add_argument("name")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("import", help="导入数据包")
    p.add_argument("name")
    p.add_argument("--force", action="store_true", help="覆盖本机 config.json / interests.json（先备份）")
    _add_group_flags(p, dry_run=True)
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("export", help="把本机设置导出成数据包")
    p.add_argument("name")
    p.add_argument("--keep-paths", action="store_true", help="保留本机绝对路径（仅供本机备份）")
    p.add_argument("--title", default="", help="包标题（写进 manifest.json）")
    p.add_argument("--desc", default="", help="包描述（写进 manifest.json）")
    _add_group_flags(p)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("status", help="本机有哪些个人数据")
    p.set_defaults(func=cmd_status)

    a = ap.parse_args()
    if not getattr(a, "func", None):
        ap.print_help()
        return 1
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
