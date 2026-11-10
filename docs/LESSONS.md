# Lessons: every mistake, its fix, and what it teaches

Kept by Claude, who builds and runs Five Minute AI, at Pavan's request (10 Nov 2026): "maintain a journal of your
mistakes and fixes and your study, build on top of it and improve ... these lessons are goldmines for my later
work." Rules for this file:

- Every incident gets a row the same day: what broke, the root cause, the fix (commit), and the **guard** that now
  catches it (a test, a check or a fallback). A fix without a guard isn't finished.
- Before shipping anything new, run the **pre-mortem checklist** at the bottom.
- The general lessons are written to carry over to Pavan's other projects (Chakra, crypto, equity, faceless pages).

## Incident log

| Date | What broke | Root cause | Fix and guard |
|---|---|---|---|
| 31 Oct | GitHub skipped the scheduled post and Reel runs | GitHub cron is best-effort, worst right after an org move | `clock.yml` self-chaining clock + laptop trigger; crons are only backups |
| 31 Oct | A Gemma haiku line was credited to a "Google spokesperson" | Quote speakers weren't checked | Model check of quote speakers and section titles |
| 2 Nov | Every "Your take?" question was dropped | The checker treated an opinion question as a factual claim | Questions are their own claim kind |
| 3 Nov | "Apple unveils a robot" for a robot Apple only plans | The writer upgraded a plan into a launch | Producer rule: a plan, report or leak is not a launch; rejected lines go back to the writer |
| 3 Nov | Re-ran a day after withdrawing the post; no model budget left | Didn't check provider quotas before a destructive redo | Check budgets before redoing; fallback model chain with retries |
| 4 Nov | Pausing the blog broke the site deploy | Tests read the live config | Tests pin control-app settings |
| 5 Nov | Fact-checker crashed on "2.1.312" | Number parser assumed one decimal point | Version-number aware parsing |
| 6 Nov | Groq's daily cap drained; the 6 Nov post skipped twice | My local tests used the production keys | Cloud keys off outside CI unless `FMA_ALLOW_PROD_KEYS=1` |
| 6 Nov | The local 7B, used as fact-checker, dropped 33 true sentences | A weak model can't judge evidence | Code judge + strong-model review; the 7B only writes, never judges |
| 6-7 Nov | Patches corrupted (`\b` became a backspace); one push went out with failing tests | Inline shell heredocs and an unchecked exit code | Patches written as files; push only when pytest's real exit code is 0 |
| 7 Nov | The backup routine couldn't write a post | Its cloud sandbox can't reach news sites | Daily run saves the day's collection; backup reads it (`collect --saved`) |
| 8 Nov | Two Reels lost their duo; METR read as "Meta" | Number-binding check flagged rewordings; TTS guessed the acronym | Binding check v2 with tests; pronunciation map |
| 8 Nov | Sent previews deleted before replacements arrived | Cleaned up too early | Keep sent files until the replacement is sent (memory rule) |
| 8 Nov | A new closing pushed a Reel past 45 s; it fell back to plain | Length depends on the closing picked | Try shorter closings before giving up the duo |
| 8 Nov | A card stated an unproven spy claim as fact | Hook dropped the attribution | Hooks keep "a memo claims" / "says"; layer-2 checks certainty |
| 9 Nov | A Reel aired "At least the spy got laid" on a CEO's affair story | Banter added a free comeback slot with no decency check | `joke_problems` filter (sex, violence, insults, swearing), sensitive-story mode (no comebacks, no private-life jokes), editor veto |
| 9 Nov | The sensitive-story check missed that very story | Rule needed two mentions; the story said "affair" once | One mention anywhere in title, story or card |
| 9 Nov | Three of four Reel cards dropped; one Reel that day | Backup writer cited S1-S3 for a story whose source was S4 | **10 Nov:** a failing line is re-cited to its own story's sources if they support it |
| 9 Nov | Live post repeated one sentence 13 times; fragments like "They then select…" | Writer padded after the checker removed sentences | `dedupe_sentences` before the gate; gate refuses repeats, dangling openers, sections under 40 words |
| 9 Nov | Carousel chart ran over the footer and mixed % with a 1-5 score | No layout bound; any bars allowed | Slides shrink to fit; max 3 bars of one measure; no quote slide on sensitive stories |
| 9 Nov | The same Short uploaded twice to YouTube | A run lost its record when its commit clashed with my push to the same file | Every post is journalled and replayed after a merge clash |
| 9 Nov | Posting runs looped every 4 minutes | Old Reels returned 404 for YouTube and counted as failures | 404 = give up at once; a YouTube miss never fails the run |
| 9 Nov | The 19:30 Reel never posted | I hand-scheduled a time no clock event covered | **10 Nov:** 22:30 IST sweep posts anything still due |
| 9 Nov | YouTube app couldn't publish; tokens would expire in 7 days | Google requires a privacy page for production; Testing tokens expire; a logo forces brand verification | Privacy/terms pages; app In production; no logo; `check-youtube.yml` |
| 10 Nov | All three Reels lost their duo | Facts-step false alarms: "October 16", "Fable 5.2", the word "filing" | Dates and names skipped; "filing" allowed; **duo falls back to the checked card's lines** |
| 10 Nov | Cards said "tumble", "dramatically", "sends your files" | Model drifts toward bigger, more certain wording | Overstatement words allowed only when the cited source uses them |
| 10 Nov | Every test run changed `data/bank` | Pipeline tests wrote the real knowledge bank | Autouse fixture points the bank at a temp folder |

## General lessons (they carry over)

1. **Every blocking check needs a graceful fallback.** A check that can refuse output must say what happens next:
   a shorter closing, the card's own lines, a re-cite, a plain Reel. "All or nothing" silently costs whole days.
2. **False alarms cost as much as misses.** Before shipping a check, run it over everything already published and
   count what it would have blocked (the decency and overstatement checks: 0 of 51 jokes, 0 published lines).
3. **Taste and safety rules belong in code, not only in prompts.** Prompts are requests; a regex and a test are
   guarantees. Every time a model was only *asked* not to do something, it eventually did it.
4. **Anything that posts must be idempotent.** Record what was done before anything else can overwrite the record,
   and check the record before acting again (journal and replay; find-by-caption before reposting).
5. **Automation writing shared state needs a merge story.** Two writers to one file will clash; decide in advance
   who wins and how the loser's work is replayed.
6. **Every scheduled thing needs a trigger, and a sweep behind it.** If an item can be queued for a time, something
   must run at that time, and a catch-all run must exist for the times nobody thought of.
7. **Tests never touch production data or keys.** Not "carefully": structurally (fixtures, env switches).
8. **Weak models can write, not judge.** Use code checks and a strong reviewer for facts and humour; a 7B grading
   its own jokes gives 7/10 to nonsense.
9. **Models drift in predictable directions:** bigger numbers, stronger verbs, more certainty, repetition when
   squeezed, and wrong citation numbering when sources are re-indexed. Check for each drift explicitly.
10. **Verify at the layer of the claim.** "Deploy succeeded" isn't "the Reel is right": download the live file,
    transcribe it, look at the frames, read the live page.
11. **When I edit live content by hand, I race the automation.** Hold the item, push, wait for the render, check
    the live file, then release it. Never edit a queue file a scheduled run may be writing at the same moment.
12. **Platform facts expire.** API parameters, quotas and policies changed monthly in 2025-2026 (Trial Reels API,
    AI label, hashtag cap, YouTube's unverified-upload rule): verify on the official page, note the date.

## Study notes (what the research found)

| Date | Finding | Source quality |
|---|---|---|
| 8 Nov | Instagram ranks Reels mainly by watch time, sends per reach and likes per reach; sends matter most for non-followers | Mosseri, Jan 2025, secondary |
| 8 Nov | Original content beats reposts; aggregators lose recommendations | Instagram official + secondary |
| 8 Nov | `is_ai_generated` (22 Jun 2026), `trial_params` (3 Dec 2025), `reels_skip_rate` (3 Dec 2025) are in the Graph API | Meta changelog, official |
| 8 Nov | Hashtags capped at 5 in the app (Dec 2025); API docs still say 30 | Secondary vs official |
| 8 Nov | YouTube uploads from unverified projects are public since 2 Nov 2026; uploads have their own 100/day quota | Google official |
| 8 Nov | TikTok unaudited apps post private only; LinkedIn posting API needs a registered company; X API is paid | Official |
| 8 Nov | Our duo Reels reached ~10x the plain ones (48-129 vs 3-18); median watch 6.2 s; zero sends | Our data |
| 9 Nov | Repos vetted: instagram-agent-skill and youtube-agent-skill (MIT, clean; ideas adopted), VoiceStudio (clean, voices only), Pixelle/Open-Higgsfield (paid backends, skip), InfiniteTalk (14B, too big), 3b1b/videos (non-commercial licence) | Read without running |
| 9 Nov | Hosting location doesn't change earnings; viewer location does (US pays most) | Reasoning, standard ad economics |
| 10 Nov | VoiceStudio tested live (Docker): its default OmniVoice (voice cloning) is CC-BY-NC, so no commercial use; the one commercial-safe engine installed, KittenTTS (Apache-2.0), read 1.5-2x slower than Kokoro, misread "OpenAI", and has 8 stock voices with no blending. Kokoro stays; nothing adopted | Our test, licence data from the repo |
| 10 Nov | Schema.org JSON-LD raised the AEO score: home 70 to 85, about 60 to 75, post 75 to 95 | ATLAS check, our site |

## Pre-mortem checklist (before shipping anything)

1. If this fails, what happens to today's output? Is there a fallback, and does the failure block anything else?
2. Run any new check over all published history: how many good items would it have blocked?
3. Is it safe to run twice, or twice at the same time? What records it, and can a clash lose that record?
4. Does anything it schedules have a trigger at that time?
5. Can a test or a local run reach production data, keys or accounts?
6. Is the rule a prompt or code? If it matters (facts, decency, length), it must be code with a test.
7. How will I verify it at the final layer (the live file, the posted Reel, the page a reader sees)?
8. Does it keep the house rules: every fact checked, healthy comedy, no clickbait the story doesn't back?
