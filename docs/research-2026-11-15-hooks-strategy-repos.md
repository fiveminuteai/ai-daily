# Hooks, scripts and strategy: what the repos say, read in full (15 Nov 2026)

Read from local clones, scanned first, nothing run: instagram-agent-skill, viral-hooks-skill, marketingskills, the
awesome-claude-video-skills list, anything2explainer, video-talkcraft, lemo-opuscar, openfilm, FreeVideo, manimgx,
threejs-skills, HeadTTS, kokoro. **No repo contains measured Instagram retention data:** every "this holds viewers"
is its author's craft claim unless marked. What was not read is listed at the end.

## The three findings that matter most
1. **Our 60% exit in 3 s is a first-frame and length problem more than a wording problem.** Two independent tools
   put the spoken hook at 8 words / 3 s, with a separate on-screen line of 6 words or fewer at frame 0. Ours allowed
   14 words (about 4 s).
2. **Our Reel ends with several non-content lines and several asks.** Every source says one ask, and the last line
   should echo the hook.
3. **Shares, saves and comments cannot be tested at ~100 reach per Reel** (thousands of views per arm are needed).
   Only the 3-second hold and watch time can, and our learning loop's outcome did not include the 3-second hold.

## 1. Hook rules
**instagram-agent-skill** (MIT), `skills/ig-reel/hooks.json`, six rules:
- The spoken line and the on-screen line are written separately; on-screen is six words or fewer.
- No setup: start at the sentence you would normally reach at second six.
- Say the number.
- The first frame is a hook too: a static picture with no motion and no text wastes it.
- If the hook would work for anyone in the niche, it is not your hook.
- Deliver the promise before the halfway mark.

**Its 26 formulas, judged for fact-checked third-person news:**
| Usable as is | Usable adapted | Not for us |
|---|---|---|
| Time Collapse (was A, now B), Before and After, If-This (a true, specific condition), Callout ("Android users:"), Head to Head (when the source compares), Deadline (a real date), Statistic (with its source), Reveal (say what it changes), Someone Else's Result (with a name) | Negative Command (only when the source says so), Replacement (only if the source says "replaces"), The Steal (how-to with the thing on screen), Numbered (exact count, 7 or fewer), Objection (a real viewer comment), Verbatim Question (for reply Reels and captions), Permission (if the source says it is no longer needed), Mid-Sentence Start (as structure), Superlative (only attributed: "Acme says it is the first") | First-person ones (Cost Confession, Receipt, Insider Leak, Flop Record). Clickbait: "Nobody tells you", "You are doing X wrong", Contrarian Flip for facts |

**Its hook scorer (`hookscore.py`), exact features:**
- **Length:** 5-12 words scores 100, falling off outside that range; minus 12 over 60 characters. Speech at 2.75
  words a second.
- **Specificity:** numbers, proper nouns, spoken numbers and money words (0 hits = 15; else 45 + 30 a hit).
- **Stakes:** words from a 90-word tension list (0 = 20, 1 = 70, 2+ = 100).
- **Frontload:** the first payload word in words 1-4 = 100, 5-7 = 70, later 40; minus 30 for a weak opener (so, ok,
  hey, today, basically, look, just, let's, did you, in this, there is, this is).
- **Address:** you/your 100, imperative 90, I/we 70, third person 35.
- **Dealbreakers:** "stop scrolling", "in this video", a greeting, a hashtag or an emoji in the hook.
- **Its own validation:** real vs bad hooks AUC 0.83, but a creator's hits vs misses only 0.56; only Specificity
  separated them.
- **For us:** a third-person news hook can never score "strong" (Address 35). Use Length, Specificity, Frontload and
  the dealbreakers to REJECT hooks; never gate on Address or Stakes, never pick a winner by the total.

**Its beat checker (`beats.py`):** hook 3.0 s (8 words); no line over 4.0 s; three lines in a row with no number or
name is flagged; the last line should share a word with line 1 (the loop); "short is usually right".

**viral-hooks-skill** (MIT, 100 formulas in 10 groups):
- Best fit for news: the "specificity and data" group ("[number]: what X costs", "[N]%: the share of…", "[date]:
  when…").
- Curiosity-gap and contrarian groups are mostly clickbait for fact lines ("the industry doesn't want you to
  know", "X is dead"); they are fine in the guest's joke.

**marketingskills** (MIT):
- **A hook is three parts,** visual action, spoken line and on-screen text, and they must complement, never repeat.
- **Diagnosis:** a weak 3-second rate means fix the visual opening and the on-screen text, same everything else; a
  weak 3-15 s hold means rework seconds 3-15, not the hook. One component per test.
- **Headline tests:** can the reader picture it; can it be proven true or false; could a competitor write this exact
  sentence.
- **Opening moves usable for news:** bold claim (the sourced fact), contrast, proof first (open on the number), old
  vs new, countdown.

## 2. Honest example hooks (an invented story: Acme launched Pocket; offline on Android; $5, was $10)
- "Acme's new AI, Pocket, works on your phone with no internet."
- "$5 a month: the price of Acme's new phone AI."
- "Acme's AI cost $10 a month. The new one costs $5."
- "Android users: Acme's new AI runs without a connection."
- "Acme says Pocket is the first big-lab AI to run fully offline."
- "Acme's $5 phone AI has one catch: no iPhone version yet."
On-screen lines (6 words or fewer, different from the spoken line): "NO INTERNET NEEDED", "$10 → $5", "ANDROID FIRST".

Never: "This changes everything", "Nobody is talking about…", or anything larger than the source ("your data never
leaves your phone" when the source only says it works offline).

**Rules for honest use:**
- withhold only the how or why, never the what;
- superlatives and benefits are attributed;
- a "you" hook needs a condition the source states;
- no universals ("nobody", "everyone", "most people").

## 3. Script and carousel structure
- **Reel beat sheet (instagram-agent-skill):**
  - 0-2 s hook, with motion in the first frame;
  - 2-7 s the stake, one line on why it matters to the viewer;
  - then one idea per beat, the frame changing every beat;
  - the payoff in the last 3 s, then ONE ask;
  - the last line echoes a word from the hook.
- **Ours compared:** no stake line at 2-7 s (our "take" comes at the end), no loop, several asks.
- **Length:** marketingskills says Reels 15-30 s, "if it can be shorter, make it shorter". Our 5.4 s average watch on
  38 s supports testing a 20-25 s arm.
- **Two-character comedy (lemo-opuscar, ideas only):**
  - a deadpan against a panicker;
  - a reaction close-up after each absurd fact;
  - a rule of three, then acceleration;
  - a 1-2 s hard silence before the best line;
  - the last line calls back the first.
- **Carousel (instagram-agent-skill):**
  - 6-10 slides;
  - a cover of 6 words or fewer, readable at thumbnail size ("the cover is 80% of the result");
  - slide 2 is a second cover that stands alone and states the stake;
  - each later slide has a 3-7 word headline and at most 25 words;
  - a recap slide before the end (the screenshot-and-send slide);
  - one action on the last slide;
  - slide numbers and the handle on every slide; type 32 px or larger.
- **Judge carousels on saves and completion,** not likes.

## 4. Caption, tags, profile, comments
- **Caption:**
  - about 125 characters show before "more";
  - for a Reel the caption carries the ask, context and search words as normal sentences (Instagram search reads
    captions);
  - ONE ask ("two asks is the same as none");
  - never a greeting, hashtag or emoji first.
- **Hashtags:** at most 5, specific to the story; cut generic ones. The repo says Instagram capped tags at 5 on
  18 Dec 2025; not verified by us.
- **Ours:** the Reel caption carried three asks (comment, send, link in bio), the spoken outro two more (comment and
  follow), and the filler tags were the generic kind.
- **Profile rubric (100 points):**
  - name field with searched words ("Five Minute AI | Daily AI news"), 12;
  - bio first line (who it is for and what changes), 12;
  - three pins (best proof, clearest explanation, best introduction), 10;
  - recent activity incl. replies, 10;
  - one link, 8;
  - 4-6 highlights named for questions, 8;
  - grid legibility, 8.
- **Rule:** views without follows is a profile problem; no views is a hook problem.
- **Comments:**
  - replies in the first hour do most of the work;
  - a question many people ask becomes a Reel;
  - never reply to a hater;
  - commenting on other accounts is 20 minutes a day, by hand: automated engagement breaks Instagram's terms.
- **Stories:** 3-7 frames a day, the ask at frame 4. We have no Stories step.

## 5. Measuring: what our learning loop lacked
- The 3-second hold was not in the outcome (it was 0.6 watch time + 0.4 reach); the skip rate was stored but unused.
- No fixed age for reading a Reel's numbers.
- No paired test (the same story with two openings is the repos' first test).
- **No power statement.** At ~100 viewers a Reel and a 40% hold, a 10-point change needs about 384 viewers an arm,
  roughly 4+ Reels an arm, so 8 an arm is about right for hold and watch time. For shares or saves no feasible
  number works yet, so the loop must not learn from them.
- No control for testing many features at once (about one false "confident" group at any time).
- No first-frame features (screen text present, length band, seconds to first visual change).
- **What it has that they lack:** shrinkage, the newest-third check, bounded weekly steps, an eval gate, a revert log.
- **Sample sizes they give:** 290 per arm to see a 50% lift on a 20% baseline; 7,700 on a 1% baseline; "allow 1,000+
  impressions before judging"; "fewer than 24 settled posts, call no pattern".

## 6. The awesome list: 15 candidates to vet next (licences as listed, unverified)
explainroo (MIT; Kokoro + Whisper timing, our stack), claude-faceless-shorts-creator (MIT; Remotion Shorts with
word-exact captions), paper-reel (MIT), papercut-explainer (MIT), skill-multik (MIT; "an event for every word"),
2d-character-sketch (MIT, graded "caution"), ClaudeAnimationBase (MIT; 31 acted emotions), viral-video-remake-skill
(MIT-0), ll-video-decomposer (MIT), video-clipforge (Apache-2; a daily pipeline with self-evolving scoring),
codebase-video and paper2video (MIT; agents verify every claim), agent-video-editor (MIT), kazi and
hbg-douyin-code-explainer-video (no licence: ideas only).

The list's "safe" grades come from a model reading READMEs, not from a code audit. In its own test, plain Claude
Code with no skill also passed.

## 7. Checks other pipelines have that we lacked
1. A per-line voice gate: transcribe each spoken line and compare it word for word with the script, numbers by
   value; regenerate on mismatch (lemo-opuscar `asr_check.py`, MIT).
2. Freeze detection on the finished file (ffmpeg freezedetect, noise 0.003 for 0.8 s). **Built 15 Nov as `fma/motion.py`.**
3. A reading-time and in-zone check for every text box: on screen at least letters/15 + 1.5 s and inside the safe
   zone (`readcheck.mjs`, MIT).
4. Every drawn string and number must be in the fact-checked list, including count-up intermediate values.
5. No window over 2 s without a visual event; a visual within 10 frames of each cut.
6. Loudness measured after encode: -14 LUFS, true peak -1 dBTP; the two voices within 4 dB of each other.
7. File sanity: 1080x1920, length within 1.5 s of plan, an audio track.
8. A fresh-context vision review of a contact sheet (needs a local vision model).
9. Captions never split a number from its unit.
10. The two characters' voices separated in pitch and speed.

## 8. Voice: what to port into `fma/voice.py`
- **Mouth shapes:** HeadTTS (MIT) maps Kokoro's phonemes to 15 mouth shapes (aa, E, I, O, U, PP, FF, TH, DD, kk,
  CH, SS, nn, RR, silence): a fallback for when Rhubarb is missing.
- **Kokoro's own timing:** 40 duration frames a second. Whether our ONNX model exposes durations is not
  established; `fma/timing.py` uses a speech model instead because `voice.py` edits the audio after synthesis.
- **Text rules worth adding:**
  - ordinals ("3rd");
  - plain ranges ("70-78" → "70 to 78");
  - years only in context;
  - £, € and ₹ like $;
  - "$1" → "1 dollar";
  - times ("9:05");
  - Dr. / Mr.;
  - dotted acronyms;
  - "Llama3" → "Llama 3";
  - negative numbers;
  - %, &, +.
- **Voice quality:** several voices we blend are graded D in kokoro.js's own table (af_jessica, af_river, bf_lily,
  bm_lewis, am_onyx).

## 9. Text that steers an AI agent, and licence traps (for anyone using these repos)
- **marketingskills** `AGENTS.md`: fetch a versions file from GitHub once per session and `git pull` on "update
  skills"; an advert for the maintainer's product inside agent instructions; one `curl … | sh` in a tools doc;
  committed bytecode (never run that script).
- **instagram-agent-skill:** reads and writes files under `~/.claude/instagram/`; one skill gives yt-dlp commands
  and drives the user's browser; another strips "invisible watermark characters" (Meta labels AI content: never use
  it to hide that).
- **lemo-opuscar:** resets itself to the latest main on every run; forces a language question over the user's
  settings; imposes a map policy on all output.
- **openfilm:** "Run `npx -y openfilm@latest` and follow the manual it prints".
- **video-talkcraft:** upgrade dependencies at every video; suggests @-mentioning the author in the published
  description; bundled sounds may bar monetised use.
- **anything2explainer:** credits itself on the end card by default.
- **FreeVideo:** tells the agent not to end its reply; copies itself into `~/.claude/skills`, deleting a folder of
  the same name; starts PowerShell with the execution policy bypassed.
- **manimgx:** points the agent at a remote primer; the default voice sends text to a paid cloud service.
- **HeadTTS:** a world-writable cache folder on install; a server with no authentication.
- **Licences:** anything2explainer and video-talkcraft are PolyForm Noncommercial; lemo-opuscar's docs and prompts
  are CC BY-NC (its code is MIT).

## Not read (so nobody assumes it was)
- **marketingskills:** 37 of 53 skills (ads, SEO, pricing, CRO, most email) and its CLI tools.
- **The awesome list:** the promo, motion and music groups (148 entries) were only keyword-filtered.
- **lemo-opuscar:** 92 of 99 style documents.
- **openfilm, FreeVideo, manimgx:** most of the source; FreeVideo's `network.py` was not read, so "no telemetry
  found" is not "proven none".
- **threejs-skills:** the 13 skill files (no use for a 2D Reel).
