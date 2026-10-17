#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文本信号抽取：HTML 去标签、人名、专业实词、主题命中（纯函数层）。

职责边界
--------
本模块**只做字符串 → 结构化信号**的变换：不读文件、不联网、不碰配置与画像文件。
传进来的 ``prof`` 是内存里的字典，传出去的也是普通 list。

这样拆开的直接好处：这些函数是「兴趣来源解析」里最需要反复调参数的部分
（哪个词该进画像、哪些是人名），现在可以用字符串字面量直接测，不用先造一个
来源文件、再 mock 一次网络请求。

依赖方向：``textscan`` → ``profile``（复用同一套分词器与停用词，避免两套口径）。
"""
import re
import sys
import os
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import profile as PF  # noqa: E402

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

NAME_PAIR = re.compile(r"\b([A-Z][a-z]{1,15})\s+([A-Z][a-z]{1,15})\b")


class _Text(HTMLParser):
    """把 HTML 抽成纯文本：丢 script/style，块级标签换行。"""

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
    """HTML → 纯文本。解析失败也要返回已读到的部分，不能让一个坏标签毁掉整次解析。"""
    p = _Text()
    try:
        p.feed(raw)
    except Exception:
        pass
    txt = "".join(p.buf)
    txt = re.sub(r"[ \t\r\f\v]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt.strip()


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
    """画像里已出现的关键词（含负向），用于去重。"""
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
