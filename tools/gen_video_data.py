# -*- coding: utf-8 -*-
"""
为 arXiv Weekly 视频生成数据文件 reel/src/papers.json。

设计原则：
- 一切文案来自真实产物：recommend.json（按分数排好的本期推荐）、issue_core.json /
  issue_expand.json（统计）、affiliations.json（作者单位）、summaries.json（中文摘要）。
- 若 output/video_notes.json 提供了人工撰写的解读（必需能追溯到摘要），优先采用；
  否则从中文摘要自动切分要点（中性编号标签，不做「方法 / 结论」之类的语义归属断言）。
- 英文原题原样呈现（真实可核实），不做机器翻译。

用法：
  python tools/gen_video_data.py [--top 8] [--expand 2] [--out reel/src/papers.json]

``--top`` 取本期「🎯 为你推荐」前列（核心六分类 feed），``--expand`` 取「🌱 兴趣扩展」
前列（其他 cs.xx / math.LO）；两者在 recommend.py 阶段已按短号排除重叠，拼接后即为成片顺序。
"""
import argparse
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")


def load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:  # 坏文件不应中断流水线
        print("[warn] 无法解析 %s: %s" % (path, exc))
        return default


def clip(text, n, tail="…"):
    """按长度截断，但尽量落在词/句边界上，避免出现 'Multi-Pa…' 这类半词。"""
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    head = text[: n - 1]
    for sep in (" ", "，", "、", "/", "：", ",", ":", "(", "（"):
        cut = head.rfind(sep)
        if cut >= int(n * 0.6):
            head = head[:cut]
            break
    return head.rstrip(" ,;:，；：、/(") + tail


def sid_of(pid):
    """http://arxiv.org/abs/2609.30163v1 -> 2609.30163"""
    s = str(pid or "").rstrip("/").split("/")[-1]
    return re.sub(r"v\d+$", "", s)


def split_points(zh, limit=3):
    """把一句中文摘要切成 <=limit 条要点（按 ；。！? 与逗号兜底）。"""
    zh = " ".join((zh or "").split())
    if not zh:
        return []
    parts = [p.strip() for p in re.split(r"[；。;]", zh) if p.strip()]
    if len(parts) < 2:
        parts = [p.strip() for p in re.split(r"[，,]", zh) if p.strip()]
    if not parts:
        return [{"tag": "要点", "text": clip(zh, 58)}]
    if len(parts) > limit:
        head = parts[: limit - 1]
        head.append("；".join(parts[limit - 1 :]))
        parts = head
    return [{"tag": "要点 %d" % (i + 1), "text": clip(p, 80)} for i, p in enumerate(parts)]


def pick_keywords(title_en, zh_text, extra=None, limit=4):
    """
    挑出「同时出现在英文题名与中文文案里」的技术词，用于强调色高亮。
    只看真实出现过的词，避免凭空标注。
    """
    blob = (" " + (zh_text or "") + " ").lower()
    cands = []

    # 缩写 / 首字母词：BFT、CRDT、TLA+ 之类，中文摘要里常原样保留
    for tok in re.findall(r"\b[A-Z][A-Za-z0-9+*-]{1,}(?:-[A-Z][A-Za-z0-9+*]*)?\b", title_en or ""):
        cands.append(tok)
    # 较长的英文实词
    for tok in re.findall(r"\b[A-Za-z][A-Za-z-]{5,}\b", title_en or ""):
        cands.append(tok)
    for tok in extra or []:
        if isinstance(tok, str):
            cands.append(tok)

    stop = {
        "the", "and", "for", "with", "from", "that", "this", "using", "towards",
        "toward", "via", "based", "systems", "paper", "papers", "learning",
        "efficient", "scalable", "distributed", "concurrency", "verification",
    }
    seen, hits = set(), []
    for tok in cands:
        key = tok.lower()
        if key in stop or len(tok) < 2 or key in seen:
            continue
        seen.add(key)
        if tok.lower() in blob:
            hits.append(tok)
        if len(hits) >= limit:
            break
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=8, help="取「为你推荐」榜前 N 篇")
    ap.add_argument(
        "--expand", type=int, default=2,
        help="追加「兴趣扩展」榜前 M 篇（排在推荐之后，短号去重）",
    )
    ap.add_argument("--out", default=os.path.join(ROOT, "reel", "src", "papers.json"))
    args = ap.parse_args(argv)

    reco = load(os.path.join(OUT, "recommend.json"), [])
    core = load(os.path.join(OUT, "issue_core.json"), {})
    expand_files = [
        load(os.path.join(OUT, "issue_expand.json"), {}),
        load(os.path.join(OUT, "expand.json"), []),
    ]
    affil = load(os.path.join(OUT, "affiliations.json"), {})
    summaries = load(os.path.join(OUT, "summaries.json"), {})
    notes = load(os.path.join(OUT, "video_notes.json"), {})

    papers_core = core.get("papers", []) if isinstance(core, dict) else []
    n_expand = 0
    for item in expand_files:
        if isinstance(item, dict):
            n_expand = max(n_expand, len(item.get("papers", [])))
        elif isinstance(item, list):
            n_expand = max(n_expand, len(item))
    n_exp_rec = len(expand_files[1]) if isinstance(expand_files[1], list) else 0

    reco_sorted = sorted(reco, key=lambda p: float(p.get("score") or 0), reverse=True)
    picked: list[tuple[dict, str]] = [(p, "推荐") for p in reco_sorted[: args.top]]

    # 兴趣扩展：expand.json 是 recommend.py 输出的本期扩展推荐（已按分数排好、与核心零重叠）
    if args.expand > 0:
        exp_sorted = sorted(
            (p for p in expand_files[1] if isinstance(p, dict)),
            key=lambda p: float(p.get("score") or 0),
            reverse=True,
        )
        taken = {sid_of(p.get("id")) for p, _ in picked}
        for p in exp_sorted:
            sid = sid_of(p.get("id"))
            if sid in taken:
                continue
            taken.add(sid)
            picked.append((p, "兴趣扩展"))
            if len([1 for _, lane in picked if lane == "兴趣扩展"]) >= args.expand:
                break

    if not picked:
        print("[err] recommend.json 为空，先跑流水线")
        return 2

    dates = sorted(
        {str(p.get("published", ""))[:10] for p, _ in picked if p.get("published")}
    )
    newest = dates[-1] if dates else ""
    window = core.get("window_days") if isinstance(core, dict) else None
    issue_date = core.get("issue_date") if isinstance(core, dict) else None
    issue = issue_date or (core.get("generated_at", "")[:10] if isinstance(core, dict) else "") or newest
    rng = newest + ((" · 回溯 %s 天公告批次" % window) if window else " 批次")

    items = []
    for idx, (p, lane) in enumerate(picked, start=1):
        sid = sid_of(p.get("id"))
        note = notes.get(sid) or notes.get(str(p.get("id"))) or {}
        # summaries.json 自 2026-10-22 起 value 为 {"en","zh"}；兼容旧的单语字符串。
        raw = p.get("summary") or summaries.get(sid) or ""
        if isinstance(raw, dict):
            raw = raw.get("zh") or raw.get("en") or ""
        zh = raw

        bullets = note.get("bullets") or []
        if not bullets:
            bullets = split_points(zh)
        if not bullets:
            bullets = [{"tag": "要点", "text": clip(p.get("abstract", ""), 60)}]
        bullets = [
            {"tag": b.get("tag", "要点"), "text": clip(b.get("text", ""), 80)}
            for b in bullets[:3]
        ]

        authors = [a for a in (p.get("authors") or []) if a]
        who = ", ".join(authors[:3])
        if len(authors) > 3:
            who += " 等 %d 人" % len(authors)

        units = list((affil.get(sid) or {}).get("units") or [])
        if len(units) > 2:
            units = units[:2] + ["等 %d 家单位" % len(units)]

        kw = note.get("kw") or pick_keywords(
            p.get("title", ""), " ".join([b["text"] for b in bullets] + [zh]),
            extra=(note.get("kw_extra") or []),
        )

        items.append(
            {
                "rank": idx,
                "lane": lane,
                "sid": sid,
                "cat": p.get("primary") or (p.get("cats") or [""])[0],
                "score": round(float(p.get("score") or 0), 1),
                "title_en": clip(p.get("title", ""), 140),
                "kw": kw,
                "authors": who,
                "units": [clip(u, 58) for u in units],
                "bullets": bullets,
                "link": "arxiv.org/abs/" + sid,
            }
        )

    data = {
        "issue": issue,
        "range": rng,
        "generated": core.get("generated_at", "") if isinstance(core, dict) else "",
        "stats": {
            "core": len(papers_core),
            "expand": n_expand,
            "rec": len(reco),
            "exp": n_exp_rec,
        },
        "papers": items,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with io.open(args.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)

    print("[ok] %s" % args.out)
    print("     期号 %s  区间 %s  统计 %s" % (issue, rng, data["stats"]))
    for it in items:
        print(
            "     #%d %-12s %-7s %-6s %5.1f  %s"
            % (it["rank"], it["sid"], it["cat"], it["lane"], it["score"],
               clip(it["title_en"], 52))
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
