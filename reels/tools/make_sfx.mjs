// Cartoon sound effects for the duo Reels, generated once with ZzFX (MIT, KilledByAPixel) and kept in fma/sfx/
// (6 Nov 2026). No recordings: each sound is a few numbers, deterministic (randomness 0), and ours to use.
//   node tools/make_sfx.mjs
import fs from 'node:fs';
globalThis.AudioContext = class { };                  // ZzFX opens an audio device on load; we only build samples
const {ZZFX} = await import('zzfx');
const SOUNDS = {
  // ZzFX parameters: volume, randomness, frequency, attack, sustain, release, shape, shapeCurve, slide, deltaSlide,
  // pitchJump, pitchJumpTime, repeatTime, noise, modulation, bitCrush, delay, sustainVolume, decay, tremolo
  party_pop: [1, 0, 520, .01, .02, .12, 0, 1, 10, 0, 300, .04, 0, 0, 0, 0, 0, 1, .05],
  sparkle: [.7, 0, 1200, .01, .1, .4, 0, 2, 0, 0, 600, .08, .08, 0, 0, 0, 0, .7, .1],
  sad_slide: [.9, 0, 420, .05, .45, .35, 2, 1, -2.5, 0, 0, 0, 0, 0, 9, 0, 0, .8, .2],
  slap: [1.4, 0, 150, 0, .02, .12, 4, 1, 0, 0, 0, 0, 0, 2, 0, 0, 0, 1, .02],
  gulp: [.9, 0, 300, .02, .05, .12, 0, 1, 20, 0, 0, 0, 0, 0, 0, 0, 0, 1, .05],
  boing: [.9, 0, 180, .01, .15, .3, 0, 1, 8, 0, 0, 0, .08, 0, 0, 0, 0, .8, .1],
};
const wav = (samples, rate) => {
  const n = samples.length, buf = Buffer.alloc(44 + n * 2);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 2, 4); buf.write('WAVEfmt ', 8); buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22); buf.writeUInt32LE(rate, 24); buf.writeUInt32LE(rate * 2, 28);
  buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) buf.writeInt16LE(Math.max(-1, Math.min(1, samples[i] * 2.5)) * 32767 | 0, 44 + i * 2);
  return buf;
};
for (const [name, p] of Object.entries(SOUNDS)) {
  const s = ZZFX.buildSamples(...p);
  fs.writeFileSync(`../fma/sfx/${name}.wav`, wav(s, ZZFX.sampleRate));
  console.log(name, (s.length / ZZFX.sampleRate).toFixed(2) + ' s');
}
