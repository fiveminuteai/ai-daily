# Instagram Reel learnings (Five Minute AI, 13-14 Nov 2026)

Written for every Instagram session to reuse. Each item says where it came from. "Our data" = @fiveminute_ai's own
numbers (9 Reels, 7 followers, about 100 reach per Reel); one account at that size proves nothing, so these are
leads to test, not facts about the platform.

## 1. What our numbers say (our data, scoreboard of 12 Nov)
- About 60% of viewers leave in the first 3 s; 5.4 s watched on average of about 38 s; zero sends, saves, comments.
- The only Reel that held people (12.3 s, 34.5% left early) named a product people know and a plain benefit
  ("Claude Fable 5.2 is out, and cheaper than before"). The worst opened with a developer API headline (76% left).
- Duo Reels reach roughly 10x plain ones (48-129 vs 3-18, 8 Nov). The learning loop's first solid finding: plain
  Reels do clearly worse (17 plain, effect -0.69).

## 2. Diagnosis framework (from a creator's screenshots Pavan shared, 13 Nov; one creator's advice, not measured)
Read the retention graph first, then fix the matching part:
| Graph shows | Problem | Fix |
|---|---|---|
| Cliff in the first seconds | Hook | Wide appeal, a specific emotion, a curiosity gap, authority |
| Steady slide | Value / attention | Shorter, get to the point faster, rehook mid-video |
| Good retention, few views | Packaging / idea | Make the idea relevant to a wide group; lead with the why |
| Many views, little engagement | Connection / positioning | Speak to a specific fear or wish; opinion; proof |
For us (60% gone in 3 s, about 100 reach) the problem is Hook and Idea, not Connection or Positioning.

## 3. The hook-loop structure (second screenshot, a 30 s explainer; our adaptation is pilot D)
Hook -> Question/Delay #1 -> Rehook -> Question/Delay #2 -> Answer, with the answer in the last seconds.
Adapted to a fact-checked news duo, keeping every fact checked and the answer delivered (no empty tease):
1. Spark: the claim, 8 words or fewer, shown as text from frame 1.
2. Doubt asks the obvious question; Spark delays in one line that states no fact ("Not yet. Stay for the reason.").
3. Rehook: a second true detail from the source.
4. Doubt reacts; Spark delays again ("The real rule is stranger.").
5. The answer: the most surprising true fact, last.

## 4. Craft rules that worked or were verified this session
- **Hook as text from the first frame** (muted viewers): big, 6 words or fewer, inside the safe zone, gone after line 1.
- **Safe zone, 1080x1920:** keep everything between x 80-1000 and y 230-1440 (the interface covers the rest: caption
  and buttons at the bottom, the action rail on the right). Our end card broke this: the slogan bar ran past both screen
  edges, the sticker sat over the characters and off the right edge. Check every card with a green box overlay on a
  frame pulled with ffmpeg; never judge by eye alone. Fixed 14 Nov in `reels/src/DuoReel.tsx`.
- **Hook strength lever:** a Reel about "your AI assistant can't book flights" beat "OpenAI adds business profiles"
  on the skill's hook scorer (78 vs 35). Name what changes for the viewer, not what the company shipped.
- **Attribute claims you cannot verify yourself:** the cost claim came from Google's own blog, so Spark says "Google
  says". The code checker accepted either wording; the story did not.
- **Numbers must be spoken as people say them** (Kokoro read "3,378,378" and "$70-$78" wrongly until a pronunciation
  map was added; transcribe every Reel once and read the numbers).

## 5. The Instagram agent skill (github.com/Jakeschincariol/instagram-agent-skill, MIT, vetted 9 and 14 Nov)
Scanned before reading: Windows Defender clean, no hidden characters, no network or shell calls in its 6 Python
scripts, no hooks or MCP servers in its plugin manifest. Useful and safe to run: `ig-reel/hookscore.py` (rank hook
lines) and `ig-reel/beats.py` (timed beat sheet; flags a hook over 3 s, a beat over 4 s, no loop). Its own README says
the score separates real hooks from bad ones (AUC 0.83) but barely separates a creator's hits from their misses
(0.56): use it to reject weak hooks, never to pick a winner. The scanner we used is `docs/pilots/skillscan.py`
(static, runs nothing from the folder): reuse it for any skill before reading it.

## 6. How we test (so no one fools themselves)
- One test Reel a day (the D structure) beside the normal three, for about two weeks; the other three pilot styles
  (A wide-appeal story, B reworked hook, C myth-or-fact) are parked in `docs/pilots/pilot_scripts.py`.
- Judge by first-3-seconds drop-off and average watch time against our own running median. The rule of thumb for
  proving a difference (n = 16 p(1-p) / difference^2 per group) needs hundreds of viewers per group, which we don't have
  yet: read trends, don't declare winners. The learning loop (`python -m fma.learn`) only calls something real when 8+
  Reels sit on each side, the effect is over twice its error, and the newest third of Reels agrees.
- Nothing that posts depends on a person writing it by hand once the test is over: today's D script is hand-written
  (a test); automating it is a pipeline step (Pavan's rule of 12 Nov: no Claude dependency).
