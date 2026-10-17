#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取论文作者单位（affiliation）。

为什么需要单独一步
  arXiv API（export.arxiv.org）**不返回** affiliation 字段。
  可行的自动来源是 arXiv 的 LaTeXML HTML 版（2023-12 之后投稿的论文有）
  以及 ar5iv 的镜像 HTML —— 两者都把作者与单位放在 ltx_* 语义标签里。

策略
  1) https://arxiv.org/html/<sid>v1..v3   （新论文）
  2) https://ar5iv.labs.arxiv.org/html/<sid> （旧论文兜底）
  3) 都拿不到 -> 不写缓存，页面就不渲染单位行（宁可缺，不要错）

结果缓存到 output/affiliations.json，跨日累积；已抓过的论文默认跳过，
所以每天只会为新入选的论文付网络代价（约 3s/篇）。

用法
  python fetch_affil.py            # 只补没抓过的
  python fetch_affil.py --force    # 全部重抓
  python fetch_affil.py --max 20   # 限制本轮篇数
"""
import html as ihtml
import json
import os
import re
import ssl
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paperutil as pu  # noqa: E402

OUT = pu.OUT
AFF_PATH = os.path.join(OUT, "affiliations.json")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) arxiv-digest/3.0"}
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

ORG_RX = re.compile(
    r"universit|institut|laborator|department|school|college|academy|research|"
    r"center|centre|group|labs?\b|faculty|technion|cnrs|inria|eth\b|epfl|"
    r"inc\b|ltd\b|corp|gmbh|foundation|hospital|observatory|"
    r"大学|学院|研究所|实验室|研究院|中心",
    re.I)

TAG_RX = re.compile(r"<[^>]+>")
NUM_PREFIX_RX = re.compile(r"^[\s\d\*†‡§¶,;]*(?:and\s+)?", re.I)
# 「First Last」形状的串多半是作者名被误当成单位
PERSON_LIKE_RX = re.compile(r"^[A-Z][A-Za-z.\-]+\s+[A-Z][A-Za-z.\-]+$")
# 「City, ST」形状是城市/州，不是机构
CITY_STATE_RX = re.compile(r"[A-Za-z\u4e00-\u9fff]+,\s*[A-Z]{2}$")


def _clean(s):
    s = TAG_RX.sub(" ", s or "")
    s = ihtml.unescape(s)
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = NUM_PREFIX_RX.sub("", s).strip()
    s = s.strip(" ,;:*†‡§¶-")
    s = re.sub(r"^(?:and|,)\s+", "", s, flags=re.I)
    return s.strip()


def _looks_like_org(s):
    """严格判定：必须命中机构关键词。宽松的「词首大写」启发式会造成大量误报。"""
    if not s or len(s) < 5 or len(s) > 160:
        return False
    if s.isdigit() or PERSON_LIKE_RX.match(s):
        return False
    if CITY_STATE_RX.search(s) and not ORG_RX.search(s):
        return False
    return bool(ORG_RX.search(s))


def _acceptable_affil(s):
    """ltx_affiliation 节点里的内容是作者明文标注的单位，可信度高，只做基本清洗。

    「城市+两位代码」的判定必须让位给机构关键词：`CITY_STATE_RX` 无法区分
    美国州缩写与英国/中国等国家代码（"Manchester, UK"、"Shanghai, CN" 都命中），
    早先无条件下这一刀，把整批英国单位判成城市丢弃（真实漏检）。
    """
    if not s or len(s) < 3 or len(s) > 160:
        return False
    if s.isdigit() or PERSON_LIKE_RX.match(s):
        return False
    if CITY_STATE_RX.search(s) and not ORG_RX.search(s):
        return False
    return True


# 单位后面常跟着联系方式 / 资助信息，一律截断
CUT_RX = re.compile(
    r"\s*(?:E-?mail|ORCID|Correspondence|Corresponding|Supported by|Funded by|"
    r"http|www\.|@|\{|\(|\[)", re.I)
# 「J. Chen is the corresponding author.」/「J. Dong, 」这类作者前缀
AUTH_PREFIX_RX = re.compile(
    r"^(?:[A-Z]\.\s*)+(?:[A-Z][a-z]+\s*)+(?:is|are)\s+(?:the\s+)?corresponding\s+author\.?\s*",
    re.I)
AUTH_LIST_RX = re.compile(r"^(?:[A-Z]\.\s*[A-Z][a-z]+(?:\s*(?:,|and|&)\s*)?)+[,，]?\s*")
INITIALS_RX = re.compile(r"^(?:[A-Z]\.[\s]*)+$")
# 网址混进来时（"...-lab.github.io/xxx"）会因含 lab 而误判成机构，直接丢弃
URL_LIKE_RX = re.compile(r"\.(?:com|org|io|cn|net|edu|gov|ac)\b|github|https?://|www\.", re.I)
# 只剩一个通用机构词（"Labs" / "University"）时不构成有效单位
GENERIC_ONLY_RX = re.compile(
    r"^(?:the\s+)?(?:labs?|universit(?:y|ies)|institut(?:e|ion)?|department|"
    r"school|college|academy|research|cent(?:er|re)|group|faculty|"
    r"corporation|company|inc|ltd)\.?$", re.I)
# 结尾的 "City, ST, Country" / "City, Country" 位置串。
# 中间段限定为「单个词」，避免把 "..., Tsinghua University, Beijing, China"
# 里的大学名一并吃掉。
COUNTRY_TAIL_RX = re.compile(
    r"(?:,\s*[A-Za-z\.\-']+)*,\s*(?:USA|U\.S\.A\.|United States|UK|United Kingdom|"
    r"Germany|France|China|India|Canada|Japan|South Korea|Korea|Italy|Spain|"
    r"Netherlands|Switzerland|Israel|Singapore|Sweden|Finland|Austria|Belgium|"
    r"Australia|Brazil|Norway|Denmark|Poland|Portugal|Ireland|Greece|Turkey|Russia|"
    r"Hong Kong, China|Taiwan, China|Macao, China|United Arab Emirates)\s*$", re.I)
# 邮编 + 城市（"90411 Nürnberg"）
ZIP_TAIL_RX = re.compile(r",\s*\d{4,6}\s+[^\W\d_][\w\.\-]*(?:\s+[^\W\d_][\w\.\-]*)*$")
# 「Institute / Department ...」开头的词是通用机构词：说明前缀属于机构名本身
GENERIC_FIRST_RX = re.compile(
    r"^(?:institut|laborator|depart(?:ment)?|school|college|academy|universit|"
    r"research|cent(?:er|re)|faculty|group|labs?|hospital|foundation|"
    r"corporation|company|faculty)\w*$", re.I)


def _tidy_unit(u, persons=()):
    """把「J. Dong, Beijing Academy of ... (BABEC), Beijing, China (dong@x.cn)」
    收敛成「Beijing Academy of Blockchain and Edge Computing」。"""
    s = u
    s = AUTH_PREFIX_RX.sub("", s)
    s = AUTH_LIST_RX.sub("", s)
    s = CUT_RX.split(s)[0]
    # 「EngineeringKorea University」这种粘连：小写串后紧跟大写时补空格（不碰 eBPF / MPI-SWS）
    s = re.sub(r"([a-z]{3,})([A-Z])", r"\1 \2", s)
    s = re.sub(r"[˜~^\s]+", " ", s).strip()
    s = s.strip(" ,;:-–—·|.")
    s = re.sub(r"\s+", " ", s)
    loc_tail = bool(COUNTRY_TAIL_RX.search(s))
    # 情况一：作者姓名以「独立前缀」形式混入单位（persons 里是干净的姓名）。
    # 仅当「末尾带位置串」且「剥离后不以通用机构词开头」时才剥离 ——
    # 否则「Max Planck Institute ...」这类姓名与机构首词相同的会被误伤。
    if loc_tail:
        for p in sorted((p for p in persons if p), key=len, reverse=True):
            if s.lower().startswith(p.lower() + " "):
                rem = s[len(p):].strip(" ,;:-")
                head = rem.split()[0] if rem.split() else ""
                if rem and not GENERIC_FIRST_RX.match(head):
                    s = rem
                break
    # 情况二：LaTeXML 把姓名与单位粘在同一个 <span class="ltx_personname"> 里
    # （"Sanmi KoyejoStanford UniversityStanford, CA, USA"）。此时 persons 里会
    # 出现与候选串几乎同形的「脏姓名」，据此判定并剥掉开头的「名 姓」两词。
    for p in sorted((p for p in persons if p), key=len, reverse=True):
        pn = re.sub(r"([a-z]{3,})([A-Z])", r"\1 \2", p)
        if len(pn.split()) >= 4 and s.lower().startswith(pn.lower()):
            rem = " ".join(s.split()[2:]).strip(" ,;:-")
            head = rem.split()[0] if rem.split() else ""
            if rem and not GENERIC_FIRST_RX.match(head):
                s = rem
            break
    # 结尾位置串：仅在剥离后仍是机构时才采用
    s2 = COUNTRY_TAIL_RX.sub("", s).strip(" ,;:-")
    if s2 and ORG_RX.search(s2):
        s = s2
    s = ZIP_TAIL_RX.sub("", s).strip(" ,;:-")
    # 末尾重复首词（"Stanford University Stanford"）去掉。
    # 只对比首词，避免误伤 "Institut Polytechnique de Paris" 这类正常机构名。
    toks = s.split()
    if len(toks) > 2 and toks[-1].lower().strip(",.") == toks[0].lower().strip(",."):
        toks.pop()
    s = " ".join(toks).strip(" ,;:-")
    if INITIALS_RX.match(s) or URL_LIKE_RX.search(s) or GENERIC_ONLY_RX.match(s):
        return ""
    # LaTeX 命令残留（如 `\ddagger Individual Researcher`、`\textsuperscript{1}`）：
    # 不是机构名，宁可判「没找到」也不写错（2026-09-14：2507.01663 曾显示成
    # 「\ddagger Individual Researcher」）。
    if "\\" in s:
        return ""
    return s


def _find_all(pattern, text, flags=re.S | re.I):
    return [m.group(1) for m in re.finditer(pattern, text, flags)]


def extract(html_text):
    """从 LaTeXML HTML 里抽取单位。返回 {units:[...], by_author:{name: unit}}。"""
    m = re.search(r'class="[^"]*ltx_authors[^"]*"', html_text, re.I)
    if not m:
        return {"units": [], "by_author": {}}
    # 作者区通常很短；取一段窗口，到 abstract 之前
    start = m.start()
    end = len(html_text)
    for anchor in ('class="ltx_abstract', 'class="ltx_section', 'id="abstract'):
        i = html_text.find(anchor, start)
        if i > 0:
            end = min(end, i)
    win = html_text[start:min(end, start + 30000)]

    persons = [_clean(x) for x in _find_all(
        r'class="[^"]*ltx_personname[^"]*"[^>]*>(.*?)</span>', win)]
    affils = [_clean(x) for x in _find_all(
        r'class="[^"]*ltx_affiliation[^"]*"[^>]*>(.*?)</span>', win)]
    contacts = [_clean(x) for x in _find_all(
        r'class="[^"]*ltx_contact[^"]*"[^>]*>(.*?)</span>', win)]

    cand = [a for a in affils if _acceptable_affil(a)]
    if not cand:
        # 兜底：作者区里任何含机构关键词的片段（这里必须严格，否则会把标题和作者名捡进来）
        cand = [x for x in re.split(r"[\n;·|]", TAG_RX.sub("\n", win)) if _looks_like_org(_clean(x))]

    pset = {p.lower() for p in persons}
    units, seen = [], set()
    for u in cand:
        t = _tidy_unit(u, persons)
        k = t.lower()
        if not t or k in seen or k in pset:
            continue
        seen.add(k)
        units.append(t)

    # 必须至少命中一个机构关键词。城市/国家（"Kelowna" / "Nanjing" / "China"）不是单位，
    # 宁可判为「没找到」也不要写进缓存 —— 展示错误信息的代价高于缺失。
    units = [u for u in units if ORG_RX.search(u)]

    by_author = {}
    if len(persons) == len(contacts) and persons:
        for p, c in zip(persons, contacts):
            if p and _looks_like_org(c):
                by_author[p] = c

    return {"units": units[:12], "by_author": by_author}


def fetch_html(sid):
    """返回 (html_text, src) 或 (None, '')。"""
    for v in ("v1", "v2", "v3"):
        url = "https://arxiv.org/html/%s%s" % (sid, v)
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as r:
                if r.status == 200:
                    t = r.read(3000000).decode("utf-8", "replace")
                    if "ltx_" in t and len(t) > 4000:
                        return t, "arxiv-html/" + v
        except Exception:
            continue
        finally:
            time.sleep(1.0)
    url = "https://ar5iv.labs.arxiv.org/html/%s" % sid
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=40, context=SSL_CTX) as r:
            if r.status == 200:
                t = r.read(3000000).decode("utf-8", "replace")
                if "ltx_" in t and len(t) > 4000:
                    return t, "ar5iv"
    except Exception:
        pass
    return None, ""


def load_cache():
    if os.path.exists(AFF_PATH):
        try:
            with open(AFF_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(d):
    tmp = AFF_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, AFF_PATH)


def targets(cfg):
    """需要单位的论文：推荐 + 兴趣扩展 + 重点论文。"""
    ids, seen = [], set()

    def add(x):
        s = pu.short_id(x)
        if s and s not in seen and re.match(r"^(\d{4}\.\d{4,5}|[a-z\-]+/\d{7})$", s):
            seen.add(s)
            ids.append(s)

    for name in ("recommend.json", "expand.json"):
        p = os.path.join(OUT, name)
        if os.path.exists(p):
            try:
                for it in json.load(open(p, encoding="utf-8")):
                    add(it.get("id"))
            except Exception:
                pass
    hp = os.path.join(OUT, "highlights.json")
    if os.path.exists(hp):
        try:
            for k in json.load(open(hp, encoding="utf-8")):
                add(k)
        except Exception:
            pass
    return ids[:int(cfg.get("affil_targets", 60))]


def main():
    cfg = pu.load_config()
    cache = load_cache()
    ids = targets(cfg)
    force = "--force" in sys.argv
    limit = None
    if "--max" in sys.argv:
        try:
            limit = int(sys.argv[sys.argv.index("--max") + 1])
        except Exception:
            limit = None

    todo = [i for i in ids if force or i not in cache]
    if "--only" in sys.argv:
        try:
            sel = set(sys.argv[sys.argv.index("--only") + 1].split(","))
        except Exception:
            sel = set()
        # 允许指定尚未进入 targets 的 arXiv 短号
        todo = [i for i in ids if i in sel] + [i for i in sel if i not in ids]
    if limit:
        todo = todo[:limit]
    if not todo:
        print("affiliations: nothing to do (%d cached)" % len(cache))
        return

    print("affiliations: %d targets, %d to fetch" % (len(ids), len(todo)))
    ok = fail = 0
    for n, sid in enumerate(todo, 1):
        html_text, src = fetch_html(sid)
        if not html_text:
            fail += 1
            sys.stderr.write("[%d/%d] %s: no HTML (skip)\n" % (n, len(todo), sid))
            time.sleep(2.0)
            continue
        res = extract(html_text)
        if res["units"]:
            cache[sid] = {"units": res["units"], "by_author": res["by_author"],
                          "src": src, "at": pu.now_str()}
            ok += 1
            print("[%d/%d] %s: %s" % (n, len(todo), sid, " | ".join(res["units"][:3])))
        else:
            fail += 1
            sys.stderr.write("[%d/%d] %s: no affiliation found\n" % (n, len(todo), sid))
        if n % 10 == 0:
            save_cache(cache)
        time.sleep(3.0)

    save_cache(cache)
    print("affiliations: %d ok, %d failed, cache=%d -> %s" % (ok, fail, len(cache), AFF_PATH))


if __name__ == "__main__":
    main()
