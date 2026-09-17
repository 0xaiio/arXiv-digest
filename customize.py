#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用户可定制项的统一读写层（被 build_report / server / profile / recommend 共用）。

三类定制
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

INTERESTS = os.path.join(HERE, "interests.json")
EXTRA_PATH = os.path.join(pu.OUT, "interests_extra.json")

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

# 人名 / 实词提取时的噪音词（首词或次词命中即丢弃）
NAME_STOP = set("""
the this that these those and or but for from with without via using use used our we you your their his her
its it is are was were be been being can could may might should would will shall not nor all any both few
own too only just about into over under again further once here there because while during before after
above below out off between among within against toward towards upon across behind beyond plus minus per
non pre post new novel approach approaches paper work works study studies show shows shown propose
proposed introduces introduced first second third also however therefore thus hence moreover furthermore
finally proceedings conference journal workshop symposium volume issue pages editors editor edition
university department institute institution laboratory labs lab college school faculty center centre
academy research group team project report technical preprint arxiv abstract introduction conclusion
references appendix figure table section chapter part springer acm ieee siam usenix
january february march april may june july august september october november december
monday tuesday wednesday thursday friday saturday sunday
""".split())

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) arxiv-digest/3.0"}

# 通用学术英语：出现频率高但没有主题区分度，不进画像
GENERIC = set("""
breaking unifying lines worlds partially trusted arbitrary number numbers achieves achieve
accelerates approaching addresses enables provides improves offers allows requires presents
discusses describes examines investigates explores applies proposes introduces combines
extends beyond toward towards across within various several different similar existing
current recent modern general specific important significant effective efficient practical
theoretical empirical comprehensive extensive detailed promising potential main major minor
overview survey review summary outline goal goals aim aims objective objectives contribution
contributions result results finding findings evaluation evaluations experiment experiments
experimental performance performances analysis analyses comparison comparisons baseline
baselines dataset datasets implementation implementations design designs tool tools
application applications problem problems solution solutions challenge challenges
case cases example examples scenario scenarios setting settings task tasks
high low large small better best good great new newer latest
""".split())

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

ARXIV_API = "http://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}


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
    return _read_json(INTERESTS, {"topics": [], "people": [], "signature_systems": []})


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
    p = os.path.join(HERE, "config.json")
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


# ---- 文本处理 ----

class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.buf = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        elif tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section"):
            self.buf.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)


def strip_html(raw):
    p = _Text()
    try:
        p.feed(raw)
    except Exception:
        pass
    txt = "".join(p.buf)
    txt = re.sub(r"[ \t\r\f\v]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt.strip()


NAME_PAIR = re.compile(r"\b([A-Z][a-z]{1,15})\s+([A-Z][a-z]{1,15})\b")


def extract_people(text, min_count=2, limit=25):
    """抽「First Last」形式且重复出现的人名（重复 = 大概率是真名字而非标题词）。"""
    freq = {}
    for m in NAME_PAIR.finditer(text or ""):
        a, b = m.group(1), m.group(2)
        if a.lower() in NAME_STOP or b.lower() in NAME_STOP:
            continue
        name = "%s %s" % (a, b)
        freq[name] = freq.get(name, 0) + 1
    items = [(n, c) for n, c in freq.items() if c >= min_count]
    items.sort(key=lambda kv: (-kv[1], kv[0]))
    return [n for n, _ in items[:limit]]


def _existing_keywords(prof):
    s = set()
    for t in prof.get("topics") or []:
        for k in t.get("keywords") or []:
            s.add(k.lower())
    for k in (prof.get("negative") or {}).get("keywords") or []:
        s.add(k.lower())
    return s


def extract_keywords(text, prof, title="", limit=14):
    """抽专业实词作为画像增量。

    过滤原则（避免把 arbitrary / achieves / number / breaking 这类泛化用词塞进主题）：
      - 排除画像里已有的关键词（含负向），避免与现有主题重复计分
      - 排除 GENERIC 通用学术词、停用词、长度 < 5 的词
      - 带连字符的术语（tee-assisted）> 标题里的长词 > 标题词 > 正文里重复出现 >= 2 次
    用户还可以在画像页上把不想要的词逐个别屏蔽（block_kw）。
    """
    import profile as PF
    have = _existing_keywords(prof)
    freq = {}
    for m in PF.TOKEN_RX.findall((text or "").lower()):
        if m in PF.STOP or m in GENERIC or len(m) < 5:
            continue
        freq[m] = freq.get(m, 0) + 1
    tset = set()
    for m in PF.TOKEN_RX.findall((title or "").lower()):
        if m not in PF.STOP and m not in GENERIC and len(m) >= 5:
            tset.add(m)
    cand = []
    for k, c in freq.items():
        if k in have:
            continue
        if "-" in k:
            # 连字符术语是最强信号，但要排掉 sub-670 / 2024-01 这类编号
            if max((len(p) for p in k.split("-")), default=0) < 4:
                continue
            tier = 4
        elif k in tset and len(k) >= 8:
            tier = 3
        elif k in tset:
            tier = 2
        elif c >= 3:
            tier = 2
        elif c >= 2:
            tier = 1
        else:
            continue
        cand.append((tier, c, k))
    cand.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return [k for _, _, k in cand[:limit]]


def matched_topics(text, prof):
    """来源文本命中了哪些现有主题（用于展示"该来源强化了什么"）。"""
    low = (text or "").lower()
    hit = []
    for t in prof.get("topics") or []:
        n = sum(1 for k in t.get("keywords") or [] if k.lower() in low)
        if n:
            hit.append((t.get("name", ""), n))
    hit.sort(key=lambda kv: -kv[1])
    return [n for n, _ in hit[:6]]


# ---- 抓取 ----

def _http_get(url, timeout=15, limit=600000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
        raw = r.read(limit)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk", "replace")


def parse_paper(value):
    """arXiv 短号 / abs 链接 / pdf 链接 -> 元数据。"""
    sid = pu.short_id(value)
    if not re.match(r"^[0-9]{4}\.[0-9]{4,5}$", sid) and not re.match(r"^[a-z\-]+/\d{7}$", sid):
        return None, "无法识别 arXiv 编号：%s" % value
    url = ARXIV_API + "?" + urllib.parse.urlencode({"id_list": sid, "max_results": 1})
    for attempt in range(3):
        try:
            root = __import__("xml.etree.ElementTree", fromlist=["x"]).fromstring(
                _http_get(url, timeout=25))
            e = root.find("a:entry", NS)
            if e is None:
                return None, "arXiv 未返回该编号：%s" % sid
            def t(p):
                n = e.find(p, NS)
                return (n.text or "").strip() if n is not None else ""
            authors = [a.find("a:name", NS).text.strip()
                       for a in e.findall("a:author", NS)
                       if a.find("a:name", NS) is not None]
            return {"title": " ".join(t("a:title").split()),
                    "text": " ".join([t("a:title"), t("a:summary"), " ".join(authors)]),
                    "authors": authors, "sid": sid}, ""
        except Exception as ex:  # noqa
            if attempt == 2:
                return None, "抓取失败：%s" % ex
            time.sleep(2)
    return None, "抓取失败"


def parse_link(value):
    url = (value or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return None, "链接需以 http:// 或 https:// 开头"
    for attempt in range(2):
        try:
            html = _http_get(url, timeout=18)
            title = ""
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
            if m:
                title = " ".join(strip_html(m.group(1)).split())[:160]
            return {"title": title or url, "text": strip_html(html)[:400000]}, ""
        except Exception as ex:  # noqa
            if attempt == 1:
                return None, "抓取失败：%s" % ex
            time.sleep(1)
    return None, "抓取失败"


TEXT_EXT = {".txt", ".md", ".markdown", ".rst", ".html", ".htm", ".csv", ".tsv",
            ".json", ".bib", ".tex", ".xml", ".yaml", ".yml", ".log"}


def parse_doc(value):
    path = os.path.expanduser((value or "").strip().strip('"')).replace("\\", "/")
    if not os.path.isfile(path):
        return None, "文件不存在：%s" % path
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    try:
        if ext == ".pdf":
            text = _read_pdf(path)
            if text is None:
                return None, "需要 pypdf 才能解析 PDF（pip install pypdf），或改用 .txt/.md"
        elif ext in (".html", ".htm"):
            text = strip_html(open(path, encoding="utf-8", errors="replace").read())
        else:
            text = open(path, encoding="utf-8", errors="replace").read()
    except Exception as ex:  # noqa
        return None, "读取失败：%s" % ex
    if not text.strip():
        return None, "文件内容为空或无法提取文本"
    return {"title": name, "text": text[:400000]}, ""


def _read_pdf(path):
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return None
    try:
        rd = PdfReader(path)
        return "\n".join((pg.extract_text() or "") for pg in rd.pages[:12])
    except Exception:
        return None


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
        "owners": prof.get("owners") or [],
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
