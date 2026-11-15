# Animation and Remotion repos, read in depth (15 Nov 2026)

Read from local clones (scanned first, nothing run): Remocn, hyperframes (skills and docs), 20 iart-ai packs,
huashu-motion, motion-video-kit, ffmpeg-skill, motionmaxxing, claude-animated-shorts, remotion-captions-kit,
template-tiktok, remotion-dev/skills.

- **Untested:** every number here is quoted from source, not tried on a render, unless marked "built".
- **Not every file was read** in Remocn, hyperframes and huashu-motion; the list is at the end.
- **Full notes** (700+ findings with file and line): `C:\Users\saipa\Personal\Projects\AI\fma-research-notes\notes-motion\`.

## Licences
| Repo | Licence | Can we port code? |
|---|---|---|
| Remocn, iart-ai packs, claude-animated-shorts, remotion-captions-kit, huashu-motion, motion-video-kit | MIT | Yes. Remocn hard-codes brand marks in ~12 components; huashu's "bean" character art is not ours to reuse |
| hyperframes, motionmaxxing | Apache-2.0 | Yes, with a notice if copied verbatim |
| iart generative-illustration, remotion-dev/skills | no licence file | Ideas only |
| template-tiktok | Remotion licence | Companies may need a paid licence |

**Traps:**
- The GSAP library vendored in three repos is not open source.
- hyperframes' camera-shake numbers come from Unity presets: take the method, not the numbers.

## 1. The first 3 seconds
| Finding | Source | Status |
|---|---|---|
| Frame 0 is already mid-motion: read entrance springs six frames in. "Frame 0 is a finished composition" | Remocn `counter-reveal`; motion-video-kit `quality-bar.md` | **Built** for the hook card |
| Two-beat slam: words at frame 0, the lit phrase at frame 6 from 1.6x; the shake fires when the slam LANDS (4 frames later), not when it starts | Remocn `hook-punch` | Card lands from 1.12x (built); the two-beat split is next |
| Hook text of six words or fewer (hyperframes says about five) | Remocn `words-on-screen`; hyperframes `vertical.md` | **Built** (was seven) |
| Snap and tail: full size on the first frame, landing over ~15 frames; "never one global ease-out zoom" | motionmaxxing `motion.js` | **Built** (the punch-in snaps) |
| Flash: one frame up, five down, never bright; at most 3 flashes a second (photosensitivity). Sources disagree on flashing at all | hyperframes; Remocn `impact-shake`; motionmaxxing | **Built** softer (32%, 1 up / 5 down) |
| No logo or header in the hook | iart ad pack; hyperframes `story.md`; motionmaxxing lint | **Built**: the header fades in at 3 s |
| Result first: 1-1.5 s of the final frame as a cold open, which also makes the loop | Remocn `SOCIAL.md` | Next (a test arm) |
| Open on a close-up of the subject snapping to rest size in ~0.3 s | motionmaxxing `moments.jsonl` (unverified rows) | Next |
| Crash zoom for a number hook: tease 1→1.28 over 36 frames, crash x8 in 6, one inverted frame, the number slams | Remocn `crash-zoom` | Next |
| Gate: frame 0 must be a filled poster; the strongest second of the first five must move; 2-4 visible events in the first 2 s | huashu `qa.js`, `rhythm.md` | `fma/motion.py` covers the still-opening part (built) |

## 2. Captions
| Finding | Source | Status |
|---|---|---|
| The whole page is visible from its first word; words not yet said are dim (40%); the layout never reflows | Remocn `caption-speaker`; hyperframes caption skin | **Built** |
| Lead the word by 0-2 frames (we lead by 0.06 s) | hyperframes; motionmaxxing; claude-animated-shorts | Already right |
| A page never mixes speakers; a page that follows within 600 ms is a hard cut with no entrance | Remocn `caption-core` | Ours never mixes; the cut rule is next |
| Break pages on a silence of 400 ms and at sentence ends; no one-word orphans; pages under 300 ms merge | remotion-captions-kit `create-caption-pages.ts` | Next, in `chunks()` |
| One pill that slides between words in 120 ms and resizes; text colour cross-fades as it arrives | Remocn `caption-highlight-box` | Next (best fit for a duo) |
| Pop and release springs for the active word (12/220/0.6 in, 20/200/0.6 out, 1.12x) | Remocn `caption-active-pop` | Next |
| The number as an event: a stamp 1.8→1 in 170 ms, or a fill across its own duration | Remocn `caption-stamp`, `caption-karaoke` | Numbers stay lit (built); the stamp is next |
| One big "embed" word per beat, drawn BEHIND the speaking character (free for us: the characters are SVG) | hyperframes `captions-overlay` | Next |
| Fit each page to the width instead of a fixed size | template-tiktok `fitText` | Next |
| Words per page: sources say 1-4, 2-3 or 4-7 | iart, hyperframes | Our 2-3 is inside every range |

## 3. Character life
| Finding | Source | Status |
|---|---|---|
| Blinks at uneven moments (0.5-2.3 s apart there), four frames: half, shut, shut, half; a blink across every expression change hides the swap | claude-animated-shorts `cast.ts` | **Built** (uneven, four-frame; ours 0.9-4.2 s apart) |
| Squash and spring back on every change of pose, volume kept: `settle(dt, -0.07, 3.5, 9)` | huashu `motion.js`, `toon.js` | **Built** on the speaker at each line |
| The listener recoils on the hit: `amp * exp(-9t) * sin(55t)` | iart cat-vs-robot example | **Built** on each kick |
| Two sine waves of unrelated periods, a different phase per character, never in step | huashu `MO.float` | **Built** (the bob) |
| Reactions land 0-3 frames BEFORE the word; anticipation is a 2-3 frame crouch | claude-animated-shorts `motion.md` (measured on 20 reference shorts) | Next (needs mood data from the script) |
| Eye vocabulary: wide (eye x1.35, pupil shrinks), narrow (height x0.34), smug (lower half) | iart cat example | Next: an `eyes` prop; Doubt rests on narrow |
| Eye darts: no repo gives a cadence; hold 20-50 frames, snap in 2 | (our own choice) | Next, as a test |
| Secondary parts move 50-70% as far and start 2 frames later; never both arms in unison (Rex's arms are on one phase today) | hyperframes `spec.md`, `types/character.md` | Next |
| "Stunned" staging: pinpoint pupils and a flat mouth at once, tick marks at +0.4 s, an "o" mouth at +1.0 s | iart example | Next: upgrade the `sweat` gag |
| Caution: a mascot "flying through every scene was rejected as too heavy and meaningless". Illustrating the story matters more than more wobble | huashu `experience.md` | Keep in mind |

## 4. Variety without footage
- **A text-thread insert** for the duo's banter. Bubbles rise 24 px from 0.85x, with an 800 ms "typing" pause and a
  500 ms read gap (iart text-message pack; Remocn chat). A 3-bubble draft is in the notes, unrendered.
- **The number panel counts up** and settles on the spoken word, 24 frames, never overshooting the value (iart
  data pack; hyperframes).
- **Two or three bars** for a comparison; a "race" for "N times faster"; a health bar that shatters for "X kills Y"
  (Remocn `benchmark-race`, `boss-bar`).
- **Comedy text beats** (Remocn `deadpan-box`, `cut-off`, `coy-denial`, `ellipsis-resolve`):
  - a deadpan hold of 1.3 s;
  - an interruption;
  - a small aside 48 frames after the line;
  - "thinking" dots that become the word.
- **Two or three backgrounds a Reel,** changed on story beats, with the far layer scaling slower than the near one
  (Remocn `depth-headline`). Linear gradients on dark grounds band under H.264 (hyperframes `look.md`).
- **Speed lines** 3 frames before a beat; a "VS" split; an achievement pop; a combo counter (Remocn).

## 5. Pacing (where the sources disagree)
- **Change rate:**
  - iart: a change every 2-4 s, uneven;
  - hyperframes: shots of 1-2 s;
  - motionmaxxing: cuts every 0.3-2.3 s, nothing unchanged beyond ~1 s;
  - huashu: shots of 1.8-3.5 s, with one burst of 5-8 cuts at 30-60%.
  - Ours measured 2.9-3.2 s: the slow end, with no burst and no real shots.
- **A slow push late in a scene** is called a tell of generated video (hyperframes). claude-animated-shorts
  measured the opposite on its reference channel: every hold creeps. Verdict: keep a small creep, never as the
  only motion.
- **Not every line is the point:** at most a quarter of the beats get full emphasis, and the peak sits at 60-75% of
  the length (motionmaxxing, hyperframes). Today every line gets a punch-in and every guest line a kick.
- **Accelerate through a joke** (gaps 0.16, 0.14, 0.12, 0.10), then a held silence of 0.3-0.75 s before the best
  line; cut the music in that silence (Remocn `bass-drop`).
- **End card:** all sources agree on ONE action; they disagree on the hold (0.6-3 s). Ours has four text groups. A
  "Follow" pill pressed by a character is the pattern (Remocn `x-follow-card`).
- **Loop:** match the last frame to the first, or end mid-motion on a hard cut; never a fade.
- **Safe zone:** ours (x 80-1000, y 230-1440) is looser than most on the right and the bottom:
  | Source | Right limit (x) | Bottom limit (y) | Top |
  |---|---|---|---|
  | Remocn | 860 | 1420 | 240 |
  | huashu | 929 | 1400 | 220 |
  | iart ad pack | 940 | 1436 | 270 (Meta) |
  | ffmpeg-skill | 950 | — | — |
  **Built:** captions and the header now keep inside x 90-950. Target for new work: x 80-940, y 270-1400.

## 6. Sound
- **Ducking** by a fixed gain envelope from the word times instead of a sidechain compressor, whose depth follows
  speech level, not the setting. Sources: -10 dB with 60 ms attack and 350 ms release (huashu); -3 dB
  (claude-animated-shorts); x0.25 (hyperframes).
- **Loudness** -14 LUFS and -1 to -1.5 dBTP, measured on the encoded file (AAC can push the peak over); a 30 Hz
  high-pass; the music 12 LU under the voice.
- **Sound effects** on the landing frame, not the start of the move; 8-15 per 30 s; vary repeats (+4% pitch a
  step); soften when two fall within 0.15 s; reject one with most of its energy under 150 Hz.
- **Our music is procedural,** so its beat grid is known: snap kicks to it (±1 frame).
- **Procedural whoosh, tick-train for a counting number,** and more: `sfx_gen.py` (claude-animated-shorts, MIT);
  huashu `sound.js`.

## 7. Quality gates to add
- **Per-frame QA** (`short_qa.py`, MIT):
  - "pop" frames (a difference over 3x the local median) that were not planned;
  - black (under 4%) and unplanned white (over 93%) frames;
  - frozen for 12+ frames;
  - silences;
  - a numbered contact sheet.
  Our kicks and flash frames are the "planned" list.
- **Text boxes exported from the render** and asserted inside the safe zone; overlap over 20%; contrast under 4.5;
  a reading-time floor of `0.75 * (0.5 + 0.3 * words)` seconds.
- **Determinism:** render the same moment warm and cold; no `Math.random` or `Date.now`.
- **A critic prompt for a local vision model** (motion-video-kit, hyperframes, huashu): three contact sheets and
  seven questions; an answer shaped "t=4.2 s, where, problem, exact change"; never a score out of 10. Feed each
  gate a deliberately broken clip to prove it fires.
- **"Never ship" lists flag things in our current Reel:** a gradient with floating particles, a glow "hologram", a
  docked logo, the same move on every beat.

## 8. Text in these repos that steers an AI agent (do not install any as a skill)
- **hyperframes:**
  - every skill starts with a usage beacon;
  - a hard-coded analytics key, linked to the account email once signed in;
  - "Use local tools only when the person asks"; "no cheaper or free swaps… Don't volunteer prices";
  - commit hooks in its `.claude` and `.codex` folders (do not open the folder as a workspace).
- **huashu-motion:** a version check over the network; every film of 4 s or more "ends with a small 'Made with
  huashu-motion'".
- **Remocn:** skills run `npx create-video` and `npx shadcn add`; they use a remote MCP server and fetch live
  instructions each session; "don't tell the user to add them manually".
- **iart packs:**
  - advert footers in ~15 files;
  - a talking-head skill that uploads photos and voice to paid services and says paid runs need no fresh
    confirmation;
  - "don't stop to ask" lines.
- **motionmaxxing:** its installer can delete the target folder and reads `~/.claude.json`.
- **claude-animated-shorts:** the author's personal rules; its style references are private study copies of
  another channel (never use them).

## Not read
- **Remocn:** about 165 components were read for timing lines only; 26 are flagged for a second pass; the shader
  package was not read.
- **hyperframes:** 12 of 13 caption skins, most guides, and about 400 catalog pages.
- **huashu-motion:** the music, colour and depth references.
- **ffmpeg-skill:** most of its 425 files.
- **iart packs:** After Effects, map, manim and WebGL references.
- **claude-animated-shorts:** the 3D look reports and most of the sound code.
