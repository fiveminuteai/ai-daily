// Five Minute AI control dashboard. Plain JavaScript, no build step, no third-party code.
// The browser only talks to /api on the same origin; the GitHub token never reaches it.

const $ = (sel, root = document) => root.querySelector(sel);
const view = $("#view");
const state = { status: null, days: new Map(), history: null, social: null, decisions: new Map(), edits: new Map(), schedules: new Map(),
                lastResult: null, media: new Map(), mail: null, accounts: null, roadmap: null, info: null, pages: null };
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
  calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M4 7l8 6 8-6"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  github: '<path d="M9 19c-4 1.5-4-2-6-2.5M15 21v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1-.3-3.4 1.3a11.6 11.6 0 0 0-6.2 0C6.6 2.8 5.6 3.1 5.6 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4.2 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
};
const svg = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICON[name]}</svg>`;
const STATUS_WORD = { ok: "OK", failed: "Failed", skipped: "Skipped", pending: "Pending", running: "Running",
                      waiting: "Waiting", bad: "Failed", warn: "Warning", missed: "No run", unknown: "Done", expired: "Expired", off: "Off",
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

function confirmDialog(title, bodyHtml, okLabel = "Confirm", danger = false) {
  const dlg = $("#confirm");
  $("#confirm-title").textContent = title;
  $("#confirm-body").innerHTML = bodyHtml;
  $("#confirm-ok").textContent = okLabel;
  $("#confirm-ok").className = `btn ${danger ? "danger-solid" : "primary"}`;
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

// ---------- data: shown from memory at once, refreshed quietly in the background ----------
// Every GitHub-backed read goes through load(): a screen that was loaded before draws instantly from memory; if that
// copy is over 20 s old, one background request refreshes it and the screen is redrawn only if something changed
// (and never while you are typing, choosing or watching a video).
const DATA = new Map();                 // path -> { at, value, promise }
const FRESH_MS = 20e3;
let usedPaths = new Set();              // what the visible screen was drawn from

function assignData(path, v) {
  if (path.startsWith("day?date=")) state.days.set(path.slice(9), v);
  else ({ history: () => { state.history = v; }, social: () => { state.social = v; }, stats: () => { state.stats = v; },
          "local/mail": () => { state.mail = v; }, "local/accounts": () => { state.accounts = v; },
          "local/pages": () => { state.pages = v; }, "local/info": () => { state.info = v; } }[path] || (() => {}))();
  if (path.startsWith("media?date=")) state.media.set(path.slice(11), v);
}

function fetchData(path) {
  const entry = DATA.get(path) || {};
  const promise = api(path).then((v) => {
    const changed = "value" in entry && JSON.stringify(entry.value) !== JSON.stringify(v);
    DATA.set(path, { at: Date.now(), value: v });
    assignData(path, v);
    if (changed) dataChanged(path);
    return v;
  }, (err) => {
    if ("value" in entry) DATA.set(path, { at: entry.at, value: entry.value }); else DATA.delete(path);
    throw err;
  });
  DATA.set(path, { ...entry, promise });
  return promise;
}

function load(path) {
  usedPaths.add(path);
  const e = DATA.get(path);
  if (e && "value" in e) {
    if (Date.now() - e.at > FRESH_MS && !e.promise) fetchData(path).catch(() => {});
    assignData(path, e.value);
    return Promise.resolve(e.value);
  }
  return e?.promise || fetchData(path);
}

function busyScreen() {
  const a = document.activeElement;
  return Boolean(document.querySelector("dialog[open]") || (a && view.contains(a) && /INPUT|TEXTAREA|SELECT/.test(a.tagName))
    || [...view.querySelectorAll("video")].some((v) => !v.paused));
}

let redrawTimer = null;
function dataChanged(path) {
  renderCounts();
  if (!usedPaths.has(path)) return;
  clearTimeout(redrawTimer);
  redrawTimer = setTimeout(() => { if (!busyScreen()) route({ keepScroll: true }); }, 300);
}

/** After the first screen: warm every section in the background, one request at a time. */
function prefetch() {
  const today = state.status?.today || todayIstClient();
  const yesterday = new Date(Date.parse(`${today}T00:00:00Z`) - 864e5).toISOString().slice(0, 10);
  const paths = state.status?.configured
    ? ["social", "history", "stats", `media?date=${today}`, `media?date=${yesterday}`, `day?date=${yesterday}`] : [];
  if (state.status?.desktop) paths.push("local/accounts", "local/pages", "local/info", "local/roadmap", "local/mail");
  let i = 0;
  const next = () => { if (i < paths.length) load(paths[i++]).catch(() => {}).finally(() => setTimeout(next, 120)); };
  setTimeout(next, 400);
}

const todayIstClient = () => new Date(Date.now() + 330 * 60e3).toISOString().slice(0, 10);

// ---------- header ----------
function renderMode() {
  const s = state.status;
  if (!s) return;
  document.body.dataset.desktop = s.desktop ? "1" : "0";
  const pills = [
    s.paused ? `<span class="pill paused"><span class="dot d-bad"></span>Paused</span>` : "",
    s.localFiles ? `<span class="pill local" title="Files not on main yet are read from this computer's checkout">Local files</span>` : "",
    s.dryRun ? `<span class="pill dry" title="Writes are only described, never sent to GitHub">Dry run</span>`
             : `<span class="pill live" title="Writes are sent to GitHub">Live</span>`,
  ].join("");
  $("#mode").innerHTML = pills;
  $("#side-mode").innerHTML = `<div class="side-pills">${pills}</div>
    <p class="side-note">${s.desktop ? "Desktop app" : "Web"} · ${s.configured ? "GitHub connected" : "GitHub not connected"}</p>`;
}

function setCount(name, n) {
  document.querySelectorAll(`[data-count="${name}"]`).forEach((el) => { el.hidden = !n; el.textContent = n > 99 ? "99+" : n; });
}

function renderCounts() {
  setCount("posts", (state.social?.days || []).flatMap((d) => d.items).filter(needsYou).length);
  if (state.mail?.connected) setCount("mail", state.mail.unread || 0);
}

// ---------- today ----------
const VERDICT = {
  ok: (d) => `Published${d.post?.generated_at ? ` ${time(d.post.generated_at)} IST` : ""}`,
  warn: () => "Published, with a problem",
  bad: () => "No post",
  running: () => "Running now",
  waiting: (d) => (d.nextRun ? `Waiting for the ${time(d.nextRun)} run` : "No run yet"),
  missed: () => "No post that day",
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
    d = await load(`day?date=${date}`);
  } catch (err) {
    view.innerHTML = problem(err, "today's pipeline");
    return;
  }
  const v = d.verdict;
  const main = d.runs.find((r) => r.id === d.mainRunId);
  const next = d.nextRun ? `Next scheduled try at ${time(d.nextRun)} IST${d.triesLeft > 1 ? `; ${d.triesLeft} tries left today, the last at ${time(d.lastTry)}` : "; it is the last today"}.` : "";
  const sub = v === "bad" ? `${esc(d.reason || "The run failed. Open its log.")}${next ? ` ${next}` : " No scheduled tries left today."}`
    : v === "waiting" ? (next || "No scheduled tries left today.")
    : v === "missed" ? "Nothing ran or was posted that day."
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
          ${d.totalSeconds ? `<span class="stat-chip" title="Time the writing pipeline took; the run row below also counts setup">Pipeline <b>${dur(d.totalSeconds)}</b></span>` : ""}
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
    state.history = await load("history");
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
const PLAT = { instagram: "Instagram", x: "X", linkedin: "LinkedIn", instagram_reel: "Instagram Reel" };
const HOW = { api: ["Auto-post", "free Instagram API"], paid: ["Paid API", "about $0.20 a post"], manual: ["Manual", "copy and post by hand"] };

function itemStatus(i) {
  const s = state.decisions.get(i.id) || i.status;
  // nobody posts yesterday's news: an item still pending after its day is over is shown as expired, with no buttons
  if (s === "pending" && i.id.slice(0, 10) < (state.status?.today || todayIstClient())) return "expired";
  return s === "pending" && i.platform === "x" ? "off" : s;       // X posting is off: not something waiting on Pavan
}

/** A carousel item can only post if the deploy made slides for that day (the carousel was dropped on 1 Nov). */
const noSlides = (i) => i.platform === "instagram" && !(state.media.get(i.id.slice(0, 10))?.slides?.length);

/** What still needs Pavan: pending items that will really post through the app (X is off, LinkedIn is by hand). */
function needsYou(i) {
  return itemStatus(i) === "pending" && (i.platform === "instagram_reel" || (i.platform === "instagram" && !noSlides(i)));
}

function queueDay(d) {
  const items = d.items.filter((i) => !isReel(i));
  if (!items.length) return "";
  return `<section class="sday">
    <div class="sday-head"><div><span class="eyebrow">${esc(longDate(d.date))}</span><h2>${esc(plain(d.headline))}</h2></div>
      <a href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener noreferrer" class="btn ghost">Read the post ${svg("ext")}</a></div>
    <div class="queue">${items.map(itemCard).join("")}</div></section>`;
}
function itemText(i) { return state.edits.get(i.id) ?? i.edited_text ?? i.text; }
function xLen(t) { return t.replace(/https?:\/\/\S+/g, "x".repeat(23)).length; }

function itemCard(i) {
  const st = itemStatus(i), text = itemText(i), edited = text !== i.text;
  const [howTitle, howNote] = HOW[i.posting] || ["", ""];
  return `<article class="card item is-${esc(st)}" data-item="${esc(i.id)}">
    <div class="item-head"><span class="picon p-${esc(i.platform)}">${svg(i.platform)}</span><span class="plat">${esc(PLAT[i.platform])}</span>
      <span class="muted" style="font-size:12.5px">${esc(i.kind)}</span>${tag(st)}</div>
    <div class="how ${i.posting === "paid" ? "paid" : ""}" title="${esc(i.note)}"><span><b>${esc(howTitle)}</b> · ${esc(howNote)}</span></div>
    ${statusLine(i)}
    ${noSlides(i) && st === "pending" ? `<p class="stline muted">No carousel was made for this day, so there is nothing to post.</p>` : ""}
    ${i.posting === "paid" && st === "pending" ? `<p class="stline muted">X posting is off (paid API): copy the text if you post it yourself.</p>` : ""}
    ${(() => {
      // the day's real carousel when the share page has one, else the single card from the queue
      const slides = i.platform === "instagram" ? state.media.get(i.id.slice(0, 10))?.slides : null;
      const src = slides?.length ? slides[0] : i.media?.[0];
      return src ? `<div class="shot"><img src="${esc(safeUrl(src))}" alt="Instagram ${slides?.length ? "carousel cover" : "card"} for ${esc(i.id.slice(0, 10))}" loading="lazy" width="1080" height="1350">
        ${slides?.length ? `<span class="shot-tag">Carousel · ${slides.length} slides</span>` : ""}</div>` : "";
    })()}
    <div class="preview ${edited ? "edited" : ""}" data-preview>${esc(text)}</div>
    ${i.platform === "x" ? `<div class="counter ${xLen(text) > 280 ? "over" : ""}">${xLen(text)} / 280</div>` : ""}
    ${(() => {
      // only what can really happen gets a button: X is off, a carousel needs slides, past days are over
      const at = state.schedules.has(i.id) ? state.schedules.get(i.id) : i.scheduled_at;
      const carouselOk = i.platform === "instagram" && !noSlides(i);
      const approvable = i.platform !== "x" && (i.platform !== "instagram" || carouselOk)
        && (["pending", "failed"].includes(st) || (st === "skipped" && carouselOk));
      const sched = st === "pending" && carouselOk
        ? `<div class="sched">${svg("calendar")}<span>${at ? `Posts ${esc(whenText(at))}` : "Not scheduled: posts when approved"}</span>
          <button class="linkbtn" data-act="schedule">${at ? "Change" : "Schedule"}</button></div>` : "";
      const copy = ["x", "linkedin"].includes(i.platform) && st !== "expired"
        ? `<button class="btn ghost" data-act="copy" aria-label="Copy ${esc(PLAT[i.platform])} text">${svg("copy")}Copy</button>` : "";
      const buttons = approvable
        ? `<button class="btn ok" data-act="approve">${st === "failed" ? "Approve again" : st === "skipped" ? "Post it anyway" : "Approve"}</button>
           ${st === "pending" ? `<button class="btn" data-act="edit">Edit</button><button class="btn ghost" data-act="skip">Skip</button>` : ""}` : "";
      return sched + (buttons || copy ? `<div class="actions">${buttons}${copy}</div>` : "");
    })()}
  </article>`;
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
    try { await navigator.clipboard.writeText(itemText(item)); toast(`${esc(PLAT[item.platform])} text copied.`); } catch { toast("Copy failed: select the text by hand.", "err"); }
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
  if (act === "schedule") {
    const box = el.querySelector(".sched");
    const at = state.schedules.has(item.id) ? state.schedules.get(item.id) : item.scheduled_at;
    const local = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60e3).toISOString().slice(0, 16);
    const def = at ? new Date(at) : new Date(Date.now() + 3600e3);
    box.innerHTML = `${svg("calendar")}<input type="datetime-local" aria-label="Post at" value="${local(def)}" min="${local(new Date())}" max="${local(new Date(Date.now() + 14 * 864e5))}">
      <button class="linkbtn" data-act="schedule-save">Set</button>${at ? `<button class="linkbtn" data-act="schedule-clear">Clear</button>` : ""}`;
    box.querySelector("input").focus();
    return;
  }
  if (act === "schedule-save" || act === "schedule-clear") {
    const input = el.querySelector(".sched input");
    const at = act === "schedule-clear" ? null : new Date(input.value).toISOString();
    try {
      const r = await api("social/schedule", { method: "POST", body: { item_id: item.id, at } });
      if (!r.dryRun) state.schedules.set(item.id, at);     // a dry run changes nothing, on GitHub or on screen
      el.outerHTML = cardFor(item);
    wireLazyVideos();
      const said = at ? `${PLAT[item.platform]} set to post ${whenText(at)} IST` : `${PLAT[item.platform]} unscheduled`;
      toast(r.dryRun ? `<b>Dry run.</b> ${esc(said)}: not saved.` : `${esc(said)}.`, r.dryRun ? "dry" : "");
    } catch (err) {
      toast(`<b>Failed.</b> ${esc(err.message)}`, "err");
    }
    return;
  }
  if (act === "save") {
    const ta = el.querySelector("textarea");
    const v = ta.value.trim();
    if (!v) return toast("Text can't be empty.", "err");
    if (v === item.text) state.edits.delete(item.id); else state.edits.set(item.id, v);
    el.outerHTML = cardFor(item);
    toast("Edit kept here: it goes out with this post when you approve it.");
    wireLazyVideos();
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
     ${act === "approve" && slotOf(item) ? `<p>${esc(slotText(item))}.</p>` : ""}
     <p class="muted">${state.status?.dryRun ? "Dry run: the dashboard only shows the request it would send." : "Live: the workflow runs now."}
     ${item.posting === "paid" && act === "approve" ? " X posting costs about $0.20 once it is live." : ""}</p>`,
    act === "approve" ? "Approve" : "Skip");
  if (!ok) return;
  try {
    const r = await api("social/action", { method: "POST", body: { item_id: item.id, action: act, ...(edited ? { text } : {}) } });
    state.lastResult = r;
    if (!r.dryRun) state.decisions.set(item.id, act === "approve" ? "approved" : "skipped");
    el.outerHTML = cardFor(item);
    wireLazyVideos();
    renderCounts();
    toast(r.dryRun ? `<b>Dry run.</b> Would dispatch publish-social.yml for ${esc(item.id)}.` : `Started publish-social for ${esc(item.id)}.`, r.dryRun ? "dry" : "");
  } catch (err) {
    toast(`<b>Failed.</b> ${esc(err.message)}`, "err");
  }
}

// ---------- story Reels: the day's set, previewed and approved together ----------
const isReel = (i) => i.platform === "instagram_reel";
const cardFor = (i) => (isReel(i) ? reelCard(i) : itemCard(i));
const slotOf = (i) => (state.schedules.has(i.id) ? state.schedules.get(i.id) : i.scheduled_at);

/** What happened to an item that is no longer pending: the live link and time, the failure, or the plan. */
function statusLine(i) {
  const st = itemStatus(i), at = slotOf(i);
  if (st === "posted") {
    return `<p class="stline ok">${i.posted_url ? `<a href="${esc(safeUrl(i.posted_url))}" target="_blank" rel="noopener noreferrer">View on Instagram ${svg("ext")}</a>` : "Posted"}
      ${i.decided_at ? `<span>Posted ${esc(whenText(i.decided_at))} IST</span>` : ""}</p>`;
  }
  if (st === "failed") return `<p class="stline bad">${svg("warn")}<span>Not posted: ${esc(i.error || "the workflow recorded a failure")}. Approve again to retry.</span></p>`;
  if (st === "approved") {
    if (i.platform === "linkedin") return `<p class="stline">Approved: copy the text and post it on LinkedIn by hand.</p>`;
    return `<p class="stline">${at && Date.parse(at) > Date.now() ? `Approved: posts ${esc(whenText(at))} IST` : "Approved: posting now"}</p>`;
  }
  if (st === "skipped") {
    return i.platform === "instagram" && !noSlides(i)
      ? `<p class="stline muted">Skipped by default (the daily Reels replace the carousel). "Post it anyway" posts it now.</p>`
      : `<p class="stline muted">Skipped: will not be posted.</p>`;
  }
  return "";
}

function slotText(i) {
  const st = itemStatus(i), at = slotOf(i);
  if (!at) return "No time set: posts when approved";
  const when = `${time(at)} IST`;
  if (st !== "pending") return `Slot ${when}`;
  return Date.parse(at) <= Date.now() ? `${when} has passed: approving posts it right away` : `Posts at ${when}, once approved`;
}

function reelCard(i) {
  const st = itemStatus(i), n = i.id.split("-reel-")[1];
  const url = i.media?.[0] || "";
  // the share page keeps only recent Reels: if it no longer lists this one, show a tile instead of a broken player
  const listed = state.media.get(i.id.slice(0, 10))?.reels;
  const gone = Array.isArray(listed) && !listed.includes(url);
  const slot = slotOf(i);
  const notYet = st === "approved" && slot && Date.parse(slot) > Date.now();        // approved, still waiting for its time
  const video = gone
    ? `<div class="reel-gone"><span>Video no longer on the site</span>${i.posted_url ? `<a href="${esc(safeUrl(i.posted_url))}" target="_blank" rel="noopener noreferrer">Watch on Instagram ${svg("ext")}</a>` : ""}</div>`
    : `<video data-src="${esc(safeUrl(url))}#t=0.1" data-posted="${esc(i.posted_url || "")}" controls preload="none" playsinline aria-label="Reel ${esc(n)}"></video>`;
  return `<article class="card reelcard is-${esc(st)}" data-item="${esc(i.id)}">
    <div class="reel-video">${video}</div>
    <div class="reel-body">
      <div class="item-head"><span class="rnum">Reel ${esc(n)}</span>${tag(st)}</div>
      <p class="rhook">${esc(plain(i.hook || ""))}</p>
      <div class="sched">${svg("calendar")}<span>${esc(slotText(i))}</span>
        ${st === "pending" || notYet ? `<button class="linkbtn" data-act="schedule">Change time</button>` : ""}</div>
      ${statusLine(i)}
      <details class="cap"><summary>Caption</summary><div class="preview">${esc(itemText(i))}</div></details>
      ${["pending", "failed"].includes(st) ? `<div class="actions"><button class="btn ok" data-act="approve">${st === "failed" ? "Approve again" : "Approve"}</button><button class="btn ghost" data-act="skip">Skip</button></div>`
        : notYet ? `<div class="actions"><button class="btn ghost" data-act="skip">Skip, don't post</button></div>` : ""}
    </div></article>`;
}

/** Pavan's rule: before anything posts he sees what is NOT in the package too. */
function notIncluded(day) {
  const by = (p) => day.items.find((i) => i.platform === p);
  const word = { pending: "waiting for approval below", approved: "approved separately", posted: "posted separately", skipped: "skipped", failed: "failed, see below" };
  const parts = [];
  const car = by("instagram");
  // a carousel that was posted (or decided) counts even if the share page no longer lists its slides
  const carouselReal = car && (!noSlides(car) || ["posted", "approved", "failed"].includes(itemStatus(car)));
  parts.push(carouselReal ? `the carousel (${word[itemStatus(car)] || itemStatus(car)})` : "no carousel today");
  if (state.media.get(day.date)?.reel) parts.push("the music Reel (not posted automatically)");
  if (by("x")) parts.push("X (paid API, off)");
  if (by("linkedin")) parts.push("LinkedIn (copy and post by hand)");
  return parts.join(", ");
}

function reelsSection(day) {
  const reels = day.items.filter(isReel);
  if (!reels.length) return "";
  const count = (s) => reels.filter((r) => itemStatus(r) === s).length;
  const pend = count("pending");
  const isToday = day.date === state.status?.today;
  const summary = [pend && `${pend} waiting for you`, count("approved") && `${count("approved")} approved`, count("posted") && `${count("posted")} posted`,
                   count("failed") && `${count("failed")} failed`, count("skipped") && `${count("skipped")} skipped`].filter(Boolean).join(" · ");
  return `<section class="card reels-card" data-reel-day="${esc(day.date)}">
    <div class="card-head"><div><h3>Story Reels · ${esc(shortDate(day.date))}</h3><p class="muted small">${reels.length} Reels, one per story · ${esc(summary)}</p></div>
      ${pend ? `<button class="btn primary" data-approve-reels="${esc(day.date)}">${isToday ? "Approve today's Reels" : "Approve these Reels"} (${pend})</button>` : ""}</div>
    <p class="not-incl">${svg("warn")}<span><b>Not in this set:</b> ${esc(notIncluded(day))}.</span></p>
    <div class="reel-grid">${reels.map(reelCard).join("")}</div>
  </section>`;
}

async function onApproveReels(btn) {
  const date = btn.dataset.approveReels;
  const day = state.social.days.find((d) => d.date === date);
  const pend = day.items.filter((i) => isReel(i) && itemStatus(i) === "pending");
  const line = (i) => {
    const at = slotOf(i);
    const when = !at ? "posts now" : Date.parse(at) <= Date.now() ? `posts now (${time(at)} IST has passed)` : `posts at ${time(at)} IST`;
    return `<li><b>Reel ${esc(i.id.split("-reel-")[1])}</b> · ${esc(when)}<br><span class="muted">${esc(plain(i.hook || ""))}</span></li>`;
  };
  const ok = await confirmDialog(`Approve ${pend.length} Reel${pend.length > 1 ? "s" : ""}?`,
    `<ul class="dlg-list">${pend.map(line).join("")}</ul>
     <p><b>Not in this set:</b> ${esc(notIncluded(day))}.</p>
     <p class="muted">${state.status?.dryRun ? "Dry run: you will see the requests, nothing is sent." : "Live: each Reel is approved now and posts at its time."}</p>`, "Approve all");
  if (!ok) return;
  btn.disabled = true;
  try {
    const r = await api("social/approve-reels", { method: "POST", body: { date } });
    state.lastResult = r;
    if (!r.dryRun) for (const id of r.items) state.decisions.set(id, "approved");
    view.querySelector(`[data-reel-day="${date}"]`).outerHTML = reelsSection(day);
    wireLazyVideos();
    renderCounts();
    toast(r.dryRun ? `<b>Dry run.</b> ${esc(r.what)}: would dispatch publish-social ${r.items.length} times.` : `${esc(r.what)}: started.`, r.dryRun ? "dry" : "");
  } catch (err) {
    toast(`<b>Failed.</b> ${esc(err.message)}`, "err");
    btn.disabled = false;
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
const notFuture = (d) => d <= (state.status?.today || todayIstClient());

function followerSeries(st, key) {
  if (key === "instagram") return st.days.map((d) => ({ date: d.date, value: d.instagram?.followers })).filter((p) => p.value != null);
  if (key === "website") return (st.days.at(-1)?.website?.daily || []).filter((d) => notFuture(d.day)).map((d) => ({ date: d.day, value: d.visitors }));
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
  const label = p.key === "website" ? "visitors, last 28 days" : value === 1 ? "follower" : "followers";
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
    state.stats = await load("stats");
  } catch (err) {
    view.innerHTML = problem(err, "stats");
    return;
  }
  const st = state.stats, latest = st.days.at(-1) || {};
  const web = latest.website?.status === "ok" ? latest.website : null;
  const ig = latest.instagram?.status === "ok" ? latest.instagram : null;
  view.innerHTML = `
    <div class="section-title" style="margin-top:0"><h1 style="font-size:clamp(26px,3.6vw,36px)">Stats</h1>
      <span class="muted">${latest.collected_at ? `Updated ${esc(whenText(latest.collected_at))} IST · collected daily at 23:30` : "Collected daily at 23:30 IST once the secrets are set"}</span></div>
    <div class="ptiles">${PLATFORMS.map((p) => platformTile(st, p)).join("")}</div>
    <div class="stages align-top">
      <section class="card two-thirds"><div class="card-head"><h3>Website visitors per day</h3><span class="muted" style="font-size:13px">GoatCounter</span></div>
        ${web ? visitsChart(web.daily.filter((d) => notFuture(d.day))) : `<p class="empty">Connect GoatCounter to see daily visits.</p>`}</section>
      <section class="card third"><div class="card-head"><h3>Where readers came from</h3><span class="muted" style="font-size:13px">7 days</span></div>
        ${web?.top_refs?.length ? barList(web.top_refs, (r) => r.name, (r) => r.visitors) : `<p class="empty">No referrers yet.</p>`}</section>
      <section class="card"><div class="card-head"><h3>Most-read pages</h3><span class="muted" style="font-size:13px">7 days</span></div>
        ${web?.top_paths?.length ? barList(web.top_paths, (r) => (web.top_paths.filter((x) => x.title === r.title).length > 1 || !r.title ? `${r.title || ""} ${r.path}`.trim() : r.title), (r) => r.visitors, "stacked") : `<p class="empty">No page numbers yet.</p>`}</section>
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

// ---------- shared helpers for the desktop screens ----------
function whenText(iso) {
  return new Date(iso).toLocaleString("en-GB", { ...IST, weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}
function ago(iso) {
  const s = (Date.now() - Date.parse(iso)) / 1000;
  if (!Number.isFinite(s)) return "";
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString("en-GB", { ...IST, day: "numeric", month: "short" });
}
async function copyText(text, label = "Copied.") {
  try { await navigator.clipboard.writeText(text); toast(esc(label)); } catch { toast("Copy failed: select the text by hand.", "err"); }
}
const pageHead = (title, right = "") => `<div class="section-title" style="margin-top:0"><h1 class="page-h">${esc(title)}</h1>${right}</div>`;

// ---------- posts: media, social queue, blog posts ----------
async function renderPosts() {
  try {
    [state.social, state.history] = await Promise.all([load("social"), load("history")]);
  } catch (err) {
    view.innerHTML = problem(err, "posts");
    return;
  }
  renderCounts();
  const posts = state.history.days.filter((d) => d.post);
  const newest = posts[0]?.date;
  const days = state.social.days;
  // each shown day's share page: carousel slides (if any were made), the music Reel; for "not in this set"
  const mediaDays = [...new Set([newest, ...days.slice(0, 2).map((d) => d.date)].filter(Boolean))];
  await Promise.all(mediaDays.map((d) => load(`media?date=${d}`).catch(() => null)));
  const media = newest ? state.media.get(newest) : null;
  view.innerHTML = `
    ${pageHead("Posts", `<span class="muted">${state.status?.dryRun ? "Dry run: approving and scheduling only show what would happen" : "Live"}</span>`)}
    ${days.slice(0, 2).map(reelsSection).join("")}
    <section class="card media-card">
      <div class="card-head"><h3>Instagram media${newest ? ` · ${esc(shortDate(newest))}` : ""}</h3>
        ${media?.page ? `<span class="head-links"><a href="${esc(safeUrl(media.page))}" target="_blank" rel="noopener noreferrer">Share kit ${svg("ext")}</a>${media.zip ? `<a href="${esc(safeUrl(media.zip))}">Slides (zip)</a>` : ""}</span>` : ""}</div>
      ${media && (media.slides.length || media.reel) ? `<div class="media">
        ${media.slides.length ? `<div class="slides" role="list" aria-label="Carousel, ${media.slides.length} slides">${media.slides.map((u, n) =>
          `<a role="listitem" href="${esc(safeUrl(u))}" target="_blank" rel="noopener noreferrer" class="slide"><img src="${esc(safeUrl(u))}" alt="Slide ${n + 1}" loading="lazy" width="1080" height="1350"><span>${n + 1}</span></a>`).join("")}</div>` : ""}
        ${media.reel ? `<figure class="reel"><video src="${esc(safeUrl(media.reel))}" controls preload="metadata" playsinline ${media.slides[0] ? `poster="${esc(safeUrl(media.slides[0]))}"` : ""}></video><figcaption>Reel · original music</figcaption></figure>` : ""}
      </div><p class="note">Made by the blog pipeline on every deploy, for the newest post. The daily Story Reels are what posts; the carousel only goes out if you choose "Post it anyway" below.</p>`
      : `<p class="empty">${newest ? "No carousel or Reel on the share page yet: the deploy makes them for the newest post." : "No posts yet."}</p>`}
    </section>
    <div class="section-title"><h2>Social queue</h2><span class="muted">Approve, edit, skip or schedule each post</span></div>
    ${days.length ? days.slice(0, 2).map(queueDay).join("") + (days.length > 2 ? `<details class="more older"><summary>Earlier days (${days.length - 2})</summary>
      <div>${days.slice(2).map(queueDay).join("")}</div></details>` : "")
      : `<div class="banner">${svg("warn")}<div><h2>Nothing in the queue</h2><p>The daily run writes <code>data/social/&lt;date&gt;.json</code> next to each new post.</p></div></div>`}
    <div class="section-title"><h2>Blog posts</h2><span class="muted">${posts.length} in the last three weeks</span></div>
    <section class="card"><ul class="postlist">${posts.map((d) => `<li>
      <span class="pdate">${esc(shortDate(d.date))}</span>
      <a class="ptitle" href="${SITE}posts/${esc(encodeURIComponent(d.slug))}/" target="_blank" rel="noopener noreferrer">${esc(plain(d.title))}</a>
      <span class="plinks"><a href="#today/${esc(d.date)}">Pipeline</a><a href="${SITE}share/${esc(d.date)}/" target="_blank" rel="noopener noreferrer">Share kit</a></span></li>`).join("")
      || `<li class="empty">No posts yet.</li>`}</ul></section>`;
  view.querySelectorAll(".shot img, .slide img").forEach((img) => img.addEventListener("error", () => {
    img.closest(".shot, .slide").classList.add("missing-img");
  }, { once: true }));
}

// ---------- mail ----------
async function renderMail(refresh = false) {
  if (refresh) view.querySelector("[data-mail-refresh]")?.setAttribute("disabled", "");
  try {
    state.mail = refresh ? await api("local/mail?refresh=1") : await load("local/mail");
    if (refresh) DATA.set("local/mail", { at: Date.now(), value: state.mail });
  } catch (err) {
    view.innerHTML = pageHead("Mail") + problem(err, "mail");
    return;
  }
  const m = state.mail;
  renderCounts();
  if (!m.connected) {
    // Checked 1 Nov 2026: Zoho's free plan shows IMAP as "not available for your account" (POP and forwarding are
    // paid too), so the inbox can't be read from here until the plan changes. hello@ is an alias of pavan@.
    view.innerHTML = `${pageHead("Mail")}
      <section class="card setup-card"><div class="card-head"><h3>pavan@fiveminuteai.net</h3><span class="status-tag t-skipped">Opens in Zoho</span></div>
        <p class="note" style="margin:0 0 var(--s4)">Mail sent to hello@ lands in the pavan@ inbox. Zoho's free plan doesn't allow other apps to read mail (IMAP, POP and forwarding are paid features), so this screen opens Zoho Mail instead.</p>
        <div class="actions"><a class="btn primary" href="${esc(safeUrl(m.web))}" target="_blank" rel="noopener noreferrer">Open Zoho Mail ${svg("ext")}</a></div>
        <details class="more"><summary>If you move to a paid Zoho plan</summary><div>
        <ol class="steps">
          <li>Zoho Mail → Settings → <b>Mail Accounts</b> → <b>IMAP</b>: turn IMAP access on.</li>
          <li>Your profile → <b>My Account</b> → <b>Security</b> → <b>App Passwords</b>: create one named "Five Minute AI app".</li>
          <li>In PowerShell, run this. It asks for the password; paste the app password (nothing shows on screen):
            <div class="cmd"><code>${esc(m.add)}</code><button class="btn ghost" data-copy="${esc(m.add)}" data-copy-label="Command copied.">${svg("copy")}Copy</button></div></li>
          <li>Press <b>Check again</b>: the inbox shows here, read-only (nothing is sent, deleted or marked as read).</li>
        </ol>
        <div class="actions"><button class="btn" data-mail-refresh>Check again</button></div></div></details>
      </section>`;
    return;
  }
  view.innerHTML = `${pageHead("Mail", `<span class="muted">${esc(m.account)} · checked ${esc(ago(m.fetched))}</span>`)}
    <div class="mail-bar">
      <div class="big"><div><b>${num(m.unread)}</b><span>unread</span></div><div><b>${num(m.total)}</b><span>in ${esc(m.folder.toLowerCase())}</span></div></div>
      <div class="actions"><button class="btn" data-mail-refresh>Refresh</button>
        <a class="btn primary" href="${esc(safeUrl(m.web))}" target="_blank" rel="noopener noreferrer">Open Zoho Mail ${svg("ext")}</a></div>
    </div>
    <section class="card mail-list">${m.messages.length ? `<ul>${m.messages.map((x) => `<li class="${x.unread ? "unread" : ""}">
      <span class="mdot" aria-label="${x.unread ? "Unread" : "Read"}"></span>
      <span class="mfrom" title="${esc(x.from.email)}">${esc(x.from.name || x.from.email || "(unknown)")}</span>
      <span class="msubj">${x.flagged ? `<b class="flag" aria-label="Flagged">★</b>` : ""}${esc(x.subject)}</span>
      <time datetime="${esc(x.date || "")}">${x.date ? esc(ago(x.date)) : ""}</time></li>`).join("")}</ul>`
      : `<p class="empty">The inbox is empty.</p>`}</section>
    <p class="note">Read-only: open Zoho Mail to reply. The newest ${m.messages.length} messages are shown; nothing is downloaded beyond sender, subject and date.</p>`;
}

// ---------- accounts and passwords ----------
async function renderAccounts() {
  try {
    state.accounts = await load("local/accounts");
  } catch (err) {
    view.innerHTML = pageHead("Accounts") + problem(err, "accounts");
    return;
  }
  const { accounts, vault } = state.accounts;
  const icon = (k) => ({ web: "deploy", github: "github", mail: "mail", chart: "chart", lock: "lock", write: "write" }[k] || k);
  view.innerHTML = `${pageHead("Accounts", `<span class="muted">${accounts.length} accounts · passwords stay in Bitwarden</span>`)}
    <div class="acct-grid">${accounts.map((a) => `<section class="card acct" data-acct="${esc(a.id)}">
      <div class="acct-head"><span class="picon p-${esc(["instagram", "x", "linkedin"].includes(a.id) ? a.id : "web")}">${svg(icon(a.icon))}</span>
        <div><h3>${esc(a.name)}</h3><p class="handle">${esc(a.handle)}</p></div>
        <span class="status-tag ${a.status === "live" ? "t-ok" : "t-pending"}">${a.status === "live" ? "Live" : "Planned"}</span></div>
      ${a.todo ? `<p class="todo">${svg("warn")}<span>${esc(a.todo)}</span></p>` : ""}
      ${a.renews ? `<p class="muted small">Renew by ${esc(new Date(`${a.renews}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }))}</p>` : ""}
      <div class="links">${a.links.map(([label, url]) => `<a href="${esc(safeUrl(url))}" target="_blank" rel="noopener noreferrer">${esc(label)} ${svg("ext")}</a>`).join("")}</div>
      ${a.vault ? `<div class="vault">${svg("lock")}<span class="vault-txt">Bitwarden item <b>${esc(a.vault)}</b></span>
        <span class="vault-btns"><button class="linkbtn" data-copy="${esc(a.vault)}" data-copy-label="Item name copied: paste it into Bitwarden's search.">Copy name</button>
        <a class="linkbtn" href="${esc(safeUrl(vault))}" target="_blank" rel="noopener noreferrer">Open vault</a></span></div>` : ""}
      <label class="notes"><span>Notes (this computer only; no passwords)</span>
        <textarea data-note="${esc(a.id)}" rows="2" maxlength="4000" placeholder="2FA method, recovery steps, who has access…">${esc(a.notes)}</textarea></label>
    </section>`).join("")}</div>`;
}

view.addEventListener("change", async (e) => {
  const ta = e.target.closest("textarea[data-note]");
  if (!ta) return;
  // same rule as the server (desktop/local-api.mjs), checked here first so the refusal is instant
  if (/(password|passwd|pwd|secret|token|api[ _-]?key)\s*[:=]\s*\S{6,}/i.test(ta.value)) {
    ta.classList.add("refused");
    toast("<b>Not saved.</b> That looks like a password or key. Keep those in Bitwarden, not in notes.", "err");
    return;
  }
  try {
    await api("local/accounts/notes", { method: "POST", body: { id: ta.dataset.note, notes: ta.value } });
    const a = state.accounts?.accounts.find((x) => x.id === ta.dataset.note);
    if (a) a.notes = ta.value.trim();
    ta.classList.remove("refused");
    toast("Note saved on this computer.");
  } catch (err) {
    ta.classList.add("refused");
    toast(`<b>Not saved.</b> ${esc(err.message)}`, "err");
  }
});

// ---------- pages: the faceless Instagram pages and their shared income (read-only, from faceless-ig) ----------
const PAGE_STATUS = { live: ["t-ok", "Live"], building: ["t-pending", "Building"], planned: ["t-skipped", "Planned"], paused: ["t-waiting", "Paused"] };
const rupees = (n) => (n == null ? "–" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`);
const per100 = (n) => (n == null ? "–" : Number(n).toFixed(2));
const monthName = (m) => (/^\d{4}-\d\d$/.test(m) ? new Date(`${m}-15T12:00:00Z`).toLocaleDateString("en-GB", { month: "short", year: "numeric" }) : m);

function pageCard(a) {
  const [cls, word] = PAGE_STATUS[a.status] || ["t-unknown", a.status];
  // the first page in accounts.yaml uses the plain names on GitHub (post.yml passes them); the rest add __<ID>
  const sfx = a.first ? "" : `__${a.id.toUpperCase().replace(/[^A-Z0-9]/g, "_")}`;
  const names = `<code>IG_USER_ID${esc(sfx)}</code> and <code>IG_ACCESS_TOKEN${esc(sfx)}</code>`;
  const at = a.secretsWhere;
  const where = at ? [at.github && "on GitHub", at.local && "on this PC"].filter(Boolean).join(" and ") : "";
  const why = !at ? "" : at.github == null ? " (GitHub not checked: this pipeline has no GitHub repository yet)" : " on GitHub";
  const secrets = a.secretsSet ? `<p class="pg-line">${svg("lock")}<span>Instagram secrets set${where ? ` ${where}` : ""}</span></p>`
    : `<p class="todo">${svg("warn")}<span>${a.secretsSet == null ? "Secrets unknown" : `Secrets not set${why}`}: add ${names} as GitHub Actions secrets</span></p>`;
  const q = a.queue, w = a.week;
  const qcCls = a.qc.built && a.qc.passed === a.qc.built ? "b-ok" : a.qc.built ? "b-warn" : "";
  const next = q.next ? `${esc(q.next.slug || "untitled")}${q.next.kind ? ` <span class="muted">· ${esc(q.next.kind)}</span>` : ""}${q.next.at ? ` <span class="muted">· ${esc(whenText(q.next.at))}</span>` : ""}`
    : `<span class="faint">Nothing queued</span>`;
  const last = a.posted.last;
  const lastHtml = !last ? `<span class="faint">Not posted yet</span>`
    : `${last.permalink ? `<a href="${esc(last.permalink)}" target="_blank" rel="noopener noreferrer">${esc(last.slug || "Open post")} ${svg("ext")}</a>` : esc(last.slug || "–")}${last.at ? ` <span class="muted">· ${esc(ago(last.at))}</span>` : ""}`;
  return `<section class="card acct pg" data-page="${esc(a.id)}">
    <div class="acct-head"><span class="picon p-instagram">${svg("instagram")}</span>
      <div><h3>${esc(a.handle || a.id)}</h3><p class="handle">${esc(a.niche || "")}</p></div>
      <span class="status-tag ${cls}">${esc(word)}</span></div>
    ${secrets}
    <div class="big pg-big">
      <div><b>${num(q.waiting)}</b><span>Waiting approval</span></div>
      <div><b>${num(q.approved)}</b><span>Approved</span></div>
      <div><b>${num(a.posted.count)}</b><span>Posted</span></div>
      <div class="${qcCls}"><b>${num(a.qc.passed)}<small>/${num(a.qc.built)}</small></b><span>QC passed</span></div>
    </div>
    <dl class="kv"><dt>Next post</dt><dd>${next}</dd><dt>Last post</dt><dd>${lastHtml}</dd></dl>
    <div class="pg-week"><p class="eyebrow">Last 7 days${w.posts != null ? ` · ${num(w.posts)} post${w.posts === 1 ? "" : "s"}` : ""}</p>
      <div class="big"><div><b>${num(w.reach)}</b><span>Reach</span></div>
        <div><b>${per100(w.sendsPer100)}</b><span>Sends per 100</span></div>
        <div><b>${per100(w.savesPer100)}</b><span>Saves per 100</span></div></div></div>
  </section>`;
}

function incomeCard(inc, accounts) {
  const handle = Object.fromEntries(accounts.map((a) => [a.id, a.handle || a.id]));
  const list = (rows, label, empty) => {
    const max = Math.max(1, ...rows.map((r) => r[1]));
    return `<div class="pg-inc"><p class="eyebrow">${label}</p>${rows.length
      ? `<div class="bars">${rows.map(([k, v]) => `<div class="bar"><span class="name" title="${esc(k)}">${esc(k)}</span>
          <span class="track"><i style="width:${Math.max(2, (v / max) * 100)}%"></i></span><span class="n">${esc(rupees(v))}</span></div>`).join("")}</div>`
      : `<p class="empty small">${empty}</p>`}</div>`;
  };
  const last = inc.byMonth.at(-1);
  return `<section class="card pg-income"><div class="card-head"><h3>Income</h3><span class="muted small">All pages, one ledger</span></div>
    <div class="big"><div><b>${esc(rupees(inc.total))}</b><span>Total so far</span></div>
      ${last ? `<div><b>${esc(rupees(last[1]))}</b><span>${esc(monthName(last[0]))}</span></div>` : ""}</div>
    ${inc.byMonth.length || inc.byAccount.length || inc.bySource.length ? `<div class="pg-inc-grid">
      ${list(inc.byMonth.map(([k, v]) => [monthName(k), v]), "By month", "No months yet.")}
      ${list(inc.byAccount.map(([k, v]) => [handle[k] || k, v]), "By page", "Nothing per page yet.")}
      ${list(inc.bySource, "By source", "No sources yet.")}
    </div>` : ""}
    ${inc.total ? "" : `<p class="note">No income logged yet. Rows go in <code>faceless-ig/data/income.csv</code>; then run <code>python -m ig feed</code> there and reload.</p>`}
  </section>`;
}

async function renderPages() {
  try {
    state.pages = await load("local/pages");
  } catch (err) {
    view.innerHTML = pageHead("Pages") + problem(err, "the pages feed");
    return;
  }
  const r = state.pages;
  const refresh = `<button class="btn ghost" data-pages-refresh>Reload</button>`;
  const where = `<p class="note">Feed: <span class="mono">${esc(r.path)}</span>${r.modified ? ` · file saved ${esc(ago(r.modified))}` : ""}.
    Change it under <a href="#settings">Settings</a>.</p>`;
  if (!r.feed) {
    view.innerHTML = `${pageHead("Pages", refresh)}<div class="banner">${svg("warn")}<div><h2>${esc(r.message || "No pages feed")}</h2>
      <p>This screen reads the file the faceless Instagram pipeline writes. To make it:</p>
      <div class="cmd"><code>${esc(r.how)}</code><button class="btn ghost" data-copy="${esc(r.how)}" data-copy-label="Command copied.">${svg("copy")}Copy</button></div>
      ${where}</div></div>`;
    return;
  }
  const f = r.feed;
  const live = f.accounts.filter((a) => a.status === "live").length;
  view.innerHTML = `${pageHead("Pages", `<span class="pg-head-r"><span class="muted">${f.accounts.length} page${f.accounts.length === 1 ? "" : "s"} · ${live} live${f.generatedAt ? ` · feed built ${esc(ago(f.generatedAt))}` : ""}</span>${refresh}</span>`)}
    ${f.warnings.length ? `<div class="banner">${svg("warn")}<div><h2>Some of the feed could not be read</h2><ul class="pg-warn">${f.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div></div>` : ""}
    ${incomeCard(f.income, f.accounts)}
    <div class="section-title"><h2>Instagram pages</h2><span class="muted small">Read-only · approve and post from faceless-ig</span></div>
    ${f.accounts.length ? `<div class="acct-grid pg-grid">${f.accounts.map(pageCard).join("")}</div>` : `<p class="empty">The feed lists no pages. Add one to <code>accounts.yaml</code>.</p>`}
    ${where}`;
}

// ---------- roadmap ----------
const COLS = [["ideas", "Ideas"], ["next", "Next"], ["doing", "Doing"], ["done", "Done"]];

async function saveRoadmap(next, msg) {
  const prev = state.roadmap;
  state.roadmap = next;
  renderRoadmapBoard();
  try {
    state.roadmap = await api("local/roadmap", { method: "POST", body: next });
    if (msg) toast(esc(msg));
  } catch (err) {
    state.roadmap = prev;
    renderRoadmapBoard();
    toast(`<b>Not saved.</b> ${esc(err.message)}`, "err");
  }
}

async function renderRoadmap() {
  try {
    state.roadmap = state.roadmap || await load("local/roadmap");
  } catch (err) {
    view.innerHTML = pageHead("Roadmap") + problem(err, "the roadmap");
    return;
  }
  view.innerHTML = `${pageHead("Roadmap", `<span class="muted">Saved on this computer</span>`)}
    <form class="card addcard" id="card-form" autocomplete="off">
      <label class="grow"><span>New card</span><input name="title" maxlength="200" placeholder="What needs doing?" required></label>
      <label><span>Column</span><select name="column">${COLS.map(([k, l]) => `<option value="${k}" ${k === "next" ? "selected" : ""}>${l}</option>`).join("")}</select></label>
      <label><span>Tag</span><input name="tag" maxlength="30" placeholder="e.g. instagram"></label>
      <button class="btn primary" type="submit">Add</button>
    </form>
    <div class="board" id="board"></div>`;
  $("#card-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const title = String(f.get("title") || "").trim();
    if (!title) return;
    const now = new Date().toISOString();
    const card = { id: `c${Math.random().toString(36).slice(2, 10)}`, column: f.get("column"), title, note: "", tag: String(f.get("tag") || "").trim(), created: now, updated: now };
    e.target.reset();
    saveRoadmap({ ...state.roadmap, cards: [card, ...state.roadmap.cards] }, "Card added.");
  });
  renderRoadmapBoard();
}

function renderRoadmapBoard() {
  const board = $("#board");
  if (!board || !state.roadmap) return;
  const cards = state.roadmap.cards;
  board.innerHTML = COLS.map(([k, label], ci) => {
    const list = cards.filter((c) => c.column === k);
    return `<section class="col col-${k}" aria-label="${label}"><h3>${label} <span>${list.length}</span></h3>
      ${list.map((c) => `<article class="rcard" data-id="${esc(c.id)}">
        <p class="rtitle">${esc(c.title)}</p>${c.note ? `<p class="rnote">${esc(c.note)}</p>` : ""}
        <div class="rfoot">${c.tag ? `<span class="rtag">${esc(c.tag)}</span>` : "<span></span>"}
          <span class="rbtns">
            <button class="ib" data-card="left" data-id="${esc(c.id)}" ${ci === 0 ? "disabled" : ""} aria-label="${ci ? `Move to ${COLS[ci - 1][1]}` : "Already in the first column"}">${svg("left")}</button>
            <button class="ib" data-card="right" data-id="${esc(c.id)}" ${ci === COLS.length - 1 ? "disabled" : ""} aria-label="${COLS[ci + 1] ? `Move to ${COLS[ci + 1][1]}` : "Already in the last column"}">${svg("right")}</button>
            <button class="ib" data-card="edit" data-id="${esc(c.id)}" aria-label="Edit">${svg("write")}</button>
            <button class="ib danger" data-card="delete" data-id="${esc(c.id)}" aria-label="Delete">${svg("x")}</button></span></div>
      </article>`).join("") || `<p class="empty small">Nothing here.</p>`}</section>`;
  }).join("");
}

async function onCardAction(btn) {
  const cards = state.roadmap.cards;
  const c = cards.find((x) => x.id === btn.dataset.id);
  if (!c) return;
  const ci = COLS.findIndex(([k]) => k === c.column);
  const act = btn.dataset.card;
  if (act === "left" || act === "right") {
    const to = COLS[ci + (act === "left" ? -1 : 1)]?.[0];
    if (!to) return;
    return saveRoadmap({ ...state.roadmap, cards: cards.map((x) => (x.id === c.id ? { ...x, column: to } : x)) });
  }
  if (act === "delete") {
    if (!await confirmDialog("Delete this card?", `<p>${esc(c.title)}</p>`, "Delete", true)) return;
    return saveRoadmap({ ...state.roadmap, cards: cards.filter((x) => x.id !== c.id) }, "Card deleted.");
  }
  if (act === "edit") {
    const el = btn.closest(".rcard");
    el.innerHTML = `<label class="sr">Title</label><input class="rin" name="title" value="${esc(c.title)}" maxlength="200">
      <textarea class="rin" name="note" rows="3" maxlength="2000" placeholder="Notes">${esc(c.note)}</textarea>
      <input class="rin" name="tag" value="${esc(c.tag)}" maxlength="30" placeholder="Tag">
      <div class="rfoot"><span></span><span class="rbtns"><button class="linkbtn" data-card="cancel" data-id="${esc(c.id)}">Cancel</button>
        <button class="btn primary sm" data-card="save" data-id="${esc(c.id)}">Save</button></span></div>`;
    el.querySelector("input").focus();
    return;
  }
  if (act === "cancel") return renderRoadmapBoard();
  if (act === "save") {
    const el = btn.closest(".rcard");
    const v = (n) => el.querySelector(`[name="${n}"]`).value.trim();
    if (!v("title")) return toast("A card needs a title.", "err");
    return saveRoadmap({ ...state.roadmap, cards: cards.map((x) => (x.id === c.id ? { ...x, title: v("title"), note: v("note"), tag: v("tag") } : x)) }, "Card saved.");
  }
}

// ---------- settings ----------
async function renderSettings() {
  try {
    state.info = await load("local/info");
  } catch (err) {
    view.innerHTML = pageHead("Settings") + problem(err, "settings");
    return;
  }
  const i = state.info, s = state.status || {};
  view.innerHTML = `${pageHead("Settings")}
    <section class="card"><div class="card-head"><h3>Connections</h3><span class="muted small">Windows Credential Manager</span></div>
      <p class="note" style="margin:0 0 var(--s4)">Secrets are kept by Windows, not by this app: never in its files, logs or git. Each command asks for the secret itself.</p>
      <div class="creds">${i.credentials.map((c) => `<div class="cred">
        <div><b>${esc(c.label)}</b><span class="muted small">For ${esc(c.why)}</span></div>
        ${c.stored ? tag("ok") : `<span class="status-tag t-pending">Not stored</span>`}
        <div class="cmd"><code>${esc(c.stored ? c.remove : c.add)}</code><button class="btn ghost" data-copy="${esc(c.stored ? c.remove : c.add)}" data-copy-label="Command copied.">${svg("copy")}Copy</button></div>
      </div>`).join("")}</div>
      <p class="note">Without a stored GitHub token the app uses your GitHub CLI login (<code>gh auth login</code>). Restart the app after changing one.</p></section>
    <div class="stages align-top">
      <section class="card"><div class="card-head"><h3>Bitwarden</h3>${i.bitwarden.cli ? tag(i.bitwarden.status === "unlocked" ? "ok" : "pending") : `<span class="status-tag t-skipped">Web vault</span>`}</div>
        <p class="note" style="margin:0">${i.bitwarden.cli ? `Bitwarden CLI found, vault ${esc(i.bitwarden.status)}. The app never reads items from it.`
          : `Accounts link into your Bitwarden web vault; the app never sees a password. Optional: the Bitwarden CLI (<code>winget install Bitwarden.CLI</code>) lets this screen show whether the vault is locked.`}</p></section>
      <section class="card"><div class="card-head"><h3>Mail server</h3></div>
        <form class="mform" id="mail-settings"><label>IMAP host<input name="imapHost" value="${esc(i.settings.imapHost)}"></label>
          <label>Webmail link<input name="mailWeb" value="${esc(i.settings.mailWeb)}"></label>
          <button class="btn" type="submit">Save</button></form>
        <p class="note">India accounts use imap.zoho.in and mail.zoho.in; others imap.zoho.com and mail.zoho.com.</p></section>
      <section class="card"><div class="card-head"><h3>This app</h3></div>
        <dl class="kv"><dt>Writes</dt><dd>${s.dryRun ? "Dry run. For live, start <b>Five Minute AI (live)</b> from the Start menu." : "Live"}</dd>
          <dt>Data folder</dt><dd class="mono">${esc(i.dataDir)}</dd>
          <dt>Repository</dt><dd class="mono">${esc(s.repo || "")}</dd>
          <dt>GitHub</dt><dd>${s.configured ? "Connected" : "Not connected"}</dd></dl></section>
      <section class="card"><div class="card-head"><h3>Pages feed</h3></div>
        <form class="mform" id="pages-settings"><label class="span-all">Path to dashboard.json<input name="pagesFeed" class="mono" value="${esc(i.settings.pagesFeed || "")}" placeholder="Empty: faceless-ig next to this repository"></label>
          <button class="btn" type="submit">Save</button></form>
        <p class="note">Leave it empty for the default. Read-only: the app never writes to this file.</p></section>
    </div>`;
  $("#mail-settings").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    try {
      await api("local/settings", { method: "POST", body: { imapHost: f.get("imapHost").trim(), mailWeb: f.get("mailWeb").trim() } });
      state.mail = null;
      DATA.delete("local/mail");
      DATA.delete("local/info");
      toast("Mail settings saved.");
    } catch (err) {
      toast(`<b>Not saved.</b> ${esc(err.message)}`, "err");
    }
  });
  $("#pages-settings").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("local/settings", { method: "POST", body: { pagesFeed: String(new FormData(e.target).get("pagesFeed")).trim() } });
      state.pages = null;
      DATA.delete("local/pages");                // the next visit reads the new path, not the remembered feed
      DATA.delete("local/info");
      toast("Pages feed path saved.");
    } catch (err) {
      toast(`<b>Not saved.</b> ${esc(err.message)}`, "err");
    }
  });
}

// ---------- more (phone) ----------
function renderMore() {
  const items = [...document.querySelectorAll(".side-nav a")].filter((a) => !(a.hasAttribute("data-desk") && document.body.dataset.desktop !== "1"));
  view.innerHTML = `${pageHead("Everything")}<nav class="more-list">${items.map((a) => `<a href="${a.getAttribute("href")}">${a.querySelector("svg").outerHTML}<span>${esc([...a.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join("").trim())}</span>${svg("right")}</a>`).join("")}</nav>`;
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

/** Reel videos are heavy: each one starts loading only when it comes near the screen. */
let videoObserver = null;
function wireLazyVideos() {
  const vids = view.querySelectorAll("video[data-src]");
  if (!vids.length) return;
  videoObserver?.disconnect();
  const start = (v) => {
    const src = v.dataset.src;
    // a load error is usually a slow or dropped connection, not a missing file (the share-page listing catches
    // those before a player is drawn), so offer a retry instead of a broken player
    v.addEventListener("error", () => {
      const link = v.dataset.posted, box = v.parentElement;
      box.innerHTML = `<div class="reel-gone"><span>The video didn't load. The connection may be slow.</span>
        <button class="linkbtn" type="button">Try again</button>
        ${link ? `<a href="${esc(safeUrl(link))}" target="_blank" rel="noopener noreferrer">Watch on Instagram ${svg("ext")}</a>` : ""}</div>`;
      box.querySelector("button").addEventListener("click", () => {
        box.innerHTML = `<video controls playsinline aria-label="${esc(v.getAttribute("aria-label") || "Reel")}"></video>`;
        const again = box.querySelector("video");
        again.dataset.src = src; again.dataset.posted = link || "";
        start(again);
      }, { once: true });
    }, { once: true });
    v.src = src; v.preload = "metadata"; v.removeAttribute("data-src");
  };
  if (!("IntersectionObserver" in window)) { vids.forEach(start); return; }
  videoObserver = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { videoObserver.unobserve(e.target); start(e.target); }
  }, { rootMargin: "120px 0px" });
  vids.forEach((v) => videoObserver.observe(v));
}

// ---------- routing ----------
async function route({ keepScroll = false } = {}) {
  clearTimeout(timer);
  const myTurn = ++routeTurn;
  usedPaths = new Set();
  const scrollY = window.scrollY;
  const [tab = "today", arg] = location.hash.replace(/^#/, "").split("/");
  const desk = ["pages", "mail", "accounts", "roadmap", "settings"];
  const all = ["today", "history", "posts", "stats", "controls", "more", ...(state.status?.desktop ? desk : [])];
  const name = tab === "social" ? "posts" : all.includes(tab) ? tab : "today";
  document.querySelectorAll("[data-tab]").forEach((a) => {
    if (a.dataset.tab === name) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  document.title = `${name[0].toUpperCase()}${name.slice(1)} · Five Minute AI Control`;
  view.setAttribute("aria-busy", "true");
  document.body.classList.add("loading-data");
  // a screen that has to wait shows a quiet placeholder after 150 ms instead of leaving the old one frozen
  const slow = keepScroll ? null : setTimeout(() => {
    if (myTurn === routeTurn) view.innerHTML = `<div class="skeleton" aria-hidden="true"><i></i><i></i><i></i></div>`;
  }, 150);
  const date = /^\d{4}-\d\d-\d\d$/.test(arg || "") ? arg : null;
  if (name === "today") await renderToday(date);
  else if (name === "history") await renderHistory();
  else if (name === "posts") await renderPosts();
  else if (name === "stats") await renderStats();
  else if (name === "pages") await renderPages();
  else if (name === "mail") await renderMail();
  else if (name === "accounts") await renderAccounts();
  else if (name === "roadmap") await renderRoadmap();
  else if (name === "settings") await renderSettings();
  else if (name === "more") renderMore();
  else renderControls();
  clearTimeout(slow);
  if (myTurn !== routeTurn) return;             // the user moved on while this screen was loading
  view.setAttribute("aria-busy", "false");
  document.body.classList.remove("loading-data");
  if (keepScroll) window.scrollTo(0, scrollY);
  wireLazyVideos();
}
let routeTurn = 0;

view.addEventListener("click", (e) => {
  const t = e.target.closest("button, a");
  if (!t) return;
  if (t.dataset.jump) { document.getElementById(t.dataset.jump)?.scrollIntoView({ behavior: "smooth", block: "start" }); return; }
  if (t.dataset.approveReels) { onApproveReels(t); return; }
  if (t.dataset.act) { onItemAction(t); return; }
  if (t.dataset.control) { onControl(t); return; }
  if (t.dataset.card) { onCardAction(t); return; }
  if (t.dataset.copy != null) { copyText(t.dataset.copy, t.dataset.copyLabel || "Copied."); return; }
  if (t.dataset.mailRefresh != null) {
    renderMail(true).then(() => toast(state.mail?.connected ? `Mail checked: ${num(state.mail.unread)} unread.` : "Still not connected: Zoho's free plan has no IMAP."));
    return;
  }
  if (t.dataset.pagesRefresh != null) {
    state.pages = null;
    DATA.delete("local/pages");
    renderPages().then(() => toast("Pages feed reloaded."));
    return;
  }
  if (t.hasAttribute("data-retry")) {
    Object.assign(state, { history: null, social: null, stats: null, mail: null, accounts: null, roadmap: null, info: null, pages: null });
    DATA.clear();
    state.days.clear();
    route();
  }
});
let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (location.hash.startsWith("#stats") && state.stats) renderStats(); }, 250);
});
window.addEventListener("hashchange", () => { $("#tip").hidden = true; window.scrollTo(0, 0); route(); });

(async function start() {
  load(`day?date=${todayIstClient()}`).catch(() => {});      // the first screen's data, alongside the status call
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
  prefetch();
  if (state.status.desktop) {
    setInterval(() => fetch("/api/ping", { cache: "no-store" }).catch(() => {}), 60e3);   // keeps the desktop server running
  }
})();
