#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预设（presets/）：把「某套现成设置」按需导入，或把当前设置导出成预设。

项目默认初始化只给干净模板（config.example.json / interests.example.json），
任何人的个人画像与分类都放在 presets/<名字>/ 下，**默认不生效**，由用户自己决定是否导入。

用法
  python tools/preset.py list                     列出可用预设
  python tools/preset.py import hengxin           导入（已存在同名文件时拒绝覆写）
  python tools/preset.py import hengxin --force    覆盖导入（原文件先备份到 output/backup/<时间>/）
  python tools/preset.py export hengxin            把当前 config.json / interests.json 存回预设

导入后
  1) 重跑 `python run_daily.py`（或只 `python recommend.py && python build_report.py`）
  2) 重启 `python server.py`，页面才会读到新的画像
"""
import argparse
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import paperutil as pu  # noqa: E402

PRESETS = os.path.join(ROOT, "presets")
FILES = ("config.json", "interests.json")


def _preset_dir(name):
    return os.path.join(PRESETS, name)


def _presets():
    if not os.path.isdir(PRESETS):
        return []
    out = []
    for n in sorted(os.listdir(PRESETS)):
        d = _preset_dir(n)
        if os.path.isdir(d) and any(os.path.exists(os.path.join(d, f)) for f in FILES):
            out.append(n)
    return out


def _describe(name):
    d = _preset_dir(name)
    meta = os.path.join(d, "meta.json")
    if os.path.exists(meta):
        try:
            m = json.load(open(meta, encoding="utf-8"))
            return m.get("title") or "", m.get("description") or ""
        except Exception:
            pass
    readme = os.path.join(d, "README.md")
    if os.path.exists(readme):
        try:
            for line in open(readme, encoding="utf-8"):
                line = line.strip()
                if line and not line.startswith("#"):
                    return "", line
        except Exception:
            pass
    return "", ""


def cmd_list(_a):
    names = _presets()
    if not names:
        print("没有可用预设。用 `python tools/preset.py export <名字>` 把当前设置存成预设。")
        return 0
    print("可用预设（导入后才会生效，默认不加载任何个人画像）：\n")
    for n in names:
        title, desc = _describe(n)
        files = [f for f in FILES if os.path.exists(os.path.join(_preset_dir(n), f))]
        print("  %-10s %s" % (n, title or ""))
        if desc:
            print("             %s" % desc)
        print("             包含：%s" % "、".join(files))
        print("             导入：python tools/preset.py import %s" % n)
    return 0


def _backup(paths):
    ts = time.strftime("%Y%m%d-%H%M%S")
    bdir = os.path.join(pu.OUT, "backup", ts)
    os.makedirs(bdir, exist_ok=True)
    moved = []
    for p in paths:
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(bdir, os.path.basename(p)))
            moved.append(os.path.basename(p))
    return bdir, moved


def cmd_import(a):
    name = a.name
    d = _preset_dir(name)
    if not os.path.isdir(d):
        print("找不到预设：%s（可用：%s）" % (name, "、".join(_presets()) or "无"))
        return 2
    src = {f: os.path.join(d, f) for f in FILES if os.path.exists(os.path.join(d, f))}
    if not src:
        print("预设 %s 里没有 config.json / interests.json" % name)
        return 2
    dst = {f: os.path.join(ROOT, f) for f in src}
    clash = [f for f, p in dst.items() if os.path.exists(p)]
    if clash and not a.force:
        print("以下本地文件已存在，未覆盖：%s" % "、".join(clash))
        print("确认要覆盖请加 --force（会先备份到 output/backup/<时间>/）")
        return 1
    if clash:
        bdir, moved = _backup(list(dst.values()))
        print("已备份原文件到 %s（%s）" % (bdir, "、".join(moved)))
    for f, p in src.items():
        shutil.copy2(p, dst[f])
        print("已写入 %s" % dst[f])
    print("\n下一步：\n"
          "  1) python run_daily.py            # 抓取 + 推荐 + 渲染（或 --skip-fetch 只重算）\n"
          "  2) python server.py               # 启动本地服务后刷新页面\n"
          "  注意：预设里的 download_dir 可能是别人机器上的路径，建议先改成自己的。")
    return 0


def cmd_export(a):
    name = a.name
    d = _preset_dir(name)
    os.makedirs(d, exist_ok=True)
    saved = []
    for f in FILES:
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(d, f))
            saved.append(f)
    if not saved:
        print("本地没有 config.json / interests.json 可导出")
        return 1
    meta = os.path.join(d, "meta.json")
    if not os.path.exists(meta):
        with open(meta, "w", encoding="utf-8") as fh:
            json.dump({"title": name,
                       "description": "由 `python tools/preset.py export %s` 导出" % name,
                       "exported_at": pu.now_str()}, fh, ensure_ascii=False, indent=1)
    print("已导出 %s 到 %s" % ("、".join(saved), d))
    print("提示：预设里含个人画像与可能的本机路径，提交前确认你愿意公开。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="画像与配置预设管理")
    sub = ap.add_subparsers(dest="cmd")
    p1 = sub.add_parser("list", help="列出可用预设")
    p1.set_defaults(func=cmd_list)
    p2 = sub.add_parser("import", help="导入预设")
    p2.add_argument("name")
    p2.add_argument("--force", action="store_true", help="覆盖已存在的本地文件（先备份）")
    p2.set_defaults(func=cmd_import)
    p3 = sub.add_parser("export", help="把当前设置导出成预设")
    p3.add_argument("name")
    p3.set_defaults(func=cmd_export)
    a = ap.parse_args()
    if not getattr(a, "func", None):
        ap.print_help()
        return 1
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
