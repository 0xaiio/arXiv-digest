"""B 站扫码登录 → 写出 biliup 可识别的 cookies.json。

为什么不用 `biliup login`：
    biliup-rs 的 login 只在进程正常退出时才落盘，且必须交互终端（无 TTY 直接拒绝）。
    无人值守场景（定时任务）下不可靠，所以这里直连 passport API 自己做：
    生成二维码 PNG → 用户扫码并在 App 里点「确认」→ 轮询 code=0 →
    从 Set-Cookie / 回调 URL 取凭据 → 按 biliup 的 LoginInfo 结构写文件。

cookies.json 的 schema（用 `biliup renew` 实测得出，不是猜的）：
    {
      "cookie_info": {"cookies": [{"name": ..., "value": ...}], "domains": [...]},
      "sso": [...],
      "token_info": {"access_token": ..., "expires_in": ..., "mid": ..., "refresh_token": ...}
    }

用法：
    python -X utf8 tools/bili_qr_login.py --wait 240
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from pathlib import Path

import qrcode
import requests

ROOT = Path(__file__).resolve().parents[1]
QR_PNG = ROOT / "output" / "bili_qr.png"
COOKIE = ROOT / ".secrets" / "bili_cookies.json"

GEN = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
POLL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
NEEDED = ("SESSDATA", "bili_jct", "DedeUserID")


def build_login_info(jar: dict, mid: int, refresh_token: str) -> dict:
    cookies = [{"name": k, "value": v} for k, v in jar.items() if v]
    return {
        "cookie_info": {
            "cookies": cookies,
            "domains": [".bilibili.com", "bilibili.com", "passport.bilibili.com"],
        },
        "sso": [],
        "token_info": {
            "access_token": "",
            "expires_in": 0,
            "mid": mid,
            "refresh_token": refresh_token or "",
        },
    }


def harvest(session: requests.Session, callback_url: str) -> dict:
    """凭据来源优先级：Session 的 Set-Cookie > 回调 URL 的 query（要 unquote）。"""
    jar = {c.name: c.value for c in session.cookies}
    if all(k in jar for k in NEEDED):
        return jar
    if "?" in callback_url:
        q = urllib.parse.parse_qs(callback_url.split("?", 1)[1], keep_blank_values=True)
        for k in NEEDED:
            if k not in jar and k in q:
                jar[k] = urllib.parse.unquote(q[k][0])
    return jar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=240, help="轮询等待秒数（二维码约 180s 有效）")
    a = ap.parse_args()

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://passport.bilibili.com/"})

    gen = s.get(GEN, timeout=15).json()
    if gen.get("code") != 0:
        print(f"[fail] 生成二维码失败：{gen}")
        return 2
    qr_url, key = gen["data"]["url"], gen["data"]["qrcode_key"]
    QR_PNG.parent.mkdir(parents=True, exist_ok=True)
    qrcode.make(qr_url).save(QR_PNG)
    print(f"[ok] 二维码已生成 → {QR_PNG}")
    print("[ok] 请用 B站 App 扫描，并在手机上点『确认登录』（约 3 分钟有效）")

    deadline = time.time() + a.wait
    last = None
    while time.time() < deadline:
        r = s.get(POLL, params={"qrcode_key": key}, timeout=15)
        d = r.json().get("data", {})
        code = d.get("code")
        name = {86101: "WAIT(未扫描)", 86090: "SCAN(已扫描,待确认)",
                86038: "TIMEOUT(已过期)", 0: "DONE(登录成功)"}.get(code, f"code={code}")
        if name != last:
            print(f"[state] {name}")
            last = name
        if code == 0:
            jar = harvest(s, d.get("url", ""))
            missing = [k for k in NEEDED if not jar.get(k)]
            if missing:
                print(f"[fail] 凭据缺字段：{missing}（回调 URL 与 Set-Cookie 都没拿到）")
                return 4
            mid = int(jar.get("DedeUserID") or 0)
            info = build_login_info(jar, mid, d.get("refresh_token", ""))
            COOKIE.parent.mkdir(parents=True, exist_ok=True)
            COOKIE.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[ok] cookie 已写入 → {COOKIE}")
            print(f"[ok] DedeUserID={jar['DedeUserID']} · SESSDATA={jar['SESSDATA'][:8]}… "
                  f"· bili_jct={jar['bili_jct'][:6]}… · 共 {len(jar)} 项")
            return 0
        if code == 86038:
            print("[fail] 二维码过期，请重跑本命令重新扫码")
            return 3
        time.sleep(2)
    print(f"[fail] 等待超时（{a.wait}s），请重跑本命令")
    return 3


if __name__ == "__main__":
    sys.exit(main())
