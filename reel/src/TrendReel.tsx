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

type Sample = { sid: string; title: string; short: string; note: string };
type Topic = {
  kind: "topic";
  rank: number;
  label: string;
  terms: string[];
  term_weights?: number[];
  count: number;
  share: number;
  samples?: Sample[];
  sample?: { sid: string; title: string };
};
type Word = { text: string; weight: number; count: number };
type Cloud = { kind: "cloud"; rank: number; words: Word[] };
type GrowthItem = { key: string; cur: number; ratio: number; z: number };
type Growth = { kind: "growth"; rank: number; items: GrowthItem[] };
type Segment = Cloud | Topic | Growth;

type Category = { cat: string; name: string; count: number; share: number };
type Data = {
  issue: string;
  window: { start?: string; end?: string };
  generated: string;
  stats: { total: number; cats: number; clusters: number; growth: number };
  categories?: Category[];
  cloud?: Word[];
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
const BLUE = "#4F9DFF"; // 「最接近的工作」小字：比强调色更柔，避免和标题抢注意力
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

/* --------------------------------- 图表 ---------------------------------- */

/** 水平柱状图：一条柱子 + 数值，宽度按比例动画到目标值。 */
const Bar: React.FC<{
  label: string;
  value: number;
  max: number;
  width?: number;
  color?: string;
  delay?: number;
  suffix?: string;
  mono?: boolean;
}> = ({ label, value, max, width = 420, color = ACC, delay = 0, suffix = "", mono = false }) => {
  const f = useCurrentFrame();
  const p = interpolate(f, [delay, delay + 26], [0, 1], clamp);
  const ratio = max > 0 ? Math.max(0.02, Math.min(1, value / max)) : 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 16 }}>
      <div style={{ width: 210, fontSize: 24, color: SUB, fontFamily: mono ? MONO : SANS,
                    textAlign: "right", whiteSpace: "nowrap", overflow: "hidden" }}>
        {label}
      </div>
      <div style={{ width, height: 22, background: "#0E1620", borderRadius: 4, overflow: "hidden" }}>
        <div style={{ width: width * ratio * p, height: "100%", background: color,
                      boxShadow: `0 0 14px ${color}55` }} />
      </div>
      <div style={{ fontFamily: MONO, fontSize: 24, color: DIM, minWidth: 90 }}>
        {value}
        {suffix}
      </div>
    </div>
  );
};

/** 扇形图（环形）：主题占比 vs 其余。 */
const Donut: React.FC<{ share: number; size?: number; delay?: number }> = ({
  share,
  size = 320,
  delay = 18,
}) => {
  const f = useCurrentFrame();
  const p = interpolate(f, [delay, delay + 34], [0, 1], clamp);
  const r = size / 2 - 22;
  const c = 2 * Math.PI * r;
  const frac = Math.max(0, Math.min(1, share)) * p;
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#141C26" strokeWidth={26} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={ACC}
        strokeWidth={26}
        strokeLinecap="round"
        strokeDasharray={`${c * frac} ${c}`}
        style={{ filter: "drop-shadow(0 0 10px rgba(0,212,255,0.45))" }}
      />
    </svg>
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
  const barW = interpolate(s, [0, 1], [0, 460], clamp);
  const sub = enter(f, 30, 0, 34);
  const stats = enter(f, 44, 0, 30);
  const chart = enter(f, 22, 40, 0);
  const win = DATA.window || {};
  const cats = (DATA.categories || []).slice(0, 6);
  const maxCat = cats.reduce((m, c) => Math.max(m, c.count), 0);

  return (
    <AbsoluteFill style={{ opacity: op, fontFamily: SANS }}>
      <div style={{ position: "absolute", left: 180, top: 230, width: 800 }}>
        <div style={{ fontFamily: MONO, fontSize: 24, letterSpacing: 8, color: ACC,
                      opacity: interpolate(f, [0, 14], [0, 1], clamp) }}>
          ARXIV · CS.* · WEEKLY TREND
        </div>
        <div style={{ fontSize: 132, fontWeight: 900, letterSpacing: -4, lineHeight: 1, color: FG,
                      marginTop: 26, transform: `translateY(${titleY}px)`,
                      opacity: interpolate(f, [0, 10], [0, 1], clamp) }}>
          本周趋势
        </div>
        <div style={{ width: barW, height: 6, background: ACC, marginTop: 26,
                      boxShadow: `0 0 22px rgba(0,212,255,0.7)` }} />
        <div style={{ ...sub, fontSize: 36, color: SUB, marginTop: 30 }}>
          第 {DATA.issue} 期 · {win.start} → {win.end}
        </div>
        <div style={{ ...stats, display: "flex", gap: 40, marginTop: 26, fontFamily: MONO,
                      fontSize: 26, color: DIM }}>
          <span>论文 <span style={{ color: FG }}>{DATA.stats.total}</span></span>
          <span>分类 <span style={{ color: FG }}>{DATA.stats.cats}</span></span>
          <span>主题簇 <span style={{ color: FG }}>{DATA.stats.clusters}</span></span>
        </div>
      </div>

      <div style={{ position: "absolute", left: 180, bottom: 96, fontFamily: MONO,
                    fontSize: 22, color: DIM, letterSpacing: 1,
                    opacity: interpolate(f, [40, 60], [0, 1], clamp) }}>
        数据：arXiv cs.* 全量 · 仅取标题 / 摘要 / 分类 · 每周日 10:00 更新
      </div>

      <div style={{ position: "absolute", left: 1130, top: 246, width: 660, ...chart }}>
        <div style={{ fontFamily: MONO, fontSize: 20, letterSpacing: 5, color: DIM }}>
          TOP CATEGORIES
        </div>
        <div style={{ marginTop: 26 }}>
          {cats.map((c, i) => (
            <Bar key={c.cat} label={c.name || c.cat} value={c.count} max={maxCat}
                 width={330} delay={40 + i * 6} suffix=" 篇" />
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* --------------------------------- 高频词 --------------------------------- */

const CloudCard: React.FC<{ s: Cloud }> = ({ s }) => {
  const f = useCurrentFrame();
  const op = interpolate(f, [SEG, SEG + XFADE], [1, 0], clamp);
  const head = enter(f, 6, -60, 0);
  const words = (s.words || []).slice(0, 26);

  return (
    <AbsoluteFill style={{ opacity: op, fontFamily: SANS }}>
      <div style={{ position: "absolute", left: 180, top: 150 }}>
        <div style={{ ...head, fontFamily: MONO, fontSize: 22, letterSpacing: 6, color: ACC }}>
          WORD CLOUD {pad2(s.rank)} / {pad2(N)}
        </div>
        <div style={{ ...head, fontSize: 84, fontWeight: 900, color: FG, marginTop: 16 }}>
          本周高频词
        </div>
        <div style={{ ...head, width: 120, height: 6, background: ACC, marginTop: 22,
                      boxShadow: `0 0 18px rgba(0,212,255,0.7)` }} />
        <div style={{ ...head, fontSize: 26, color: DIM, marginTop: 20 }}>
          字号 = 出现该词的论文数；已剔除通用词与重复词形
        </div>
      </div>

      <div style={{
        position: "absolute", left: 180, top: 400, width: 1560, height: 520,
        display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "center",
        gap: "10px 30px", alignContent: "center",
      }}>
        {words.map((w, i) => {
          const size = 26 + Math.round(58 * (w.weight || 0));
          const color = i < 4 ? ACC : i < 10 ? FG : SUB;
          const st = enter(f, 18 + i * 3, 0, 18);
          return (
            <span key={w.text} style={{ ...st, fontSize: size, lineHeight: 1.1,
                                        color, fontWeight: i < 4 ? 800 : 600,
                                        textShadow: i < 4 ? "0 0 24px rgba(0,212,255,0.25)" : "none" }}>
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* -------------------------------- 主题卡片 -------------------------------- */

const TopicCard: React.FC<{ s: Topic; total: number }> = ({ s, total }) => {
  const f = useCurrentFrame();
  const op = interpolate(f, [SEG, SEG + XFADE], [1, 0], clamp);
  const head = enter(f, 6, -60, 0);
  const kicker = enter(f, 16, -40, 0);
  const chips = enter(f, 30, 0, 24);
  const chart = enter(f, 22, 40, 0);
  const samples = (s.samples || []).slice(0, 3);
  const peers = DATA.segments
    .filter((x): x is Topic => x.kind === "topic")
    .sort((a, b) => b.count - a.count)
    .slice(0, 4);
  const maxPeer = peers.reduce((m, p) => Math.max(m, p.count), 1);

  return (
    <AbsoluteFill style={{ opacity: op, fontFamily: SANS }}>
      <div style={{ position: "absolute", left: 180, top: 112, width: 1120 }}>
        <div style={{ ...kicker, fontFamily: MONO, fontSize: 22, letterSpacing: 6, color: ACC }}>
          TOPIC {pad2(s.rank)} / {pad2(total)}
        </div>
        <div style={{ ...head, fontSize: 84, fontWeight: 900, lineHeight: 1.08, color: FG, marginTop: 12 }}>
          {s.label}
        </div>
        <div style={{ ...head, width: 120, height: 6, background: ACC, marginTop: 18,
                      boxShadow: `0 0 18px rgba(0,212,255,0.7)` }} />
        <div style={{ ...chips, display: "flex", flexWrap: "wrap", gap: 10, marginTop: 20 }}>
          {s.terms.slice(0, 5).map((t) => (
            <span key={t} style={{ fontFamily: MONO, fontSize: 22, color: SUB,
                                   border: "1px solid #24303E", borderRadius: 8,
                                   padding: "5px 12px", background: "#0B1219" }}>
              {t}
            </span>
          ))}
        </div>

        <div style={{ ...chips, marginTop: 30, fontFamily: MONO, fontSize: 21,
                      letterSpacing: 4, color: DIM }}>
          最接近的三项工作
        </div>
        <div style={{ marginTop: 14 }}>
          {samples.map((p, i) => {
            const row = enter(f, 44 + i * 10, -24, 0);
            return (
              <div key={p.sid || i} style={{ ...row, display: "flex", gap: 20,
                                             padding: "15px 0", borderBottom: "1px solid #131C26" }}>
                <div style={{ fontFamily: MONO, fontSize: 24, color: ACC, width: 36,
                              paddingTop: 4 }}>
                  {pad2(i + 1)}
                </div>
                <div style={{ width: 1030 }}>
                  <div style={{ fontSize: 29, color: SUB, lineHeight: 1.3,
                                overflow: "hidden", display: "-webkit-box",
                                WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                    {p.title}
                  </div>
                  <div style={{ fontFamily: MONO, fontSize: 18, color: "#55606E", marginTop: 4 }}>
                    arXiv:{p.sid}
                  </div>
                  {p.note ? (
                    <div style={{ fontSize: 26, color: BLUE, marginTop: 6, lineHeight: 1.35 }}>
                      {p.note}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ position: "absolute", right: 190, top: 250, width: 380, textAlign: "center",
                    ...chart }}>
        <div style={{ position: "relative", width: 320, height: 320, margin: "0 auto" }}>
          <Donut share={s.share} />
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column",
                        alignItems: "center", justifyContent: "center" }}>
            <div style={{ fontFamily: MONO, fontSize: 76, fontWeight: 700, color: ACC,
                          textShadow: `0 0 40px rgba(0,212,255,0.35)` }}>
              {Math.round(s.share * 100)}%
            </div>
            <div style={{ fontSize: 24, color: SUB, marginTop: 2 }}>占本周</div>
          </div>
        </div>
        <div style={{ fontSize: 40, color: FG, marginTop: 18 }}>{s.count} 篇</div>
        <div style={{ fontSize: 22, color: DIM, marginTop: 4 }}>全部 {DATA.stats.total} 篇中的占比</div>

        <div style={{ marginTop: 42, textAlign: "left" }}>
          <div style={{ fontFamily: MONO, fontSize: 16, letterSpacing: 3, color: DIM,
                        marginBottom: 10, textAlign: "right" }}>
            主题规模对比
          </div>
          {peers.map((p) => (
            <div key={p.rank} style={{ display: "flex", alignItems: "center", gap: 8,
                                       marginTop: 7, justifyContent: "flex-end" }}>
              <div style={{ width: 128, fontSize: 17, textAlign: "right",
                            color: p.rank === s.rank ? FG : DIM,
                            whiteSpace: "nowrap", overflow: "hidden" }}>
                {p.label.split(" / ")[0]}
              </div>
              <div style={{ width: 140, height: 10, background: "#0E1620", borderRadius: 2 }}>
                <div style={{ width: (140 * p.count) / maxPeer, height: "100%",
                              background: p.rank === s.rank ? ACC : "#24303E" }} />
              </div>
              <div style={{ fontFamily: MONO, fontSize: 16, color: DIM, width: 44,
                            textAlign: "right" }}>
                {p.count}
              </div>
            </div>
          ))}
        </div>
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
  // 柱长从 1.0 起算：所有上榜方向都 ≥1.2，按绝对值画会四条都顶满，看不出差别。
  const maxOver = items.reduce((m, g) => Math.max(m, g.ratio - 1), 0.01);
  const maxBar = 760;

  return (
    <AbsoluteFill style={{ opacity: op, fontFamily: SANS }}>
      <div style={{ position: "absolute", left: 180, top: 150 }}>
        <div style={{ ...kicker, fontFamily: MONO, fontSize: 22, letterSpacing: 6, color: ACC }}>
          SHIFT {pad2(s.rank)} / {pad2(N)}
        </div>
        <div style={{ ...head, fontSize: 96, fontWeight: 900, color: FG, marginTop: 16 }}>
          本周异常增长
        </div>
        <div style={{ ...head, width: 120, height: 6, background: ACC, marginTop: 24,
                      boxShadow: `0 0 18px rgba(0,212,255,0.7)` }} />
      </div>

      {items.length === 0 ? (
        <div style={{ position: "absolute", left: 180, top: 470, fontSize: 56, color: SUB }}>
          本周没有达到门槛的增长方向
        </div>
      ) : (
        <div style={{ position: "absolute", left: 180, top: 420, width: 1560 }}>
          <div style={{ display: "flex", fontFamily: MONO, fontSize: 18, color: DIM,
                        letterSpacing: 3, marginBottom: 12, paddingLeft: 58 }}>
            <span style={{ width: 380 }}>方向</span>
            <span>相对一周均值的倍数</span>
          </div>
          {items.map((g, i) => {
            const row = enter(f, 26 + i * 10, -30, 0);
            const p = interpolate(f, [34 + i * 10, 64 + i * 10], [0, 1], clamp);
            const w = maxOver > 0 ? ((g.ratio - 1) / maxOver) * maxBar * p : 0;
            return (
              <div key={g.key} style={{ ...row, display: "flex", alignItems: "center",
                                        gap: 20, padding: "14px 0", borderBottom: "1px solid #1B2430" }}>
                <div style={{ fontFamily: MONO, fontSize: 28, color: DIM, width: 38 }}>{pad2(i + 1)}</div>
                <div style={{ fontFamily: MONO, fontSize: 40, color: FG, width: 340 }}>{g.key}</div>
                <div style={{ width: maxBar, height: 26, background: "#0E1620", borderRadius: 4 }}>
                  <div style={{ width: w, height: "100%", background: ACC,
                                boxShadow: `0 0 16px rgba(0,212,255,0.35)` }} />
                </div>
                <div style={{ fontFamily: MONO, fontSize: 42, color: ACC, width: 170, textAlign: "right" }}>
                  ×{g.ratio.toFixed(2)}
                </div>
                <div style={{ fontSize: 26, color: SUB, width: 130, textAlign: "right" }}>
                  {g.cur} 篇
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div style={{ position: "absolute", left: 180, bottom: 120, fontSize: 26, color: DIM }}>
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
    .map((x) => (x.samples && x.samples[0] ? x.samples[0].sid : x.sample?.sid || ""))
    .filter(Boolean)
    .slice(0, 8);

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
  const topicTotal = DATA.segments.filter((s) => s.kind === "topic").length;

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
          {s.kind === "cloud" ? (
            <CloudCard s={s} />
          ) : s.kind === "topic" ? (
            <TopicCard s={s} total={topicTotal} />
          ) : (
            <GrowthCard s={s} />
          )}
        </Sequence>
      ))}

      <Sequence from={DURATION - OUTRO} durationInFrames={OUTRO}>
        <Outro />
      </Sequence>
    </AbsoluteFill>
  );
};
