# YouTube Shorts plan (22 Nov 2026)

Pavan: "build a strategy to push youtube views, they are dead. work on autopilot, do research and take full ownership."

## Where we start (read from the public channel page, 22 Nov 2026, 20:30 IST)

- @five_minute_ai: **4 subscribers**. Every Instagram Reel was mirrored as a Short since 8 Nov: 4 a day.
- Of the last 40 Shorts, **17 show "No views"**: the feed never showed them to anyone. Most others have 1-12.
- Best: "Levent Alpöge says Claude helped him draft a proof of the Riemann hypothesis…" (91), "How to switch off
  Google's AI Coach" (31), "Apple splits Mac permissions…" (23), "Nvidia inflated GPU prices" (23). The winners are
  specific: a named person, a how-to, a concrete number. The losers are generic headlines ("AI CEOs can't be trusted").

## What the research says (sources in the session report; YouTube's own pages first)

1. Distribution is per viewer: "viewed vs swiped away", watch time, and responses. Near-zero views means the feed is
   hardly testing the Shorts at all, not mainly a weak hook.
2. Since 1 Oct 2026 the Shorts feed favours original content. YouTube's reused/inauthentic rules name
   "readings of … news feeds" and templated, mass-produced AI content. Invented AI characters and a fixed outro are
   fine; an original angle (commentary, analysis, storytelling) is what counts. **Four look-alike AI-voiced headline
   Shorts a day fits the pattern YouTube discounts.** This is the most likely reason views are dead.
3. The AI disclosure label alone doesn't change reach. Keep it.
4. "#Shorts" in the title isn't needed; Shorts have their own search filter since 8 Jan 2026, so titles should be
   plain search phrases, key words first. Links in Shorts descriptions aren't clickable.
5. Custom Shorts thumbnails and Shorts series are Partner Program only; playlists, a first comment and stats need
   wider API permissions than our upload-only token.

## Shipped 22 Nov 2026 (fma/youtube.py, config/site.yaml)

- **2 Shorts a day, not 4** (`growth.youtube_slots: [1, 2]`, the day's two best stories). Instagram keeps all four.
- **Titles**: the Reel's short cover line as a plain phrase, no " #Shorts".
- **Descriptions**: the story's own lines, "Every claim checked against its source: fiveminuteai.net", and topic
  hashtags; no pasted Instagram lines ("link in bio", "Send this to a friend").

## Next, in order (I do these unless marked)

1. **A real take in every Short** (the biggest lever, step 2 of the research). Spark's last line before the question
   becomes the card's checked "why it matters" line, so each Short says something no feed reading does. Needs care: a
   longer script must still fit the length cap, or the Reel loses its duo. Built and tested on a trial render first.
2. **Numbers for decisions** — *needs Pavan once*: re-run `python -m fma.youtube_auth` adding the
   `youtube.readonly` scope, so the daily stats collect views per Short (today I read them off the public page by
   hand). Same step with `youtube.force-ssl` unlocks playlists by topic and the question as our first comment.
3. **A weekly long-form recap** (5-8 min, the week's best stories with the cast), linked from the Shorts as their
   related video in Studio. Linking Shorts to long-form is the funnel creators recommend; it's also original content.
4. **Measure for 14 days** (from 23 Nov): views per Short, share of Shorts with zero views, subscribers. Baseline
   above. If the two-a-day Shorts still show "No views" after a week, the cross-post itself is the problem, and we
   test YouTube-first versions (different opening frame, no Instagram-only lines in the video).
