#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日流水线 v3：抓取 → 扩展抓取 → 打分推荐 → 作者单位 → 渲染页面 → 确保本地服务在线。

用法：
  python run_daily.py                  # 抓取（核心+扩展）→ 推荐 → 作者单位 → 渲染 → 确保服务在线
  python run_daily.py --skip-fetch     # 复用已有 raw.json / raw_expand.json，只重算推荐并渲染
  python run_daily.py --skip-affil     # 跳过作者单位抓取（较慢，约 3s/篇）
  python run_daily.py --no-serve       # 不自动启动本地服务
  python run_daily.py --serve          # 渲染完在前台启动本地服务（阻塞）
  python run_daily.py --categories cs.DB,cs.DC
                                       # 先把跟踪的类别设为这几个（覆盖 config.json），再抓取
  python run_daily.py --preset hengxin # 先导入 presets/hengxin/ 这份数据包（配置+画像），再抓取
  python run_daily.py --preset hengxin --preset-force
                                       # 覆盖本机已有的 config.json / interests.json（先备份）

首次运行（config.json 里的 categories 为空）不会抓取任何东西：脚本会提示去
/profile 的「arXiv 类别」面板自选，并把本地服务拉起来。这是通用版的设计——
默认不预设任何领域，也不会读取 presets/ 下的任何人的画像。
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
PY = sys.executable

sys.path.insert(0, HERE)


def _payload_ok(text):
    """抓取脚本的 stdout 是否是「可用的」论文数据。

    arXiv API 限流/宕机时脚本会输出 {"error": "no data"}；这种内容绝不能覆盖
    上一期真实的 raw.json（2026-09-12 踩过：一次 429 把历史数据清空了）。
    """
    try:
        d = json.loads(text or "")
    except Exception:
        return False
    if not isinstance(d, dict):
        return False
    if d.get("error"):
        return False
    return bool(d.get("papers"))


def run(script, capture=None, keep_previous=False):
    """运行子脚本。返回 True 表示产出有效数据。

    keep_previous=True 且新输出无效时：保留已存在的旧文件，把坏输出另存
    `<capture>.bad_<ts>` 便于排查，不抛异常（下游可继续用旧数据渲染）。
    """
    cmd = [PY, os.path.join(HERE, script)]
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, cwd=HERE, capture_output=bool(capture), text=True,
                       encoding="utf-8", errors="replace")
    if r.stderr:
        print((r.stderr or "").strip()[:2000], file=sys.stderr)

    if not capture:
        print((r.stdout or "").strip()[:2000])
        if r.returncode != 0:
            raise SystemExit("%s failed with %d" % (script, r.returncode))
        return True

    out_path = os.path.join(OUT, capture)
    ok = r.returncode == 0 and _payload_ok(r.stdout)
    if ok:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(r.stdout)
        print("[ok] %s -> %s (%d bytes)" % (script, capture, len(r.stdout)))
        return True

    print("[warn] %s 未产出有效数据（rc=%s）" % (script, r.returncode), file=sys.stderr)
    if keep_previous and os.path.exists(out_path) and _payload_ok(open(out_path, encoding="utf-8").read()):
        bad = os.path.join(OUT, "%s.bad_%s" % (capture, time.strftime("%Y%m%d_%H%M%S")))
        try:
            with open(bad, "w", encoding="utf-8") as f:
                f.write(r.stdout or "")
        except Exception:
            pass
        print("[keep] %s 保持上一期内容不变（坏输出已存 %s）" % (capture, os.path.basename(bad)),
              file=sys.stderr)
        return False

    # 没有历史数据可保：仍然写盘，让下游报错信息真实反映「无数据」
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(r.stdout or "")
    return False


def port_of():
    try:
        import paperutil as pu
        return int((pu.load_config() or {}).get("port", 8765))
    except Exception:
        return 8765


def _no_proxy_opener():
    """探测本机服务必须绕开 HTTP_PROXY：部分环境会把 127.0.0.1 也丢给代理，返回 502。"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def server_alive(port, timeout=2.0):
    try:
        op = _no_proxy_opener()
        with op.open("http://127.0.0.1:%d/api/ping" % port, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def ensure_server(port=None, wait=15.0):
    """服务已在线则复用；否则后台拉起 server.py --no-open 并等待就绪。

    返回 (url, started)。Windows 下用 `cmd /c start /b` 脱离当前进程树，
    run_daily.py 退出后服务仍然存活。

    **坑（2026-09-12 迁移时踩到）**：`start /b` 不继承 Popen(cwd=...)，
    子进程会拿到上层 shell 的工作目录——项目搬到新目录后，服务仍以旧目录为 cwd，
    继续读写旧 output/。故必须用 `start /d <dir>` 显式指定启动目录，
    并给 server.py 传绝对路径（双保险）。
    """
    port = port or port_of()
    url = "http://127.0.0.1:%d" % port
    if server_alive(port):
        print("server already online: %s" % url)
        return url, False

    logpath = os.path.join(OUT, "server.log")
    try:
        log = open(logpath, "ab")
        cmd = [PY, os.path.join(HERE, "server.py"), "--no-open"]
        if os.name == "nt":
            cmd = ["cmd", "/c", "start", "", "/d", HERE, "/b"] + cmd
        subprocess.Popen(cmd, cwd=HERE, stdin=subprocess.DEVNULL,
                         stdout=log, stderr=log, close_fds=True)
        print("starting local server: %s  (log: %s)" % (url, logpath))
    except Exception as e:  # noqa
        print("failed to start server: %s" % e, file=sys.stderr)
        return url, False

    deadline = time.time() + wait
    while time.time() < deadline:
        if server_alive(port, timeout=1.0):
            print("server ready: %s" % url)
            return url, True
        time.sleep(0.3)
    print("server did not become ready in %.0fs, 可手动运行 start_digest.bat" % wait,
          file=sys.stderr)
    return url, False


def arg_value(args, name):
    """从 `--name v` 或 `--name=v` 里取值；没出现返回 None。"""
    for i, a in enumerate(args):
        if a == name:
            return args[i + 1] if i + 1 < len(args) else ""
        if a.startswith(name + "="):
            return a[len(name) + 1:]
    return None


def apply_preset_arg(args):
    """`--preset <名字>`：在其它动作之前导入一份数据包。

    顺序很关键：先 `--preset`（带进类别与画像），后 `--categories`（可以再覆盖类别），
    这样 `--preset hengxin --categories cs.LG` 的语义是"用这份画像，但类别只看 cs.LG"。
    导入失败只打印原因、继续跑：让服务起来，用户才能从界面排查。
    """
    name = arg_value(args, "--preset")
    if not name:
        return True
    import datapack as DP
    ok, msg, report = DP.import_pack(name, force="--preset-force" in args)
    print(("[preset] " + msg) if ok else ("[preset] 未完全导入：" + msg),
          file=sys.stdout if ok else sys.stderr)
    for r in report:
        if r["action"] != "skipped":
            print("         %-22s %-9s %s %s"
                  % (r["file"], r["group"], r["action"], r["reason"]))
    return ok


def apply_categories_arg(args):
    """`--categories cs.DB,cs.DC`：先写入 config.json，再走正常抓取流程。

    存在的理由：无 GUI 的机器（服务器、定时任务）也要能一次性配好类别，
    不必先手动编辑一个 JSON。校验与 /profile 面板完全同源（arxiv_cats）。
    """
    raw = arg_value(args, "--categories")
    if raw is None:
        return True
    cats = [c.strip() for c in raw.replace("，", ",").split(",") if c.strip()]
    import customize as CZ
    ok, msg, _ = CZ.set_categories(cats)
    print(("[categories] " + msg) if ok else ("[categories] 设置失败：" + msg),
          file=sys.stdout if ok else sys.stderr)
    return ok


def main():
    os.makedirs(OUT, exist_ok=True)
    args = sys.argv[1:]
    apply_preset_arg(args)
    if not apply_categories_arg(args):
        raise SystemExit(2)
    import customize as CZ
    if not CZ.categories():
        # 通用版的首次运行：没有类别就什么都不抓，避免「抓了个空还报成功」。
        print("[init] 尚未选择任何 arXiv 分类。\n"
              "       1) 打开 http://127.0.0.1:%d/profile ，在「🗂 arXiv 类别」面板里\n"
              "          先选主类（abc）再选子类（def），可多选、可搜索、可拖拽排序；\n"
              "          也可在「📦 数据包」里一键导入一份现成设置（可选，默认不加载）。\n"
              "       2) 或者直接：python run_daily.py --categories cs.DB,cs.DC,cs.FL\n"
              "       3) 想直接套用一份现成设置：python run_daily.py --preset hengxin\n"
              "       选好后再运行一次本脚本即可抓取。" % port_of())
        if "--no-serve" not in args:
            url, _ = ensure_server()
            print("profile: %s/profile" % url)
        return
    if "--skip-fetch" not in args:
        ok1 = run("fetch_arxiv.py", capture="raw.json", keep_previous=True)
        ok2 = run("fetch_expand.py", capture="raw_expand.json", keep_previous=True)
        if not (ok1 and ok2):
            # API 被限流（429/503）时的降级通道：分类 RSS 与主站不同域、不限流，
            # 能拿到最近一次公告日的条目，**按短号增量合并**进既有 feed（绝不删条目）。
            #
            # 注意条件必须是 and 而不是 or：2026-09-16 踩过——六类里只有 cs.SE 在末次重试
            # 成功，ok1=True 让降级没触发，raw.json 从 281 篇被覆盖成 58 篇（全是 cs.SE），
            # 其余五个类别当天的论文直接丢失。只要有一路没成功就补 RSS。
            print("[fallback] arXiv API 部分/全部不可用，改用 RSS 增量抓取", file=sys.stderr)
            run("fetch_rss.py")
    # 抓取失败且无历史数据时，raw.json 会是 {"error": ...}；此时不硬跑 recommend，
    # 直接复用上一期已渲染的报告（见下方 fallback）。
    try:
        raw = json.load(open(os.path.join(OUT, "raw.json"), encoding="utf-8"))
    except Exception:
        raw = {}
    if not raw.get("papers"):
        print("raw.json 无可用论文数据：跳过推荐/渲染，沿用上一期报告", file=sys.stderr)
        if "--no-serve" not in args:
            ensure_server()
        return
    run("recommend.py")
    # 作者单位：arXiv API 不提供，需从 HTML 版抓；很慢（3s/篇），失败不影响后续
    if "--skip-affil" not in args:
        try:
            run("fetch_affil.py")
        except SystemExit as e:
            print("fetch_affil.py 失败（%s），跳过作者单位" % e, file=sys.stderr)
    run("build_report.py")
    if "--no-serve" not in args:
        url, _ = ensure_server()
        if "--serve" in args:
            run("server.py")          # 前台阻塞
        else:
            print("digest online: %s" % url)


if __name__ == "__main__":
    main()
