import React from 'react';
import {spring} from 'remotion';

// The comment drop (19 Nov 2026, Pavan's reel batch, brief B; written from scratch): on the closing line, the Reel's
// own question drops in as Five Minute AI's pinned comment, bounces, its heart fills, and an empty reply box blinks
// under it: a reason to answer, shown where the eye already is. It is always our own question, never a made-up viewer
// comment. Outside the camera layer, inside Instagram's safe zone (x 110-970, y 300-680): it takes the header's place
// (DuoReel fades the header out) and ends above the characters' heads (about y 690).
const NIGHT = '#120E2A', YELLOW = '#FFD65A';

const Heart: React.FC<{fill: number}> = ({fill}) => (
  <svg width={46} height={42} viewBox="0 0 24 22" style={{transform: `scale(${1 + 0.35 * Math.sin(Math.PI * Math.min(1, fill))})`}}>
    <path d="M12 21s-8-5.2-10.2-10C0.3 7.6 2.3 3 6.3 3c2.3 0 3.9 1.4 5.7 3.4C13.8 4.4 15.4 3 17.7 3c4 0 6 4.6 4.5 8C20 15.8 12 21 12 21z"
      fill={fill > 0 ? '#FF4D6A' : 'none'} stroke={fill > 0 ? '#FF4D6A' : '#8A86A3'} strokeWidth={2} />
  </svg>
);

export const CommentDrop: React.FC<{text: string; since: number; fps: number; until?: number}> = ({text, since, fps, until}) => {
  if (since < 0) return null;
  const drop = spring({frame: since * fps, fps, config: {damping: 11, stiffness: 170, mass: 0.9}});
  const out = until !== undefined && since > until ? Math.max(0, 1 - (since - until) / 0.3) : 1;
  const heart = since > 0.9 ? Math.min(1, (since - 0.9) / 0.35) : 0;
  const caret = Math.floor(since * 2.2) % 2 === 0;
  const box = spring({frame: Math.max(0, (since - 0.45) * fps), fps, config: {damping: 16, stiffness: 140}});
  const size = text.length > 46 ? 44 : 52;
  return (
    <div style={{position: 'absolute', left: 110, right: 110, top: 300, opacity: out,
      transform: `translateY(${(1 - drop) * -520}px) rotate(${(1 - drop) * -5}deg)`}}>
      <div style={{background: '#FFFFFF', borderRadius: 34, padding: '26px 30px', boxShadow: '0 22px 44px rgba(0,0,0,0.4)',
        display: 'flex', gap: 22, alignItems: 'flex-start'}}>
        <div style={{flex: '0 0 auto', width: 78, height: 78, borderRadius: 39, background: `linear-gradient(135deg, ${YELLOW}, #FF845F)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Bricolage', fontWeight: 800, fontSize: 40, color: NIGHT}}>5</div>
        <div style={{flex: 1, minWidth: 0}}>
          <div style={{display: 'flex', alignItems: 'center', gap: 14, fontFamily: 'Inter', fontSize: 30}}>
            <span style={{fontWeight: 800, color: NIGHT}}>fiveminute_ai</span>
            <span style={{color: '#8A86A3', fontWeight: 600}}>Pinned</span>
          </div>
          <div style={{marginTop: 8, fontFamily: 'Inter', fontWeight: 700, fontSize: size, lineHeight: 1.18, color: NIGHT}}>{text}</div>
          <div style={{marginTop: 14, fontFamily: 'Inter', fontWeight: 700, fontSize: 28, color: '#8A86A3'}}>Reply</div>
        </div>
        <div style={{flex: '0 0 auto', paddingTop: 30}}><Heart fill={heart} /></div>
      </div>
      <div style={{marginTop: 16, marginLeft: 100, marginRight: 20, opacity: box, transform: `translateY(${(1 - box) * 24}px)`,
        background: 'rgba(255,255,255,0.14)', border: '3px solid rgba(255,255,255,0.5)', borderRadius: 40,
        padding: '10px 28px', fontFamily: 'Inter', fontWeight: 600, fontSize: 30, color: '#F6F2FF'}}>
        Add a comment<span style={{opacity: caret ? 1 : 0, color: YELLOW, fontWeight: 800}}>|</span>
      </div>
    </div>
  );
};
