# Five Minute AI control dashboard

A private page that shows every step of the daily post and lets you approve social posts and run the controls,
from your phone or desktop. It is free to host (Cloudflare Pages + Cloudflare Access) and has no dependencies.

- **Today**: the day's pipeline as eight stages: collect, rank, write, verify (layer 1 + layer 2), gate, publish,
  deploy, social. Each shows status, time and its numbers: items per source, the stories picked and their scores,
  sentences checked / confirmed / repaired / removed, why the gate failed, the deploy result. Arrows step back
  through earlier days.
- **History**: the last 21 days as a strip and a timeline of runs and deploys, problems in red, every run linked to
  its GitHub Actions log.
- **Social**: the day's Instagram carousel, X post and LinkedIn text with Approve / Edit / Skip.
- **Stats**: followers and reach across the website, Instagram, X and LinkedIn: one tile per platform with its
  7-day change, website visitors per day, where readers came from, the most-read pages, and Instagram reach, views,
  likes, saves and shares per post.
- **Controls**: pause / resume daily posts, rerun today, retry the deploy.

**Every write is a dry run until you turn it on** (`DRY_RUN=0`). In a dry run the dashboard shows the exact request
it would send to GitHub and sends nothing.

## How it fits together

```
phone / browser ──> Cloudflare Access (only your email) ──> Pages: dashboard/public  (static page, no secrets)
                                                         └─> Pages Function /api/*  (dashboard/functions -> lib/api.js)
                                                                  │ GitHub token from a Worker secret
                                                                  ▼
                                   GitHub REST API: Actions runs, jobs, logs, workflow_dispatch; repository files
```

- The browser never sees a GitHub token. Only the Function holds it, and it only sends it to `api.github.com`.
- The Function checks the Cloudflare Access token itself (signature, audience, issuer, expiry, email), so even a
  URL that Access does not cover (a preview deployment, say) returns 403.
- Writes must be same-origin JSON with the `X-FMA-Dashboard` header. The page has a strict Content Security Policy
  (`public/_headers`).

Where the numbers come from:

| Stage | Source |
| --- | --- |
| Collect, rank, write, verify, gate | `data/runs/<date>.json` (written by `fma/pipeline.py` and committed with the post), else the `FMA_RUN_SUMMARY` line in the run's log (also on skipped days), else older log lines (fetch stats, model calls) |
| Verify (totals, removed sentences) | `content/posts/<date>.json` and `content/reports/<date>.json` |
| Publish, deploy | the daily run's jobs and steps; `deploy.yml` runs after the post |
| Social | `data/social/<date>.json`, built by `python -m fma.social_queue build` from `share_texts()` |
| History | `daily.yml` and `deploy.yml` runs, `content/posts/`, `data/history.json` |
| Stats | `data/stats/<date>.json` (`collect-stats.yml`, daily) and `data/stats/manual.json` (typed in) |

Days before 31 Oct 2026 have no run summary: their ranking shows the post's sections instead of scores.

## Host it on this laptop (before Cloudflare)

One command from the repository folder. It uses your GitHub CLI login if you have one (otherwise it asks for the
token), opens http://127.0.0.1:8788/ and keeps running until you close the window:

```powershell
powershell -ExecutionPolicy Bypass -File dashboard\start.ps1
```

Add `-Live` when you want the buttons to really commit and start workflows; without it every button is a dry run.
It only answers on this laptop (127.0.0.1): your phone can't reach it until it is on Cloudflare, and nothing on the
network can reach it either. New daily posts appear by themselves because everything is read from GitHub; files that
are only on this branch so far (the run summaries and the social queue) are read from this checkout until the branch
is merged. The GitHub CLI token can do more than the dashboard needs; for anything past a few days, make the
fine-grained token below and set `$env:GITHUB_TOKEN` before starting.

## Turn on the Stats tab

A workflow (`.github/workflows/collect-stats.yml`) runs every day at 23:30 India time, runs
`python -m fma.stats collect` and commits `data/stats/<date>.json`. A platform whose secret is missing shows as
"not connected"; one that fails shows the error (an expired token reads "HTTP 400" or "HTTP 401"). Add the secrets
under GitHub → the repository → Settings → Secrets and variables → Actions:

| Secret | Where it comes from | Cost |
| --- | --- | --- |
| `GOATCOUNTER_TOKEN` | fiveminuteai.goatcounter.com → your username (top menu) → **API** → create a key that can read statistics | free |
| `INSTAGRAM_TOKEN` | the Meta developer app (the same one Instagram auto-posting will use): Instagram → API setup with Instagram login → add the @fiveminute_ai account → **Generate token**, with `instagram_business_basic` and `instagram_business_manage_insights` | free |

The Instagram token lasts 60 days. Regenerate it in the Meta app and update the secret before then (a calendar
reminder at 50 days); the Stats tab says so when it has expired. X (paid API) and LinkedIn (page stats need Community
Management approval) have no free stats API: type their numbers into the form on the Stats tab once a week. They
are saved to `data/stats/manual.json` (in dry run they are only shown, not saved). To try it at once instead of
waiting for 23:30: Actions → Collect stats → Run workflow.

## Run it on your computer

Needs Node 18 or newer. Nothing to install.

1. Make a GitHub token (see "The GitHub token" below), or, only for a quick local look, use the GitHub CLI's.
2. In PowerShell, from the repository folder:

```powershell
cd dashboard
$s = Read-Host -AsSecureString "GitHub token"
$env:GITHUB_TOKEN = [System.Net.NetworkCredential]::new("", $s).Password
node dev-server.mjs
```

3. Open http://127.0.0.1:8788/ .

Options (environment variables): `PORT` (default 8788), `DRY_RUN=0` to make writes live, `LOCAL_FILES=..` to read
posts, reports and `data/` from this checkout instead of GitHub's `main` (useful to preview a branch that is not
pushed; runs and logs still come from GitHub). The server only listens on 127.0.0.1, so it skips the Access check.
Without `GITHUB_TOKEN` the page says so and shows how to set it.

Tests: `node --test test/*.test.mjs` (dashboard) and `python -m pytest -q` (pipeline, from the repository root).

## Put it on Cloudflare (free)

You do these steps yourself; nothing here has been set up. Free limits as of 31 Oct 2026: Pages unlimited static
requests, Functions 100,000 requests a day, Zero Trust (Access) free up to 50 users.

### 1. The GitHub token

GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token.

- Resource owner: **fiveminuteai** (if the organisation asks, approve fine-grained tokens for it under the
  organisation's Settings → Personal access tokens).
- Repository access: **Only select repositories** → `fiveminuteai/ai-daily`.
- Repository permissions: **Actions: Read and write**, **Contents: Read and write** (Metadata: read is added
  automatically). Nothing else.
- Expiry: 90 days, with a calendar reminder to rotate it.

Copy it straight into the Cloudflare secret in step 3. Do not save it in a file, a note or a chat.

### 2. The Pages project

Cloudflare dashboard → Workers & Pages → Create → Pages → **Connect to Git** → `fiveminuteai/ai-daily`.

- Project name: e.g. `fma-control` (the address becomes `fma-control.pages.dev`).
- Production branch: `main`.
- Build settings: Framework preset **None**, Build command **empty**, Build output directory **`public`**,
  Root directory **`dashboard`**.

Cloudflare picks up `dashboard/functions/` automatically. To stop a preview deployment for every branch:
Settings → Builds → Branch control → Preview branches: **None**.

### 3. Secrets and variables

Pages project → Settings → Variables and Secrets (Production):

| Name | Type | Value |
| --- | --- | --- |
| `GITHUB_TOKEN` | **Secret** | the token from step 1 |
| `REPO` | Text | `fiveminuteai/ai-daily` |
| `ALLOWED_EMAILS` | Text | your email (comma-separate to add more) |
| `ACCESS_TEAM_DOMAIN` | Text | from step 4, e.g. `fiveminuteai.cloudflareaccess.com` |
| `ACCESS_AUD` | Text | from step 4, the Application Audience (AUD) tag |
| `DRY_RUN` | Text | leave unset (dry run) until you have checked everything, then `0` |

Until `ACCESS_TEAM_DOMAIN`, `ACCESS_AUD` and `ALLOWED_EMAILS` are all set, every `/api` request is refused (403).
Redeploy after changing variables (Deployments → latest → Retry deployment).

### 4. Cloudflare Access (only you can open it)

Cloudflare dashboard → **Zero Trust** (first time: pick a team name and the Free plan; this gives
`<team>.cloudflareaccess.com`).

1. Access → Applications → Add an application → **Self-hosted**.
2. Name: `Five Minute AI control`. Session duration: 1 week (so the phone does not ask every day).
3. Public hostnames: `fma-control.pages.dev`, and a second one `*.fma-control.pages.dev` (preview deployments).
4. Policy: name `Pavan only`, Action **Allow**, Include → **Emails** → your email.
5. Login method: **One-time PIN** (the default: Cloudflare emails a code; no password to manage).
6. Save, open the application again, and copy the **Application Audience (AUD) tag** into `ACCESS_AUD`.
   The team domain goes into `ACCESS_TEAM_DOMAIN`.

Optional: Pages project → Settings → General → **Access policy** → enable for preview deployments as well.

### 5. Check it

1. Open `https://fma-control.pages.dev/` in a private window: you should get the Cloudflare Access login, then the
   dashboard after the emailed code.
2. With any other email: Access refuses it.
3. `https://fma-control.pages.dev/api/status` without signing in: refused.
4. On your phone, open it and use "Add to Home Screen".

## Going live (one switch at a time)

1. Leave `DRY_RUN` unset and use every button once: each shows the request it would send.
2. Set `DRY_RUN=0` and redeploy. From then on:
   - **Pause / Resume** commits one line in `config/site.yaml` to `main` (this also redeploys the site).
   - **Rerun today** dispatches `daily.yml` (it stops at once if today's post exists).
   - **Retry deploy** dispatches `deploy.yml`.
   - **Approve / Skip** dispatches `publish-social.yml`, which is still a dry-run stub: it prints what it would
     post and changes nothing.

## What is stubbed

- `.github/workflows/publish-social.yml` only runs `python -m fma.social_queue act ... --dry-run`. Real posting
  needs, per platform, keys in GitHub secrets and a posting step:
  - Instagram: free through the Instagram Content Publishing API (Instagram Login, Meta developer app).
  - X: no free API tier since Feb 2026, about $0.20 per post with a link. Your decision.
  - LinkedIn company page: needs Community Management API approval, so it stays manual (the Copy button).
- Approve / Skip / Edit decisions are not saved yet: the live workflow should write `status`, `edited_text` and
  `decided_at` back to `data/social/<date>.json` (the fields already exist) and the page reloads them.
- The Instagram item shows the single card from the site's share kit; it will show the carousel slides once the
  carousel generator lands.

## Files

```
dashboard/
  public/           index.html, app.js, app.css, fonts/, icon.svg, _headers (security headers on Cloudflare)
  functions/api/    [[path]].js: the Pages Function, hands every /api request to lib/api.js
  lib/api.js        routes, Cloudflare Access check, dry-run writes
  lib/github.js     GitHub REST client (the only place the token is used)
  lib/parse.js      turns runs, logs and files into the day view and history (pure, tested)
  dev-server.mjs    local server: same handler plus the static files, 127.0.0.1 only
  test/             node --test
```
