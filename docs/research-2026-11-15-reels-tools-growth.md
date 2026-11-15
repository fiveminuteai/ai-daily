# Research, 15 Nov 2026: 27 repos, 6 Reels, 4 YouTube videos, and better alternatives

Pavan shared these on 15 Nov: "check and adapt if they are virus free … transcribe or watch from all of them and
learn and improve on top of it … Don't ignore anything, do thorough research … if you can identify similar and
better repos go ahead and fetch them and learn from them." This file records what was checked, how, what was found,
and what Five Minute AI should copy, beat or drop. Sources are marked; "our data" means @fiveminute_ai's own numbers.

## How it was checked (so nothing is taken on trust)
- **Repos:** read through the GitHub API first: metadata, file tree, install hooks, every SKILL.md and agent file, and
  security advisories. Promising repos were then shallow-cloned, each into its own empty folder in the session
  scratchpad, with git hooks disabled. `docs/pilots/skillscan.py` was run on each before any file was read. Nothing
  from any repo was installed, built or run.
- **Reels:** opened in the built-in browser without logging in. The caption and comment counts were read, and the
  frames were sampled by seeking the video at 5-25% steps. No audio was heard; the spoken words were judged from the
  on-screen captions.
- **YouTube videos:** the "Show transcript" text was read in the browser; nothing was downloaded. Three videos were
  read in full. The 6 h course was about 60% read, and its Team section only skimmed (chapter openings plus a keyword
  scan).

## A. The six Reels

| # | Account | What it is | Length | Numbers seen | Lesson for us |
|---|---|---|---|---|---|
| 1 | maheshigexpert | Still "Ultimate Instagram Cheat Sheet": 24 Reel formats (talking head, B-roll + text hook, reaction, myth or fact, this or that, problem/solution, Q&A, skits, tutorial…) | short | 10.4K likes, 244 comments | A screenshot-and-save list earns saves. Our missing formats: **myth or fact** (pilot C), **this or that**, **rating Reels**, **reaction / split screen** |
| 2 | _post2all | Remotion-made kinetic text: "Don't post until these 5 free Claude skills", an "x/5 installed" progress counter, repo cards, ends "Comment SKILLS" | 50 s | 1.9K likes, 2.3K comments | **A progress counter is a retention device** (viewers stay to reach 5/5). **Comments outnumber likes** because of the keyword CTA. Built with remocn + Remotion, our own stack |
| 3 | yournishaant | "Episode 4: Finding crazy GitHub repositories": talking head over a screen recording of public-apis, with a fixed top label "CRAZY GITHUB REPO" | 41 s | 237K likes, 28K comments (almost all "API") | **A numbered series + one fixed label** makes a binge habit; **comment-keyword-for-link** drives comments 1:8 to likes |
| 4 | harshsharma_ai | Hindi talking head + screen, contrarian on-screen hook ("You haven't seen a real AI agent in production"), Hindi word captions, ends "Comment anything for the full guide" | 108 s | (caption only) | **Contrarian hook as text**; an **Indian-language** version of the same news is an open lane |
| 5 | mate.jimenez | Spanish split screen: face on top, a diagram underneath that it walks through step by step. "Publica todo mínimo 5 veces": every idea in 5 placements, including **re-posting a Reel 30 days later** | 89 s | 41 likes, 21 comments (2 days old) | **Repurpose every story 5 ways and re-run winners after 30 days**; a split-screen "explainer + diagram" layout |
| 6 | godigitalwithaakriti | 12 s "4 videos to become a content GOD" (the four videos in section B) | 12 s | 2K likes, 567 comments | A **curation Reel** (a list of other people's best work) is cheap and saveable |

Patterns across all six:
- Every Reel with high comments uses a **one-word comment CTA** that is answered with a link.
- The hook is always **text on screen from frame 1**.
- Four of the six are **talking heads with a screen** behind or below.
- Two are **numbered or serialised** ("Episode 4", "x/5").
- None is a plain news read-out.

## B. The four YouTube videos (summarised; full notes from the study are kept below)
1. **Dan Koe, "How To Build A Better Personal Brand Than 99% Of People"** (24 min).
   - Trust is the business model. Persuade the uninterested: open on a desire or a pain, never on dry information.
   - Swipe file of other creators' 2x outliers, each with 3-5 bullets on why it worked.
   - "People follow people who share ideas", so a stance matters.
2. **Kallaway, "0 to 2M+ followers in 3 years"** (27 min).
   - Of the "Lego bricks" (topic, angle, format, hook, substance, CTA, story, layout, visuals, audio), **only the
     idea and angle multiply views ~100x**.
   - Contrarian insights come before hooks. 1x1x1: one traffic source, one customer, one offer.
   - "Gold standard" execution is how a late entrant catches up.
3. **Caleb Ralston, "How to Build a Personal Brand (Full Course)"** (6 h 22 min).
   - **Hook window 2-3 s on short form.** "Unexpected fact" hooks are getting tired; bold or contrarian claims,
     pattern interrupts and questions work.
   - **Carousel: a hook on slide 1 AND slide 2**, because Instagram re-shows an ignored carousel from slide 2. One
     image plus 1-2 sentences per slide; listicles.
   - **Multiplier sheet:** the per-format median of the last 75-90 days, each post judged as a multiple of it at
     **day 11**, re-baselined monthly, 2-4 metrics that change actions.
   - **70/20/10:** proven / iterations / experiments.
   - **Top 10% study monthly:** look only at what all the winners share; never learn from the bottom.
   - Reply to the people already commenting. Inside jokes and shared language. "Accordion": volume early to learn,
     then fewer, better pieces.
4. **heyDominik, "Grow fast on Instagram in 30 days (2026)"** (19 min).
   - Follows and purchases happen mostly in the **first 14-30 days after discovery**; about 20 Reels need to be
     seen in that window.
   - **Optimise for the first-time viewer:** the last 9 posts must all clearly serve one need.
   - "X things I'd never do as a Y" format.
   - **Borrow formats from other niches** (topics from yours, opinions from you, formats from elsewhere).

Where they agree:
- The idea or angle beats production.
- A contrarian or different view is the main hook.
- Learn from outliers, not averages.
- Narrow focus.
- Trust over hard selling.
- Endurance.

Where they disagree:
- Volume vs effort: Dominik says about 20 Reels in 30 days; Caleb now prefers fewer, better ones.
- Copying inside the niche: Dan Koe studies admired creators, while Dominik says borrow formats from outside it.
- How much polarisation: Dan Koe wants it; Caleb warns against controversy for its own sake.

Not covered by any of the four:
- Comment-keyword DMs, hashtags, posting times, trial Reels and covers.
- Mid-Reel retention editing.

## C. The 27 repos Pavan listed (plus two named in Reel 2)

Overall:
- **Malware:** none found.
- **Security advisories:** none on GitHub for any of them.
- **Planted binaries or hidden install hooks:** none.
- **Agent-steering text** (an instruction file telling an AI agent to update, install or report on its own) is in four
  repos: hyperframes, lemo-opuscar, openfilm and motionmaxxing. Each is quoted in its row.

| # | Name → real repo | Licence | Safety | Decision for FMA |
|---|---|---|---|---|
| 1 | OpenToonz (opentoonz/opentoonz) | BSD | Official, maintained; releases unsigned | By hand only: drawn mouth/blink frames (pick this or Pencil2D) |
| 2 | Friction (friction2d/friction) | GPL-3 | Best-signed releases (sha256/sha512/sig) | By hand: hook-card and end-card motion templates |
| 3 | FreeMoCap | AGPL-3 | v2 alpha | Park: webcam gestures could drive Spark later |
| 4 | Synfig | GPL-3 | CI-built, checksums; use 1.5.5 | Separate tool: bone-rigged characters, headless CLI render (try on an Ubuntu runner first) |
| 5 | Effekseer | MIT | Use build 1808+ (sigstore provenance, a CVE fixed) | Drop: particles are easier in Remotion. **Avoid the lookalike `kanaworksai-hue/effekseer-vfx-skill`** |
| 6 | theater → Theatre.js | Apache-2 | Public repo stale since 2024 | Ideas only (visual keyframe editor) |
| 7 | Pencil2D | GPL-2 | Use 0.7.2 (bundled-ffmpeg CVEs fixed) | By hand (or OpenToonz) |
| 8 | OpenVDB | Apache-2 | Fine | Drop: 3D volumes, no use for 2D Reels |
| 9 | svg.js | MIT | Fine | Drop: clock-based animation fights Remotion's frame-based rendering |
| 10 | Natron | GPL-2 | Last stable 2022 | Drop: Remotion + ffmpeg cover it |
| 11 | APILayer.com (Idera) | Commercial | Hands over contact data; paid plans non-refundable | Drop: not needed, adds an account and a key |
| 12 | PlacesToPostYourStartup (mmccaff) | CC0 | Text only | Use by hand: launch checklist for the email list and the Desk page. Avoid the lookalike lists with MCP servers |
| 13 | motion-skills (iart-ai) | MIT | Hub repo, mostly an advert | Its sub-repo **tiktok-video-skills** is the useful one: fetched and scanned clean, see D |
| 14 | hyperframes (heygen-com) | Apache-2 | Every skill tells the agent to run a usage beacon ("account-linked when signed in"); telemetry is on unless `HYPERFRAMES_NO_TELEMETRY` | Ideas only: the **drop / rail / embed** caption rule |
| 15 | threejs-skills | MIT | Markdown only; owner account 16 days older than the repo | Drop (no 3D) |
| 16 | awesome-claude-video-skills | CC0 | A list of 503 repos; its "SAFE" badges come from a third party, don't trust them | Index only (Pavan's list came from here) |
| 17 | whisper (openai) | MIT | Clean, models hash-checked | **Adopt as faster-whisper** (better, same model): real word timing for captions |
| 18 | lemo-opuscar | Code MIT, prompts CC BY-NC | Its setup runs `git reset --hard` to main on every use and installs in the background | Ideas only ("style = STYLE.md + demo" presets); never copy its prompts |
| 19 | openfilm | MIT | Org 6 weeks old; the skill is one line, "Run `npx -y openfilm@latest`", so the real instructions can't be reviewed | Drop |
| 20 | ffmpeg-skill (kajisho5) | MIT | Fetched and scanned clean; stdlib only, no network. Its `.claude/settings.json` turns on 6 plugins for anyone opening the repo in Claude Code | **Port:** platform delivery checks, a 3x2 contact sheet, karaoke caption code |
| 21 | anything2explainer | PolyForm **Noncommercial** | Clean | Ideas only (QC gates, TTS fallback chain); copying code is not allowed |
| 22 | freeVideo (FlashML) | Apache-2 | Prefers third-party mirrors; needs an 8 GB GPU | Drop for production |
| 23 | manimgx | MIT + bundled GPL | Clean | Drop for now (maths inserts only) |
| 24 | video-talkcraft | PolyForm **Noncommercial** | Clean | Ideas only (script → word timing → storyboard → render, plus a freeze-detect gate) |
| 25 | huashu-motion (alchaincyf) | MIT | Fetched and scanned clean (the hidden characters are a CJK regex range) | **Port:** beat tracker (`cli/lib/beats.js`), Kokoro long-text chunking (`cli/lib/kokoro.py`) |
| 26 | motion-video-kit (echris6) | MIT | Fetched and scanned clean | **Port:** frozen-frame check, loudness check, SFX softening, independent-critic prompts |
| 27 | motionmaxxing | Apache-2 | Looks for an ElevenLabs key in `.env`, `~/.elevenlabs` and `~/.claude.json` | Ideas only: the "never ship" slop list, "cut on motion, never on rest" |
| + | remocn (Remocn/remocn) | MIT | Source you copy in (shadcn registry), pure Remotion + React; its only install hook builds its docs site | **Adopt:** 789 components incl. `caption-karaoke`, `caption-active-pop`, `hook-punch`, `impact-shake`, `counter-reveal`, `crash-zoom` |
| + | marketingskills (coreyhaines31) | MIT | 60K stars | Ideas: its social skill bans AI tells like "it's not X, it's Y" |

## D. What our own Reels show when measured with these tools (15 Nov, today's four Reels)
Measured with motion-video-kit's frozen-frame filter (frame difference at 10 fps; YAVG under 0.35 counts as frozen)
and ebur128 loudness:

| Reel | Type | Length | Near-frozen samples | Big visual changes | Loudness |
|---|---|---|---|---|---|
| 1 | plain | 54.8 s | **38%** | 10 | -14.4 LUFS |
| 2 | duo | 35.3 s | 3% | 7 | -15.1 |
| 3 | duo | 38.5 s | 1% | 9 | -14.8 |
| 4 | plain | 45.1 s | **54%** | 8 | -14.5 |

- **Plain Reels are 38-54% still frames and run longer.** That fits the learning loop's one solid finding: plain
  Reels do clearly worse.
- **Duos move, but slowly.** A big change comes about every 5 s; the short-form guides ask for one every 2-4 s, at
  uneven intervals.
- **Loudness is fine.** Instagram's target is about -14 LUFS.

## E. Better than what was on the list (searched, fetched, scanned)
Fetched and scanned clean (shallow clones, hooks off, static scan first, nothing run): HeadTTS,
claude-animated-shorts, remotion-captions-kit, remotion-dev/template-tiktok, remotion-dev/skills, rhubarb-lip-sync,
lipsync-engine, hexgrad/kokoro, motion-video-kit, ffmpeg-skill, huashu-motion, tiktok-video-skills.

- **Our captions are timed by guesswork (verified in our code).** `fma/pulse_reel.py` `word_times()` places each
  word by its share of the letters, and duo Reels use it too (`fma/duo_reel.py`), so the highlighted word drifts
  from the voice. Better options:
  - **kokoro-onnx 0.6.1** (MIT; we pin 0.4.7 in deploy.yml) has `create_timed()` with per-phoneme times. It only
    works with an ONNX model exported with durations: ours isn't, and whether the Apache-2.0
    `onnx-community/Kokoro-82M-v1.0-ONNX-timestamped` model works with it is unverified.
  - **faster-whisper** (MIT, base.en, int8, CPU) with word timestamps on each finished line, matched back to the
    known script. This is the robust route, because `voice.py` trims and squeezes the audio after synthesis.
    (openai/whisper is slower; stable-ts was archived in May 2026; whisper-timestamped is AGPL.)
- **Lip sync is already right.** Rhubarb v1.14.0 is in production and still the latest. HeadTTS (MIT) maps Kokoro's
  own phonemes to 15 mouth shapes, a fallback for when Rhubarb is missing.
- **Life in the characters** (claude-animated-shorts, MIT code only; its sample frames are someone else's, don't use
  them):
  - an impact "kick" (a shake that decays over 7 frames) on the punchline word and the hook;
  - reactions that land 2 frames BEFORE the word;
  - a blink that hides each expression swap;
  - a white flash after the hook line.
- **A motion QA gate** (`short_qa.py`, MIT, ffmpeg + numpy) reports black, white, frozen and "pop" frames and a
  "held %". Fail a render whose first 3 s barely move.
- **Captions:**
  - remocn's `caption-active-pop` / `caption-karaoke` (MIT);
  - remotion-captions-kit KineticSlam: each word pops in over 180 ms, and an emphasis rule colours the number or
    company name;
  - `@remotion/captions` `createTikTokStyleCaptions` for 2-3-word pages;
  - the hyperframes rule: drop filler words, keep the line as the "rail", and give at most ONE big "embed" word per
    beat.
- **Sound:**
  - Kenney "Interface Sounds" and "Impact Sounds" (CC0, verified on kenney.nl);
  - claude-animated-shorts' procedural whoosh, oof and whoa (numpy only).
  - Avoid the meme clips in remotion-dev/skills' list (vine-boom, wilhelm scream, Windows XP error): unclear
    licence, and wrong for clean comedy.
- **Voices:** Kokoro stays.
  - Chatterbox (MIT, emotion control) is a laptop trial only: 0.5B, slow on CPU, and it adds a watermark.
  - pocket-tts has CC-BY weights, so attribution would be needed.
  - **Avoid** F5-TTS (non-commercial weights), the MMS aligner (non-commercial) and fish-speech (unclear).
- **Engines:** stay on Remotion. Revideo (MIT) is a licence hedge only. (Remotion's licence is free for organisations
  of up to 3 people; recheck if FMA grows.)
- **Automation projects to avoid** (ShortGPT, MoneyPrinter, upload pipelines): stock-footage b-roll and unofficial
  posting. gyoridavid/short-video-maker is the closest architecture to ours (Remotion + kokoro + whisper.cpp) but has
  been stale since June 2025.

## F. Decisions: what Five Minute AI does with all this

### Fix first (evidence in our own data; each is a pipeline change, no Claude at runtime)
1. **The first 2 seconds.**
   - Hook text and the first spoken words carry the viewer's stake or a contrarian angle, in plain words ("Your
     free ChatGPT just got worse").
   - The strongest visual and motion are on frame 1 (a punch-in or kick), with speech from 0.0 s.
   - Sources: Caleb, Dan Koe, tiktok-video-skills, and our 60%-gone-in-3-s.
2. **Kill still frames.**
   - The plain fallback Reel is 38-54% near-frozen: give it the duo's motion, or drop it for a carousel slot.
   - Add a QC gate: fail a render if the first 3 s are under a motion bar, or if more than 15% of the Reel is
     frozen.
   - Add uneven pattern interrupts every 2-4 s: punch-in, kick on the punchline, caption pop.
3. **Real word timing for captions** (faster-whisper alignment, or kokoro-onnx timed output once verified).
   Captions: 2-3-word pages, one accent word.
4. **Angle before story.**
   - The writer drafts 3 angles per story and scores them for broad appeal and contrast.
   - The Reel picks the story with the best angle, not the biggest news (Kallaway's "only the idea multiplies").
5. **Measure like Caleb.**
   - A multiplier report: each Reel as a multiple of the per-format median of the last 75-90 days, judged at
     day 11.
   - 4 metrics: 3-s hold, average watch, shares+saves per reach, follows per reach.
   - A 70/20/10 slot plan (proven / iterate / experiment), one variable per experiment.

### Test next (as pilots beside the normal flow, like pilot D)
- **A fixed editorial stance** per story: "Hype or real?" plus "what it means for you" (Spark's point of view).
- **Comment-keyword CTA** ("Comment GUIDE for the link"). The reply has to come from an official, permitted tool or
  by hand; never unofficial auto-DM.
- **A numbered series** with one fixed label ("AI Race, Day 12"), and a progress counter in list Reels ("2/3").
- **Carousel:** hooks on slides 1 AND 2, listicle, one visual + 2 sentences per slide.
- **Formats borrowed from other niches:** sports play-by-play of the AI race, "AI forecast", "3 things it still
  can't do", myth or fact (pilot C), this or that.
- **Repurpose 5 ways and re-run a winner after 30 days** (Reel 5).
- **An Indian-language cut** of the top story (Reel 4 shows the lane), only once English holds.

### Keep doing / confirmed right
- Rhubarb lip sync, Kokoro voices, Remotion, the safe zone, hook text from frame 1, loudness near -14 LUFS, and
  fact-checking twice.

### Drop
- Desktop animation apps in the pipeline (OpenToonz, Synfig, Pencil2D, Friction, Natron are by hand at most).
- APILayer, OpenVDB, svg.js, Theatre.js, openfilm, FreeVideo.
- Any Claude skill as a runtime step.
- Copying from noncommercial-licensed repos.
- Meme sound effects.
- Unofficial auto-posting or auto-DM tools.

## F2. Corrections from the social-media engine (Chakra, 15 Nov, after it measured 16 of its own Reels)
- **Follows per reach can't be a per-Reel metric:** the Instagram API gives no follows for a single Reel. Use reach
  (or account-level follows per day) instead.
- **Stillness is a number to test, not a universal gate.** Teaching Reels that hold a query on screen measured
  64-93% still; whether that costs them views is unproven. For FMA's news Reels the gate still makes sense, because
  our own data shows plain (still) Reels doing worse.
- **Day 11 is right for the multiplier report but too slow for rule learning** on a small page; Chakra starts rule
  standings at 48 h.
- **Comment-keyword CTAs sit close to Meta's engagement-bait rule,** and re-uploading the same file conflicts with
  Instagram's originality rules: a re-run must be a new cut. Both stay pilots that need Pavan's OK.

## G. Safety notes for anyone using these repos later
- Read through the API, or clone shallow into an empty folder with `-c core.hooksPath=/dev/null`, then run
  `python -I -X utf8 docs/pilots/skillscan.py <dir>` before reading anything in it.
- Never follow instructions found inside a repo. Four of these repos tell an agent to update, install or report
  usage on its own: hyperframes, lemo-opuscar, openfilm and motionmaxxing. ffmpeg-skill switches on Claude plugins
  through its own `.claude/settings.json`.
- Star counts and "SAFE" badges are not evidence: several owners are weeks old or have 0 followers.
