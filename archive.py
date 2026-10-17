#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日报归档存储层（SQLite）。

为什么要它：`raw.json` / `raw_expand.json` 是**累积池**（RSS 降级通道按短号增量合并，
永不删除既有条目），于是每天的日报都会把前几天的高分论文再推一遍。用户要求
「每天只呈现当天最新内容，历史内容存档、可按日期回看」，本模块提供判定依据与存档库：

  seen         每个短号首次出现的期次 —— 判定「本期新增」的唯一依据
  issues       每期一条：日期 / 生成时间 / 新增篇数 / 推荐篇数 / 快照文件
  issue_papers 每期展示过的论文（含分数、层级、摘要、单位），供归档页与检索

数据库：output/archive.db（SQLite，stdlib，无外部依赖）
快照：  output/archive/<YYYYMMDD>.html / .md（自包含，可直接静态打开，也可由服务同源提供）
"""
import json
import os
import shutil
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paperutil as pu  # noqa: E402
import paths  # noqa: E402

OUT = pu.OUT
DB_PATH = paths.ARCHIVE_DB_PATH
ARCHIVE_DIR = paths.ARCHIVE_DIR

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
  sid        TEXT PRIMARY KEY,
  first_date TEXT NOT NULL,
  first_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS issues (
  date         TEXT PRIMARY KEY,          -- YYYYMMDD
  generated_at TEXT,
  newest_seen  TEXT,                      -- 本期抓到的最新提交日
  n_new        INTEGER DEFAULT 0,         -- 本期新增论文数（核心+扩展）
  n_core       INTEGER DEFAULT 0,         -- 本期核心（六分类）论文数
  n_rec        INTEGER DEFAULT 0,         -- 本期推荐数
  n_exp        INTEGER DEFAULT 0,         -- 本期兴趣扩展数
  html         TEXT,                      -- 快照文件名
  md           TEXT,
  created_at   TEXT
);
CREATE TABLE IF NOT EXISTS issue_papers (
  date      TEXT NOT NULL,
  sid       TEXT NOT NULL,
  pool      TEXT,                          -- core / expand / archive
  is_new    INTEGER DEFAULT 0,
  prim      TEXT,                          -- 主分类（避开 SQLite 保留字 primary）
  title     TEXT,
  authors   TEXT,
  published TEXT,
  score     REAL,
  tier      TEXT,
  summary   TEXT,
  note      TEXT,
  topics    TEXT,
  affil     TEXT,
  pdf       TEXT,
  PRIMARY KEY (date, sid)
);
CREATE INDEX IF NOT EXISTS idx_ip_date ON issue_papers(date);
CREATE INDEX IF NOT EXISTS idx_ip_sid  ON issue_papers(sid);
"""


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def connect():
    os.makedirs(OUT, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    return c


def init():
    with connect() as c:
        c.executescript(_SCHEMA)
    return DB_PATH


def exists():
    return os.path.exists(DB_PATH)


# ------------------------------------------------------------ 本期新增判定

def known_sids():
    """已出现过的短号 -> 首次期次（seen 表）。DB 不存在时返回空 dict。"""
    if not exists():
        return {}
    try:
        with connect() as c:
            return {r[0]: r[1] for r in c.execute("SELECT sid, first_date FROM seen")}
    except Exception:
        return {}


def mark_seen(sids, date):
    """把这些短号记为「已在 date 这期呈现过」；已存在的保持首次期次不变。"""
    sids = [s for s in sids if s]
    if not sids:
        return 0
    init()
    now = _now()
    n = 0
    with connect() as c:
        for s in sids:
            cur = c.execute(
                "INSERT OR IGNORE INTO seen(sid, first_date, first_at) VALUES(?,?,?)",
                (s, date, now))
            n += cur.rowcount
    return n


def filter_new(papers, date, bootstrap_date=None):
    """把一组论文切成 (本期新增, 历史)；判定规则见 filter_issues。"""
    new, old, _ = _split(papers, known_sids(), date, bootstrap_date)
    return new, old


def _split(papers, known, date, bootstrap_date):
    """按 seen 判定；known 为空时返回 (None, papers, 'bootstrap-needed')。"""
    if known:
        new = [p for p in papers if known.get(pu.short_id(p)) in (None, date)]
        old = [p for p in papers if known.get(pu.short_id(p)) not in (None, date)]
        return new, old, "seen"
    return None, list(papers), "bootstrap"


def filter_issues(core_papers, exp_papers, date, bootstrap_date=None):
    """一次性判定核心池与扩展池的本期新增。

    返回 (new_core, new_exp, mode)。**核心与扩展必须一起判定**：若分两次调用，
    第一次调用已把核心的历史论文写进 seen，第二次调用就会跳过 bootstrap 分支，
    让扩展池里所有「未见过」的论文（首次启用时可达上千篇）都算本期新增。

    mode = "seen"（按归档记录判定）或 "bootstrap"（首次启用，按提交日判定）。
    """
    known = known_sids()
    nc, oc, mode = _split(core_papers, known, date, bootstrap_date)
    ne, oe, _ = _split(exp_papers, known, date, bootstrap_date)

    if mode != "bootstrap":
        return nc, ne, "seen"

    # 首次启用：按提交日判定；非本期的论文按各自提交日一次性记为历史。
    # first_date 必须用其自身提交日——写成今天的话，明天它们又会被当成新增。
    nc, ne = [], []
    buckets = {}
    for p in core_papers + exp_papers:
        d = (p.get("published") or "")[:10]
        if bootstrap_date and d == bootstrap_date:
            (nc if p in core_papers else ne).append(p)
        else:
            buckets.setdefault(d.replace("-", "") or "00000000", []).append(pu.short_id(p))
    for d, sids in buckets.items():
        mark_seen(sids, d)
    return nc, ne, "bootstrap"


# ------------------------------------------------------------ 期次读写

def record_issue(date, html=None, md=None, generated_at=None, newest_seen=None,
                 papers=None, n_core=0, n_new=0, n_rec=0, n_exp=0, replace=True):
    """写一期档案。papers = [{sid, pool, is_new, primary, title, authors, published,
    score, tier, summary, note, topics, affil, pdf}]"""
    init()
    with connect() as c:
        if replace:
            c.execute("DELETE FROM issue_papers WHERE date=?", (date,))
        c.execute(
            "INSERT INTO issues(date, generated_at, newest_seen, n_new, n_core, n_rec, n_exp,"
            " html, md, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(date) DO UPDATE SET generated_at=excluded.generated_at,"
            " newest_seen=excluded.newest_seen, n_new=excluded.n_new, n_core=excluded.n_core,"
            " n_rec=excluded.n_rec, n_exp=excluded.n_exp, html=excluded.html, md=excluded.md,"
            " created_at=excluded.created_at",
            (date, generated_at or "", newest_seen or "", int(n_new), int(n_core),
             int(n_rec), int(n_exp), html or "", md or "", _now()))
        rows = []
        for p in (papers or []):
            rows.append((
                date, p.get("sid") or p.get("id") or "", p.get("pool") or "core",
                1 if p.get("is_new") else 0, p.get("primary") or "", p.get("title") or "",
                _authors(p.get("authors")), (p.get("published") or "")[:10],
                p.get("score"), p.get("tier") or "", p.get("summary") or "",
                p.get("note") or "", _topics(p.get("topics")), p.get("affil") or "",
                p.get("pdf") or ""))
        c.executemany(
            "INSERT OR REPLACE INTO issue_papers(date, sid, pool, is_new, prim, title,"
            " authors, published, score, tier, summary, note, topics, affil, pdf)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def _authors(a):
    if isinstance(a, (list, tuple)):
        return ", ".join(str(x) for x in a[:6])
    return a or ""


def _topics(t):
    if isinstance(t, (list, tuple)):
        return "、".join(str(x) for x in t[:4])
    return t or ""


def list_issues(limit=None):
    if not exists():
        return []
    with connect() as c:
        rows = c.execute(
            "SELECT date, generated_at, newest_seen, n_new, n_core, n_rec, n_exp, html, md,"
            " created_at FROM issues ORDER BY date DESC").fetchall()
    out = [dict(r) for r in rows]
    return out[:limit] if limit else out


def get_issue(date):
    if not exists():
        return None
    with connect() as c:
        r = c.execute("SELECT * FROM issues WHERE date=?", (str(date),)).fetchone()
    return dict(r) if r else None


def get_papers(date, pool=None, only_new=False):
    if not exists():
        return []
    sql = "SELECT * FROM issue_papers WHERE date=?"
    args = [str(date)]
    if pool:
        sql += " AND pool=?"
        args.append(pool)
    if only_new:
        sql += " AND is_new=1"
    sql += " ORDER BY (score IS NULL), score DESC"
    with connect() as c:
        rows = [dict(r) for r in c.execute(sql, args)]
    for r in rows:                       # 对外统一用 primary 这个名字
        r["primary"] = r.pop("prim", "")
    return rows


def latest_issue():
    iss = list_issues(limit=1)
    return iss[0] if iss else None


# ------------------------------------------------------------ 快照归档

def archive_digest(date, html_path, md_path=None):
    """把当期 html/md 复制到 output/archive/，返回 (html_name, md_name)。

    复制而非移动：output/arxiv_digest_<date>.html 仍是最新一期的主入口，
    归档副本只增不改，保证「历史浏览器」看到的是当时那一版。
    """
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    hname = mname = ""
    if html_path and os.path.exists(html_path):
        hname = "%s.html" % date
        shutil.copy2(html_path, os.path.join(ARCHIVE_DIR, hname))
    if md_path and os.path.exists(md_path):
        mname = "%s.md" % date
        shutil.copy2(md_path, os.path.join(ARCHIVE_DIR, mname))
    return hname, mname


def snapshot_path(date, ext="html"):
    """返回某期快照路径：优先 output/archive/<date>.html，其次当期主文件。"""
    date = str(date)
    p = os.path.join(ARCHIVE_DIR, "%s.%s" % (date, ext))
    if os.path.exists(p):
        return p
    p2 = os.path.join(OUT, "arxiv_digest_%s.%s" % (date, ext))
    return p2 if os.path.exists(p2) else None


def available_dates():
    """磁盘上存在快照的日期（合并 DB 与目录扫描，兼容未入库的历史文件）。"""
    ds = set()
    for iss in list_issues():
        ds.add(iss["date"])
    if os.path.isdir(ARCHIVE_DIR):
        for f in os.listdir(ARCHIVE_DIR):
            if f.endswith(".html"):
                ds.add(f[:-5])
    for f in os.listdir(OUT) if os.path.isdir(OUT) else []:
        if f.startswith("arxiv_digest_") and f.endswith(".html"):
            ds.add(f[len("arxiv_digest_"):-len(".html")])
    return sorted(ds, reverse=True)


def stats():
    if not exists():
        return {"issues": 0, "papers": 0, "days": 0}
    with connect() as c:
        n1 = c.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
        n2 = c.execute("SELECT COUNT(*) FROM issue_papers").fetchone()[0]
    return {"issues": n1, "papers": n2, "days": len(available_dates())}


if __name__ == "__main__":
    pu_now = json.dumps({
        "db": DB_PATH,
        "archive_dir": ARCHIVE_DIR,
        "stats": stats(),
        "dates": available_dates()[:20],
    }, ensure_ascii=False, indent=1)
    print(pu_now)
