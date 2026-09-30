/**
 * arXiv Weekly 重点论文解读短片（Remotion，代码渲染 / 数据驱动）
 *
 * 设计要点：
 * - 纯深色背景 + 白字；仅用 #00D4FF 作强调色（类别、编号、关键词、分数、时间线节点）
 * - 每篇论文独立 12s（360f@30fps）：meta → 英文原题 → 作者/单位 → 中文要点三行 → 链接
 *   论文解读不可能用 3s 讲完，故单篇给出完整「背景 / 方法 / 结论」三层信息
 * - 左侧竖向时间线串联全片，节点在当前篇开始时用 spring 弹亮，已播节点保持点亮
 * - 一切动画由 useCurrentFrame + spring / interpolate 驱动（禁用 CSS transition）
 * - 字体走系统栈，不依赖 @remotion/google-fonts（渲染期不联网）
 */
import React from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  interpolate,
  spring,
} from "remotion";
import raw from "./papers.json";

type Bullet = { tag: string; text: string };
type Paper = {
  rank: number;
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

const DATA = raw as unknown as Data;

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

const INTRO = 90; // 3.0s 片头
const PAPER = 360; // 12.0s / 篇
const OUTRO = 90; // 3.0s 片尾
const XFADE = 14; // 段落交叉淡入淡出
const N = DATA.papers.length;

export const DURATION = INTRO + N * PAPER + XFADE + OUTRO;

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
    durationInFrames: 80,
  });
  const titleY = interpolate(s, [0, 1], [-280, 0], clamp);
  const barW = interpolate(s, [0, 1], [0, 560], clamp);

  const sub = enter(f, 24, 0, 34);
  const stats = enter(f, 36, 0, 30);

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

  const meta = enter(f, 2, -40);
  const title = enter(f, 10, -60);
  const who = enter(f, 26, -46);
  const units = enter(f, 34, -40);
  const b1 = enter(f, 52, -48);
  const b2 = enter(f, 66, -48);
  const b3 = enter(f, 80, -48);
  const foot = enter(f, 100, -30);
  const bulletStyle = [b1, b2, b3];

  return (
    <AbsoluteFill style={{ fontFamily: SANS, opacity: outOp }}>
      {/* 巨型序号水印 */}
      <div
        style={{
          position: "absolute",
          right: 132,
          top: 150,
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
          paddingLeft: 232,
          paddingRight: 150,
          paddingTop: 150,
          flexDirection: "column",
          justifyContent: "center",
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
                fontSize: 26,
                letterSpacing: 1.5,
                color: ACC,
              }}
            >
              {p.cat}
            </span>
            <span style={{ color: "rgba(255,255,255,0.18)" }}>|</span>
            <span style={{ fontFamily: MONO, fontSize: 26, color: DIM }}>
              arXiv:{p.sid}
            </span>
          </div>
          <div
            style={{
              fontFamily: MONO,
              fontSize: 24,
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
            fontSize: 52,
            fontWeight: 800,
            lineHeight: 1.24,
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
            fontSize: 27,
            color: SUB,
            marginTop: 22,
            lineHeight: 1.35,
          }}
        >
          {p.authors}
        </div>
        {p.units && p.units.length > 0 ? (
          <div
            style={{
              ...units,
              fontSize: 24,
              color: DIM,
              marginTop: 10,
              lineHeight: 1.35,
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
            opacity: interpolate(f, [44, 58], [0, 1], clamp),
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
              marginBottom: 20,
            }}
          >
            <span
              style={{
                fontFamily: MONO,
                fontSize: 24,
                color: ACC,
                background: "rgba(0,212,255,0.12)",
                borderRadius: 8,
                padding: "4px 12px",
                marginRight: 18,
                flexShrink: 0,
              }}
            >
              {b.tag}
            </span>
            <span
              style={{
                fontSize: 31,
                lineHeight: 1.5,
                color: "#E6EDF5",
                flex: 1,
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
            fontSize: 23,
            color: DIM,
            marginTop: 22,
          }}
        >
          {p.link}
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

  const in1 = enter(f, 4, 0, 40);
  const in2 = enter(f, 20, 0, 30);
  const in3 = enter(f, 32, 0, 24);

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
        }}
      >
        {DATA.papers.map((p) => p.sid).join("   ·   ")}
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
