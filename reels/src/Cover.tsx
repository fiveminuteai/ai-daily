// The Reel's cover (8 Nov 2026, Pavan: "an attractive thumbnail with a catchy heading pulls more people"). One still
// per Reel: a big headline with one key phrase lit up, the cast, and the guest's best line in a bubble. Instagram's
// profile grid crops the 9:16 cover to the middle 3:4 (y 240-1680), so everything that matters sits inside that band.
import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Background, INK, MUTED, NIGHT, YELLOW, useFonts} from './DuoReel';
import {Doubt, Rex, Spark} from './Characters';

export type CoverProps = {title: string; hi: string; bubble: string | null; guest: string; label: string};

const Headline: React.FC<{title: string; hi: string}> = ({title, hi}) => {
  const n = title.length;
  const size = n <= 18 ? 160 : n <= 38 ? 132 : n <= 52 ? 112 : 96;
  const at = hi ? title.toLowerCase().indexOf(hi.toLowerCase()) : -1;
  const parts = at < 0 ? [{s: title, on: false}] : [{s: title.slice(0, at), on: false}, {s: title.slice(at, at + hi.length), on: true},
    {s: title.slice(at + hi.length), on: false}];
  return (
    <div style={{fontFamily: 'Bricolage', fontWeight: 800, fontSize: size, lineHeight: 1.16, color: INK, letterSpacing: -2,
      textAlign: 'center', textShadow: '0 8px 30px rgba(0,0,0,0.45)'}}>
      {parts.map((p, k) => p.on
        ? <span key={k} style={{background: YELLOW, color: NIGHT, padding: '0 16px', borderRadius: 18, display: 'inline',
            boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone',
            boxShadow: '0 10px 30px rgba(0,0,0,0.35)'}}>{p.s}</span>
        : <span key={k}>{p.s}</span>)}
    </div>
  );
};

export const Cover: React.FC<CoverProps> = ({title, hi, bubble, guest, label}) => {
  useFonts();
  const solo = guest === 'solo';
  const t = 1.3;
  const still = {t, talking: false, pop: 0, vis: null};
  const G = guest === 'rex' ? Rex : Doubt;
  return (
    <AbsoluteFill style={{backgroundColor: NIGHT}}>
      <Background t={t} i={1} since={0} />
      <div style={{position: 'absolute', left: 90, right: 90, top: 290, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <span style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 34, letterSpacing: 1, color: YELLOW}}>FIVE MINUTE AI</span>
        {label && <span style={{fontFamily: 'Inter', fontWeight: 700, fontSize: 30, color: INK, border: `3px solid ${INK}cc`, borderRadius: 30, padding: '6px 24px'}}>{label}</span>}
      </div>
      <div style={{position: 'absolute', left: 70, right: 70, top: 390, height: 520, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <Headline title={title} hi={hi} />
      </div>
      {solo ? (
        <div style={{position: 'absolute', left: 540 - 250, top: 1050, width: 500, height: 525}}>
          <Spark {...still} mouth={0.35} look={0} talking />
        </div>
      ) : (
        <>
          <div style={{position: 'absolute', left: 330 - 220, top: 1130, width: 440, height: 462}}><Spark {...still} mouth={0.25} look={1} /></div>
          <div style={{position: 'absolute', left: 790 - 180, top: 1230, width: 360, height: 378}}><G {...still} mouth={0.4} look={-1} talking /></div>
          {bubble && (
            <div style={{position: 'absolute', right: 60, top: 975, maxWidth: 600, background: '#fff', color: NIGHT, borderRadius: 34,
              padding: '22px 34px', fontFamily: 'Bricolage', fontWeight: 800, fontSize: 50, lineHeight: 1.08,
              boxShadow: '0 14px 34px rgba(0,0,0,0.4)', transform: 'rotate(2deg)'}}>
              {bubble}
              <div style={{position: 'absolute', right: 200, bottom: -26, width: 0, height: 0, borderLeft: '22px solid transparent',
                borderRight: '22px solid transparent', borderTop: '30px solid #fff'}} />
            </div>
          )}
        </>
      )}
      <div style={{position: 'absolute', bottom: 250, width: '100%', textAlign: 'center', fontFamily: 'Inter', fontWeight: 700, fontSize: 34, color: MUTED}}>
        @fiveminute_ai
      </div>
    </AbsoluteFill>
  );
};
