# Five Minute AI: runbook

Plain-English instructions for running the blog without any AI assistant. Nothing here needs Claude or any paid
subscription. The daily post is written and published by GitHub's servers using the Groq and Gemini free tiers, with
keys stored as GitHub secrets.

Repo: https://github.com/saipavan333/ai-daily · Site: https://fiveminuteai.net/

---

## 1. Did today's post go out?

1. Open the site. The top story should carry today's date (posts go out at **05:45 IST**; if GitHub drops that run, backups at 07:15 and 09:07 IST pick it up).
2. If it doesn't, open **Actions → Daily post** in the repo and click today's run.
   - Green, and the "Write today's post" step ends with `PUBLISHED <post name>` → it worked; the site updates a
     minute or two later.
   - It ends with `SKIPPED <date>: <reason>` → no post today, on purpose. Common reasons:
     - `paused in config/site.yaml` → someone paused it (section 2).
     - `no model provider available` → the API keys are missing (section 5).
     - `only N new stories found` → a quiet news day.
     - `gate failed after retries: …` → the draft wasn't good enough even after a retry, so nothing was published.
       If the text after it mentions `daily limit reached` or `HTTP 429`, the free AI allowance ran out; it refills
       by itself and tomorrow's run is normally fine.
   - A red run → see section 7.

If all three tries fail, the 09:07 IST run turns red with "No post for <date> after all three scheduled tries", and GitHub emails you. Read the 'Write today's post' step of the earlier runs for the reason.

A skipped day is not an emergency. The blog is built to publish nothing rather than publish something wrong.

## 2. Stop everything now

Either of these works on its own:

- **Fastest:** Actions → Daily post → `···` → **Disable workflow**. Turn it back on with **Enable workflow**.
- **In the files:** edit `config/site.yaml` on GitHub (pencil icon), change `paused: false` to `paused: true`, and
  click **Commit changes**.

The site stays online with the posts it already has.

## 3. A post says something wrong

**Quick fix from the browser (no tools needed):**

1. In the repo, open `content/posts/<date>.json` (for example `2026-10-29.json`).
2. Click the pencil icon, find the wrong sentence, and fix or delete it. Keep the `[S1]`-style markers on sentences
   you keep.
3. Click **Commit changes**. The site rebuilds itself in about two minutes.

**The proper way (logs the correction publicly on the post's verification page):** on a computer with Python:

```bash
git clone https://github.com/saipavan333/ai-daily
cd ai-daily
pip install -r requirements.txt
python -m fma correct 2026-10-29 --remove "Start of the wrong sentence" --reason "What was wrong"
git add content && git commit -m "Correction" && git push
```

Add `--suppress` when the sentence must not stay public word for word (a legal complaint, possible defamation, or someone's private details): the log then shows `[text withheld: <reason>]` and a fingerprint (sha256) of the original instead of the sentence. Note the old wording stays in git history; for a serious legal case, ask for help scrubbing it (section 9).

**To take a whole post down:** delete both `content/posts/<date>.json` and `content/reports/<date>.json`, then commit.

## 4. Change which AI writes the posts

The providers are listed in `config/site.yaml` under `providers:` and are tried top to bottom. Each one is used
only if its key is set.

- **A model was retired or renamed:** change the `model:` value on that line to the provider's new model name, which
  their docs list. That's the only edit.
- **Groq's free plan ended:** move the `gemini` line above `groq`, or add a paid Groq key (same secret name; paid
  usage is a few rupees a day for one post).
- **Use a different provider** that speaks the "OpenAI-compatible" format (most do): copy one line and change
  `name`, `base_url`, `model` and `key_env`, then add that key as a secret (section 5).

## 5. Add or replace an API key

Keys live only in GitHub secrets, never in a file or a chat message.

- **Web:** repo **Settings → Secrets and variables → Actions → New repository secret**. Names in use:
  `GROQ_API_KEY`, `GEMINI_API_KEY`, optionally `OPENROUTER_API_KEY`.
- **Command line:** `gh secret set GROQ_API_KEY --repo saipavan333/ai-daily` (it asks for the value).

Where to get them: Groq at https://console.groq.com/keys, Gemini at https://aistudio.google.com/apikey.

If a key might have leaked, delete it on the provider's site, make a new one, and update the secret.

## 6. Sources (where the news comes from)

`config/sources.yaml`, one line per source. To stop a broken or noisy source, add `enabled: false` to its line.
To add one, copy a line and change the name and RSS URL.

## 7. A red (failed) run

1. Open the run and read the last 20 lines of the failed step.
2. If it's a network or "503" error, click **Re-run jobs**. These usually pass the second time.
3. If the **Deploy site** run failed on `pytest`, a recent change broke a test. Undo that commit
   (open it on GitHub → **Revert**), or ask for help (section 9).

## 8. Things that switch themselves off

- **GitHub pauses scheduled jobs after 60 days without activity** in a repo. The daily post commit counts as
  activity, so this only happens if posts stop for two months. Fix: Actions → Daily post → **Enable workflow**.
- **The domain (once you have one)** stops working if it isn't renewed. Keep auto-renew on and check the card
  on file once a year.

## 9. Getting help from any free AI chat

Paste this, plus the error text, into ChatGPT, Gemini, Copilot or any other assistant:

> I run a static Python blog generator on GitHub Actions (repo github.com/saipavan333/ai-daily, public).
> The daily workflow is `.github/workflows/daily.yml` and runs `python -m fma daily`. Settings are in
> `config/site.yaml`. Here is the error from the run log: … What is the smallest change that fixes it?

Make one change at a time, commit it, and check the next run.

## 10. Where everything lives

| What | Where |
|---|---|
| Code, posts, settings | GitHub repo `saipavan333/ai-daily` |
| Daily schedule | `.github/workflows/daily.yml` (`cron: "15 0 * * *"` = 05:45 IST, backups 07:15 and 09:07 IST) |
| AI keys | Repo secrets (section 5) |
| Groq usage and limits | https://console.groq.com |
| Gemini usage and limits | https://aistudio.google.com |
| Visitor stats (private) | https://fiveminuteai.goatcounter.com |
| Hosting | GitHub Pages (repo Settings → Pages) |

## 11. What it costs

₹0 a month today. GitHub Actions and Pages are free for public repos, and Groq, Gemini and GoatCounter are on
free plans. A domain, once bought, is the only yearly cost. Before earning money from the blog, check the commercial-use
terms of each free plan (see the business blueprint).
