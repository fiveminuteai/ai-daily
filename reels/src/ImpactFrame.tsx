import React from 'react';

// The impact frame (19 Nov 2026, Pavan's reel batch, brief B; written from scratch): the moment a new number is said,
// the picture cuts for a third of a second to a dark frame with a burst of lines and the figure huge, then the figure
// shrinks onto the number panel's spot and the panel takes over. One hit per new number, never a strobe: two frames
// at full strength, then it fades. It sits outside the camera layer, inside Instagram's safe zone (x 80-1000).
export const IMPACT_S = 0.3;

const YELLOW = '#FFD65A', NIGHT = '#120E2A';

export const ImpactFrame: React.FC<{text: string; since: number; fps: number}> = ({text, since, fps}) => {
  if (since < 0 || since >= IMPACT_S) return null;
  const f = since * fps;
  const hold = f < 2 ? 1 : Math.max(0, 1 - (since - 2 / fps) / (IMPACT_S - 2 / fps));   // 2 frames full, then out
  const land = Math.min(1, since / IMPACT_S);
  const ease = 1 - Math.pow(1 - land, 3);
  const size = text.length > 8 ? 120 : 190;
  // the biggest it may start at and still fit 840 px across (about 0.62 em a character in Bricolage 800)
  const top = Math.max(1, Math.min(1.9, 840 / (0.62 * size * Math.max(1, text.length))));
  const scale = top - (top - 1) * ease;                // lands at the panel's own size
  const y = 900 - (900 - 560) * ease;                  // from mid-screen up to the panel's centre line
  const rays = Array.from({length: 22}, (_, k) => k);
  return (
    <div style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
      <div style={{position: 'absolute', inset: 0, background: NIGHT, opacity: 0.88 * hold}} />
      <svg width={1080} height={1920} style={{position: 'absolute', inset: 0, opacity: hold}}>
        {rays.map((k) => {
          const a = (k / rays.length) * 2 * Math.PI + since * 1.2;
          const r0 = 230 + 40 * ((k * 7) % 3), r1 = 1300;
          return <line key={k} x1={540 + r0 * Math.cos(a)} y1={900 + r0 * Math.sin(a)} x2={540 + r1 * Math.cos(a)}
            y2={900 + r1 * Math.sin(a)} stroke={k % 2 ? YELLOW : '#FF845F'} strokeWidth={k % 3 ? 10 : 22}
            strokeLinecap="round" opacity={0.75} />;
        })}
      </svg>
      <div style={{position: 'absolute', left: 80, right: 80, top: y - size * 0.6, display: 'flex', justifyContent: 'center'}}>
        <span style={{fontFamily: 'Bricolage', fontWeight: 800, fontSize: size, color: YELLOW, lineHeight: 1.2,
          transform: `scale(${scale})`, textShadow: '0 0 34px rgba(255,214,90,0.7), 0 10px 0 rgba(0,0,0,0.35)',
          whiteSpace: 'nowrap'}}>{text}</span>
      </div>
    </div>
  );
};
