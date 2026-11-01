# Five Minute AI: growth roadmap

Owner: the blog session (autopilot, given by Pavan on 1 Nov 2026). Goal: the most trusted 25-second AI news on
Instagram. Accurate first, then worth watching to the end, then worth sharing.

## Where we start (1 Nov 2026)

- 6 Reels posted. Reach 42 to 55 each, 0 shares, 0 saves, 1 follower. Normal for a new account, but shares and
  saves are what Instagram rewards with reach, and we have none yet.
- 13 of the last 15 stories rest on one source. The model check removes 10 to 13 overreaching sentences a day.
- GitHub's scheduler skipped runs on 31 Oct and 1 Nov; the laptop backup now covers both the post and the Reels.

## Shipped 1 Nov

| Upgrade | Why |
|---|---|
| Reels chosen by interest, not post order (`reel_score`) | The writer rates each story 1 to 5 for a general viewer; two or more publishers, a number in the hook and a practical "do this" add points; specialist architecture stories lose one |
| Full-sentence hooks | Writer rule with a bad/good example: labels like "AI speeds up credential profiling" don't stop a scroll |
| "Your take?" ending | Each card can end on an opinion question (no facts, checked as commentary). Comments are a strong signal and give people a reason to come back |
| Watch time per Reel | Stats now record average watch time for every Reel, the number that decides reach |
| Variety | Five colour sets by topic, seeded shapes, before/after cards (from 2 Nov) |
| Auto-posting | 09:00, 13:00, 19:00 India time without approval; Skip still works |

## Next, in order

1. **Two-source rule for Reels (accuracy).** When a Reel story has one source, search the day's feeds for a second
   outlet covering it and cite both; if none, prefer another story. Today 13 of 15 stories have one source.
2. **Weekly learning report (Sundays).** From the stats: average watch time, shares and saves per Reel, grouped by
   topic, colour set, hook type (number first or statement) and posting slot. One short report in the control
   app, then adjust `reel_score` weights and posting times from data, not guesses. Needs about 2 weeks of Reels.
3. **"Week in AI: 5 numbers" Reel every Sunday.** A recurring format built from the week's checked cards. Recurring
   series build habit; this one is made entirely from facts already verified.
4. **Pinned "How we check every claim" Reel.** A one-off explainer for the profile grid, so new visitors see the
   difference at once. Needs Pavan's OK (a one-off post).
5. **Hook test.** For one Reel a day, keep two hook versions and alternate them across days; the learning report
   tells us which pattern holds viewers longer.
6. **Voiceover (maybe).** Narrated Reels often hold attention longer, but free voices need a licence check and add a
   new failure point. Only after the report shows where viewers drop off.

## Rules that don't change

- Every word on screen and in the caption has passed both fact-check layers (or is labelled commentary).
- No clickbait, no hype words, no rhetorical questions in the post. The "Your take?" question asks for an opinion
  and states no facts.
- Already-posted or approved Reels are never changed by a redeploy.
- Design changes get samples before they go live; the daily routine runs without asking.
