// The Pages screen's data: the faceless Instagram pages (faceless-ig) write one file, data/dashboard.json, covering
// every page in their accounts.yaml plus the shared income ledger. This module reads it from disk and turns it into
// something the page can render without guessing. Read-only: nothing here writes to faceless-ig.
//
// Schema v1 is documented at the top of faceless-ig/ig/feed.py. Anything missing or malformed becomes null (shown as
// "–") plus a warning, so one bad field never blanks the whole screen.

import { readFile, stat } from "node:fs/promises";
import { dirname, isAbsolute, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

// ai-daily and faceless-ig sit side by side in Projects/AI; Settings can point somewhere else.
export const DEFAULT_FEED = normalize(join(fileURLToPath(new URL("../../../", import.meta.url)), "faceless-ig", "data", "dashboard.json"));
export const FEED_VERSION = 1;

const STATUSES = new Set(["live", "building", "planned", "paused"]);

const int = (v) => (Number.isInteger(v) && v >= 0 ? v : null);
const amount = (v) => (typeof v === "number" && Number.isFinite(v) ? Math.round(v * 100) / 100 : null);
const ratio = (v) => (typeof v === "number" && Number.isFinite(v) && v >= 0 ? Math.round(v * 100) / 100 : null);
const text = (v, max = 300) => (typeof v === "string" ? v.slice(0, max) : null);
const isoish = (v) => (typeof v === "string" && Number.isFinite(Date.parse(v)) ? v : null);
const httpsUrl = (v) => (typeof v === "string" && /^https:\/\/[^\s"'<>]+$/.test(v) ? v : null);
const obj = (v) => (v && typeof v === "object" && !Array.isArray(v) ? v : {});

/** {key: number} -> [[key, amount]] sorted by key, dropping non-numbers. */
function money(map, warn, where) {
  const out = [];
  for (const [k, v] of Object.entries(obj(map))) {
    const a = amount(v);
    if (a == null) warn(`${where}.${k} is not a number`);
    else out.push([String(k).slice(0, 80), a]);
  }
  return out.sort((a, b) => a[0].localeCompare(b[0]));
}

function account(a, i, warn) {
  a = obj(a);
  const id = text(a.id, 40) || `page-${i + 1}`;
  if (!text(a.id)) warn(`accounts[${i}] has no id`);
  const q = obj(a.queue), p = obj(a.posted), qc = obj(a.qc), w = obj(a.week);
  const next = a.queue?.next ? obj(q.next) : null;
  const last = a.posted?.last ? obj(p.last) : null;
  const status = text(a.status, 20);
  if (status && !STATUSES.has(status)) warn(`${id}: unknown status "${status}"`);
  const built = int(qc.built), passed = int(qc.passed);
  if (built != null && passed != null && passed > built) warn(`${id}: QC passed (${passed}) is more than built (${built})`);
  if (last?.permalink && !httpsUrl(last.permalink)) warn(`${id}: last permalink is not an https link, hidden`);
  return {
    id, handle: text(a.handle, 60), niche: text(a.niche), status: status || "unknown",
    secretsSet: typeof a.secrets_set === "boolean" ? a.secrets_set : null,
    queue: { waiting: int(q.waiting_approval), approved: int(q.approved),
             next: next ? { slug: text(next.slug, 120), kind: text(next.kind, 20), at: isoish(next.at) } : null },
    posted: { count: int(p.count),
              last: last ? { slug: text(last.slug, 120), kind: text(last.kind, 20), at: isoish(last.posted_at), permalink: httpsUrl(last.permalink) } : null },
    qc: { built, passed },
    week: { posts: int(w.posts), reach: int(w.reach), sendsPer100: ratio(w.sends_per_100), savesPer100: ratio(w.saves_per_100) },
  };
}

/** Parse the feed's text. Throws (badInput) only when it isn't a v1 feed at all; everything else is a warning. */
export function parseFeed(raw) {
  let data;
  try { data = JSON.parse(String(raw).replace(/^﻿/, "")); } catch {
    throw Object.assign(new Error("The pages feed is not valid JSON."), { feedError: "invalid" });
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw Object.assign(new Error("The pages feed is not a JSON object."), { feedError: "invalid" });
  }
  if (data.version !== FEED_VERSION) {
    throw Object.assign(new Error(`The pages feed is version ${JSON.stringify(data.version ?? null)}; this app reads version ${FEED_VERSION}.`),
      { feedError: "version" });
  }
  const warnings = [];
  const warn = (m) => { if (warnings.length < 20) warnings.push(m); };
  if (!Array.isArray(data.accounts)) warn("accounts is missing");
  const accounts = (Array.isArray(data.accounts) ? data.accounts : []).slice(0, 50).map((a, i) => account(a, i, warn));
  const inc = obj(data.income);
  const income = {
    total: amount(inc.total_inr) ?? 0,
    byMonth: money(inc.by_month, warn, "income.by_month"),
    byAccount: money(inc.by_account, warn, "income.by_account"),
    bySource: money(inc.by_source, warn, "income.by_source"),
  };
  if (inc.total_inr != null && amount(inc.total_inr) == null) warn("income.total_inr is not a number");
  const sum = income.byMonth.reduce((s, [, v]) => s + v, 0);
  if (income.byMonth.length && Math.abs(sum - income.total) > 0.05) warn(`income by month adds to ${sum.toFixed(2)}, not the total ${income.total.toFixed(2)}`);
  return { version: data.version, generatedAt: isoish(data.generated_at), accounts, income, warnings };
}

export function validFeedPath(p) {
  return typeof p === "string" && p.length < 400 && isAbsolute(p) && /\.json$/i.test(p) && !/[\0"<>|?*]/.test(p);
}

/** The whole GET local/pages answer. readImpl/statImpl are injectable for tests. */
export async function readPagesFeed(path, { readImpl = readFile, statImpl = stat } = {}) {
  // feeds live at <faceless-ig>/data/dashboard.json, so the command runs two folders up (PowerShell syntax)
  const base = { path, how: `cd "${dirname(dirname(path))}"; python -m ig feed` };
  let raw, info;
  try {
    [raw, info] = await Promise.all([readImpl(path, "utf-8"), statImpl(path)]);
  } catch (err) {
    if (err.code === "ENOENT" || err.code === "ENOTDIR") return { ...base, found: false, message: "No pages feed at this path yet." };
    return { ...base, found: false, message: `Could not read the pages feed (${err.code || "error"}).` };
  }
  try {
    return { ...base, found: true, modified: info.mtime.toISOString(), feed: parseFeed(raw) };
  } catch (err) {
    if (err.feedError) return { ...base, found: true, modified: info.mtime.toISOString(), message: err.message };
    throw err;
  }
}
