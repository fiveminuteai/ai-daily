// Five Minute AI control dashboard. Plain JavaScript, no build step, no third-party code.
// The browser only talks to /api on the same origin; the GitHub token never reaches it.

const $ = (sel, root = document) => root.querySelector(sel);
const view = $("#view");
const state = { status: null, days: new Map(), history: null, social: null, decisions: new Map(), edits: new Map(), lastResult: null };
const CATS = new Set(["models", "architecture", "research", "products", "tools", "policy", "impact"]);
const SITE = "https://fiveminuteai.net/";

// ---------- helpers ----------
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const plain = (t) => String(t || "").replace(/\[S\d+\]/g, "").replace(/‑/g, "-").replace(/\s+([.,;:!?])/g, "$1").trim();
const num = (n) => (n == null ? "–" : Number(n).toLocaleString("en-IN"));
const safeUrl = (u) => (/^https:\/\//.test(u || "") ? u : "#");
const IST = { timeZone: "Asia/Kolkata" };

function time(iso) {
  return iso ? new Date(iso).toLocaleTimeString("en-GB", { ...IST, hour: "2-digit", minute: "2-digit" }) : "";
}
function longDate(d) {
  return new Date(`${d}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
}
function shortDate(d) {
  return new Date(`${d}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}
function dur(s) {
  if (s == null) return "";
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60), r = Math.round(s % 60);
  return m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : r ? `${m}m ${r}s` : `${m}m`;
}
function shiftDate(d, n) {
  return new Date(Date.parse(`${d}T00:00:00Z`) + n * 864e5).toISOString().slice(0, 10);
}

const ICON = {
  collect: '<path d="M4 5h16l-6 7v6l-4 2v-8z"/>',
  rank: '<path d="M5 20V10M12 20V4M19 20v-7"/>',
  write: '<path d="M4 20l4-1 11-11-3-3L5 16z"/><path d="M14 6l3 3"/>',
  verify: '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
  gate: '<path d="M4 21V7l8-4 8 4v14"/><path d="M9 21v-7h6v7"/>',
  publish: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v4h16v-4"/>',
  deploy: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18"/>',
  social: '<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.2 11l7.6-4M8.2 13l7.6 4"/>',
  instagram: '<rect x="4" y="4" width="16" height="16" rx="5"/><circle cx="12" cy="12" r="3.6"/><circle cx="16.8" cy="7.2" r=".6"/>',
  x: '<path d="M5 4l14 16M19 4L5 20"/>',
  linkedin: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 10v6M8 7.5v.01M12 16v-6M12 12.5c0-1.5 1-2.5 2.3-2.5S16 11 16 12.5V16"/>',
  left: '<path d="M15 5l-7 7 7 7"/>', right: '<path d="M9 5l7 7-7 7"/>',
  warn: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17v.01"/>',
  ext: '<path d="M14 5h5v5M19 5l-8 8M10 6H5v13h13v-5"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
};
const svg = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICON[name]}</svg>`;
const STATUS_WORD = { ok: "OK", failed: "Failed", skipped: "Skipped", pending: "Pending", running: "Running",
                      waiting: "Waiting", bad: "Failed", warn: "Warning", missed: "No run", unknown: "Done",
                      approved: "Approved", posted: "Posted" };
const tag = (s) => `<span class="status-tag t-${esc(s)}">${esc(STATUS_WORD[s] || s)}</span>`;

async function api(path, opts = {}) {
  const res = await fetch(`/api/${path}`, {
    ...opts,
    headers: opts.body ? { "Content-Type": "application/json", "X-FMA-Dashboard": "1" } : {},
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) throw Object.assign(new Error(data?.message || `HTTP ${res.status}`), { status: res.status, data });
  return data;
}

function toast(html, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = html;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), 6000);
}

function confirmDialog(title, bodyHtml, okLabel = "Confirm") {
  const dlg = $("#confirm");
  $("#confirm-title").textContent = title;
  $("#confirm-body").innerHTML = bodyHtml;
  $("#confirm-ok").textContent = okLabel;
  return new Promise((resolve) => {
    const done = (v) => { dlg.close(); cleanup(); resolve(v); };
    const ok = () => done(true), cancel = () => done(false);
    const onCancel = (e) => { e.preventDefault(); done(false); };
    const cleanup = () => {
      $("#confirm-ok").removeEventListener("click", ok);
      $("#confirm-cancel").removeEventListener("click", cancel);
      dlg.removeEventListener("cancel", onCancel);
    };
    $("#confirm-ok").addEventListener("click", ok);
    $("#confirm-cancel").addEventListener("click", cancel);
    dlg.addEventListener("cancel", onCancel);
    dlg.showModal();
    $("#confirm-cancel").focus();
  });
}

function problem(err, what) {
  if (err.data?.error === "no_token") {
    return `<div class="banner">${svg("warn")}<div><h2>Connect GitHub to see ${esc(what)}</h2>
      <p>${esc(err.data.message)}</p>
      <p class="muted">Locally, in PowerShell: <code>$env:GITHUB_TOKEN = "&lt;token&gt;"; node dev-server.mjs</code>.
      Use a fine-grained token limited to <code>fiveminuteai/ai-daily</code>. Never paste it into this page or a file.</p></div></div>`;
  }
  return `<div class="banner bad">${svg("warn")}<div><h2>Could not load ${esc(what)}</h2><p>${esc(err.message)}</p>
    <p><button class="btn" data-retry>Try again</button></p></div></div>`;
}

// ---------- header ----------
function renderMode() {
  const s = state.status;
  if (!s) return;
  $("#mode").innerHTML = [
    s.paused ? `<span class="pill paused"><span class="dot d-bad"></span>Paused</span>` : "",
    s.localFiles ? `<span class="pill local" title="Committed files read from a local checkout">Local files</span>` : "",
    s.dryRun ? `<span class="pill dry" title="Writes are only described, never sent to GitHub">Dry run</span>`
             : `<span class="pill live" title="Writes are sent to GitHub">Live</span>`,
  ].join("");
}

function renderCounts() {
  const n = (state.social?.days || []).flatMap((d) => d.items).filter((i) => itemStatus(i) === "pending").length;
  for (const id of ["#social-count", "#social-count-m"]) {
    const el = $(id);
    el.hidden = !n;
    el.textContent = n;
  }
}

// ---------- today ----------
const VERDICT = {
  ok: (d) => `Published${d.post?.generated_at ? ` ${time(d.post.generated_at)} IST` : ""}`,
  warn: () => "Published, with a problem",
  bad: () => "No post",
  running: () => "Running now",
  waiting: (d) => (d.nextRun ? `Waiting for the ${time(d.nextRun)} run` : "No run yet"),
  paused: () => "Paused",
};

function stageSub(s) {
  const n = s.numbers || {};
  switch (s.key) {
    case "collect": return n.items != null ? `${num(n.items)} items` : "";
    case "rank": return n.picked ? `${n.picked} picked` : "";
    case "write": return s.seconds ? dur(s.seconds) : n.attempts ? `${n.attempts} ${n.attempts > 1 ? "tries" : "try"}` : "";
    case "verify": return n.checked ? `${n.confirmed}/${n.checked} ok` : "";
    case "gate": return s.status === "ok" ? "passed" : s.status === "failed" ? "failed" : "";
    case "publish": return n.words ? `${num(n.words)} words` : "";
    case "deploy": return s.seconds ? dur(s.seconds) : "";
    case "social": return n.pending != null ? (n.pending ? `${n.pending} to review` : "done") : "";
    default: return "";
  }
}

function rail(d) {
  let lastOk = -1;
  d.stages.forEach((s, i) => { if (s.status === "ok") lastOk = i; });
  const pad = "(var(--s4) + 100% / 16 - var(--s4) / 4)";
  const width = lastOk > 0 ? `calc((100% - 2 * ${pad}) * ${lastOk / 7})` : "0px";
  return `<nav class="rail" aria-label="Pipeline stages">
    <span class="fill" style="width:0" data-w="${esc(width)}"></span>
    ${d.stages.map((s) => `<button type="button" class="node s-${esc(s.status)}" data-jump="stage-${esc(s.key)}"
        style="background:none;border:0;cursor:pointer" aria-label="${esc(s.label)}: ${esc(STATUS_WORD[s.status] || s.status)}">
      <span class="ring">${svg(s.key)}</span><span class="lbl">${esc(s.label)}</span>
      <span class="sub">${esc(stageSub(s) || STATUS_WORD[s.status] || "")}</span></button>`).join("")}
  </nav>`;
}

function catTag(c) {
  const k = CATS.has(c) ? c : "";
  return c ? `<span class="cat" style="--c: var(--${k || "faint"})">${esc(c)}</span>` : "";
}

function card(s, cls, body) {
  return `<section class="card ${cls}" id="stage-${esc(s.key)}" aria-labelledby="h-${esc(s.key)}">
    <div class="card-head"><h3 id="h-${esc(s.key)}">${esc(s.label)}</h3>
      <span style="display:flex;gap:8px;align-items:center">${s.seconds ? `<span class="muted mono">${dur(s.seconds)}</span>` : ""}${tag(s.status)}</span></div>
    ${body}</section>`;
}

function stageCards(d) {
  const S = Object.fromEntries(d.stages.map((s) => [s.key, s]));
  const out = [];

  // collect
  {
    const s = S.collect, n = s.numbers;
    const max = Math.max(1, ...s.sources.map((x) => x.items));
    const row = (x) => `<div class="bar ${x.status === "error" ? "err" : !x.items ? "zero" : ""}">
      <span class="name" title="${esc(x.id)}">${esc(x.id)}</span>
      <span class="track"><i style="width:${x.status === "error" ? 0 : Math.max(2, (x.items / max) * 100)}%"></i></span>
      <span class="n">${x.status === "error" ? "error" : x.status === "disabled" ? "off" : num(x.items)}</span></div>`;
    const top = s.sources.slice(0, 8), rest = s.sources.slice(8);
    const errors = s.sources.filter((x) => x.status === "error");
    out.push(card(s, "", n.items == null ? `<p class="empty">Nothing fetched yet.</p>` : `
      <div class="big"><div><b>${num(n.items)}</b><span>items fetched</span></div>
        <div><b>${num(n.sources)}</b><span>sources</span></div>
        <div class="${n.failing ? "b-bad" : ""}"><b>${num(n.failing)}</b><span>failing</span></div>
        <div class="${n.empty ? "b-warn" : ""}"><b>${num(n.empty)}</b><span>returned nothing</span></div></div>
      <div class="bars">${top.map(row).join("")}</div>
      ${rest.length ? `<details class="more"><summary>All ${s.sources.length} sources</summary><div class="bars">${rest.map(row).join("")}</div></details>` : ""}
      ${errors.length ? `<p class="note">Errors: ${errors.map((x) => `${esc(x.id)} (${esc(x.error)})`).join(", ")}</p>` : ""}`));
  }

  // rank
  {
    const s = S.rank;
    const list = (s.top.length ? s.top : s.lineup);
    const item = (x, i) => `<li class="story ${x.picked ? "" : "out"}">
      <span class="rank-n">${i + 1}</span>
      <div>${x.url ? `<a class="t" href="${esc(safeUrl(x.url))}" target="_blank" rel="noopener noreferrer">${esc(plain(x.title))}</a>` : `<span class="t">${esc(plain(x.title))}</span>`}
        <div class="m">${catTag(x.category)}${x.outlets?.length ? `<span>${esc(x.outlets.length)} outlet${x.outlets.length > 1 ? "s" : ""}: ${esc(x.outlets.slice(0, 3).join(", "))}</span>` : ""}
        ${x.interest != null ? `<span>editor ${esc(x.interest)}/10</span>` : ""}${x.picked ? `<span style="color:var(--ok)">picked</span>` : ""}</div></div>
      <span class="score">${x.score != null ? esc(x.score.toFixed(1)) : ""}</span></li>`;
    out.push(card(s, "", list.length ? `
      ${s.numbers.stories ? `<div class="big"><div><b>${num(s.numbers.stories)}</b><span>stories after clustering</span></div>
        <div><b>${num(s.numbers.picked)}</b><span>picked</span></div></div>` : ""}
      <ol class="stories">${list.map(item).join("")}</ol>
      ${s.note ? `<p class="note">${esc(s.note)}</p>` : s.top.length ? `<p class="note">Score is importance plus the editor's interest rating; stories above a picked one that were not picked hit the per-topic or per-source cap, or had too little article text.</p>` : ""}`
      : `<p class="empty">No ranking yet.</p>`));
  }

  // write + gate side by side
  {
    const s = S.write, n = s.numbers;
    out.push(card(s, "third", n.attempts || s.model ? `
      <div class="big"><div><b>${num(n.attempts)}</b><span>${n.attempts === 1 ? "attempt" : "attempts"}</span></div>
        ${n.calls ? `<div><b>${num(n.calls)}</b><span>model calls</span></div>` : ""}
        ${n.words ? `<div><b>${num(n.words)}</b><span>words</span></div>` : ""}</div>
      <dl class="kv">${s.model ? `<dt>Model</dt><dd class="mono">${esc(s.model)}</dd>` : ""}
        ${n.tokens ? `<dt>Tokens</dt><dd>${num(n.tokens)}</dd>` : ""}</dl>` : `<p class="empty">Not written yet.</p>`));
  }
  {
    const s = S.verify, n = s.numbers;
    const total = n.checked || 0;
    const seg = (v, c) => (total && v ? `<i style="width:${(v / total) * 100}%;background:${c}"></i>` : "");
    const layer = (name, l, done) => `<div class="layer"><span class="eyebrow">${name}</span>
      <p>${l ? `${num(l.checked)} checked · ${num(l.ok)} confirmed · ${num(l.repaired)} repaired · ${num(l.dropped)} removed` : done ? "Done" : "No numbers recorded"}</p></div>`;
    out.push(card(s, "two-thirds", total ? `
      <div class="big"><div><b>${num(n.checked)}</b><span>sentences checked</span></div>
        <div class="b-ok"><b>${num(n.confirmed)}</b><span>confirmed</span></div>
        <div class="b-warn"><b>${num(n.repaired)}</b><span>repaired</span></div>
        <div class="b-bad"><b>${num(n.removed)}</b><span>removed</span></div>
        ${n.unused ? `<div><b>${num(n.unused)}</b><span>verified, not used</span></div>` : ""}</div>
      <div class="stack" role="img" aria-label="${n.confirmed} confirmed, ${n.repaired} repaired, ${n.removed} removed of ${n.checked}">
        ${seg(n.confirmed, "var(--ok)")}${seg(n.repaired, "var(--warn)")}${seg(n.removed, "var(--bad)")}</div>
      <div class="legend"><span><i style="background:var(--ok)"></i>Confirmed by the source</span><span><i style="background:var(--warn)"></i>Repaired (e.g. a number fixed)</span><span><i style="background:var(--bad)"></i>Removed</span></div>
      <div class="layers">${layer("Layer 1 · rules against source text", s.layer1, s.layer1Done)}${layer("Layer 2 · model re-reads the sources", s.layer2, s.layer2Done)}</div>
      ${s.removedSamples.length ? `<details class="more"><summary>Removed sentences (${s.removedSamples.length}${n.removed > s.removedSamples.length ? ` of ${n.removed}` : ""})</summary>
        <ul class="removed">${s.removedSamples.map((r) => `<li>${esc(plain(r.text))}<small>${esc(r.where)} · ${esc((r.problems || []).join("; "))}</small></li>`).join("")}</ul></details>` : ""}`
      : `<p class="empty">Nothing verified yet.</p>`));
  }
  {
    const s = S.gate;
    out.push(card(s, "", s.status === "pending" ? `<p class="empty">Not reached yet.</p>` : `
      <div class="big"><div class="${s.status === "ok" ? "b-ok" : s.status === "failed" ? "b-bad" : ""}"><b>${s.status === "ok" ? "Passed" : s.status === "failed" ? "Failed" : STATUS_WORD[s.status]}</b>
        <span>after ${num(s.numbers.attempts)} ${s.numbers.attempts === 1 ? "attempt" : "attempts"}</span></div></div>
      ${s.fails.length ? `<ul class="fails">${s.fails.map((f) => `<li><b>Try ${esc(f.attempt)}</b>${esc(f.text)}</li>`).join("")}</ul>`
        : s.status === "ok" ? `<p class="note">Word count, sources, links, images and the verification bar all passed.</p>` : ""}`));
  }
  {
    const p = S.publish, dp = S.deploy;
    out.push(card({ ...p, label: "Publish & deploy" }, "", `
      <dl class="kv"><dt>Commit</dt><dd>${tag(p.status)} ${p.numbers.words ? `<span class="muted">${num(p.numbers.words)} words · ${num(p.numbers.sources)} sources</span>` : ""}</dd>
        <dt>Deploy</dt><dd>${tag(dp.status)} ${dp.seconds ? `<span class="muted">${dur(dp.seconds)}</span>` : ""}
          ${dp.url ? ` · <a href="${esc(safeUrl(dp.url))}" target="_blank" rel="noopener noreferrer">log</a>` : ""}</dd>
        ${p.error ? `<dt>Error</dt><dd>${esc(p.error)}</dd>` : ""}
        <dt>Social</dt><dd>${tag(S.social.status)} ${S.social.numbers.pending != null ? `<a href="#social">${S.social.numbers.pending} to review</a>` : ""}</dd></dl>`));
  }
  return out.join("");
}

async function renderToday(date) {
  const today = state.status?.today;
  date = date || today;
  let d;
  try {
    d = state.days.get(date) || await api(`day?date=${date}`);
    state.days.set(date, d);
  } catch (err) {
    view.innerHTML = problem(err, "today's pipeline");
    return;
  }
  const v = d.verdict;
  const main = d.runs.find((r) => r.id === d.mainRunId);
  const sub = v === "bad" ? esc(d.reason || "The run failed. Open its log.")
    : v === "waiting" ? (d.nextRun ? `Next scheduled try at ${time(d.nextRun)} IST; backups at 07:15 and 09:07.` : "No scheduled tries left today.")
    : v === "paused" ? "Daily posts are paused in config/site.yaml. Resume from Controls."
    : v === "running" ? "A run is in progress; this page refreshes every 30 seconds."
    : d.hasSummary ? "" : "This day ran before run summaries existed: numbers come from the run log and the committed post.";
  view.innerHTML = `
    <div class="hero">
      <div>
        <div class="datenav">
          <span class="eyebrow">${date === today ? "Today" : "Day"} · ${esc(longDate(date))}</span>
          <a class="iconbtn" href="#today/${shiftDate(date, -1)}" aria-label="Previous day">${svg("left")}</a>
          <a class="iconbtn" href="#today/${shiftDate(date, 1)}" aria-label="Next day" ${date >= today ? 'aria-disabled="true" tabindex="-1"' : ""}>${svg("right")}</a>
        </div>
        <h1 class="verdict v-${esc(v)}"><span class="orb" aria-hidden="true"></span><span class="verdict-text">${esc(VERDICT[v](d))}</span></h1>
        ${sub ? `<p class="subline">${sub}</p>` : ""}
        ${d.post ? `<a class="headline-link" href="${SITE}posts/${esc(encodeURIComponent(d.post.slug))}/" target="_blank" rel="noopener noreferrer">${esc(plain(d.post.headline))} <span class="arrow">↗</span></a>` : ""}
        <div class="meta-row">
          ${d.totalSeconds ? `<span class="stat-chip">Run <b>${dur(d.totalSeconds)}</b></span>` : ""}
          ${d.post ? `<span class="stat-chip">Read <b>${d.post.minutes} min</b></span><span class="stat-chip">Model <b>${esc(d.post.model.split(":").pop())}</b></span>` : ""}
          ${d.runs.length ? `<span class="stat-chip">Runs <b>${d.runs.length}</b></span>` : ""}
        </div>
      </div>
      <div class="runs" aria-label="Runs this day">
        ${d.runs.length ? d.runs.map((r) => `<a class="run ${r.id === d.mainRunId ? "main" : ""} ${r.noop ? "noop" : ""}" href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener noreferrer"
          title="${esc(r.reason || "")}"><span class="dot d-${esc(runDot(r))}"></span>
          <span><span class="when">${time(r.created)}</span> · ${esc(r.trigger)} · ${esc(r.noop ? "nothing to do" : r.outcome === "unknown" ? "finished" : r.outcome)}${r.seconds ? ` · ${dur(r.seconds)}` : ""}</span>
          <span class="ext">log ↗</span></a>`).join("") : `<div class="run"><span class="dot d-pending"></span><span>No runs yet this day</span><span></span></div>`}
      </div>
    </div>
    ${rail(d)}
    <div class="stages">${d.stages.every((s) => s.status === "pending" || s.status === "skipped") && !d.runs.length ? `
      <section class="card wide"><div class="card-head"><h3>What happens next</h3></div>
        <p class="note" style="margin:0">${v === "paused" ? "Nothing runs while posts are paused." : `At each scheduled try the run collects from every source, ranks the stories, writes the post, checks every sentence against its sources twice, and publishes only if the gate passes. This page fills in stage by stage${d.nextRun ? ` from ${time(d.nextRun)} IST` : ""}.`}</p></section>` : stageCards(d)}</div>`;
  requestAnimationFrame(() => { const f = $(".rail .fill"); if (f) f.style.width = f.dataset.w; });
  if (main?.outcome === "running" || v === "running") schedule(() => { state.days.delete(date); route(); }, 30000);
}

// a run that skipped after real work (gate failed, too few stories) is a warning; "post already there" is not
function runDot(r) {
  if (r.noop) return "skipped";
  return { published: "ok", unknown: "ok", skipped: "warn", failed: "failed", running: "running" }[r.outcome] || "skipped";
}

let timer = null;
function schedule(fn, ms) { clearTimeout(timer); timer = setTimeout(fn, ms); }

// ---------- history ----------
async function renderHistory() {
  try {
    state.history = state.history || await api("history");
  } catch (err) {
    view.innerHTML = problem(err, "history");
    return;
  }
  const strip = [...state.history.days].reverse();
  const days = state.history.days.filter((d) => d.status !== "before");
  const failures = days.filter((d) => d.status === "bad" || d.status === "warn").length;
  const posted = days.filter((d) => d.post).length;
  view.innerHTML = `
    <div class="section-title" style="margin-top:0"><h1 style="font-size:clamp(26px,3.6vw,36px)">History</h1>
      <span class="muted">${posted} posts · ${failures ? `<span style="color:var(--bad)">${failures} with problems</span>` : "no failures"}</span></div>
    <div class="strip" aria-label="Last ${strip.length} days">${strip.map((d) => d.status === "before" ? `<span class="before" title="${esc(shortDate(d.date))}: before the first post"></span>` : `<a href="#today/${esc(d.date)}" class="${esc(d.status)}"
      title="${esc(shortDate(d.date))}: ${esc(STATUS_WORD[d.status] || d.status)}" aria-label="${esc(shortDate(d.date))}: ${esc(STATUS_WORD[d.status] || d.status)}"></a>`).join("")}</div>
    <div class="strip-ends"><span>${esc(shortDate(strip[0].date))}</span><span>Today</span></div>
    <ol class="timeline">${days.map((d) => {
      const isBad = d.status === "bad" || d.status === "warn";
      const runs = d.runs.map((r) => `<a class="chip ${r.outcome === "failed" ? "bad" : ""}" href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener noreferrer">
        <span class="dot d-${esc(runDot(r))}"></span>${time(r.created)} ${esc(r.trigger)}${r.noop ? " · nothing to do" : r.seconds ? ` · ${dur(r.seconds)}` : ""}</a>`).join("");
      const bad = d.deploys.filter((x) => x.conclusion && x.conclusion !== "success");
      const okDeps = d.deploys.filter((x) => !bad.includes(x));
      const deps = bad.map((x) => `<a class="chip deploy bad" href="${esc(safeUrl(x.url))}" target="_blank" rel="noopener noreferrer"
        title="${esc(x.title)}"><span class="dot d-failed"></span>deploy failed ${time(x.created)}</a>`).join("")
        + (okDeps.length ? `<a class="chip deploy" href="${esc(safeUrl(okDeps[0].url))}" target="_blank" rel="noopener noreferrer"
        title="Latest: ${esc(okDeps[0].title)}"><span class="dot d-${okDeps[0].status !== "completed" ? "running" : "ok"}"></span>${okDeps.length} deploy${okDeps.length > 1 ? "s" : ""}, last ${time(okDeps[0].created)}</a>` : "");
      return `<li class="day ${isBad ? "is-bad" : ""}"><span class="dot d-${esc(d.status)}"></span><div class="card">
        <div class="day-head"><span class="date">${esc(shortDate(d.date))}</span>${tag(d.status)}
          <a href="#today/${esc(d.date)}" style="margin-left:auto;font-size:13px">Pipeline →</a></div>
        <h3 class="day-title">${d.title ? esc(plain(d.title)) : `<span class="muted">${d.status === "waiting" ? "Not posted yet" : "No post"}</span>`}</h3>
        ${runs || deps ? `<div class="chips">${runs}${deps}</div>` : ""}</div></li>`;
    }).join("")}</ol>`;
}

// ---------- social ----------
const PLAT = { instagram: "Instagram", x: "X", linkedin: "LinkedIn" };
const HOW = { api: ["Auto-post", "free Instagram API"], paid: ["Paid API", "about $0.20 a post"], manual: ["Manual", "copy and post by hand"] };

function itemStatus(i) { return state.decisions.get(i.id) || i.status; }
function itemText(i) { return state.edits.get(i.id) ?? i.edited_text ?? i.text; }
function xLen(t) { return t.replace(/https?:\/\/\S+/g, "x".repeat(23)).length; }

function itemCard(i) {
  const st = itemStatus(i), text = itemText(i), edited = text !== i.text;
  const [howTitle, howNote] = HOW[i.posting] || ["", ""];
  return `<article class="card item is-${esc(st)}" data-item="${esc(i.id)}">
    <div class="item-head"><span class="picon p-${esc(i.platform)}">${svg(i.platform)}</span><span class="plat">${esc(PLAT[i.platform])}</span>
      <span class="muted" style="font-size:12.5px">${esc(i.kind)}</span>${tag(st)}</div>
    <div class="how ${i.posting === "paid" ? "paid" : ""}" title="${esc(i.note)}"><span><b>${esc(howTitle)}</b> · ${esc(howNote)}</span></div>
    ${i.media?.length ? `<div class="shot"><img src="${esc(safeUrl(i.media[0]))}" alt="Instagram card for ${esc(i.id.slice(0, 10))}" loading="lazy" width="1080" height="1350"></div>` : ""}
    <div class="preview ${edited ? "edited" : ""}" data-preview>${esc(text)}</div>
    ${i.platform === "x" ? `<div class="counter ${xLen(text) > 280 ? "over" : ""}">${xLen(text)} / 280</div>` : ""}
    <div class="actions">
      <button class="btn ok" data-act="approve" ${st !== "pending" ? "disabled" : ""}>Approve</button>
      <button class="btn" data-act="edit" ${st !== "pending" ? "disabled" : ""}>Edit</button>
      <button class="btn ghost" data-act="skip" ${st !== "pending" ? "disabled" : ""}>Skip</button>
      ${i.platform === "linkedin" ? `<button class="btn ghost" data-act="copy" aria-label="Copy LinkedIn text">${svg("copy")}Copy</button>` : ""}
    </div></article>`;
}

async function renderSocial() {
  try {
    state.social = state.social || await api("social");
  } catch (err) {
    view.innerHTML = problem(err, "the social queue");
    return;
  }
  renderCounts();
  const days = state.social.days;
  view.innerHTML = `
    <div class="section-title" style="margin-top:0"><h1 style="font-size:clamp(26px,3.6vw,36px)">Social queue</h1>
      <span class="muted">${state.status?.dryRun ? "Dry run: approving only shows what would be posted" : "Live"}</span></div>
    ${days.length ? days.map((d) => `<section class="sday">
      <div class="sday-head"><div><span class="eyebrow">${esc(longDate(d.date))}</span><h2>${esc(plain(d.headline))}</h2></div>
        <a href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener noreferrer" class="btn ghost">Read the post ${svg("ext")}</a></div>
      <div class="queue">${d.items.map(itemCard).join("")}</div></section>`).join("")
      : `<div class="banner">${svg("warn")}<div><h2>Nothing in the queue</h2><p>The daily run writes <code>data/social/&lt;date&gt;.json</code> next to each new post. None are on main yet.</p></div></div>`}`;
  view.querySelectorAll(".shot img").forEach((img) => img.addEventListener("error", () => {
    img.parentElement.innerHTML = `<div class="missing">Card not on the live site yet</div>`;
  }, { once: true }));
}

function findItem(id) {
  for (const d of state.social?.days || []) for (const i of d.items) if (i.id === id) return i;
  return null;
}

async function onItemAction(btn) {
  const el = btn.closest("[data-item]");
  const item = findItem(el.dataset.item);
  const act = btn.dataset.act;
  if (!item) return;
  if (act === "copy") {
    try { await navigator.clipboard.writeText(itemText(item)); toast("LinkedIn text copied."); } catch { toast("Copy failed: select the text by hand.", "err"); }
    return;
  }
  if (act === "edit") {
    const pre = el.querySelector("[data-preview]");
    const ta = document.createElement("textarea");
    ta.className = "edit";
    ta.value = itemText(item);
    ta.setAttribute("aria-label", `Edit ${PLAT[item.platform]} text`);
    pre.replaceWith(ta);
    const counter = el.querySelector(".counter");
    ta.addEventListener("input", () => {
      if (counter) { counter.textContent = `${xLen(ta.value)} / 280`; counter.classList.toggle("over", xLen(ta.value) > 280); }
    });
    btn.textContent = "Save";
    btn.dataset.act = "save";
    ta.focus();
    return;
  }
  if (act === "save") {
    const ta = el.querySelector("textarea");
    const v = ta.value.trim();
    if (!v) return toast("Text can't be empty.", "err");
    if (v === item.text) state.edits.delete(item.id); else state.edits.set(item.id, v);
    el.outerHTML = itemCard(item);
    return;
  }
  const open = el.querySelector("textarea.edit");       // approving while editing keeps the edit
  if (open && open.value.trim()) {
    if (open.value.trim() === item.text) state.edits.delete(item.id); else state.edits.set(item.id, open.value.trim());
  }
  const text = itemText(item);
  if (act === "approve" && item.platform === "x" && xLen(text) > 280) return toast("<b>Too long.</b> X allows 280 characters.", "err");
  const edited = text !== item.text;
  const ok = await confirmDialog(act === "approve" ? `Approve ${PLAT[item.platform]}?` : `Skip ${PLAT[item.platform]}?`,
    `<p>${act === "approve" ? `This starts the <b>publish-social</b> workflow for <code>${esc(item.id)}</code>${edited ? " with your edited text" : ""}.` : `Nothing will be posted for <code>${esc(item.id)}</code>.`}</p>
     <p class="muted">${state.status?.dryRun ? "Dry run: the dashboard only shows the request it would send." : "Live: the workflow runs now."}
     ${item.posting === "paid" && act === "approve" ? " X posting costs about $0.20 once it is live." : ""}</p>`,
    act === "approve" ? "Approve" : "Skip");
  if (!ok) return;
  try {
    const r = await api("social/action", { method: "POST", body: { item_id: item.id, action: act, ...(edited ? { text } : {}) } });
    state.lastResult = r;
    state.decisions.set(item.id, act === "approve" ? "approved" : "skipped");
    el.outerHTML = itemCard(item);
    renderCounts();
    toast(r.dryRun ? `<b>Dry run.</b> Would dispatch publish-social.yml for ${esc(item.id)}.` : `Started publish-social for ${esc(item.id)}.`, r.dryRun ? "dry" : "");
  } catch (err) {
    toast(`<b>Failed.</b> ${esc(err.message)}`, "err");
  }
}

// ---------- stats ----------
const PLATFORMS = [
  { key: "website", name: "Website", color: "var(--accent)", icon: "deploy" },
  { key: "instagram", name: "Instagram", color: "var(--policy)", icon: "instagram" },
  { key: "x", name: "X", color: "var(--ink)", icon: "x" },
  { key: "linkedin", name: "LinkedIn", color: "var(--models)", icon: "linkedin" },
];
const fmtDay = (d) => new Date(`${d}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

/** [{date, value}] ascending, nulls dropped. */
function followerSeries(st, key) {
  if (key === "instagram") return st.days.map((d) => ({ date: d.date, value: d.instagram?.followers })).filter((p) => p.value != null);
  if (key === "website") return (st.days.at(-1)?.website?.daily || []).map((d) => ({ date: d.day, value: d.visitors }));
  return (st.manual?.[key] || []).map((e) => ({ date: e.date, value: e.followers })).filter((p) => p.value != null);
}

/** Change against the latest point at least 7 days older (or the oldest point there is). */
function weekChange(series) {
  if (series.length < 2) return null;
  const last = series.at(-1);
  const cutoff = new Date(Date.parse(`${last.date}T00:00:00Z`) - 7 * 864e5).toISOString().slice(0, 10);
  const base = [...series].reverse().find((p) => p.date <= cutoff) || series[0];
  return base === last ? null : { delta: last.value - base.value, since: base.date };
}

function sparkline(series, color) {
  if (series.length < 2) return "";
  const W = 160, H = 40, P = 4;
  const vals = series.map((p) => p.value), lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
  const pts = series.map((p, i) => [P + (i / (series.length - 1)) * (W - 2 * P), H - P - ((p.value - lo) / span) * (H - 2 * P)]);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
  const [lx, ly] = pts.at(-1);
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
    <path d="${d}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>
    <circle cx="${lx}" cy="${ly}" r="3.5" fill="${color}" stroke="var(--surface)" stroke-width="2"/></svg>`;
}

function platformTile(st, p) {
  const latest = st.days.at(-1) || {};
  const auto = p.key === "website" || p.key === "instagram";
  const snap = auto ? latest[p.key] : null;
  const series = followerSeries(st, p.key);
  const head = `<div class="ptile-head"><span class="picon p-${p.key === "website" ? "web" : p.key}">${svg(p.icon)}</span>
    <span class="plat">${p.name}</span>`;
  if (auto && (!snap || snap.status !== "ok")) {
    const how = p.key === "website" ? "Add the <code>GOATCOUNTER_TOKEN</code> secret" : "Add the <code>INSTAGRAM_TOKEN</code> secret";
    return `<section class="card ptile is-off">${head}${tag(snap?.status === "error" ? "failed" : "pending")}</div>
      <p class="note" style="margin:0">${snap?.status === "error" ? `Last collection failed: ${esc(snap.error)}. If it says HTTP 400 or 401, the token has expired.` : `${st.days.length ? "Not connected." : "No numbers collected yet."} ${how} (see README).`}</p></section>`;
  }
  if (!auto && !series.length) {
    return `<section class="card ptile is-off">${head}<span class="status-tag t-pending">Manual</span></div>
      <p class="note" style="margin:0">No free API for these numbers. Type them in below once a week.</p></section>`;
  }
  const last = series.at(-1);
  const ch = p.key === "website" ? null : weekChange(series);
  const value = p.key === "website" ? snap.visitors_28d : last?.value;
  const label = p.key === "website" ? "visitors, last 28 days" : "followers";
  const sub = p.key === "website"
    ? `${num(snap.visitors_day ?? 0)} on ${fmtDay(latest.date)}`
    : p.key === "instagram" && snap.day?.reach != null ? `reach ${num(snap.day.reach)} on ${fmtDay(latest.date)}` : `as of ${fmtDay(last.date)}`;
  return `<section class="card ptile">${head}${auto ? "" : `<span class="status-tag t-pending">Manual</span>`}</div>
    <div class="pnum"><b>${num(value)}</b><span>${label}</span></div>
    <div class="pmeta">${ch ? `<span class="delta ${ch.delta > 0 ? "up" : ch.delta < 0 ? "down" : ""}">${ch.delta > 0 ? "+" : ""}${num(ch.delta)}</span> since ${fmtDay(ch.since)} · ` : ""}${esc(sub)}</div>
    ${sparkline(series, p.color)}</section>`;
}

function visitsChart(daily) {
  if (!daily.length) return `<p class="empty">No daily numbers yet.</p>`;
  // drawn at the card's real width, so axis text stays readable on a phone
  const W = Math.round(Math.min(760, Math.max(300, view.clientWidth * (window.innerWidth > 1080 ? 0.62 : 1) - 64)));
  const H = W < 500 ? 170 : 200, L = 34, B = 22, T = 10, n = daily.length;
  const max = Math.max(1, ...daily.map((d) => d.visitors));
  // a round top for the axis that halves to a whole number, close above the highest bar
  const mag = 10 ** Math.max(0, Math.floor(Math.log10(max)));
  const nice = [1, 1.2, 1.4, 1.6, 2, 2.4, 3, 4, 5, 6, 8, 10].map((m) => m * mag).find((v) => v >= max && Number.isInteger(v / 2)) || max + (max % 2);
  const step = (W - L) / n, bw = Math.max(3, step - 3);
  const y = (v) => T + (H - T - B) * (1 - v / nice);
  const grid = [0, 0.5, 1].map((f) => `<line x1="${L}" x2="${W}" y1="${y(nice * f)}" y2="${y(nice * f)}" class="grid"/>
    <text x="${L - 6}" y="${y(nice * f) + 4}" class="axis" text-anchor="end">${num(nice * f)}</text>`).join("");
  const bars = daily.map((d, i) => {
    const x = L + i * step + (step - bw) / 2, top = y(d.visitors), h = Math.max(0, H - B - top);
    const r = Math.min(4, bw / 2, h);
    // rounded data end, square on the baseline
    const path = h <= 0 ? "" : `M${x} ${H - B}V${top + r}Q${x} ${top} ${x + r} ${top}H${x + bw - r}Q${x + bw} ${top} ${x + bw} ${top + r}V${H - B}Z`;
    return `<g class="hit" data-tip="${esc(fmtDay(d.day))}: ${num(d.visitors)} visitors"><rect x="${L + i * step}" y="${T}" width="${step}" height="${H - T - B}" fill="transparent"/>
      <path d="${path}" class="barfill"/></g>`;
  }).join("");
  const anchor = (i) => (i === 0 ? "start" : i === n - 1 ? "end" : "middle");
  const tx = (i) => (i === 0 ? L + (step - bw) / 2 : i === n - 1 ? L + i * step + (step + bw) / 2 : L + i * step + step / 2);
  const ticks = [0, Math.floor((n - 1) / 2), n - 1].map((i) => `<text x="${tx(i)}" y="${H - 6}" class="axis" text-anchor="${anchor(i)}">${esc(fmtDay(daily[i].day))}</text>`).join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Website visitors per day, ${esc(fmtDay(daily[0].day))} to ${esc(fmtDay(daily.at(-1).day))}">${grid}${bars}${ticks}</svg>
    <details class="more"><summary>Table</summary><div><table class="tbl"><thead><tr><th>Day</th><th>Visitors</th></tr></thead>
    <tbody>${[...daily].reverse().map((d) => `<tr><td>${esc(fmtDay(d.day))}</td><td>${num(d.visitors)}</td></tr>`).join("")}</tbody></table></div></details>`;
}

function barList(rows, name, value, cls = "") {
  const max = Math.max(1, ...rows.map(value));
  return `<div class="bars ${cls}">${rows.map((r) => `<div class="bar"><span class="name" title="${esc(name(r))}">${esc(name(r))}</span>
    <span class="track"><i style="width:${Math.max(2, (value(r) / max) * 100)}%"></i></span><span class="n">${num(value(r))}</span></div>`).join("")}</div>`;
}

function igPosts(posts) {
  if (!posts?.length) return `<p class="empty">No posts yet.</p>`;
  const cell = (v) => (v == null ? `<span class="faint">–</span>` : num(v));
  return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Post</th><th>Reach</th><th>Views</th><th>Likes</th><th>Saves</th><th>Shares</th></tr></thead><tbody>
    ${posts.map((p) => `<tr><td class="post"><a href="${esc(safeUrl(p.permalink))}" target="_blank" rel="noopener noreferrer">${esc(p.caption || p.type || "Post")}</a>
      <small>${p.timestamp ? esc(fmtDay(p.timestamp.slice(0, 10))) : ""}${p.type === "CAROUSEL_ALBUM" ? " · carousel" : ""}</small></td>
      <td>${cell(p.reach)}</td><td>${cell(p.views)}</td><td>${cell(p.likes)}</td><td>${cell(p.saved)}</td><td>${cell(p.shares)}</td></tr>`).join("")}
  </tbody></table></div>`;
}

function manualForm(st) {
  const today = state.status?.today || "";
  const recent = ["x", "linkedin"].flatMap((k) => (st.manual?.[k] || []).slice(-3).map((e) => ({ k, ...e })))
    .sort((a, b) => b.date.localeCompare(a.date)).slice(0, 4);
  return `<form class="mform" id="manual-form" novalidate>
    <label>Platform<select name="platform"><option value="x">X</option><option value="linkedin">LinkedIn</option></select></label>
    <label>Date<input type="date" name="date" value="${esc(today)}" max="${esc(today)}" required></label>
    <label>Followers<input type="number" name="followers" min="0" step="1" inputmode="numeric"></label>
    <label><span>Impressions <small>· 7 days</small></span><input type="number" name="impressions" min="0" step="1" inputmode="numeric"></label>
    <label><span>Engagements <small>· 7 days</small></span><input type="number" name="engagements" min="0" step="1" inputmode="numeric"></label>
    <button class="btn primary" type="submit">Save numbers</button>
  </form>
  ${recent.length ? `<p class="note">Last saved: ${recent.map((e) => `${e.k === "x" ? "X" : "LinkedIn"} ${esc(fmtDay(e.date))}${e.followers != null ? ` · ${num(e.followers)} followers` : ""}`).join("; ")}</p>` : ""}`;
}

async function renderStats() {
  try {
    state.stats = state.stats || await api("stats");
  } catch (err) {
    view.innerHTML = problem(err, "stats");
    return;
  }
  const st = state.stats, latest = st.days.at(-1) || {};
  const web = latest.website?.status === "ok" ? latest.website : null;
  const ig = latest.instagram?.status === "ok" ? latest.instagram : null;
  view.innerHTML = `
    <div class="section-title" style="margin-top:0"><h1 style="font-size:clamp(26px,3.6vw,36px)">Stats</h1>
      <span class="muted">${latest.date ? `Collected ${esc(fmtDay(latest.date))}, 23:30 IST daily` : "Collected daily at 23:30 IST once the secrets are set"}</span></div>
    <div class="ptiles">${PLATFORMS.map((p) => platformTile(st, p)).join("")}</div>
    <div class="stages top">
      <section class="card two-thirds"><div class="card-head"><h3>Website visitors per day</h3><span class="muted" style="font-size:13px">GoatCounter</span></div>
        ${web ? visitsChart(web.daily) : `<p class="empty">Connect GoatCounter to see daily visits.</p>`}</section>
      <section class="card third"><div class="card-head"><h3>Where readers came from</h3><span class="muted" style="font-size:13px">7 days</span></div>
        ${web?.top_refs?.length ? barList(web.top_refs, (r) => r.name, (r) => r.visitors) : `<p class="empty">No referrers yet.</p>`}</section>
      <section class="card"><div class="card-head"><h3>Most-read pages</h3><span class="muted" style="font-size:13px">7 days</span></div>
        ${web?.top_paths?.length ? barList(web.top_paths, (r) => r.title || r.path, (r) => r.visitors, "stacked") : `<p class="empty">No page numbers yet.</p>`}</section>
      <section class="card"><div class="card-head"><h3>X and LinkedIn numbers</h3><span class="muted" style="font-size:13px">typed in</span></div>
        <p class="note" style="margin:0 0 var(--s4)">Neither has a free API for stats. Copy them from each app's analytics once a week.</p>
        ${manualForm(st)}</section>
      <section class="card wide"><div class="card-head"><h3>Instagram posts</h3><span class="muted" style="font-size:13px">${ig ? `@${esc(ig.username || "")} · numbers can lag up to 48 hours` : ""}</span></div>
        ${ig ? igPosts(ig.posts) : `<p class="empty">Connect Instagram to see reach, saves and shares per post.</p>`}</section>
    </div>`;
  wireTips();
  $("#manual-form")?.addEventListener("submit", onManualSubmit);
}

async function onManualSubmit(e) {
  e.preventDefault();
  const f = new FormData(e.target);
  const body = { platform: f.get("platform"), date: f.get("date") };
  for (const k of ["followers", "impressions", "engagements"]) {
    const v = String(f.get(k) || "").trim();
    if (v) body[k] = Number(v);
  }
  if (!["followers", "impressions", "engagements"].some((k) => k in body)) return toast("<b>Nothing to save.</b> Enter at least one number.", "err");
  const btn = e.target.querySelector("button");
  btn.disabled = true;
  try {
    const r = await api("stats/manual", { method: "POST", body });
    state.lastResult = r;
    if (r.done) { state.stats = null; await renderStats(); }
    toast(r.dryRun ? `<b>Dry run.</b> ${esc(r.what)}: not saved.` : `${esc(r.what)}: saved.`, r.dryRun ? "dry" : "");
  } catch (err) {
    toast(`<b>Failed.</b> ${esc(err.message)}`, "err");
  } finally {
    btn.disabled = false;
  }
}

function wireTips() {
  const tip = $("#tip");
  const show = (g, x, y) => {
    tip.textContent = g.dataset.tip;
    tip.hidden = false;
    const w = tip.offsetWidth;
    tip.style.left = `${Math.min(window.innerWidth - w - 8, Math.max(8, x - w / 2))}px`;
    tip.style.top = `${y - 44}px`;
    view.querySelectorAll(".hit.on").forEach((o) => o.classList.remove("on"));
    g.classList.add("on");
  };
  view.querySelectorAll(".chart .hit").forEach((g) => {
    g.addEventListener("pointermove", (e) => show(g, e.clientX, e.clientY));
    g.addEventListener("pointerdown", (e) => show(g, e.clientX, e.clientY));
    g.addEventListener("pointerleave", () => { tip.hidden = true; g.classList.remove("on"); });
  });
}

// ---------- controls ----------
function renderControls() {
  const s = state.status || {};
  const todayDay = state.days.get(s.today);
  view.innerHTML = `
    <div class="section-title" style="margin-top:0"><h1 style="font-size:clamp(26px,3.6vw,36px)">Controls</h1>
      <span class="muted">${s.dryRun ? "Dry run: nothing is sent to GitHub" : "Live: actions change the repository"}</span></div>
    <div class="controls">
      <section class="card control"><h3>${s.paused ? "Resume daily posts" : "Pause daily posts"}</h3>
        <div class="state"><span class="dot ${s.paused ? "d-bad" : s.paused === false ? "d-ok" : ""}"></span>${s.paused == null ? "Unknown (no GitHub token)" : s.paused ? "Paused" : "Running daily"}</div>
        <p>Sets <code>paused: ${s.paused ? "false" : "true"}</code> in <code>config/site.yaml</code> with one commit to main. Scheduled runs then ${s.paused ? "post again" : "skip cleanly"}.</p>
        <button class="btn ${s.paused ? "primary" : "danger"}" data-control="pause">${s.paused ? "Resume" : "Pause"}</button></section>
      <section class="card control"><h3>Rerun today</h3>
        <p>Starts <code>daily.yml</code> on main now. ${todayDay?.post ? "Today's post already exists, so the run will stop at once." : "Use it when the scheduled tries failed or were dropped."}</p>
        <button class="btn primary" data-control="rerun">Run daily now</button></section>
      <section class="card control"><h3>Retry deploy</h3>
        <p>Starts <code>deploy.yml</code>: runs the tests, rebuilds the site from main and publishes it to GitHub Pages.</p>
        <button class="btn" data-control="redeploy">Deploy again</button></section>
    </div>
    <section class="card setup"><div class="card-head"><h3>Connection</h3></div>
      <dl class="kv"><dt>Repository</dt><dd class="mono">${esc(s.repo || "")}</dd>
        <dt>GitHub token</dt><dd>${s.configured ? "Set (kept server-side)" : `<span style="color:var(--warn)">Not set</span>`}</dd>
        <dt>Signed in as</dt><dd>${esc(s.user === "local" ? "Local dev server (127.0.0.1)" : s.user || "")}</dd>
        <dt>Writes</dt><dd>${s.dryRun ? "Dry run (set DRY_RUN=0 to go live)" : "Live"}</dd></dl></section>
    <section class="result" id="result">${resultCard()}</section>`;
}

function resultCard() {
  const r = state.lastResult;
  if (!r) return "";
  return `<div class="card"><div class="card-head"><h3>Last action: ${esc(r.what)}</h3>${r.dryRun ? `<span class="status-tag t-warn">Dry run</span>` : tag(r.done ? "ok" : "pending")}</div>
    <p class="note" style="margin:0 0 var(--s3)">${r.dryRun ? "Dry run: this request was not sent." : esc(r.note || "Sent.")}${r.diff ? ` Change: <code>${esc(r.diff.from)}</code> → <code>${esc(r.diff.to)}</code>` : ""}</p>
    <pre class="json">${esc(JSON.stringify(r.request, null, 2))}</pre></div>`;
}

async function onControl(btn) {
  const c = btn.dataset.control, s = state.status || {};
  const spec = {
    pause: [s.paused ? "Resume daily posts?" : "Pause daily posts?", `<p>One commit to main changing <code>paused</code> in <code>config/site.yaml</code>. Pushing it also redeploys the site.</p>`, "pause", { paused: !s.paused }],
    rerun: ["Run the daily post now?", `<p>Starts <code>daily.yml</code>. If today's post exists it stops at once; otherwise it writes, verifies and may publish a post (10 to 40 minutes).</p>`, "rerun", {}],
    redeploy: ["Deploy the site again?", `<p>Starts <code>deploy.yml</code>: tests, build, publish to GitHub Pages.</p>`, "redeploy", {}],
  }[c];
  const ok = await confirmDialog(spec[0], spec[1] + `<p class="muted">${s.dryRun ? "Dry run: you will see the request, nothing is sent." : "Live: this changes the repository."}</p>`, s.dryRun ? "Show request" : "Do it");
  if (!ok) return;
  btn.disabled = true;
  try {
    const r = await api(`control/${spec[2]}`, { method: "POST", body: spec[3] });
    state.lastResult = r;
    if (!r.dryRun && c === "pause" && r.done) { state.status.paused = !s.paused; renderMode(); }
    toast(r.dryRun ? `<b>Dry run.</b> ${esc(r.what)}: request shown below.` : esc(r.note || `${r.what}: done.`), r.dryRun ? "dry" : "");
    renderControls();
    $("#result")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (err) {
    toast(`<b>Failed.</b> ${esc(err.message)}`, "err");
    btn.disabled = false;
  }
}

// ---------- routing ----------
async function route() {
  clearTimeout(timer);
  const [tab = "today", arg] = location.hash.replace(/^#/, "").split("/");
  const name = ["today", "history", "social", "stats", "controls"].includes(tab) ? tab : "today";
  document.querySelectorAll("[data-tab]").forEach((a) => {
    if (a.dataset.tab === name) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  document.title = `${name[0].toUpperCase()}${name.slice(1)} · Five Minute AI Control`;
  view.setAttribute("aria-busy", "true");
  if (!view.querySelector(".loading")) view.insertAdjacentHTML("afterbegin", `<div class="loading" style="padding:0 0 var(--s4)"><span class="spinner" aria-hidden="true"></span></div>`);
  const date = /^\d{4}-\d\d-\d\d$/.test(arg || "") ? arg : null;
  if (name === "today") await renderToday(date);
  else if (name === "history") await renderHistory();
  else if (name === "social") await renderSocial();
  else if (name === "stats") await renderStats();
  else renderControls();
  view.setAttribute("aria-busy", "false");
}

view.addEventListener("click", (e) => {
  const t = e.target.closest("button, a");
  if (!t) return;
  if (t.dataset.jump) { document.getElementById(t.dataset.jump)?.scrollIntoView({ behavior: "smooth", block: "start" }); return; }
  if (t.dataset.act) { onItemAction(t); return; }
  if (t.dataset.control) { onControl(t); return; }
  if (t.hasAttribute("data-retry")) { state.history = null; state.social = null; state.stats = null; state.days.clear(); route(); }
});
let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (location.hash.startsWith("#stats") && state.stats) renderStats(); }, 250);
});
window.addEventListener("hashchange", () => { $("#tip").hidden = true; route(); window.scrollTo(0, 0); });

(async function start() {
  try {
    state.status = await api("status");
  } catch (err) {
    view.innerHTML = err.status === 403
      ? `<div class="banner bad">${svg("warn")}<div><h2>Not signed in</h2><p>${esc(err.message)}</p></div></div>`
      : problem(err, "the dashboard");
    return;
  }
  renderMode();
  route();
  if (state.status.configured) api("social").then((s) => { state.social = state.social || s; renderCounts(); }).catch(() => {});
})();
