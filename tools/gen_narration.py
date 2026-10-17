# -*- coding: utf-8 -*-
"""
为 arXiv Weekly 视频生成**中文语音讲解**（每段一条独立音轨，与画面分段对齐）。

语音方案
--------
Edge TTS（Microsoft Edge 的在线朗读服务，免费、中文自然度高），默认音色
``zh-CN-YunxiNeural``（阳光男声，偏轻松活泼，不适合正式播音腔的场景也够用）。

设计要点
--------
1. **口播稿必须与幻灯片不同**：屏幕上放的是「背景 / 方法 / 结果」三条要点，
   音频讲的是把这些要点口语化重述 + 补充说明后的连贯叙述。脚本优先读取
   ``output/video_notes.json`` 里人工撰写的 ``narration`` 字段；
   没有稿件时才用 ``口语化兜底`` 组装（会把 N=5、"5%→100%" 这类符号转成中文读法，
   并加上连接语，避免变成「逐字朗读 PPT」）。
2. **语速自适应**：每段有明确的时长预算与目标（见 SEGMENT_BUDGET_SEC /
   ``SEGMENT_TARGET_SEC``）。脚本先以常速合成一次测出基准时长，再解析地算出
   把语速贴到目标所需的百分比，只在 ``-12% ~ +25%`` 区间内调整——
   **短稿适度放慢而不是在段尾留下几秒静音，长稿适度收紧而不是超支**；
   仍超预算时沿阶梯继续加速，并最终以 ``[warn]`` 报出超出秒数，供人工精简稿件。
3. **响度归一化**：Edge TTS 原始输出偏轻（整段 mean_volume 实测 ≈ −27dB，笔记本扬声器上要
   调大音量才听清）。合成后用 ffmpeg ``loudnorm`` 统一归一到 **−16 LUFS / 峰值 −1.5 dBTP**
   （网络视频通用响度），失败则保留原始音频并告警，不阻断流程。
4. **画面主控，音频服从画面**：Remotion 侧把音轨放在各段起始帧，
   段长固定；音频只会比段短，不会把画面撑长，因此不存在累积漂移。

依赖（装在 WorkBuddy 默认 venv 里）
----------------------------------
    pip install edge-tts imageio-ffmpeg

    python -m pip install edge-tts imageio-ffmpeg

用法
----
    python tools/gen_narration.py                 # 生成全部段落
    python tools/gen_narration.py --voice zh-CN-XiaoxiaoNeural
    python tools/gen_narration.py --no-tts        # 只生成稿件，不合成（离线自检用）
"""
import argparse
import asyncio
import io
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
REEL = os.path.join(ROOT, "reel")
PUB_AUDIO = os.path.join(REEL, "public", "audio")

DEFAULT_VOICE = "zh-CN-YunxiNeural"
# 段时长预算（秒）：必须与 reel/src/PaperReel.tsx 的 INTRO/PAPER/OUTRO 一致，
# 且留 ~0.8s 余量，避免语音尾巴撞上交叉淡出。
SEGMENT_BUDGET_SEC = {"intro": 4.2, "paper": 19.0, "outro": 4.2}
# 「填满目标」：每段音频应尽量贴着这个时长走，避免段尾留下大段静音。
# 目标 < 预算，差的 ~0.4s 是留给段落交叉淡出的安全余量。
SEGMENT_TARGET_SEC = {"intro": 3.9, "paper": 18.6, "outro": 3.9}
# 语速调节区间（%）。负值=放慢、正值=加快；超出这个区间就不再动，
# 因为过度放慢会显得拖沓、过度加快会失去自然感。
RATE_MIN, RATE_MAX = -12, 25

CAT_CN = {
    "cs.DB": "数据库", "cs.DC": "分布式与并行计算", "cs.DS": "数据结构与算法",
    "cs.FL": "形式化方法与自动机", "cs.LO": "逻辑学与语义", "cs.PL": "程序语言",
    "cs.SE": "软件工程", "cs.CR": "密码学与安全", "cs.LG": "机器学习",
    "cs.AI": "人工智能", "cs.AR": "硬件体系结构", "cs.NI": "网络与互联",
    "cs.OS": "操作系统", "cs.SY": "系统与控制", "cs.GT": "计算博弈论",
    "cs.MA": "多 Agent 系统", "cs.CV": "计算机视觉", "cs.CL": "计算语言学",
    "cs.IR": "信息检索", "cs.HC": "人机交互", "cs.GL": "通用文学",
    "cs.MM": "多媒体", "cs.NE": "神经与进化计算", "cs.RO": "机器人",
    "cs.SC": "符号计算", "cs.CG": "计算几何", "cs.CE": "计算工程",
    "cs.CY": "计算与社会", "cs.ET": "新兴技术", "cs.GR": "图形学",
    "cs.MS": "数学软件", "cs.NA": "数值分析", "cs.PF": "性能",
    "cs.SD": "声音", "cs.DM": "离散数学", "math.LO": "数理逻辑",
}


# --------------------------------------------------------------------------- 工具

def load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        print("[warn] 无法解析 %s: %s" % (path, exc))
        return default


def ffmpeg_exe():
    """优先用 imageio-ffmpeg 自带的静态 ffmpeg；否则退回 PATH 上的 ffmpeg。"""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = shutil.which("ffmpeg")
        return exe


def media_duration(path, ff):
    """用 ffmpeg 读媒体时长（秒）。读不到返回 None。"""
    if not ff or not os.path.exists(path):
        return None
    try:
        r = subprocess.run([ff, "-i", path], capture_output=True, timeout=60)
        s = r.stderr.decode("utf-8", "replace")
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", s)
        if not m:
            return None
        h, mi, sec = (float(x) for x in m.groups())
        return h * 3600 + mi * 60 + sec
    except Exception as exc:
        print("[warn] 读取时长失败 %s: %s" % (path, exc))
        return None


# 网络视频的通用响度目标。Edge TTS 原始输出偏轻（实测整段 mean_volume ≈ -27dB，
# 在笔记本扬声器上要调大音量才听清），统一归一到 -16 LUFS / 峰值 -1.5 dBTP 后口播更清楚。
LOUDNESS_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"
LOUDNESS_TARGET_LUFS = -16.0


def mean_volume(path, ff):
    if not ff or not os.path.exists(path):
        return None
    try:
        r = subprocess.run(
            [ff, "-i", path, "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, timeout=60,
        )
        m = re.search(r"mean_volume:\s*(-?\d+\.?\d*)\s*dB",
                      r.stderr.decode("utf-8", "replace"))
        return float(m.group(1)) if m else None
    except Exception:
        return None


def normalize_loudness(ff, path):
    """把旁白归一化到 -16 LUFS。失败则原样保留（不阻断流程）。"""
    if not ff:
        return False
    tmp = path[:-4] + ".norm.mp3"
    try:
        subprocess.run(
            [ff, "-y", "-i", path, "-af", LOUDNESS_FILTER,
             "-ar", "48000", "-b:a", "192k", tmp],
            capture_output=True, timeout=180,
        )
    except Exception as exc:
        print("[warn] 响度归一化异常：%s" % exc)
        return False
    if not (os.path.exists(tmp) and os.path.getsize(tmp) > 1024):
        print("[warn] 响度归一化未产出有效文件，保留原始音频")
        return False
    try:
        os.replace(tmp, path)
        return True
    except Exception as exc:
        print("[warn] 归一化音频替换失败：%s" % exc)
        return False


# ------------------------------------------------------------ 稿件：口语化组装

CN_NUM = "零一二三四五六七八九"


def num_to_cn(n):
    """把 0–99 的整数转成中文读法；更大的数保持阿拉伯数字（读起来更清楚）。"""
    try:
        v = int(n)
    except Exception:
        return str(n)
    if not 0 <= v <= 99:
        return str(v)
    if v < 10:
        return CN_NUM[v]
    tens, ones = divmod(v, 10)
    head = CN_NUM[tens] + "十"
    return head + (CN_NUM[ones] if ones else "")


def to_speech(text):
    """
    把屏幕要点文本转成「能读出来」的口语：
    - 箭头、等号、百分号、斜杠等符号换成中文措辞
    - 小整数转中文读法（"N=5" → "N 等于五"）
    - 去掉括号里过长的技术细节，改成停顿感的逗号
    """
    t = " ".join((text or "").split())
    if not t:
        return ""
    t = t.replace("→", " 提升到 ").replace("->", " 提升到 ").replace("=>", " 提升到 ")
    t = re.sub(r"(\d+(?:\.\d+)?)%", lambda m: "百分之" + num_to_cn(float(m.group(1))), t)
    t = re.sub(r"(\d+(\.\d+)?)倍", lambda m: m.group(1) + " 倍", t)
    t = re.sub(r"([A-Za-z])=\s*(\d+)", lambda m: "%s 等于 %s" % (m.group(1), num_to_cn(m.group(2))), t)
    t = re.sub(r"(\d+)\s*=\s*(\d+)", lambda m: "%s 等于 %s" % (num_to_cn(m.group(1)), num_to_cn(m.group(2))), t)
    t = re.sub(r"\s*；\s*", "；", t)
    t = t.replace("：", "，").replace(":", "，").replace("/", " 和 ").replace("、", "、")
    t = re.sub(r"（([^）]{0,40})）", lambda m: "，" + m.group(1) + "，", t)
    t = re.sub(r"，{2,}", "，", t).strip("，、 ")
    return t


TAG_LEAD = {
    "背景": "先说它想解决的问题。",
    "方法": "他们的做法是，",
    "结果": "结果呢，",
}


def fallback_script(paper, idx):
    """没有人工稿件时的口语化兜底：加连接语 + 符号转中文读法 + 首尾呼应。"""
    cat = CAT_CN.get(paper.get("cat", ""), paper.get("cat", ""))
    head = "第 %d 篇，%s方向的论文。" % (idx, cat)
    parts = [head]
    for b in (paper.get("bullets") or [])[:3]:
        lead = TAG_LEAD.get(b.get("tag", ""), "")
        parts.append(lead + to_speech(b.get("text", "")) + "。")
    parts.append("编号是 %s，感兴趣可以去看原文。" % paper.get("sid", ""))
    return "".join(parts)


def intro_script(data):
    n = len(data.get("papers", []))
    return "这一期 %s 周报，挑了 %s 篇最值得关注的论文，我们一篇一篇来看。" % (
        data.get("issue", "arXiv"), num_to_cn(min(n, 99))
    )


def outro_script():
    return "以上就是这一期的全部内容，完整列表和链接都在日报里，我们下期再见。"


# ------------------------------------------------------------------- Edge TTS

TTS_TIMEOUT_SEC = 45


async def synth(text, voice, rate, path):
    import edge_tts  # 延迟导入，缺依赖时报错更友好
    comm = edge_tts.Communicate(text, voice, rate=rate)
    await comm.save(path)


def run_synth(text, voice, rate, path):
    """
    Edge TTS 会偶发 NoAudioReceived（服务端瞬时抽风，与稿件内容无关）。
    篇数从 5 提到 10 后单轮要打 12 次接口，命中概率明显上升，
    无人值守的定时任务一旦撞上就会整轮失败 —— 故在这里就地重试。
    """
    import time
    last = None
    for attempt in range(3):
        try:
            # wait_for：Edge TTS 偶发「连接建好但流永不结束」的挂死（实测卡住 15+ 分钟无输出），
            # 没有超时会让无人值守的定时任务整轮白等。超时计入重试，最多 3 次。
            asyncio.run(asyncio.wait_for(synth(text, voice, rate, path), timeout=TTS_TIMEOUT_SEC))
            return
        except asyncio.TimeoutError:
            last = TimeoutError("Edge TTS 超时（%ds 未返回音频）" % TTS_TIMEOUT_SEC)
            if attempt < 2:
                print("       [retry %d/2] %s" % (attempt + 1, last))
                time.sleep(1.5 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001 - 只重试瞬时错误，三次仍失败才抛出
            last = exc
            if attempt < 2:
                print("       [retry %d/2] Edge TTS 瞬时错误：%s" % (attempt + 1, exc))
                time.sleep(1.5 * (attempt + 1))
    raise last


def fmt_rate(pct):
    """-5 -> '-5%' / 8 -> '+8%'"""
    return "%+d%%" % round(pct)


def synthesize(text, voice, budget, target, path, ff, no_tts=False):
    """
    先以 +0% 合成一次测出基准时长，再**解析地**算出把语速贴到 target 所需的百分比，
    只在必要区间内调整（RATE_MIN..RATE_MAX）；若仍超预算才沿阶梯继续加速。

    这样短稿会被适度放慢（而不是在段尾留下几秒静音），长稿会被适度收紧，
    两种情况都不牺牲自然度。返回 (seconds, rate, overflow_seconds)。
    """
    if no_tts:
        est = text_len(text) / 3.6
        return (est, "+0%", max(0.0, est - budget))

    run_synth(text, voice, "+0%", path)
    sec0 = media_duration(path, ff)
    if sec0 is None or not (os.path.exists(path) and os.path.getsize(path) > 0):
        return (None, "+0%", 0.0)

    want = (sec0 / target - 1) * 100          # 负=需放慢；正=需加快
    want = max(RATE_MIN, min(RATE_MAX, want))

    rate_s, sec = "+0%", sec0
    if abs(want) >= 2:
        rate_s = fmt_rate(want)
        run_synth(text, voice, rate_s, path)
        sec = media_duration(path, ff) or sec0

    pct = want
    tried = {round(pct)}
    while sec > budget and pct < RATE_MAX:
        pct = min(RATE_MAX, round(pct) + 6)
        if pct in tried:
            break
        tried.add(pct)
        rate_s = fmt_rate(pct)
        run_synth(text, voice, rate_s, path)
        sec = media_duration(path, ff) or sec

    normalize_loudness(ff, path)
    sec = media_duration(path, ff) or sec
    return (sec, rate_s, max(0.0, sec - budget))


def text_len(t):
    """粗略的『朗读字数』：中日韩文字按 1 计，拉丁词整体按 2 计。"""
    cjk = len(re.findall(r"[\u4e00-\u9fff]", t or ""))
    latin = len(re.findall(r"[A-Za-z][A-Za-z0-9+.\-]{1,}", t or ""))
    return cjk + latin * 2


# ------------------------------------------------------------------------ main

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--papers", default=os.path.join(REEL, "src", "papers.json"))
    ap.add_argument("--notes", default=os.path.join(OUT, "video_notes.json"))
    ap.add_argument("--outdir", default=PUB_AUDIO)
    ap.add_argument("--audio-json", default=os.path.join(REEL, "src", "audio.json"))
    ap.add_argument("--no-tts", action="store_true", help="只生成稿件，不调用 TTS")
    args = ap.parse_args(argv)

    data = load(args.papers, {})
    notes = load(args.notes, {})
    papers = data.get("papers") or []
    if not papers:
        print("[err] %s 里没有论文，先跑 gen_video_data.py" % args.papers)
        return 2

    ff = ffmpeg_exe()
    if not ff:
        print("[warn] 找不到 ffmpeg，无法校验音频时长")
    os.makedirs(args.outdir, exist_ok=True)

    try:
        import edge_tts  # noqa: F401
    except Exception:
        if not args.no_tts:
            print("[err] 未安装 edge-tts。请先执行：")
            print("       %s -m pip install edge-tts imageio-ffmpeg" % sys.executable)
            return 3

    segments = []          # 给 Remotion 用
    text_map = []          # 用于日志
    intro_ok = (notes.get("_intro") or {}).get("narration", "").strip()
    outro_ok = (notes.get("_outro") or {}).get("narration", "").strip()
    plan = [("intro", "intro", intro_ok or intro_script(data), None)]
    for i, p in enumerate(papers, start=1):
        sid = p.get("sid", "p%d" % i)
        n = notes.get(sid) or {}
        script = (n.get("narration") or "").strip() or fallback_script(p, i)
        plan.append(("paper%d" % i, "p%d" % i, script, sid))
    plan.append(("outro", "outro", outro_ok or outro_script(), None))

    ok = True
    for seg_id, fname, script, sid in plan:
        budget = SEGMENT_BUDGET_SEC["paper"] if seg_id.startswith("paper") else (
            SEGMENT_BUDGET_SEC["intro"] if seg_id == "intro" else SEGMENT_BUDGET_SEC["outro"]
        )
        target = SEGMENT_TARGET_SEC["paper"] if seg_id.startswith("paper") else (
            SEGMENT_TARGET_SEC["intro"] if seg_id == "intro" else SEGMENT_TARGET_SEC["outro"]
        )
        text_map.append((seg_id, len(script), script))
        dst = os.path.join(args.outdir, fname + ".mp3")
        sec, rate, over = synthesize(script, args.voice, budget, target, dst, ff, args.no_tts)
        if sec is None:
            ok = False
            print("[err] %-7s 合成失败" % seg_id)
            continue
        segments.append(
            {
                "id": seg_id,
                "file": "audio/%s.mp3" % fname,
                "seconds": round(sec, 2),
                "rate": rate,
                "chars": len(script),
                "mean_db": None if args.no_tts else (
                    round(mv, 1) if (mv := mean_volume(dst, ff)) is not None else None
                ),
                "sid": sid,
            }
        )
        flag = "[ok]  " if over <= 0.05 else "[warn]"
        print("%s %-7s %5.2fs/%4.1fs(目标%4.1f)  %s  %3d字  mean %s dB  %s" % (
            flag, seg_id, sec, budget, target, rate, len(script),
            ("%.1f" % mv) if (mv := mean_volume(dst, ff)) is not None else "?", os.path.basename(dst)
        ))
        if over > 0.05:
            print("         ↑ 超出 %.2fs，请精简口播稿或放长该段" % over)

    manifest = {
        "enabled": ok and not args.no_tts,
        "voice": args.voice,
        "segments": {s["id"]: s for s in segments},
    }
    os.makedirs(os.path.dirname(args.audio_json), exist_ok=True)
    with io.open(args.audio_json, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    total = sum(s["seconds"] for s in segments)
    print("[ok] %s（enabled=%s）" % (args.audio_json, manifest["enabled"]))
    print("     音色 %s · 音频合计 %.1fs" % (args.voice, total))
    if args.no_tts:
        print("     --no-tts：未真正合成，audio.json 记为 disabled")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
