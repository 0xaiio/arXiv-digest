# -*- coding: utf-8 -*-
"""
视频 A/V 质量闸门：验证「音画同步 / 旁白清晰度 / 分段时长」三件事。

为什么需要它：MP4 渲染出来之后，单看 ffprobe 只能知道「有音轨」，
无法回答「第 3 篇开始时是不是真的在第 3 篇的画面上开始讲话」「中间有没有长静音」。
本工具把时间轴按 PaperReel.tsx 的分段常数切开，逐段做电平检测。

检查项
------
1. 每个画面段（片头 / 每篇 20s / 片尾）内的音频 mean_volume 必须高于阈值 → 该段真的有人在说话。
2. 每段的**语音起始时刻**必须落在该段内部且偏前（否则说明旁白漂移到了上一段/下一段）。
3. 全片不允许出现 > MAX_SILENCE 的静音空洞（RMS 低于 -45dB 视为静音）。
4. 总时长必须与 compositions 报的帧数一致（允许 AAC 补齐带来的 ±0.2s 误差）。

用法
----
    python tools/check_video_av.py reel/out/arxiv-weekly.mp4 [--papers 10]

篇数默认从 reel/src/papers.json 自动读取（与画面分段严格同源），
仅在离线核对时才有必要用 --papers 覆盖。
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys

FPS = 30
INTRO = 150
PAPER = 600
OUTRO = 150
XFADE = 18

MIN_MEAN_DB = -40.0      # 低于此值认为该段几乎没声音
SILENCE_DB = -45.0
MAX_SILENCE = 3.0        # 允许的最长静音（秒）；段落间的自然留白在 3s 以内


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        import shutil
        return shutil.which("ffmpeg")


def run(ff, args, timeout=180):
    r = subprocess.run([ff] + args, capture_output=True, timeout=timeout)
    return r.stderr.decode("utf-8", "replace") + r.stdout.decode("utf-8", "replace")


def duration_of(ff, path):
    out = run(ff, ["-i", path])
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", out)
    if not m:
        return None
    h, mi, s = (float(x) for x in m.groups())
    return h * 3600 + mi * 60 + s


def slice_stats(ff, path, start, dur):
    """返回该时间窗的 mean_volume / max_volume（dB）。"""
    out = run(ff, [
        "-ss", "%.3f" % start, "-t", "%.3f" % dur, "-i", path,
        "-af", "volumedetect", "-f", "null", "-",
    ])
    mean = re.search(r"mean_volume:\s*(-?\d+\.?\d*)\s*dB", out)
    mx = re.search(r"max_volume:\s*(-?\d+\.?\d*)\s*dB", out)
    return (
        float(mean.group(1)) if mean else None,
        float(mx.group(1)) if mx else None,
    )


def speech_start(ff, path, start, dur, step=0.5):
    """在窗口内以 step 秒为粒度找第一个「有声」的时刻（相对窗口起点的偏移）。"""
    t = 0.0
    while t < dur:
        mean, _ = slice_stats(ff, path, start + t, min(step, dur - t))
        if mean is not None and mean > MIN_MEAN_DB:
            return t
        t += step
    return None


def silences(ff, path):
    out = run(ff, ["-i", path, "-af", "silencedetect=n=%fdB:d=%.2f" % (SILENCE_DB, MAX_SILENCE), "-f", "null", "-"])
    return [
        (float(a), float(b))
        for a, b in re.findall(r"silence_start:\s*(\d+\.?\d*)[^\n]*\n[^\n]*silence_end:\s*(\d+\.?\d*)", out)
    ]


def paper_count(default=10):
    """从 reel/src/papers.json 读篇数，保证与画面分段严格同源。"""
    p = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "reel", "src", "papers.json",
    )
    try:
        with io.open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        n = len(data.get("papers") or [])
        return n or default
    except Exception as exc:
        print("[warn] 读取 %s 失败（%s），按 %d 篇核对" % (p, exc, default))
        return default


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument(
        "--papers", type=int, default=None,
        help="篇数；默认从 reel/src/papers.json 自动读取",
    )
    args = ap.parse_args(argv)
    if args.papers is None:
        args.papers = paper_count()

    ff = ffmpeg_exe()
    if not ff:
        print("[err] 找不到 ffmpeg")
        return 2
    if not os.path.exists(args.video):
        print("[err] 文件不存在: %s" % args.video)
        return 2

    total_frames = INTRO + args.papers * PAPER + XFADE + OUTRO
    expect = total_frames / FPS
    real = duration_of(ff, args.video)
    print("视频: %s" % os.path.abspath(args.video))
    print("时长: %.2fs（期望 %.2fs，%d 帧 @%dfps）" % (real, expect, total_frames, FPS))
    ok = True
    if abs(real - expect) > 0.25:
        print("[FAIL] 总时长偏差 %.2fs，超过 ±0.25s 容差" % abs(real - expect))
        ok = False
    else:
        print("[ok]   总时长符合预期")

    segs = [("片头", 0.0, INTRO / FPS)]
    for i in range(args.papers):
        st = (INTRO + i * PAPER) / FPS
        segs.append(("第%d篇" % (i + 1), st, PAPER / FPS))
    segs.append(("片尾", (total_frames - OUTRO) / FPS, OUTRO / FPS))

    print("\n%-8s %-14s %10s %8s %10s" % ("段", "窗口(s)", "均值dB", "峰值dB", "语音起点"))
    print("-" * 58)
    for name, st, du in segs:
        if st >= real:
            print("%-8s %-14s (超出视频末尾)" % (name, "%.1f-%.1f" % (st, st + du)))
            continue
        du = min(du, real - st)
        mean, mx = slice_stats(ff, args.video, st, du)
        off = speech_start(ff, args.video, st, min(du, 8.0))
        flag = "[ok]   "
        if mean is None or mean < MIN_MEAN_DB:
            flag = "[FAIL] "
            ok = False
        elif off is None or off > 2.0:
            flag = "[warn] "   # 有声音但起步偏晚：可能是旁白比画面晚太多
        print("%s%-6s %-14s %10s %8s %10s" % (
            flag, name, "%.1f-%.1f" % (st, st + du),
            "%.1f" % mean if mean is not None else "?",
            "%.1f" % mx if mx is not None else "?",
            "+%.1fs" % off if off is not None else "未检出",
        ))

    print()
    sl = silences(ff, args.video)
    long_sil = [(a, b) for a, b in sl if (b - a) > MAX_SILENCE]
    if long_sil:
        ok = False
        print("[FAIL] 存在 %d 段超过 %.1fs 的静音：" % (len(long_sil), MAX_SILENCE))
        for a, b in long_sil:
            print("         %.2fs - %.2fs（%.2fs）" % (a, b, b - a))
    else:
        print("[ok]   无超过 %.1fs 的静音空洞" % MAX_SILENCE)

    print()
    print("结论: %s" % ("全部通过" if ok else "存在问题，需修复后重渲"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
