#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""论文命名与本地库（收藏/下载）工具函数，被 build_report.py 与 server.py 共用。"""
import json
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
CONFIG_PATH = os.path.join(HERE, "config.json")

DEFAULT_CONFIG = {
    "download_dir": "D:/git-papers/arXiv",
    "categories": ["cs.DB", "cs.DC", "cs.FL", "cs.LO", "cs.PL", "cs.SE"],
    "window_days": 3,
    "max_results_per_cat": 80,
    "top_recommend": 14,
    "port": 8765,
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            cfg.update(json.load(open(CONFIG_PATH, encoding="utf-8")))
        except Exception:
            pass
    return cfg


def short_id(p):
    """从 arXiv id / paper dict 取出短号（如 2609.01234，去掉版本号）。"""
    s = p if isinstance(p, str) else (p.get("id") or "")
    s = s.rsplit("/", 1)[-1]
    return re.sub(r"v\d+$", "", s)


_ILLEGAL = r'<>:"/\|?*'
_KEEP_SOFT = "-_."


def clean_title(title, maxlen=110):
    """去除标点符号：保留中英文、数字、空格、连字符、下划线与句点。"""
    t = (title or "").strip()
    t = re.sub(r"[’‘“”`']", "", t)                 # 引号/撇号直接删除
    t = re.sub(r"[\\/:*?\"<>|#&$%@^~]", " ", t)    # 非法/杂符 -> 空格
    t = re.sub(r"[,;:!?()\[\]{}<>]", " ", t)       # 标点 -> 空格
    t = re.sub(r"\s+", " ", t).strip()
    t = t.strip(" ").rstrip(".").strip()
    if len(t) > maxlen:
        cut = t[:maxlen]
        sp = cut.rfind(" ")
        t = (cut[:sp] if sp > maxlen * 0.6 else cut).rstrip(" .-_")
    return t


def build_filename(sid, title, year=None):
    """arXiv<年> <arXiv号> <去标点标题>.pdf"""
    year = year or str(time.localtime().tm_year)
    sid = short_id(sid)
    return "arXiv%s %s %s.pdf" % (year, sid, clean_title(title))


# ---------------- 本地库 ----------------

LIB_PATH = os.path.join(OUT, "library.json")


def load_library():
    if os.path.exists(LIB_PATH):
        try:
            d = json.load(open(LIB_PATH, encoding="utf-8"))
            d.setdefault("favorites", {})
            d.setdefault("downloads", {})
            d.setdefault("downvotes", {})
            return d
        except Exception:
            pass
    return {"favorites": {}, "downloads": {}, "downvotes": {}}


def save_library(lib):
    os.makedirs(OUT, exist_ok=True)
    tmp = LIB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    os.replace(tmp, LIB_PATH)


def paper_meta(p):
    return {
        "id": short_id(p),
        "title": p.get("title", ""),
        "authors": p.get("authors", []),
        "abstract": p.get("abstract", ""),
        "published": p.get("published", ""),
        "primary": p.get("primary") or p.get("queried_cat", ""),
        "cats": p.get("cats", []),
        "pdf": p.get("pdf", ""),
        "comment": p.get("comment", ""),
    }


def now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def load_papers():
    """加载最近一次抓取的全部论文（核心 + 兴趣扩展），返回 {short_id: paper}。"""
    idx = {}
    for name in ("raw.json", "raw_expand.json"):
        p = os.path.join(OUT, name)
        if not os.path.exists(p):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
            for x in d.get("papers", []):
                idx.setdefault(short_id(x), x)
        except Exception:
            pass
    return idx
