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

## Code red, 2 Nov: the newsroom rebuilt

Pavan: the Reels "aren't interesting at all". Diagnosis from the run logs: the blog took a hobbyist's AI pocket
watch (editor interest 4/10) over "chatbots are leading hikers astray" (5) because two outlets covered it; the editor
rated a GitHub repo 6; the blog writer wrote the Reel lines as headlines with the story removed; and every day got
three Reels, however weak the third.

| Role | Brief | Change |
|---|---|---|
| Editor (`editor.py`) | Fifteen years on a consumer tech desk; anchored 0-10 scale (repos and model cards 0-2, people harmed or a giant in trouble 9-10) | Weight 1.5 -> 3; stories under 5 only fill gaps (`pick_lineup`) |
| Producer (`reel_desk.py`) | Senior Instagram news producer; rubric (stakes 3, surprise 2, names 2, number 1, relatable 2); writes hook (who + stakes, a full sentence), three beats, take, question | New, one call per story; over-long lines sent back once; facts only from the section text |
| Editor-in-chief (`reel_desk.py`) | Compares the day's scripts side by side | New; final score = mean of rubric and chief |
| Quality bar | Only stories at 6/10 or more become Reels; a weak day posts its single best | `card_stories` |
| Fact-check | Unchanged: both layers check every Reel line | Question openers no longer flagged as names |
| Log | Every story's scores, the chief's reason and the hook | `reel_desk` in each run's attempt record |
| The AI race (3 Nov) | Stories about the giants (OpenAI, Anthropic, Google Gemini, Meta, xAI, Microsoft, Apple, Nvidia, Amazon) and the challengers that take them on rank first; our own top pages (Gemini 4, Mistral, OpenAI) agreed | `players` + `player_boost` in sources.yaml (rivalry 1.2, giant 1.0, challenger 0.6; repos excluded); editor scale rebuilt around the race; `learn.py` tracks "player" so the lean is checked against our numbers |

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
