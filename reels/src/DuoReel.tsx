// A Five Minute AI duo Reel, drawn by Remotion (6 Nov 2026). Python (fma/duo_reel.py) does everything that matters
// for correctness: the script, its fact-checks, the voices, music and timing; it writes the audio and a timeline,
// and this file only draws the pictures from them. If a render fails, Python draws the Reel itself.
import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Audio, continueRender, delayRender, interpolate, spring, staticFile, useCurrentFrame,
        useVideoConfig, Easing} from 'remotion';
import {Doubt, Rex, Spark, Vis} from './Characters';

// Rhubarb's mouth shapes (fma/lipsync.py) as mouth geometry: how open, how wide, teeth showing, tongue up
const SHAPES: Record<string, Vis> = {
  A: {open: 0.04, wide: 0.9, teeth: 0, tongue: 0}, B: {open: 0.22, wide: 1.0, teeth: 1, tongue: 0},
  C: {open: 0.45, wide: 1.05, teeth: 0.5, tongue: 0}, D: {open: 0.85, wide: 1.15, teeth: 0.3, tongue: 1},
  E: {open: 0.5, wide: 0.72, teeth: 0, tongue: 0}, F: {open: 0.28, wide: 0.48, teeth: 0, tongue: 0},
  G: {open: 0.18, wide: 0.95, teeth: 1, tongue: 0}, H: {open: 0.42, wide: 0.95, teeth: 0.3, tongue: 1},
  X: {open: 0.06, wide: 0.85, teeth: 0, tongue: 0},
};

const shapeAt = (cues: any[] | undefined, t: number): Vis | null => {
  if (!cues || !cues.length) return null;
  let k = -1;
  for (let i = 0; i < cues.length; i++) { if (cues[i][0] <= t) k = i; else break; }
  if (k < 0 || t > cues[k][1] + 0.05) return SHAPES.X;
  const cur = SHAPES[cues[k][2]] ?? SHAPES.X;
  const prev = k > 0 && cues[k - 1][1] >= cues[k][0] - 0.02 ? SHAPES[cues[k - 1][2]] ?? SHAPES.X : SHAPES.X;
  const m = Math.min(1, (t - cues[k][0]) / 0.06);              // ease from the last shape over about two frames
  const mix = (a: number, b: number) => a + (b - a) * m;
  return {open: mix(prev.open, cur.open), wide: mix(prev.wide, cur.wide), teeth: mix(prev.teeth, cur.teeth), tongue: mix(prev.tongue, cur.tongue)};
};

export type Timeline = any;

const INK = '#F6F2FF', YELLOW = '#FFD65A', MUTED = '#A8A2C8', NIGHT = '#120E2A';
const HI: Record<string, string> = {spark: YELLOW, doubt: '#A0B2FF', rex: '#98D88C'};
const TAG: Record<string, string> = {spark: 'SPARK', doubt: 'DOUBT', rex: 'REX'};
const WASH = ['#FF7860', '#40D6C4', '#946EFF', '#FFB347'];

type Line = any;

const useFonts = () => {
  const [handle] = useState(() => delayRender('fonts'));
  useEffect(() => {
    const faces = [new FontFace('Bricolage', `url(${staticFile('Bricolage.ttf')})`, {weight: '200 800'}),
                   new FontFace('Inter', `url(${staticFile('Inter.ttf')})`, {weight: '100 900'})];
    Promise.all(faces.map((f) => f.load())).then((fs) => { fs.forEach((f) => (document.fonts as any).add(f)); continueRender(handle); });
  }, [handle]);
};

const rnd = (i: number) => { const x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); };

const Background: React.FC<{t: number; i: number; since: number}> = ({t, i, since}) => {
  const k = Math.min(1, since / 0.8);
  const a = WASH[(i + 3) % 4], b = WASH[i % 4];
  return (
    <AbsoluteFill style={{background: `linear-gradient(180deg, ${NIGHT} 0%, #1E1438 55%, #2A1240 100%)`}}>
      {[{c: a, o: 1 - k}, {c: b, o: k}].map((w, n) => (
        <AbsoluteFill key={n} style={{opacity: w.o * 0.55,
          background: `radial-gradient(circle at ${50 + 18 * Math.sin(t * 0.25)}% ${42 + 8 * Math.cos(t * 0.2)}%, ${w.c}55 0%, transparent 55%)`}} />
      ))}
      {Array.from({length: 46}, (_, d) => {
        const depth = 0.3 + rnd(d) * 0.7;
        const y = ((rnd(d + 99) * 2000 - t * 18 * depth) % 2000 + 2000) % 2000 - 40;
        const x = rnd(d + 7) * 1080 + Math.sin(t * 0.5 + d) * 12;
        const s = 4 + depth * 16;
        return <div key={d} style={{position: 'absolute', left: x, top: y, width: s, height: s, borderRadius: '50%',
          background: WASH[d % 4], opacity: 0.08 + 0.22 * depth, filter: `blur(${(1 - depth) * 6}px)`}} />;
      })}
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,0.45) 100%)'}} />
    </AbsoluteFill>
  );
};

const Caption: React.FC<{line: Line; lt: number; fps: number}> = ({line, lt, fps}) => {
  const groups = line.groups;
  let g = 0;
  groups.forEach((grp, k) => { if (grp[0].t <= lt + 0.05) g = k; });
  const words = groups[g];
  const cur = words.reduce((acc, w, k) => (w.t <= lt ? k : acc), -1);
  return (
    <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '6px 14px', padding: '0 70px'}}>
      {words.map((w, k) => {
        const shown = lt >= w.t - 0.06;
        const s = shown ? spring({frame: Math.max(0, (lt - w.t + 0.06) * fps), fps, config: {damping: 11, stiffness: 180}}) : 0;
        const on = k === cur;
        return (
          <span key={k} style={{fontFamily: 'Bricolage', fontWeight: 800, fontSize: 92, lineHeight: 1.15, color: on ? NIGHT : INK,
            padding: '0 14px', borderRadius: 18, background: on ? HI[line.who] : 'transparent',
            transform: `translateY(${(1 - s) * 26}px) scale(${0.7 + 0.3 * s})`, opacity: s,
            textShadow: on ? 'none' : '0 4px 18px rgba(0,0,0,0.45)', display: 'inline-block'}}>{w.w}</span>
        );
      })}
    </div>
  );
};

const Logo: React.FC<{p: number; sweep: number}> = ({p, sweep}) => {
  const r = 120, c = 2 * Math.PI * r;
  const a = (-90 + 60 * sweep) * Math.PI / 180;
  const ex = 150 + 100 * Math.cos(a), ey = 150 + 100 * Math.sin(a);
  return (
    <svg width={300} height={300} viewBox="0 0 300 300" style={{transform: `scale(${0.7 + 0.3 * p}) rotate(${(1 - p) * -40}deg)`, opacity: p}}>
      <circle cx="150" cy="150" r={r} fill="none" stroke="#FF7A3C" strokeWidth="26" strokeLinecap="round"
              strokeDasharray={c} strokeDashoffset={c * (1 - p)} transform="rotate(-90 150 150)" />
      {sweep > 0 && <path d={`M150 150 L150 50 A100 100 0 0 1 ${ex.toFixed(1)} ${ey.toFixed(1)} Z`} fill="#FF7A3C" />}
    </svg>
  );
};

const CONFETTI = ['#FFD65A', '#FF8460', '#40D6C4', '#946EFF', '#FAFAFF'];

const Confetti: React.FC<{since: number; flop: number | null}> = ({since, flop}) => (
  <AbsoluteFill>
    {Array.from({length: 110}, (_, k) => {
      const ang = -Math.PI * (0.08 + 0.84 * rnd(k + 3));
      const sp = 900 + 1200 * rnd(k + 11);
      const e = (1 - Math.exp(-3.2 * since)) / 3.2;
      let x = 540 + Math.cos(ang) * sp * e + 40 * Math.sin(since * 3 + k);
      let y = 900 + Math.sin(ang) * sp * e + (110 + 100 * rnd(k)) * since;
      let o = Math.min(1, since / 0.08);
      if (flop !== null) { y += 900 * flop * flop; o *= Math.max(0, 1 - flop / 0.9); }
      const w = 8 + 18 * Math.abs(Math.sin(since * 5 + k));
      return o > 0 && y < 1920 ? <div key={k} style={{position: 'absolute', left: x - w / 2, top: y - 9, width: w, height: 18,
        background: CONFETTI[k % 5], opacity: o, transform: `rotate(${since * 200 + k * 37}deg)`}} /> : null;
    })}
  </AbsoluteFill>
);

const Panel: React.FC<{text: string; p: number; fade: number; t: number}> = ({text, p, fade, t}) => {
  const s = Math.min(1, p);
  const flick = p < 0.35 ? (Math.sin(t * 90) > 0 ? 1 : 0.35) : 1;     // switches on with a flicker
  return (
    <div style={{position: 'absolute', top: 470, width: '100%', display: 'flex', justifyContent: 'center', opacity: fade * flick}}>
      <div style={{padding: '18px 56px', borderRadius: 26, border: '4px solid #40D6C4', background: 'rgba(20,28,60,0.72)',
        boxShadow: '0 0 40px rgba(64,214,196,0.45), inset 0 0 30px rgba(64,214,196,0.18)',
        transform: `scaleY(${0.2 + 0.8 * s}) translateY(${(1 - s) * 40}px)`}}>
        <span style={{fontFamily: 'Bricolage', fontWeight: 800, fontSize: text.length > 8 ? 120 : 190, color: '#FFD65A',
          textShadow: '0 0 24px rgba(255,214,90,0.55)'}}>{text}</span>
      </div>
    </div>
  );
};

export const DuoReel: React.FC<{timeline: Timeline; audio: string}> = ({timeline, audio}) => {
  useFonts();
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const lines = timeline.lines;
  let i = 0;
  lines.forEach((ln, k) => { if (ln.start <= t) i = k; });
  const line = lines[i];
  const lt = t - line.start;
  const guest = timeline.guest;
  const cardFrom = lines.find((ln) => ln.card)?.start ?? timeline.seconds + 1;
  const onCard = t >= cardFrom;
  const cp = onCard ? interpolate(t - cardFrom, [0, 0.7], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)}) : 0;
  const lastStory = Math.max(...lines.map((ln, k) => (ln.card ? -1 : k)));
  const facing = onCard || i >= lastStory;
  const pop = spring({frame: Math.max(0, lt * fps), fps, config: {damping: 9, stiffness: 140}});

  // the camera eases toward whoever is talking, and pushes in slowly
  const focus = facing ? 0 : line.who === 'spark' ? -1 : 1;
  const pan = spring({frame: Math.max(0, lt * fps), fps, config: {damping: 20, stiffness: 60}});
  const camX = -focus * 40 * pan;
  const zoom = 1.04 + 0.025 * Math.min(1, lt / 3);

  const mouthAt = (who: string) => { const m = (timeline.mouth as any)[who] as number[]; return m[Math.min(m.length - 1, frame)] ?? 0; };
  const sweat = lines.find((ln) => ln.tags.includes('sweat'));
  const sweatT = sweat && t >= sweat.start ? t - sweat.start : 0;

  const char = (who: string) => {
    const talking = who === line.who;
    const isSpark = who === 'spark';
    const base = {x: isSpark ? 330 : 790, y: isSpark ? 1110 : 1100, size: isSpark ? 400 : 330};
    const y = base.y + 230 * cp, size = base.size * (1 - 0.3 * cp);
    const s = talking ? 1 + 0.07 * pop : 0.95;
    const look = facing ? 0 : isSpark ? 1 : -1;
    const bob = Math.sin(t * 2.2 + (isSpark ? 0 : 1.7)) * 6;
    const vis = shapeAt((timeline.visemes || {})[who], t);
    const props = {t, mouth: mouthAt(who), talking, look, pop: talking ? 1 - pop : 0, vis};
    return (
      <div key={who} style={{position: 'absolute', left: base.x - size / 2, top: y - size + bob, width: size, height: size * 1.05,
        transform: `scale(${s})`, transformOrigin: '50% 100%', opacity: talking || onCard ? 1 : 0.92,
        filter: talking || onCard ? 'none' : 'brightness(0.94)'}}>
        {isSpark ? <Spark {...props} sweat={sweatT} /> : guest === 'rex' ? <Rex {...props} /> : <Doubt {...props} />}
      </div>
    );
  };

  const order = line.who === 'spark' ? [guest, 'spark'] : ['spark', guest];

  // the number panel: the figure Spark is saying rises in as it is said, and switches off when Spark moves on to a
  // line without one (an old number under a new fact misleads); while the guest reacts it stays up
  let panel: {text: string; at: number} | null = lines[0].fig ? {text: lines[0].fig, at: -9} : null;
  let off: number | null = null;
  for (let k = 0; k <= i; k++) {
    const ln = lines[k];
    if (ln.card) { if (panel && off === null) off = ln.start; continue; }
    if (ln.fig && k > 0) { const at = ln.start + ln.figAt - 0.25; if (t >= at && (!panel || panel.text !== ln.fig)) { panel = {text: ln.fig, at}; off = null; } }
    else if (ln.who === 'spark' && !ln.fig && k > 0 && panel && off === null && t >= ln.start) off = ln.start;
  }
  const fade = off === null ? 1 : Math.max(0, 1 - (t - off) / 0.3);
  const party = lines.find((ln) => ln.tags.includes('confetti'));
  const flopLine = party ? lines.find((ln) => ln.tags.includes('drop') && ln.start > party.start) : undefined;
  const slogan = lines.find((ln) => ln.card && ln.who !== 'spark');
  const sticker = slogan ? lines.find((ln) => ln.card && ln.start > slogan.start) : undefined;
  const sp = slogan && t >= slogan.start ? spring({frame: (t - slogan.start) * fps, fps, config: {damping: 12, stiffness: 160}}) : 0;
  const st = sticker && t >= sticker.start ? spring({frame: (t - sticker.start) * fps, fps, config: {damping: 7, stiffness: 220}}) : 0;

  return (
    <AbsoluteFill style={{backgroundColor: NIGHT}}>
      <Audio src={staticFile(audio)} />
      <AbsoluteFill style={{transform: `translateX(${camX}px) scale(${zoom})`}}>
        <Background t={t} i={i} since={lt} />
        {/* header */}
        <div style={{position: 'absolute', left: 90, right: 90, top: 290, opacity: 1 - cp}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
            <span style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 32, letterSpacing: 1, color: YELLOW}}>{timeline.site}</span>
            <span style={{fontFamily: 'Inter', fontWeight: 700, fontSize: 28, color: INK, border: `3px solid ${INK}cc`, borderRadius: 30, padding: '6px 24px'}}>{timeline.label}</span>
          </div>
          <div style={{marginTop: 26, height: 8, borderRadius: 4, background: `${INK}33`}}>
            <div style={{height: 8, borderRadius: 4, background: INK, width: `${100 * Math.min(1, t / cardFrom)}%`}} />
          </div>
        </div>
        {panel && fade > 0 && !onCard && <Panel text={panel.text} p={(t - panel.at) / 0.6} fade={fade} t={t} />}
        {order.map(char)}
        {party && t >= party.start && <Confetti since={t - party.start} flop={flopLine && t >= flopLine.start ? t - flopLine.start : null} />}
        {/* the logo card */}
        {onCard && (
          <div style={{position: 'absolute', top: 470, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
            <Logo p={cp} sweep={interpolate(t - cardFrom, [0.2, 1.0], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)})} />
            <div style={{fontFamily: 'Bricolage', fontWeight: 800, fontSize: 96, color: INK, marginTop: 30, opacity: cp, transform: `translateY(${(1 - cp) * 30}px)`}}>Five Minute AI</div>
            {sp > 0 && <div style={{marginTop: 22, fontFamily: 'Bricolage', fontWeight: 800, fontSize: 62, color: NIGHT, background: YELLOW,
              borderRadius: 32, padding: '10px 34px', transform: `scale(${0.6 + 0.4 * sp})`, opacity: Math.min(1, sp * 2)}}>{slogan!.text}</div>}
          </div>
        )}
        {st > 0 && (
          <div style={{position: 'absolute', left: 560, top: 1110, fontFamily: 'Bricolage', fontWeight: 800, fontSize: 92, color: '#fff',
            background: '#FF845F', borderRadius: 22, padding: '6px 34px', boxShadow: '0 12px 30px rgba(0,0,0,0.35)',
            transform: `rotate(-9deg) scale(${0.4 + 0.6 * st})`}}>{sticker!.text}</div>
        )}
        {/* name tag and captions */}
        {!onCard && (
          <div style={{position: 'absolute', top: 1140, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22}}>
            <span style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 30, color: NIGHT, background: HI[line.who], borderRadius: 24,
              padding: '6px 22px', transform: `scale(${0.85 + 0.15 * pop})`}}>{TAG[line.who]}</span>
            <Caption line={line} lt={lt} fps={fps} />
          </div>
        )}
        <div style={{position: 'absolute', bottom: 330, width: '100%', textAlign: 'center', fontFamily: 'Inter', fontSize: 32,
          color: MUTED, opacity: onCard ? 0 : 1}}>Source: {timeline.source}</div>
        {onCard && <div style={{position: 'absolute', top: 1470, width: '100%', textAlign: 'center', fontFamily: 'Inter', fontWeight: 800,
          fontSize: 42, color: INK, opacity: cp}}>Follow @fiveminute_ai</div>}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
