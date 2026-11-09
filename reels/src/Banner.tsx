// The YouTube channel banner (9 Nov 2026). 2560 x 1440; YouTube shows only the middle 1546 x 423 on every device,
// so the name, the line and the cast all sit inside that band. Drawn with the Reels' own characters and night sky.
import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Background, INK, MUTED, NIGHT, YELLOW, useFonts} from './DuoReel';
import {Doubt, Spark} from './Characters';

export const Banner: React.FC = () => {
  useFonts();
  const still = {t: 1.3, talking: false, pop: 0, vis: null};
  return (
    <AbsoluteFill style={{backgroundColor: NIGHT}}>
      <Background t={2} i={2} since={0} />
      {/* the safe band: 1546 x 423, centred */}
      <div style={{position: 'absolute', left: (2560 - 1546) / 2, top: (1440 - 423) / 2, width: 1546, height: 423,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
        <div style={{width: 330, height: 346}}><Spark {...still} mouth={0.35} look={1} talking /></div>
        <div style={{textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18}}>
          <div style={{fontFamily: 'Bricolage', fontWeight: 800, fontSize: 132, lineHeight: 1, color: INK, letterSpacing: -3}}>
            Five Minute AI</div>
          <div style={{fontFamily: 'Bricolage', fontWeight: 800, fontSize: 50, color: NIGHT, background: YELLOW,
            borderRadius: 30, padding: '8px 32px'}}>AI news in 40 seconds</div>
          <div style={{fontFamily: 'Inter', fontWeight: 700, fontSize: 34, color: MUTED, letterSpacing: 1}}>
            Every claim checked · New Shorts daily</div>
        </div>
        <div style={{width: 290, height: 305, marginTop: 40}}><Doubt {...still} mouth={0.2} look={-1} /></div>
      </div>
    </AbsoluteFill>
  );
};
