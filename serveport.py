#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地服务的「怎么暴露」：选端口、开浏览器、把结果落盘。

为什么单独一个模块
------------------
「端口被占用就顺延」这件事有三个入口：`server.py` 自己（用户直接跑 / 双击
`start_digest.bat`）、`run_daily.py`（后台拉起服务后要轮询就绪）、以及测试。
三处各写一遍 try/except 的话，行为必然漂移 —— 一处顺延、一处硬失败，用户看到
的就是「双击能开、定时任务开不了」。端口解析、占用探测、浏览器开关都在这里收敛
成一份实现，两个入口只负责调用。

设计约束
--------
1. **只用标准库**（运行期零依赖）；
2. **不做缓存、不持全局状态**：每次调用都重新探测，否则「刚才还空着」的快照会骗人；
3. **不认识 HTTP、不 import 业务模块**：本模块可以被 server / run_daily / 测试任意引用，
   也算最底层的一份子（与 paths.py 同级）。

两个与平台有关的坑
------------------
* Windows 的 `SO_REUSEADDR` 语义与 POSIX 不同：第二个 socket 带上它去 bind 一个
  已监听的端口**可能成功**（端口劫持）。因此「占用」的判据不能只看 bind，必须先
  做一次 connect 探测：能连上 = 有进程在监听 = 不能用；
* 反过来，TIME_WAIT 的遗留连接不影响 `SO_REUSEADDR` 绑定，所以「刚 Ctrl-C 完
  立刻重启」不会被误判成占用（connect 探测对 TIME_WAIT 是无响应的）。
"""
import json
import os
import re
import socket
import threading
import time
import webbrowser

DEFAULT_PORT = 8765
MAX_PORT = 65535
# 连续尝试多少个端口就放弃：20 个足够躲开「8765 被别的软件占着」的常见情况，
# 又不会在真的没端口时把 6 万次 bind 试一遍。
SCAN_LIMIT = 20
HOST = "127.0.0.1"


# ---------------------------------------------------------------- 取值的解析与校验

def valid_port(value):
    """把任意输入（配置值 / 命令行 / 环境变量）解析成合法端口；非法返回 None。

    合法范围是 1–65535。`0` 刻意视为非法：它表示「让内核随便挑」，只应出现在
    测试里，不是用户能配置的东西。
    """
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= MAX_PORT else None


def configured_port(cfg=None, default=DEFAULT_PORT):
    """从配置字典取端口；缺失或非法都回落到默认值（绝不抛异常）。"""
    port = valid_port((cfg or {}).get("port"))
    return port if port else default


def url_for(port):
    """把一个端口拼成可直接访问的本地地址。"""
    return "http://%s:%d" % (HOST, int(port))


# ---------------------------------------------------------------- 占用探测与顺延

def port_in_use(port, host=HOST, timeout=0.2):
    """有进程在 `host:port` 上监听吗？

    用 connect 而不是只看 bind：Windows 下 `SO_REUSEADDR` 允许第二个 socket 绑上
    已被监听的端口，只看 bind 会把「已被占用」误判成「可用」。connect 成功即说明
    对端真的在监听；TIME_WAIT 的连接不会应答，因此不影响「重启即用」。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((host, int(port))) == 0
    except OSError:
        return False
    finally:
        sock.close()


def can_bind(port, host=HOST):
    """本进程能在这个端口上 bind 吗（与 HTTPServer 一样带 SO_REUSEADDR）。

    这一层用来兜住 connect 探测看不到的情况：地址不属于本机、端口被独占式占用、
    IPv4 地址族不可用等。任一异常都算「不可用」，不往外抛。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def usable(port, host=HOST):
    """端口现在就能拿来起服务吗（先看有没有人在听，再看能不能绑）。"""
    return not port_in_use(port, host) and can_bind(port, host)


def find_free_port(start=None, limit=SCAN_LIMIT, host=HOST):
    """从 `start` 起向后找第一个可用端口。

    返回 ``(port, tried)``：找到时 port 是整数；找不到时是 None，`tried` 列出所有
    试过的端口 —— 调用方据此打印「试了 8765–8784 都被占用」这种可行动的提示，
    而不是让用户面对一个裸的 OSError。

    边界：起点必须合法（非法则回落到 DEFAULT_PORT）；越过 65535 立即停止，
    不会绕回 1（绕回会让「端口耗尽」变成「偷偷占用一个低端口」）。
    """
    start = valid_port(start) or DEFAULT_PORT
    tried = []
    for port in range(start, min(start + limit - 1, MAX_PORT) + 1):
        tried.append(port)
        if usable(port, host):
            return port, tried
    return None, tried


# ---------------------------------------------------------------- 页面端口改写

# 页面模板里是 `var APIPORT=__APIPORT__;`，渲染后成为 `var APIPORT=8765;`。
# 只匹配「标识符 + 等号 + 数字」，不会碰到 `String(APIPORT)` 这类读取点。
_APIPORT_RX = re.compile(r"\bAPIPORT=\d+")


def rewrite_api_port(text, port):
    """把静态 HTML/JS 文本里烘焙的 `APIPORT=<数字>` 换成实际端口。

    为什么需要它：日报与归档快照是**静态文件**（必须与 `output/archive` 逐字节一致，
    不能被重新渲染），而 JS 里的端口是渲染当时的 `config.port`。服务因端口被占而
    顺延时，不改写就会让收藏/下载/Dowvote 打到旧端口 —— 表现是「点了没反应」。
    """
    if not text or not valid_port(port):
        return text
    return _APIPORT_RX.sub("APIPORT=%d" % int(port), text)


# ---------------------------------------------------------------- 浏览器开关

_TRUTHY = {"1", "true", "yes", "on", "y", "t"}


def browser_enabled(argv=(), cfg=None):
    """该不该自动打开浏览器（默认打开）。

    优先级：命令行 > 配置项 `open_browser` > 默认 True。
    命令行两个方向都留了口子：`--no-open` 关（定时任务/服务器用）、`--open` 开
    （配置里关了但这次想看）。
    """
    argv = list(argv or ())
    if "--no-open" in argv:
        return False
    if "--open" in argv:
        return True
    value = (cfg or {}).get("open_browser", True)
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY
    return bool(value)


def open_browser(url, delay=0.8, opener=None):
    """延迟一小会儿再用系统默认浏览器打开 url，返回 Timer（便于测试 join）。

    三条硬约束：
      1. 只做「尽力而为」：无桌面环境、没装浏览器、`webbrowser` 抛错都只打印一行
         提示，**绝不把异常抛给调用方**（否则服务器版的启动会直接失败）；
      2. 在后台线程里做：`webbrowser.open` 在部分平台会阻塞到浏览器窗口出现，
         不能卡住 `serve_forever()`；
      3. 延迟 0.8 秒：先把「serving ...」和端口打完，再弹浏览器，日志顺序才不乱。
    """
    opener = opener or webbrowser.open

    def _go():
        try:
            ok = opener(url)
        except Exception as e:  # noqa: BLE001 —— 任何失败都只是"没开成浏览器"
            print("[browser] 未能自动打开浏览器（%s），请手动访问 %s" % (e, url))
            return
        if not ok:
            print("[browser] 未能自动打开浏览器，请手动访问 %s" % url)

    timer = threading.Timer(float(delay), _go)
    timer.daemon = True
    timer.start()
    return timer


# ---------------------------------------------------------------- 运行期信息落盘

def write_runtime_info(path, port, pid=None, when=None):
    """把「实际在哪个端口」写到 `output/server.json`，失败返回 None。

    为什么需要：`run_daily.py` 后台拉起服务后只能靠 HTTP 轮询（看不到子进程的
    stdout）。服务如果又顺延了一次，轮询旧端口就会白等到超时。落盘一份实际端口，
    调用方就能对上账；人排查时也能一眼看到「上次开在哪」。
    """
    info = {
        "port": int(port),
        "url": url_for(port),
        "pid": int(pid or os.getpid()),
        "started_at": when or time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception:  # noqa: BLE001 —— 落盘只是辅助信息，不能影响服务启动
        return None
    return info


def read_runtime_info(path):
    """读回运行期信息；文件缺失/损坏/端口非法都返回 None（调用方当作"不知道"）。"""
    try:
        with open(path, encoding="utf-8") as f:
            info = json.load(f)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(info, dict):
        return None
    port = valid_port(info.get("port"))
    if not port:
        return None
    return dict(info, port=port, url=url_for(port))
