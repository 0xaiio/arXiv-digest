/**
 * arXiv Weekly 重点论文解读短片（Remotion，代码渲染 / 数据驱动）
 *
 * 设计要点：
 * - 纯深色背景 + 白字；仅用 #00D4FF 作强调色（类别、编号、关键词、分数、时间线节点）
 * - 每篇论文独立 20s（600f@30fps）：meta → 英文原题 → 作者/单位 → 中文要点三行 → 链接
 *   论文解读不可能用 3s 讲完；三条要点分别在 4.1s / 7.1s / 10.1s 错峰入场，
 *   每条要点在屏幕上至少停留 10s，给足阅读与思考时间（配合中文语音讲解）
 * - 左侧竖向时间线串联全片，节点在当前篇开始时用 spring 弹亮，已播节点保持点亮
 * - 一切动画由 useCurrentFrame + spring / interpolate 驱动（禁用 CSS transition）
 * - 音轨：每段一条 mp3（reel/public/audio/），起始帧与画面段严格对齐；
 *   缺失/禁用时静默降级为无旁白，不影响渲染
 * - 字体走系统栈，不依赖 @remotion/google-fonts（渲染期不联网）
 */
import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
  useCurrentFrame,
  interpolate,
  spring,
} from "remotion";
import raw from "./papers.json";
import audioRaw from "./audio.json";

type Bullet = { tag: string; text: string };
type Paper = {
  rank: number;
  lane?: string; // "推荐" / "兴趣扩展"（由 gen_video_data.py 写入）
  sid: string;
  cat: string;
  score: number;
  title_en: string;
  kw: string[];
  authors: string;
  units: string[];
  bullets: Bullet[];
  link: string;
};
type Data = {
  issue: string;
  range: string;
  generated: string;
  stats: { core: number; expand: number; rec: number; exp: number };
  papers: Paper[];
};
type AudioSeg = {
  id: string;
  file: string;
  seconds: number;
  rate: string;
  chars: number;
  sid: string | null;
};
type AudioMap = {
  enabled: boolean;
  voice: string;
  segments: Record<string, AudioSeg>;
};

const DATA = raw as unknown as Data;
const AUDIO = audioRaw as unknown as AudioMap;
const AUDIO_ON = Boolean(AUDIO && AUDIO.enabled && AUDIO.segments);

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

const INTRO = 150; // 5.0s 片头
const PAPER = 600; // 20.0s / 篇（论文讲解的下限，配合中文旁白）
const OUTRO = 150; // 5.0s 片尾
const XFADE = 18; // 段落交叉淡入淡出
// 片尾旁白提前 1s 进入，盖住最后一张卡的淡出：否则第 5 篇讲完到片尾开场之间会留下 ~3s 空档，
// 观感像卡住了。这是标准的 voice lead-in 手法，不构成音画错位（说的仍是片尾自己的话）。
const OUTRO_LEAD = 30;
const N = DATA.papers.length;

export const DURATION = INTRO + N * PAPER + XFADE + OUTRO;

// 片尾的 arXiv 号清单按行折行（每行 SID_PER_ROW 个）：篇数从 5 扩到 10 后，
// 单行等宽排版会超过 1920px 被裁切。
const SID_PER_ROW = 5;
const SID_ROWS: string[] = Array.from(
  { length: Math.ceil(N / SID_PER_ROW) },
  (_, r) =>
    DATA.papers
      .slice(r * SID_PER_ROW, (r + 1) * SID_PER_ROW)
      .map((p) => p.sid)
      .join("   ·   "),
);

const BG = "#05070A";
const FG = "#FFFFFF";
const ACC = "#00D4FF";
const DIM = "#7C8896";
const SUB = "#C3CEDA";
const SANS =
  "'Segoe UI','Microsoft YaHei','PingFang SC','Hiragino Sans GB',sans-serif";
const MONO = "'Cascadia Mono','Consolas','SFMono-Regular',monospace";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const pad2 = (n: number) => String(n).padStart(2, "0");

/** 元素入场：左侧滑入 + 淡入（spring 位移，线性透明度） */
function enter(f: number, delay: number, dx = -56, dy = 0) {
  const s = spring({
    frame: Math.max(0, f - delay),
    fps: FPS,
    config: { damping: 200, mass: 0.6, stiffness: 120 },
    durationInFrames: 30,
  });
  return {
    opacity: interpolate(f, [delay, delay + 10], [0, 1], clamp),
    transform: `translate(${interpolate(s, [0, 1], [dx, 0])}px, ${interpolate(
      s,
      [0, 1],
      [dy, 0]
    )}px)`,
  };
}

/** 把文本中的技术关键词染成强调色（大小写不敏感） */
function hl(text: string, kws: string[]) {
  if (!kws || kws.length === 0) return text as React.ReactNode;
  const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(
    "(" +
      [...kws]
        .map(esc)
        .sort((a, b) => b.length - a.length)
        .join("|") +
      ")",
    "gi"
  );
  const lower = new Set(kws.map((k) => k.toLowerCase()));
  return text.split(re).map((part, i) =>
    lower.has(part.toLowerCase()) ? (
      <span key={i} style={{ color: ACC }}>
        {part}
      </span>
    ) : (
      part
    )
  );
}

/* ------------------------------- 语音讲解音轨 ------------------------------- */

/**
 * 一段旁白。音频时长只会短于所在画面段（Python 侧强制保证），因此不会撑长分段、
 * 也不会产生跨段漂移；首尾各做 5/10 帧淡入淡出，避免爆音与硬切。
 */
const VoiceInner: React.FC<{ file: string; frames: number }> = ({
  file,
  frames,
}) => {
  const f = useCurrentFrame();
  const v = Math.min(
    interpolate(f, [0, 5], [0, 1], clamp),
    interpolate(f, [frames, frames + 10], [1, 0], clamp)
  );
  return <Audio src={staticFile(file)} volume={v} />;
};

const Voice: React.FC<{ id: string; start: number }> = ({ id, start }) => {
  const seg = AUDIO.segments ? AUDIO.segments[id] : undefined;
  if (!seg) return null;
  const frames = Math.max(1, Math.round(seg.seconds * FPS));
  return (
    <Sequence from={start} durationInFrames={frames + 12}>
      <VoiceInner file={seg.file} frames={frames} />
    </Sequence>
  );
};

/* ------------------------------ 左侧竖向时间线 ------------------------------ */

const RAIL_TOP = 250;
const RAIL_BOT = 880;

const Rail: React.FC<{ active: number }> = ({ active }) => {
  const f = useCurrentFrame();
  const step = N > 1 ? (RAIL_BOT - RAIL_TOP) / (N - 1) : 0;

  const showIn = interpolate(f, [INTRO - 26, INTRO - 4], [0, 1], clamp);
  const showOut = interpolate(
    f,
    [DURATION - OUTRO, DURATION - OUTRO + 14],
    [1, 0],
    clamp
  );
  const railOpacity = Math.min(showIn, showOut);

  const filled = interpolate(
    f,
    [INTRO, INTRO + N * PAPER],
    [0, RAIL_BOT - RAIL_TOP],
    clamp
  );

  return (
    <AbsoluteFill style={{ opacity: railOpacity }}>
      {/* 底线 */}
      <div
        style={{
          position: "absolute",
          left: 150,
          top: RAIL_TOP,
          width: 2,
          height: RAIL_BOT - RAIL_TOP,
          background: "rgba(255,255,255,0.10)",
        }}
      />
      {/* 进度线 */}
      <div
        style={{
          position: "absolute",
          left: 150,
          top: RAIL_TOP,
          width: 2,
          height: filled,
          background: `linear-gradient(180deg, ${ACC}, rgba(0,212,255,0.25))`,
          boxShadow: `0 0 14px rgba(0,212,255,0.55)`,
        }}
      />
      {DATA.papers.map((p, i) => {
        const y = RAIL_TOP + i * step;
        const isActive = i === active;
        const isDone = i < active;
        const pop = spring({
          frame: Math.max(0, f - (INTRO + i * PAPER)),
          fps: FPS,
          config: { damping: 11, mass: 0.7, stiffness: 190 },
          durationInFrames: 26,
        });
        const scale = isDone ? 1 : isActive ? interpolate(pop, [0, 1], [0.25, 1]) : 1;
        const r = isActive ? 13 : 9;
        return (
          <React.Fragment key={p.sid}>
            <div
              style={{
                position: "absolute",
                left: 151 - r,
                top: y - r,
                width: r * 2,
                height: r * 2,
                borderRadius: r,
                transform: `scale(${scale})`,
                background: isDone ? "rgba(0,212,255,0.35)" : isActive ? ACC : BG,
                border: `2px solid ${isActive || isDone ? ACC : "rgba(255,255,255,0.22)"}`,
                boxShadow: isActive ? `0 0 26px rgba(0,212,255,0.85)` : "none",
              }}
            />
            <div
              style={{
                position: "absolute",
                left: 106,
                top: y - 16,
                width: 30,
                textAlign: "right",
                fontFamily: MONO,
                fontSize: 24,
                fontWeight: 700,
                color: isActive ? ACC : isDone ? "rgba(0,212,255,0.5)" : "rgba(255,255,255,0.22)",
              }}
            >
              {pad2(i + 1)}
            </div>
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};

/* ---------------------------------- 片头 ---------------------------------- */

const Intro: React.FC = () => {
  const f = useCurrentFrame();
  const op = interpolate(f, [INTRO, INTRO + XFADE], [1, 0], clamp);

  const s = spring({
    frame: Math.max(0, f - 3),
    fps: FPS,
    config: { damping: 13, mass: 0.9, stiffness: 92 },
    durationInFrames: 100,
  });
  const titleY = interpolate(s, [0, 1], [-280, 0], clamp);
  const barW = interpolate(s, [0, 1], [0, 560], clamp);

  const sub = enter(f, 34, 0, 34);
  const stats = enter(f, 52, 0, 30);

  return (
    <AbsoluteFill
      style={{
        opacity: op,
        fontFamily: SANS,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          fontFamily: MONO,
          fontSize: 24,
          letterSpacing: 8,
          color: ACC,
          marginBottom: 18,
          opacity: interpolate(f, [0, 14], [0, 1], clamp),
        }}
      >
        ARXIV · CS.* DIGEST
      </div>
      <div
        style={{
          fontSize: 156,
          fontWeight: 900,
          letterSpacing: -4,
          lineHeight: 1,
          color: FG,
          transform: `translateY(${titleY}px)`,
          opacity: interpolate(f, [0, 10], [0, 1], clamp),
        }}
      >
        arXiv Weekly
      </div>
      <div
        style={{
          width: barW,
          height: 6,
          background: ACC,
          marginTop: 26,
          boxShadow: `0 0 22px rgba(0,212,255,0.7)`,
        }}
      />
      <div style={{ ...sub, fontSize: 38, color: SUB, marginTop: 34 }}>
        第 {DATA.issue} 期 · {DATA.range}
      </div>
      <div
        style={{
          ...stats,
          display: "flex",
          gap: 46,
          marginTop: 30,
          fontFamily: MONO,
          fontSize: 28,
          color: DIM,
        }}
      >
        <span>
          本期新增 <span style={{ color: FG }}>{DATA.stats.core}</span>
        </span>
        <span>
          推荐 <span style={{ color: FG }}>{DATA.stats.rec}</span>
        </span>
        <span>
          兴趣扩展 <span style={{ color: FG }}>{DATA.stats.exp}</span>
        </span>
      </div>
    </AbsoluteFill>
  );
};

/* --------------------------------- 论文卡片 --------------------------------- */

const Card: React.FC<{ p: Paper }> = ({ p }) => {
  const f = useCurrentFrame();
  const outOp = interpolate(f, [PAPER, PAPER + XFADE], [1, 0], clamp);

  // 20s 段落内的入场节奏：识别信息在前 3s 铺完，三条要点分别在 4.1/7.1/10.1s 错峰出现，
  // 每条要点至少停留 10s 才切走，观众有时间读完并跟着旁白思考。
  const meta = enter(f, 6, -40);
  const title = enter(f, 26, -60);
  const who = enter(f, 62, -46);
  const units = enter(f, 82, -40);
  const b1 = enter(f, 124, -48);
  const b2 = enter(f, 214, -48);
  const b3 = enter(f, 304, -48);
  const foot = enter(f, 430, -30);
  const bulletStyle = [b1, b2, b3];

  return (
    <AbsoluteFill style={{ fontFamily: SANS, opacity: outOp }}>
      {/* 巨型序号水印 */}
      <div
        style={{
          position: "absolute",
          right: 78,
          top: 118,
          fontFamily: MONO,
          fontSize: 200,
          fontWeight: 900,
          letterSpacing: -4,
          color: "rgba(255,255,255,0.045)",
        }}
      >
        {pad2(p.rank)}
      </div>

      <AbsoluteFill
        style={{
          paddingLeft: 208,
          paddingRight: 82,
          paddingTop: 108,
          paddingBottom: 56,
          flexDirection: "column",
          justifyContent: "center",
          boxSizing: "border-box",
        }}
      >
        {/* meta 行 */}
        <div
          style={{
            ...meta,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span
              style={{
                fontFamily: MONO,
                fontSize: 28,
                letterSpacing: 1.5,
                color: ACC,
              }}
            >
              {p.cat}
            </span>
            <span style={{ color: "rgba(255,255,255,0.18)" }}>|</span>
            <span
              style={{
                fontFamily: SANS,
                fontSize: 25,
                color: p.lane === "兴趣扩展" ? SUB : ACC,
                border: `1px solid rgba(0,212,255,0.35)`,
                borderRadius: 8,
                padding: "2px 10px",
              }}
            >
              {p.lane === "兴趣扩展" ? "🌱 兴趣扩展" : "🎯 为你推荐"}
            </span>
            <span style={{ color: "rgba(255,255,255,0.18)" }}>|</span>
            <span style={{ fontFamily: MONO, fontSize: 28, color: DIM }}>
              arXiv:{p.sid}
            </span>
          </div>
          <div
            style={{
              fontFamily: MONO,
              fontSize: 27,
              color: ACC,
              border: `1px solid rgba(0,212,255,0.55)`,
              borderRadius: 8,
              padding: "3px 14px",
            }}
          >
            匹配度 {p.score}
          </div>
        </div>

        {/* 英文原题（真实可核实，不机器翻译） */}
        <div
          style={{
            ...title,
            fontSize: 56,
            fontWeight: 800,
            lineHeight: 1.22,
            letterSpacing: -0.5,
            color: FG,
            marginTop: 20,
          }}
        >
          {hl(p.title_en, p.kw)}
        </div>

        {/* 作者 / 单位 */}
        <div
          style={{
            ...who,
            fontSize: 30,
            color: SUB,
            marginTop: 22,
            lineHeight: 1.34,
          }}
        >
          {p.authors}
        </div>
        {p.units && p.units.length > 0 ? (
          <div
            style={{
              ...units,
              fontSize: 27,
              color: DIM,
              marginTop: 10,
              lineHeight: 1.34,
            }}
          >
            🏛 {p.units.join(" · ")}
          </div>
        ) : null}

        <div
          style={{
            height: 1,
            background: "rgba(255,255,255,0.10)",
            marginTop: 26,
            marginBottom: 24,
            opacity: interpolate(f, [96, 122], [0, 1], clamp),
          }}
        />

        {/* 中文要点：背景 / 方法 / 结论 */}
        {p.bullets.slice(0, 3).map((b, i) => (
          <div
            key={i}
            style={{
              ...(bulletStyle[i] ?? bulletStyle[2]),
              display: "flex",
              alignItems: "flex-start",
              marginBottom: 24,
            }}
          >
            <span
              style={{
                fontFamily: MONO,
                fontSize: 30,
                color: ACC,
                background: "rgba(0,212,255,0.12)",
                borderRadius: 8,
                padding: "5px 14px",
                marginRight: 20,
                flexShrink: 0,
              }}
            >
              {b.tag}
            </span>
            <span
              style={{
                fontSize: 37,
                lineHeight: 1.46,
                color: "#E6EDF5",
                flex: 1,
                overflowWrap: "anywhere",
              }}
            >
              {hl(b.text, p.kw)}
            </span>
          </div>
        ))}

        <div
          style={{
            ...foot,
            fontFamily: MONO,
            fontSize: 28,
            color: ACC,
            marginTop: 24,
            display: "flex",
            alignItems: "center",
            gap: 18,
          }}
        >
          <span>{p.link}</span>
          <span style={{ fontFamily: SANS, fontSize: 22, color: DIM }}>
            可点击链接见视频简介
          </span>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* ---------------------------------- 片尾 ---------------------------------- */

const Outro: React.FC = () => {
  const f = useCurrentFrame();
  const t = f / FPS;
  const breath = 1 + 0.032 * Math.sin((t * Math.PI * 2) / 2.4);
  const glow = 20 + 12 * Math.sin((t * Math.PI * 2) / 2.4);

  const in1 = enter(f, 8, 0, 40);
  const in2 = enter(f, 34, 0, 30);
  const in3 = enter(f, 56, 0, 24);

  return (
    <AbsoluteFill
      style={{
        fontFamily: SANS,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          ...in1,
          fontSize: 112,
          fontWeight: 900,
          letterSpacing: 2,
          color: FG,
          transform: `${in1.transform} scale(${breath})`,
          textShadow: `0 0 ${glow}px rgba(0,212,255,0.45)`,
        }}
      >
        关注获取更多
      </div>
      <div style={{ ...in2, fontSize: 32, color: SUB, marginTop: 30 }}>
        本片由 arXiv-daily 自动生成 · 每周二 / 周五 23:10 更新
      </div>
      <div
        style={{
          ...in3,
          fontFamily: MONO,
          fontSize: 22,
          color: DIM,
          marginTop: 26,
          letterSpacing: 1,
          textAlign: "center",
        }}
      >
        {SID_ROWS.map((row, i) => (
          <div key={i} style={{ marginTop: i === 0 ? 0 : 10 }}>
            {row}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/* ---------------------------------- 主合成 ---------------------------------- */

export const PaperReel: React.FC = () => {
  const f = useCurrentFrame();
  const active = Math.min(
    N - 1,
    Math.max(0, Math.floor((f - INTRO) / PAPER))
  );

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      {/* 中文语音讲解：各段起始帧与画面严格对齐（缺失音轨时整条链路静默跳过） */}
      {AUDIO_ON ? <Voice id="intro" start={0} /> : null}
      {AUDIO_ON
        ? DATA.papers.map((p, i) => (
            <Voice key={"v" + p.sid} id={"paper" + (i + 1)} start={INTRO + i * PAPER} />
          ))
        : null}
      {AUDIO_ON ? (
        <Voice id="outro" start={Math.max(0, DURATION - OUTRO - OUTRO_LEAD)} />
      ) : null}

      <Sequence from={0} durationInFrames={INTRO + XFADE}>
        <Intro />
      </Sequence>

      {f >= INTRO - 30 ? <Rail active={active} /> : null}

      {DATA.papers.map((p, i) => (
        <Sequence
          key={p.sid}
          from={INTRO + i * PAPER}
          durationInFrames={PAPER + XFADE}
        >
          <Card p={p} />
        </Sequence>
      ))}

      <Sequence from={DURATION - OUTRO} durationInFrames={OUTRO}>
        <Outro />
      </Sequence>
    </AbsoluteFill>
  );
};
