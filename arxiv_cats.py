#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arXiv 分类体系的唯一权威表（校验 / 检索 / 中文名 / 邻域推导）。

为什么要有这个模块
------------------
改造前，分类是**硬编码**在代码与模板里的：`config.example.json` 写死四个类别、
`page.html` 的标题写死 `arXiv cs.*`、`fetch_expand.py` 兜底写死一串 cs.xx。
这在一个「只盯 cs.DB 等六类」的个人工具里没问题，但作为通用 digest 应用就不成立：
用户要能自己选任意 arXiv 分类，而分类是否合法必须有一个可查询的真源。

数据来源
--------
<https://arxiv.org/category_taxonomy>（抓取于 2026-10，共 20 个 archive / 156 个分类）。
arXiv 增删分类时，只改本文件的 `_ARCHIVES` 即可，其它模块无需改动。

两级结构（与界面上的两个联动下拉框一一对应）
--------------------------------------------
``abc``    archive，如 ``cs`` / ``math`` / ``quant-ph``
``def``    archive 内的分类后缀，如 ``DB`` / ``LO`` / ``stat-mech``

绝大多数分类形如 ``abc.def``。少数 archive 只有唯一一个分类、且分类号与 archive
同名（``hep-th``、``quant-ph``、``gr-qc``、``math-ph``、``nucl-ex``、``nucl-th``、
``hep-ex``、``hep-lat``、``hep-ph``），它们**没有点号**。这类 archive 在表里以
``"categories": []`` + ``"single": True`` 表示，对外仍给出一个虚拟分类项
（id 等于 archive id），使「先选 abc 再选 def」的交互对它们同样成立。

公共 API
--------
``validate(raw) -> (ok, cat, msg)``   归一化 + 合法性校验（**唯一校验入口**）
``suggest(raw, n)``                   拼写纠错建议
``label(cat)``                        中文主题名（未知分类原样返回）
``archive(cat)`` / ``split(cat)``     结构拆分
``search(q, archive)``                ID / 英文名 / 中文名模糊搜索（界面下拉用）
``taxonomy()``                        JSON 友好快照（`/api/arxiv_categories` 与页面内嵌）
``neighbors(cats)``                   「兴趣扩展」的默认邻域池（同 archive 的兄弟分类）
"""
import re

# 分类号：archive 段小写字母/连字符；可选的点号后缀以字母开头（可含连字符）。
# 例：cs.DB、math.LO、cond-mat.stat-mech、physics.acc-ph、quant-ph。
CAT_RE = re.compile(r"^[a-z][a-z-]*(?:\.[A-Za-z][A-Za-z-]*)?$")

TAXONOMY_VERSION = "2026-10"
TAXONOMY_SOURCE = "https://arxiv.org/category_taxonomy"

# ---------------------------------------------------------------- 分类表
# (分类号, 英文名, 中文名)。中文名用于界面与摘要页分类小节标题；
# 由于全表都给了中文名，`category_names` 只需在用户想自定义时才出现。
_ARCHIVES = [
    ("cs", "Computer Science", "计算机科学", [
        ("cs.AI", "Artificial Intelligence", "人工智能"),
        ("cs.AR", "Hardware Architecture", "硬件体系结构"),
        ("cs.CC", "Computational Complexity", "计算复杂性"),
        ("cs.CE", "Computational Engineering, Finance, and Science", "计算工程、金融与科学"),
        ("cs.CG", "Computational Geometry", "计算几何"),
        ("cs.CL", "Computation and Language", "计算与语言"),
        ("cs.CR", "Cryptography and Security", "密码学与安全"),
        ("cs.CV", "Computer Vision and Pattern Recognition", "计算机视觉与模式识别"),
        ("cs.CY", "Computers and Society", "计算机与社会"),
        ("cs.DB", "Databases", "数据库"),
        ("cs.DC", "Distributed, Parallel, and Cluster Computing", "分布式、并行与集群计算"),
        ("cs.DL", "Digital Libraries", "数字图书馆"),
        ("cs.DM", "Discrete Mathematics", "离散数学"),
        ("cs.DS", "Data Structures and Algorithms", "数据结构与算法"),
        ("cs.ET", "Emerging Technologies", "新兴技术"),
        ("cs.FL", "Formal Languages and Automata Theory", "形式语言与自动机理论"),
        ("cs.GL", "General Literature", "综合文献"),
        ("cs.GR", "Graphics", "图形学"),
        ("cs.GT", "Computer Science and Game Theory", "计算机科学与博弈论"),
        ("cs.HC", "Human-Computer Interaction", "人机交互"),
        ("cs.IR", "Information Retrieval", "信息检索"),
        ("cs.IT", "Information Theory", "信息论"),
        ("cs.LG", "Machine Learning", "机器学习"),
        ("cs.LO", "Logic in Computer Science", "计算机逻辑"),
        ("cs.MA", "Multiagent Systems", "多智能体系统"),
        ("cs.MM", "Multimedia", "多媒体"),
        ("cs.MS", "Mathematical Software", "数学软件"),
        ("cs.NA", "Numerical Analysis", "数值分析"),
        ("cs.NE", "Neural and Evolutionary Computing", "神经与进化计算"),
        ("cs.NI", "Networking and Internet Architecture", "网络与互联网体系结构"),
        ("cs.OH", "Other Computer Science", "其他计算机科学"),
        ("cs.OS", "Operating Systems", "操作系统"),
        ("cs.PF", "Performance", "性能"),
        ("cs.PL", "Programming Languages", "程序设计语言"),
        ("cs.RO", "Robotics", "机器人学"),
        ("cs.SC", "Symbolic Computation", "符号计算"),
        ("cs.SD", "Sound", "声音"),
        ("cs.SE", "Software Engineering", "软件工程"),
        ("cs.SI", "Social and Information Networks", "社会与信息网络"),
        ("cs.SY", "Systems and Control", "系统与控制"),
    ]),
    ("econ", "Economics", "经济学", [
        ("econ.EM", "Econometrics", "计量经济学"),
        ("econ.GN", "General Economics", "一般经济学"),
        ("econ.TH", "Theoretical Economics", "理论经济学"),
    ]),
    ("eess", "Electrical Engineering and Systems Science", "电气工程与系统科学", [
        ("eess.AS", "Audio and Speech Processing", "音频与语音处理"),
        ("eess.IV", "Image and Video Processing", "图像与视频处理"),
        ("eess.SP", "Signal Processing", "信号处理"),
        ("eess.SY", "Systems and Control", "系统与控制"),
    ]),
    ("math", "Mathematics", "数学", [
        ("math.AC", "Commutative Algebra", "交换代数"),
        ("math.AG", "Algebraic Geometry", "代数几何"),
        ("math.AP", "Analysis of PDEs", "偏微分方程分析"),
        ("math.AT", "Algebraic Topology", "代数拓扑"),
        ("math.CA", "Classical Analysis and ODEs", "经典分析与常微分方程"),
        ("math.CO", "Combinatorics", "组合数学"),
        ("math.CT", "Category Theory", "范畴论"),
        ("math.CV", "Complex Variables", "复变函数"),
        ("math.DG", "Differential Geometry", "微分几何"),
        ("math.DS", "Dynamical Systems", "动力系统"),
        ("math.FA", "Functional Analysis", "泛函分析"),
        ("math.GM", "General Mathematics", "一般数学"),
        ("math.GN", "General Topology", "一般拓扑"),
        ("math.GR", "Group Theory", "群论"),
        ("math.GT", "Geometric Topology", "几何拓扑"),
        ("math.HO", "History and Overview", "数学史与综述"),
        ("math.IT", "Information Theory", "信息论"),
        ("math.KT", "K-Theory and Homology", "K 理论与同调"),
        ("math.LO", "Logic", "数理逻辑"),
        ("math.MG", "Metric Geometry", "度量几何"),
        ("math.MP", "Mathematical Physics", "数学物理"),
        ("math.NA", "Numerical Analysis", "数值分析"),
        ("math.NT", "Number Theory", "数论"),
        ("math.OA", "Operator Algebras", "算子代数"),
        ("math.OC", "Optimization and Control", "优化与控制"),
        ("math.PR", "Probability", "概率论"),
        ("math.QA", "Quantum Algebra", "量子代数"),
        ("math.RA", "Rings and Algebras", "环与代数"),
        ("math.RT", "Representation Theory", "表示论"),
        ("math.SG", "Symplectic Geometry", "辛几何"),
        ("math.SP", "Spectral Theory", "谱理论"),
        ("math.ST", "Statistics Theory", "统计理论"),
    ]),
    ("astro-ph", "Astrophysics", "天体物理", [
        ("astro-ph.CO", "Cosmology and Nongalactic Astrophysics", "宇宙学与非星系天体物理"),
        ("astro-ph.EP", "Earth and Planetary Astrophysics", "地球与行星天体物理"),
        ("astro-ph.GA", "Astrophysics of Galaxies", "星系天体物理"),
        ("astro-ph.HE", "High Energy Astrophysical Phenomena", "高能天体物理现象"),
        ("astro-ph.IM", "Instrumentation and Methods for Astrophysics", "天体物理仪器与方法"),
        ("astro-ph.SR", "Solar and Stellar Astrophysics", "太阳与恒星天体物理"),
    ]),
    ("cond-mat", "Condensed Matter", "凝聚态物理", [
        ("cond-mat.dis-nn", "Disordered Systems and Neural Networks", "无序系统与神经网络"),
        ("cond-mat.mes-hall", "Mesoscale and Nanoscale Physics", "介观与纳米物理"),
        ("cond-mat.mtrl-sci", "Materials Science", "材料科学"),
        ("cond-mat.other", "Other Condensed Matter", "其他凝聚态物理"),
        ("cond-mat.quant-gas", "Quantum Gases", "量子气体"),
        ("cond-mat.soft", "Soft Condensed Matter", "软凝聚态物理"),
        ("cond-mat.stat-mech", "Statistical Mechanics", "统计力学"),
        ("cond-mat.str-el", "Strongly Correlated Electrons", "强关联电子"),
        ("cond-mat.supr-con", "Superconductivity", "超导"),
    ]),
    ("gr-qc", "General Relativity and Quantum Cosmology", "广义相对论与量子宇宙学", []),
    ("hep-ex", "High Energy Physics - Experiment", "高能物理 - 实验", []),
    ("hep-lat", "High Energy Physics - Lattice", "高能物理 - 格点", []),
    ("hep-ph", "High Energy Physics - Phenomenology", "高能物理 - 唯象", []),
    ("hep-th", "High Energy Physics - Theory", "高能物理 - 理论", []),
    ("math-ph", "Mathematical Physics", "数学物理", []),
    ("nlin", "Nonlinear Sciences", "非线性科学", [
        ("nlin.AO", "Adaptation and Self-Organizing Systems", "适应与自组织系统"),
        ("nlin.CD", "Chaotic Dynamics", "混沌动力学"),
        ("nlin.CG", "Cellular Automata and Lattice Gases", "元胞自动机与格点气体"),
        ("nlin.PS", "Pattern Formation and Solitons", "图案形成与孤子"),
        ("nlin.SI", "Exactly Solvable and Integrable Systems", "精确可解与可积系统"),
    ]),
    ("nucl-ex", "Nuclear Experiment", "核物理 - 实验", []),
    ("nucl-th", "Nuclear Theory", "核物理 - 理论", []),
    ("physics", "Physics", "物理学", [
        ("physics.acc-ph", "Accelerator Physics", "加速器物理"),
        ("physics.ao-ph", "Atmospheric and Oceanic Physics", "大气与海洋物理"),
        ("physics.app-ph", "Applied Physics", "应用物理"),
        ("physics.atm-clus", "Atomic and Molecular Clusters", "原子与分子团簇"),
        ("physics.atom-ph", "Atomic Physics", "原子物理"),
        ("physics.bio-ph", "Biological Physics", "生物物理"),
        ("physics.chem-ph", "Chemical Physics", "化学物理"),
        ("physics.class-ph", "Classical Physics", "经典物理"),
        ("physics.comp-ph", "Computational Physics", "计算物理"),
        ("physics.data-an", "Data Analysis, Statistics and Probability", "数据分析、统计与概率"),
        ("physics.ed-ph", "Physics Education", "物理教育"),
        ("physics.flu-dyn", "Fluid Dynamics", "流体力学"),
        ("physics.gen-ph", "General Physics", "一般物理"),
        ("physics.geo-ph", "Geophysics", "地球物理"),
        ("physics.hist-ph", "History and Philosophy of Physics", "物理学史与物理哲学"),
        ("physics.ins-det", "Instrumentation and Detectors", "仪器与探测器"),
        ("physics.med-ph", "Medical Physics", "医学物理"),
        ("physics.optics", "Optics", "光学"),
        ("physics.plasm-ph", "Plasma Physics", "等离子体物理"),
        ("physics.pop-ph", "Popular Physics", "大众物理"),
        ("physics.soc-ph", "Physics and Society", "物理与社会"),
        ("physics.space-ph", "Space Physics", "空间物理"),
    ]),
    ("quant-ph", "Quantum Physics", "量子物理", []),
    ("q-bio", "Quantitative Biology", "定量生物学", [
        ("q-bio.BM", "Biomolecules", "生物大分子"),
        ("q-bio.CB", "Cell Behavior", "细胞行为"),
        ("q-bio.GN", "Genomics", "基因组学"),
        ("q-bio.MN", "Molecular Networks", "分子网络"),
        ("q-bio.NC", "Neurons and Cognition", "神经元与认知"),
        ("q-bio.OT", "Other Quantitative Biology", "其他定量生物学"),
        ("q-bio.PE", "Populations and Evolution", "种群与演化"),
        ("q-bio.QM", "Quantitative Methods", "定量方法"),
        ("q-bio.SC", "Subcellular Processes", "亚细胞过程"),
        ("q-bio.TO", "Tissues and Organs", "组织与器官"),
    ]),
    ("q-fin", "Quantitative Finance", "定量金融", [
        ("q-fin.CP", "Computational Finance", "计算金融"),
        ("q-fin.EC", "Economics", "经济学"),
        ("q-fin.GN", "General Finance", "一般金融"),
        ("q-fin.MF", "Mathematical Finance", "数学金融"),
        ("q-fin.PM", "Portfolio Management", "投资组合管理"),
        ("q-fin.PR", "Pricing of Securities", "证券定价"),
        ("q-fin.RM", "Risk Management", "风险管理"),
        ("q-fin.ST", "Statistical Finance", "统计金融"),
        ("q-fin.TR", "Trading and Market Microstructure", "交易与市场微观结构"),
    ]),
    ("stat", "Statistics", "统计学", [
        ("stat.AP", "Applications", "应用统计"),
        ("stat.CO", "Computation", "统计计算"),
        ("stat.ME", "Methodology", "统计方法论"),
        ("stat.ML", "Machine Learning", "统计机器学习"),
        ("stat.OT", "Other Statistics", "其他统计学"),
        ("stat.TH", "Statistics Theory", "统计理论"),
    ]),
]


def _build():
    """把声明式的 _ARCHIVES 展开成查询用的索引（import 期一次性完成）。"""
    archives = []
    cats = {}
    for aid, en, zh, items in _ARCHIVES:
        single = not items
        cat_items = list(items) if items else [(aid, en, zh)]
        archives.append({
            "id": aid, "en": en, "zh": zh, "single": single,
            "categories": [{"id": c, "en": e, "zh": z} for c, e, z in cat_items],
        })
        for cid, cen, czh in cat_items:
            cats[cid] = {"id": cid, "en": cen, "zh": czh, "archive": aid,
                         "single": single}
    return tuple(archives), cats


ARCHIVES, CATEGORIES = _build()
ARCHIVE_IDS = tuple(a["id"] for a in ARCHIVES)
TOTAL = len(CATEGORIES)


# ---------------------------------------------------------------- 结构

def split(cat):
    """``cs.DB`` -> ("cs", "DB")；``quant-ph`` -> ("quant-ph", "")。"""
    cat = (cat or "").strip()
    if "." in cat:
        abc, def_ = cat.split(".", 1)
        return abc, def_
    return cat, ""


def archive_of(cat):
    """分类所属的 archive id（未知名时退化为点号前的部分）。"""
    hit = CATEGORIES.get((cat or "").strip())
    return hit["archive"] if hit else split(cat)[0]


def is_known(cat):
    return (cat or "").strip() in CATEGORIES


def label(cat):
    """中文主题名；未知分类原样返回（摘要页宁可显示 ID，也不显示「未命名」）。"""
    hit = CATEGORIES.get((cat or "").strip())
    return hit["zh"] if hit else (cat or "").strip()


def en_name(cat):
    hit = CATEGORIES.get((cat or "").strip())
    return hit["en"] if hit else ""


def archive_label(aid):
    for a in ARCHIVES:
        if a["id"] == aid:
            return a["zh"]
    return aid


def archive_info(aid):
    """按 id 取 archive 定义；不存在返回 None。"""
    for a in ARCHIVES:
        if a["id"] == aid:
            return a
    return None


# ---------------------------------------------------------------- 校验

def suggest(raw, n=3):
    """拼写纠错：同 archive 内按**后缀段**的相似度取近邻。

    为什么只比后缀（def）而不是整个 ID：``cs.`` 这一段所有候选都一样，会让
    ``cs.ZZ`` 与 ``cs.SY`` 也算「六成相似」，给出的建议纯属噪音。比较
    ``ZZ`` / ``SY`` 才能真正区分「打错一个字母」和「根本不是一个词」。
    """
    raw = (raw or "").strip()
    if not raw:
        return []
    import difflib

    abc, suffix = split(raw)
    pool = [c for c, v in CATEGORIES.items() if v["archive"] == abc] or list(CATEGORIES)
    low = raw.lower()
    exact = [c for c in CATEGORIES if c.lower() == low]
    if exact:
        return exact[:n]

    pairs = [((split(c)[1] or c).lower(), c) for c in pool]
    target = (suffix or raw).lower()
    hits = difflib.get_close_matches(target, [k for k, _ in pairs], n=n, cutoff=0.6)
    out = []
    for h in hits:
        for k, c in pairs:
            if k == h and c not in out:
                out.append(c)
                break
    return out


def validate(raw, allow_unknown=False):
    """归一化 + 合法性校验。返回 ``(ok, cat, msg)``。

    ``msg`` 在失败时是给用户看的中文原因（含正确写法/纠错建议），成功时为空串。
    **这是全项目唯一的分类校验入口**：`customize.add_category`、HTTP 接口、
    前端提示都应以它为准，避免三处规则各写一遍而互相漂移。

    ``allow_unknown=True`` 用于「导入别人手改过的 config」这种场景：
    只校验格式，不校验是否在官方表内（历史配置里可能有已下线的分类）。
    """
    cat = (raw or "").strip()
    if not cat:
        return False, "", "分类不能为空"
    cat = re.sub(r"\s+", "", cat)
    # 大小写写错是最常见的手输错误（CS.DB / cs.db），先给出确定的正确写法，
    # 比笼统的「格式不合法」有用得多。
    low = cat.lower()
    for known in CATEGORIES:
        if known.lower() == low and known != cat:
            return False, cat, "arXiv 分类区分大小写，正确写法是 %s" % known
    if not CAT_RE.match(cat):
        return False, cat, ("格式不合法：应为 abc.def（如 cs.DB、math.LO、"
                            "physics.acc-ph），或单段归档（如 quant-ph）")
    if cat in CATEGORIES:
        return True, cat, ""
    if allow_unknown:
        return True, cat, ""
    abc, suffix = split(cat)
    # 「只写了主类」是新手最常见的一次输入（cs / physics）：直接告诉他缺子类，
    # 比笼统地说「不是官方分类」有用得多。
    info = archive_info(abc)
    if info is not None and not suffix and not info["single"]:
        return False, cat, ("%s 是主类（archive），还需要选择子类，例如 %s"
                            % (cat, info["categories"][0]["id"]))
    if abc not in ARCHIVE_IDS:
        # 没有点号的未知 ID 几乎都是「主类打错了」，此时给近邻建议只会添乱
        near = [] if not suffix else suggest(cat)
        hint = ("你是不是指 %s？" % "、".join(near)) if near else \
               "主类（abc）应为 cs / math / physics / stat 等 20 个归档之一"
        return False, cat, "不是 arXiv 官方分类：%s。%s" % (cat, hint)
    near = suggest(cat)
    hint = ("你是不是指 %s？" % "、".join(near)) if near else \
           "请从下拉列表中同 archive 的分类里选择"
    return False, cat, "不是 arXiv 官方分类：%s。%s" % (cat, hint)


# ---------------------------------------------------------------- 检索

def search(q, archive=None, limit=60):
    """按 ID / 英文名 / 中文名模糊匹配，返回分类 dict 列表（有序、去重）。"""
    q = (q or "").strip().lower()
    pool = [v for v in CATEGORIES.values()
            if archive is None or v["archive"] == archive]
    if not q:
        return pool[:limit]

    def hit(v):
        return (q in v["id"].lower() or q in v["en"].lower()
                or q in v["zh"].lower())

    exact = [v for v in pool if v["id"].lower() == q]
    prefix = [v for v in pool if v["id"].lower().startswith(q)]
    rest = [v for v in pool if hit(v)]
    out, seen = [], set()
    for v in exact + prefix + rest:
        if v["id"] in seen:
            continue
        seen.add(v["id"])
        out.append(v)
    return out[:limit]


def taxonomy():
    """JSON 友好的完整快照（前端两个联动下拉框的数据源）。"""
    return {"version": TAXONOMY_VERSION, "source": TAXONOMY_SOURCE,
            "total": TOTAL, "archives": [
                {"id": a["id"], "en": a["en"], "zh": a["zh"], "single": a["single"],
                 "categories": [dict(c) for c in a["categories"]]}
                for a in ARCHIVES]}


# ---------------------------------------------------------------- 邻域

def neighbors(cats, limit=None):
    """「兴趣扩展」的默认候选池：所选分类的**兄弟分类**（同 archive，去掉已选）。

    这是通用化的关键一环：旧实现把扩展池写死成一串 cs.xx，一旦用户选的是
    math 或 q-bio，扩展池就完全对不上了。改为按 archive 推导后，任何领域都成立；
    用户仍可用 config.json 的 `expand_categories` 显式覆盖。
    """
    chosen = [c for c in (cats or []) if c]
    chosen_set = set(chosen)
    order = []
    for c in chosen:
        a = archive_of(c)
        if a not in order:
            order.append(a)
    out = []
    for a in order:
        for v in CATEGORIES.values():
            if v["archive"] == a and v["id"] not in chosen_set:
                out.append(v["id"])
    # 单类 archive（quant-ph 之类）推不出兄弟分类，用全表的相邻 ID 兜底没有意义，
    # 直接返回空 —— 调用方（fetch_expand）会退化为「本轮无扩展」而不是乱抓。
    if limit is not None:
        out = out[:limit]
    return out


def main():
    """``python arxiv_cats.py``：打印分类表概览并做一次自检。"""
    print("arXiv 分类表 %s（来源 %s）" % (TAXONOMY_VERSION, TAXONOMY_SOURCE))
    print("archive %d 个，分类 %d 个\n" % (len(ARCHIVES), TOTAL))
    for a in ARCHIVES:
        ids = [c["id"] for c in a["categories"]]
        print("%-10s %-46s %2d  %s" % (a["id"], a["zh"], len(ids),
                                       "、".join(ids[:4]) + (" …" if len(ids) > 4 else "")))
    bad = [c["id"] for c in CATEGORIES.values() if not CAT_RE.match(c["id"])]
    assert not bad, "分类表里有格式不合法的项：%s" % bad
    print("\n自检通过：%d 个分类号全部匹配 CAT_RE" % TOTAL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
