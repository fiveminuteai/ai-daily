// The dashboard's whole server side: one handler shared by the Cloudflare Pages Function and the local dev server.
//
// Environment (Worker secrets / variables, or process env locally):
//   GITHUB_TOKEN        fine-grained token for fiveminuteai/ai-daily only (Actions + Contents read/write). Secret.
//   REPO                owner/name, default fiveminuteai/ai-daily
//   DRY_RUN             anything but "0"/"false" means every write is only described, never sent (default: dry run)
//   ACCESS_TEAM_DOMAIN  e.g. fiveminuteai.cloudflareaccess.com   } every request must carry a valid Cloudflare
//   ACCESS_AUD          the Access application's audience tag    } Access token for one of ALLOWED_EMAILS
//   ALLOWED_EMAILS      comma-separated
//   LOCAL_DEV           "1" only in dev-server.mjs (listens on 127.0.0.1): skips the Access check

import { GitHub, GitHubError, b64decode } from "./github.js";
import { buildDay, buildHistory, dayRange, parseLog, todayIst } from "./parse.js";

const WORKFLOWS = { daily: "daily.yml", deploy: "deploy.yml", social: "publish-social.yml" };
const DATE_RE = /^\d{4}-\d\d-\d\d$/;
const ITEM_RE = /^\d{4}-\d\d-\d\d-(instagram|x|linkedin)$/;

// desktop: {handle(key, body, query)} from desktop/local-api.mjs: mail, accounts, roadmap, credentials. Only the
// desktop app passes it, and only with LOCAL_DEV (127.0.0.1); on Cloudflare every /api/local/* route is a 404.
export async function handle(request, env = {}, { fetchImpl, local, desktop } = {}) {
  const url = new URL(request.url);
  const route = url.pathname.replace(/^\/api\/?/, "").replace(/\/$/, "");
  try {
    const who = await authorize(request, env, fetchImpl);
    if (!who) return json({ error: "forbidden", message: "Sign in through Cloudflare Access with an allowed email." }, 403);
    if (request.method !== "GET") {
      const bad = checkWrite(request, url);
      if (bad) return json({ error: "bad_request", message: bad }, 400);
    }
    const dryRun = !["0", "false"].includes(String(env.DRY_RUN ?? "").toLowerCase());
    const repo = env.REPO || "fiveminuteai/ai-daily";
    const gh = env.GITHUB_TOKEN ? new GitHub({ token: env.GITHUB_TOKEN, repo, fetchImpl, local: env.LOCAL_DEV === "1" ? local : null }) : null;
    const isDesktop = Boolean(desktop) && env.LOCAL_DEV === "1";
    const ctx = { env, gh, dryRun, repo, who, url, isDesktop, fetchImpl };

    const key = `${request.method} ${route}`;
    if (key === "GET status") return json(await status(ctx));
    if (route.startsWith("local/")) {
      if (!isDesktop) return json({ error: "not_found" }, 404);
      return json(await desktop.handle(key.replace(" local/", " "), request.method === "GET" ? null : await body(request),
        url.searchParams));
    }
    if (key === "GET media") return json(await media(ctx, url.searchParams.get("date")));
    if (request.method === "GET" && !gh) {
      return json({ error: "no_token", message: "No GITHUB_TOKEN is set, so there is no GitHub data to show. "
        + "Locally: set the GITHUB_TOKEN environment variable before starting the dev server. "
        + "On Cloudflare: add it as an encrypted Worker secret (see dashboard/README.md)." }, 503);
    }
    if (key === "GET day") return json(await day(ctx, url.searchParams.get("date")));
    if (key === "GET history") return json(await history(ctx));
    if (key === "GET social") return json(await social(ctx));
    if (key === "GET stats") return json(await stats(ctx));
    if (key === "POST control/pause") return json(await pause(ctx, await body(request)));
    if (key === "POST control/rerun") return json(await dispatch(ctx, WORKFLOWS.daily, {}, "Rerun today's daily post"));
    if (key === "POST control/redeploy") return json(await dispatch(ctx, WORKFLOWS.deploy, {}, "Retry the site deploy"));
    if (key === "POST social/action") return json(await socialAction(ctx, await body(request)));
    if (key === "POST stats/manual") return json(await manualStats(ctx, await body(request)));
    if (key === "POST social/schedule") return json(await schedule(ctx, await body(request)));
    return json({ error: "not_found" }, 404);
  } catch (err) {
    if (err instanceof GitHubError) return json({ error: "github", message: err.message }, err.status === 401 ? 502 : 502);
    if (err instanceof BadInput || err?.badInput) return json({ error: "bad_request", message: err.message }, 400);
    if (err?.userMessage) return json({ error: err.code || "failed", message: err.userMessage }, err.status || 502);
    return json({ error: "internal", message: "Something went wrong in the dashboard API." }, 500);
  }
}

class BadInput extends Error {}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store",
               "X-Content-Type-Options": "nosniff" },
  });
}

async function body(request) {
  try { return await request.json(); } catch { throw new BadInput("Body must be JSON."); }
}

/** Writes must come from the dashboard page itself: JSON with our header (forces a CORS preflight) and our origin. */
function checkWrite(request, url) {
  if (request.headers.get("x-fma-dashboard") !== "1") return "missing dashboard header";
  if (!(request.headers.get("content-type") || "").startsWith("application/json")) return "body must be JSON";
  const origin = request.headers.get("origin");
  if (origin && origin !== url.origin) return "cross-origin write refused";
  return "";
}

// ---------- Cloudflare Access ----------

let certCache = { at: 0, team: "", keys: [] };

async function authorize(request, env, fetchImpl) {
  if (env.LOCAL_DEV === "1") return { email: "local" };
  const team = env.ACCESS_TEAM_DOMAIN, aud = env.ACCESS_AUD;
  const allowed = String(env.ALLOWED_EMAILS || "").split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  if (!team || !aud || !allowed.length) return null;          // not configured: refuse everything
  const token = request.headers.get("cf-access-jwt-assertion")
    || (request.headers.get("cookie") || "").match(/(?:^|;\s*)CF_Authorization=([^;]+)/)?.[1];
  if (!token) return null;
  const claims = await verifyJwt(token, { team, aud, fetchImpl });
  const email = String(claims?.email || "").toLowerCase();
  return claims && allowed.includes(email) ? { email } : null;
}

const b64url = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(s.length / 4) * 4, "=")),
  (c) => c.charCodeAt(0));

export async function verifyJwt(token, { team, aud, fetchImpl = globalThis.fetch.bind(globalThis), now = Date.now() }) {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  let header, claims;
  try {
    header = JSON.parse(new TextDecoder().decode(b64url(parts[0])));
    claims = JSON.parse(new TextDecoder().decode(b64url(parts[1])));
  } catch { return null; }
  if (header.alg !== "RS256") return null;
  if (certCache.team !== team || now - certCache.at > 3600e3 || !certCache.keys.some((k) => k.kid === header.kid)) {
    const res = await fetchImpl(`https://${team}/cdn-cgi/access/certs`);
    if (!res.ok) return null;
    certCache = { at: now, team, keys: (await res.json()).keys || [] };
  }
  const jwk = certCache.keys.find((k) => k.kid === header.kid);
  if (!jwk) return null;
  const key = await crypto.subtle.importKey("jwk", { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: "RS256", ext: true },
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64url(parts[2]),
    new TextEncoder().encode(`${parts[0]}.${parts[1]}`));
  if (!ok) return null;
  const auds = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (!auds.includes(aud) || claims.iss !== `https://${team}` || !(claims.exp * 1000 > now)) return null;
  return claims;
}

export function _resetCertCache() { certCache = { at: 0, team: "", keys: [] }; }

// ---------- read views ----------

async function readPaused(gh) {
  const yaml = await gh.file("config/site.yaml");
  return /^paused:\s*true\b/m.test(yaml || "");
}

async function status({ gh, dryRun, repo, who, isDesktop }) {
  const base = { repo, dryRun, user: who.email, today: todayIst(), configured: Boolean(gh), localFiles: Boolean(gh?.local),
                 desktop: isDesktop };
  if (!gh) return { ...base, paused: null, message: "No GITHUB_TOKEN set." };
  return { ...base, paused: await readPaused(gh) };
}

async function day({ gh }, date) {
  date = date || todayIst();
  if (!DATE_RE.test(date)) throw new BadInput("date must be YYYY-MM-DD");
  const [start, end] = dayRange(date);
  const created = `${start.toISOString().slice(0, 19)}Z..${end.toISOString().slice(0, 19)}Z`;
  const [daily, deploys, post, report, summary, queue, paused] = await Promise.all([
    gh.runs(WORKFLOWS.daily, { created, perPage: 10 }),
    gh.runs(WORKFLOWS.deploy, { created, perPage: 10 }),
    gh.json(`content/posts/${date}.json`),
    gh.json(`content/reports/${date}.json`),
    gh.json(`data/runs/${date}.json`),
    gh.json(`data/social/${date}.json`),
    readPaused(gh),
  ]);
  const runs = await Promise.all(daily.slice(0, 6).map(async (run) => {
    const jobs = await gh.jobs(run);
    const gen = jobs.find((j) => j.name === "generate");
    const log = gen && gen.status === "completed" ? parseLog(await gh.jobLog(gen)) : null;
    return { run, jobs, log };
  }));
  return buildDay({ date, runs, deploys, post, report, summary, queue, paused });
}

async function history({ gh }) {
  const [runs, deploys, posts, hist] = await Promise.all([
    gh.runs(WORKFLOWS.daily, { perPage: 60 }),
    gh.runs(WORKFLOWS.deploy, { perPage: 40 }),
    gh.listDir("content/posts"),
    gh.json("data/history.json"),
  ]);
  const dates = posts.map((f) => f.name.replace(/\.json$/, "")).filter((n) => DATE_RE.test(n));
  // headlines and publish times for the last three weeks (at most 21 small reads)
  const recent = dates.sort().reverse().slice(0, 21);
  const meta = Object.fromEntries((await Promise.all(recent.map((d) => gh.json(`content/posts/${d}.json`))))
    .filter(Boolean).map((p) => [p.date, { headline: p.headline, generated_at: p.generated_at }]));
  return { days: buildHistory({ runs, deploys, posts: dates, history: hist || [], meta }) };
}

async function social({ gh }) {
  const files = (await gh.listDir("data/social")).map((f) => f.name).filter((n) => /^\d{4}-\d\d-\d\d\.json$/.test(n))
    .sort().reverse().slice(0, 7);
  const days = (await Promise.all(files.map((f) => gh.json(`data/social/${f}`)))).filter(Boolean);
  return { days };
}

// ---------- writes (dry run unless DRY_RUN=0) ----------

async function dispatch({ gh, dryRun, repo }, workflow, inputs, what) {
  const request = { method: "POST", path: `/repos/${repo}/actions/workflows/${workflow}/dispatches`, body: { ref: "main", inputs } };
  if (dryRun) return { dryRun: true, done: false, what, request };
  if (!gh) throw new BadInput("No GITHUB_TOKEN set.");
  await gh.dispatch(workflow, inputs);
  return { dryRun: false, done: true, what, request, note: "Started. It shows in History within a minute." };
}

export function setPaused(yaml, paused) {
  const re = /^paused:[ \t]*(true|false)\b/m;
  if (!re.test(yaml)) throw new BadInput("config/site.yaml has no 'paused:' line");
  return yaml.replace(re, `paused: ${paused ? "true" : "false"}`);
}

async function pause({ gh, dryRun, repo }, { paused }) {
  if (typeof paused !== "boolean") throw new BadInput("paused must be true or false");
  const what = paused ? "Pause daily posts" : "Resume daily posts";
  const message = `${paused ? "Pause" : "Resume"} daily posts (from the control dashboard)`;
  const request = { method: "PUT", path: `/repos/${repo}/contents/config/site.yaml`, message };
  if (!gh) {
    if (dryRun) return { dryRun: true, done: false, what, request, diff: null };
    throw new BadInput("No GITHUB_TOKEN set.");
  }
  const meta = await gh.fileMeta("config/site.yaml");
  const before = b64decode(meta.content);
  const after = setPaused(before, paused);
  const line = (t) => t.match(/^paused:.*$/m)[0];
  const diff = { from: line(before), to: line(after) };
  if (before === after) return { dryRun, done: false, what, request, diff, note: `Already ${paused ? "paused" : "running"}.` };
  if (dryRun) return { dryRun: true, done: false, what, request, diff };
  await gh.putFile("config/site.yaml", { content: after, sha: meta.sha, message });
  return { dryRun: false, done: true, what, request, diff };
}

async function socialAction(ctx, { item_id, action, text }) {
  if (!ITEM_RE.test(item_id || "")) throw new BadInput("unknown item id");
  if (!["approve", "skip"].includes(action)) throw new BadInput("action must be approve or skip");
  if (text != null && (typeof text !== "string" || text.length > 2200)) throw new BadInput("text must be under 2,200 characters");
  const inputs = { item_id, action, ...(text ? { text } : {}) };
  const what = `${action === "approve" ? "Approve" : "Skip"} ${item_id}${text ? " with edited text" : ""}`;
  return dispatch(ctx, WORKFLOWS.social, inputs, what);
}

// ---------- stats ----------

const MANUAL = "data/stats/manual.json";
const MANUAL_FIELDS = ["followers", "impressions", "engagements"];

async function stats({ gh }) {
  const dates = (await gh.listDir("data/stats")).map((f) => f.name).filter((n) => /^\d{4}-\d\d-\d\d\.json$/.test(n))
    .sort().slice(-30);
  const [days, manual] = await Promise.all([
    Promise.all(dates.map((f) => gh.json(`data/stats/${f}`))),
    gh.json(MANUAL),
  ]);
  return { days: days.filter(Boolean), manual: manual || { x: [], linkedin: [] } };
}

/** Add or replace one day's typed-in numbers for X or LinkedIn in data/stats/manual.json. */
export function mergeManual(current, { platform, date, ...nums }) {
  const out = { x: [], linkedin: [], ...(current || {}) };
  const entry = { date, ...Object.fromEntries(MANUAL_FIELDS.filter((k) => nums[k] != null).map((k) => [k, nums[k]])) };
  out[platform] = [...(out[platform] || []).filter((e) => e.date !== date), entry].sort((a, b) => a.date.localeCompare(b.date));
  return out;
}

async function manualStats({ gh, dryRun, repo }, input) {
  const { platform, date } = input || {};
  if (!["x", "linkedin"].includes(platform)) throw new BadInput("platform must be x or linkedin");
  if (!DATE_RE.test(date || "")) throw new BadInput("date must be YYYY-MM-DD");
  const nums = {};
  for (const k of MANUAL_FIELDS) {
    const v = input[k];
    if (v == null || v === "") continue;
    if (!Number.isInteger(v) || v < 0 || v > 1e9) throw new BadInput(`${k} must be a whole number`);
    nums[k] = v;
  }
  if (!Object.keys(nums).length) throw new BadInput("enter at least one number");
  const what = `Save ${platform === "x" ? "X" : "LinkedIn"} numbers for ${date}`;
  const message = `${what} (from the control dashboard)`;
  const request = { method: "PUT", path: `/repos/${repo}/contents/${MANUAL}`, message, entry: { date, ...nums } };
  if (dryRun) return { dryRun: true, done: false, what, request, entry: { date, ...nums } };
  if (!gh) throw new BadInput("No GITHUB_TOKEN set.");
  const meta = await gh.fileMeta(MANUAL);               // null when the file doesn't exist yet
  const current = meta ? JSON.parse(b64decode(meta.content)) : null;
  const next = mergeManual(current, { platform, date, ...nums });
  await gh.putFile(MANUAL, { content: `${JSON.stringify(next, null, 1)}\n`, sha: meta?.sha, message });
  return { dryRun: false, done: true, what, request, entry: { date, ...nums } };
}

// ---------- media (the blog session's carousel and Reel on the live share page) ----------

const SITE = "https://fiveminuteai.net/";

/** Slides and Reel for a day, read from its public share page (only the newest post has them). */
export function parseShareMedia(html, date) {
  const base = `${SITE}share/${date}/`;
  const slides = [...new Set([...String(html).matchAll(/src="[^"]*?\/share\/\d{4}-\d\d-\d\d\/carousel\/(\d{2}\.jpg)"/g)].map((m) => m[1]))]
    .sort().map((f) => `${base}carousel/${f}`);
  const reel = /\/share\/\d{4}-\d\d-\d\d\/reel\.mp4/.test(html) ? `${base}reel.mp4` : null;
  const card = /instagram\.png/.test(html) ? `${base}instagram.png` : null;
  return { date, slides, reel, card, page: base, zip: /carousel\.zip/.test(html) ? `${base}carousel.zip` : null };
}

async function media({ fetchImpl = globalThis.fetch.bind(globalThis) }, date) {
  if (!DATE_RE.test(date || "")) throw new BadInput("date must be YYYY-MM-DD");
  const res = await fetchImpl(`${SITE}share/${date}/`, { headers: { "User-Agent": "fiveminuteai-dashboard" } });
  if (res.status === 404) return { date, slides: [], reel: null, card: null, page: null, zip: null };
  if (!res.ok) throw Object.assign(new Error(), { userMessage: `The share page answered ${res.status}.`, status: 502 });
  return parseShareMedia(await res.text(), date);
}

// ---------- scheduling ----------

/** Plan (dry run) or write a time for one queue item; the publish-social workflow will post at that time. */
async function schedule({ gh, dryRun, repo }, { item_id, at }) {
  if (!ITEM_RE.test(item_id || "")) throw new BadInput("unknown item id");
  const when = at === null ? null : Date.parse(at || "");
  if (at !== null && (!Number.isFinite(when) || when < Date.now() - 60e3 || when > Date.now() + 14 * 864e5)) {
    throw new BadInput("pick a time in the next 14 days");
  }
  const iso = at === null ? null : new Date(when).toISOString();
  const path = `data/social/${item_id.slice(0, 10)}.json`;
  const what = iso ? `Schedule ${item_id} for ${iso}` : `Unschedule ${item_id}`;
  const request = { method: "PUT", path: `/repos/${repo}/contents/${path}`, item: item_id, scheduled_at: iso };
  if (dryRun) return { dryRun: true, done: false, what, request };
  if (!gh) throw new BadInput("No GITHUB_TOKEN set.");
  const meta = await gh.fileMeta(path);
  if (!meta) throw new BadInput(`no social queue for ${item_id.slice(0, 10)}`);
  const queue = JSON.parse(b64decode(meta.content));
  const item = queue.items.find((i) => i.id === item_id);
  if (!item) throw new BadInput(`no item ${item_id}`);
  item.scheduled_at = iso;
  await gh.putFile(path, { content: `${JSON.stringify(queue, null, 1)}
`, sha: meta.sha, message: `${what} (from the control app)` });
  return { dryRun: false, done: true, what, request };
}
