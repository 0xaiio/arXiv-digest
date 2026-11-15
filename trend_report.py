#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arXiv cs.* 周度趋势报告：抓全量 → TF-IDF 聚类 → 趋势页 → 归档。

和日报的分工
------------
日报回答「今天哪几篇值得我看」，靠的是**个人画像**排序；
周报回答「这一周整个 cs 在往哪走」，靠的是**全量语料**的分布与变化。
所以周报故意不用画像、不挑十篇、不逐篇翻译 —— 那是日报的活。

产物（与日报的命名/归档规范一致）
--------------------------------
    output/arxiv_trend_<YYYYMMDD>.html / .md     当期主入口
    output/trend_archive/<YYYYMMDD>.html / .md    只增不改的快照
    output/trend_archive/<YYYYMMDD>.json          报告数据（便于二次分析）
    output/trend_history.json                     跨周累积的基线（cats / terms）
    output/trend_raw_<YYYYMMDD>.json              抓取缓存（--skip-fetch 复用）

用法::

    python trend_report.py                     # 本周（周日跑）= 最近 7 天
    python trend_report.py --date 20261115     # 指定期号（周日日期）
    python trend_report.py --skip-fetch        # 复用缓存，只重算与重渲染
    python trend_report.py --no-bootstrap      # 首跑时不补抓上一周做基线
    python trend_report.py --json              # 机器可读摘要

数据窗口与基线
--------------
窗口 = 期号当天的前 7 天（含当天），按 arXiv 的 `submittedDate` 过滤 `cat:cs.*`。
基线 = `trend_history.json` 里更早的周（最多 8 周）的 `cats` / `terms` 计数。
第一次运行没有历史时，会自动补抓上一周写入历史，这样首期就能给出「周环比」，
而不是等下周才有对比。
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

import trend_analysis as TA

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
ARCHIVE_DIR = os.path.join(OUT, "trend_archive")
HISTORY_PATH = os.path.join(OUT, "trend_history.json")
TEMPLATE_DIR = os.path.join(HERE, "templates")

API = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
OS = "{http://a9.com/-/spec/opensearch/1.1/}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

PAGE = 500          # 单次请求条数（实测 500 条 ≈ 1.2 MB，1.8s）
PAUSE = 3.0         # arXiv 官方建议的请求间隔
WINDOW_DAYS = 7
# 公告延迟：arXiv 的 API 只索引**已公告**的论文。周日上午跑时，最近一次公告是
# 周五 09:00（周四批次），周五至周日的投稿要等到下周一才出现。若直接用 [D-6, D]，
# 窗口只有 4 天是完整的，与"上一周 7 天"对比会得出"全领域萎缩"的假信号
# （2026-11-15 实测：2371 vs 4652，差的那一半全是尚未公告的论文）。
# 所以窗口整体回退 LAG_DAYS 天，保证两端都是完整周。
LAG_DAYS = 3
MAX_BASELINE_WEEKS = 8

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


# ---------------------------------------------------------------- 抓取
def _get(url: str, timeout: int = 90, retries: int = 3) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) arxiv-digest/2.0"})
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as exc:  # 网络抖动重试；三次都失败才算真失败
            last = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("请求失败：%s" % last)


def parse_feed(xml_text: str) -> tuple[list[dict], int]:
    """解析 Atom：只保留 id / title / abstract / categories / published。

    周报要的就这几样 —— 作者、单位、PDF 链接一律不取，一是用不上，二是能把
    每次抓取的体积压到最小（全量 3200 篇 ≈ 4 MB）。
    """
    root = ET.fromstring(xml_text)
    total_text = root.findtext(OS + "totalResults") or "0"
    total = int(total_text or 0)
    papers = []
    for entry in root.findall(ATOM + "entry"):
        raw_id = (entry.findtext(ATOM + "id") or "").strip()
        sid = re.sub(r"v\d+$", "", raw_id.rstrip("/").split("/")[-1])
        title = " ".join((entry.findtext(ATOM + "title") or "").split())
        abstract = " ".join((entry.findtext(ATOM + "summary") or "").split())
        cats = [c.get("term") for c in entry.findall(ATOM + "category") if c.get("term")]
        prim = entry.find(ARXIV_NS + "primary_category")
        primary = prim.get("term") if prim is not None else (cats[0] if cats else "")
        if not sid:
            continue
        papers.append({
            "sid": sid,
            "title": title,
            "abstract": abstract,
            "cats": cats,
            "primary": primary,
            "published": entry.findtext(ATOM + "published") or "",
        })
    return papers, total


def fetch_range(start: datetime, end: datetime, page: int = PAGE,
                pause: float = PAUSE, progress=None) -> tuple[list[dict], int]:
    """按 submittedDate 区间分页拉取 `cat:cs.*` 全量，按 sid 去重。"""
    query = "cat:cs.* AND submittedDate:[%s TO %s]" % (
        start.strftime("%Y%m%d%H%M"), end.strftime("%Y%m%d%H%M"))
    seen, papers, total, offset = set(), [], None, 0
    while True:
        params = {
            "search_query": query,
            "start": offset,
            "max_results": page,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        xml_text = _get(API + "?" + urllib.parse.urlencode(params))
        batch, total = parse_feed(xml_text)
        fresh = [p for p in batch if p["sid"] not in seen]
        for p in fresh:
            seen.add(p["sid"])
        papers.extend(fresh)
        offset += page
        if progress:
            progress(offset, total)
        if not batch or offset >= (total or 0):
            break
        time.sleep(pause)
    papers.sort(key=lambda p: p["sid"])
    return papers, int(total or len(papers))


def week_window(day: date, lag: int = LAG_DAYS) -> tuple[date, date]:
    """期号对应的 7 天窗口：**再回退 `lag` 天**，只取已公告的部分。

    见 LAG_DAYS 的注释：不回退就会把「还没公告」误读成「这一周没人投稿」。
    """
    end = day - timedelta(days=lag)
    return end - timedelta(days=WINDOW_DAYS - 1), end


# ---------------------------------------------------------------- 持久化
def jload(path: str, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def jdump(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def load_history() -> dict:
    hist = jload(HISTORY_PATH, {"weeks": []})
    if not isinstance(hist, dict):
        hist = {"weeks": []}
    hist["weeks"] = [w for w in hist.get("weeks", []) if isinstance(w, dict) and w.get("date")]
    return hist


def upsert_week(hist: dict, issue: str, papers: list[dict]) -> dict:
    """把一期写进历史（按日期 upsert），返回这一期的基线条目。"""
    entry = {
        "date": issue,
        "total": len(papers),
        "cats": TA.category_counts(papers),
        "terms": TA.term_doc_counts(papers),
    }
    weeks = [w for w in hist.get("weeks", []) if w.get("date") != issue]
    weeks.append(entry)
    weeks.sort(key=lambda w: w["date"])
    hist["weeks"] = weeks[-MAX_BASELINE_WEEKS:]
    return entry


def baseline_for(hist: dict, issue: str) -> list[dict]:
    """取比本期更早的周做基线（最多 8 周），当前期本身不进基线。"""
    weeks = [w for w in hist.get("weeks", []) if w.get("date", "") < issue]
    return weeks[-MAX_BASELINE_WEEKS:]


def raw_cache_path(issue: str) -> str:
    return os.path.join(OUT, "trend_raw_%s.json" % issue)


# ---------------------------------------------------------------- 渲染
TREND_CSS = """
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:0 0 16px}
.kpi{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px 18px}
.kpi .n{font-size:26px;font-weight:600;color:var(--tx);letter-spacing:.5px}
.kpi .k{font-size:12.5px;color:var(--tx3);margin-top:4px}
section.blk{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:20px 24px;margin:0 0 16px}
section.blk h2{margin:0 0 12px;font-size:17px}
section.blk h2 .hint{font-size:12.5px;color:var(--tx3);font-weight:400;margin-left:8px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--bd);vertical-align:top}
th{color:var(--tx3);font-weight:500;font-size:12.5px}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.up{color:var(--warn)}
.down{color:var(--exp)}
.tag{display:inline-block;background:var(--acbg);color:var(--ac);border-radius:6px;
 padding:1px 7px;font-size:12px;margin-right:4px}
.sample{color:var(--tx2);font-size:12.5px;line-height:1.55}
.muted{color:var(--tx3);font-size:13px}
.note{background:var(--acbg);border-left:3px solid var(--ac);padding:10px 14px;border-radius:6px;
 color:var(--tx2);font-size:13px;margin:12px 0 0}
footer{color:var(--tx3);font-size:12.5px;line-height:1.8;margin:8px 0 40px}
"""


def _css() -> str:
    try:
        with open(os.path.join(TEMPLATE_DIR, "style.css"), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


def _pct(x: float) -> str:
    return "%.1f%%" % (x * 100)


def _num(n) -> str:
    return "{:,}".format(int(n))


def _ratio_cell(row: dict) -> str:
    ratio = row.get("ratio") or 0
    cls = "up" if ratio >= 1 else "down"
    return '<span class="%s">×%.2f</span>' % (cls, ratio)


def build_html(issue: str, win: tuple[date, date], data: dict,
               baseline_weeks: int) -> str:
    total = data["total"]
    cats = data["categories"]
    clusters = data["clusters"]
    up = data["growth_up"]
    down = data["growth_down"]
    cat_growth = data["cat_growth"]
    strongest = up[0]["key"] if up else "—"
    strongest_zh = TA.TERM_ZH.get(strongest, strongest)

    parts = [
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<title>arXiv cs.* 周度趋势 %s</title>" % issue,
        "<style>%s\n%s</style></head><body><div class=\"wrap\">" % (_css(), TREND_CSS),
        "<header><h1>arXiv cs.* 本周趋势</h1>",
        '<div class="sub">第 <b>%s</b> 期 · 窗口 <b>%s → %s</b> · 全量 <b>%s</b> 篇 · '
        "基线 <b>%s</b> 周</div>"
        % (issue, win[0].isoformat(), win[1].isoformat(), _num(total), baseline_weeks),
        '<div class="sub" style="margin-top:6px">窗口已回退 %d 天：arXiv 只索引已公告论文，'
        "周日运行时最近两三天尚未公告，直接对比会得出「全面萎缩」的假信号。</div>"
        % LAG_DAYS,
        "</header>",
        '<section class="kpis">',
        '<div class="kpi"><div class="n">%s</div><div class="k">本周论文（cs.* 全量）</div></div>' % _num(total),
        '<div class="kpi"><div class="n">%d</div><div class="k">覆盖分类</div></div>' % len(cats),
        '<div class="kpi"><div class="n">%d</div><div class="k">主题簇</div></div>' % len(clusters),
        '<div class="kpi"><div class="n">%s</div><div class="k">增长最快方向</div></div>' % _esc(strongest_zh),
        "</section>",
    ]

    # 一、主题分布
    parts.append('<section class="blk"><h2>一、本周主题分布'
                 '<span class="hint">TF-IDF + 球形 k-means，占比按论文数</span></h2>')
    if clusters:
        parts.append('<table><thead><tr><th>主题</th><th class="num">篇数</th>'
                     '<th class="num">占比</th><th>代表词</th><th>代表论文</th></tr></thead><tbody>')
        for c in clusters:
            tags = "".join('<span class="tag">%s</span>' % _esc(t) for t in c["terms"][:5])
            sample = c["samples"][0] if c["samples"] else None
            sample_html = ('<div class="sample">%s<br><span class="muted">%s</span></div>'
                           % (_esc(sample["title"]), _esc(sample["sid"]))) if sample else ""
            parts.append('<tr><td><b>%s</b></td><td class="num">%s</td><td class="num">%s</td>'
                         "<td>%s</td><td>%s</td></tr>"
                         % (_esc(c["label"]), _num(c["size"]), _pct(c["share"]), tags, sample_html))
        parts.append("</tbody></table>")
    else:
        parts.append('<p class="muted">本周没有足够语料做聚类。</p>')
    parts.append("</section>")

    # 二、异常增长
    parts.append('<section class="blk"><h2>二、异常增长方向'
                 '<span class="hint">本周文档频率 vs 历史周均值</span></h2>')
    if up:
        parts.append('<table><thead><tr><th>方向</th><th class="num">本周</th>'
                     '<th class="num">历史均值</th><th class="num">倍数</th>'
                     '<th class="num">z</th></tr></thead><tbody>')
        for r in up:
            parts.append("<tr><td><b>%s</b></td><td class=\"num\">%s</td><td class=\"num\">%.1f</td>"
                         "<td class=\"num\">%s</td><td class=\"num\">%+.2f</td></tr>"
                         % (_esc(TA.TERM_ZH.get(r["key"], r["key"])), _num(r["cur"]),
                            r["base"], _ratio_cell(r), r["z"]))
        parts.append("</tbody></table>")
    else:
        if baseline_weeks == 0:
            parts.append('<div class="note">基线不足：本期是第一次记录该窗口，'
                         "已把本周写入 <code>trend_history.json</code> 作为后续对比基准。"
                         "下一期起这里会出现周环比与 z 值。</div>")
        else:
            parts.append('<div class="note">本周没有达到门槛的增长方向'
                         "（要求 z ≥ 1.5、倍数 ≥ 1.2、本周 ≥ 12 篇）。"
                         "这不等于「没变化」，而是「没有异常」——分布可在上一节对照。</div>")
    if down:
        parts.append('<p class="muted" style="margin-top:12px">明显收缩：' +
                     "、".join("%s（×%.2f）" % (_esc(TA.TERM_ZH.get(r["key"], r["key"])), r["ratio"])
                               for r in down) + "</p>")
    parts.append("</section>")

    # 三、分类分布
    parts.append('<section class="blk"><h2>三、分类分布<span class="hint">按 primary 分类</span></h2>')
    base_map = {r["key"]: r for r in cat_growth}
    parts.append('<table><thead><tr><th>分类</th><th class="num">本周</th>'
                 '<th class="num">占比</th><th class="num">周变化</th></tr></thead><tbody>')
    for row in cats[:15]:
        g = base_map.get(row["cat"])
        change = ('<span class="%s">×%.2f</span>' % ("up" if g["ratio"] >= 1 else "down", g["ratio"])
                  if g else '<span class="muted">—</span>')
        parts.append('<tr><td><code>%s</code></td><td class="num">%s</td>'
                     '<td class="num">%s</td><td class="num">%s</td></tr>'
                     % (_esc(row["cat"]), _num(row["count"]), _pct(row["share"]), change))
    parts.append("</tbody></table></section>")

    method = data["method"]
    parts.append("<footer>")
    parts.append("方法：%s；%s；词表 %s 个词。<br>" % (_esc(method["vectorizer"]),
                                                      _esc(method["cluster"]),
                                                      _num(method["vocab"])))
    parts.append("增长判据：%s；只报「绝对量够大且偏离够远」的方向，不做语义推断。<br>"
                 % _esc(method["growth"]))
    parts.append("数据来源：arXiv API <code>cat:cs.*</code>，按 submittedDate 过滤；"
                 "只取 title / abstract / categories。<br>")
    parts.append("局限：聚类是无监督结果，主题名由代表词映射，不代表作者自述的分类；"
                 "分类计数按 primary 计，跨类论文只算一次。<br>")
    parts.append("生成时间：%s</footer></div></body></html>"
                 % datetime.now().strftime("%Y-%m-%d %H:%M"))
    return "".join(parts)


def build_md(issue: str, win: tuple[date, date], data: dict, baseline_weeks: int) -> str:
    lines = [
        "# arXiv cs.* 本周趋势 · %s" % issue,
        "",
        "窗口 %s → %s ｜ 全量 %s 篇 ｜ 基线 %s 周"
        % (win[0].isoformat(), win[1].isoformat(), _num(data["total"]), baseline_weeks),
        "",
        "## 一、本周主题分布",
        "",
    ]
    if data["clusters"]:
        lines += ["| 主题 | 篇数 | 占比 | 代表词 |", "| --- | ---: | ---: | --- |"]
        for c in data["clusters"]:
            lines.append("| %s | %d | %s | %s |"
                         % (c["label"], c["size"], _pct(c["share"]), "、".join(c["terms"][:4])))
    else:
        lines.append("（本周没有足够语料做聚类）")
    lines += ["", "## 二、异常增长方向", ""]
    if data["growth_up"]:
        lines += ["| 方向 | 本周 | 历史均值 | 倍数 | z |", "| --- | ---: | ---: | ---: | ---: |"]
        for r in data["growth_up"]:
            lines.append("| %s | %d | %.1f | ×%.2f | %+.2f |"
                         % (TA.TERM_ZH.get(r["key"], r["key"]), r["cur"], r["base"],
                            r["ratio"], r["z"]))
    else:
        lines.append("基线不足：本期为首次记录，已写入 `trend_history.json`，下一期起给出周环比。")
    if data["growth_down"]:
        lines += ["", "明显收缩：" + "、".join(
            "%s（×%.2f）" % (TA.TERM_ZH.get(r["key"], r["key"]), r["ratio"])
            for r in data["growth_down"])]
    lines += ["", "## 三、分类分布", "", "| 分类 | 本周 | 占比 |", "| --- | ---: | ---: |"]
    for row in data["categories"][:15]:
        lines.append("| `%s` | %d | %s |" % (row["cat"], row["count"], _pct(row["share"])))
    lines += ["", "---", "",
              "方法：%s；%s；词表 %d。" % (data["method"]["vectorizer"],
                                          data["method"]["cluster"], data["method"]["vocab"]),
              "",
              "数据来源：arXiv API `cat:cs.*`，按 submittedDate 过滤，只取 title / abstract / categories。",
              "",
              "生成时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- 归档
def archive(issue: str, html_path: str, md_path: str, data: dict) -> tuple[str, str, str]:
    """当期主文件另存一份到 trend_archive/（只增不改），并把报告数据落盘。"""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    h = os.path.join(ARCHIVE_DIR, "%s.html" % issue)
    m = os.path.join(ARCHIVE_DIR, "%s.md" % issue)
    j = os.path.join(ARCHIVE_DIR, "%s.json" % issue)
    for src, dst in ((html_path, h), (md_path, m)):
        with open(src, "rb") as fh:
            payload = fh.read()
        with open(dst, "wb") as fh:
            fh.write(payload)
    jdump(j, data)
    return h, m, j


# ---------------------------------------------------------------- 主流程
def run(issue: str, skip_fetch: bool = False, bootstrap: bool = True,
        json_out: bool = False) -> int:
    day = datetime.strptime(issue, "%Y%m%d").date()
    start, end = week_window(day)
    cache = raw_cache_path(issue)

    if skip_fetch:
        cached = jload(cache, None)
        if not cached:
            sys.stderr.write("没有缓存 %s，去掉 --skip-fetch 先抓一次\n" % os.path.basename(cache))
            return 2
        papers = cached.get("papers") or []
        sys.stderr.write("[cache] 复用 %s（%d 篇）\n" % (os.path.basename(cache), len(papers)))
    else:
        t0 = time.time()
        sys.stderr.write("[fetch] cs.* %s → %s\n" % (start.isoformat(), end.isoformat()))
        papers, total = fetch_range(datetime.combine(start, datetime.min.time()),
                                    datetime.combine(end, datetime.max.time()),
                                    progress=lambda n, t: sys.stderr.write(
                                        "        %d/%s\r" % (n, t or "?")))
        sys.stderr.write("\n[fetch] %d 篇，用时 %.1fs\n" % (len(papers), time.time() - t0))
        jdump(cache, {"issue": issue, "window": [start.isoformat(), end.isoformat()],
                      "fetched_at": datetime.now().isoformat(timespec="seconds"),
                      "papers": papers})

    if not papers:
        sys.stderr.write("[FAIL] 窗口内没有抓到任何论文\n")
        return 2

    hist = load_history()
    baseline = baseline_for(hist, issue)
    if not baseline and bootstrap:
        # 首跑：补抓上一周做基线，否则第一期只能报"基线不足"，没有对比价值。
        # 这一步是**尽力而为**：arXiv 偶发慢响应时不能把整期报告拖死——没有基线
        # 顶多少一张增长表，报告本身仍然成立。
        # 基线窗口就是紧邻当前窗口的前 7 天：**不能再过一遍 week_window**，
        # 否则会把 LAG_DAYS 叠加两次，基线窗口与当前窗口之间空出 3 天来。
        b_end = start - timedelta(days=1)
        b_start = b_end - timedelta(days=WINDOW_DAYS - 1)
        b_issue = b_end.strftime("%Y%m%d")
        sys.stderr.write("[bootstrap] 补抓上一周 %s → %s 作为基线\n"
                         % (b_start.isoformat(), b_end.isoformat()))
        try:
            b_papers, _ = fetch_range(datetime.combine(b_start, datetime.min.time()),
                                      datetime.combine(b_end, datetime.max.time()))
        except Exception as exc:
            b_papers = []
            sys.stderr.write("[warn] 基线补抓失败（%s），本期先不报增长\n" % exc)
        if b_papers:
            upsert_week(hist, b_issue, b_papers)
            baseline = baseline_for(hist, issue)
            sys.stderr.write("[bootstrap] 基线周 %s：%d 篇\n" % (b_issue, len(b_papers)))

    data = TA.analyze(papers, baseline=baseline)
    data["issue"] = issue
    data["window"] = {"start": start.isoformat(), "end": end.isoformat()}
    data["baseline_weeks"] = len(baseline)
    data["generated_at"] = datetime.now().isoformat(timespec="seconds")
    data["source"] = "arXiv API cat:cs.* (submittedDate)"

    page = build_html(issue, (start, end), data, len(baseline))
    md = build_md(issue, (start, end), data, len(baseline))
    os.makedirs(OUT, exist_ok=True)
    hp = os.path.join(OUT, "arxiv_trend_%s.html" % issue)
    mp = os.path.join(OUT, "arxiv_trend_%s.md" % issue)
    with open(hp, "w", encoding="utf-8") as fh:
        fh.write(page)
    with open(mp, "w", encoding="utf-8") as fh:
        fh.write(md)

    # 历史只在本期确实抓到数据时更新，避免半截运行污染基线。
    upsert_week(hist, issue, papers)
    jdump(HISTORY_PATH, hist)
    h, m, j = archive(issue, hp, mp, data)

    summary = {
        "issue": issue,
        "window": data["window"],
        "total": data["total"],
        "categories": len(data["categories"]),
        "clusters": len(data["clusters"]),
        "baseline_weeks": len(baseline),
        "growth_up": [r["key"] for r in data["growth_up"][:5]],
        "files": {"html": str(hp), "md": str(mp), "archive": [str(h), str(m), str(j)],
                  "history": str(HISTORY_PATH)},
    }
    if json_out:
        print(json.dumps(summary, ensure_ascii=False, indent=1))
    else:
        print("== arXiv cs.* 周度趋势 %s ==" % issue)
        print("   窗口 %s → %s ｜ %d 篇 ｜ 分类 %d ｜ 主题簇 %d ｜ 基线 %d 周"
              % (start.isoformat(), end.isoformat(), data["total"],
                 len(data["categories"]), len(data["clusters"]), len(baseline)))
        for c in data["clusters"][:5]:
            print("   · %-18s %4d 篇  %5.1f%%  %s"
                  % (c["label"], c["size"], c["share"] * 100, "、".join(c["terms"][:4])))
        if data["growth_up"]:
            print("   增长最快：" + "、".join("%s(×%.2f)" % (TA.TERM_ZH.get(r["key"], r["key"]),
                                                            r["ratio"])
                                             for r in data["growth_up"][:5]))
        elif not baseline:
            print("   增长：基线不足，已建立首期记录")
        else:
            print("   增长：没有达到门槛的方向（z≥1.5、倍数≥1.2、本周≥12 篇）")
        print("   产物：%s" % hp)
        print("         %s" % mp)
        print("         归档 %s" % os.path.dirname(h))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="arXiv cs.* 周度趋势报告")
    ap.add_argument("-d", "--date", help="期号 YYYYMMDD（周日）；默认本周日")
    ap.add_argument("--skip-fetch", action="store_true", help="复用 trend_raw_<期号>.json")
    ap.add_argument("--no-bootstrap", action="store_true", help="首跑时不补抓上一周做基线")
    ap.add_argument("--json", action="store_true", help="输出机器可读摘要")
    args = ap.parse_args(argv)

    issue = (args.date or "").strip()
    if issue:
        if not re.fullmatch(r"\d{8}", issue):
            print("[FAIL] 期号必须是 8 位数字：%s" % issue, file=sys.stderr)
            return 2
    else:
        today = date.today()
        # 默认取「最近的周日」：周日跑就是当天，其他日子取上一个周日。
        issue = (today - timedelta(days=(today.weekday() + 1) % 7)).strftime("%Y%m%d")
    return run(issue, skip_fetch=args.skip_fetch,
               bootstrap=not args.no_bootstrap, json_out=args.json)


if __name__ == "__main__":
    sys.exit(main())
