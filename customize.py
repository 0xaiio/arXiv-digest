#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用户可定制项的统一读写层（被 build_report / server / profile / recommend 共用）。

四类定制
  1) arXiv 类别   -> config.json 的 categories + category_names
  2) 下载目录     -> config.json 的 download_dir
  3) 兴趣来源     -> output/interests_extra.json
       type=link   个人主页 / 项目页 / 任何网页
       type=paper  arXiv 论文（短号或链接）
       type=doc    本地文档（.txt/.md/.html/.csv/.json/.pdf）
     每个来源尽力解析出「人名」与「专业实词」，作为画像的增量信号：
       人名 -> 追加到 people（命中 +10 分/人）
       实词 -> 追加到自定义主题 "我的来源关注" 的 keywords
     解析结果逐条可查、可删；删除来源即撤销其增量。
  4) 画像主来源   -> interests.json 的 owners（增 / 删 / 改）
      摘要页头部「基于 A × B × C 的兴趣画像」即取自 owners 的 label/name；
      可选择把 owner 计入 people（熟悉研究者 +10 分/篇）。

顺序不变式（重要）
  recommend.py 的 topics 顺序、profile.seed_weights() 的顺序、
  前端 papers_index / profile_snapshot 的 weights 顺序必须完全一致，
  否则前端重排会拿错权重。因此合并后的主题列表固定为：
      [interests.json 原有主题（原序）] + [自定义主题（固定 1 个）]
  两边都只走 effective_* 这组函数，不要各自拼装。
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paperutil as pu  # noqa: E402
import paths  # noqa: E402

HERE = paths.ROOT
INTERESTS = paths.INTERESTS
INTERESTS_EXAMPLE = paths.INTERESTS_EXAMPLE
# 画像骨架：字段齐全但没有内容，保证任何模块都能安全 .get()
EMPTY_PROFILE = {"owners": [], "topics": [], "people": [], "signature_systems": [],
                 "negative": {"keywords": []}, "behavior": {}}
EXTRA_PATH = paths.INTERESTS_EXTRA_PATH

# 自定义主题：承载「来源解析出的实词」，名字固定，便于两边对齐
CUSTOM_TOPIC = "我的来源关注"
CUSTOM_TOPIC_WEIGHT = 0.6
CUSTOM_TOPIC_KW_CAP = 60

CAT_RE = re.compile(r"^[a-z][a-z\-]*\.[A-Za-z][A-Za-z\-]*$")

# 常见 arXiv 分类的中文主题（新增类别时自动带出，用户可覆盖）
CS_TOPIC_DICT = {
    "cs.DB": "数据库", "cs.DC": "分布式 / 并行 / 集群计算", "cs.FL": "形式语言与自动机",
    "cs.LO": "计算逻辑", "cs.PL": "程序设计语言", "cs.SE": "软件工程",
    "cs.AR": "体系结构", "cs.CR": "密码学与安全", "cs.CC": "计算复杂性",
    "cs.DS": "数据结构与算法", "cs.NI": "网络与互联网", "cs.OS": "操作系统",
    "cs.SY": "系统与控制", "cs.GT": "博弈论与机制设计", "cs.IT": "信息论",
    "cs.MA": "多智能体系统", "cs.AI": "人工智能", "cs.LG": "机器学习",
    "cs.CL": "计算语言学", "cs.IR": "信息检索", "cs.HC": "人机交互",
    "cs.SC": "符号计算", "cs.ET": "新兴技术", "cs.CY": "计算与社会",
    "cs.DL": "数字图书馆", "cs.GL": "综合", "cs.MS": "数学软件",
    "cs.NA": "数值分析", "cs.NE": "神经与进化计算", "cs.PF": "性能",
    "cs.RO": "机器人学", "cs.SD": "声音", "cs.CV": "计算机视觉",
    "cs.GR": "图形学", "cs.MM": "多媒体", "cs.SI": "社会与信息网络",
    "cs.CE": "计算工程 / 金融 / 科学", "cs.DM": "离散数学",
    "math.LO": "数理逻辑", "math.CO": "组合数学", "math.DS": "动力系统",
    "math.IT": "信息论（数学）", "math.PR": "概率论", "math.ST": "统计理论",
    "stat.ML": "统计机器学习", "stat.ME": "统计方法论",
    "quant-ph": "量子物理", "eess.SY": "系统与控制（EESS）",
}

# 文本信号抽取与来源取数各自独立成层（见 textscan.py / fetchsrc.py）。
# 这里 re-export，保证 `customize.strip_html` / `customize.parse_link` 等既有
# 调用点（服务端、tools、测试）继续可用，调用方无需改动。
from textscan import (  # noqa: E402,F401
    GENERIC, NAME_PAIR, NAME_STOP, _existing_keywords, extract_keywords,
    extract_people, matched_topics, strip_html,
)
from fetchsrc import (  # noqa: E402,F401
    ARXIV_API, MAX_TEXT, NS, SSL_CTX, TEXT_EXT, UA, _read_pdf, is_arxiv_id, parse,
)
from fetchsrc import _http_get  # noqa: E402,F401
from fetchsrc import parse_doc as _parse_doc  # noqa: E402
from fetchsrc import parse_link as _parse_link  # noqa: E402
from fetchsrc import parse_paper as _parse_paper  # noqa: E402


# ------------------------------------------------------------------ 基础 IO

def _read_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load_interests():
    """读画像种子；不存在就按 interests.example.json 初始化一份（干净默认）。

    interests.json 属个人数据（研究方向、对标学者、熟悉作者），不进版本库；
    想用别人的现成画像，走 `python tools/preset.py import <预设名>`。
    """
    if not os.path.exists(INTERESTS):
        pu.seed_from_example(
            INTERESTS, INTERESTS_EXAMPLE, EMPTY_PROFILE,
            notice="[init] 已按 interests.example.json 生成 interests.json（画像种子）。"
                   "可在 /profile 页维护，或 `python tools/preset.py import <预设>` 导入一份示例画像。")
    return _read_json(INTERESTS, dict(EMPTY_PROFILE))


# ------------------------------------------------------------------ 类别 & 目录

def category_names():
    """{cat: 中文主题}；config 里的优先，其次内置表，最后退回分类号本身。"""
    cfg = pu.load_config()
    names = dict(CS_TOPIC_DICT)
    names.update(cfg.get("category_names") or {})
    return names


def categories():
    return list(pu.load_config().get("categories") or [])


def category_label(cat):
    return category_names().get(cat) or "（未命名主题）"


def _save_cfg_patch(patch):
    # 必须走 paperutil.CONFIG_PATH：它是「配置文件在哪」的唯一真源。
    # 早先这里写的是 os.path.join(HERE, "config.json")，与 load_config() 的读取路径
    # 各算一遍，一旦有人重定向 CONFIG_PATH（测试、多实例）就会出现「读的是 A、写的是 B」。
    p = pu.CONFIG_PATH
    cfg = _read_json(p, {})
    cfg.update(patch)
    _write_json(p, cfg)
    return pu.load_config()


def add_category(cat, name=""):
    cat = (cat or "").strip()
    if not CAT_RE.match(cat):
        return False, "分类格式不合法，应形如 cs.DB / math.LO（小写主类 + 大写子类）", None
    cfg = pu.load_config()
    cats = list(cfg.get("categories") or [])
    if cat in cats:
        return False, "分类 %s 已存在" % cat, None
    cats.append(cat)
    names = dict(cfg.get("category_names") or {})
    nm = (name or "").strip() or CS_TOPIC_DICT.get(cat, "")
    if nm:
        names[cat] = nm
    _save_cfg_patch({"categories": cats, "category_names": names})
    return True, ("已添加 %s（主题：%s）。需重新抓取（run_daily.py）才会出现该类别的论文。"
                  % (cat, nm or "未命名")), {"cat": cat, "name": nm or cat}


def remove_category(cat):
    cat = (cat or "").strip()
    cfg = pu.load_config()
    cats = list(cfg.get("categories") or [])
    if cat not in cats:
        return False, "分类 %s 不存在" % cat, None
    if len(cats) <= 1:
        return False, "至少要保留一个分类", None
    cats = [c for c in cats if c != cat]
    names = dict(cfg.get("category_names") or {})
    names.pop(cat, None)
    _save_cfg_patch({"categories": cats, "category_names": names})
    return True, "已移除 %s（已抓取的旧数据会在下次 run_daily.py 后消失）" % cat, {"cat": cat}


def download_dir():
    return pu.load_config().get("download_dir", "")


def set_download_dir(path):
    path = (path or "").strip().strip('"')
    if not path:
        return False, "目录不能为空", None
    path = os.path.expanduser(path).replace("\\", "/")
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        return False, "无法创建目录：%s" % e, None
    if not os.path.isdir(path):
        return False, "不是有效目录：%s" % path, None
    _save_cfg_patch({"download_dir": path})
    return True, "下载目录已更新为 %s（立即生效，无需重抓）" % path, {"download_dir": path}


# ------------------------------------------------------------------ 兴趣来源

def empty_extra():
    return {"sources": [],
            "_derived": {"people": [], "keywords": [], "matched_topics": []},
            "block_kw": [], "updated_at": ""}


def load_extra():
    d = _read_json(EXTRA_PATH, empty_extra())
    d.setdefault("sources", [])
    d.setdefault("block_kw", [])
    d.setdefault("_derived", {"people": [], "keywords": [], "matched_topics": []})
    return d


def save_extra(d):
    d["updated_at"] = pu.now_str()
    _write_json(EXTRA_PATH, d)


# ---- 来源取数的注入型包装 ----
# 为什么不直接 re-export 函数本身：单测会 patch `customize._http_get` 来避免联网。
# 包装在这里显式把**本模块的** `_http_get` 传下去，因此 patch 本模块仍然生效；
# 同时 patch `fetchsrc._http_get` 也生效（那是默认值）。两种写法都兼容。

def parse_paper(value):
    """arXiv 短号 / abs 链接 / pdf 链接 -> 元数据。"""
    return _parse_paper(value, _get=_http_get)


def parse_link(value):
    """任意网页 -> {title, text}。"""
    return _parse_link(value, _get=_http_get)


def parse_doc(value):
    """本地文档（文本类 / PDF）-> {title, text}。"""
    return _parse_doc(value)


def derive(src, prof):
    """解析一个来源，返回 {people, keywords, matched_topics, title} 或 {'error': ...}。"""
    typ = src.get("type")
    val = src.get("value", "")
    if typ == "paper":
        meta, err = parse_paper(val)
    elif typ == "link":
        meta, err = parse_link(val)
    elif typ == "doc":
        meta, err = parse_doc(val)
    else:
        return {"error": "未知来源类型 %s" % typ}
    if err:
        return {"error": err}
    text = meta.get("text", "")
    # 论文来源的作者是确定信号，直接采信；link/doc 靠重复出现筛
    people = [a for a in (meta.get("authors") or [])]
    if typ != "paper":
        people = extract_people(text, min_count=2)
    return {
        "title": meta.get("title", ""),
        "people": people[:30],
        "keywords": extract_keywords(text, prof, meta.get("title", "")),
        "matched_topics": matched_topics(text, prof),
    }


def rebuild(extra=None):
    """重算所有来源的汇总增量（people / keywords / matched_topics）。"""
    extra = extra if extra is not None else load_extra()
    prof = load_interests()
    have_people = {p.lower() for p in (prof.get("people") or [])}
    have_kw = _existing_keywords(prof)
    blocked = {k.lower() for k in (extra.get("block_kw") or [])}
    people, keywords, topics, seen_kw = [], [], [], set()
    for s in extra["sources"]:
        d = s.get("derived") or {}
        for p in d.get("people") or []:
            if p.lower() in have_people:
                continue
            if p not in people:
                people.append(p)
        for k in d.get("keywords") or []:
            if k in have_kw or k in seen_kw or k.lower() in blocked:
                continue
            seen_kw.add(k)
            keywords.append(k)
        for t in d.get("matched_topics") or []:
            if t not in topics:
                topics.append(t)
    extra["_derived"] = {"people": people[:60],
                         "keywords": keywords[:CUSTOM_TOPIC_KW_CAP],
                         "matched_topics": topics[:10]}
    return extra


def block_keyword(kw, on=True):
    """屏蔽 / 恢复某个来自来源的关键词。"""
    kw = (kw or "").strip()
    if not kw:
        return False, "缺少关键词", None
    extra = load_extra()
    cur = list(extra.get("block_kw") or [])
    low = {k.lower() for k in cur}
    if on:
        if kw.lower() not in low:
            cur.append(kw)
    else:
        cur = [k for k in cur if k.lower() != kw.lower()]
    extra["block_kw"] = cur
    rebuild(extra)
    save_extra(extra)
    return True, ("已屏蔽关键词 %s" % kw) if on else ("已恢复关键词 %s" % kw), None


def add_source(typ, value, note=""):
    value = (value or "").strip()
    if not value:
        return False, "内容不能为空", None
    extra = load_extra()
    for s in extra["sources"]:
        if s.get("type") == typ and s.get("value") == value:
            return False, "该来源已存在", None
    prof = load_interests()
    src = {"sid": "s%d" % (int(time.time() * 1000)),
           "type": typ, "value": value, "note": (note or "").strip(),
           "added_at": pu.now_str()}
    src["derived"] = derive(src, prof)
    extra["sources"].append(src)
    rebuild(extra)
    save_extra(extra)
    if src["derived"].get("error"):
        return True, "已添加，但解析失败：%s（条目已保留，可稍后重试或删除）" % src["derived"]["error"], src
    n_p = len(src["derived"].get("people") or [])
    n_k = len(src["derived"].get("keywords") or [])
    return True, "已添加并解析出 %d 个人名、%d 个关键词" % (n_p, n_k), src


def remove_source(sid):
    extra = load_extra()
    before = len(extra["sources"])
    extra["sources"] = [s for s in extra["sources"] if s.get("sid") != sid]
    if len(extra["sources"]) == before:
        return False, "未找到该来源", None
    rebuild(extra)
    save_extra(extra)
    return True, "已删除该来源及其全部增量", None


def refresh_all():
    """重跑所有来源的解析（例如画像主题改过之后）。"""
    extra = load_extra()
    prof = load_interests()
    for s in extra["sources"]:
        s["derived"] = derive(s, prof)
    rebuild(extra)
    save_extra(extra)
    return True, "已重新解析 %d 个来源" % len(extra["sources"]), extra


# ------------------------------------------------------------------ 画像主来源
# 「画像主来源」= interests.json 的 owners：画像页顶部的几张卡片，
# 也是摘要页顶部「基于 A × B × C 的兴趣画像」这行文案的来源。
# 它此前只能手改 interests.json，这里补上增 / 删 / 改的统一入口。
#
# 与「熟悉研究者」(people) 的联动：owner 可选择同步进 people（命中 +10 分/篇）。
# 打标 people_linked 记录该名字是「跟着 owner 加进来的」，删 owner / 取消勾选时
# 才会把它撤掉，不会误删用户自己手写的熟悉研究者。

OWNER_TEXT_FIELDS = ("name", "label", "site", "affiliation", "interests")


def owners():
    return list(load_interests().get("owners") or [])


def _people_add(lst, name):
    if not name:
        return lst
    low = {x.lower() for x in lst}
    return lst if name.lower() in low else lst + [name]


def _people_drop(lst, name):
    return [x for x in lst if x.lower() != (name or "").strip().lower()]


def _clean_owner(data):
    o = {k: (data.get(k) or "").strip() for k in OWNER_TEXT_FIELDS}
    topics = data.get("signature_topics") or []
    if isinstance(topics, str):
        topics = topics.splitlines()
    o["signature_topics"] = [s.strip(" \t-·•") for s in topics if s and s.strip()]
    return o


def _owner_check(o, owners, skip_name=""):
    """校验一条 owner；返回错误串或 ""。"""
    if not o["name"]:
        return "姓名不能为空"
    if o["site"] and not o["site"].lower().startswith(("http://", "https://")):
        return "主页链接需以 http:// 或 https:// 开头"
    for x in owners:
        nm = (x.get("name") or "")
        if nm.lower() == o["name"].lower() and nm.lower() != (skip_name or "").lower():
            return "画像主来源已存在：%s" % o["name"]
    return ""


def _owner_save(prof):
    _write_json(INTERESTS, prof)
    return prof.get("owners") or []


def add_owner(data, link_person=True):
    o = _clean_owner(data)
    prof = load_interests()
    owners = list(prof.get("owners") or [])
    err = _owner_check(o, owners)
    if err:
        return False, err, None
    o["people_linked"] = bool(link_person)
    owners.append(o)
    prof["owners"] = owners
    if o["people_linked"]:
        prof["people"] = _people_add(list(prof.get("people") or []), o["name"])
    _owner_save(prof)
    return True, ("已添加画像主来源 %s。点工具栏「↻ 重算推荐」后，摘要页头部与作者加成同步更新。"
                  % o["name"]), o


def update_owner(orig, data, link_person=None):
    """按原姓名 orig 定位并整条覆盖；允许改名。link_person=None 表示保持原联动状态。"""
    orig = (orig or "").strip()
    prof = load_interests()
    owners = list(prof.get("owners") or [])
    idx = next((i for i, x in enumerate(owners)
                if (x.get("name") or "").lower() == orig.lower()), -1)
    if idx < 0:
        return False, "未找到画像主来源：%s" % (orig or "（空）"), None
    old = owners[idx]
    o = _clean_owner(data)
    err = _owner_check(o, owners, skip_name=orig)
    if err:
        return False, err, None

    prev_linked = bool(old.get("people_linked"))
    new_linked = prev_linked if link_person is None else bool(link_person)
    renamed = (old.get("name") or "").lower() != o["name"].lower()
    people = list(prof.get("people") or [])
    if prev_linked and (renamed or not new_linked):
        people = _people_drop(people, old.get("name"))
    if new_linked:
        people = _people_add(people, o["name"])

    o["people_linked"] = new_linked
    owners[idx] = o
    prof["owners"] = owners
    prof["people"] = people
    _owner_save(prof)
    return True, "已更新画像主来源 %s%s。" % (
        o["name"], "（原 %s）" % orig if renamed else ""), o


def remove_owner(name):
    name = (name or "").strip()
    prof = load_interests()
    owners = list(prof.get("owners") or [])
    hit = next((x for x in owners if (x.get("name") or "").lower() == name.lower()), None)
    if hit is None:
        return False, "未找到画像主来源：%s" % (name or "（空）"), None
    owners = [x for x in owners if x is not hit]
    if not owners:
        return False, "至少要保留一个画像主来源", None
    prof["owners"] = owners
    if hit.get("people_linked"):
        prof["people"] = _people_drop(list(prof.get("people") or []), hit.get("name"))
    _owner_save(prof)
    return True, "已删除画像主来源 %s（其熟悉研究者加成同时撤销）。" % name, None


def owners_view():
    """画像页渲染用：只暴露前端要用的字段。"""
    out = []
    for o in owners():
        out.append({
            "name": o.get("name", ""),
            "label": o.get("label", ""),
            "site": o.get("site", ""),
            "affiliation": o.get("affiliation", ""),
            "interests": o.get("interests", ""),
            "signature_topics": list(o.get("signature_topics") or []),
            "people_linked": bool(o.get("people_linked")),
        })
    return out


# ------------------------------------------------------------------ 画像合并

def effective_topics(prof=None):
    """合并后的主题列表：原画像主题（原序）+ 自定义主题。顺序即权重索引顺序。"""
    prof = prof or load_interests()
    out = []
    for t in prof.get("topics") or []:
        out.append({"name": t.get("name", ""),
                    "weight": float(t.get("weight", 1.0)),
                    "keywords": list(t.get("keywords") or []),
                    "seed": float(t.get("weight", 1.0)),
                    "custom": False})
    kws = (load_extra().get("_derived") or {}).get("keywords") or []
    if kws:
        out.append({"name": CUSTOM_TOPIC, "weight": CUSTOM_TOPIC_WEIGHT,
                    "keywords": kws, "seed": CUSTOM_TOPIC_WEIGHT, "custom": True})
    return out


def effective_people(prof=None):
    prof = prof or load_interests()
    base = list(prof.get("people") or [])
    have = {p.lower() for p in base}
    for p in (load_extra().get("_derived") or {}).get("people") or []:
        if p.lower() not in have:
            base.append(p)
            have.add(p.lower())
    return base


def effective_systems(prof=None):
    prof = prof or load_interests()
    return list(prof.get("signature_systems") or [])


def effective_seed_weights():
    """[(主题名, 种子权重)] —— 与 effective_topics 严格同序。"""
    return [(t["name"], t["seed"]) for t in effective_topics()]


def sources_view():
    """给前端用的来源列表（含解析结果摘要）。"""
    extra = load_extra()
    out = []
    for s in extra["sources"]:
        d = s.get("derived") or {}
        out.append({
            "sid": s.get("sid"), "type": s.get("type"), "value": s.get("value"),
            "note": s.get("note", ""), "added_at": s.get("added_at", ""),
            "title": d.get("title", ""),
            "error": d.get("error", ""),
            "people": (d.get("people") or [])[:12],
            "keywords": (d.get("keywords") or [])[:14],
            "matched_topics": d.get("matched_topics") or [],
        })
    out.sort(key=lambda x: x.get("added_at", ""), reverse=True)
    return out


def snapshot():
    """定制项总览（给 /api/state 与画像页用）。"""
    extra = load_extra()
    return {
        "categories": categories(),
        "category_names": {c: category_label(c) for c in categories()},
        "download_dir": download_dir(),
        "sources": sources_view(),
        "derived": extra.get("_derived") or {},
        "blocked_keywords": list(extra.get("block_kw") or []),
        "updated_at": extra.get("updated_at", ""),
    }


def profile_view():
    """画像页/接口需要的完整画像视图（主题顺序 = 权重索引顺序，不要重排）。"""
    import profile as PF  # 延迟导入，避免循环
    prof = load_interests()
    st = PF.load()
    themes = []
    for t in effective_topics(prof):
        mult = float(st.get("topic_mult", {}).get(t["name"], 1.0))
        seed = float(t.get("seed", t.get("weight", 1.0)))
        themes.append({
            "name": t["name"],
            "seed": round(seed, 3),
            "mult": round(mult, 3),
            "weight": round(seed * mult, 3),
            "nkw": len(t["keywords"]),
            "keywords": list(t["keywords"])[:36],
            "custom": bool(t.get("custom")),
        })
    neg = prof.get("negative") or {}
    return {
        "owners": owners_view(),
        "themes": themes,
        "people": effective_people(prof),
        "systems": effective_systems(prof),
        "negative": list(neg.get("keywords") or []),
        "counts": st.get("counts") or {},
        "downvoted": [k for k, v in (st.get("paper_bonus") or {}).items() if v < 0],
        "updated_at": st.get("updated_at", ""),
    }


def view():
    """画像页一次性取数：定制项 + 画像。"""
    d = snapshot()
    d["profile"] = profile_view()
    return d


if __name__ == "__main__":
    print(json.dumps(snapshot(), ensure_ascii=False, indent=1)[:4000])
