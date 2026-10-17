#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打分核心：纯函数，无 IO、无全局状态（单一职责）。

为什么单独一层
--------------
`recommend.py` 原来同时承担四件事：读四个输入文件、拼画像、按公式打分、
写四个输出文件。于是「打分是否正确」这件事**只能整条流水线跑起来才能验**，
而它恰恰是最容易出错、最值得单独测的部分（多词关键词失效那次缺陷就藏在这里，
表现为"分数普遍偏低"，不报错、不崩溃）。

拆出来后本模块只回答两个问题：
  features(paper, ...) -> 这篇论文的分数由哪几块构成（可解释）
  score(features, ...) -> 把这几块合成一个数

调用方（recommend.py）负责组装参数与落盘。因此这里的每个函数都可以用普通
单测覆盖，不需要碰文件系统，也不需要 mock 网络。

公式（与 README / docs/architecture/ranking.md 保持一致）
    score = base + pen + Σ(raw_topic × weight_topic) + Σ(关键词权重)
    base  = 10×熟悉作者数 + 6×代表系统命中数 + neg_w×3×min(负向词命中数, 4)
    raw   = 4×min(标题命中数, 4) + 0.8×min(摘要命中数, 15)
"""
import re

import profile as PF

# ---- 打分常量（原来是散落在公式里的字面量，提取后便于对照文档与调参） ----
TITLE_HIT_W = 4.0         # 标题里命中一个主题关键词的分值
TITLE_HIT_CAP = 4         # 标题命中计数上限（防止关键词堆砌刷分）
ABS_HIT_W = 0.8           # 摘要里命中一个主题关键词的分值
ABS_HIT_CAP = 15          # 摘要命中计数上限
FAMILIAR_W = 10.0         # 每命中一位「熟悉研究者」
SYSTEM_W = 6.0            # 每命中一个「代表系统」
NEG_CAP = 4               # 负向关键词计次上限
NEG_SCALE = 3.0           # 负向词与 neg_w 相乘的放大系数


def _norm(s):
    """归一化：折叠空白 + 小写。匹配前必须做，否则换行会切断关键词。"""
    return re.sub(r"\s+", " ", (s or "")).lower()


def _rx(term):
    r"""关键词 → 词边界正则。

    空格 / 连字符 / 下划线视为**等价分隔**：`isolation level` 也要能命中
    `isolation-level`。早期实现是一串链式 replace：

        re.escape(t).replace(r"\ ", r"[\s\-]+").replace(r"\-", r"[\s\-]?")

    第二次 replace 会把第一次刚生成的 `[\s\-]` 里的 `\-` 再改一遍，产出的字符类
    实际变成 `[\\s[\\s\\-]?]`（`?` 成了字面量、`]` 提前闭合），**多词关键词从此永不命中**，
    且单测很难察觉——分数只是偏低而不会报错。现改为按分隔符切词再拼装。
    """
    parts = [p for p in re.split(r"[\s\-_]+", (term or "").lower().strip()) if p]
    if not parts:
        return re.compile(r"(?!)")          # 空关键词：永不匹配
    body = r"[\s\-_]+".join(re.escape(p) for p in parts)
    return re.compile(r"(?<![a-z0-9])" + body + r"(?![a-z0-9])")


def topic_hits(paper, topics):
    """各主题在这篇论文里的原始命中量。

    返回 ``(tv, detail)``：
      tv      [[主题下标, 原始分], ...] —— 给 score() 用，保持紧凑
      detail  [{"topic", "raw", "title_hits", "abstract_hits"}, ...] —— 给调试与解释用
    """
    title = _norm(paper.get("title"))
    abstract = _norm(paper.get("abstract"))
    tv, detail = [], []
    for i, t in enumerate(topics):
        th = sum(1 for r in t["rx"] if r.search(title))
        ah = sum(1 for r in t["rx"] if r.search(abstract))
        if not (th or ah):
            continue
        raw = TITLE_HIT_W * min(th, TITLE_HIT_CAP) + ABS_HIT_W * min(ah, ABS_HIT_CAP)
        tv.append([i, round(raw, 2)])
        detail.append({"topic": t["name"], "raw": round(raw, 2),
                       "title_hits": th, "abstract_hits": ah})
    detail.sort(key=lambda x: -x["raw"])
    return tv, detail


def base_score(paper, people, systems, neg_w, neg_rx):
    """与行为权重无关的静态分（作者 / 系统 / 负向词）。

    返回 ``(base, fam, syshit, neg_hits)``，四者都进 features，便于前端解释。
    """
    blob = _norm(paper.get("title")) + " " + _norm(paper.get("abstract"))
    authors = " ".join(paper.get("authors") or []).lower()
    fam = [n for n in people if n.lower() in authors]
    syshit = [s for s in systems if _rx(s).search(blob)]
    neg_hits = sum(1 for r in neg_rx if r.search(blob))
    base = (FAMILIAR_W * len(fam) + SYSTEM_W * len(syshit)
            + neg_w * min(neg_hits, NEG_CAP) * NEG_SCALE)
    return round(base, 2), fam, syshit, neg_hits


def features(p, topics, neg_w, neg_rx, people, systems, kwmap=None):
    """拆解一篇论文的得分构成（静态 base 与动态部分分离）。

    ``kwmap`` 目前不参与计算（关键词权重要按 token 逐个累加，属于 score 阶段），
    保留在签名里是为了与既有调用方兼容。
    """
    tv, detail = topic_hits(p, topics)
    base, fam, syshit, neg_hits = base_score(p, people, systems, neg_w, neg_rx)
    return {
        "tv": tv,
        "base": base,
        "toks": PF.tokens((p.get("title") or "") + " " + (p.get("abstract") or "")),
        "detail": detail,
        "fam": fam,
        "sys": syshit,
        "neg_hits": neg_hits,
    }


def score(f, topics, kwmap, pen):
    """合成总分 = 静态基准 + 论文级罚分 + 主题命中×主题权重 + 关键词累计权重。"""
    s = f["base"] + float(pen or 0.0)
    for i, raw in f["tv"]:
        s += raw * topics[i]["weight"]
    for tk in f["toks"]:
        s += float(kwmap.get(tk, 0.0))
    return s
