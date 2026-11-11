# Five Minute AI: market research, decisions and the closed loop (11 Nov 2026)

Written by Claude for Pavan's "full ownership" brief. Three researchers read the web on 11 Nov 2026 (read-only:
nothing downloaded, no sign-ups). Every fact below carries its source and the source's date where it shows one;
"read 11 Nov" means the page is undated. Anything that is our own inference says **judgment**. Subscriber counts are
the publishers' own claims. Tax and legal lines are general information, not advice.

## 1. What the market looks like

| Player | Size (self-stated) | Format | Money | 2025-26 |
|---|---|---|---|---|
| The Rundown AI | 2.1M; 54.8% open, 2.5% click | Daily | Ads + a $1,000/yr "University" | First outside investment, Jun 2026 |
| TLDR AI | ~1.1M; 47% open | Daily link digest | 3 ad slots | - |
| Superhuman AI | "1 million+" | Daily, "3 minutes" | Ads | - |
| The Neuron | 700K+ | Daily | Ads | Bought by TechnologyAdvice, Feb 2025 |
| Ben's Bites | ~150K (secondary) | Newsletter + Pro | Membership, ads | Founder took a job, Sep 2025 |
| Import AI / The Batch / Last Week in AI | 90K+ / n.a. / n.a. | Weekly | Optional paid; courses | - |
| Mint Tech & AI (India) | 198K+ | n.a. | Part of Mint | - |

Sources: therundown.ai/advertise-with-us; advertise.tldr.tech/audiences/ai-engineers/; superhuman.ai;
theneuron.ai/newsletter; bensbites.com/p/my-announcement; importai.substack.com/about; techaimint.substack.com
(all read 11 Nov 2026).

1. **The leaders earn from education as much as ads.** Rundown's run-rate is reported near $10M/yr with its paid
   course product close to half (newslettergrowthmemo.com, 28 Oct 2025; secondary, author's estimates).
2. **Nobody publishes ad prices.** Under 5,000 subscribers a slot sells for $50-$250, about $15-$35 CPM, and
   B2B niches reach $50-$100+ (beehiiv.com/blog/newsletter-sponsorship-cost, 9 Nov 2025).
3. **Growth came from social first, then paid.** Rundown went 0 to 150K on viral X threads, then bought readers
   at an estimated ~$2 each (emailbreakdown.beehiiv.com, 20 Dec 2024; secondary). In one operator's $6,400 test,
   referral rewards cost ~$2 per reader still there at day 90, against $6-$9 for paid recommendation networks
   (omidsaffari.com/blog/newsletter-growth-cost-per-retained-subscriber-boosts-sparkloop; one anecdote).
4. **A normal new newsletter is small.** Median 482 subscribers after month one and 8,314 after a year on
   beehiiv (beehiiv.com/blog/the-state-of-newsletters-2026, 5 Jan 2026).
5. **Opens can't be trusted; clicks are falling.** Network open rate 41.24%, click rate down from 4.74% to 3.23%
   (same beehiiv report). Apple Mail pre-loads the tracking pixel, so opens are inflated
   (litmus.com/email-client-market-share; share figure secondary).
6. **Too many emails is the top reason people unsubscribe** in every general survey found (GetApp 46%, ZeroBounce
   44%, Baymard 51%; older, not AI-specific, read as snippets). Only 1.37% of beehiiv newsletters send daily.
7. **What readers complain about: hype and sameness.** Reddit and Hacker News threads in 2026 ask for releases
   "without too much hype" and distrust promotional lists (reddit r/ArtificialInteligence, Feb 2026; hn.algolia.com
   comments 49225097, 47710317). An operator critique adds that curators rarely verify vendor benchmarks
   (dev.to/rawveg/ai-curation-is-broken-56e).
8. **India is video-first and low-trust.** 58% get news from YouTube, 56% from WhatsApp, 39% trust news
   (Reuters Institute Digital News Report 2026, India, Jun 2026; read as coverage). Rundown says 80%+ of its
   readers are in the US (therundown.ai/advertise-with-us).
9. **The gap (judgment):** none of the player pages advertises sentence-level sourcing or a corrections policy;
   the India working-professional angle and short verified video are thinly served. That is exactly what we do.

## 2. What exists technically

1. **Closest open-source analogue: Meridian** (MIT): RSS, per-article analysis, small-embedding clusters, and a
   brief that is fed the previous day's summary so it doesn't repeat itself. Its own README says brief generation
   is still manual (github.com/iliane5/meridian, read 11 Nov 2026). GPT Researcher (Apache-2.0) and STORM (MIT)
   research and cite but don't claim publication-ready output (their READMEs, read 11 Nov 2026).
2. **Small fact-check models exist and are commercially usable.** Vectara HHEM-2.1-Open (Apache-2.0, ~110M
   parameters, CPU, under 600 MB) and MiniCheck-Flan-T5-Large (MIT, 770M) score within about 4 points of the best
   27B model on the LLM-AggreFact leaderboard (huggingface.co/vectara/hallucination_evaluation_model;
   huggingface.co/lytang/MiniCheck-Flan-T5-Large; llm-aggrefact.github.io, read 11 Nov 2026). Bespoke-MiniCheck-7B
   is non-commercial (CC BY-NC).
3. **Dedup thresholds must be calibrated on your own pairs.** The bge-small model card says its similarities sit
   in about 0.6-1.0 and to pick a threshold on your data (huggingface.co/BAAI/bge-small-en-v1.5). No validated
   "same event" threshold exists for headlines (**judgment**: label our own pairs).
4. **Safe self-improvement has a known recipe** (Hamel Husain and Shreya Shankar's evals FAQ, hamel.dev,
   18 Sep 2026): binary pass/fail labels, measure the judge's true-positive and true-negative rates, keep a test
   split out of every tuning decision, rerun the evals on every change. GEPA/DSPy optimise prompts but must
   select on a separate validation set (arxiv.org/abs/2507.19457).
5. **What breaks, from an operator's post-mortem** (app.therundown.ai community post, 14 Aug 2026): an invented
   newsletter name, counts nobody measured, week-old stories run as fresh, six stories repeated across four
   editions, and a reply cut at its token limit while every dashboard stayed green. Their fixes: names and URLs
   verbatim from the input, counts injected by code, hidden per-issue counters, a dead-man switch.
6. **Feed failures are silent.** One operator flags a feed returning under 3 items or nothing newer than 24 h,
   and skips the issue when under half the sources are healthy (dev.to/alanwest, 17 Apr).

## 3. Measuring reading, and channels

1. GoatCounter (already ours, free, no cookies) takes custom JavaScript events (goatcounter.com/help/events).
   Plausible has scroll depth built in but costs $9/month; Cloudflare Web Analytics has no custom events
   (plausible.io/docs/scroll-depth; developers.cloudflare.com/web-analytics/faq/).
2. News sites average 26-30 s of engaged time; a reader who sees 2 pages is 2.75x likelier to return
   (chartbeat.com, 2025 reports).
3. Rule of thumb for trusting a difference: n = 16·p(1−p)/δ² per group (evanmiller.org). At a 40% baseline a
   10-point difference needs about 384 readers per group. **Judgment:** with our traffic, almost nothing about
   the site can be A/B tested yet; compare against our own running median instead.
4. Email at zero cost: Kit free (10,000 subscribers, API listed), beehiiv free (2,500, no send API), Amazon SES
   ($0.10 per 1,000) with listmonk, Buttondown (100 free) (their pricing pages, read 11 Nov 2026). Gmail's rules
   since Feb 2024 need SPF/DKIM, DMARC and one-click unsubscribe for bulk senders (support.google.com/a/answer/81126).
5. Telegram is the only channel with free official bot posting (core.telegram.org/bots/faq). WhatsApp Channels
   and LinkedIn newsletters have no official posting API (vendor sources).
6. Money from India: Stripe is invite-only for new Indian accounts since May 2024 (docs.stripe.com/india-exports);
   Lemon Squeezy and Gumroad pay Indian sellers out through PayPal or bank (their docs; Gumroad secondary).

## 4. Decisions: copy, beat or drop

| Finding | What we do | How we'll know it worked |
|---|---|---|
| Readers complain of hype; nobody claims sentence-level sourcing (1.7, 1.9) | **Beat.** Keep every-sentence checking as the product; it now has a measured score (eval suite: 99.1% of 349 published claims still pass, 93.7% of 126 altered ones are caught) | Eval rates stay above their bars every night; corrections stay rare |
| Operators' pipelines repeat stories and truncate silently (2.5) | **Copy the fixes.** Reply cut at the token limit is now a failure; dedupe has a labelled eval (15 of 16 pairs) | Dedupe eval; no repeated event in a lineup |
| Feeds die silently (2.6) | **Copy.** Health check fails under 50% live sources, warns on any dead one | Feed line in the daily health run |
| Self-improvement recipe (2.4) | **Copy.** Eval suite with pass bars gates every self-change; held-out newest third must agree; every change logged and reversible | learn-noise ≥ 95% (measured 97.5%), learn-signal ≥ 90% (97.0%) |
| Our own loop was teaching itself noise (found in the audit) | **Rebuild that part.** Lessons only from a confident group, re-tested every night | 0 lessons while 0 groups are confident |
| Opens are unreliable; reading matters (1.5, 3.1) | **Build.** Three cookie-free read events per post (30 s, half, end), collected nightly | `reads_7d` in data/stats once deployed |
| India is video-first (1.8) | **Keep** Reels and Shorts as the front door; email is a later retention layer, not the business | Reels send rate and site return visits |
| Small fact-check models (2.2) | **Later, behind a switch.** HHEM as a second opinion once the new machine is here; needs a ~600 MB download (Pavan's OK) | Its true/false rates on our labelled set versus layer 2 |
| Email platforms (3.4) | **Pavan's call** (an account). Recommendation: Kit free tier, weekly digest plus optional daily | Clicks and read events, not opens |
| Paid acquisition (1.3) | **Drop for now.** At 2 followers there's nothing to retain yet | - |
| Multi-day repeat rule | **Dropped after testing.** 3 of its 5 hits on our history were wrong | Re-test when a labelled multi-day set exists |

## 5. The closed loop, as built

| Step | What does it | Guard |
|---|---|---|
| Identify | Collect ~650 items from primary sources; Instagram, YouTube and site stats nightly; read events (new) | Feed health check |
| Decide | Rules first (rank, caps, dedupe, fact-check layer 1, decency), model second (editor, layer 2, comedy editor) | Eval suite: 10 suites with bars |
| Build | Post, cards, duo Reels, carousel | Gate, time budget, fallbacks |
| Measure | Health check three times a day; stats and scoreboard nightly | Red run emails the owner |
| Learn | `fma/learn.py`: bounded category lean, lessons | 8+ Reels a side, effect over 2 standard errors, newest third agrees, evals passing |
| Change itself | Only `category_bonus` (±1.0, 0.25 a week) and lessons | Logged with reason in `data/learning/changes.jsonl`; `python -m fma.learn revert` undoes the newest |
| Never learned | Fact-check, decency, posting rules, quality floor | Fixed in code |

Hardware: everything above runs on today's laptop and in GitHub Actions with no model download. The second-opinion
fact-check model and embedding-based clustering are the two pieces designed for the upgraded machine; both wait
for a config switch and Pavan's OK on the downloads.

## 6. Not verified

Ad prices and Rundown revenue (estimates only); Indian payout rules for Razorpay and Paddle; WhatsApp's official
policy on automated Channel posts; Kit's broadcast-by-API on the free plan; any Shorts retention benchmark; the
unsubscribe surveys and Reuters figures were read as snippets, not on primary pages.
