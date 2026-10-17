#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动态兴趣画像：根据「收藏 / 下载 / PDF / Abstract / Downvote」行为在线更新权重。

持久化文件（output/ 下）：
  profile_state.json  主题倍率、关键词权重、论文级偏好、行为计数
  behavior.json       行为流水（最近 2000 条），供审计与离线分析

设计要点
  - 主题级：seed_weight[主题] × learned_mult[主题]，倍率初值 1.0，范围 [0.25, 3.0]
  - 关键词级：从论文标题/摘要抽取的实词，权重随行为增减，范围 [-4, 4]
  - 论文级：downvote 直接给该论文一个大负分（-12），保证后续不再推荐
  - 所有权重供 recommend.py（服务端）与报告页面（前端实时重排）共用
"""
import json
import os
import re
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paperutil as pu  # noqa: E402
import paths  # noqa: E402

OUT = pu.OUT
PROFILE_PATH = paths.PROFILE_STATE_PATH
BEHAVIOR_PATH = paths.BEHAVIOR_PATH
INTERESTS = paths.INTERESTS

DEFAULT_CFG = {
    "actions": {
        "favorite": 1.0, "unfavorite": -0.7, "download": 1.3,
        "pdf": 0.55, "abstract": 0.3, "downvote": -1.6, "undownvote": 0.9,
    },
    "lr_topic": 0.06, "lr_keyword": 0.05,
    "topic_range": [0.25, 3.0], "keyword_range": [-4.0, 4.0],
    "downvote_paper_penalty": -12.0,
    # 负向行为（downvote / undownvote）是否参与「主题倍率 / 关键词权重」的全局学习。
    # 默认关闭，原因见 apply_event() 的注释：Downvote 的语义是「这篇不要」，
    # 它已经由论文级 -12 惩罚精确定位；再让它在全局词表 / 主题上扣分会产生曝光偏置，
    # 把用户的主研究方向反复打到下限，最终让推荐器整体失效。
    "learn_neg_topics": False, "learn_neg_keywords": False,
}

STOP = set("""a an the and or but if then than that this these those of in on at to for from by with without
via using use used uses we our us it its is are was were be been being can could may might should would
do does did not no nor as so such very more most less least many much each other others same different
new novel approach approaches based paper work works study studies show shows shown propose proposed
proposes present presents presented introduce introduces introduced first second third also however
therefore thus hence moreover furthermore finally our we ours their his her they them which who whom
whose what when where why how all any both few own too only just about into over under again further
once here there because while during before after above below up down out off between among within
against toward towards upon across behind beyond plus minus per via non pre post re un
""".split())

TOKEN_RX = re.compile(r"[a-z][a-z0-9\-]{2,}")

_lock = threading.Lock()


# ------------------------------------------------------------------ 基础 IO

def _cfg():
    try:
        d = json.load(open(INTERESTS, encoding="utf-8"))
        c = dict(DEFAULT_CFG)
        c.update(d.get("behavior") or {})
        a = dict(DEFAULT_CFG["actions"])
        a.update((d.get("behavior") or {}).get("actions") or {})
        c["actions"] = a
        return c
    except Exception:
        return dict(DEFAULT_CFG)


def load():
    if os.path.exists(PROFILE_PATH):
        try:
            d = json.load(open(PROFILE_PATH, encoding="utf-8"))
            d.setdefault("topic_mult", {})
            d.setdefault("kw", {})
            d.setdefault("paper_bonus", {})
            d.setdefault("counts", {})
            return d
        except Exception:
            pass
    return {"topic_mult": {}, "kw": {}, "paper_bonus": {}, "counts": {}, "updated_at": ""}


def save(st):
    os.makedirs(OUT, exist_ok=True)
    st["updated_at"] = pu.now_str()
    tmp = PROFILE_PATH + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, PROFILE_PATH)


def load_behavior():
    if os.path.exists(BEHAVIOR_PATH):
        try:
            return json.load(open(BEHAVIOR_PATH, encoding="utf-8"))
        except Exception:
            pass
    return []


def save_behavior(items):
    os.makedirs(OUT, exist_ok=True)
    tmp = BEHAVIOR_PATH + ".tmp"
    json.dump(items[-2000:], open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, BEHAVIOR_PATH)


def seed_weights():
    """主题种子权重。顺序 = interests.json 原有主题 + 用户自定义主题（customize 合并）。

    必须与 recommend.py 的 topics 顺序一致，否则前端重排会拿错权重。
    """
    import customize as CZ  # 延迟导入，避免循环
    return CZ.effective_seed_weights()


def weights(st=None):
    """当前主题权重 = 种子 × 学习倍率。"""
    st = st or load()
    out = []
    for name, w in seed_weights():
        out.append((name, round(w * float(st["topic_mult"].get(name, 1.0)), 4)))
    return out


def topic_names():
    return [n for n, _ in seed_weights()]


# ------------------------------------------------------------------ 文本特征

def tokens(text, limit=45):
    """抽实词（去停用词），返回按出现频次降序的前 limit 个。"""
    freq = {}
    for m in TOKEN_RX.findall((text or "").lower()):
        if m in STOP or len(m) < 3:
            continue
        freq[m] = freq.get(m, 0) + 1
    if not freq:
        return []
    items = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in items[:limit]]


# ------------------------------------------------------------------ 行为更新

def _topic_hits(paper, topics):
    """返回 {主题名: (标题命中, 摘要命中)}。"""
    import recommend as R  # 延迟导入，避免循环
    title = R._norm(paper.get("title"))
    abstract = R._norm(paper.get("abstract"))
    out = {}
    for name, kws in topics:
        th = sum(1 for rx in kws if rx.search(title))
        ah = sum(1 for rx in kws if rx.search(abstract))
        if th or ah:
            out[name] = (th, ah)
    return out


def apply_event(sid, action, paper=None, index=None):
    """记录一次行为并就地更新画像。返回 (profile_state, delta_info)。"""
    cfg = _cfg()
    w = float(cfg["actions"].get(action, 0.0))
    sid = pu.short_id(sid)
    with _lock:
        st = load()
        st["counts"][action] = int(st["counts"].get(action, 0)) + 1

        if action in ("downvote", "undownvote"):
            pen = float(cfg.get("downvote_paper_penalty", -12.0))
            st["paper_bonus"][sid] = pen if action == "downvote" else 0.0
            if action == "undownvote":
                st["paper_bonus"].pop(sid, None)

        if paper is None and index is not None:
            paper = index.get(sid)

        # 负向行为是否参与全局学习（见 DEFAULT_CFG 注释）。
        # 曝光偏置：推荐越多的主题，被 Downvote 的绝对次数也越多；若让 Downvote 扣主题分，
        # 系统会把自己的主打方向一路打到 0.25 下限（2026-10-16 实测：用户五个主研究方向
        # 全部触底，164 篇新论文 0 篇够到推荐线）。论文级 -12 已经能精确定位「这篇不要」，
        # 全局学习只保留正向信号（收藏 / 下载 / PDF / Abstract），语义上更可靠。
        is_neg = action in ("downvote", "undownvote")
        learn_t = bool(cfg.get("learn_neg_topics", False)) if is_neg else True
        learn_k = bool(cfg.get("learn_neg_keywords", False)) if is_neg else True
        if is_neg and not (learn_t or learn_k):
            save(st)
            beh = load_behavior()
            beh.append({"id": sid, "action": action, "at": pu.now_str(), "topics": []})
            save_behavior(beh)
            return st, {"action": action, "weight": w, "topics": [], "kw": 0,
                        "note": "negative signal: paper-level penalty only"}

        info = {"action": action, "weight": w, "topics": [], "kw": 0}
        if paper and w:
            try:
                import recommend as R
                _p, topics, _nw, _n = R.load_profile()
                topic_kws = [(t["name"], t["rx"]) for t in topics]
                hits = _topic_hits(paper, topic_kws)
                blob = (paper.get("title") or "") + " " + (paper.get("abstract") or "")
                toks = tokens(blob)
                lr_t = float(cfg.get("lr_topic", 0.06))
                lr_k = float(cfg.get("lr_keyword", 0.05))
                tmin, tmax = cfg.get("topic_range", [0.25, 3.0])
                kmin, kmax = cfg.get("keyword_range", [-4.0, 4.0])
                # 命中越多，单次学习量越大（但收敛，避免刷同一篇刷爆）
                if learn_t:
                    for name, (th, ah) in hits.items():
                        strength = min(4, th) * 0.6 + min(8, ah) * 0.1
                        cur = float(st["topic_mult"].get(name, 1.0))
                        nxt = cur + lr_t * w * max(0.3, min(2.5, strength))
                        st["topic_mult"][name] = round(min(tmax, max(tmin, nxt)), 4)
                        info["topics"].append(name)
                if learn_k:
                    for tk in toks:
                        cur = float(st["kw"].get(tk, 0.0))
                        nxt = cur + lr_k * w
                        st["kw"][tk] = round(min(kmax, max(kmin, nxt)), 4)
                    info["kw"] = len(toks)
            except Exception as e:  # noqa
                info["error"] = str(e)

        save(st)
        beh = load_behavior()
        beh.append({"id": sid, "action": action, "at": pu.now_str(),
                    "topics": info.get("topics", [])[:6]})
        save_behavior(beh)
        return st, info


def paper_bonus(sid, st=None):
    st = st or load()
    return float(st["paper_bonus"].get(pu.short_id(sid), 0.0))


def main():
    st = load()
    print("counts:", st.get("counts"))
    print("topic multipliers:")
    for n, m in sorted(st.get("topic_mult", {}).items(), key=lambda kv: -kv[1]):
        print("  %.2f  %s" % (m, n))
    kws = sorted(st.get("kw", {}).items(), key=lambda kv: kv[1])
    print("most negative keywords:", kws[:12])
    print("most positive keywords:", kws[-12:][::-1])
    print("downvoted:", [k for k, v in st.get("paper_bonus", {}).items() if v < 0])


if __name__ == "__main__":
    main()
