import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
} from "remotion";
import raw from "./trend.json";
import audioRaw from "./trend_audio.json";

/* ------------------------------- 数据与音轨 ------------------------------- */

type Topic = {
  kind: "topic";
  rank: number;
  label: string;
  terms: string[];
  count: number;
  share: number;
  sample: { sid: string; title: string };
};
type GrowthItem = { key: string; cur: number; ratio: number; z: number };
type Growth = { kind: "growth"; rank: number; items: GrowthItem[] };
type Segment = Topic | Growth;

type Data = {
  issue: string;
  window: { start?: string; end?: string };
  generated: string;
  stats: { total: number; cats: number; clusters: number; growth: number };
  segments: Segment[];
};
type AudioSeg = { id: string; file: string; seconds: number; rate: string; chars: number };
type AudioMap = { enabled: boolean; voice: string; segments: Record<string, AudioSeg> };

const DATA = raw as unknown as Data;
const AUDIO = audioRaw as unknown as AudioMap;
const AUDIO_ON = Boolean(AUDIO && AUDIO.enabled && AUDIO.segments);

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

const INTRO = 150; // 5.0s
const SEG = 600; // 20.0s / 段，与日报视频的 PAPER 一致
const OUTRO = 150; // 5.0s
const XFADE = 18;
// 片尾旁白提前 0.5s：完全不提前会在末段讲话结束与片尾开场之间留 3.19s 静音；
// 提前 1s（日报的取值）又会在结尾留 3.07s 静音。两头都是 A/V 闸门的红线（3.0s），
// 0.5s 是实测过闸门的位置（2026-11-15，两版都跑过闸门）。
const OUTRO_LEAD = 15;
const N = DATA.segments.length;

export const DURATION = INTRO + N * SEG + XFADE + OUTRO;

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

/** 元素入场：左侧滑入 + 淡入（与 PaperReel 同一套节奏） */
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

const VoiceInner: React.FC<{ file: string; frames: number }> = ({ file, frames }) => {
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

/* --------------------------------- 时间线 --------------------------------- */

const Rail: React.FC<{ active: number }> = ({ active }) => {
  const total = N;
  const top = 250;
  const bottom = 880;
  const gap = total > 1 ? (bottom - top) / (total - 1) : 0;
  return (
    <div style={{ position: "absolute", left: 64, top, width: 80, height: bottom - top }}>
      <div style={{ position: "absolute", left: 9, top: 0, width: 2, height: bottom - top, background: "#1B2430" }} />
      <div
        style={{
          position: "absolute",
          left: 9,
          top: 0,
          width: 2,
          height: Math.max(0, gap * active),
          background: ACC,
          boxShadow: `0 0 12px rgba(0,212,255,0.8)`,
        }}
      />
      {Array.from({ length: total }, (_, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            top: i * gap - 9,
            left: 0,
            width: 20,
            height: 20,
            borderRadius: 10,
            background: i <= active ? ACC : BG,
            border: `2px solid ${i <= active ? ACC : "#2A3644"}`,
            boxShadow: i === active ? `0 0 26px rgba(0,212,255,0.9)` : "none",
            fontFamily: MONO,
            fontSize: 12,
            color: i <= active ? BG : DIM,
            textAlign: "center",
            lineHeight: "16px",
          }}
        >
          {i + 1}
        </div>
      ))}
    </div>
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
  const win = DATA.window || {};

  return (
    <AbsoluteFill style={{ opacity: op, fontFamily: SANS, alignItems: "center", justifyContent: "center" }}>
      <div style={{ fontFamily: MONO, fontSize: 24, letterSpacing: 8, color: ACC, marginBottom: 18,
                    opacity: interpolate(f, [0, 14], [0, 1], clamp) }}>
        ARXIV · CS.* · WEEKLY TREND
      </div>
      <div style={{ fontSize: 156, fontWeight: 900, letterSpacing: -4, lineHeight: 1, color: FG,
                    transform: `translateY(${titleY}px)`,
                    opacity: interpolate(f, [0, 10], [0, 1], clamp) }}>
        本周趋势
      </div>
      <div style={{ width: barW, height: 6, background: ACC, marginTop: 26,
                    boxShadow: `0 0 22px rgba(0,212,255,0.7)` }} />
      <div style={{ ...sub, fontSize: 38, color: SUB, marginTop: 34 }}>
        第 {DATA.issue} 期 · {win.start} → {win.end}
      </div>
      <div style={{ ...stats, display: "flex", gap: 46, marginTop: 30, fontFamily: MONO,
                    fontSize: 28, color: DIM }}>
        <span>论文 <span style={{ color: FG }}>{DATA.stats.total}</span></span>
        <span>分类 <span style={{ color: FG }}>{DATA.stats.cats}</span></span>
        <span>主题簇 <span style={{ color: FG }}>{DATA.stats.clusters}</span></span>
      </div>
    </AbsoluteFill>
  );
};

/* -------------------------------- 主题卡片 -------------------------------- */

const TopicCard: React.FC<{ s: Topic }> = ({ s }) => {
  const f = useCurrentFrame();
  const op = interpolate(f, [SEG, SEG + XFADE], [1, 0], clamp);
  const head = enter(f, 6, -60, 0);
  const kicker = enter(f, 16, -40, 0);
  const chips = enter(f, 34, 0, 26);
  const num = enter(f, 22, 40, 0);
  const sample = enter(f, 52, 0, 24);

  return (
    <AbsoluteFill style={{ opacity: op, fontFamily: SANS }}>
      <div style={{ position: "absolute", left: 180, top: 170, width: 1150 }}>
        <div style={{ ...kicker, fontFamily: MONO, fontSize: 22, letterSpacing: 6, color: ACC }}>
          TOPIC {pad2(s.rank)} / {pad2(N - 1)}
        </div>
        <div style={{ ...head, fontSize: 104, fontWeight: 900, lineHeight: 1.08, color: FG, marginTop: 18 }}>
          {s.label}
        </div>
        <div style={{ ...head, width: 120, height: 6, background: ACC, marginTop: 26,
                      boxShadow: `0 0 18px rgba(0,212,255,0.7)` }} />
        <div style={{ ...chips, display: "flex", flexWrap: "wrap", gap: 12, marginTop: 34 }}>
          {s.terms.map((t) => (
            <span key={t} style={{ fontFamily: MONO, fontSize: 26, color: SUB,
                                   border: "1px solid #24303E", borderRadius: 8,
                                   padding: "6px 14px", background: "#0B1219" }}>
              {t}
            </span>
          ))}
        </div>
        <div style={{ ...sample, marginTop: 40, maxWidth: 1040 }}>
          <div style={{ fontSize: 32, color: SUB, lineHeight: 1.45 }}>{s.sample.title}</div>
          <div style={{ fontFamily: MONO, fontSize: 22, color: DIM, marginTop: 12, letterSpacing: 1 }}>
            arXiv:{s.sample.sid}
          </div>
        </div>
      </div>

      <div style={{ position: "absolute", right: 180, top: 250, textAlign: "right", ...num }}>
        <div style={{ fontFamily: MONO, fontSize: 160, fontWeight: 700, color: ACC, lineHeight: 1,
                      textShadow: `0 0 40px rgba(0,212,255,0.35)` }}>
          {Math.round(s.share * 100)}%
        </div>
        <div style={{ fontSize: 40, color: SUB, marginTop: 10 }}>{s.count} 篇</div>
        <div style={{ fontSize: 24, color: DIM, marginTop: 6 }}>占本周全部论文</div>
      </div>
    </AbsoluteFill>
  );
};

/* -------------------------------- 增长卡片 -------------------------------- */

const GrowthCard: React.FC<{ s: Growth }> = ({ s }) => {
  const f = useCurrentFrame();
  const op = interpolate(f, [SEG, SEG + XFADE], [1, 0], clamp);
  const head = enter(f, 6, -60, 0);
  const kicker = enter(f, 16, -40, 0);
  const items = s.items || [];

  return (
    <AbsoluteFill style={{ opacity: op, fontFamily: SANS }}>
      <div style={{ position: "absolute", left: 180, top: 170 }}>
        <div style={{ ...kicker, fontFamily: MONO, fontSize: 22, letterSpacing: 6, color: ACC }}>
          SHIFT {pad2(s.rank)} / {pad2(N)}
        </div>
        <div style={{ ...head, fontSize: 104, fontWeight: 900, color: FG, marginTop: 18 }}>
          本周异常增长
        </div>
        <div style={{ ...head, width: 120, height: 6, background: ACC, marginTop: 26,
                      boxShadow: `0 0 18px rgba(0,212,255,0.7)` }} />
      </div>

      {items.length === 0 ? (
        <div style={{ position: "absolute", left: 180, top: 470, fontSize: 56, color: SUB }}>
          本周没有达到门槛的增长方向
        </div>
      ) : (
        <div style={{ position: "absolute", left: 180, top: 430, width: 1500 }}>
          {items.map((g, i) => {
            const row = enter(f, 34 + i * 12, -30, 0);
            return (
              <div key={g.key} style={{ ...row, display: "flex", alignItems: "baseline",
                                        gap: 28, padding: "18px 0", borderBottom: "1px solid #1B2430" }}>
                <div style={{ fontFamily: MONO, fontSize: 30, color: DIM, width: 60 }}>{pad2(i + 1)}</div>
                <div style={{ fontFamily: MONO, fontSize: 44, color: FG, flex: 1 }}>{g.key}</div>
                <div style={{ fontFamily: MONO, fontSize: 46, color: ACC, width: 190, textAlign: "right" }}>
                  ×{g.ratio.toFixed(2)}
                </div>
                <div style={{ fontSize: 28, color: SUB, width: 190, textAlign: "right" }}>
                  {g.cur} 篇
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div style={{ position: "absolute", left: 180, bottom: 150, fontSize: 26, color: DIM }}>
        口径：本周文档频率 ÷ 按总量缩放后的历史周均值；只报 z ≥ 1.5 且倍数 ≥ 1.2 的方向。
      </div>
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
  const sids = DATA.segments
    .filter((x): x is Topic => x.kind === "topic")
    .map((x) => x.sample.sid)
    .filter(Boolean);

  return (
    <AbsoluteFill style={{ fontFamily: SANS, alignItems: "center", justifyContent: "center" }}>
      <div style={{ ...in1, fontSize: 112, fontWeight: 900, letterSpacing: 2, color: FG,
                    transform: `${in1.transform} scale(${breath})`,
                    textShadow: `0 0 ${glow}px rgba(0,212,255,0.45)` }}>
        关注获取更多
      </div>
      <div style={{ ...in2, fontSize: 32, color: SUB, marginTop: 30 }}>
        本片由 arXiv-daily 自动生成 · 每周日 10:00 更新
      </div>
      <div style={{ ...in3, fontFamily: MONO, fontSize: 22, color: DIM, marginTop: 26,
                    letterSpacing: 1, textAlign: "center" }}>
        {sids.join("   ·   ")}
      </div>
    </AbsoluteFill>
  );
};

/* ---------------------------------- 主合成 ---------------------------------- */

export const TrendReel: React.FC = () => {
  const f = useCurrentFrame();
  const active = Math.min(N - 1, Math.max(0, Math.floor((f - INTRO) / SEG)));

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      {AUDIO_ON ? <Voice id="intro" start={0} /> : null}
      {AUDIO_ON
        ? DATA.segments.map((s, i) => (
            <Voice key={"v" + i} id={"paper" + (i + 1)} start={INTRO + i * SEG} />
          ))
        : null}
      {AUDIO_ON ? <Voice id="outro" start={Math.max(0, DURATION - OUTRO - OUTRO_LEAD)} /> : null}

      <Sequence from={0} durationInFrames={INTRO + XFADE}>
        <Intro />
      </Sequence>

      {f >= INTRO - 30 ? <Rail active={active} /> : null}

      {DATA.segments.map((s, i) => (
        <Sequence key={s.rank} from={INTRO + i * SEG} durationInFrames={SEG + XFADE}>
          {s.kind === "topic" ? <TopicCard s={s} /> : <GrowthCard s={s} />}
        </Sequence>
      ))}

      <Sequence from={DURATION - OUTRO} durationInFrames={OUTRO}>
        <Outro />
      </Sequence>
    </AbsoluteFill>
  );
};
