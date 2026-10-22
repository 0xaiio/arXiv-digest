# -*- coding: utf-8 -*-
"""测试基础设施：把整条链路重定向到一个临时沙箱。

为什么必须这么做
----------------
项目里 9 个模块在**导入时**就把路径固化成了模块级常量：

    paperutil.OUT / CONFIG_PATH / LIB_PATH
    customize.INTERESTS / EXTRA_PATH
    profile.OUT / PROFILE_PATH / BEHAVIOR_PATH
    archive.OUT / DB_PATH / ARCHIVE_DIR
    recommend.OUT        build_report.OUT        server.OUT        netroute.CACHE_PATH
    datapack.PACKS       （真实 presets/ 里有作者本人的画像，测试绝不能读到）

直接跑测试会写进真实的 output/、改写真实的 interests.json —— 那是不可接受的。
`sandbox` fixture 把这些常量逐个改用 monkeypatch 指向一次性目录，测试结束自动还原。

沙箱目录放在项目内 `tmp_pytest/`，**从不删除**：本机沙箱对删除是累积计数拦截的，
删除会连带拒掉整条 pytest 命令（见 pytest.ini 的注释）。
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import archive as AR          # noqa: E402
import build_report as B      # noqa: E402
import customize as CZ        # noqa: E402
import datapack as DP         # noqa: E402
import fetch_affil as FA      # noqa: E402
import fetch_rss as FR        # noqa: E402
import netroute as NR         # noqa: E402
import paperutil as pu        # noqa: E402
import profile as PF          # noqa: E402
import recommend as R         # noqa: E402
import run_daily as RD        # noqa: E402
import server as S            # noqa: E402

TMP_ROOT = ROOT / "tmp_pytest"


def _fresh_dir(tag):
    """每次调用都拿到一个**全新**目录。

    为什么不用 `tag-pid-序号`：沙箱对删除是累积拦截的，这些目录只会越攒越多；
    而 pid 会被系统复用 —— 上一轮 `<tag>-12345-001` 里留下的 config/archive/language
    会被下一轮的同一路径**继承**，表现为一批与本用例无关的断言失败
    （2026-10-22 实测：完整套件 13 个用例随机红，单跑却全绿）。
    `mkdtemp` 只建不删，也不与历史目录重名。
    """
    TMP_ROOT.mkdir(exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="%s-" % tag, dir=str(TMP_ROOT)))
    (d / "output").mkdir(parents=True, exist_ok=True)
    return d


class Sandbox:
    """一次测试的隔离工作区。"""

    def __init__(self, root):
        self.root = root
        self.out = root / "output"
        self.cfg = root / "config.json"
        self.interests = root / "interests.json"
        self.download_dir = root / "papers"
        self.packs = root / "presets"

    # ---- 便捷写入 ----
    def write(self, name, obj):
        p = self.out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        return p

    def make_pack(self, name, files=None, manifest=None):
        """在沙箱里造一个数据包（files = {文件名: Python 对象}）。"""
        d = self.packs / name
        d.mkdir(parents=True, exist_ok=True)
        for fname, obj in (files or {}).items():
            (d / fname).write_text(json.dumps(obj, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        if manifest is not None:
            (d / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        return d

    def read(self, name):
        return json.loads((self.out / name).read_text(encoding="utf-8"))

    def exists(self, name):
        return (self.out / name).exists()

    def set_profile(self, **kw):
        """改写画像（interests.json），未给出的键保持模板原值。"""
        d = json.loads(self.interests.read_text(encoding="utf-8"))
        d.update(kw)
        self.interests.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        return d

    def profile(self):
        return json.loads(self.interests.read_text(encoding="utf-8"))

    def set_config(self, **kw):
        d = json.loads(self.cfg.read_text(encoding="utf-8"))
        d.update(kw)
        self.cfg.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        return d

    def config(self):
        return json.loads(self.cfg.read_text(encoding="utf-8"))

    def library(self):
        return pu.load_library()


# 每个模块在 import 时就把 OUT 复制成了模块级常量。少打一个，测试就会写进真实的
# output/ —— 这不是假设：`fetch_rss.OUT` 曾被漏掉，测试直接把真实抓取池重写了一遍。
# 因此这里集中登记，并在最后断言「一个都不许漏」。
_OUT_OWNERS = [pu, PF, AR, R, B, RD, S, NR, FR, FA, DP]


def _redirect(monkeypatch, sb):
    """把所有模块级路径常量指向沙箱，并校验隔离完整。"""
    monkeypatch.setattr(pu, "OUT", str(sb.out))
    monkeypatch.setattr(pu, "CONFIG_PATH", str(sb.cfg))
    monkeypatch.setattr(pu, "LIB_PATH", str(sb.out / "library.json"))

    monkeypatch.setattr(CZ, "INTERESTS", str(sb.interests))
    monkeypatch.setattr(CZ, "EXTRA_PATH", str(sb.out / "interests_extra.json"))

    monkeypatch.setattr(PF, "OUT", str(sb.out))
    monkeypatch.setattr(PF, "PROFILE_PATH", str(sb.out / "profile_state.json"))
    monkeypatch.setattr(PF, "BEHAVIOR_PATH", str(sb.out / "behavior.json"))
    monkeypatch.setattr(PF, "INTERESTS", str(sb.interests))

    monkeypatch.setattr(AR, "OUT", str(sb.out))
    monkeypatch.setattr(AR, "DB_PATH", str(sb.out / "archive.db"))
    monkeypatch.setattr(AR, "ARCHIVE_DIR", str(sb.out / "archive"))

    monkeypatch.setattr(R, "OUT", str(sb.out))
    monkeypatch.setattr(B, "OUT", str(sb.out))
    monkeypatch.setattr(RD, "OUT", str(sb.out))
    monkeypatch.setattr(S, "OUT", str(sb.out))
    monkeypatch.setattr(FR, "OUT", str(sb.out))
    monkeypatch.setattr(FA, "OUT", str(sb.out))
    monkeypatch.setattr(FA, "AFF_PATH", str(sb.out / "affiliations.json"))
    monkeypatch.setattr(NR, "OUT", str(sb.out))
    monkeypatch.setattr(NR, "CACHE_PATH", str(sb.out / "netroute.json"))

    # 数据包根目录：测试里绝不允许读到真实的 presets/（里面有作者本人的画像）
    sb.packs.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(DP, "PACKS", str(sb.packs))

    # 模块内缓存也要清，否则上一个测试的数据会漏进来。
    # 论文索引缓存已下沉到 service.PaperIndex（类实例，有显式 reset），
    # 不能再靠 monkeypatch 模块级 dict —— 那只会替换 server 的一个没人读的别名。
    S.reset_papers()
    monkeypatch.setattr(B, "AFF", {}, raising=False)

    assert_isolated(sb)


def assert_isolated(sb):
    """硬断言：所有模块的 OUT / 路径常量都必须落在本测试的沙箱里。"""
    root = str(sb.root)
    bad = []
    for mod in _OUT_OWNERS:
        for attr in ("OUT", "CONFIG_PATH", "LIB_PATH", "INTERESTS", "EXTRA_PATH",
                     "PROFILE_PATH", "BEHAVIOR_PATH", "DB_PATH", "ARCHIVE_DIR",
                     "CACHE_PATH", "PACKS"):
            v = getattr(mod, attr, None)
            if isinstance(v, str) and v and not v.startswith(root):
                bad.append("%s.%s=%s" % (mod.__name__, attr, v))
    assert not bad, "以下常量未指向沙箱，测试会污染真实数据：%s" % ", ".join(bad)


@pytest.fixture()
def sandbox(monkeypatch):
    """带「模板已就位」的沙箱：config.json + interests.json 已按 *.example.json 生成。"""
    sb = Sandbox(_fresh_dir("case"))
    shutil.copy(ROOT / "config.example.json", sb.cfg)
    shutil.copy(ROOT / "interests.example.json", sb.interests)
    _redirect(monkeypatch, sb)
    return sb


@pytest.fixture()
def bare_sandbox(monkeypatch):
    """干净沙箱：**没有任何配置文件**，用于验证首次初始化行为。"""
    sb = Sandbox(_fresh_dir("bare"))
    _redirect(monkeypatch, sb)
    return sb


# ---------------------------------------------------------------- 数据工厂

_TOPIC_CACHE = {"seq": 0}


@pytest.fixture()
def make_paper():
    """构造一篇 arXiv 论文（字段与 fetch_arxiv.parse 的输出一致）。"""

    def _make(sid="2609.00001", title="A Paper", abstract="",
              authors=("Ada Lovelace",), published="2026-10-15T00:00:00Z",
              primary="cs.DB", cats=("cs.DB",), **extra):
        p = {
            "id": "http://arxiv.org/abs/%sv1" % sid,
            "title": title,
            "abstract": abstract,
            "authors": list(authors),
            "published": published,
            "updated": published,
            "primary": primary,
            "cats": list(cats),
            "pdf": "https://arxiv.org/pdf/%s" % sid,
            "comment": "",
            "queried_cat": primary,
        }
        p.update(extra)
        return p

    return _make


@pytest.fixture()
def pool(make_paper):
    """默认数据集：3 篇核心 + 2 篇扩展，主题关键词与「强相关/弱相关」可控。

    readable 主题命中情况（默认画像，见 sandbox_interests）：
      p1 标题含 isolation level / serializability → 强命中 T1
      p2 摘要含 linearizability              → 弱命中 T2
      p3 无关（区块链）                        → 无命中
    """

    def _pool():
        core = [
            make_paper("2609.10001", "Isolation Level Selection for Serializable Transactions",
                       "We study isolation level and serializability in transactional databases "
                       "with linearizability guarantees.",
                       authors=("Ada Lovelace", "Alan Turing")),
            make_paper("2609.10002", "A Study of Consensus Protocols",
                       "We revisit linearizability of consensus protocols under partitions.",
                       authors=("Grace Hopper",)),
            make_paper("2609.10003", "Blockchain Consensus for Digital Assets",
                       "A survey of blockchain consensus and cryptocurrency incentives.",
                       authors=("Satoshi Nakamoto",)),
        ]
        expand = [
            make_paper("2610.20001", "Refinement Types for Distributed Protocols",
                       "Refinement types and formal verification for distributed protocols.",
                       primary="cs.PL", cats=("cs.PL", "cs.LO"),
                       authors=("Barbara Liskov",)),
            make_paper("2610.20002", "Graph Neural Networks for Molecules",
                       "We train graph neural networks on molecular datasets.",
                       primary="cs.LG", cats=("cs.LG",), authors=("Yann LeCun",)),
        ]
        core_doc = {"generated_at": "2026-10-15T08:00:00+08:00",
                    "newest_seen": "2026-10-15", "cutoff": "2026-10-12",
                    "window_days": 3, "categories": ["cs.DB"], "papers": core}
        exp_doc = dict(core_doc, categories=["cs.PL", "cs.LG"], papers=expand)
        return core_doc, exp_doc

    return _pool


@pytest.fixture()
def seeded(sandbox, pool):
    """沙箱 + 已写入两个抓取池，并把画像配成「事务 / 一致性」两个主题。"""
    core_doc, exp_doc = pool()
    sandbox.write("raw.json", core_doc)
    sandbox.write("raw_expand.json", exp_doc)
    sandbox.set_profile(
        topics=[
            {"name": "事务与隔离级别",
             "weight": 1.5,
             "keywords": ["isolation level", "serializability", "transaction"]},
            {"name": "一致性模型",
             "weight": 1.0,
             "keywords": ["linearizability", "consistency model"]},
        ],
        people=["Ada Lovelace"],
        signature_systems=["RocksDB"],
        negative={"weight": -1.0, "keywords": ["blockchain"]},
        owners=[{"name": "Ada Lovelace", "label": "Ada", "site": "https://example.org",
                 "affiliation": "Analytical Engine Lab", "interests": "程序化推理",
                 "signature_topics": ["分析机"], "people_linked": True}],
    )
    sandbox.set_config(categories=["cs.DB"], top_recommend=3, top_expand=2,
                       download_dir=str(sandbox.download_dir))
    return sandbox


# ---------------------------------------------------------------- 服务

@pytest.fixture()
def live_server(sandbox):
    """在随机端口起真实的 ThreadingHTTPServer（与生产同一套 Handler）。

    起好后把端口写回 config：页面里的 APIBASE 由 config.port 决定，
    若两者不一致，前端请求会打到别的端口 —— 表现就是「点了按钮被回滚」。
    """
    import threading
    from http.server import ThreadingHTTPServer

    srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
    port = srv.server_address[1]
    sandbox.set_config(port=port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield port
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


@pytest.fixture()
def http(live_server):
    """极简 HTTP 客户端：绕开环境代理（否则 127.0.0.1 会被拦成 502）。"""
    import urllib.error
    import urllib.request

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    class Client:
        base = "http://127.0.0.1:%d" % live_server

        def get(self, path, **kw):
            req = urllib.request.Request(self.base + path, **kw)
            try:
                with opener.open(req, timeout=10) as r:
                    return r.status, r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode("utf-8", "replace")

        def get_json(self, path):
            code, body = self.get(path)
            return code, json.loads(body)

        def post(self, path, payload=None):
            data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                self.base + path, data=data,
                headers={"Content-Type": "application/json"}, method="POST")
            try:
                with opener.open(req, timeout=20) as r:
                    return r.status, json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read().decode("utf-8") or "{}")

        def options(self, path):
            req = urllib.request.Request(self.base + path, method="OPTIONS")
            with opener.open(req, timeout=10) as r:
                return r.status, dict(r.headers)

    return Client()
