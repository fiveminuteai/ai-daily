# Five Minute AI

A daily, five-minute read on what happened in AI, written automatically from public sources, with every
claim linked to the source it came from. Free to read, free to run, no ads, no cookies, anonymous visit counts only (GoatCounter).

Live site: https://saipavan333.github.io/ai-daily/ · RSS: https://saipavan333.github.io/ai-daily/feed.xml

## How it works

Every morning at 05:45 India time a GitHub Actions job runs `python -m fma daily`:

1. **Collect** from the feeds in [`config/sources.yaml`](config/sources.yaml): AI lab blogs, arXiv (cs.AI, cs.CL, cs.LG),
   Hugging Face blog and daily papers, tech news RSS, the Hacker News API and new AI repos on GitHub.
2. **Rank.** Items about the same event are grouped across outlets, then scored on recency, how many outlets covered
   it and community attention (HN points, paper upvotes). Customer stories are demoted, lab releases boosted, and
   anything already covered (same URL in the last 14 days, or a near-identical story in the last 3) is skipped.
   At most two stories per section type and one per single company blog.
3. **Read.** The linked pages are fetched and their text kept. That text is all the model gets.
4. **Write.** The model returns structured JSON: headline, 3-bullet "what happened", 3-5 sections, "why it
   matters" (opinion flagged as speculation), at most one quote, an optional chart and diagram. Every sentence
   must carry `[S#]` citations.
5. **Verify** (`fma/verify.py`).
   - *Layer 1, deterministic:* every number and proper name in every sentence must appear in the text of the source
     it cites. A fact found in a sibling source of the same story is re-cited; anything else is deleted. Quotes must
     be verbatim, chart values must be printed in the chart's source, hype words are removed.
   - *Layer 2:* the model re-reads each surviving sentence next to its source and flags anything unsupported, which is
     also deleted.
   - Every decision is written to `content/reports/<date>.json` and published as the post's verification log.
6. **Gate** (`fma/gate.py`): 880-1,150 words, 3 bullets, 3-5 sections, both verification layers done, no hype words,
   every cited source listed, at least one visual, every source link resolves, every image in the built page exists,
   and not a near-duplicate of a recent post. If the gate fails, the model gets the reasons and one more try. If that
   fails, there is no post that day. Nothing is written to `content/` unless the whole post passes.
7. **Publish.** The post JSON is committed and the static site is rebuilt and deployed to GitHub Pages.

Visuals (a timeline of when the day's stories broke, bar charts of numbers from the sources, step diagrams) are
SVGs drawn by the site from verified data, in a wide and a narrow layout. No images are copied from sources.
Share cards (Open Graph PNGs) are generated with Pillow.

## Design

"Night Signal", picked by Sai Pavan from three rendered directions (screenshots in `docs/design/`).

- Dark-first deep navy with a separately built light theme (toggle in the header, remembered per browser).
- One colour per topic, used everywhere a story appears: Models `#8B9CFF`, Research `#4FD1C5`, Products
  `#FFB86B`, Tools `#C792EA`, Policy & safety `#FF7A93`, Real-world impact `#7BE495` (darker variants in light mode).
  All text colours pass WCAG AA (4.5:1) on both backgrounds.
- Headlines in Bricolage Grotesque Bold (SIL Open Font License, self-hosted from `site/static/fonts/`, licence
  alongside). Body text uses the reader's own system UI font at 17-18px with a ~68-character line.
- Signature moment: the home-page "signal field", a canvas flow field drawn in the colours of today's topics that
  bends around the cursor. It pauses off-screen and shows a still frame for reduced-motion visitors.
- Every post opens with "The 30-second version", carries a reading-time badge and a reading-progress bar, and ends with
  numbered sources and a link to its verification log.
- Search runs entirely in the browser over `search.json`; nothing typed leaves the page.

## Model choice, and what it costs

| Route | Cost | Used when |
|---|---|---|
| Google Gemini API free tier (`gemini-3.8-flash`, then `gemini-3.5-flash-lite`) via its OpenAI-compatible endpoint | Free, no card. One post uses 2-4 requests a day. | `GEMINI_API_KEY` secret is set (the default cloud route) |
| Groq free plan (`openai/gpt-oss-120b`) | Free | `GROQ_API_KEY` secret is set; tried if Gemini fails |
| OpenRouter `:free` models | Free (50 requests/day) | `OPENROUTER_API_KEY` secret is set |
| Local Ollama `qwen2.5:14b` | Free, runs on your laptop | `scripts/run_local.ps1` |

Why not GitHub Models with the built-in `GITHUB_TOKEN`? It was the first choice, but GitHub retired GitHub Models
on 30 July 2026 (see docs.github.com/en/github-models). Checked on 27 October 2026.

Terms to know about the Gemini free tier (ai.google.dev/gemini-api/terms, checked 27 October 2026): on unpaid quota,
Google may use prompts and responses to improve its products and human reviewers may read them. That is fine here
because everything sent is public news text, but don't reuse this key for anything private. Free-tier rate limits are
shown per project at aistudio.google.com/rate-limit.

## Setup (one time)

1. Get a free Gemini API key at https://aistudio.google.com/apikey (Google account, no card).
2. Store it as a repository secret, never in a file:
   ```bash
   gh secret set GEMINI_API_KEY --repo saipavan333/ai-daily
   ```
   (`gh` prompts for the value, so it never lands in your shell history.)
3. Optional backups: `GROQ_API_KEY`, `OPENROUTER_API_KEY`, set the same way.
4. Repo Settings → Pages → Source: **GitHub Actions**.

## Everyday operations

| I want to… | Do this |
|---|---|
| Run today's post now | Actions → **Daily post** → Run workflow, or `gh workflow run daily.yml` |
| Pause the blog | `gh workflow disable daily.yml` (resume: `gh workflow enable daily.yml`), or set `paused: true` in `config/site.yaml` |
| Change the time | Edit the `cron` line in `.github/workflows/daily.yml` (it's in UTC; 00:15 UTC = 05:45 IST) |
| Add or remove a source | Edit `config/sources.yaml` (an RSS URL, a name, a weight). Set `enabled: false` to turn one off |
| Change the byline or name | `config/site.yaml` |
| Write a post on the laptop | `powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1` (add `-NoPush` to look first) |
| Preview the site locally | `python -m fma build --base-url http://localhost:8000/` then `python -m http.server 8000 -d public` |
| See why a day was skipped | The Daily post run log ends with `SKIPPED <date>: <reason>` |
| Remove a post | Delete `content/posts/<date>.json` and `content/reports/<date>.json`, commit, push |

GitHub disables scheduled workflows in public repos after 60 days without repository activity. The daily commit of
each post counts as activity, so this only matters if posts stop for two months; then re-enable with
`gh workflow enable daily.yml`.

## Development

```bash
pip install -r requirements.txt
python -m pytest -q          # all fetchers and models are mocked; no network needed
python -m fma candidates     # see today's ranked stories without writing anything
```

Layout: `fma/` (pipeline), `config/` (sources and site settings), `site/` (templates and CSS), `content/` (posts
and verification reports, the source of truth), `data/history.json` (what's been covered, for de-duplication),
`tests/`.

## What the checks can't catch

The verifier confirms that numbers and names in each sentence appear in the cited source, and the model pass looks
for unsupported claims. Neither can tell whether a source is itself wrong, and correct words can still be combined
into a misleading sentence. The source links are on every post so readers can check.
