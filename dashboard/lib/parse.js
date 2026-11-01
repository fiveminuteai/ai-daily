// Turns GitHub Actions runs, job logs and committed files into the day's pipeline view.
// Pure functions only: no network, so the tests can feed them fixtures.

export const STAGES = [
  ["collect", "Collect"], ["rank", "Rank"], ["write", "Write"], ["verify", "Verify"],
  ["gate", "Gate"], ["publish", "Publish"], ["deploy", "Deploy"], ["social", "Social"],
];

// Scheduled tries, UTC "HH:MM": 05:45 to 12:07 India time. test/api.test.mjs fails if this stops matching the cron
// lines in .github/workflows/daily.yml.
export const SCHEDULE_UTC = ["00:15", "00:47", "01:23", "01:53", "02:29", "03:07", "03:43", "04:19", "05:11", "06:37"];
const IST_MS = 330 * 60 * 1000;

/** The UTC window of one India-time calendar day. */
export function dayRange(date) {
  const start = new Date(Date.parse(`${date}T00:00:00Z`) - IST_MS);
  return [start, new Date(start.getTime() + 864e5)];
}

export function istDate(iso) {
  return new Date(Date.parse(iso) + IST_MS).toISOString().slice(0, 10);
}

export function todayIst(now = new Date()) {
  return istDate(now.toISOString());
}

/** Read what a "generate" job printed. The FMA_RUN_SUMMARY line (runs from 31 Oct 2026 on) has everything; for older
 *  runs the fetch stats, model calls and outcome are recovered from ordinary log lines. */
export function parseLog(text) {
  const out = { summary: null, fetched: null, sources: null, llmCalls: 0, tokens: 0, rejected: [], outcome: null,
                firstAt: null, fetchedAt: null };
  for (const raw of String(text || "").split(/\r?\n/)) {
    const m = raw.match(/^(\d{4}-\d\d-\d\dT[\d:.]+Z) ?(.*)$/);
    const at = m ? m[1] : null;
    const line = m ? m[2] : raw;
    if (line.startsWith("FMA_RUN_SUMMARY ")) {
      try { out.summary = JSON.parse(line.slice(16)); } catch { /* a cut-off line is ignored */ }
      continue;
    }
    const f = line.match(/fma\.pipeline: fetched (\d+) items: (\{.*\})\s*$/);
    if (f) {
      out.fetched = Number(f[1]);
      out.fetchedAt = at;
      try { out.sources = sourcesFromStats(JSON.parse(f[2].replace(/'/g, '"'))); } catch { out.sources = null; }
      continue;
    }
    const u = line.match(/fma\.llm: \S+ used (\d+) tokens/);
    if (u) { out.llmCalls += 1; out.tokens += Number(u[1]); continue; }
    const r = line.match(/attempt (\d+) rejected: (.*)$/);
    if (r) { out.rejected.push({ n: Number(r[1]), fails: r[2].split("; ") }); continue; }
    const p = line.match(/^PUBLISHED (\S+) \((\d+) words, model (.+)\)$/);
    if (p) { out.outcome = { kind: "published", slug: p[1], words: Number(p[2]), model: p[3], at }; continue; }
    const s = line.match(/^SKIPPED (\S+): (.*)$/);
    if (s) { out.outcome = { kind: "skipped", reason: s[2], at }; continue; }
    if (!out.firstAt && /\[group\]Run python -m fma daily/.test(line)) out.firstAt = at;
  }
  return out;
}

export function sourcesFromStats(stats) {
  const out = {};
  for (const [id, val] of Object.entries(stats || {})) {
    const [kind, rest = ""] = String(val).split(/:(.*)/s);
    out[id] = { status: kind, items: kind === "ok" ? Number(rest) || 0 : 0, ...(kind === "error" ? { error: rest } : {}) };
  }
  return out;
}

const secs = (a, b) => (a && b ? Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / 1000)) : null);

function step(job, name) {
  return job?.steps?.find((s) => s.name === name) || null;
}

function stepStatus(s) {
  if (!s) return "pending";
  if (s.status !== "completed") return "running";
  return { success: "ok", failure: "failed", cancelled: "failed", skipped: "skipped" }[s.conclusion] || "pending";
}

/** A short form of one daily run for the run chips and the history list. */
export function runInfo(run, jobs = [], log = null) {
  const gen = jobs.find((j) => j.name === "generate");
  const write = step(gen, "Write today's post");
  const commit = step(gen, "Commit the post");
  let outcome = log?.outcome?.kind || log?.summary?.status || null;
  let reason = log?.outcome?.reason || log?.summary?.reason || "";
  if (!outcome && commit?.conclusion === "success") outcome = "published";
  if (!outcome && commit?.conclusion === "skipped" && write?.conclusion === "success") outcome = "skipped";
  if (run.status !== "completed") outcome = "running";
  else if (run.conclusion && run.conclusion !== "success") outcome = "failed";
  const seconds = run.status === "completed" ? secs(run.run_started_at || run.created_at, run.updated_at) : null;
  // without the log, a successful run that ended within 90 s found the post already there (or was paused)
  const noop = (outcome === "skipped" && /already exists|paused/.test(reason))
    || (!log && run.conclusion === "success" && seconds != null && seconds < 90);
  return {
    id: run.id, url: run.html_url, event: run.event, status: run.status, conclusion: run.conclusion,
    created: run.created_at, started: run.run_started_at || run.created_at, updated: run.updated_at,
    seconds, outcome: outcome || "unknown", reason, noop,
    // GitHub doesn't say which cron line started a run, and delays scheduled runs by up to hours, so no guessing
    trigger: run.event === "schedule" ? "scheduled" : run.event === "workflow_dispatch" ? "manual" : run.event,
  };
}

/** The run that decided the day: the one that published, else the latest real (non-"already exists") run. */
export function mainRun(runs) {
  const real = runs.filter((r) => !r.info.noop);
  return real.find((r) => r.info.outcome === "published") || real[0] || runs[0] || null;
}

function stage(key, status, extra = {}) {
  const label = STAGES.find(([k]) => k === key)[1];
  return { key, label, status, seconds: null, numbers: {}, ...extra };
}

/**
 * Build the day view.
 * runs: [{run, jobs, log}] newest first (daily.yml runs created that India-time day)
 * deploys: deploy.yml runs that day (newest first); post, report, summary (data/runs), queue (data/social): or null
 */
export function buildDay({ date, now = new Date(), runs = [], deploys = [], post = null, report = null,
                           summary = null, queue = null, paused = false }) {
  const withInfo = runs.map((r) => ({ ...r, info: runInfo(r.run, r.jobs, r.log) }));
  const main = mainRun(withInfo);
  const log = main?.log || null;
  const sum = summary || log?.summary || null;
  const st = sum?.stages || {};
  const attempts = sum?.attempts || (log?.rejected || []).map((r) => ({ n: r.n, fails: r.fails }));
  const last = attempts[attempts.length - 1] || null;
  const published = Boolean(post) || main?.info.outcome === "published";
  const reason = main?.info.reason || sum?.reason || "";
  const gen = main?.jobs?.find((j) => j.name === "generate");
  const writeStep = step(gen, "Write today's post");
  const running = main?.info.outcome === "running";
  const failedRun = main && ["failed", "skipped"].includes(main.info.outcome) && !published;
  const nothing = !main && !post;
  // stages after a hard stop are "skipped", stages not reached yet in a running/future run are "pending"
  const after = (ok) => (ok ? "ok" : running || nothing ? "pending" : "skipped");

  const stages = [];

  // collect
  const sources = st.collect?.sources || log?.sources || null;
  const fetched = st.collect?.items ?? log?.fetched ?? null;
  const srcList = sources ? Object.entries(sources).map(([id, s]) => ({ id, ...s })) : [];
  stages.push(stage("collect", st.collect?.status || (fetched != null ? "ok" : after(false)), {
    seconds: st.collect?.seconds ?? secs(log?.firstAt || writeStep?.started_at, log?.fetchedAt),
    numbers: fetched != null ? {
      items: fetched, sources: srcList.length,
      failing: srcList.filter((s) => s.status === "error").length,
      empty: srcList.filter((s) => s.status === "ok" && !s.items).length,
    } : {},
    sources: srcList.sort((a, b) => b.items - a.items),
  }));

  // rank
  const lineup = st.rank?.lineup || (post ? post.sections.map((s) => ({ title: s.title, category: s.category, picked: true })) : []);
  const early = /new stories found/.test(reason);
  stages.push(stage("rank", st.rank?.status || (early ? "failed" : lineup.length || fetched != null ? "ok" : after(false)), {
    seconds: st.rank?.seconds ?? null,
    numbers: st.rank ? { stories: st.rank.stories, picked: lineup.length } : lineup.length ? { picked: lineup.length } : {},
    top: st.rank?.top || [], lineup, editor: st.rank?.editor ?? null,
    note: st.rank ? "" : lineup.length ? "Ranking scores are recorded from 31 Oct 2026 on; this shows the post's sections." : "",
  }));

  // write
  const model = post?.model || log?.outcome?.model || last?.model || "";
  const wroteSecs = attempts.reduce((a, x) => a + (x.seconds?.write || 0), 0);
  const writeOk = published || attempts.some((a) => a.seconds?.write != null);
  stages.push(stage("write", attempts.some((a) => (a.fails || []).some((f) => f.startsWith("attempt crashed"))) && !published
    ? "failed" : writeOk ? "ok" : early ? "skipped" : after(false), {
    seconds: wroteSecs || null,
    numbers: { attempts: attempts.length || (published ? 1 : 0), ...(log?.llmCalls ? { calls: log.llmCalls, tokens: log.tokens } : {}),
               ...(post ? { words: post.word_count } : {}) },
    model,
  }));

  // verify: layer 1 (rules against source text) and layer 2 (model re-reads the sources)
  const v = post?.verification || null;
  const l1 = last?.layer1 && Object.keys(last.layer1).length ? last.layer1 : null;
  const l2 = last?.layer2 && Object.keys(last.layer2).length ? last.layer2 : v && v.layer2_done ? pick(v) : null;
  const removed = (report?.entries || []).filter((e) => e.status === "dropped").slice(0, 8)
    .map((e) => ({ text: e.text, where: e.where, problems: e.problems }));
  stages.push(stage("verify", l2 || l1 || v ? "ok" : writeOk ? (running ? "running" : "failed") : after(false), {
    seconds: attempts.reduce((a, x) => a + (x.seconds?.layer1 || 0) + (x.seconds?.layer2 || 0), 0) || null,
    numbers: l2 ? { checked: l2.checked, confirmed: l2.ok, repaired: l2.repaired, removed: l2.dropped, unused: v?.unused ?? last?.unused ?? 0 } : {},
    layer1: l1, layer2: l2, layer1Done: v?.layer1_done ?? Boolean(l1), layer2Done: v?.layer2_done ?? Boolean(last?.layer2 && Object.keys(last.layer2).length),
    removedSamples: removed,
  }));

  // gate
  const gateFails = attempts.flatMap((a) => (a.fails || []).map((f) => ({ attempt: a.n, text: f })));
  stages.push(stage("gate", published ? "ok" : /gate failed/.test(reason) ? "failed" : writeOk ? (running ? "running" : "failed") : after(false), {
    seconds: attempts.reduce((a, x) => a + (x.seconds?.gate || 0), 0) || null,
    numbers: { attempts: attempts.length || (published ? 1 : 0), rejected: attempts.filter((a) => (a.fails || []).length).length },
    fails: gateFails,
  }));

  // publish: the post is committed to main
  const commit = step(gen, "Commit the post");
  stages.push(stage("publish", post ? "ok" : commit ? stepStatus(commit) === "skipped" ? "skipped" : stepStatus(commit) : st.publish?.status === "failed" ? "failed" : after(false), {
    seconds: secs(commit?.started_at, commit?.completed_at),
    numbers: post ? { words: post.word_count, minutes: post.reading_minutes, sources: post.sources.length } : {},
    error: st.publish?.error || "",
  }));

  // deploy: the daily run's own deploy jobs, else a deploy.yml run that day
  const depJobs = (main?.jobs || []).filter((j) => j.name.startsWith("deploy"));
  let dep = null;
  if (depJobs.length) {
    const failed = depJobs.find((j) => j.conclusion && j.conclusion !== "success" && j.conclusion !== "skipped");
    const allSkipped = depJobs.every((j) => j.conclusion === "skipped");
    dep = { status: depJobs.some((j) => j.status !== "completed") ? "running" : failed ? "failed" : allSkipped ? "skipped" : "ok",
            started: depJobs[0].started_at, finished: depJobs[depJobs.length - 1].completed_at,
            url: depJobs[depJobs.length - 1].html_url, via: "daily run" };
  } else if (post && deploys.some((d) => d.created_at >= (post.generated_at || "").replace("+00:00", "Z"))) {
    // a deploy.yml run started after the post was written (a push or a manual retry)
    const d = deploys.find((x) => x.created_at >= post.generated_at.replace("+00:00", "Z"));
    dep = { status: d.status !== "completed" ? "running" : d.conclusion === "success" ? "ok" : "failed",
            started: d.run_started_at || d.created_at, finished: d.updated_at, url: d.html_url, via: d.event };
  }
  stages.push(stage("deploy", dep ? dep.status : post ? "pending" : after(false), {
    seconds: dep ? secs(dep.started, dep.finished) : null, url: dep?.url || "", via: dep?.via || "",
    numbers: { deploys: deploys.length },
  }));

  // social
  // what can really post: the story Reels, or the carousel on days before Reels existed (X is off, LinkedIn by hand)
  const all = queue?.items || [];
  const items = all.filter((i) => i.platform === "instagram_reel" || (i.platform === "instagram" && !all.some((r) => r.platform === "instagram_reel")));
  const count = (s) => items.filter((i) => i.status === s).length;
  stages.push(stage("social", !items.length ? (post ? "pending" : after(false)) :
    count("pending") ? "pending" : count("failed") ? "failed" : "ok", {
    numbers: items.length ? { pending: count("pending"), approved: count("approved") + count("posted"), skipped: count("skipped") } : {},
  }));

  for (const s of stages) if (paused && nothing && s.status === "pending") s.status = "skipped";

  let verdict;
  if (published) verdict = stages.some((s) => s.status === "failed") ? "warn" : "ok";
  else if (running) verdict = "running";
  else if (failedRun) verdict = /already exists/.test(reason) ? "ok" : "bad";
  else verdict = paused ? "paused" : "waiting";

  return {
    date, verdict, reason, paused,
    nextRun: published ? null : nextSchedule(date, now),
    triesLeft: published ? 0 : schedulesLeft(date, now),
    lastTry: scheduleTimes(date).at(-1).toISOString(),
    post: post ? { headline: post.headline, dek: post.dek, slug: post.slug, model: post.model, tags: post.tags,
                   generated_at: post.generated_at, words: post.word_count, minutes: post.reading_minutes } : null,
    runs: withInfo.map((r) => r.info),
    mainRunId: main?.info.id || null,
    totalSeconds: sum?.seconds ?? main?.info.seconds ?? null,
    hasSummary: Boolean(sum),
    stages,
  };
}

function pick(v) {
  return { checked: v.checked, ok: v.ok, repaired: v.repaired, dropped: v.dropped };
}

/** The day's scheduled tries as UTC instants. The UTC times all fall on the India-time date's own UTC calendar day
 *  (the India day starts at 18:30 UTC the day before, and every try is before 18:30 UTC). */
export function scheduleTimes(date) {
  const [start] = dayRange(date);
  return SCHEDULE_UTC.map((hm) => {
    const [h, m] = hm.split(":").map(Number);
    return new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate() + 1, h, m));
  });
}

/** The next scheduled try on that India-time day, or null if they have all passed. */
export function nextSchedule(date, now = new Date()) {
  return scheduleTimes(date).find((t) => t > now)?.toISOString() || null;
}

export function schedulesLeft(date, now = new Date()) {
  return scheduleTimes(date).filter((t) => t > now).length;
}

/** Group daily runs and posts into India-time days for the history timeline (newest first). */
export function buildHistory({ runs = [], deploys = [], posts = [], history = [], meta = {}, now = new Date(), days = 21 }) {
  const byDay = new Map();
  const slugOf = Object.fromEntries(history.map((h) => [h.date, h.slug]));
  const today = todayIst(now);
  const start = Date.parse(`${today}T00:00:00Z`);
  for (let i = 0; i < days; i++) {
    const d = new Date(start - i * 864e5).toISOString().slice(0, 10);
    byDay.set(d, { date: d, runs: [], deploys: [], post: posts.includes(d), slug: slugOf[d] || "" });
  }
  for (const r of runs) {
    const d = istDate(r.created_at), info = runInfo(r), at = meta[d]?.generated_at?.replace("+00:00", "Z");
    // the post's generated_at falls inside the run that published it; other real runs that day did not publish
    if (at && info.status === "completed") {
      if (at >= (r.run_started_at || r.created_at) && at <= r.updated_at) Object.assign(info, { outcome: "published", noop: false });
      else if (!info.noop && r.updated_at > at) info.noop = true;
      else if (!info.noop && info.outcome === "unknown") info.outcome = "skipped";
    }
    byDay.get(d)?.runs.push(info);
  }
  for (const r of deploys) {
    byDay.get(istDate(r.created_at))?.deploys.push({
      id: r.id, url: r.html_url, event: r.event, created: r.created_at, status: r.status, conclusion: r.conclusion,
      title: r.display_title || r.head_commit?.message?.split("\n")[0] || "" });
  }
  const firstPost = posts.length ? [...posts].sort()[0] : today;
  return [...byDay.values()].map((d) => {
    if (d.date < firstPost && !d.runs.length) return { ...d, title: "", status: "before" };
    const failed = d.runs.some((r) => r.outcome === "failed") || d.deploys.some((x) => x.conclusion && x.conclusion !== "success");
    return { ...d, title: meta[d.date]?.headline || (d.slug ? d.slug.slice(11).replace(/-/g, " ") : ""),
             status: d.post ? (failed ? "warn" : "ok") : d.date === today ? "waiting" : d.runs.length ? "bad" : "missed" };
  });
}
