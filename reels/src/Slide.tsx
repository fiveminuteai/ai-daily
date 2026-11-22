// The daily carousel, drawn like the Reels (22 Nov 2026, Pavan: the carousel "looks cheap as if there is no content
// left ... apply same rules of reels to carousel too"). Same night palette, fonts and cast as the Reels; each slide
// says one thing in big plain words: a short hook line with its key words lit up, two plain points, and the guest's
// reaction in a bubble. Instagram's 4:5 carousel size (1080x1350). Python builds the props (fma/carousel_reel.py).
import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {Background, INK, MUTED, NIGHT, YELLOW, useFonts} from './DuoReel';
import {Doubt, Rex, Spark} from './Characters';

export type SlideProps = {
  kind: 'cover' | 'story' | 'close';
  n: number; total: number;            // slide number and count, for the dots
  title: string; hi: string;           // the big line and the words to light up
  points: string[];                    // story: up to two plain lines
  kicker: string;                      // small line above the title
  label: string;                       // the topic chip
  bubble: string | null;               // the guest's line
  guest: string;                       // doubt | rex | solo
  source: string;                      // "Source: The Verge"
  others: string[];                    // cover: the other stories' short lines
  fig?: string;                        // story: its key number, shown big (as the Reels pop numbers)
};

const still = {t: 1.3, talking: false, pop: 0, vis: null};

const Lit: React.FC<{title: string; hi: string; size: number; align?: 'left' | 'center'}> = ({title, hi, size, align = 'left'}) => {
  const at = hi ? title.toLowerCase().indexOf(hi.toLowerCase()) : -1;
  const parts = at < 0 ? [{s: title, on: false}] : [{s: title.slice(0, at), on: false},
    {s: title.slice(at, at + hi.length), on: true}, {s: title.slice(at + hi.length), on: false}];
  return (
    <div style={{fontFamily: 'Bricolage', fontWeight: 800, fontSize: size, lineHeight: 1.12, color: INK, letterSpacing: -1.5,
      textAlign: align, textShadow: '0 8px 30px rgba(0,0,0,0.45)'}}>
      {parts.map((p, k) => p.on
        ? <span key={k} style={{background: YELLOW, color: NIGHT, padding: '0 14px', borderRadius: 16,
            boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone'}}>{p.s}</span>
        : <span key={k}>{p.s}</span>)}
    </div>
  );
};

const size = (s: string, big: number) => {
  const n = s.length;
  return n <= 20 ? big : n <= 36 ? big * 0.84 : n <= 52 ? big * 0.72 : n <= 70 ? big * 0.62 : big * 0.54;
};

const Bubble: React.FC<{text: string; style: React.CSSProperties; tail?: 'left' | 'right'}> = ({text, style, tail = 'right'}) => (
  <div style={{position: 'absolute', background: '#fff', color: NIGHT, borderRadius: 30, padding: '18px 30px',
    fontFamily: 'Bricolage', fontWeight: 800, fontSize: 40, lineHeight: 1.1, boxShadow: '0 14px 34px rgba(0,0,0,0.4)', ...style}}>
    {text}
    <div style={{position: 'absolute', [tail]: 70, bottom: -24, width: 0, height: 0, borderLeft: '20px solid transparent',
      borderRight: '20px solid transparent', borderTop: '28px solid #fff'} as React.CSSProperties} />
  </div>
);

const Head: React.FC<{label: string; kicker: string}> = ({label, kicker}) => (
  <div style={{position: 'absolute', left: 80, right: 80, top: 70, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
    <span style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 30, letterSpacing: 1, color: YELLOW}}>{kicker}</span>
    {label && <span style={{fontFamily: 'Inter', fontWeight: 700, fontSize: 26, color: INK, border: `3px solid ${INK}cc`,
      borderRadius: 30, padding: '5px 20px'}}>{label}</span>}
  </div>
);

const Dots: React.FC<{n: number; total: number}> = ({n, total}) => (
  <div style={{position: 'absolute', right: 80, bottom: 62, display: 'flex', gap: 10}}>
    {Array.from({length: total}, (_, k) => <div key={k} style={{width: k === n - 1 ? 30 : 12, height: 12, borderRadius: 6,
      background: k === n - 1 ? YELLOW : `${MUTED}88`}} />)}
  </div>
);

export const Slide: React.FC<SlideProps> = (p) => {
  useFonts();
  const G = p.guest === 'rex' ? Rex : Doubt;
  const duo = p.guest !== 'solo';
  return (
    <AbsoluteFill style={{backgroundColor: NIGHT}}>
      <Background t={1.3} i={p.n} since={0} />
      <Head label={p.label} kicker={p.kicker} />

      {p.kind === 'cover' && (<>
        <div style={{position: 'absolute', left: 80, right: 80, top: 150, bottom: 560, display: 'flex', alignItems: 'center'}}>
          <Lit title={p.title} hi={p.hi} size={size(p.title, 150)} />
        </div>
        <div style={{position: 'absolute', left: 80, width: 520, bottom: 150, fontFamily: 'Inter', fontWeight: 700, fontSize: 31,
          color: INK, lineHeight: 1.3}}>
          <div style={{color: MUTED, fontSize: 26, fontWeight: 800, letterSpacing: 1, marginBottom: 14}}>ALSO TODAY</div>
          {p.others.map((o, k) => <div key={k} style={{display: 'flex', gap: 14, marginBottom: 14}}>
            <span style={{color: YELLOW, fontWeight: 900}}>{`0${k + 2}`}</span><span>{o}</span></div>)}
        </div>
        <div style={{position: 'absolute', left: 640, bottom: 150, width: 250, height: 262}}><Spark {...still} mouth={0.3} look={1} /></div>
        {duo && <div style={{position: 'absolute', left: 860, bottom: 150, width: 190, height: 200}}><G {...still} mouth={0.4} look={-1} talking /></div>}
        {p.bubble && <Bubble text={p.bubble} style={{right: 50, bottom: 450, maxWidth: 400, fontSize: 34, transform: 'rotate(2deg)'}} />}
        <div style={{position: 'absolute', left: 80, bottom: 62, fontFamily: 'Bricolage', fontWeight: 800, fontSize: 46, color: YELLOW}}>
          Swipe →
        </div>
      </>)}

      {p.kind === 'story' && (<>
        <div style={{position: 'absolute', left: 80, right: 80, top: 150, bottom: p.bubble ? 360 : 130, display: 'flex',
          flexDirection: 'column', justifyContent: 'center'}}>
          {p.fig && <div style={{fontFamily: 'Bricolage', fontWeight: 800, fontSize: 150, lineHeight: 1, color: YELLOW,
            marginBottom: 24, textShadow: '0 10px 40px rgba(255,214,90,0.35)'}}>{p.fig}</div>}
          <Lit title={p.title} hi={p.hi} size={size(p.title, p.fig ? 96 : 116)} />
          <div style={{marginTop: 44}}>
            {p.points.map((pt, k) => (
              <div key={k} style={{display: 'flex', gap: 22, marginBottom: 28, fontFamily: 'Inter', fontWeight: 600, fontSize: 42,
                lineHeight: 1.3, color: INK}}>
                <span style={{color: YELLOW, fontWeight: 900}}>→</span><span>{pt}</span>
              </div>
            ))}
          </div>
        </div>
        {p.bubble && (<>
          <div style={{position: 'absolute', left: 70, bottom: 110, width: 210, height: 220}}>
            {duo ? <G {...still} mouth={0.4} look={1} talking /> : <Spark {...still} mouth={0.3} look={1} />}
          </div>
          <Bubble text={p.bubble} tail="left" style={{left: 250, bottom: 250, maxWidth: 720, transform: 'rotate(-1.5deg)'}} />
        </>)}
        <div style={{position: 'absolute', left: 80, bottom: 64, fontFamily: 'Inter', fontWeight: 600, fontSize: 24, color: MUTED}}>{p.source}</div>
      </>)}

      {p.kind === 'close' && (<>
        <div style={{position: 'absolute', left: 80, right: 80, top: 190, textAlign: 'center'}}>
          <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 34, color: MUTED, marginBottom: 28, letterSpacing: 1}}>YOUR TURN</div>
          <Lit title={p.title} hi={p.hi} size={size(p.title, 110)} align="center" />
          <div style={{marginTop: 40, fontFamily: 'Inter', fontWeight: 700, fontSize: 38, color: YELLOW}}>Tell us in the comments</div>
        </div>
        <div style={{position: 'absolute', left: 230, top: 780, width: 300, height: 315}}><Spark {...still} mouth={0.35} look={1} talking /></div>
        {duo && <div style={{position: 'absolute', left: 580, top: 860, width: 240, height: 252}}><G {...still} mouth={0.2} look={-1} /></div>}
        <div style={{position: 'absolute', left: 80, right: 80, bottom: 120, textAlign: 'center', fontFamily: 'Inter', fontWeight: 600,
          fontSize: 30, color: INK, lineHeight: 1.5}}>
          {p.points.map((x, k) => <div key={k} style={k === 0 ? {fontWeight: 800, fontSize: 36} : {color: MUTED}}>{x}</div>)}
        </div>
      </>)}

      <Dots n={p.n} total={p.total} />
    </AbsoluteFill>
  );
};

// All the day's slides in one render: frame k is slide k (python renders with --sequence, one JPEG per frame).
export const Carousel: React.FC<{slides: SlideProps[]}> = ({slides}) => {
  const f = useCurrentFrame();
  return <Slide {...slides[Math.min(f, slides.length - 1)]} />;
};
