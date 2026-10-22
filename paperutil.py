#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""论文命名与本地库（收藏/下载）工具函数，被 build_report.py 与 server.py 共用。"""
import json
import os
import re
import time

import paths
import serveport

HERE = paths.ROOT
# 路径取值统一来自 paths.py（唯一权威定义）。这里保留同名模块级常量，
# 既方便阅读，也保持「按模块属性 monkeypatch 重定向」这一既有测试约定。
OUT = paths.OUT
CONFIG_PATH = paths.CONFIG_PATH
CONFIG_EXAMPLE = paths.CONFIG_EXAMPLE

# 最后兜底（config.example.json 也缺失时才用）。刻意不含任何本机路径与个人分类：
# 新用户拿到的是「干净默认」，个人设置走 presets/ 或自己改 config.json。
# categories 为空 = 通用版：用户首次打开在 /profile 里自选 arXiv 分类（155 个官方分类可选）。
DEFAULT_CONFIG = {
    "download_dir": "papers",
    "categories": [],
    "window_days": 3,
    "max_results_per_cat": 80,
    "top_recommend": 14,
    "port": 8765,
    "open_browser": True,
}

# ---------------------------------------------------------------- 运行期端口
# 服务实际监听的端口可能与 config.port 不同（默认端口被占用时会自动顺延，
# 见 serveport.find_free_port）。页面里的 APIBASE 必须指向**实际**端口，否则
# 顺延之后收藏/下载/Downvote 会打到旧端口，表现为「点了没反应」。
#
# 为什么放在本模块：build_report 会在每个请求里被 importlib.reload（代码改动即时
# 生效），模块级变量会被重置；paperutil 只被导入、不会被 reload，这个值才留得住。
RUNTIME_PORT = None


def set_runtime_port(port):
    """记录本进程实际监听的端口（None = 不知道，按 config.port 走）。"""
    global RUNTIME_PORT
    RUNTIME_PORT = serveport.valid_port(port)
    return RUNTIME_PORT


def effective_port(cfg=None):
    """页面应该指向的端口：运行期实际端口 > config.port > 默认 8765。

    非法配置（手写坏了、字符串、超范围）一律回落默认值，不让下游崩掉。
    """
    if RUNTIME_PORT:
        return RUNTIME_PORT
    return serveport.configured_port(cfg if isinstance(cfg, dict) else load_config())


def seed_from_example(target, example, fallback=None, notice=""):
    """目标文件不存在时，用同目录的 *.example.json 生成一份。

    这样仓库里只需要提交「模板」，而 config.json / interests.json 属于每个用户的
    个人数据（含本机路径与画像），既不进版本库，也不会在别人 clone 后带着我的痕迹。
    返回 True 表示这次真的初始化了。
    """
    if os.path.exists(target):
        return False
    data = fallback or {}
    try:
        if os.path.exists(example):
            with open(example, encoding="utf-8") as f:
                data = json.load(f)
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        tmp = "%s.%d.tmp" % (target, os.getpid())
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, target)
    except Exception:
        return False
    if notice:
        try:
            print(notice)
        except Exception:
            pass
    return True


def load_config():
    """读 config.json；不存在就按 config.example.json 初始化一份（干净默认）。"""
    if not os.path.exists(CONFIG_PATH):
        seed_from_example(
            CONFIG_PATH, CONFIG_EXAMPLE, DEFAULT_CONFIG,
            notice="[init] 已按 config.example.json 生成 config.json。"
                   "categories 默认为空：请在 /profile 的「arXiv 类别」面板里自选，"
                   "或 `python run_daily.py --categories cs.DB,cs.DC` 指定；"
                   "download_dir（PDF 保存目录）也可在那里改。")
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            cfg.update(json.load(open(CONFIG_PATH, encoding="utf-8")))
        except Exception:
            pass
    if not isinstance(cfg.get("categories"), list):
        cfg["categories"] = []
    return cfg


def short_id(p):
    """从 arXiv id / paper dict 取出短号（如 2609.01234，去掉版本号）。

    接受的形态：纯短号、带版本、`arXiv:2609.01234v2` 前缀、abs/pdf 链接、前后空白。
    库文件与接口的 key 都由此产生，所以这一步必须幂等且不抛异常。
    """
    s = p if isinstance(p, str) else (p.get("id") or "")
    s = (s or "").strip()
    s = s.rsplit("/", 1)[-1].strip()
    s = re.sub(r"^arxiv:\s*", "", s, flags=re.I)
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

LIB_PATH = paths.LIB_PATH


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
