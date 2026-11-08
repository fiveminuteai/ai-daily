import React from 'react';
import {Composition, Still} from 'remotion';
import {Cover} from './Cover';
import {DuoReel} from './DuoReel';

// The timeline and audio come in as props (python: fma/duo_reel.py remotion_render -> --props=<job>/props.json)
export const Root: React.FC = () => (
  <>
  <Composition id="DuoReel" component={DuoReel as any} width={1080} height={1920} fps={30} durationInFrames={300}
    defaultProps={{timeline: {fps: 30, seconds: 10, guest: 'doubt', lines: [], mouth: {}}, audio: ''}}
    calculateMetadata={({props}: any) => ({durationInFrames: Math.max(1, Math.round(props.timeline.seconds * props.timeline.fps)),
                                           fps: props.timeline.fps})} />

  <Still id="Cover" component={Cover as any} width={1080} height={1920}
    defaultProps={{title: 'AI is speeding up its own research', hi: 'its own research', bubble: 'Even I cannot keep up.', guest: 'doubt', label: 'RESEARCH'}} />
  </>
);
