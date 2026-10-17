#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染 arXiv cs.* 论文摘要（v3）。

v3 能力
  - 🎯 为你推荐（六分类 feed 内） 与  🌱 兴趣扩展（六分类之外的 cs.xx / 其他）
  - 每篇论文：收藏 / 下载 / Abstract（内联展开折叠）/ PDF / Downvote
  - Downvote 在「为你推荐 / 兴趣扩展 / 分类详解」三处表现统一：变灰 + 标题删除线，
    卡片保留原位、不消失，可再点一次撤销（三处共用同一组 CSS 规则与同一段 JS）
  - 所有交互行为都会回传本地服务，实时更新兴趣画像；按钮乐观更新，重排合并执行
  - 顶部分类统计为可跳转锚点

输入（output/ 下）
  raw.json  raw_expand.json  papers_index.json  recommend.json  expand.json
  summaries.json  rec_notes.json  themes.json  highlights.json  library.json
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

OUT = pu.OUT

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
    invalidate_cat_names()
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
            p["_summary"] = (summaries.get(key) or summaries.get(pu.short_id(p)) or "").strip()
            p["_hl"] = (highs.get(key) or highs.get(pu.short_id(p)) or "").strip()
            by_sid[pu.short_id(p)] = p
    return d, groups, by_sid, rec, exp, themes, lib, idx


# ---------------------------------------------------------------- 组件

ACTS = ('<div class="acts">'
        '<button class="btn fav" data-act="fav" data-sid="{sid}">'
        '<span class="ico">☆</span><span class="lb">收藏</span></button>'
        '<button class="btn dl" data-act="dl" data-sid="{sid}">'
        '<span class="ico">⬇</span><span class="lb">下载</span></button>'
        '<button class="btn ab" data-act="abs" data-sid="{sid}">'
        '<span class="ico">▸</span><span class="lb">Abstract</span></button>'
        '<a class="btn ghost pdf" data-sid="{sid}" href="{pdf}" target="_blank" rel="noopener">PDF</a>'
        '<button class="btn dv" data-act="dv" data-sid="{sid}" title="不感兴趣：以后减少推荐">'
        '<span class="ico">👎</span><span class="lb">Downvote</span></button>'
        '</div>')


def acts(sid):
    return ACTS.format(sid=esc(sid), pdf=esc(pdf_url(sid)))


def abst_block(sid, abstract):
    return ('<div class="abst" id="ab-%s"><div class="abst-in">%s</div></div>'
            % (esc(sid), esc(abstract or "(无摘要)")))


def tier_cls(tier):
    return {"强烈推荐": "t1", "推荐": "t2"}.get(tier, "t3")


def build_card(item, i, note_default=""):
    """推荐 / 扩展列表中的一张卡片。"""
    sid = item["id"]
    topics = "".join('<span class="tp">%s</span>' % esc(t) for t in item.get("topics", [])[:4])
    fam = "".join('<span class="tp au">%s</span>' % esc(a) for a in item.get("familiar_authors", [])[:3])
    summ = (item.get("summary") or "").strip()
    if not summ:
        summ = (item.get("abstract") or "")[:220].strip()
        if len(item.get("abstract") or "") > 220:
            summ += "…"
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
           esc(short_authors(item)), esc(sid), aff_line(sid), esc(summ), esc(why),
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
                   esc(p["_summary"]), esc(p["_hl"]), acts(p["_sid"]),
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
               esc(p["_summary"] or ((p.get("abstract") or "")[:180] + "…")),
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

CSS = """
:root{--bg:#f5f6f8;--card:#fff;--bd:#e2e6ec;--tx:#1b1f24;--tx2:#5c6672;--tx3:#8b95a1;
--ac:#2f6fed;--acbg:#eef3ff;--star:#f0a020;--ok:#1a9e63;--warn:#d9534f;--exp:#0e9f6e;
--expbg:#e9f8f1}
*{box-sizing:border-box}
body{margin:0;padding:0 0 80px;background:var(--bg);color:var(--tx);
 font:15px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:0 18px}
header{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:24px 28px;margin:22px 0 16px}
h1{margin:0 0 6px;font-size:24px;letter-spacing:.3px}
.sub{color:var(--tx2);font-size:13.5px}
.sub b{color:var(--tx)}
.toolbar{position:sticky;top:0;z-index:20;background:rgba(245,246,248,.94);backdrop-filter:blur(8px);
 border:1px solid var(--bd);border-radius:12px;padding:10px 14px;margin-bottom:12px;
 display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.toolbar .grow{flex:1}
.tb{background:#fff;border:1px solid var(--bd);color:var(--tx2);border-radius:8px;padding:5px 12px;
 font-size:13px;cursor:pointer;font-family:inherit;text-decoration:none;display:inline-block}
.tb:hover{border-color:var(--ac);color:var(--ac)}
.tb.on{background:var(--ac);border-color:var(--ac);color:#fff}
input.search{border:1px solid var(--bd);border-radius:8px;padding:6px 11px;font-size:13.5px;
 min-width:180px;font-family:inherit;color:var(--tx)}
.counter{font-size:13px;color:var(--tx2)}
.counter b{color:var(--star)}
/* ---- 类别统计卡片：页面里唯一的类别统计入口；整卡可点，靠 hover 抬升 + 描边 + 箭头表达 ---- */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:20px}
.stat{position:relative;display:block;background:var(--card);border:1px solid var(--bd);
 border-radius:12px;padding:13px 16px;text-decoration:none;color:inherit;cursor:pointer;
 transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease,background .16s ease}
.stat:hover,.stat:focus-visible{transform:translateY(-2px);border-color:var(--ac);
 box-shadow:0 6px 18px rgba(47,111,237,.15);background:linear-gradient(180deg,#f7faff,#fff);outline:none}
.stat:active{transform:translateY(0)}
.stat-top{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.stat-top b,.stat-top em{color:var(--ac);font-size:16.5px;font-weight:800;letter-spacing:.2px}
.stat-top em{font-style:normal;font-variant-numeric:tabular-nums}
.stat-sub{font-size:12.5px;color:var(--tx2);margin-top:3px}
.stat-go{position:absolute;top:9px;right:11px;font-size:13px;color:var(--ac);opacity:.28;
 transition:opacity .16s ease,transform .16s ease}
.stat:hover .stat-go,.stat:focus-visible .stat-go{opacity:1;transform:translate(2px,-2px)}
.sec-h{font-size:18px;margin:26px 0 12px}
.rec-box{background:linear-gradient(180deg,#fffdf6,#fff);border:1px solid #f0dfbe;
 border-radius:14px;padding:18px 22px 8px;margin-bottom:20px}
.exp-box{background:linear-gradient(180deg,#f4fdf9,#fff);border:1px solid #c8ecdc;
 border-radius:14px;padding:18px 22px 8px;margin-bottom:20px}
.rec-box>.rec-h,.exp-box>.rec-h{font-size:17px;margin:0 0 4px;display:flex;align-items:center;gap:8px}
.rec-box>.rec-sub,.exp-box>.rec-sub{font-size:12.8px;color:var(--tx3);margin:0 0 14px}
.rec-card{display:flex;gap:14px;padding:14px 0;border-top:1px dashed #eadfc9}
.exp-box .rec-card{border-top-color:#d3ecdf}
.rec-card.hidden{display:none}
/* ---- Downvote 视觉统一（为你推荐 / 兴趣扩展 / 分类详解 / 重点论文 / 收藏列表）：
   「变灰 + 标题删除线」，卡片不隐藏、不消失，就地保留以便再次点击撤销。
   三处共用这一组规则，改这里就等于三处同改。 ---- */
.rec-card.down,.plist li.item.down,.hl.down,.fav-item.down{opacity:.42}
.rec-card.down .rec-t,.plist li.item.down .r-t a,.hl.down .hl-t a,
.fav-item.down .rec-t{text-decoration:line-through}
.rec-no{font-size:19px;font-weight:800;color:#d9c49a;min-width:34px;padding-top:2px;font-variant-numeric:tabular-nums}
.exp-box .rec-no{color:#9ecfb8}
.rec-main{flex:1;min-width:0}
.rec-head{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-bottom:4px}
.tier{font-size:11.5px;font-weight:700;padding:2px 8px;border-radius:5px;color:#fff}
.tier.t1{background:#d9480f}.tier.t2{background:var(--ac)}.tier.t3{background:#8b95a1}
.score{font-size:12px;color:var(--tx3);background:#f1f3f6;border-radius:5px;padding:2px 7px}
.tag{background:var(--ac);color:#fff;font-size:11.5px;padding:2px 8px;border-radius:5px;font-weight:600}
.exp-box .tag{background:var(--exp)}
.date,.cnt{font-size:12px;color:var(--tx3);font-style:normal;font-weight:400}
.totop{font-size:11.5px;color:var(--tx3);text-decoration:none;margin-left:auto}
.totop:hover{color:var(--ac)}
.rec-t{color:var(--tx);font-weight:650;text-decoration:none;font-size:15.5px;line-height:1.5}
.rec-t:hover{color:var(--ac)}
.rec-a{font-size:12.2px;color:var(--tx3);margin:3px 0 5px}
.rec-s{font-size:13.6px;color:var(--tx2)}
.rec-why{font-size:13.2px;color:#3d4753;margin-top:6px;background:#fff;border-left:3px solid #f0a020;
 padding:6px 10px;border-radius:0 6px 6px 0}
.exp-box .rec-why{border-left-color:var(--exp)}
.rec-tp{margin-top:7px;display:flex;flex-wrap:wrap;gap:5px}
.tp{font-size:11.5px;background:var(--acbg);color:var(--ac);border-radius:20px;padding:2px 9px}
.tp.au{background:#fdf0dd;color:#a15c00}
.acts{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.btn{display:inline-flex;align-items:center;gap:4px;background:#fff;border:1px solid var(--bd);
 color:var(--tx2);border-radius:7px;padding:4px 10px;font-size:12.5px;cursor:pointer;
 text-decoration:none;font-family:inherit;line-height:1.6}
.btn:hover{border-color:var(--ac);color:var(--ac)}
.btn .ico{font-size:12px}
.btn.fav.on{background:#fff8e8;border-color:var(--star);color:#a15c00}
.btn.fav.on .ico{color:var(--star)}
.btn.dl.done{background:#eaf7f0;border-color:var(--ok);color:var(--ok)}
.btn.ab.open{border-color:var(--ac);color:var(--ac);background:var(--acbg)}
.btn.dv.on{background:#fdecec;border-color:var(--warn);color:var(--warn)}
.btn:disabled{opacity:.6;cursor:default}
.abst{display:none;margin-top:9px}
.abst.open{display:block}
.abst-in{background:#f7f9fc;border:1px solid var(--bd);border-left:3px solid var(--ac);
 border-radius:0 8px 8px 0;padding:10px 13px;font-size:13.2px;color:#3d4753;line-height:1.75;
 white-space:pre-wrap}
.cat{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:20px 24px 24px;margin-bottom:18px}
.cat h2{font-size:18px;margin:0 0 12px;display:flex;align-items:center;gap:9px}
.hl-box{background:#fbfcfe;border:1px solid var(--bd);border-radius:10px;padding:4px 18px 12px;margin-bottom:16px}
.hl-h{font-size:13px;color:var(--ac);font-weight:700;padding:10px 0 6px;letter-spacing:.5px}
.hl{padding:10px 0;border-top:1px dashed var(--bd)}
.hl-t a{color:var(--tx);font-weight:650;text-decoration:none;font-size:14.6px}
.hl-t a:hover{color:var(--ac)}
.hl-m,.r-m,.rec-u,.r-u{font-size:12px;color:var(--tx3);margin:3px 0 5px}
.hl-m code,.r-m code{background:#f1f3f6;padding:1px 5px;border-radius:4px;font-size:11.5px}
.hl-s,.r-s{font-size:13.6px;color:var(--tx2)}
.hl-w{font-size:13.2px;color:#3d4753;margin-top:6px;background:#fff;border-left:3px solid var(--ac);
 padding:6px 10px;border-radius:0 6px 6px 0}
.plist{margin:0;padding-left:22px}
.plist li.item{margin:0 0 14px;padding:2px 4px;border-radius:8px}
.plist li.item.hidden{display:none}
.r-t a{color:var(--tx);text-decoration:none;font-size:14.2px}
.r-t a:hover{color:var(--ac)}
.theme{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:15px 19px;margin-bottom:11px}
.theme h3{margin:0 0 6px;font-size:15.5px}
.theme p{margin:0 0 9px;color:var(--tx2);font-size:13.8px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:11.5px;background:var(--acbg);color:var(--ac);border-radius:20px;padding:2px 9px;text-decoration:none}
.chip:hover{background:#dfe9ff}
#toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:99;display:flex;
 flex-direction:column;gap:8px;align-items:center;pointer-events:none}
.tst{background:#1b1f24;color:#fff;font-size:13.5px;padding:9px 16px;border-radius:9px;box-shadow:0 6px 20px rgba(0,0,0,.18);
 max-width:80vw;opacity:.97}
.tst.ok{background:#1a7f52}.tst.err{background:#b3382f}
.empty{padding:16px;color:var(--tx3);font-size:13.5px}
.notice{margin:0 0 14px;padding:12px 14px;border-radius:10px;background:#fff8e6;border:1px solid #f0dfbe;
 color:#7a5b16;font-size:13.5px;line-height:1.75}
.notice a{color:var(--ac);font-weight:600}
/* ---- 历史存档页 ---- */
.arc-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:12px;margin:18px 0 8px}
.arc{display:block;text-decoration:none;color:inherit;background:#fff;border:1px solid var(--bd);
 border-radius:12px;padding:14px 16px;transition:transform .15s,border-color .15s,box-shadow .15s;position:relative}
.arc:hover{transform:translateY(-2px);border-color:var(--ac);box-shadow:0 6px 18px rgba(20,40,90,.08)}
.arc .d{font-size:16px;font-weight:800;color:var(--ac);letter-spacing:.3px;font-variant-numeric:tabular-nums}
.arc .w{font-size:12px;color:var(--tx3);margin-left:6px;font-weight:400}
.arc .m{font-size:12.8px;color:var(--tx2);margin-top:6px;line-height:1.7}
.arc .m b{color:var(--ac)}
.arc .go{position:absolute;right:12px;top:11px;color:var(--ac);opacity:.3;font-size:14px}
.arc:hover .go{opacity:1}
.arc.cur{border-color:var(--ac);background:linear-gradient(180deg,#fffdf6,#fff)}
.arc-hint{color:var(--tx3);font-size:12.8px;margin:6px 0 0}
footer{color:var(--tx3);font-size:12.5px;text-align:center;margin-top:26px;line-height:1.9}

/* ---- 平滑滚动 + 关闭滚动锚定（避免重排时视口跳动） ---- */
html{scroll-behavior:smooth;overflow-anchor:none}
html.nosm{scroll-behavior:auto}
body{overflow-anchor:none}

/* ---- Downvote 的「变灰 + 删除线」规则统一在上面 .rec-card.down 那一组 ---- */
.hl{scroll-margin-top:78px}
#sec-rec,#sec-exp,section.cat{scroll-margin-top:78px}

/* ---- 侧边分类导航（可点击横线，scrollspy） ---- */
#rail{position:fixed;right:16px;top:50%;transform:translateY(-50%);z-index:40;
 display:flex;flex-direction:column;gap:9px;align-items:flex-end}
#rail .navi{display:flex;align-items:center;justify-content:flex-end;gap:8px;text-decoration:none;
 cursor:pointer;height:14px}
#rail .line{display:block;width:13px;height:2px;border-radius:2px;background:#c9d0da;
 transition:width .18s ease,background .18s ease}
#rail .navlbl{font-size:11px;color:var(--tx3);white-space:nowrap;opacity:0;line-height:1;
 transform:translateX(4px);transition:opacity .18s ease,transform .18s ease;
 background:rgba(255,255,255,.94);border:1px solid var(--bd);border-radius:5px;padding:2px 6px}
#rail .navi:hover .line{width:24px;background:var(--ac)}
#rail .navi:hover .navlbl{opacity:1;transform:translateX(0)}
#rail .navi.on .line{width:26px;height:3px;background:var(--ac)}
#rail .navi.on .navlbl{opacity:1;transform:translateX(0);color:var(--ac);border-color:#c9dcff;
 background:var(--acbg)}
#rail .rail-sep{width:13px;height:1px;background:var(--bd);margin:2px 0}

/* ---- 回到顶部按钮 ---- */
#totop{position:fixed;right:20px;bottom:26px;z-index:41;width:42px;height:42px;border-radius:50%;
 border:1px solid var(--bd);background:var(--card);color:var(--tx2);cursor:pointer;font-size:17px;
 display:flex;align-items:center;justify-content:center;box-shadow:0 4px 14px rgba(16,24,40,.12);
 font-family:inherit;opacity:0;visibility:hidden;transform:translateY(8px);
 transition:opacity .22s ease,transform .22s ease,visibility .22s,border-color .18s,color .18s}
#totop.show{opacity:1;visibility:visible;transform:translateY(0)}
#totop:hover{border-color:var(--ac);color:var(--ac)}
@media(max-width:700px){.wrap{padding:0 10px}.cat{padding:16px 14px 20px}.rec-box{padding:14px 14px 6px}}
/* 侧栏只在右侧真正有留白时出现（1080 正文列 + 两侧留白），否则会压到卡片边缘 */
@media(max-width:1320px){#rail{display:none}}
"""

try:
    _PORT = int((pu.load_config() or {}).get("port", 8765))
except Exception:
    _PORT = 8765

JS = """
var PD={papers:[],topics:[],weights:[],kw:{},pens:{},expand_ids:[]};
try{PD=JSON.parse(document.getElementById('pdata').textContent);}catch(e){}
var W=(PD.weights||[]).slice(), KW=PD.kw||{}, PENS=PD.pens||{};
var BYID={}; (PD.papers||[]).forEach(function(p){BYID[p.id]=p;});
var EXPSET={}; (PD.expand_ids||[]).forEach(function(i){EXPSET[i]=1;});
var DV={};
/* 页面可能被以 file:// 或别的静态服务打开，此时相对路径 /api/* 会打到错误的 origin。
   统一指向本地服务（同源时用相对路径，跨源/文件协议时用绝对地址 + CORS）。 */
var APIPORT=__APIPORT__;
var APIBASE=(location.protocol==='file:'||!location.port||location.port!==String(APIPORT))
  ?('http://127.0.0.1:'+APIPORT):'';
/* 站内链接（收藏 / 画像 / 存档 / 返回本期）同样要指向本地服务：
   页面被以 file:// 或别的静态服务打开时，href="/x" 会变成 file:///x 打不开。
   统一给所有根相对链接加上 APIBASE（同源时 APIBASE 为空串，等于没改）。 */
function fixLinks(){document.querySelectorAll('a[href^="/"]').forEach(function(a){
 var h=a.getAttribute('href');
 if(h.charAt(0)==='/'&&h.charAt(1)!=='/')a.setAttribute('href',APIBASE+h);});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',fixLinks);
else fixLinks();
function toast(msg,kind){var w=document.getElementById('toast');if(!w){w=document.createElement('div');w.id='toast';document.body.appendChild(w);}
 var d=document.createElement('div');d.className='tst '+(kind||'');d.textContent=msg;w.appendChild(d);
 /* 报错信息通常较长，给它更长的停留时间，否则来不及看完就消失 */
 setTimeout(function(){d.style.transition='opacity .4s';d.style.opacity='0';setTimeout(function(){d.remove();},420);},kind==='err'?7000:2600);}
async function api(path,body){try{var r=await fetch(APIBASE+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});return await r.json();}
 catch(e){return {ok:false,offline:true,msg:'本地服务未启动，请运行 start_digest.bat 后刷新'};}}
function applyProfile(p){if(!p)return;if(p.weights)W=p.weights;if(p.kw)KW=p.kw;if(p.pens)PENS=p.pens;}
function scoreOf(p){var s=p.base+(PENS[p.id]||0);
 for(var k=0;k<(p.tv||[]).length;k++){s+=p.tv[k][1]*W[p.tv[k][0]];}
 var t=p.toks||[];for(var j=0;j<t.length;j++){s+=(KW[t[j]]||0);}
 return s;}
function eachBtn(sid,fn){document.querySelectorAll('[data-sid="'+sid+'"]').forEach(fn);}
function setFav(sid,on){eachBtn(sid,function(b){if(b.dataset.act!=='fav')return;
 b.classList.toggle('on',on);var lb=b.querySelector('.lb');if(lb)lb.textContent=on?'已收藏':'收藏';
 var ic=b.querySelector('.ico');if(ic)ic.textContent=on?'★':'☆';});syncCount();}
function setDl(sid,on){eachBtn(sid,function(b){if(b.dataset.act!=='dl')return;
 b.classList.toggle('done',!!on);var lb=b.querySelector('.lb');if(lb)lb.textContent=on?'已下载':'下载';});}
function setDv(sid,on){if(on)DV[sid]=1;else delete DV[sid];
 eachBtn(sid,function(b){if(b.dataset.act!=='dv')return;b.classList.toggle('on',!!on);
  var lb=b.querySelector('.lb');if(lb)lb.textContent=on?'已 Downvote':'Downvote';});
 document.querySelectorAll('.rec-card[data-sid="'+sid+'"],li.item[data-sid="'+sid+'"],'
  +'.hl[data-sid="'+sid+'"],.fav-item[data-sid="'+sid+'"]')
  .forEach(function(e){e.classList.toggle('down',!!on);});
 /* 记住点击时卡片在列表里的位次：重排时按这个位次「钉」回原处，
    让 Downvote 在三个模块里一律只是「变灰 + 删除线」，不位移、不消失。 */
 document.querySelectorAll('#rec-list .rec-card[data-sid="'+sid+'"],#exp-list .rec-card[data-sid="'+sid+'"]')
  .forEach(function(c){
   if(!on){delete c.dataset.dvpos;return;}
   var sibs=[].slice.call(c.parentNode.children).filter(function(e){return e.classList.contains('rec-card');});
   var i=sibs.indexOf(c);if(i>=0)c.dataset.dvpos=i;});}
function syncCount(){var s={};document.querySelectorAll('.btn.fav.on').forEach(function(b){if(b.dataset.sid)s[b.dataset.sid]=1;});
 var c=document.getElementById('favcount');if(c)c.textContent=Object.keys(s).length;}
async function track(sid,action,extra){var body={id:sid,action:action};if(extra)for(var k in extra)body[k]=extra[k];
 var r=await api('/api/event',body);applyProfile(r.profile);
 /* 只刷新分数数字，绝不重排：展开 Abstract / 点 PDF 时列表不能动，否则像页面在刷新。 */
 if(action==='abstract'||action==='pdf')rescore();return r;}
/* ---- 并发与响应速度：乐观更新 + 合并重排 ----
   1) 点按钮立刻改界面（不等网络往返），请求在后台跑：一篇论文正在下载时，
      别的论文的 Downvote / 收藏 / 下载照常响应，不同操作真正并行。
   2) 重排（排序 + 重新编号 + 视口锚定）在 30ms 内合并成一次，连点不会
      反复重排整屏。 */
var _rsT=0,_rsNoAnchor=false;
function queueResort(noAnchor){if(noAnchor)_rsNoAnchor=true;
 if(_rsT)return;
 _rsT=setTimeout(function(){_rsT=0;var na=_rsNoAnchor;_rsNoAnchor=false;resort(na);},30);}
function toggleFav(sid){
 var b=document.querySelector('.btn.fav[data-act="fav"][data-sid="'+sid+'"]');
 var on=!(b&&b.classList.contains('on'));
 setFav(sid,on);                    /* 先改按钮，再发请求（失败回滚） */
 api(on?'/api/favorite':'/api/unfavorite',{id:sid}).then(function(r){
  if(!r.ok){setFav(sid,!on);queueResort();toast(r.msg||'操作失败','err');return;}
  applyProfile(r.profile);toast(on?'已收藏 ★ '+sid:'已取消收藏 '+sid,'ok');queueResort();});}
function doDl(sid,btn){if(btn)btn.disabled=true;var lb=btn?btn.querySelector('.lb'):null;var old=lb?lb.textContent:'';
 if(lb)lb.textContent='下载中…';
 api('/api/download',{id:sid}).then(function(r){
  if(btn){btn.disabled=false;if(lb)lb.textContent=old;}
  if(r.ok){setFav(sid,true);setDl(sid,r.path||true);applyProfile(r.profile);
   toast('已下载并收藏：'+((r.path||'').split(/[\\\\/]/).pop()||sid),'ok');queueResort();}
  else toast('下载失败：'+(r.msg||''),'err');});}
function toggleDv(sid){
 var on=!DV[sid];
 setDv(sid,on);                     /* 先变灰划线，再发请求（失败回滚） */
 api(on?'/api/downvote':'/api/undownvote',{id:sid}).then(function(r){
  if(!r.ok){setDv(sid,!on);queueResort();toast(r.msg||'操作失败','err');return;}
  applyProfile(r.profile);
  toast(on?'已 Downvote：'+sid+'（变灰划线，再点一次可撤销）':'已撤销 Downvote：'+sid,'ok');
  queueResort();});}
function toggleAbs(sid,btn){var box=document.getElementById('ab-'+sid);if(!box)return;
 var open=!box.classList.contains('open');box.classList.toggle('open',open);
 document.querySelectorAll('[data-act="abs"][data-sid="'+sid+'"]').forEach(function(b){
  b.classList.toggle('open',open);var ic=b.querySelector('.ico');if(ic)ic.textContent=open?'▾':'▸';});
 if(open)track(sid,'abstract');}
async function dlAll(){var ids=[];document.querySelectorAll('#rec-list .rec-card:not(.hidden):not(.down),#exp-list .rec-card:not(.hidden):not(.down)').forEach(function(e){ids.push(e.dataset.sid);});
 if(!ids.length){toast('没有可下载的推荐','err');return;}
 toast('开始批量下载 '+ids.length+' 篇…');
 var r=await api('/api/download_all',{ids:ids});
 if(!r.ok){toast(r.msg||'批量下载失败','err');return;}
 (r.results||[]).forEach(function(x){if(x.ok){setFav(x.id,true);setDl(x.id,x.path||true);}});
 toast('完成：'+(r.n_ok||0)+' / '+ids.length+' 篇已保存到 '+(STATE.dldir||''),'ok');}
/* ---- 视口稳定：重排时把当前可见的那篇论文「钉」在原位置，避免跳到页面顶部 ---- */
function pageY(){return window.pageYOffset||document.documentElement.scrollTop||document.body.scrollTop||0;}
function noSmooth(on){document.documentElement.classList.toggle('nosm',!!on);}
function saveAnchor(){
  var y=pageY(),best=null;
  document.querySelectorAll('#rec-list .rec-card,#exp-list .rec-card,.plist li.item,.hl').forEach(function(e){
    if(e.classList.contains('hidden'))return;
    var r=e.getBoundingClientRect();
    if(r.height&&r.bottom>0&&(!best||r.top<best.top))best={el:e,top:r.top,y:y};});
  return best||{el:null,top:0,y:y};}
function restoreAnchor(a){if(!a)return;
  noSmooth(true);
  var y=a.y;
  if(a.el&&a.el.isConnected&&!a.el.classList.contains('hidden')){
    var r=a.el.getBoundingClientRect();
    if(r.height)y=pageY()+(r.top-a.top);}
  y=Math.max(0,y);
  window.scrollTo(0,y);
  requestAnimationFrame(function(){window.scrollTo(0,y);noSmooth(false);});}
function rescore(){['rec-list','exp-list'].forEach(function(id){
 var box=document.getElementById(id);if(!box)return;
 box.querySelectorAll('.rec-card').forEach(function(c){
  var p=BYID[c.dataset.sid];var s=p?scoreOf(p):parseFloat(c.dataset.score||0);
  c.dataset.score=s.toFixed(2);var sc=c.querySelector('.score');if(sc)sc.textContent=s.toFixed(1);
  if(p){var tg=c.querySelector('.tag');if(tg&&p.primary)tg.textContent=p.primary;}});});}
function resort(noAnchor){var anchor=noAnchor?null:saveAnchor();
 rescore();
 ['rec-list','exp-list'].forEach(function(id){
 var box=document.getElementById(id);if(!box)return;
 var all=[].slice.call(box.querySelectorAll('.rec-card'));
 /* Downvote 的卡片一律不隐藏（与「分类详解」同一套逻辑：变灰 + 删除线），
    并钉在点击时记下的位次上，所以它既不消失也不跳到别处，再点一次即可撤销。
    data-limit 只约束「正常推荐」的条数，灰色卡片额外保留。 */
 var ups=all.filter(function(c){return !DV[c.dataset.sid];});
 var downs=all.filter(function(c){return DV[c.dataset.sid];});
 ups.sort(function(a,b){return parseFloat(b.dataset.score)-parseFloat(a.dataset.score);});
 var limit=parseInt(box.dataset.limit||'14',10),shown=0;
 ups.forEach(function(c){var hide=shown>=limit;c.classList.toggle('hidden',hide);if(!hide)shown++;});
 var cards=ups.slice();
 downs.forEach(function(c){
  c.classList.remove('hidden');
  var p=parseInt(c.dataset.dvpos||'',10);if(isNaN(p))p=cards.length;
  cards.splice(Math.max(0,Math.min(p,cards.length)),0,c);});
 /* 顺序没变就不动 DOM —— 逐个 appendChild 会造成整屏闪烁与跳动 */
 var cur=[].slice.call(box.children).filter(function(e){return e.classList.contains('rec-card');});
 var same=cur.length===cards.length;
 if(same)for(var i=0;i<cards.length;i++){if(cur[i]!==cards[i]){same=false;break;}}
 if(!same){var frag=document.createDocumentFragment();
  cards.forEach(function(c){frag.appendChild(c);});box.appendChild(frag);}
 var no=box.querySelectorAll('.rec-card:not(.hidden)');
 for(var j=0;j<no.length;j++){var e2=no[j].querySelector('.rec-no');if(e2)e2.textContent=('0'+(j+1)).slice(-2);}
 var em=box.querySelector('.empty');if(em)em.style.display=shown?'none':'';});
 restoreAnchor(anchor);updateRail();}
/* ---- 视口稳定结束 ---- */
/* ---- 侧边导航（分类横线）+ 回到顶部 ---- */
var RAIL=[];
function railInit(){RAIL=[];
 document.querySelectorAll('#rail .navi').forEach(function(n){
  var el=document.getElementById(n.dataset.target);
  if(el)RAIL.push({n:n,el:el});});
 updateRail();}
function updateRail(){if(!RAIL.length)return;
 var best=null;
 RAIL.forEach(function(t){var top=t.el.getBoundingClientRect().top;
  if(top<=150&&(!best||top>best.top))best={item:t,top:top};});
 var act=best?best.item:RAIL[0];
 RAIL.forEach(function(t){t.n.classList.toggle('on',t===act);});}
/* 用 setTimeout 节流而不是 requestAnimationFrame：后台标签页/无头环境里 rAF 会停摆，
   导致高亮更新滞后甚至不更新。 */
var _st=0;
function onScroll(){if(_st)return;_st=setTimeout(function(){_st=0;
 updateRail();
 var b=document.getElementById('totop');if(b)b.classList.toggle('show',pageY()>420);},90);}
function openFolder(){api('/api/open_folder',{}).then(function(r){if(!r.ok)toast(r.msg||'打开失败','err');});}
async function openPaper(sid){var r=await api('/api/open',{id:sid});if(!r.ok)toast(r.msg||'尚未下载该论文','err');}
function applyFilter(mode){document.querySelectorAll('.tb[data-mode]').forEach(function(b){b.classList.toggle('on',b.dataset.mode===mode);});
 var q=(document.getElementById('q').value||'').toLowerCase();
 document.querySelectorAll('li.item').forEach(function(li){
   var sid=li.dataset.sid, ok=true;
   if(mode==='fav'&&!li.querySelector('.btn.fav.on'))ok=false;
   if(mode==='dl'&&!li.querySelector('.btn.dl.done'))ok=false;
   if(mode==='dv'&&!DV[sid])ok=false;
   if(ok&&q)ok=(li.textContent||'').toLowerCase().indexOf(q)>=0;
   li.classList.toggle('hidden',!ok);});
 document.querySelectorAll('.cat').forEach(function(s){
   var vis=s.querySelectorAll('li.item:not(.hidden)').length;
   s.style.display=(q||mode!=='all')?(vis?'':'none'):'';});}
var STATE={dldir:''};
document.addEventListener('click',function(ev){
 var b=ev.target.closest('button[data-act]');
 if(b){ev.preventDefault();var sid=b.dataset.sid,a=b.dataset.act;
  if(a==='fav')toggleFav(sid);else if(a==='dl')doDl(sid,b);
  else if(a==='abs')toggleAbs(sid,b);else if(a==='dv')toggleDv(sid,b);return;}
 var p=ev.target.closest('a.pdf[data-sid]');if(p){track(p.dataset.sid,'pdf');return;}
 var o=ev.target.closest('button[data-open]');if(o){openPaper(o.dataset.open);}});
document.addEventListener('DOMContentLoaded',function(){
 var q=document.getElementById('q');
 if(q)q.addEventListener('input',function(){var m=(document.querySelector('.tb[data-mode].on')||{dataset:{mode:'all'}}).dataset.mode;applyFilter(m);});
 document.querySelectorAll('.tb[data-mode]').forEach(function(b){b.addEventListener('click',function(){applyFilter(b.dataset.mode);});});
 var da=document.getElementById('dlall');if(da)da.addEventListener('click',dlAll);
 var of=document.getElementById('openfolder');if(of)of.addEventListener('click',openFolder);
 var fl=document.getElementById('favlink');if(fl)fl.href=APIBASE+'/favorites';
 var pf=document.getElementById('proflink');if(pf)pf.href=APIBASE+'/profile';
 railInit();
 var tt=document.getElementById('totop');
 if(tt)tt.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});
 window.addEventListener('scroll',onScroll,{passive:true});
 window.addEventListener('resize',railInit);
 onScroll();
 fetch(APIBASE+'/api/state').then(function(r){return r.json();}).then(function(s){
   STATE.dldir=s.download_dir||'';
   document.querySelectorAll('.dldir,.dldir-m').forEach(function(e){
     if(STATE.dldir)e.textContent=STATE.dldir;});
   (s.favorites||[]).forEach(function(id){setFav(id,true);});
   Object.keys(s.downloads||{}).forEach(function(id){setDl(id,s.downloads[id]);});
   (s.downvotes||[]).forEach(function(id){setDv(id,true);});
   applyProfile(s.profile);syncCount();resort(true);
  }).catch(function(){toast('本地服务未运行：收藏/下载/Downvote 不可用，请运行 start_digest.bat','err');});});
"""
JS = JS.replace("__APIPORT__", str(_PORT))

PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>arXiv cs.* 论文摘要 · %(span)s</title>
<link rel="icon" href="data:,">
<style>%(css)s</style></head><body id="top">
<div class="wrap">
<header>
<h1>arXiv cs.* 新论文摘要</h1>
<div class="sub">覆盖 %(cats)s ｜ 提交时间 %(span)s（UTC）｜ 本期新增 <b>%(total)d</b> 篇 ｜ 生成于 %(gen)s ｜
下载目录 <code class="dldir">%(dldir)s</code></div>
</header>

%(notice)s

<div class="toolbar">
<button class="tb on" data-mode="all">全部</button>
<button class="tb" data-mode="fav">已收藏</button>
<button class="tb" data-mode="dl">已下载</button>
<button class="tb" data-mode="dv">已 Downvote</button>
<input class="search" id="q" placeholder="搜索标题 / 摘要…">
<span class="grow"></span>
<span class="counter">收藏 <b id="favcount">0</b> 篇</span>
<button class="tb" id="dlall">⬇ 下载全部推荐</button>
<button class="tb" id="openfolder">📁 打开目录</button>
<a class="tb" id="favlink" href="/favorites" target="_blank">★ 收藏列表</a>
<a class="tb" id="archlink" href="/archive">🗂 历史存档</a>
<a class="tb" id="proflink" href="/profile">⚙ 画像与设置</a>
</div>

<div class="stats">%(stats)s</div>

<div class="rec-box" id="sec-rec">
<div class="rec-h">🎯 为你推荐<span class="cnt">基于 %(srclabels)s 的兴趣画像</span></div>
<p class="rec-sub">%(topicline)s
「Abstract」就地展开原文摘要；「下载」按 <code>arXiv&lt;年&gt; &lt;arXiv号&gt; &lt;去标点标题&gt;.pdf</code>
保存到 <code class="dldir-m">%(dldir)s</code> 并自动收藏；「Downvote」表示不感兴趣：卡片当场<b>变灰 + 标题删除线</b>并留在原位（再点一次撤销），画像同时降权该类主题。
按钮动作即时生效、互不等待，一篇论文正在下载时其余操作照常响应。
类别、兴趣来源与下载目录可在 <a href="/profile">⚙ 画像与设置</a> 里增删修改。</p>
<div id="rec-list" data-limit="%(toprec)d">%(recs)s</div>
</div>

<div class="exp-box" id="sec-exp">
<div class="rec-h">🌱 兴趣扩展<span class="cnt">来自六分类之外的 %(excats)s 等，用于打破知识茧房</span></div>
<p class="rec-sub">这些论文不在你日常追踪的六个分类里，但主题上与你的研究方向相邻。
它们同样支持收藏 / 下载 / Abstract / Downvote；如果觉得不相关，直接 Downvote，画像会自动降权该类主题。
Downvote 的表现与「为你推荐」「分类详解」完全一致：变灰 + 删除线，卡片不消失，可随时再点一次撤销。</p>
<div id="exp-list" data-limit="%(topexp)d">%(exps)s</div>
</div>

%(themes)s
<h2 class="sec-h">分类详解</h2>
%(secs)s

<footer>
数据来源：arXiv API（export.arxiv.org）｜ 本页<b>只呈现本期新增</b>的论文；往期日报已存档，可点上方「🗂 历史存档」按日期回看。<br>
标题与作者保留英文原文，摘要为中文归纳；推荐理由结合个人兴趣画像自动生成。<br>
收藏 / 下载 / Downvote 记录保存在 output/library.json，行为画像保存在 output/profile_state.json。
</footer>
</div>
<nav id="rail" aria-label="章节导航">%(rail)s</nav>
<button id="totop" type="button" aria-label="回到顶部" title="回到顶部">↑</button>
<div id="toast"></div>
<script id="pdata" type="application/json">%(pdata)s</script>
<script>%(js)s</script>
</body></html>
"""


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
    excats = "、".join((cfg.get("expand_categories") or [])[:8])

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
                "summary", "tv", "base", "toks", "pen", "topics",
                "familiar_authors", "systems")} for p in idx.get("papers", [])],
        }

    return PAGE % {
        "css": CSS, "js": JS, "span": span,
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


def build_md(d, groups, recs, exps):
    L = ["# arXiv cs.* 新论文摘要\n",
         "覆盖范围：%s ｜ 共 %d 篇 ｜ 生成于 %s\n"
         % ("、".join(d.get("categories", [])), len(d["papers"]),
            d.get("generated_at", "").replace("T", " "))]
    L.append("\n## 🎯 个性化推荐\n")
    for i, r in enumerate(recs, 1):
        L.append("%d. **[%s](%s)** `%s` · %s · %s · %.1f 分"
                 % (i, r.get("title", ""), pdf_url(r["id"]), r["id"],
                    r.get("primary", ""), r.get("published", ""), r.get("score", 0)))
        if r.get("summary"):
            L.append("   - %s" % r["summary"])
        L.append("   - **推荐理由：** %s" % (r.get("note") or ""))
    if exps:
        L.append("\n## 🌱 兴趣扩展\n")
        for i, r in enumerate(exps, 1):
            L.append("%d. **[%s](%s)** `%s` · %s · %s"
                     % (i, r.get("title", ""), pdf_url(r["id"]), r["id"],
                        r.get("primary", ""), r.get("published", "")))
            if r.get("summary"):
                L.append("   - %s" % r["summary"])
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
            if p.get("_summary"):
                L.append("  - %s" % p["_summary"])
            if p.get("_hl"):
                L.append("  - **看点：** %s" % p["_hl"])
        L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------- 收藏页

FAV_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>论文收藏列表</title>
<link rel="icon" href="data:,">
<style>%(css)s
.fav-item{display:flex;gap:12px;padding:14px 0;border-top:1px dashed var(--bd)}
.fav-item:first-child{border-top:none}
.fi-no{color:var(--tx3);font-size:12.5px;min-width:26px;padding-top:3px;font-variant-numeric:tabular-nums}
.fi-main{flex:1;min-width:0}
.hd{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:3px}
.dl-yes{font-size:11.5px;background:#eaf7f0;color:var(--ok);border-radius:5px;padding:2px 8px}
.dl-no{font-size:11.5px;background:#f1f3f6;color:var(--tx3);border-radius:5px;padding:2px 8px}
.path{font-size:11.8px;color:var(--tx3);word-break:break-all;margin-top:4px}
</style></head><body><div class="wrap">
<header>
<h1>★ 论文收藏列表</h1>
<div class="sub">共 <b>%(n)d</b> 篇 ｜ 其中已下载 <b>%(nd)d</b> 篇 ｜ 下载目录 <code class="dldir">%(dldir)s</code> ｜ 更新于 %(now)s</div>
</header>
<div class="toolbar">
<button class="tb" id="openfolder">📁 打开下载目录</button>
<button class="tb" id="export">⬇ 导出清单 (.md)</button>
<span class="grow"></span>
<span class="counter">收藏 <b id="favcount">0</b> 篇</span>
<a class="tb" href="/archive">🗂 历史存档</a>
<a class="tb" href="/profile">⚙ 画像与设置</a>
<a class="tb" id="backlink" href="/">← 回到本期摘要</a>
</div>
<div class="cat">%(items)s</div>
<footer>收藏记录来源：output/library.json</footer>
</div>
<button id="totop" type="button" aria-label="回到顶部" title="回到顶部">↑</button>
<div id="toast"></div>
<script>%(js)s</script>
<script>
function exportMd(){var lines=['# 收藏论文清单\\n'];
document.querySelectorAll('.fav-item').forEach(function(e,i){
 var t=e.querySelector('a.fav-t');var m=e.querySelector('.fi-meta');
 lines.push((i+1)+'. ['+(t?t.textContent:'')+']('+(t?t.href:'')+')');
 lines.push('   - '+(m?m.textContent.trim():''));});
 var blob=new Blob([lines.join('\\n')],{type:'text/markdown;charset=utf-8'});
 var a=document.createElement('a');a.href=URL.createObjectURL(blob);
 a.download='favorites.md';a.click();URL.revokeObjectURL(a.href);toast('已导出 favorites.md','ok');}
document.addEventListener('DOMContentLoaded',function(){
 var of=document.getElementById('openfolder');if(of)of.addEventListener('click',openFolder);
 var ex=document.getElementById('export');if(ex)ex.addEventListener('click',exportMd);
 var bl=document.getElementById('backlink');if(bl)bl.href=APIBASE+'/';
 var tt=document.getElementById('totop');
 if(tt)tt.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});
 function fvScroll(){if(tt)tt.classList.toggle('show',pageY()>420);}
 window.addEventListener('scroll',fvScroll,{passive:true});fvScroll();
 fetch(APIBASE+'/api/state').then(function(r){return r.json();}).then(function(s){
  STATE.dldir=s.download_dir||'';(s.favorites||[]).forEach(function(id){setFav(id,true);});
  Object.keys(s.downloads||{}).forEach(function(id){setDl(id,s.downloads[id]);});
  (s.downvotes||[]).forEach(function(id){setDv(id,true);});syncCount();}).catch(function(){});});
document.addEventListener('click',function(ev){
 var b=ev.target.closest('button[data-act]');
 if(b){ev.preventDefault();var a=b.dataset.act,sid=b.dataset.sid;
  if(a==='fav')toggleFav(sid);else if(a==='dl')doDl(sid,b);
  else if(a==='abs')toggleAbs(sid,b);else if(a==='dv')toggleDv(sid,b);return;}
 var o=ev.target.closest('button[data-open]');if(o){openPaper(o.dataset.open);return;}
 var p=ev.target.closest('a.pdf[data-sid]');if(p){track(p.dataset.sid,'pdf');}});
</script>
</body></html>
"""


def build_favorites(lib):
    load_affiliations()
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
            '<button class="btn ab" data-act="abs" data-sid="%s"><span class="ico">▸</span><span class="lb">Abstract</span></button>'
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
               esc(sid),
               ('<button class="btn" data-open="%s">打开</button>' % esc(sid)) if dlp else "",
               esc(sid), esc(pdf_url(sid)), esc(sid),
               abst_block(sid, f.get("abstract", ""))))
    if not items:
        items = ['<div class="empty">还没有收藏。回到摘要页点击「☆ 收藏」即可加入这里；'
                 '点击「⬇ 下载」会自动收藏并保存 PDF。</div>']
    return FAV_PAGE % {
        "css": CSS, "js": JS, "n": len(favs),
        "nd": sum(1 for s in favs if lib.get("downloads", {}).get(s, {}).get("path")),
        "dldir": esc(cfg["download_dir"]), "now": pu.now_str(), "items": "".join(items),
    }


# ---------------------------------------------------------------- 画像与设置页

PROFILE_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>兴趣画像与设置</title>
<link rel="icon" href="data:,">
<style>%(css)s
.panel{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:18px 22px 20px;margin-bottom:18px}
.p-h{font-size:14.5px;font-weight:700;margin:16px 0 8px;display:flex;align-items:baseline;gap:9px;flex-wrap:wrap}
.p-h:first-child{margin-top:0}
.p-hint{font-size:12px;color:var(--tx3);font-weight:400}
.p-note{font-size:13px;color:var(--tx2);margin:0 0 12px;line-height:1.75}
.p-note code{background:#f1f3f6;padding:1px 5px;border-radius:4px;font-size:12.2px}
.owners{display:grid;grid-template-columns:repeat(auto-fit,minmax(258px,1fr));gap:12px}
.owner{border:1px solid var(--bd);border-radius:12px;padding:13px 15px;background:#fbfcfe}
.owner h4{margin:0 0 3px;font-size:14.5px}
.owner .aff{font-size:12.2px;color:var(--tx2);margin-bottom:6px}
.owner ul{margin:6px 0 0;padding-left:18px;font-size:12.6px;color:var(--tx2);line-height:1.7}
.owner a{font-size:12px;color:var(--ac);text-decoration:none;word-break:break-all}
.ow-top{display:flex;align-items:flex-start;gap:8px}
.ow-top h4{flex:1;min-width:0}
.ow-act{display:flex;gap:6px;flex-shrink:0}
.ow-tag{font-size:11.5px;color:var(--exp);background:#eaf7f0;border-radius:5px;
 padding:2px 7px;display:inline-block;margin-top:8px}
.own-form{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px;
 align-items:start;margin-bottom:14px;padding:12px 14px;border:1px dashed var(--bd);border-radius:10px;background:#fcfdfe}
.own-form input,.own-form textarea{border:1px solid var(--bd);border-radius:8px;padding:7px 11px;
 font-size:13.2px;font-family:inherit;color:var(--tx);background:#fff;width:100%%;box-sizing:border-box}
.own-form textarea{grid-column:1/-1;resize:vertical;line-height:1.6}
.own-form .chk{grid-column:1/-1;font-size:12.8px;color:var(--tx2);display:flex;align-items:center;gap:6px}
.own-form .chk input{width:auto}
.own-form .tb{align-self:center}
.own-form.editing{border-color:var(--ac);background:#f7faff}
.themes{display:flex;flex-direction:column;gap:7px}
.theme-row{display:grid;grid-template-columns:minmax(112px,196px) 1fr 58px;gap:10px;align-items:center}
.theme-name{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.theme-row.is-custom .theme-name{color:var(--exp);font-weight:700}
.bar{height:9px;background:#eef1f5;border-radius:6px;overflow:hidden}
.bar i{display:block;height:100%%;border-radius:6px;background:linear-gradient(90deg,#5b93f5,var(--ac))}
.theme-row.is-custom .bar i{background:linear-gradient(90deg,#48c79b,var(--exp))}
.theme-w{font-size:12.5px;color:var(--tx2);text-align:right;font-variant-numeric:tabular-nums}
.form{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.form input,.form select{border:1px solid var(--bd);border-radius:8px;padding:7px 11px;font-size:13.5px;
 font-family:inherit;color:var(--tx);background:#fff;min-width:0}
.form #src-value{flex:1;min-width:240px}
.form #src-note{width:150px}
.form #cat-value{width:160px}
.form #cat-name{flex:1;min-width:180px}
.form #dldir{flex:1;min-width:240px}
.tb.primary{background:var(--ac);border-color:var(--ac);color:#fff;font-weight:600}
.tb.primary:hover{background:#2560d4;border-color:#2560d4;color:#fff}
.src-item,.cat-item{display:flex;gap:12px;align-items:flex-start;padding:11px 0;border-top:1px dashed var(--bd)}
.src-item:first-child,.cat-item:first-child{border-top:none}
.si-main{flex:1;min-width:0}
.si-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.si-type{font-size:11px;border-radius:5px;padding:2px 7px;background:var(--acbg);color:var(--ac);font-weight:600}
.si-type.paper{background:#fdf0dd;color:#a15c00}
.si-type.doc{background:#e9f8f1;color:var(--exp)}
.si-val{font-size:12.6px;color:var(--tx2);word-break:break-all;margin-top:3px}
.si-title{font-size:13.2px;font-weight:600;margin-top:3px}
.si-err{font-size:12.2px;color:var(--warn);margin-top:4px}
.si-chips{margin-top:7px;display:flex;flex-wrap:wrap;gap:5px}
.tp.kw{cursor:pointer;user-select:none}
.tp.kw:hover{background:#dfe9ff;box-shadow:inset 0 0 0 1px var(--ac)}
.tp.kw.blk{background:#f1f3f6;color:var(--tx3);text-decoration:line-through;opacity:.65}
.tp.kw.blk:hover{background:#e6e9ee;box-shadow:inset 0 0 0 1px var(--tx3)}
.cat-item{align-items:center}
.cat-code{font-weight:800;color:var(--ac);font-size:14.5px;min-width:76px}
.cat-topic{flex:1;font-size:13.4px}
.cat-n{font-size:12.5px;color:var(--tx3);font-variant-numeric:tabular-nums}
.btn-x{background:#fff;border:1px solid var(--bd);color:var(--tx3);border-radius:7px;padding:3px 9px;
 font-size:12px;cursor:pointer;font-family:inherit}
.btn-x:hover{border-color:var(--warn);color:var(--warn)}
.chips.neg .chip{background:#fdecec;color:var(--warn)}
.p-empty{color:var(--tx3);font-size:13px;padding:8px 0}
</style></head><body id="top"><div class="wrap">
<header>
<h1>⚙ 兴趣画像与设置</h1>
<div class="sub">%(summary)s</div>
</header>
<div class="toolbar">
<a class="tb" id="backlink" href="/">← 回到本期摘要</a>
<a class="tb" href="/favorites">★ 收藏列表</a>
<a class="tb" href="/archive">🗂 历史存档</a>
<button class="tb" id="openfolder">📁 打开下载目录</button>
<button class="tb" id="rebuild" title="重跑 recommend.py + build_report.py（不重新抓取），让类别与画像改动立刻反映到摘要页">↻ 重算推荐</button>
<span class="grow"></span>
<span class="counter">兴趣来源 <b id="srccount">0</b> 条</span>
</div>

<h2 class="sec-h">🎛 兴趣画像</h2>
<div class="panel">
<div class="p-h">画像主来源<span class="p-hint">摘要页头部「基于 … 的兴趣画像」就取自这里</span></div>
<p class="p-note">下面几位是画像的主来源（本人 + 对标研究者），可<b>新增 / 编辑 / 删除</b>。
「简称」用于摘要页头部那行文案（留空则显示姓名）；勾选<b>计入熟悉研究者</b>后，
该作者出现在论文作者列表里即 <b>+10 分／篇</b>，删除该来源会同时撤销这条加成。
改动后点工具栏 <b>↻ 重算推荐</b>，摘要页的文案与排序即刻同步。</p>
<div class="form own-form" id="own-form">
<input id="own-name" placeholder="姓名（必填，如 Jane Doe / 张三）">
<input id="own-label" placeholder="简称（可选，头部显示）">
<input id="own-site" placeholder="主页 https://…（可选）">
<input id="own-affil" placeholder="所属机构（可选）">
<input id="own-interests" placeholder="研究兴趣一句话（可选）">
<textarea id="own-topics" rows="2" placeholder="代表方向（每行一条，可选）"></textarea>
<label class="chk"><input type="checkbox" id="own-link" checked> 计入熟悉研究者（+10/篇）</label>
<button class="tb primary" id="own-save">+ 添加画像来源</button>
<button class="tb" id="own-cancel" style="display:none">取消编辑</button>
</div>
<div class="owners" id="owners">%(owners)s</div>
<div class="p-h">主题权重<span class="p-hint">权重 = 种子权重 × 行为学习倍率；收藏 / 下载 / Downvote 会实时改变倍率</span></div>
<div class="themes" id="themes"></div>
<div class="p-h">熟悉研究者<span class="p-hint">姓名出现在作者列表里即 +10 分／篇；由下方「兴趣来源」自动扩充</span></div>
<div class="chips" id="people"></div>
<div class="p-h">代表系统<span class="p-hint">标题 / 摘要里出现即 +6 分</span></div>
<div class="chips" id="systems"></div>
<div class="p-h">降权关键词<span class="p-hint">出现即减分（用于压掉与主线无关的热点）</span></div>
<div class="chips neg" id="negkw"></div>
</div>

<h2 class="sec-h">🔗 兴趣来源（链接 / 论文 / 文档）</h2>
<div class="panel">
<p class="p-note">添加后系统会尽力解析出<b>人名</b>与<b>专业实词</b>：人名并入「熟悉研究者」（命中 +10 分／篇），
实词汇入主题<b>「%(customtopic)s」</b>（权重 %(customw)s），用于提升相关论文的排序。删除来源即撤销它的全部增量。
自动抽词难免有噪音，<b>点任意关键词即可屏蔽 / 恢复</b>（划掉 = 已屏蔽，不计入画像）。
改动后点工具栏的 <b>↻ 重算推荐</b> 即可让摘要页排序立刻反映新画像。</p>
<div class="form">
<select id="src-type">
<option value="link">🔗 链接</option>
<option value="paper">📄 arXiv 论文</option>
<option value="doc">📁 本地文档</option>
</select>
<input id="src-value" placeholder="https://… 或 2609.09742 或 D:/path/paper.pdf">
<input id="src-note" placeholder="备注（可选）">
<button class="tb primary" id="src-add">+ 添加</button>
</div>
<div id="src-list"></div>
</div>

<h2 class="sec-h">🗂 arXiv 类别</h2>
<div class="panel">
<p class="p-note">增删会写入 <code>config.json</code>。<b>新增</b>类别后需重新抓取（重跑 <code>run_daily.py</code>）
才会出现该类别的论文；<b>删除</b>只影响下一次抓取。</p>
<div class="form">
<input id="cat-value" placeholder="如 cs.LG / math.CO / stat.ML">
<input id="cat-name" placeholder="主题名（可选，留空自动匹配内置中文名）">
<button class="tb primary" id="cat-add">+ 添加类别</button>
</div>
<div id="cat-list"></div>
</div>

<h2 class="sec-h">📁 下载目录</h2>
<div class="panel">
<div class="form">
<input id="dldir" placeholder="例如 ./papers 或 D:/papers">
<button class="tb primary" id="dldir-save">保存</button>
<button class="tb" id="dldir-open">📁 打开</button>
</div>
<p class="p-note">修改后<b>立即生效</b>（下载接口每次都读 <code>config.json</code>）；摘要页顶部显示的路径在下次重建页面后同步。</p>
</div>
<footer>画像：<code>interests.json</code> ｜ 来源增量：<code>output/interests_extra.json</code> ｜
行为学习：<code>output/profile_state.json</code></footer>
</div>
<button id="totop" type="button" aria-label="回到顶部" title="回到顶部">↑</button>
<div id="toast"></div>
<script>%(js)s</script>
<script>
function esc2(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML;}
var BLOCKED={};
function chip(t,cls){return '<span class="tp'+(cls?' '+cls:'')+'">'+esc2(t)+'</span>';}
function renderThemes(th){
 var mx=1;(th||[]).forEach(function(t){if(t.weight>mx)mx=t.weight;});
 var h=(th||[]).map(function(t){
  var w=Math.max(4,Math.round(t.weight/mx*100));
  return '<div class="theme-row'+(t.custom?' is-custom':'')+'" title="'+esc2(t.name)+'｜种子 '+t.seed+
   ' × 倍率 '+t.mult+' ｜ '+t.nkw+' 个关键词">'
   +'<span class="theme-name">'+esc2(t.name)+'</span>'
   +'<span class="bar"><i style="width:'+w+'%%"></i></span>'
   +'<span class="theme-w">'+t.weight.toFixed(2)+'</span></div>';}).join('');
 document.getElementById('themes').innerHTML=h||'<div class="p-empty">暂无主题</div>';}
function renderChips(id,arr,cls){
 document.getElementById(id).innerHTML=(arr||[]).map(function(x){return chip(x,cls);}).join('')
  ||'<span class="p-empty">（空）</span>';}
function renderSources(list){
 document.getElementById('srccount').textContent=(list||[]).length;
 var el=document.getElementById('src-list');
 if(!list||!list.length){el.innerHTML='<div class="p-empty">还没有添加来源。可以添加个人主页、arXiv 论文或本地 PDF / 笔记。</div>';return;}
 el.innerHTML=list.map(function(s){
  var tn={link:'🔗 链接',paper:'📄 论文',doc:'📁 文档'}[s.type]||s.type;
  var ch=(s.people||[]).map(function(p){return chip(p,'au');}).join('')
        +(s.keywords||[]).map(function(k){
          var off=BLOCKED[k.toLowerCase()]?' blk':'';
          return '<span class="tp kw'+off+'" data-kw="'+esc2(k)+'" title="点击屏蔽 / 恢复该关键词">'+esc2(k)+'</span>';}).join('');
  return '<div class="src-item"><div class="si-main">'
   +'<div class="si-top"><span class="si-type '+esc2(s.type)+'">'+tn+'</span>'
   +'<span class="cat-n">'+esc2(s.added_at)+'</span>'
   +((s.matched_topics||[]).length?'<span class="date">相关主题：'+esc2(s.matched_topics.join('、'))+'</span>':'')
   +'</div>'
   +(s.title?'<div class="si-title">'+esc2(s.title)+'</div>':'')
   +'<div class="si-val">'+esc2(s.value)+'</div>'
   +(s.note?'<div class="si-val">备注：'+esc2(s.note)+'</div>':'')
   +(s.error?'<div class="si-err">⚠ '+esc2(s.error)+'</div>':'')
   +(ch?'<div class="si-chips">'+ch+'</div>':'')
   +'</div><button class="btn-x" data-del-src="'+esc2(s.sid)+'">删除</button></div>';}).join('');}
/* ---- 画像主来源（interests.json 的 owners）：新增 / 编辑 / 删除 ----
   表单是「新增」与「编辑」共用的：点卡片上的「编辑」把该条填进表单，
   按钮变成「保存修改」，提交时带 orig=原姓名，服务端按原名定位后整条覆盖（允许改名）。 */
var OWNS=[],EDITING=null;
function ownerCard(o){
 var ch=(o.signature_topics||[]).slice(0,4).map(function(s){return '<li>'+esc2(s)+'</li>';}).join('');
 return '<div class="owner" data-owner="'+esc2(o.name)+'">'
  +'<div class="ow-top"><h4>'+esc2(o.name)+'</h4><span class="ow-act">'
  +'<button class="btn-x" data-edit-owner="'+esc2(o.name)+'">编辑</button>'
  +'<button class="btn-x" data-del-owner="'+esc2(o.name)+'">删除</button></span></div>'
  +(o.affiliation?'<div class="aff">'+esc2(o.affiliation)+'</div>':'')
  +(o.site?'<a href="'+esc2(o.site)+'" target="_blank" rel="noopener">'+esc2(o.site)+'</a>':'')
  +(o.interests?'<div class="date">'+esc2(o.interests)+'</div>':'')
  +(ch?'<ul>'+ch+'</ul>':'')
  +(o.people_linked?'<span class="ow-tag">已计入熟悉研究者（+10/篇）</span>':'')
  +'</div>';}
function renderOwners(){
 var el=document.getElementById('owners');if(!el)return;
 el.innerHTML=(OWNS||[]).map(ownerCard).join('')
  ||'<div class="p-empty">还没有画像主来源，请在上方添加。</div>';}
function ownForm(d){d=d||{};
 var set=function(id,v){var e=document.getElementById(id);if(e)e.value=v==null?'':v;};
 set('own-name',d.name);set('own-label',d.label);set('own-site',d.site);
 set('own-affil',d.affiliation);set('own-interests',d.interests);
 set('own-topics',(d.signature_topics||[]).join('\\n'));
 var lk=document.getElementById('own-link');if(lk)lk.checked=(d.people_linked!==false);
 var f=document.getElementById('own-form');if(f)f.classList.toggle('editing',!!EDITING);
 var sv=document.getElementById('own-save');if(sv)sv.textContent=EDITING?'保存修改':'+ 添加画像来源';
 var cc=document.getElementById('own-cancel');if(cc)cc.style.display=EDITING?'':'none';}
function ownPayload(){
 var g=function(id){var e=document.getElementById(id);return e?e.value.trim():'';};
 var lk=document.getElementById('own-link');
 return {name:g('own-name'),label:g('own-label'),site:g('own-site'),
  affiliation:g('own-affil'),interests:g('own-interests'),
  signature_topics:g('own-topics').split('\\n'),
  link_person:lk?!!lk.checked:true};}
function ownSubmit(btn){
 var p=ownPayload();
 if(!p.name){toast('姓名不能为空','err');return;}
 var body=EDITING?Object.assign({},p,{op:'update',orig:EDITING})
                  :Object.assign({},p,{op:'add'});
 var lbl=EDITING?'保存修改':'+ 添加画像来源';
 busy(btn,true,'保存中…');
 api('/api/owner',body).then(function(r){
  busy(btn,false,lbl);toast(r.msg||'',r.ok?'ok':'err');
  if(r.ok){EDITING=null;ownForm({people_linked:true});apply(r.state);}});}
function startEditOwner(name){
 var o=(OWNS||[]).filter(function(x){return x.name===name;})[0];
 if(!o)return;
 EDITING=name;ownForm(o);
 var f=document.getElementById('own-form');
 if(f&&f.scrollIntoView)f.scrollIntoView({behavior:'smooth',block:'center'});
 var n=document.getElementById('own-name');if(n)n.focus();}
function renderCats(cats,names){
 document.getElementById('cat-list').innerHTML=
  (cats||[]).map(function(c){
   return '<div class="cat-item"><span class="cat-code">'+esc2(c)+'</span>'
    +'<span class="cat-topic">'+esc2((names||{})[c]||'（未命名主题）')+'</span>'
    +'<button class="btn-x" data-del-cat="'+esc2(c)+'">删除</button></div>';}).join('')
  ||'<div class="p-empty">至少要保留一个类别</div>';}
function apply(d){if(!d)return;
 var p=d.profile||{};
 BLOCKED={};((d.blocked_keywords)||[]).forEach(function(k){BLOCKED[String(k).toLowerCase()]=1;});
 OWNS=p.owners||[];
 renderOwners();
 renderThemes(p.themes||[]);
 renderChips('people',p.people,'au');
 renderChips('systems',p.systems);
 renderChips('negkw',p.negative);
 renderSources(d.sources||[]);
 renderCats(d.categories||[],d.category_names||{});
 var de=document.getElementById('dldir');
 if(de&&document.activeElement!==de)de.value=d.download_dir||'';}
function busy(btn,on,txt){if(!btn)return;btn.disabled=!!on;if(txt)btn.textContent=txt;}
document.addEventListener('DOMContentLoaded',function(){
 var tt=document.getElementById('totop');
 if(tt)tt.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});
 function sl(){if(tt)tt.classList.toggle('show',pageY()>420);}
 window.addEventListener('scroll',sl,{passive:true});sl();
 var of=document.getElementById('openfolder');if(of)of.addEventListener('click',openFolder);
 var bl=document.getElementById('backlink');if(bl)bl.href=APIBASE+'/';

 var sa=document.getElementById('src-add');
 if(sa)sa.addEventListener('click',function(){
  var t=document.getElementById('src-type').value;
  var v=document.getElementById('src-value').value.trim();
  var n=document.getElementById('src-note').value.trim();
  if(!v){toast('请输入内容','err');return;}
  busy(sa,true,'解析中…');
  api('/api/source',{op:'add',type:t,value:v,note:n}).then(function(r){
   busy(sa,false,'+ 添加');toast(r.msg||'',r.ok?'ok':'err');
   if(r.ok){document.getElementById('src-value').value='';document.getElementById('src-note').value='';apply(r.state);}});});

 var os=document.getElementById('own-save');
 if(os)os.addEventListener('click',function(){ownSubmit(os);});
 var oc=document.getElementById('own-cancel');
 if(oc)oc.addEventListener('click',function(){EDITING=null;ownForm({people_linked:true});});

 var ca=document.getElementById('cat-add');
 if(ca)ca.addEventListener('click',function(){
  var c=document.getElementById('cat-value').value.trim();
  var nm=document.getElementById('cat-name').value.trim();
  if(!c){toast('请输入分类，如 cs.LG','err');return;}
  busy(ca,true,'添加中…');
  api('/api/category',{op:'add',cat:c,name:nm}).then(function(r){
   busy(ca,false,'+ 添加类别');toast(r.msg||'',r.ok?'ok':'err');
   if(r.ok){document.getElementById('cat-value').value='';document.getElementById('cat-name').value='';apply(r.state);}});});

 var ds=document.getElementById('dldir-save');
 if(ds)ds.addEventListener('click',function(){
  var v=document.getElementById('dldir').value.trim();
  if(!v){toast('请输入目录','err');return;}
  busy(ds,true,'保存中…');
  api('/api/config',{download_dir:v}).then(function(r){
   busy(ds,false,'保存');toast(r.msg||'',r.ok?'ok':'err');if(r.ok)apply(r.state);});});

 var dob=document.getElementById('dldir-open');
 if(dob)dob.addEventListener('click',function(){
  api('/api/open_folder',{dir:document.getElementById('dldir').value.trim()});});

 var rb=document.getElementById('rebuild');
 if(rb)rb.addEventListener('click',function(){
  busy(rb,true,'重算中…');
  api('/api/rebuild',{}).then(function(r){
   busy(rb,false,'↻ 重算推荐');toast(r.msg||'',r.ok?'ok':'err');if(r.ok)apply(r.state);});});

 fetch(APIBASE+'/api/customize').then(function(r){return r.json();}).then(apply)
  .catch(function(){toast('本地服务未运行：无法读取画像与设置','err');});
});
document.addEventListener('click',function(ev){
 var eo=ev.target.closest('[data-edit-owner]');
 if(eo){startEditOwner(eo.dataset.editOwner);return;}
 var dob=ev.target.closest('[data-del-owner]');
 if(dob){var nm=dob.dataset.delOwner;
  if(!window.confirm('删除画像主来源「'+nm+'」？该条目及其熟悉研究者加成会一并撤销。'))return;
  dob.disabled=true;
  api('/api/owner',{op:'remove',name:nm}).then(function(r){
   dob.disabled=false;toast(r.msg||'',r.ok?'ok':'err');
   if(r.ok){if(EDITING===nm){EDITING=null;ownForm({people_linked:true});}apply(r.state);}});return;}
 var k=ev.target.closest('.tp.kw');
 if(k){var kw=k.dataset.kw,off=!!BLOCKED[kw.toLowerCase()];
  api('/api/source',{op:off?'unblock':'block',kw:kw}).then(function(r){
   toast(r.msg||'',r.ok?'ok':'err');if(r.ok)apply(r.state);});return;}
 var d=ev.target.closest('[data-del-src]');
 if(d){var sid=d.dataset.delSrc;d.disabled=true;
  api('/api/source',{op:'remove',sid:sid}).then(function(r){
   d.disabled=false;toast(r.msg||'',r.ok?'ok':'err');if(r.ok)apply(r.state);});return;}
 var c=ev.target.closest('[data-del-cat]');
 if(c){var cat=c.dataset.delCat;
  if(!window.confirm('删除类别 '+cat+' ？（下一次抓取后生效）'))return;
  api('/api/category',{op:'remove',cat:cat}).then(function(r){
   toast(r.msg||'',r.ok?'ok':'err');if(r.ok)apply(r.state);});}
});
</script>
</body></html>
"""


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
    """兴趣画像 + 定制项（类别 / 下载目录 / 来源）独立页面。"""
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
        "css": CSS, "js": JS, "summary": summary,
        "owners": _owner_cards({"owners": p.get("owners") or []}),
        "customtopic": esc(_custom_topic_name()),
        "customw": _custom_topic_weight(),
    }


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

ARCHIVE_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>历史存档 · arXiv cs.* 日报</title>
<link rel="icon" href="data:,">
<style>%(css)s</style></head><body id="top">
<div class="wrap">
<header>
<h1>🗂 历史存档</h1>
<div class="sub">共 <b>%(n)d</b> 期 ｜ 已归档论文 <b>%(np)d</b> 条 ｜ 点日期即可查看当天那一版日报</div>
</header>

<div class="toolbar">
<a class="tb on" href="/">← 今日日报</a>
<a class="tb" href="/favorites">★ 收藏列表</a>
<a class="tb" href="/profile">⚙ 画像与设置</a>
<span class="grow"></span>
<span class="counter">归档库 <code>output/archive.db</code></span>
</div>

<p class="arc-hint">每期日报只呈现<b>当天新出现</b>的论文，往期不再重复出现；下面按日期（新→旧）列出全部存档。
点进去看到的是当时那一版的完整页面，Abstract 展开 / 收藏 / 下载 / Downvote 等按钮同样可用。</p>

<div class="arc-list">%(items)s</div>

<footer>
存档快照保存在 <code>output/archive/&lt;日期&gt;.html</code>，索引与统计保存在 <code>output/archive.db</code>（SQLite）。<br>
快照只增不改，是「当时那一版」的真实留痕。
</footer>
</div>
<button id="totop" type="button" aria-label="回到顶部" title="回到顶部">↑</button>
<div id="toast"></div>
<script>%(js)s</script>
</body></html>
"""


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
        return ARCHIVE_PAGE % {"css": CSS, "js": JS, "n": 0, "np": 0,
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
    return ARCHIVE_PAGE % {"css": CSS, "js": JS, "n": len(dates), "np": st.get("papers", 0),
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
