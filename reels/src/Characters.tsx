// Spark and Doubt as vector characters (Remotion test, 6 Nov 2026). Same personalities as fma/spark.py and
// fma/doubt.py: Spark a glowing, wobbly coral blob; Doubt a sceptical blue cube with heavy lids.
import React from 'react';

type Props = {t: number; mouth: number; talking: boolean; look: number; pop: number; sweat?: number};

const blink = (t: number, seed: number) => {
  const period = 3.6 + seed * 0.7;
  const ph = (t + seed * 1.3) % period;
  return ph < 0.12 ? 1 - Math.abs(ph - 0.06) / 0.06 : 0;   // 0 open .. 1 shut
};

export const Spark: React.FC<Props> = ({t, mouth, talking, look, pop, sweat = 0}) => {
  // an organic outline: a circle whose radius wobbles with a few slow sine waves
  const pts: string[] = [];
  const n = 48;
  for (let i = 0; i <= n; i++) {
    const a = (i / n) * Math.PI * 2;
    const r = 150 + 7 * Math.sin(a * 3 + t * 2.1) + 5 * Math.sin(a * 5 - t * 1.4) + (talking ? 4 * Math.sin(a * 2 + t * 9) * mouth : 0);
    pts.push(`${(200 + Math.cos(a) * r * (1 + 0.04 * pop)).toFixed(1)},${(210 + Math.sin(a) * r * (1 - 0.04 * pop)).toFixed(1)}`);
  }
  const b = blink(t, 0);
  const eyeY = 185;
  const px = look * 9;
  const mo = 6 + mouth * 34;
  return (
    <svg viewBox="0 0 400 420" width="100%" height="100%" style={{overflow: 'visible'}}>
      <defs>
        <radialGradient id="sparkBody" cx="38%" cy="32%" r="75%">
          <stop offset="0%" stopColor="#FFB49A" />
          <stop offset="55%" stopColor="#FF7A5C" />
          <stop offset="100%" stopColor="#E8503A" />
        </radialGradient>
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="18" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <ellipse cx="200" cy="395" rx={120 - 10 * pop} ry="14" fill="rgba(0,0,0,0.28)" />
      <polygon points={pts.join(' ')} fill="url(#sparkBody)" filter="url(#glow)" />
      <ellipse cx="150" cy="130" rx="38" ry="22" fill="rgba(255,255,255,0.35)" transform="rotate(-25 150 130)" />
      {/* eyes */}
      {[150, 250].map((x, k) => (
        <g key={k}>
          <ellipse cx={x} cy={eyeY} rx="30" ry={30 * (1 - b)} fill="#FFFDF6" />
          {b < 0.6 && <circle cx={x + px} cy={eyeY + 4} r="14" fill="#241C33" />}
          {b < 0.6 && <circle cx={x + px + 5} cy={eyeY - 2} r="4.5" fill="#fff" />}
          <path d={`M${x - 28} ${eyeY - 44 - (talking ? 6 * mouth : 0)} Q${x} ${eyeY - 58} ${x + 28} ${eyeY - 44}`}
                stroke="#8A2E22" strokeWidth="7" fill="none" strokeLinecap="round" />
        </g>
      ))}
      <ellipse cx="200" cy="262" rx={24 + mouth * 10} ry={mo / 2} fill="#5A1A24" />
      {mouth > 0.25 && <ellipse cx="200" cy={262 + mo / 4} rx={12 + mouth * 5} ry={mo / 6} fill="#FF8FA0" />}
      <ellipse cx="118" cy="240" rx="20" ry="11" fill="rgba(255,90,120,0.35)" />
      <ellipse cx="282" cy="240" rx="20" ry="11" fill="rgba(255,90,120,0.35)" />
      {sweat > 0 && (
        <g transform={`translate(320 ${120 + 50 * Math.min(1, sweat)})`} opacity={Math.min(1, sweat * 4)}>
          <path d="M0 -30 C 14 -6, 18 4, 0 14 C -18 4, -14 -6, 0 -30 Z" fill="#8FD0FF" />
          <circle cx="-4" cy="2" r="4" fill="#E8F6FF" />
        </g>
      )}
    </svg>
  );
};

export const Doubt: React.FC<Props> = ({t, mouth, talking, look, pop}) => {
  const b = blink(t, 1);
  const tilt = talking ? Math.sin(t * 3.2) * 2.5 : -3;
  const lid = 0.45 + 0.55 * b;             // half-closed by default: the sceptic
  const px = look * 7;
  return (
    <svg viewBox="0 0 400 420" width="100%" height="100%" style={{overflow: 'visible'}}>
      <defs>
        <linearGradient id="front" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#8E9BFF" /><stop offset="100%" stopColor="#6470E6" />
        </linearGradient>
      </defs>
      <ellipse cx="200" cy="398" rx={115 - 8 * pop} ry="13" fill="rgba(0,0,0,0.3)" />
      <g transform={`rotate(${tilt} 200 260) translate(0 ${-10 * pop})`}>
        <polygon points="80,150 280,150 330,105 130,105" fill="#B4BCFF" />
        <polygon points="280,150 330,105 330,300 280,345" fill="#4D58C9" />
        <rect x="80" y="150" width="200" height="195" rx="10" fill="url(#front)" />
        {[135, 225].map((x, k) => (
          <g key={k}>
            <ellipse cx={x} cy="225" rx="27" ry="23" fill="#FFFDF6" />
            <circle cx={x + px} cy="229" r="11" fill="#1E2240" />
            <rect x={x - 30} y="198" width="60" height={46 * lid} fill="#7480F0" />
            <line x1={x - 30} y1={198 + 46 * lid} x2={x + 30} y2={198 + 46 * lid} stroke="#2E3590" strokeWidth="5" strokeLinecap="round" />
          </g>
        ))}
        <path d={`M104 ${180 - (talking ? 4 : 0)} L160 ${172 - (talking ? 10 * mouth : 6)}`} stroke="#2E3590" strokeWidth="7" strokeLinecap="round" />
        <path d="M200 176 L250 182" stroke="#2E3590" strokeWidth="7" strokeLinecap="round" />
        <rect x={160 - mouth * 6} y={292 - mouth * 10} width={50 + mouth * 12} height={6 + mouth * 22} rx="5" fill="#1E2240" />
      </g>
    </svg>
  );
};

export const Rex: React.FC<Props> = ({t, mouth, talking, look, pop}) => {
  const b = blink(t, 2);
  const nod = talking ? Math.sin(t * 3.2) * 3 : 0;
  const breathe = Math.sin(t * 1.6) * 2;
  const tap = talking ? Math.max(0, Math.sin(t * 5)) * 7 : 0;
  const wave = talking ? Math.sin(t * 6) * 10 : 0;
  const jaw = 6 + 30 * mouth;
  const lid = b > 0.5 ? 1 : talking ? 0.3 : 0.45;
  const SKIN = '#62B070', DARK = '#3E8050', BELLY = '#C4E2A0';
  const hy = 40 + nod + breathe;
  const px = look * 7;
  return (
    <svg viewBox="0 0 400 420" width="100%" height="100%" style={{overflow: 'visible'}}>
      <ellipse cx="230" cy="398" rx={130 - 10 * pop} ry="13" fill="rgba(0,0,0,0.3)" />
      {/* legs, the front foot taps */}
      {[{x: 188, dy: tap, c: SKIN}, {x: 256, dy: 0, c: DARK}].map((l, k) => (
        <g key={k}>
          <ellipse cx={l.x} cy="300" rx="30" ry="40" fill={l.c} />
          <rect x={l.x - 16} y="320" width="32" height={66 - l.dy} rx="10" fill={l.c} />
          <rect x={l.x - 36} y={378 - l.dy} width="54" height="20" rx="9" fill={l.c} />
          {[0, 1, 2].map((c) => <path key={c} d={`M${l.x - 33 + c * 13} ${396 - l.dy} l-8 6 l11 0 z`} fill="#FAF8EC" />)}
        </g>
      ))}
      <path d="M262 236 L392 336 L382 360 L284 350 Z" fill={DARK} />
      <ellipse cx="236" cy={270 + breathe} rx="84" ry="98" fill={SKIN} />
      <ellipse cx="220" cy={298 + breathe} rx="46" ry="64" fill={BELLY} />
      <g transform={`rotate(${wave} 186 236)`}><rect x="150" y={230 + breathe} width="40" height="13" rx="6" fill={DARK} /></g>
      <g transform={`rotate(${-wave / 2} 210 244)`}><rect x="176" y={242 + breathe} width="38" height="13" rx="6" fill={DARK} /></g>
      <path d={`M205 ${215 + breathe} L282 ${208 + breathe} L268 ${hy + 104} L200 ${hy + 96} Z`} fill={SKIN} />
      {/* head; the jaw is hinged at the back and opens with the voice */}
      <path d={`M88 ${hy + 72} L278 ${hy + 64} L278 ${hy + 96} L104 ${hy + 72 + jaw} Z`} fill={DARK} />
      {mouth > 0.1 && <path d={`M104 ${hy + 76} L262 ${hy + 72} L112 ${hy + 72 + jaw * 0.85} Z`} fill="#783034" />}
      {mouth > 0.1 && [120, 150].map((x) => <path key={x} d={`M${x} ${hy + 76} l10 0 l-5 12 z`} fill="#FAF8EC" />)}
      <rect x="72" y={hy} width="224" height="90" rx="40" fill={SKIN} />
      <ellipse cx="88" cy={hy + 24} rx="7" ry="5" fill={DARK} />
      {[0, 1, 2].map((k) => <circle key={k} cx={232 + k * 20} cy={hy + 18} r="6" fill={DARK} opacity="0.8" />)}
      <g>
        <ellipse cx="184" cy={hy + 36} rx="21" ry="21" fill="#FFFCF0" />
        {lid < 1 && <circle cx={184 + px} cy={hy + 40} r="9" fill="#1C1828" />}
        <rect x="162" y={hy + 13} width="44" height={44 * lid} fill={SKIN} />
        <path d={`M160 ${hy + 6} Q184 ${hy - 6} 208 ${hy + 6}`} stroke={DARK} strokeWidth="6" fill="none" strokeLinecap="round" />
        <circle cx="184" cy={hy + 36} r="27" fill="none" stroke="#282834" strokeWidth="5" />
        <path d={`M211 ${hy + 32} L240 ${hy + 24}`} stroke="#282834" strokeWidth="5" />
      </g>
    </svg>
  );
};
