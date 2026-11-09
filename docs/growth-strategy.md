# Five Minute AI: growth strategy (8 Nov 2026)

Owner: the blog session (Claude), with Pavan deciding anything public-facing that changes the look or the voice.
The system that runs it: `fma/growth.py` (scoreboard), `fma/social.py` (captions), `fma/instagram.py` (labels,
trial Reels), `fma/youtube.py` (Shorts copy), `fma/cover.py` (thumbnails), `fma/duo_desk.py` (banter).

## 1. Where we are (data/stats, 8 Nov 2026)

| | Number |
|---|---|
| Followers | 2 (account started 31 Oct) |
| Reels posted | 23 posts in 9 days |
| Reach per Reel | plain Reels (4-5 Nov): 3-18; duo Reels (6 Nov on): 48-129 |
| Average watch | 5.5-11 s of a ~40 s Reel (median 6.2 s) |
| Sends, saves, comments | 0, 0, 0 |
| Website | 3-7 visitors a day, mostly direct and LinkedIn |

The duo format multiplied reach about tenfold in two days. Instagram is willing to show the Reels: **it shows each
one to about a hundred people, and almost all of them leave by second 8.** That is the problem to fix first.

## 2. What decides reach (checked 8 Nov 2026)

- **Watch time, sends per reach, likes per reach** are Instagram's top three ranking signals; sends matter most for
  reaching people who don't follow you. *Adam Mosseri, Jan 2025, via Social Media Today (secondary).*
- **Original content wins; aggregators lose recommendations.** *Instagram ranking page (official) and April 2024
  change (secondary).* Our animation, script and fact-check are original: keep it that way, never repost clips.
- **AI label:** realistic AI audio needs Meta's AI-info label (official Help Center). We now self-label every Reel
  (`is_ai_generated`, official API since 22 Jun 2026). No evidence that a label reduces reach.
- **Hashtags:** five at most since Dec 2025 (secondary; the API page still says 30). They help Instagram file the
  Reel, not reach more people.
- **Skip rate** (people gone in the first 3 s) is now in the API (`reels_skip_rate`, official, Dec 2025). We collect it.
- **Trial Reels** (shown to non-followers first) can be posted through the API (`trial_params`, official, Dec 2025).
  Eligibility for new accounts is unclear.
- **YouTube Shorts:** since 2 Nov 2026, uploads from personal API projects are public (official). Same video, a
  second audience, free.
- **Not worth it now:** TikTok (unaudited apps post private only), LinkedIn video API (registered companies only),
  X API (paid: about $0.015 a post, $0.20 with a link).
- **No official growth benchmarks exist for accounts under 1,000 followers.** Our targets below are ours.

## 3. The goal, in numbers

"Multiples" means each phase multiplies the one before. Targets, not predictions:

| By | Followers | Median reach per Reel | Average watch | Sends per 1,000 reached |
|---|---|---|---|---|
| 8 Nov (now) | 2 | 64 | 6.2 s | 0 |
| 6 Dec 2026 | 100 | 500 | 15 s | 5 |
| 7 Feb 2027 | 1,000 | 2,000 | 18 s | 10 |

The scoreboard (`data/growth/scoreboard.md`, rebuilt every evening) checks the weekly gates: skip rate at most 45%,
15 s average watch, 5 sends and 30 likes per 1,000 reached, 15 new followers a week. The first gate not met is the
week's bottleneck, and the week's one change goes there.

## 4. The plan, in three phases

**Phase 1, 9 Nov to 6 Dec: make people stay.** (Bottleneck now: watch time.)
- Shipped 8 Nov: designed covers with a catchy headline; banter instead of one-liners; rotating closings.
- To test (each needs Pavan's yes on a sample first): a cold open, the first 2 seconds show the hook in big type
  and the guest's reaction, before the story starts; scripts trimmed to 30-35 s.
- Trial Reels on one slot once the account is eligible (`growth.trial_reels`, off now).

**Phase 2, 7 Dec to 3 Jan: make people send it.**
- Shipped 8 Nov: every caption asks for a send ("Send this to your group chat's AI person"); five topic hashtags.
- To test with Pavan's yes: the spoken outro asks for a send instead of a comment; Sunday "Week in AI: 5 numbers"
  carousel with music (carousels earn saves and sends, and can show in the Reels tab).
- Story choice: the scoreboard's best Reels feed the editor's weights (`fma/learn.py` already does this weekly).

**Phase 3, from 4 Jan: more doors in.**
- YouTube Shorts copy of every Reel (built; waits for Pavan's 15-minute setup).
- Threads video posts (same Meta family; needs a Threads app token).
- Profile and pinned Reels that say in one line why to follow.
- Collab posts with other AI creators (API supports up to three collaborators).

## 4b. The content engine: every Reel, end to end (9 Nov 2026, `fma/audience.py`)

| Step | What it means | Where it lives |
|---|---|---|
| Pain | The viewer worry the story speaks to: job, skills, tools, money, privacy, trust, keeping up, power, safety | `PAINS`; the Reel desk tags every card; no pain = relatable 0 |
| Hook | One of six formulas (stakes, surprise, number, conflict, you, gap), on the cover and in the first 4 seconds | `HOOK_TYPES`; hook checker sends back filler openers; duo line 1 at most 12 words |
| Value | Three fact-checked points: what happened, the twist, who it affects | Reel desk + both fact-check layers |
| Solve | What it means for you, or one thing to do | the take (`take_kind` do/read) |
| Visual | Cover headline with lit words, the cast, the number panel | `fma/cover.py`, Remotion |
| CTA | One action by goal: save a how-to, send to a colleague (job, skills, tools), send to a friend | `cta_for`; the comment question stays |
| Learn | Which pains and hook formulas hold viewers, by watch time and reach | `fma/learn.py` features `pain`, `hook type` |
| Market | The week's most-watched AI Shorts in the US and India, as hook ideas only | `fma/market.py` (needs `YOUTUBE_API_KEY`) |

## 4c. Instagram playbook

- **Cadence:** 3 to 5 duo Reels a day at fixed times (09:00, 13:00, 16:00, 19:00 IST). Test a 21:30 IST slot (11:00
  US Eastern) for two weeks: the US audience pays most for ads and sponsors.
- **Formats:** the daily duo Reel; a Sunday "Week in AI: 5 numbers" carousel with music (needs Pavan's yes on a
  sample); Trial Reels on one slot once the scoreboard has a baseline.
- **Profile:** name field "Five Minute AI | Daily AI News"; bio "AI news in 40 seconds. Every claim checked."; the
  three best Reels pinned; one Highlight "How we check" later.
- **Community:** Pavan answers comments by hand in the first hour (automated replies read as bot engagement); Doubt
  may answer in character later, drafted by code, sent by a person.
- **Collabs:** invite 2-3 AI creators a month to a collab Reel (the API supports up to 3 collaborators); never
  follow-for-follow or engagement pods.
- **Captions:** hook, three points, the take, the question, one CTA, five topic hashtags (Instagram's cap).
- **Never:** reposted clips, bought followers, mass comments, misleading hooks, jokes about people's private lives.

## 4d. Earning in dollars

Hosting doesn't decide earnings; viewers do. The site is already served worldwide by GitHub Pages' CDN. Dollars
come from US and other high-paying viewers, through: YouTube's Partner Programme (Shorts path, as last published:
1,000 subscribers plus 10 million Shorts views in 90 days; check the current bar), AdSense on the website (needs a
privacy page first), sponsorships once the audience is real (a media kit from the scoreboard), and later a paid
weekly brief. Google and YouTube pay Indian creators in USD, converted at the bank.

## 5. The weekly loop

1. Every evening: stats collected, scoreboard rebuilt (code, no model).
2. Sunday: read the scoreboard, pick ONE change aimed at the bottleneck, write it here with the date.
3. Next Sunday: keep it if its gate improved over at least 10 Reels; otherwise roll it back.

## 6. Rules that don't change

- Every fact is checked by both layers; the guest and Spark's comebacks state no facts.
- No bought followers, follow-for-follow, engagement pods or automated mass comments: Instagram punishes them.
- No reposting other people's clips. No fake urgency, no clickbait the story doesn't back.
- Pavan sees a sample and says yes before any change to the look, the voices or the spoken lines.

## 7. What Pavan does (one time)

1. **YouTube** (about 15 minutes): create a channel "Five Minute AI"; Google Cloud project with "YouTube Data API
   v3"; OAuth consent screen External, publishing status **In production**; OAuth client "Desktop app"; then run
   `python -m fma.youtube_auth --client-id ... --client-secret ...` and save the three secrets it lists.
2. **Instagram profile:** name field "Five Minute AI | Daily AI News" (the name field is searchable); bio says what a
   follower gets ("AI news in 40 seconds, every claim checked"); pin the three best Reels.
3. **Decide** on the samples I send for the cold open, the spoken send line and the Sunday carousel.

## Log

- 8 Nov 2026: plan written; shipped covers, rotating closings, banter, AI label, five hashtags, send line in
  captions, skip-rate tracking, scoreboard, YouTube uploader (off until secrets), trial-Reel switch (off).
