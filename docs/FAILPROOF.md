# Five Minute AI: the fail-proof plan
> Every incident, its root cause, fix and guard, plus the pre-mortem checklist: [LESSONS.md](LESSONS.md).


Written 6 Nov 2026, after the day the post was skipped twice. Goal: a true, checked post and its Reels every day,
with no single model, key or step able to stop the day.

## What went wrong on 6 Nov

1. Groq's free daily cap was used up the evening before by local tests on the same key, so the day started on
   weaker fallback models.
2. Their drafts lost too many sentences in fact-checking (560-700 words left, 880 needed) and one headline mixed two
   stories.
3. A draft that passed everything else was thrown away for one "!".
4. The 5 Nov evening Reel slot was empty: the fact-check removed the best story's card and nothing rewrote it.

## The plan, in layers

Each layer catches what the one above lets through. Status: **done** = live in the code; **to do** = next.

### 1. Never burn the day's quota (done)
- Off GitHub Actions, cloud models are off unless `FMA_ALLOW_PROD_KEYS=1` (fma/llm.py `cloud_allowed`).
- One switch for every model call: `cloud_models: false` in config/site.yaml (now off, Pavan's order of 6 Nov).
- Experiments run on the local model (Ollama) or right after the day's post.

### 2. Fix, don't fail (done)
- A stray "!" becomes a full stop; quotes stay verbatim.
- A headline that fails its check becomes the lead story's checked title.
- If every attempt fails only on length or "why it matters", a **short edition** goes out (450+ words, every fact
  checked twice, marked on the page).
- Fact-check: contractions at the start of a sentence ("They're") are no longer read as unknown names.

### 3. The writer must not depend on one free model (decided 6 Nov 2026, Pavan: no paid models)
1. **Groq and Gemini first** (the automatic daily run, free, with every safeguard above).
2. **Claude as the backup:** a scheduled Claude run on Pavan's existing plan checks at 08:15 India time; if there is
   still no post it writes and checks the day by hand, following docs/MANUAL_DAY.md (`python -m fma.manual`).
3. **The local model, prepared to take over:** not by training its weights (that needs serious hardware, and
   Anthropic's terms don't allow training other models on Claude's output) but by building everything around it:
   - the knowledge bank (`fma/bank.py`, data/bank/): every published day's checked sections, Reel cards and duo
     punchlines, used as worked examples (the duo writer already reads the newest punchlines);
   - code doing the judging: layer-2 evidence found by code (`fma/review.py`), every rule checked by code;
   - small steps a 7B model completes (the duo writer's facts / jokes / assembly);
   - voice, characters, animation and music already run locally (Kokoro, fma/spark.py, doubt.py, rex.py, music.py).
   To do: a daily shadow test (the local model writes the same day; scored against what was published), so the day
   it is good enough is measured, not guessed.

### 4. The day always has a post (done + to do)
- Done: the daily run retries, waits out outages, has backup runs until 14:23, and raises an alert after the last.
- Done: short edition instead of a skipped day.
- To do: a "manual day" command that runs today's stages for a session to write by hand (6 Nov's steps, scripted).

### 5. Reels never go silent (done + to do)
- Done: a duo Reel that fails any check, or can't be voiced, falls back to the ordinary Reel for that story.
- Done: duo scripts capped at 45 s; every Spark line through both fact-check layers.
- To do: **card rescue**. When the fact-check removes a story's Reel card, send just that story back to the Reel desk
  with the reasons, and check it again (5 Nov lost the OpenAI Reel this way).
- To do: when the queue is built after a slot has passed, move that Reel to the next free slot automatically (done by
  hand on 6 Nov: 13:00, 19:00, next day 09:00).

### 6. Small models can do the job (done)
- Every model step is small, with its rules and worked examples written out: docs/PLAYBOOK.md, generated from the code
  (`python -m fma.playbook`), and a test fails if it drifts.
- The duo script is written in three steps (facts, jokes, code assembly) that a 7B model completes.
- Code checks every answer and sends it back with the exact problems; anything still failing falls back safely.

### 7. Know before Pavan does (to do)
- A morning status at 08:00 India time: post published or not, Reels queued, which model wrote it, any fallbacks.
- An alert when a provider reports its daily cap, so the day switches before it fails.
