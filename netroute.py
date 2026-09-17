#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载路由：自动挑一条「真能取到 arXiv」的路（直连 / 环境代理 / 本机代理端口）。

背景（2026-09-14 定位）
----------------------
本机常被注入 ``HTTP_PROXY`` / ``HTTPS_PROXY``（沙箱出口代理，端口每次会话都变）。
它会对 ``arxiv.org`` 完成 CONNECT，却立刻掐断 TLS 流，表现为::

    SSL: UNEXPECTED_EOF_WHILE_READING  EOF occurred in violation of protocol

而直连又被拦（``WinError 10054``）。真正能通的是**本机上另外某个代理端口**
（如 7890）。所以「用默认 opener 直接 urlopen」在两种环境下都会失败 —— 这就是
下载按钮报错的原因。

本模块不写死端口：先试显式配置与直连，再试环境代理，然后枚举本机**正在监听**
的端口逐个探测；命中后缓存（内存 + ``output/netroute.json``），后续下载直接走它；
缓存失效时自动重新探测。

CLI::

    python netroute.py            # 探测并打印可用路由
    python netroute.py --forget   # 清掉缓存重新探测
"""
import argparse
import json
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
CACHE_PATH = os.path.join(OUT, "netroute.json")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) arxiv-digest/2.0"}

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# 探测目标：与真实下载同域同路径，避免「探测能通、下载不通」。
PROBE_URL = "https://arxiv.org/pdf/2601.00001"
PROBE_HOST, PROBE_PORT = "arxiv.org", 443

# 常见本机代理端口（按常见度排序；只有真的在监听才会被采用）。
COMMON_PROXY_PORTS = (7890, 7891, 7897, 8889, 10809, 10808, 1080, 1087,
                      20171, 20172, 8118, 3128, 8080, 8888, 60080)
# 这些端口即便在监听也不当代理试（避免噪声 / 误碰系统服务）。
SKIP_PORTS = {8765, 135, 139, 445, 5040, 1900, 5357, 7680, 49664, 49665,
              49666, 49667, 49668, 49669, 49670, 49671, 49672, 49673, 49674}
MAX_LISTENING_PROBES = 40          # 枚举监听端口时的探测上限
PROBE_BUDGET_S = 30.0              # 整个探测过程的时间预算

_cache = {"proxy": "__unset__", "label": "", "ts": 0.0, "url": "", "dead_ts": 0.0}
CACHE_TTL = 900                    # 秒；过期后仍先用再校验，失败才重探
FAIL_TTL = 45                      # 秒；「全都不通」的负缓存，避免批量下载时反复探测
_listen_cache = {"ts": 0.0, "ports": []}
_last_fail = {"summary": "", "detail": "", "ts": 0.0}

# 把 urllib/ssl 的原始报错翻成人话（原文太吵，不该出现在页面 toast 里）。
_ERR_HINTS = (
    ("UNEXPECTED_EOF_WHILE_READING", "代理掐断 TLS 流（出口代理不可用于 arXiv）"),
    ("10061", "端口未监听"),
    ("10054", "连接被重置"),
    ("10060", "连接超时"),
    ("timed out", "超时"),
    ("timeout", "超时"),
    ("CERTIFICATE_VERIFY_FAILED", "证书校验失败"),
    ("getaddrinfo", "域名解析失败"),
    ("Name or service not known", "域名解析失败"),
    ("Tunnel connection failed", "代理隧道失败"),
    ("502", "代理返回 502"),
    ("407", "代理需要认证"),
    ("Connection refused", "连接被拒绝"),
)


def friendly(err):
    """原始异常 → 短语。"""
    s = str(err)
    for k, v in _ERR_HINTS:
        if k in s:
            return v
    return (s or "未知错误").replace("\n", " ")[:60]


class RouteError(Exception):
    pass


# ---------------------------------------------------------------- 基础

def ssl_context():
    return SSL_CTX


def user_agent():
    return dict(UA)


def build_opener(proxy=None):
    """proxy 为 None → 显式**绕过**环境代理；为 URL 则用它。"""
    handlers = [urllib.request.HTTPSHandler(context=SSL_CTX),
                urllib.request.HTTPHandler()]
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def make_request(url, headers=None):
    h = dict(UA)
    if headers:
        h.update(headers)
    return urllib.request.Request(url, headers=h)


# ---------------------------------------------------------------- 候选路由

def listening_ports(ttl=30.0):
    """本机 127.0.0.1 / 0.0.0.0 上正在监听的端口（netstat 较慢，结果缓存 ttl 秒）。

    批量下载时 `candidates()` 会被反复调用，没有这层缓存会拖慢整个批次。
    """
    if time.time() - _listen_cache["ts"] < ttl and _listen_cache["ports"]:
        return list(_listen_cache["ports"])
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "tcp"],
                             capture_output=True, timeout=10).stdout
    except Exception:
        return list(_listen_cache["ports"])
    ports = set()
    for line in out.decode("gbk", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[3].upper() == "LISTENING":
            addr = parts[1]
            if ":" not in addr:
                continue
            host, _, port = addr.rpartition(":")
            if not port.isdigit():
                continue
            if host in ("127.0.0.1", "0.0.0.0", "[::]", "[::1]", "::"):
                ports.add(int(port))
    _listen_cache.update({"ts": time.time(), "ports": sorted(ports)})
    return sorted(ports)


def _alive(port, timeout=0.25):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def _env_proxy():
    for k in ("ARXIV_DL_PROXY", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = (os.environ.get(k) or "").strip()
        if v:
            if not v.startswith("http"):
                v = "http://" + v
            return v, k
    return "", ""


def candidates(prefer=None):
    """按优先级产出 (proxy_or_None, label)。不重复。

    prefer 可给一个 URL（通常来自缓存），排在最前。
    """
    seen, out = set(), []

    def add(proxy, label):
        key = proxy or "__direct__"
        if key in seen:
            return
        seen.add(key)
        out.append((proxy, label))

    if prefer:
        add(prefer, "缓存 " + prefer.split("//")[-1])

    env, envk = _env_proxy()
    if os.environ.get("ARXIV_DL_PROXY"):
        add(env, "ARXIV_DL_PROXY")
    add(None, "直连")
    if env:
        add(env, "环境代理 %s(%s)" % (env.split("//")[-1], envk))

    live = [p for p in listening_ports() if p not in SKIP_PORTS]
    live_set = set(live)
    for p in COMMON_PROXY_PORTS:
        if p in live_set:
            add("http://127.0.0.1:%d" % p, "本机代理 :%d" % p)
    used = {p for p in COMMON_PROXY_PORTS}
    n = 0
    for p in live:
        if p in used or p >= 65535:
            continue
        if not _alive(p):
            continue
        add("http://127.0.0.1:%d" % p, "本机端口 :%d" % p)
        n += 1
        if n >= MAX_LISTENING_PROBES:
            break
    return out


# ---------------------------------------------------------------- 路由探测

def _from_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("proxy") or d.get("proxy") is None:
            return d.get("proxy"), d.get("label", ""), float(d.get("ts") or 0)
    except Exception:
        pass
    return "__unset__", "", 0.0


def _to_cache(proxy, label, url):
    _cache.update({"proxy": proxy, "label": label, "ts": time.time(), "url": url,
                   "dead_ts": 0.0})
    try:
        os.makedirs(OUT, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"proxy": proxy, "label": label, "ts": _cache["ts"],
                       "url": url}, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def forget():
    _cache.update({"proxy": "__unset__", "label": "", "ts": 0.0, "url": "",
                   "dead_ts": 0.0})
    _listen_cache.update({"ts": 0.0, "ports": []})
    try:
        os.remove(CACHE_PATH)
    except OSError:
        pass


def _looks_like_pdf(head, total_len=None):
    if head.startswith(b"%PDF"):
        return True
    if total_len is None:
        return len(head) > 8 and not head[:1] in (b"<", b"{")
    return not (len(head) < 5000 and not head.startswith(b"%PDF"))


def note_ok(proxy, label):
    _to_cache(proxy, label, PROBE_URL)


def probe(prefer=None, timeout=12.0, log=False):
    """逐个路由试探，命中即缓存并返回 (proxy, label)；全失败返回 (None, '')。"""
    t0 = time.time()
    last_errs = []
    for proxy, label in candidates(prefer=prefer):
        if time.time() - t0 > PROBE_BUDGET_S:
            last_errs.append("探测超预算 %.0fs" % PROBE_BUDGET_S)
            break
        try:
            with build_opener(proxy).open(make_request(PROBE_URL), timeout=timeout) as r:
                head = r.read(8)
            if not head.startswith(b"%PDF"):
                last_errs.append("%s: 非 PDF 响应 %r" % (label, head[:16]))
                continue
            _to_cache(proxy, label, PROBE_URL)
            if log:
                print("[netroute] 选中：%s（%.2fs）" % (label, time.time() - t0))
            return proxy, label
        except Exception as e:
            last_errs.append("%s: %s" % (label, friendly(e)))
            if log:
                print("[netroute] %-24s 不可用：%s" % (label, friendly(e)))
    _cache["dead_ts"] = time.time()      # 负缓存：短时间内不再重复全量探测
    if log:
        print("[netroute] 无可用路由：")
        for e in last_errs:
            print("   ", e)
    return None, ""


def ensure_route(force=False, log=False):
    """返回可用路由的 (proxy, label)；必要时重新探测。"""
    if not force:
        # 负缓存：刚全量探测过且都不通，短时间内别再折腾（批量下载会调用很多次）
        if _cache.get("dead_ts") and time.time() - _cache["dead_ts"] < FAIL_TTL:
            return None, ""
        cproxy, clabel, ts = _from_cache()
        if cproxy != "__unset__" and time.time() - ts < CACHE_TTL:
            _cache.update({"proxy": cproxy, "label": clabel, "ts": ts})
            return cproxy, clabel
        if cproxy != "__unset__":
            # 缓存过期：先按它试一次，失败再重探
            try:
                with build_opener(cproxy).open(make_request(PROBE_URL), timeout=8) as r:
                    if r.read(8).startswith(b"%PDF"):
                        _cache.update({"proxy": cproxy, "label": clabel, "ts": time.time()})
                        return cproxy, clabel
            except Exception:
                pass
        elif _cache["proxy"] != "__unset__":
            return _cache["proxy"], _cache["label"]
    return probe(log=log)


# ---------------------------------------------------------------- 取数

def fetch_first(urls, timeout=60, log=False):
    """按「缓存路由 → 其它候选路由」×「候选 URL」逐个尝试，返回 (data, label, url)。

    全部失败抛 RouteError：消息是**人话摘要**（去重、最多 4 条），完整细节进
    `netroute.last_failure()`，可在 /api/net_route 里看到 —— 别把 SSL 原文丢给用户。
    """
    if isinstance(urls, str):
        urls = [urls]
    if _cache.get("dead_ts") and time.time() - _cache["dead_ts"] < FAIL_TTL \
            and _last_fail["summary"]:
        raise RouteError(_last_fail["summary"])     # 负缓存内直接失败，不重复试探
    cproxy, clabel = ensure_route(log=log)
    order = candidates(prefer=cproxy if clabel else None)
    seen, pairs, raw = set(), [], []
    for url in urls:
        for proxy, label in order:
            try:
                with build_opener(proxy).open(make_request(url), timeout=timeout) as r:
                    data = r.read()
                if not data.startswith(b"%PDF") and len(data) < 5000:
                    raise ValueError("返回的不是 PDF（前 %d 字节：%r）" % (len(data), data[:60]))
                if (proxy or None) != (cproxy or None):
                    note_ok(proxy, label)
                return data, label, url
            except Exception as e:
                raw.append("%s → %s: %s" % (label, url.split("/")[-1][:28], str(e)[:120]))
                key = (label, friendly(e))
                if key not in seen:
                    seen.add(key)
                    pairs.append("%s：%s" % key)
                if log:
                    print("[netroute] %-22s %s 失败：%s"
                          % (label, url.split("/")[-1][:24], friendly(e)))
    summary = "；".join(pairs[:4]) or "无可用网络路由"
    _last_fail.update({"summary": summary, "detail": " | ".join(raw[-6:]),
                       "ts": time.time()})
    if log:
        print("[netroute] 全部路由失败：%s" % summary)
    raise RouteError(summary)


def last_failure():
    return dict(_last_fail)


def pdf_urls(sid, primary=None):
    """候选 PDF 地址：元数据里的地址优先，再补两个稳定兜底入口。"""
    out = []
    for u in (primary, "https://arxiv.org/pdf/%s" % sid,
              "https://export.arxiv.org/pdf/%s" % sid):
        if not u:
            continue
        if u.startswith("http://"):
            u = "https://" + u[len("http://"):]
        if u not in out:
            out.append(u)
    return out


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description="arXiv 下载路由探测")
    ap.add_argument("--forget", action="store_true", help="清掉缓存后重新探测")
    ap.add_argument("--quick", action="store_true", help="只列出候选，不实际探测")
    a = ap.parse_args()
    if a.forget:
        forget()
        print("已清除路由缓存", CACHE_PATH)
    cands = candidates()
    print("候选路由（%d 条）：" % len(cands))
    for proxy, label in cands:
        print("  %-28s %s" % (label, proxy or "（不用代理）"))
    if a.quick:
        return 0
    proxy, label = ensure_route(force=a.forget, log=True)
    if label:
        print("\n结论：可用路由 = %s" % label)
        print("缓存已写入 %s" % CACHE_PATH)
        return 0
    print("\n结论：未找到可用路由")
    return 1


if __name__ == "__main__":
    sys.exit(main())
