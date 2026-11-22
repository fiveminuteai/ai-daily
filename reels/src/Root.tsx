import React from 'react';
import {Composition, Still} from 'remotion';
import {Banner} from './Banner';
import {Cover} from './Cover';
import {DuoReel} from './DuoReel';
import {Carousel, Slide} from './Slide';

// The timeline and audio come in as props (python: fma/duo_reel.py remotion_render -> --props=<job>/props.json)
export const Root: React.FC = () => (
  <>
  <Composition id="DuoReel" component={DuoReel as any} width={1080} height={1920} fps={30} durationInFrames={300}
    defaultProps={{timeline: {fps: 30, seconds: 10, guest: 'doubt', lines: [], mouth: {}}, audio: ''}}
    calculateMetadata={({props}: any) => ({durationInFrames: Math.max(1, Math.round(props.timeline.seconds * props.timeline.fps)),
                                           fps: props.timeline.fps})} />

  <Still id="Cover" component={Cover as any} width={1080} height={1920}
    defaultProps={{title: 'AI is speeding up its own research', hi: 'its own research', bubble: 'Even I cannot keep up.', guest: 'doubt', label: 'RESEARCH'}} />
  <Still id="Banner" component={Banner as any} width={2560} height={1440} />
  <Still id="Slide" component={Slide as any} width={1080} height={1350}
    defaultProps={{kind: 'story', n: 2, total: 7, title: 'Google removes the search button', hi: 'search button',
      points: ['An AI chat sidebar takes its place.', 'It shows your recent AI chats.'], kicker: 'FIVE MINUTE AI',
      label: 'PRODUCTS', bubble: 'I prefer the old silence.', guest: 'doubt', source: 'Source: The Verge', others: []}} />
  <Composition id="Carousel" component={Carousel as any} width={1080} height={1350} fps={1} durationInFrames={1}
    defaultProps={{slides: []}}
    calculateMetadata={({props}: any) => ({durationInFrames: Math.max(1, props.slides.length)})} />
  </>
);
