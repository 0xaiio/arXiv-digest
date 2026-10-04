"""B 站 TV 通道扫码登录 → 写出 biliup 可识别且带 access_token 的 cookies.json。

为什么需要这个：
    biliup-rs 0.2.4 的上传流程在提交时走 App 接口（submit_by_app），需要
    token_info.access_token。纯 Web 扫码（cookie/info 换不来 token）写出的
    cookies.json 缺 access_token，biliup 会在启动时的 SSO 交换环节收到 -400。
    TV 通道扫码直接返回 access_token + refresh_token + cookie_info，一步到位。

接口（bilibili-API-collect 公开约定）：
    POST https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code   生成二维码
    POST https://passport.bilibili.com/x/passport-tv-login/qrcode/poll        轮询
    appkey=4409e2ce8ffd12b8  appsec=59b43e04ad6965f34319062b478f83dd
    sign = md5(sorted_query_string + appsec)

用法：
    python -X utf8 tools/bili_tv_qr_login.py --wait 280
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
import uuid
from pathlib import Path

import qrcode
import requests

ROOT = Path(__file__).resolve().parents[1]
QR_PNG = ROOT / "output" / "bili_qr_tv.png"
COOKIE = ROOT / ".secrets" / "bili_cookies.json"

AUTH = "https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code"
POLL = "https://passport.bilibili.com/x/passport-tv-login/qrcode/poll"
APPKEY = "4409e2ce8ffd12b8"
APPSEC = "59b43e04ad6965f34319062b478f83dd"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def sign(params: dict) -> str:
    q = urllib.parse.urlencode(sorted(params.items()))
    return hashlib.md5((q + APPSEC).encode()).hexdigest()


def build_login_info(data: dict) -> dict:
    return {
        "cookie_info": data["cookie_info"],
        "sso": [],
        "token_info": {
            "access_token": data["access_token"],
            "expires_in": data.get("expires_in", 0),
            "mid": data.get("mid", 0),
            "refresh_token": data["refresh_token"],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=280)
    a = ap.parse_args()

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
    local_id = uuid.uuid4().hex

    base = {"appkey": APPKEY, "local_id": local_id, "ts": int(time.time())}
    p1 = dict(base, sign=sign(base))
    r = s.post(AUTH, data=p1, timeout=15).json()
    if r.get("code") != 0:
        print(f"[fail] 生成二维码失败：{r}")
        return 2
    auth_code, qr_url = r["data"]["auth_code"], r["data"]["url"]
    QR_PNG.parent.mkdir(parents=True, exist_ok=True)
    qrcode.make(qr_url).save(QR_PNG)
    print(f"[ok] TV 通道二维码已生成 → {QR_PNG}")
    print("[ok] 请用 B站 App 扫描，并在手机上点『确认登录』（约 3 分钟有效）")

    deadline = time.time() + a.wait
    last = None
    while time.time() < deadline:
        base = {"appkey": APPKEY, "auth_code": auth_code, "local_id": local_id, "ts": int(time.time())}
        p = dict(base, sign=sign(base))
        d = s.post(POLL, data=p, timeout=15).json()
        code = d.get("code")
        name = {56005: "WAIT(未扫描)", 86039: "SCAN(已扫描,待确认)",
                86038: "TIMEOUT(已过期)", 0: "DONE(登录成功)"}.get(code, f"code={code} {d.get('message','')}")
        if name != last:
            print(f"[state] {name}")
            last = name
        if code == 0:
            info = build_login_info(d["data"])
            COOKIE.parent.mkdir(parents=True, exist_ok=True)
            COOKIE.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
            jar = {c["name"]: c["value"] for c in info["cookie_info"]["cookies"]}
            print(f"[ok] cookie 已写入 → {COOKIE}")
            print(f"[ok] mid={info['token_info']['mid']} · access_token={info['token_info']['access_token'][:8]}… "
                  f"· SESSDATA={'有' if jar.get('SESSDATA') else '无'} · bili_jct={'有' if jar.get('bili_jct') else '无'}")
            return 0
        if code == 86038:
            print("[fail] 二维码过期，请重跑本命令重新扫码")
            return 3
        time.sleep(2)
    print(f"[fail] 等待超时（{a.wait}s），请重跑本命令")
    return 3


if __name__ == "__main__":
    sys.exit(main())
