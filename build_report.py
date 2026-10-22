#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染 arXiv 论文摘要页（v5，双语简介 + 双语摘要）。

v5 变更
  - 论文**简介**统一为双语：上方英文（优先复用摘要原句）、下方对应中文；
    历史单语条目按是否含汉字自动归位，缺失的一侧用摘要开头兜底；
  - 论文**摘要**拆成英文与中文两版：`Abstract (EN)` 与 `Abstract (CH)` 两个按钮，
    中文译文来自 `output/abstracts_zh.json`，互斥展开；
  - Markdown 导出同步为双语（`- EN …` / `- 中 …`）。

v4 变更
  - 不再假定 cs.* 六分类：分类完全由 config.json 决定（用户在 /profile 里自选），
    页面标题、分类小节、统计卡片、Markdown 标题都随之变化；
  - 分类小节的顺序 = config.json 里 categories 的顺序（支持界面拖拽排序）；
  - categories 为空时渲染「欢迎 / 选择类别」引导页，而不是报错。

v3 能力
  - 🎯 为你推荐（主分类 feed 内） 与  🌱 兴趣扩展（主分类之外的邻域分类）
  - 每篇论文：收藏 / 下载 / Abstract (EN) / Abstract (CH)（内联展开折叠）/ PDF / Downvote
  - Downvote 在「为你推荐 / 兴趣扩展 / 分类详解」三处表现统一：变灰 + 标题删除线，
    卡片保留原位、不消失，可再点一次撤销（三处共用同一组 CSS 规则与同一段 JS）
  - 所有交互行为都会回传本地服务，实时更新兴趣画像；按钮乐观更新，重排合并执行
  - 顶部分类统计为可跳转锚点

输入（output/ 下）
  raw.json  raw_expand.json  papers_index.json  recommend.json  expand.json
  summaries.json  abstracts_zh.json  rec_notes.json  themes.json  highlights.json
  library.json
输出
  output/arxiv_digest_<YYYYMMDD>.html / .md     output/favorites.html
"""
import collections
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paperutil as pu  # noqa: E402
import paths  # noqa: E402
import arxiv_cats  # noqa: E402

OUT = pu.OUT

# ---------------------------------------------------------------- 模板加载
# 这些模板原先以三引号字符串内联在本文件里，占了 1400 行，导致「逻辑」与「版面」
# 混在一起：改一行 CSS 要在 1600 行里翻，Python 的 %-格式化还会吃掉内联 JS 里的
# 反斜杠与百分号（历史事故：`join('\n')` 被 Python 解析成真换行，整段脚本语法错误，
# 页面正常渲染但所有按钮失效）。现在模板是独立文件，可单独 lint、单独 diff。
#
# 缓存按 mtime 判断：改模板后**不需要重启服务**（旧实现靠请求里 importlib.reload
# 整个模块来刷新，既有竞态又慢）。文件小（十几 KB），mtime 命中时零 IO。
_TEMPLATE_DIR = paths.under_root("templates")
_TEMPLATE_CACHE = {}


def read_template(name):
    """读 templates/<name>，按 mtime 缓存。模板缺失属于安装损坏，直接报清楚。"""
    path = os.path.join(_TEMPLATE_DIR, name)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        raise SystemExit("模板文件缺失：%s（仓库不完整，请重新 clone 或 git checkout .）" % path)
    hit = _TEMPLATE_CACHE.get(name)
    if hit and hit[0] == mtime:
        return hit[1]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    _TEMPLATE_CACHE[name] = (mtime, text)
    return text


# 类别中文主题名来自 config.json 的 category_names（经 customize 与内置表合并），
# 支持在页面上增删类别；缓存一份避免每张卡片都读盘。
_CAT_NAMES = None


def cat_name(c):
    global _CAT_NAMES
    if _CAT_NAMES is None:
        try:
            import customize as CZ
            _CAT_NAMES = CZ.category_names()
        except Exception:
            _CAT_NAMES = {}
    return _CAT_NAMES.get(c) or c


def invalidate_cat_names():
    global _CAT_NAMES
    _CAT_NAMES = None


def ordered_categories(cats):
    """按 config.json 的 categories 顺序排列抓取快照里的分类。

    为什么需要这一步：分类顺序是用户可以拖拽调整的（/profile → arXiv 类别），
    但页面数据来自 `raw.json` 的抓取快照。不重新排序的话，拖完顺序要点「↻ 重算推荐」
    也看不到变化（快照里的顺序没变）。这里以「配置顺序优先、快照里多出来的追加在后」
    的规则合并，既尊重用户排序，也不会让手改过的快照丢分类。
    """
    cats = [c for c in (cats or []) if c]
    try:
        import customize as CZ
        want = [c for c in CZ.categories() if c in cats]
    except Exception:  # noqa
        want = []
    if not want:
        return cats
    return want + [c for c in cats if c not in want]

# 推荐 / 扩展 卡片池大小（用于前端实时重排时"替补上位"）
POOL_CORE = 24
POOL_EXPAND = 16


def jload(name, default):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        return default
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default


def esc(x):
    return html.escape(str(x or ""))


def short_authors(p, n=4):
    a = p.get("authors") or []
    if not a:
        return ""
    if len(a) <= n:
        return ", ".join(a)
    return ", ".join(a[:n]) + " 等 %d 人" % len(a)


def abs_url(sid):
    return "https://arxiv.org/abs/%s" % sid


def pdf_url(sid):
    return "https://arxiv.org/pdf/%s" % sid


# 作者单位（fetch_affil.py 产出，跨日累积）。arXiv API 不提供 affiliation，
# 只能从 arXiv HTML 版 / ar5iv 解析，拿不到就不渲染该行。
AFF = {}

# 英文摘要的**中文译文**（output/abstracts_zh.json，短号 -> 译文）。
# 与 AFF 同样按请求加载一次：它是可选编辑内容，缺失时页面退化成只给英文摘要，
# 而不是报错（新用户 clone 下来没有这个文件）。
ABS_ZH = {}


def load_abstracts_zh():
    global ABS_ZH
    ABS_ZH = jload("abstracts_zh.json", {}) or {}


def load_affiliations():
    global AFF
    AFF = jload("affiliations.json", {}) or {}


def aff_units(sid):
    a = AFF.get(pu.short_id(sid)) or {}
    return [u for u in (a.get("units") or []) if u]


def aff_line(sid, cls="rec-u"):
    units = aff_units(sid)
    if not units:
        return ""
    shown = "；".join(units[:3])
    more = "" if len(units) <= 3 else " 等 %d 家" % len(units)
    return ('<div class="%s" title="%s">🏛 %s%s</div>'
            % (cls, esc("；".join(units)), esc(shown), esc(more)))


# ---------------------------------------------------------------- 数据组装

def load():
    # 优先读「本期新增」子集（recommend.py 产出）：日报只呈现当天新出现的论文，
    # 历史内容已归档到 output/archive/ 与 archive.db，按日期回看。
    d = jload("issue_core.json", None)
    if not (d and "papers" in d and d.get("issue_date")):
        d = jload("raw.json", None)          # 兼容旧产物（尚未跑过新版 recommend.py）
        if not d or not d.get("papers"):
            raise SystemExit("output/raw.json 缺失或为空，请先运行 fetch_arxiv.py")
    load_affiliations()
    load_abstracts_zh()
    invalidate_cat_names()
    if d.get("categories"):
        d["categories"] = ordered_categories(d["categories"])
    lib = pu.load_library()
    summaries = jload("summaries.json", {})
    rec = jload("recommend.json", [])
    exp = jload("expand.json", [])
    idx = jload("papers_index.json", None)
    themes = jload("themes.json", [])
    highs = jload("highlights.json", {})

    # 主题归纳（themes.json）是编辑性内容，写的时候针对的是当时那批论文。
    # 日报只呈现本期新增，因此这里把引用了往期论文的主题剔除，避免旧主题、
    # 旧编号（cs.DC#8 之类）与失效锚点混进当期页面。
    cur_ids = {pu.short_id(p) for p in d["papers"]}
    if themes:
        kept = []
        for t in themes:
            refs = [r for r in (t.get("refs") or []) if r in cur_ids]
            if refs:
                kept.append(dict(t, refs=refs))
        themes = kept

    groups = collections.defaultdict(list)
    for p in d["papers"]:
        sid = pu.short_id(p)
        p["_sid"] = sid
        k = p.get("primary") if p.get("primary") in d.get("categories", []) else p.get("queried_cat")
        groups[k].append(p)
    for k in groups:
        groups[k].sort(key=lambda p: p.get("published", ""), reverse=True)

    by_sid = {}
    for cat in d.get("categories", []):
        for i, p in enumerate(groups.get(cat, []), 1):
            key = "%s#%d" % (cat, i)
            p["_key"] = key
            # 简介按「英文在上、中文在下」双语呈现：value 可以是 {"en","zh"}，
            # 也可以是历史单语字符串（按是否含汉字归位）。见 pu.split_bilingual。
            en, zh = pu.split_bilingual(
                summaries.get(key) or summaries.get(pu.short_id(p)) or "")
            p["_summary"] = zh
            p["_summary_en"] = en
            p["_hl"] = (highs.get(key) or highs.get(pu.short_id(p)) or "").strip()
            by_sid[pu.short_id(p)] = p
    return d, groups, by_sid, rec, exp, themes, lib, idx


# ---------------------------------------------------------------- 组件

# 摘要拆成两个按钮：EN 是 arXiv 原文，CH 是它的中文译文（来自 abstracts_zh.json）。
# 两者互斥展开（见 app.js 的 toggleAbs），同时展开会把卡片撑成两倍高。
ACTS = ('<div class="acts">'
        '<button class="btn fav" data-act="fav" data-sid="{sid}">'
        '<span class="ico">☆</span><span class="lb">收藏</span></button>'
        '<button class="btn dl" data-act="dl" data-sid="{sid}">'
        '<span class="ico">⬇</span><span class="lb">下载</span></button>'
        '<button class="btn ab" data-act="abs" data-sid="{sid}">'
        '<span class="ico">▸</span><span class="lb">Abstract (EN)</span></button>'
        '<button class="btn ab abz" data-act="abszh" data-sid="{sid}">'
        '<span class="ico">▸</span><span class="lb">Abstract (CH)</span></button>'
        '<a class="btn ghost pdf" data-sid="{sid}" href="{pdf}" target="_blank" rel="noopener">PDF</a>'
        '<button class="btn dv" data-act="dv" data-sid="{sid}" title="不感兴趣：以后减少推荐">'
        '<span class="ico">👎</span><span class="lb">Downvote</span></button>'
        '</div>')


def acts(sid):
    return ACTS.format(sid=esc(sid), pdf=esc(pdf_url(sid)))


def abst_block(sid, abstract):
    """英文摘要 + 中文译文两个折叠块（互斥展开，由 app.js 控制）。

    中文译文缺时不隐藏按钮，而是展开后给一句可操作的提示：按钮消失会让人以为
    这篇没有中文版；写明去哪里补，才是可自愈的。
    """
    zh = (ABS_ZH.get(pu.short_id(sid)) or "").strip()
    hint = "（本篇还没有中文摘要译文：可在 output/abstracts_zh.json 里按短号补写）"
    return ('<div class="abst" id="ab-%s"><div class="abst-in">%s</div></div>'
            '<div class="abst zh" id="abz-%s"><div class="abst-in">%s</div></div>'
            % (esc(sid), esc((abstract or "").strip() or "(无摘要)"),
               esc(sid), esc(zh or hint)))


def summ_lines(en, zh, abstract=""):
    """简介的双语两行：上英文、下中文。

    英文优先复用摘要里的原始句子（`summaries.json` 没写 `en` 时，用
    `pu.en_excerpt` 取摘要开头若干完整句子兜底），中文是它的对应译文。
    只有一侧有内容时就只渲染那一行——双语是目标，但缺一半不该显示空行。
    """
    en = (en or "").strip() or pu.en_excerpt(abstract)
    zh = (zh or "").strip()
    if not en and not zh:
        return ""
    if not zh:
        return '<span class="s-en">%s</span>' % esc(en)
    if not en:
        return '<span class="s-zh">%s</span>' % esc(zh)
    return ('<span class="s-en">%s</span><span class="s-zh">%s</span>'
            % (esc(en), esc(zh)))


def tier_cls(tier):
    return {"强烈推荐": "t1", "推荐": "t2"}.get(tier, "t3")


def build_card(item, i, note_default=""):
    """推荐 / 扩展列表中的一张卡片。"""
    sid = item["id"]
    topics = "".join('<span class="tp">%s</span>' % esc(t) for t in item.get("topics", [])[:4])
    fam = "".join('<span class="tp au">%s</span>' % esc(a) for a in item.get("familiar_authors", [])[:3])
    # 双语简介（英文在上 / 中文在下）；两侧都没有时用摘要开头兜底成英文一行。
    summ = summ_lines(item.get("summary_en"), item.get("summary"), item.get("abstract", ""))
    why = (item.get("note") or note_default or "").strip()
    return (
        '<div class="rec-card" data-sid="%s" data-score="%.2f">'
        '<div class="rec-no">%02d</div>'
        '<div class="rec-main">'
        '<div class="rec-head"><span class="tier %s">%s</span><span class="score">%.1f</span>'
        '<span class="tag">%s</span><span class="date">%s</span></div>'
        '<a class="rec-t" href="%s" target="_blank" rel="noopener">%s</a>'
        '<div class="rec-a">%s · <code>%s</code></div>'
        '%s'
        '<div class="rec-s">%s</div>'
        '<div class="rec-why"><b>推荐理由：</b>%s</div>'
        '<div class="rec-tp">%s%s</div>'
        '%s%s'
        '</div></div>'
        % (esc(sid), item.get("score", 0), i, tier_cls(item.get("tier", "")),
           esc(item.get("tier") or "推荐"), item.get("score", 0),
           esc(item.get("primary") or ""), esc(item.get("published") or ""),
           esc(pdf_url(sid)), esc(item.get("title") or ""),
           esc(short_authors(item)), esc(sid), aff_line(sid), summ, esc(why),
           topics, fam, acts(sid), abst_block(sid, item.get("abstract", "")))
    )


def build_pool_cards(pool, limit, cls_extra=""):
    """把候选池渲染成卡片；超出 limit 的先隐藏，供前端重排时替补。"""
    out = []
    for i, it in enumerate(pool, 1):
        card = build_card(it, i)
        if i > limit:
            card = card.replace('class="rec-card"', 'class="rec-card hidden"', 1)
        out.append(card)
    return "".join(out)


def build_sections(d, groups, themes, by_sid):
    cats = d.get("categories", [])
    secs = []
    for c in cats:
        ps = groups.get(c, [])
        hi = [p for p in ps if p.get("_hl")]
        hl = ""
        if hi:
            items = "".join(
                '<div class="hl" id="%s" data-sid="%s"><div class="hl-t"><a href="%s" target="_blank" rel="noopener">%s</a></div>'
                '<div class="hl-m">%s · %s · <code>%s</code></div>'
                '%s'
                '<div class="hl-s">%s</div><div class="hl-w"><b>看点：</b>%s</div>%s%s</div>'
                % (esc(p["_key"]), esc(p["_sid"]),
                   esc(p.get("pdf") or pdf_url(p["_sid"])), esc(p["title"]),
                   esc(p.get("published", "")[:10]), esc(short_authors(p)), esc(p["_sid"]),
                   aff_line(p["_sid"]),
                   summ_lines(p["_summary_en"], p["_summary"], p.get("abstract", "")),
                   esc(p["_hl"]), acts(p["_sid"]),
                   abst_block(p["_sid"], p.get("abstract", "")))
                for p in hi)
            hl = '<div class="hl-box"><div class="hl-h">重点论文</div>%s</div>' % items

        rows = "".join(
            '<li class="item" id="%s" data-sid="%s" data-cat="%s">'
            '<div class="r-t"><a href="%s" target="_blank" rel="noopener">%s</a></div>'
            '<div class="r-m">%s · %s · <code>%s</code></div>'
            '%s'
            '<div class="r-s">%s</div>%s%s</li>'
            % (esc(p["_key"]), esc(p["_sid"]), esc(c),
               esc(p.get("pdf") or pdf_url(p["_sid"])), esc(p["title"]),
               esc(p.get("published", "")[:10]), esc(short_authors(p)), esc(p["_sid"]),
               aff_line(p["_sid"], "r-u"),
               summ_lines(p["_summary_en"], p["_summary"], p.get("abstract", "")),
               acts(p["_sid"]), abst_block(p["_sid"], p.get("abstract", "")))
            for p in ps)
        secs.append(
            '<section class="cat" id="cat-%s"><h2><span class="tag">%s</span> %s '
            '<em class="cnt">%d 篇</em><a class="totop" href="#top">↑ 回到顶部</a></h2>'
            '%s<ol class="plist">%s</ol></section>'
            % (c, c, cat_name(c), len(ps), hl, rows))

    th = ""
    if themes:
        items = []
        for t in themes:
            refs = " ".join('<a class="chip" href="#%s">%s</a>' % (esc(r), esc(r))
                            for r in t.get("refs", [])[:10])
            items.append('<div class="theme"><h3>%s</h3><p>%s</p><div class="chips">%s</div></div>'
                         % (esc(t.get("name", "")), esc(t.get("desc", "")), refs))
        th = ('<h2 class="sec-h">跨领域热点主题</h2>' + "".join(items))
    return th, "".join(secs)


# ---------------------------------------------------------------- 页面

CSS = read_template("style.css")

def api_port():
    """页面里的 APIBASE 应指向的端口（每次调用都重新解析，不缓存）。

    取值优先级见 ``paperutil.effective_port``：服务进程实际监听的端口优先，
    其次是配置里的 ``port``。服务因默认端口被占用而顺延时，这一层保证动态页面
    （/favorites、/profile、/archive）生成出来的 JS 指向新端口。
    """
    return pu.effective_port()


# 端口占位符在**渲染时**替换，而不是模块加载时：
# 改 config.port、或在测试里换端口重新生成页面，都无需重启服务进程。
_JS_CACHE = {}
JS = read_template("app.js")


def render_js():
    """把 app.js 里的 __APIPORT__ 换成当前端口（按端口缓存结果）。"""
    port = api_port()
    hit = _JS_CACHE.get(port)
    if hit is None:
        hit = JS.replace("__APIPORT__", str(port))
        _JS_CACHE[port] = hit
    return hit


_PORT = api_port()          # 兼容旧引用；渲染请用 render_js()
PAGE = read_template("page.html")


def jssafe(s):
    return s.replace("</", "<\\/").replace("<!--", "<\\!--")


def build_html(d, groups, by_sid, recs, exps, themes, idx):
    dates = sorted({p.get("published", "")[:10] for p in d["papers"] if p.get("published")})
    span = "%s ~ %s" % (dates[0], dates[-1]) if dates else "-"
    cfg = pu.load_config()
    cats = d.get("categories", [])

    # 类别统计卡片（页面里唯一的类别统计入口）：
    #   第一行 = arXiv 类别 + 篇数（蓝色粗体）；第二行 = 该类别的中文主题
    #   去掉"点击跳转"文案，改用整卡可点 + 悬浮抬升 + 右上角箭头来传达可跳转
    stats = "".join(
        '<a class="stat" href="#cat-%s" title="跳到 %s %s 分类">'
        '<span class="stat-go" aria-hidden="true">↗</span>'
        '<div class="stat-top"><b>%s</b><em>%d 篇</em></div>'
        '<div class="stat-sub">%s</div></a>'
        % (c, esc(c), esc(cat_name(c)), esc(c), len(groups.get(c, [])), esc(cat_name(c)))
        for c in cats)

    # 卡片池（多于展示数，供前端重排时替补）
    pool_core = build_pool_list(idx, recs, "core", POOL_CORE)
    pool_exp = build_pool_list(idx, exps, "expand", POOL_EXPAND)
    recs_html = build_pool_cards(pool_core, int(cfg.get("top_recommend", 14)))
    exps_html = build_pool_cards(pool_exp, int(cfg.get("top_expand", 10)))
    if not recs_html:
        recs_html = '<div class="empty">本轮没有命中兴趣画像的论文（可放宽 interests.json 或检查抓取窗口）。</div>'
    if not exps_html:
        exps_html = ('<div class="empty">本轮没有合适的跨领域候选。'
                     '可在 config.json 的 expand_categories 中增加分类，或放宽评分阈值。</div>')

    th, secs = build_sections(d, groups, themes, by_sid)
    expand_cats = [c for c in (cfg.get("expand_categories") or []) if c]
    if not expand_cats:
        # 与 fetch_expand.py 的推导保持一致：未显式配置时取同 archive 的兄弟分类
        expand_cats = arxiv_cats.neighbors([c for c in cats if c])
    excats = "、".join(expand_cats[:8]) or "同领域的其它分类"

    # 本期无新增时的提示（arXiv 周末不公告、或本期抓取到的类别都没有新投稿）
    notice = ""
    if not d.get("papers"):
        notice = ('<div class="notice">本期<b>没有新出现的论文</b>：arXiv 无新公告，或本期各分类无新投稿。'
                  '往期日报已存档，可到 <a href="/archive">🗂 历史存档</a> 按日期回看。</div>')

    # 侧边导航：推荐 / 扩展 + 各 arXiv 分类（可点击横线；常显标签用短名，全名放 title）
    rail = "".join(
        '<a class="navi" href="#%s" data-target="%s" aria-label="%s" title="%s">'
        '<span class="navlbl">%s</span><span class="line"></span></a>'
        % (tid, tid, esc(full), esc(full), esc(short))
        for tid, short, full in (
            ("sec-rec", "推荐", "🎯 为你推荐"),
            ("sec-exp", "扩展", "🌱 兴趣扩展"))
    )
    rail += '<span class="rail-sep"></span>'
    rail += "".join(
        '<a class="navi" href="#cat-%s" data-target="cat-%s" aria-label="%s" title="%s">'
        '<span class="navlbl">%s</span><span class="line"></span></a>'
        % (c, c, esc(c + " " + cat_name(c)), esc(c + " " + cat_name(c)),
           esc(c))
        for c in cats)

    pdata = {"papers": [], "topics": [], "weights": [], "kw": {}, "pens": {}, "expand_ids": []}
    if idx:
        pdata = {
            "topics": idx.get("topics", []),
            "weights": idx.get("weights", []),
            "kw": idx.get("kw", {}),
            "pens": idx.get("pens", {}),
            "expand_ids": idx.get("expand_ids", []),
            "papers": [{k: p.get(k) for k in (
                "id", "title", "authors", "primary", "published", "abstract",
                "summary", "summary_en", "tv", "base", "toks", "pen", "topics",
                "familiar_authors", "systems")} for p in idx.get("papers", [])],
        }

    return PAGE % {
        "css": CSS, "js": render_js(), "span": span,
        "cats": "、".join(cats),
        "total": len(d["papers"]),
        "notice": notice,
        "gen": d.get("generated_at", "").replace("T", " "),
        "dldir": esc(cfg["download_dir"]),
        "stats": stats,
        "recs": recs_html, "exps": exps_html,
        "toprec": int(cfg.get("top_recommend", 14)),
        "topexp": int(cfg.get("top_expand", 10)),
        "themes": th, "secs": secs, "win": d.get("window_days", 3),
        "excats": excats, "rail": rail,
        "srclabels": esc(_source_labels()),
        "topicline": _topic_line(),
        "pdata": jssafe(json.dumps(pdata, ensure_ascii=False)),
    }


def _topic_line():
    """摘要页「画像主线」一句：由 interests.json 的主题名现算，不写死在模板里。

    默认画像（interests.example.json）只有一个占位主题，这里就提示怎么配置，
    避免别人 clone 后看到作者的研究方向。
    """
    try:
        import customize as CZ
        names = [t.get("name", "") for t in CZ.effective_topics() if t.get("name")]
    except Exception:  # noqa
        names = []
    real = [n for n in names if "示例主题" not in n]
    if not real:
        return ('画像主线尚未设置：到 <a href="/profile">⚙ 画像与设置</a> 填主题与熟悉研究者，'
                '或 <code>python tools/preset.py list</code> 查看并导入一份示例画像。')
    shown = " · ".join(esc(n) for n in real[:8])
    more = "" if len(real) <= 8 else "（共 %d 个主题）" % len(real)
    return "画像主线：%s%s。" % (shown, more)


def _source_labels():
    """摘要页头部「基于 A × B × C 的兴趣画像」里的 A/B/C。

    取自 interests.json 的 owners（画像主来源，可在 /profile 增删改）：
    优先用 label（简称），否则用姓名。改完 owner 后「↻ 重算推荐」即同步。
    """
    try:
        import customize as CZ
        ow = CZ.owners()
    except Exception:  # noqa
        ow = []
    labs = [((o.get("label") or "").strip() or (o.get("name") or "").strip()) for o in ow]
    labs = [x for x in labs if x]
    return " × ".join(labs) if labs else "（尚未设置画像主来源）"


def build_pool_list(idx, chosen, pool, size):
    """把推荐结果与 papers_index 合并成卡片池（已选的在前，其余按分数补足）。"""
    if not idx:
        return chosen
    chosen_ids = {c["id"] for c in chosen}
    byid = {p["id"]: p for p in idx.get("papers", [])}
    is_expand = pool == "expand"
    expand_ids = set(idx.get("expand_ids", []))
    rest = []
    for p in idx.get("papers", []):
        if p["id"] in chosen_ids:
            continue
        if is_expand and p["id"] not in expand_ids:
            continue
        if not is_expand and p["id"] in expand_ids:
            continue
        rest.append(p)

    notes = jload("rec_notes.json", {})
    rest = [p for p in rest if not (notes.get(p["id"]) or {}).get("skip")]

    def score_of(p):
        s = p.get("base", 0) + p.get("pen", 0)
        for i, raw in p.get("tv", []):
            if i < len(idx.get("weights", [])):
                s += raw * idx["weights"][i]
        for t in p.get("toks", []):
            s += idx.get("kw", {}).get(t, 0)
        return s

    rest.sort(key=score_of, reverse=True)
    out = list(chosen)
    for p in rest[:max(0, size - len(chosen))]:
        item = dict(p)
        item["score"] = round(score_of(p), 1)
        item["tier"] = "推荐" if item["score"] >= 11 else "相关"
        item["note"] = "命中：" + "、".join(p.get("topics", [])[:3])
        out.append(item)
    return out


def md_summ_lines(en, zh, abstract="", indent="   "):
    """Markdown 版双语简介：与页面同一顺序（英文在前、中文在后）。"""
    en = (en or "").strip() or pu.en_excerpt(abstract)
    zh = (zh or "").strip()
    out = []
    if en:
        out.append("%s- EN %s" % (indent, en))
    if zh:
        out.append("%s- 中 %s" % (indent, zh))
    return out


def build_md(d, groups, recs, exps):
    L = ["# arXiv 新论文摘要\n",
         "覆盖范围：%s ｜ 共 %d 篇 ｜ 生成于 %s\n"
         % ("、".join(d.get("categories", [])) or "（未选择分类）", len(d["papers"]),
            d.get("generated_at", "").replace("T", " "))]
    L.append("\n## 🎯 个性化推荐\n")
    for i, r in enumerate(recs, 1):
        L.append("%d. **[%s](%s)** `%s` · %s · %s · %.1f 分"
                 % (i, r.get("title", ""), pdf_url(r["id"]), r["id"],
                    r.get("primary", ""), r.get("published", ""), r.get("score", 0)))
        L += md_summ_lines(r.get("summary_en"), r.get("summary"), r.get("abstract", ""))
        L.append("   - **推荐理由：** %s" % (r.get("note") or ""))
    if exps:
        L.append("\n## 🌱 兴趣扩展\n")
        for i, r in enumerate(exps, 1):
            L.append("%d. **[%s](%s)** `%s` · %s · %s"
                     % (i, r.get("title", ""), pdf_url(r["id"]), r["id"],
                        r.get("primary", ""), r.get("published", "")))
            L += md_summ_lines(r.get("summary_en"), r.get("summary"), r.get("abstract", ""))
            L.append("   - **推荐理由：** %s" % (r.get("note") or ""))
    L.append("\n| 分类 | 方向 | 篇数 |\n|---|---|---|")
    for c in d.get("categories", []):
        L.append("| %s | %s | %d |" % (c, cat_name(c), len(groups.get(c, []))))
    L.append("\n## 分类详解\n")
    for c in d.get("categories", []):
        ps = groups.get(c, [])
        L.append("### %s %s（%d 篇）\n" % (c, cat_name(c), len(ps)))
        for p in ps:
            L.append("- `%s` **[%s](%s)** — %s · %s"
                     % (p["_sid"], p["title"], p.get("pdf") or pdf_url(p["_sid"]),
                        p.get("published", "")[:10], short_authors(p)))
            L += md_summ_lines(p.get("_summary_en"), p.get("_summary"),
                               p.get("abstract", ""), indent="  ")
            if p.get("_hl"):
                L.append("  - **看点：** %s" % p["_hl"])
        L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------- 首次引导页

WELCOME_PAGE = read_template("welcome.html")


def build_welcome():
    """「还没有选任何分类」时的引导页（通用版首次 clone 打开 / 的情形）。

    与其在 `/` 上抛一句 404 文本，不如把「下一步点哪里」直接摆在用户面前：
    分类是这套工具唯一的必填项，而这个入参现在由用户自己给。
    """
    t = arxiv_cats.taxonomy()
    # 示例分类刻意跨学科、且**不含**作者本人跟踪的那几个：首屏不该出现任何
    # "像某人的研究方向"的暗示。这个列表只是「官方分类长什么样」的演示。
    samples = ["cs.LG", "math.LO", "stat.ML", "quant-ph",
               "eess.AS", "q-bio.NC", "econ.EM", "astro-ph.GA"]
    return WELCOME_PAGE % {
        "css": CSS,
        "total": t["total"],
        "source": t["source"],
        "version": t["version"],
        "samples": "".join("<span>%s</span>" % esc(s) for s in samples),
    }


# ---------------------------------------------------------------- 收藏页

FAV_PAGE = read_template("favorites.html")


def build_favorites(lib):
    load_affiliations()
    load_abstracts_zh()
    invalidate_cat_names()
    cfg = pu.load_config()
    favs = lib.get("favorites", {})
    items = []
    for i, (sid, f) in enumerate(sorted(favs.items(),
                                        key=lambda kv: kv[1].get("added_at", ""), reverse=True), 1):
        dlp = lib.get("downloads", {}).get(sid, {}).get("path", "") or f.get("path", "")
        badge = ('<span class="dl-yes">已下载</span>' if dlp
                 else '<span class="dl-no">未下载</span>')
        items.append(
            '<div class="fav-item" data-sid="%s"><div class="fi-no">%d</div><div class="fi-main">'
            '<div class="hd">%s<span class="tag">%s</span><span class="date">%s</span>'
            '<span class="date">收藏于 %s</span></div>'
            '<a class="fav-t rec-t" href="%s" target="_blank">%s</a>'
            '<div class="fi-meta rec-a">%s · <code>%s</code></div>'
            '%s'
            '<div class="path">%s</div>'
            '<div class="acts">'
            '<button class="btn fav on" data-act="fav" data-sid="%s"><span class="ico">★</span><span class="lb">已收藏</span></button>'
            '<button class="btn dl %s" data-act="dl" data-sid="%s"><span class="ico">⬇</span><span class="lb">%s</span></button>'
            '<button class="btn ab" data-act="abs" data-sid="%s"><span class="ico">▸</span><span class="lb">Abstract (EN)</span></button>'
            '<button class="btn ab abz" data-act="abszh" data-sid="%s"><span class="ico">▸</span><span class="lb">Abstract (CH)</span></button>'
            '%s'
            '<a class="btn ghost pdf" data-sid="%s" href="%s" target="_blank" rel="noopener">PDF</a>'
            '<button class="btn dv" data-act="dv" data-sid="%s"><span class="ico">👎</span><span class="lb">Downvote</span></button>'
            '</div>%s</div></div>'
            % (esc(sid), i, badge, esc(f.get("primary", "")),
               esc((f.get("published") or "")[:10]), esc(f.get("added_at", "")),
               esc(pdf_url(sid)), esc(f.get("title", sid)),
               esc(", ".join((f.get("authors") or [])[:5])), esc(sid),
               aff_line(sid),
               esc(dlp or "尚未下载到本地"),
               esc(sid), "done" if dlp else "", esc(sid), "已下载" if dlp else "下载",
               esc(sid), esc(sid),
               ('<button class="btn" data-open="%s">打开</button>' % esc(sid)) if dlp else "",
               esc(sid), esc(pdf_url(sid)), esc(sid),
               abst_block(sid, f.get("abstract", ""))))
    if not items:
        items = ['<div class="empty">还没有收藏。回到摘要页点击「☆ 收藏」即可加入这里；'
                 '点击「⬇ 下载」会自动收藏并保存 PDF。</div>']
    return FAV_PAGE % {
        "css": CSS, "js": render_js(), "n": len(favs),
        "nd": sum(1 for s in favs if lib.get("downloads", {}).get(s, {}).get("path")),
        "dldir": esc(cfg["download_dir"]), "now": pu.now_str(), "items": "".join(items),
    }


# ---------------------------------------------------------------- 画像与设置页

PROFILE_PAGE = read_template("profile.html")


def _owner_cards(prof):
    """画像主来源卡片（服务端首屏渲染；改动用前端 renderOwners 重画，两者结构保持一致）。"""
    out = []
    for o in prof.get("owners") or []:
        name = o.get("name", "")
        sig = "".join("<li>%s</li>" % esc(s) for s in (o.get("signature_topics") or [])[:4])
        site = (o.get("site") or "").strip()
        link = ('<a href="%s" target="_blank" rel="noopener">%s</a>' % (esc(site), esc(site))
                if site else "")
        aff = ('<div class="aff">%s</div>' % esc(o.get("affiliation", ""))
               if o.get("affiliation") else "")
        itr = ('<div class="date">%s</div>' % esc(o.get("interests", ""))
               if o.get("interests") else "")
        tag = ('<span class="ow-tag">已计入熟悉研究者（+10/篇）</span>'
               if o.get("people_linked") else "")
        out.append(
            '<div class="owner" data-owner="%s">'
            '<div class="ow-top"><h4>%s</h4><span class="ow-act">'
            '<button class="btn-x" data-edit-owner="%s">编辑</button>'
            '<button class="btn-x" data-del-owner="%s">删除</button></span></div>'
            '%s%s%s%s%s</div>'
            % (esc(name), esc(name), esc(name), esc(name), aff, link, itr,
               ("<ul>%s</ul>" % sig) if sig else "", tag))
    return "".join(out) or '<div class="p-empty">还没有画像主来源，请在上方添加。</div>'


def build_profile_page():
    """兴趣画像 + 定制项（类别 / 下载目录 / 来源 / 数据包）独立页面。"""
    invalidate_cat_names()
    try:
        import customize as CZ
        d = CZ.view()
    except Exception as e:  # noqa
        d = {"categories": [], "category_names": {}, "download_dir": "", "sources": [],
             "profile": {"owners": [], "themes": [], "people": [], "systems": [],
                         "negative": [], "counts": {}}}
        sys.stderr.write("profile view failed: %s\n" % e)
    p = d.get("profile") or {}
    th = p.get("themes") or []
    custom = [t for t in th if t.get("custom")]
    summary = ("画像来源 <b>%d</b> 位研究者 ｜ 主题 <b>%d</b> 个（含 %d 个来自你的来源）｜ "
               "熟悉研究者 <b>%d</b> 位 ｜ 代表系统 <b>%d</b> 个 ｜ 兴趣来源 <b>%d</b> 条 ｜ "
               "行为学习更新于 %s"
               % (len(p.get("owners") or []), len(th), len(custom),
                  len(p.get("people") or []), len(p.get("systems") or []),
                  len(d.get("sources") or []), esc(p.get("updated_at") or "—")))
    return PROFILE_PAGE % {
        "css": CSS, "js": render_js(), "summary": summary,
        "owners": _owner_cards({"owners": p.get("owners") or []}),
        "packs": _pack_panel(),
        "customtopic": esc(_custom_topic_name()),
        "customw": _custom_topic_weight(),
        # 官方分类表随页面一起下发：两个联动下拉框的数据源，等价于
        # GET /api/arxiv_categories（同一份 arxiv_cats.taxonomy()）。
        "taxonomy": jssafe(json.dumps(arxiv_cats.taxonomy(), ensure_ascii=False)),
    }


# 分组的中文标签（数据包面板用）。写成映射而不是散在拼接里，
# 新增分组时只需在这里加一行。
_PACK_GROUPS = {"core": "配置 / 画像", "usage": "收藏与下载",
                "learning": "行为学习", "notes": "摘要与笔记"}


def _pack_panel():
    """画像页「📦 数据包」面板：**只渲染形状**（包名 / 文件清单 / 体积 / 分组）。

    刻意不渲染 manifest 的 title 与 description —— 那句描述往往就是作者的类别选择
    与研究方向，正是要隔离的内容。想了解包内容有两条正当路径：读
    `presets/<名字>/README.md`，或导入。边界规则见
    docs/architecture/data-isolation.md §六。
    """
    try:
        import datapack as DP
        packs = DP.list_packs()
    except Exception as e:  # noqa
        sys.stderr.write("datapack view failed: %s\n" % e)
        return '<div class="p-empty">数据包模块不可用（datapack.py 缺失？）</div>'
    if not packs:
        return ('<div class="p-empty">没有可导入的数据包。把包放进 '
                '<code>presets/&lt;名字&gt;/</code>，或用 '
                '<code>python tools/preset.py export &lt;名字&gt;</code> 把当前设置存成一个包。</div>'
                '<div class="pk-state">%s</div>' % _packs_state_note())
    rows = []
    for p in packs:
        grp = "、".join(_PACK_GROUPS.get(g, g) for g in p["groups"])
        size = ("%.1f KB" % (p["bytes"] / 1024.0)) if p["bytes"] >= 1024 else "%d B" % p["bytes"]
        rows.append(
            '<div class="pack-item">'
            '<div class="pk-main">'
            '<div class="pk-top"><b>%s</b><span class="pk-size">%d 个文件 · %s</span>'
            '<span class="pk-grp">%s</span></div>'
            '<div class="pk-files">%s</div>'
            '<div class="pk-hint">导入前建议先读 <code>presets/%s/README.md</code></div>'
            '</div>'
            '<button class="tb primary" data-import-pack="%s">导入</button>'
            '</div>'
            % (esc(p["name"]), len(p["files"]), esc(size), esc(grp),
               esc(" · ".join(p["files"])), esc(p["name"]), esc(p["name"])))

    # 本机现状按**内容**统计，而不是按文件是否存在：首次打开页面就会生成空的
    # config.json / interests.json，"文件存在"并不能说明用户已经开始积累数据。
    return "".join(rows) + '<div class="pk-state">%s</div>' % _packs_state_note()


def _packs_state_note():
    """「本机现状」一句话：有数据就报数，没数据就明确说干净。"""
    try:
        import customize as CZ
        n_cat = len(CZ.categories())
        n_topic = len(CZ.effective_topics())
    except Exception:  # noqa
        n_cat = n_topic = 0
    try:
        n_fav = len(pu.load_library().get("favorites") or {})
    except Exception:  # noqa
        n_fav = 0
    if n_cat or n_topic or n_fav:
        return ('本机现状：<b>%d</b> 个类别 ｜ <b>%d</b> 个画像主题 ｜ 收藏 <b>%d</b> 篇。'
                '配置类文件默认<b>不覆盖</b>，收藏与 Downvote 只做<b>并集</b>。'
                % (n_cat, n_topic, n_fav))
    return ('本机是<b>干净状态</b>（未选类别、未设画像、没有收藏）。'
            '导入只会补齐，不会覆盖任何东西。')


def _custom_topic_name():
    try:
        import customize as CZ
        return CZ.CUSTOM_TOPIC
    except Exception:
        return "我的来源关注"


def _custom_topic_weight():
    try:
        import customize as CZ
        return CZ.CUSTOM_TOPIC_WEIGHT
    except Exception:
        return 0.6


# ---------------------------------------------------------------- 历史存档页

ARCHIVE_PAGE = read_template("archive.html")


def _weekday_cn(date):
    try:
        import datetime as _dt
        w = _dt.datetime.strptime(str(date), "%Y%m%d").weekday()
        return "周" + "一二三四五六日"[w]
    except Exception:
        return ""


def build_archive_page():
    """按日期浏览历史存档。数据来自 archive.db + output/archive/ 目录扫描。"""
    try:
        import archive as AR
    except Exception as e:  # noqa
        sys.stderr.write("archive module missing: %s\n" % e)
        return ARCHIVE_PAGE % {"css": CSS, "js": render_js(), "n": 0, "np": 0,
                               "items": '<div class="empty">归档模块不可用</div>'}
    iss = {i["date"]: i for i in AR.list_issues()}
    dates = AR.available_dates()
    items = []
    for d in dates:
        i = iss.get(d)
        wd = _weekday_cn(d)
        day = "%s-%s-%s" % (d[:4], d[4:6], d[6:8])
        if i and (i.get("n_new") or i.get("n_rec")):
            meta = ("新增 <b>%s</b> 篇 ｜ 推荐 <b>%s</b> ｜ 扩展 <b>%s</b>"
                    % (i.get("n_new") or 0, i.get("n_rec") or 0, i.get("n_exp") or 0))
            newest = (i.get("newest_seen") or "")[:10]
            if newest:
                meta += " ｜ 抓到最新提交 %s" % esc(newest)
        else:
            meta = "当期快照（未入库统计）"
        items.append(
            '<a class="arc" href="/archive/%s"><span class="go">↗</span>'
            '<div class="d">%s<span class="w">%s</span></div>'
            '<div class="m">%s</div></a>' % (esc(d), esc(day), esc(wd), meta))
    if not items:
        items = ['<div class="empty">还没有任何存档：跑一次 run_daily.py 就会生成当期快照。</div>']
    st = AR.stats()
    return ARCHIVE_PAGE % {"css": CSS, "js": render_js(), "n": len(dates), "np": st.get("papers", 0),
                           "items": "".join(items)}


# ---------------------------------------------------------------- 归档写入

def _archive_rows(d, groups, recs, exps):
    """当期要入库的论文：核心分类明细全部 + 扩展推荐（k 上限）。"""
    rows, seen = [], set()

    def push(sid, **kw):
        if not sid or sid in seen:
            return
        seen.add(sid)
        rows.append(dict(sid=sid, **kw))

    for cat in d.get("categories", []):
        for p in groups.get(cat, []):
            sid = pu.short_id(p)
            push(sid, pool="core", is_new=1, primary=cat, title=p.get("title", ""),
                 authors=p.get("authors") or [], published=p.get("published", ""),
                 summary=p.get("_summary") or "", pdf=p.get("pdf") or pdf_url(sid),
                 affil="；".join(aff_units(sid)))
    for r in list(recs) + list(exps):
        sid = r.get("id")
        push(sid, pool="expand" if r in exps else "core", is_new=1,
             primary=r.get("primary", ""), title=r.get("title", ""),
             authors=r.get("authors") or [], published=r.get("published", ""),
             score=r.get("score"), tier=r.get("tier", ""), summary=r.get("summary", ""),
             note=r.get("note", ""), topics=r.get("topics") or [],
             pdf=r.get("pdf") or pdf_url(sid), affil="；".join(aff_units(sid)))
    return rows


# ---------------------------------------------------------------- main

def main():
    os.makedirs(OUT, exist_ok=True)
    d, groups, by_sid, recs, exps, themes, lib, idx = load()
    ts = (d.get("issue_date")
          or d.get("generated_at", "")[:10].replace("-", "")
          or pu.now_str()[:10].replace("-", ""))
    hp = os.path.join(OUT, "arxiv_digest_%s.html" % ts)
    mp = os.path.join(OUT, "arxiv_digest_%s.md" % ts)
    fp = os.path.join(OUT, "favorites.html")
    open(hp, "w", encoding="utf-8").write(build_html(d, groups, by_sid, recs, exps, themes, idx))
    open(mp, "w", encoding="utf-8").write(build_md(d, groups, recs, exps))
    open(fp, "w", encoding="utf-8").write(build_favorites(lib))
    print(hp)
    print(mp)
    print(fp)

    # 归档：快照另存 output/archive/<日期>.html 并登记进 archive.db；同时把本期
    # 论文写进 seen 表——这是「明天不会再当成本期新增」的唯一依据。
    try:
        import archive as AR
        n_new = len(d.get("papers") or [])
        hname, mname = AR.archive_digest(ts, hp, mp)
        AR.record_issue(ts, html=hname, md=mname, generated_at=d.get("generated_at", ""),
                        newest_seen=d.get("newest_seen", ""),
                        papers=_archive_rows(d, groups, recs, exps),
                        n_new=n_new, n_core=n_new, n_rec=len(recs), n_exp=len(exps))
        for f in ("issue_core.json", "issue_expand.json"):
            doc = jload(f, {}) or {}
            AR.mark_seen([pu.short_id(p) for p in (doc.get("papers") or [])], ts)
        ap = os.path.join(OUT, "archive.html")
        open(ap, "w", encoding="utf-8").write(build_archive_page())
        print(ap)
        print("[archive] issue %s: %d papers, %d recs, %d exps -> %s"
              % (ts, n_new, len(recs), len(exps), AR.DB_PATH))
    except Exception as e:  # noqa
        import traceback
        traceback.print_exc()
        sys.stderr.write("archive failed (日报本身已生成，可忽略): %s\n" % e)


if __name__ == "__main__":
    main()
