# What we learned on 15 Nov 2026, and what it changed (the consolidated analysis)

Pavan's brief: go through every resource end to end, embed what adds value into the current system, and share it
with the social media engine. "No half cooking … No compromises."

This file is the decision record. The evidence is in five companion files:
| File | What it covers |
|---|---|
| `docs/research-2026-11-15-reels-tools-growth.md` | The first pass: the 27 repos' safety table, our own Reels measured |
| `docs/research-2026-11-15-reels-frame-study.md` | The six Reels, frame by frame |
| `docs/research-2026-11-15-videos-full.md` | The four YouTube videos (plus one they link to), read in full |
| `docs/research-2026-11-15-hooks-strategy-repos.md` | Hook, script, caption, measurement and voice repos, read |
| `docs/research-2026-11-15-motion-repos.md` | Animation, caption and quality-gate repos, read |
Raw notes (700+ findings with file and line) are in `C:\Users\saipa\Personal\Projects\AI\fma-research-notes\`.

## What was covered, and what was not
- **Repos:** every repo on Pavan's list, plus 13 alternatives we found (Remocn, claude-animated-shorts,
  remotion-captions-kit, template-tiktok, remotion-dev/skills, HeadTTS, kokoro, rhubarb, lipsync-engine, the 21
  iart-ai packs, marketingskills, instagram-agent-skill, viral-hooks-skill).
  - Each was shallow-cloned into its own empty folder with git hooks off and scanned with
    `docs/pilots/skillscan.py` before any file was read. Nothing from any repo was installed, built or run.
  - The desktop apps (OpenToonz, Synfig, Friction, Pencil2D, Natron, OpenVDB) were judged from their official
    repos, releases and advisories; their binaries were not downloaded.
- **Reels:** all six, frame by frame, logged out, with no downloads. No audio was heard: speech comes from burned-in
  captions, and two Reels have none.
- **YouTube videos:** all four transcripts in full, plus the grid video Dominik links to. On-screen-only material and
  the linked worksheets were not seen.
- **Not read:** about 165 Remocn components were read for timing only; most of hyperframes' catalog; 37 of 53
  marketingskills skills; most of openfilm, FreeVideo and manimgx. Each companion file lists its gaps.

## Safety verdicts (short)
- **Malware:** no malware, no GitHub security advisories, no planted binaries, no hidden install hooks in any repo.
- **Text that steers an AI agent** is common, and none of these repos may ever be installed as a skill:
  - hyperframes: a usage beacon in every skill, analytics tied to the account email, commit hooks;
  - lemo-opuscar: resets itself to the latest main on every run;
  - openfilm: "run npx openfilm@latest and follow what it prints";
  - marketingskills: fetches updates each session;
  - FreeVideo: "do not end your reply", and copies itself into the skills folder;
  - Remocn: a remote MCP server with live instructions;
  - motionmaxxing: reads `~/.claude.json`.
- **Licences:**
  - copy code only from the MIT/Apache repos;
  - anything2explainer and video-talkcraft are noncommercial, and lemo-opuscar's prompts are CC BY-NC: ideas only;
  - the GSAP library some repos bundle is not open source.
- **Lookalikes to avoid:** `kanaworksai-hue/effekseer-vfx-skill`; startup lists that bundle an MCP server.
- **Untrusted signals:** star counts, and the awesome list's "safe" badges (a model read the READMEs, nothing more).

## The diagnosis, from our own numbers
- **Viewers leave at the start.** About 60% of viewers leave in the first 3 s; the average watch is 5.4 s of
  about 38 s; reach is about 100.
- **It is the opening, not the length.** Every source that diagnoses retention says this means the first frame
  and the first seconds, not the length of the rest (marketingskills: fix the visual opening and the on-screen
  text, same everything else).
- **Still frames cost viewers.** Measured on 15 Nov: our plain Reels were 38-54% still frames, our duos 1-3%.
  Plain Reels do clearly worse in our data (the learning loop's one solid finding).
- **Our own Reels broke the rules the sources agree on:**
  - captions timed by guesswork;
  - the hook text came only on a test day;
  - the spoken hook allowed up to 14 words;
  - the caption carried three asks and the voice two more;
  - the learning loop did not look at the first seconds at all.

## Built into the pipeline (all in code, tested; no Claude anywhere at runtime)
| Change | Why (source) | Where |
|---|---|---|
| Every rendered Reel is measured for still frames; the health check fails a duo that stands still and reports how still a plain one is | Our plain Reels were 38-54% still; motion-video-kit's frozen-frame filter | `fma/motion.py`, `fma/site.py`, `fma/health.py` |
| Captions timed from the real voice (a small speech model as a clock, matched back to our own text; the old guess as fallback). On a real line the guess was off by up to 0.32 s | Every caption source; HeadTTS and kokoro maths read; faster-whisper chosen because `voice.py` edits the audio after synthesis | `fma/timing.py`, `deploy.yml` |
| The hook text on frame 0 of every duo, already moving, landing from 1.12x; six words at most; the lit words in red | All six Reels; instagram-agent-skill; Remocn hook-punch and words-on-screen; hyperframes | `reels/src/DuoReel.tsx`, `fma/duo_reel.py` |
| No header for the first 3 s; captions and header kept inside x 90-950 | iart, hyperframes, motionmaxxing ("no logo in the hook"); safe-zone table | `DuoReel.tsx` |
| Movement: a punch-in that snaps on each new line (not the hook's), a 7-frame shake on each punchline, the listener recoiling, a squash-and-spring "take" on each change of speaker, two-wave bobbing out of step, uneven four-frame blinks | claude-animated-shorts, huashu-motion, iart, motionmaxxing (all MIT/Apache) | `DuoReel.tsx`, `Characters.tsx` |
| A softer flash after the hook (1 frame up, 5 down, 32%) | hyperframes, Remocn; photosensitivity limit | `DuoReel.tsx` |
| Caption pages appear whole, with words not yet said dimmed; numbers stay lit | Remocn caption-speaker; hyperframes; Reel 2 | `DuoReel.tsx`, `fma/duo_reel.py` |
| A story with no duo gets Spark presenting alone in the animated Reel instead of the still card Reel (measured 6% still against 38-54%) | Our motion numbers | `fma/duo_desk.solo_script`, `fma/site.py` |
| The cover line (thumbnail and frame-0 text) gets the second fact-check too, and is dropped when it states as fact what the hook attributes ("AI CEOs can't be trusted" from "Helen Toner says…") | Today's post | `fma/verify.py` |
| Carousel slide 2 leads with the story's cover line | Caleb Ralston and instagram-agent-skill: Instagram re-serves an ignored carousel from slide 2 | `fma/carousel.py` |
| The producer is told: hook 10 words or fewer where possible, name or number in the first four words, sound like a friend, no universals; cover 3-6 words, different from the hook, keeping who said it | instagram-agent-skill (8 words / 3 s), hookscore, Dominik, marketingskills | `fma/reel_desk.py` |
| A style check sends a card back once for machine-sounding or baity phrasing ("it's not X, it's Y", "the result?", em dashes, "game-changer", "unveils", "Thoughts?") | marketingskills' AI-tells list; motionmaxxing/hyperframes banned words | `fma/reel_desk.style_problems` |
| The duo's facts: line 2 is the stake when the story states one; the last line brings back a name or number from line 1 | instagram-agent-skill beat sheet; beats.py loop check | `fma/duo_desk.py` FACTS_TASK |
| ONE ask in the caption (the send or save line; the voice asks the question); no filler hashtags; the site named as a fact, not an instruction | instagram-agent-skill ("two asks is the same as none"); marketingskills | `fma/social.py`, `fma/youtube.py` |
| The voice reads "70-78" as "70 to 78" and "$1" as "1 dollar" | HeadTTS and kokoro.js reviewed: both got ranges wrong | `fma/voice.py` |
| The multiplier report: each Reel as a multiple of its format's 90-day median, judged at day 11, with a top-tenth study once 20 Reels are judged. Stats now reach back 70 posts so day-11 numbers exist | Caleb Ralston (multiplier sheet, top 10%) | `fma/multiplier.py`, `fma/stats.py` |
| The learning loop's outcome now includes the share that stayed past the first seconds (0.5 stayed + 0.3 watch + 0.2 reach). Sends, saves and comments are reported, never learned from: at ~100 viewers no number of Reels could tell them from luck | marketingskills sample sizes; the 3-second problem | `fma/learn.py` |
| One test at a time on one Reel a day: the 4th Reel ends on its question and the name, without the tagline and comeback (until 6 Dec); the loop compares it under its usual guards | Caleb's 70/20/10; every source: end on the payoff, one ask | `fma/experiment.py`, `config/site.yaml` |
| Found and fixed: from 3 Nov the producer's facts rule read "use O / Y facts" (a line break inside ONLY) | — | `fma/reel_desk.py`, a test now guards it |

## Next, in order (each a test against the control, one change at a time)
1. **A cold open:** 1 s of the Reel's best frame (the number, both characters reacting) before the hook, which also
   makes the loop join (Remocn SOCIAL.md). Then a close-up open that snaps out (motionmaxxing).
2. **Captions:**
   - one pill that slides between words;
   - pages that break on silences and sentence ends, with no one-word orphans;
   - a hard cut, not a re-entrance, when pages follow each other (Remocn caption-core, remotion-captions-kit).
3. **One illustration per Reel:** the number panel counts up to the spoken word; two bars for a comparison; a text
   thread for the banter (iart data and text-message packs).
4. **Emphasis on a quarter of the lines only,** with the payoff at 60-75% of the length; accelerate through a joke,
   then a held silence before the best line (motionmaxxing, hyperframes, Remocn).
5. **A shorter Reel arm (20-25 s):** hook, stake, one fact, one joke, payoff, ask (marketingskills 15-30 s; our
   5.4 s average watch).
6. **A per-line voice check:** transcribe each spoken line and compare it word for word, numbers by value; redo the
   line on a mismatch (lemo-opuscar `asr_check.py`, MIT). The timing clock already transcribes; this adds the check.
7. **Per-frame QA:** unplanned "pop" frames, black or white frames, silences, a numbered contact sheet
   (claude-animated-shorts `short_qa.py`, MIT).
8. **Sound:** ducking from the word times instead of a sidechain; effects on the landing frame with varied pitch;
   kicks snapped to the music's known beat grid.
9. **An editorial verdict on every story** ("Hype or real?" plus "what it means for you"), as a pilot. It is
   Spark's stance, and gives viewers a reason to share and follow.
10. **The profile, by hand (Pavan's call):**
    - a name field with searched words ("Five Minute AI | Daily AI news");
    - a bio naming who it is for and the one need;
    - three pins in order: the problem, our proof, a free resource;
    - highlights for viewers on the left;
    - a daily first-hour reply to comments.

## Pilots that need Pavan's OK (they touch platform rules or his accounts)
- **A comment-keyword call to action** ("Comment GUIDE"), answered by hand or an official tool, never unofficial
  auto-DM. Meta's engagement-bait rule sits close to this; every high-comment Reel Pavan shared used it.
- **Re-running a winning Reel after 30 days,** only as a new cut (a new hook, a new edit). Re-uploading the same
  file conflicts with Instagram's originality rules; Reel 5's "so Instagram doesn't recognise it" is the line not
  to cross.
- **Fewer Reels a day** while reach stays under a few hundred (marketingskills, unproven): a cadence change is his.

## Where the sources disagree, and what we chose
- **Volume vs effort:** Dominik says ~20 Reels in 30 days; Caleb now prefers fewer, better ones. We keep the
  volume while we are learning, and let the multiplier report show when to compress.
- **Flash or no flash:** hyperframes and Remocn flash; motionmaxxing never does. We kept a soft one and can test it.
- **Unexpected-fact hooks:** Caleb says they are wearing out; the data-hook libraries say numbers work best. We
  lead with the number or name, framed for the viewer, and test the shapes.
- **Slow camera push:** hyperframes calls it a tell of generated video; claude-animated-shorts measured creeping
  holds in successful shorts. We keep a small creep, never as the only motion.
- **Learning from the bottom:** Caleb never studies flops; Dominik keeps a flop list. The top-tenth study looks only
  up; the learning loop compares both sides under its noise guards.

## For other engines (what transfers beyond Five Minute AI)
- **Measure stillness on every render;** for teaching Reels treat it as a number to test, not a gate (the social
  engine measured 64-93% still on SQL and govt-jobs Reels).
- **Time captions from the real audio,** not by letters.
- **One ask per post, everywhere.**
- **Judge each post as a multiple of its own format's median, at a fixed age.** Learn only from what the sample
  size can support: at ~100 reach, that is the first-seconds hold and watch time.
- **Never install a skill repo; port its maths by hand after a static scan.**
