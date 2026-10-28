#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3 推荐引擎：核心推荐 + 兴趣扩展 + 行为驱动的动态权重。

输入: output/raw.json         核心六分类（fetch_arxiv.py）
      output/raw_expand.json  相邻分类候选（fetch_expand.py）
      interests.json          兴趣种子画像
      output/profile_state.json 行为学习到的动态权重（profile.py）
输出: output/scores.json       核心论文全量打分（调试用）
      output/recommend.json   核心推荐（供报告与 MD）
      output/expand.json      兴趣扩展推荐（供报告与 MD）
      output/recommend_candidates.json  供 LLM 撰写推荐理由的精简候选
      output/papers_index.json 前端实时重排用的特征索引
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import archive as AR  # noqa: E402
import paperutil as pu  # noqa: E402
import profile as PF  # noqa: E402
# 打分是纯函数，单独一层（见 scoring.py 顶部说明）。这里 re-export，
# 保证既有调用方（server / tools / tests）继续用 recommend.features 等名字。
from scoring import (  # noqa: E402,F401
    ABS_HIT_CAP, ABS_HIT_W, FAMILIAR_W, NEG_CAP, NEG_SCALE, SYSTEM_W,
    TITLE_HIT_CAP, TITLE_HIT_W, _norm, _rx, base_score, features, score,
    topic_hits,
)

OUT = pu.OUT


def short_id(p):
    s = p if isinstance(p, str) else (p.get("id") or "")
    s = s.rsplit("/", 1)[-1]
    return re.sub(r"v\d+$", "", s)


def load_profile():
    """返回 (prof, topics, neg_w, neg_rx)；topics 已乘上学习到的倍率。

    topics 的组成与顺序由 customize.effective_topics() 决定
    （interests.json 原有主题 + 用户自定义主题），必须与 profile.seed_weights() 同序。
    """
    import customize as CZ  # noqa: E402
    # 用 customize.load_interests() 而不是直接 json.load：
    # 前者在文件缺失时会按 interests.example.json 初始化，并且对缺字段有兜底，
    # 新用户手写半份画像（比如只写 topics）也不会在这里 KeyError。
    prof = CZ.load_interests()
    st = PF.load()
    topics = []
    for t in CZ.effective_topics(prof):
        mult = float(st.get("topic_mult", {}).get(t["name"], 1.0))
        topics.append({
            "name": t["name"],
            "weight": float(t.get("weight", 1.0)) * mult,
            "seed": float(t.get("seed", t.get("weight", 1.0))),
            "custom": bool(t.get("custom")),
            "rx": [_rx(k) for k in t["keywords"]],
        })
    neg = prof.get("negative") or {}
    return (prof, topics, float(neg.get("weight", -1.0)),
            [_rx(k) for k in (neg.get("keywords") or [])])


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = pu.load_config()
    core_path = os.path.join(OUT, "raw.json")
    if not os.path.exists(core_path):
        raise SystemExit("missing %s -- run fetch_arxiv.py first" % core_path)
    core = json.load(open(core_path, encoding="utf-8"))
    exp_path = os.path.join(OUT, "raw_expand.json")
    exp = json.load(open(exp_path, encoding="utf-8")) if os.path.exists(exp_path) else {"papers": []}

    prof, topics, neg_w, neg_rx = load_profile()
    import customize as CZ  # noqa: E402
    people = CZ.effective_people(prof)
    systems = CZ.effective_systems(prof)
    st = PF.load()
    kwmap = st.get("kw", {})
    pens = st.get("paper_bonus", {})
    summaries = {}
    sp = os.path.join(OUT, "summaries.json")
    if os.path.exists(sp):
        try:
            summaries = json.load(open(sp, encoding="utf-8"))
        except Exception:
            summaries = {}
    notes = {}
    np_ = os.path.join(OUT, "rec_notes.json")
    if os.path.exists(np_):
        try:
            notes = json.load(open(np_, encoding="utf-8"))
        except Exception:
            notes = {}

    def pack(p, key_prefix=""):
        sid = short_id(p)
        f = features(p, topics, neg_w, neg_rx, people, systems, kwmap)
        s = score(f, topics, kwmap, pens.get(sid, 0.0))
        # 简介是双语的：en 走 `summary_en`，zh 走 `summary`（历史单语文件按
        # 是否含汉字自动归位，见 paperutil.split_bilingual）。
        summ_en, summ_zh = pu.split_bilingual(
            summaries.get(sid) or summaries.get("%s#%s" % (key_prefix, "")) or "")
        return {
            "id": sid,
            "title": p.get("title", ""),
            "authors": (p.get("authors") or [])[:6],
            "primary": p.get("primary") or p.get("queried_cat", ""),
            "cats": p.get("cats", []),
            "published": (p.get("published") or "")[:10],
            # 摘要保留全文：页面上的「Abstract (EN)」就是它，截到 1400 会在句子
            # 中途断开（看起来像残缺），中文译文也无从"对应完整摘要"。
            # arXiv 摘要普遍 1–2 KB，对 JSON 体积影响可忽略。
            "abstract": (p.get("abstract") or ""),
            "summary": summ_zh,
            "summary_en": summ_en,
            "score": round(s, 1),
            "topics": [d["topic"] for d in f["detail"][:4]],
            "topic_detail": f["detail"][:4],
            "familiar_authors": f["fam"],
            "systems": f["sys"],
            "tv": f["tv"],
            "base": f["base"],
            "toks": f["toks"],
            "pen": round(float(pens.get(sid, 0.0)), 2),
            "pdf": p.get("pdf") or ("https://arxiv.org/pdf/%s" % sid),
        }

    # 严格切分：凡是出现在六分类 feed（raw.json）里的论文，都不属于「兴趣扩展」
    core_ids = {short_id(p) for p in core["papers"]}
    extra = [p for p in exp.get("papers", []) if short_id(p) not in core_ids]

    # ---- 本期新增隔离（2026-09-14 新增）----
    # raw/raw_expand 是累积池（RSS 降级通道按短号增量合并），全池打分会让前几天的高分
    # 论文反复出现在每天的日报里。这里按 archive.db 的 seen 表切出「本期新增」，
    # 日报只渲染本期；历史内容留在 output/archive/ 快照与 archive.db 里按日期回看。
    issue_date = (core.get("generated_at") or "")[:10].replace("-", "") or time.strftime("%Y%m%d")
    bs = (core.get("newest_seen") or "")[:10]
    new_core, new_exp, mode = AR.filter_issues(core["papers"], exp.get("papers", []),
                                              issue_date, bs)
    new_core = new_core or []
    new_exp = new_exp or []
    new_core_ids = {short_id(p) for p in new_core}
    new_exp_ids = {short_id(p) for p in new_exp}
    pool_stats = {
        "issue_date": issue_date,
        "mode": mode,
        "pool_core": len(core["papers"]), "pool_expand": len(extra),
        "new_core": len(new_core), "new_expand": len(new_exp),
    }
    print("[issue %s] %s | pool %d/%d -> new %d/%d"
          % (issue_date, mode, pool_stats["pool_core"], pool_stats["pool_expand"],
             pool_stats["new_core"], pool_stats["new_expand"]))

    scored_all = [pack(p) for p in core["papers"]]
    expand_full = [pack(p) for p in extra]
    scored = [s for s in scored_all if s["id"] in new_core_ids]
    expand_all = [s for s in expand_full if s["id"] in new_exp_ids]
    scored.sort(key=lambda x: -x["score"])
    expand_all.sort(key=lambda x: -x["score"])

    top_n = int(cfg.get("top_recommend", 14))
    top_e = int(cfg.get("top_expand", 10))
    # 打分达标，或被 LLM 显式点评过（人工挑选优先于分数阈值）的论文入选
    def picked(s, floor):
        if (notes.get(s["id"]) or {}).get("skip") or s["pen"] < 0:
            return False
        return s["score"] >= floor or bool(notes.get(s["id"]))

    core_recs = [s for s in scored if picked(s, 7)][:top_n]
    exp_recs = [s for s in expand_all if picked(s, 9)][:top_e]

    # 首次上手兜底：画像还很薄（比如刚用 examples 初始化、一个主题都没调）时，
    # 严格阈值可能一篇都不达标，页面会是空的。此时退化为「按分数取前 N」，
    # 并给每条打上提示，让用户至少能开始收藏 / Downvote 来喂画像。
    # 注意只在**严格结果为 0** 时触发，不改变已调好画像的用户（作者本人）的精度。
    fallback = []
    if not core_recs and scored:
        core_recs = [s for s in scored if picked(s, -1e9)][:top_n]
        for s in core_recs:
            s["_fb"] = True
        if core_recs:
            fallback.append("core")
    if not exp_recs and expand_all:
        exp_recs = [s for s in expand_all if picked(s, -1e9)][:top_e]
        for s in exp_recs:
            s["_fb"] = True
        if exp_recs:
            fallback.append("expand")
    if fallback:
        print("[fallback] 画像未命中主题，%s 列表改为按分数兜底（建议补充主题关键词）"
              % " / ".join(fallback), file=sys.stderr)

    def tier(s):
        return "强烈推荐" if s >= 16 else ("推荐" if s >= 11 else "相关")

    for s in core_recs + exp_recs:
        n = notes.get(s["id"], {})
        s["tier"] = n.get("tier") or tier(s["score"])
        if n.get("note"):
            s["note"] = n["note"]
        elif s.get("_fb"):
            s["note"] = "画像尚未命中：先按分数兜底（到 /profile 补充主题关键词后会更准）"
        elif s["topics"]:
            s["note"] = "命中：" + "、".join(s["topics"][:3])
        else:
            s["note"] = "主题相关"
        s.pop("_fb", None)
    order = {short_id(k): v.get("rank") for k, v in (notes or {}).items()
             if isinstance(v, dict) and "rank" in v}
    if order:
        core_recs.sort(key=lambda r: order.get(r["id"], 999))
        exp_recs.sort(key=lambda r: order.get(r["id"], 999))

    json.dump(scored_all, open(os.path.join(OUT, "scores.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # 本期新增子集（结构同 raw.json）：build_report.py 优先读它渲染日报，
    # 于是分类统计 / 分类小节 / 推荐卡池都只覆盖「当天新出现的论文」。
    def issue_doc(papers, cats):
        return {
            "issue_date": issue_date,
            "mode": mode,
            "generated_at": core.get("generated_at", ""),
            "newest_seen": core.get("newest_seen", ""),
            "window_days": core.get("window_days", cfg.get("window_days", 3)),
            "categories": cats,
            "pool_size": pool_stats["pool_core"],
            "papers": papers,
        }

    json.dump(issue_doc(new_core, cfg["categories"]),
              open(os.path.join(OUT, "issue_core.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(issue_doc(new_exp, cfg.get("expand_categories", [])),
              open(os.path.join(OUT, "issue_expand.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(pool_stats, open(os.path.join(OUT, "issue_stats.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(core_recs, open(os.path.join(OUT, "recommend.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(exp_recs, open(os.path.join(OUT, "expand.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    cand = [{
        "id": s["id"], "title": s["title"], "primary": s["primary"],
        "score": s["score"], "topics": s["topics"],
        "familiar_authors": s["familiar_authors"], "abstract": s["abstract"][:700],
        "pool": "core",
    } for s in core_recs] + [{
        "id": s["id"], "title": s["title"], "primary": s["primary"],
        "score": s["score"], "topics": s["topics"],
        "familiar_authors": s["familiar_authors"], "abstract": s["abstract"][:700],
        "pool": "expand",
    } for s in exp_recs]
    json.dump(cand, open(os.path.join(OUT, "recommend_candidates.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # 前端实时重排索引：核心全量 + 扩展池前 80 篇
    idx = {
        "topics": [t["name"] for t in topics],
        "weights": [round(t["weight"], 4) for t in topics],
        "seeds": [t["seed"] for t in topics],
        "kw": {k: round(v, 3) for k, v in kwmap.items() if abs(v) > 0.05},
        "pens": {k: v for k, v in pens.items() if v},
        "papers": [{k: v for k, v in s.items()
                    if k in ("id", "title", "authors", "primary", "cats", "published",
                             "abstract", "summary", "summary_en", "tv", "base", "toks",
                             "pen", "pdf",
                             "topics", "familiar_authors", "systems")}
                   for s in scored + expand_all[:80]],
        "expand_ids": [s["id"] for s in expand_all[:80]],
    }
    json.dump(idx, open(os.path.join(OUT, "papers_index.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print("core %d -> rec %d | expand pool %d -> rec %d" % (
        len(scored), len(core_recs), len(expand_all), len(exp_recs)))
    for s in core_recs:
        print("  C %6.1f %-11s %-8s %s" % (s["score"], s["id"], s["primary"], s["title"][:58]))
    for s in exp_recs:
        print("  E %6.1f %-11s %-8s %s" % (s["score"], s["id"], s["primary"], s["title"][:58]))


if __name__ == "__main__":
    main()
