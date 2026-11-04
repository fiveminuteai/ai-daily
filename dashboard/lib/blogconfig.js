// The blog's own settings (config/site.yaml and config/sources.yaml), as the control app shows and edits them.
//
// Only the keys listed here can be read or changed, each with a type and a range. A change replaces exactly one value
// on one line and leaves every other byte (comments, order, spacing) as it was; after the edit every setting is read
// back, and anything other than the requested values changing refuses the whole save. The files hold no secrets
// (provider keys are only named, never stored), and nothing outside this list is ever sent to the page.

export const FILES = { site: "config/site.yaml", sources: "config/sources.yaml" };

export class ConfigError extends Error {}

// ---------- where a value lives ----------

const whole = (text) => [0, text.length];

/** A top-level block: from its `name:` line to the next line that starts at column 0 (a key or a comment). */
const block = (name) => (text) => {
  const m = new RegExp(`^${name}:.*$`, "m").exec(text);
  if (!m) return null;
  const rest = text.slice(m.index + m[0].length);
  const next = /\n(?=\S)/.exec(rest);
  return [m.index, m.index + m[0].length + (next ? next.index : rest.length)];
};

/** One provider entry inside `providers:` (its flow map may run over two lines). */
const provider = (name) => (text) => {
  const b = block("providers")(text);
  if (!b) return null;
  const inner = text.slice(b[0], b[1]);
  const m = new RegExp(`\\n[ \\t]*- \\{name: ${name}\\b`).exec(inner);
  if (!m) return null;
  const after = inner.slice(m.index + 1);
  const next = /\n[ \t]*- \{/.exec(after);
  const start = b[0] + m.index + 1;
  return [start, start + (next ? next.index : after.length)];
};

/** The one line of a source in sources.yaml. */
const sourceLine = (id) => (text) => {
  const m = new RegExp(`^[ \\t]*- \\{id:[ \\t]*${id.replace(/[-.]/g, "\\$&")},.*$`, "m").exec(text);
  return m ? [m.index, m.index + m[0].length] : null;
};

const VALUE = { int: "-?\\d+", float: "-?\\d+(?:\\.\\d+)?", bool: "true|false", time: '"\\d\\d:\\d\\d"', times: "\\[[^\\]\\n]*\\]" };
const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/;
const mins = (t) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// ---------- the settings ----------

const S = (id, file, scope, key, type, min, max, label, help, group, extra = {}) =>
  ({ id, file, scope, key, type, min, max, label, help, group, ...extra });

export const SETTINGS = [
  S("schedule.daily", "site", block("schedule"), "daily", "time", "03:00", "07:00", "Daily post",
    "When the day's post is written. Kept before 07:30, when the laptop backup checks for a missing post.", "schedule"),
  S("schedule.reels", "site", block("schedule"), "reels", "times", null, null, "Reel times",
    "1 to 3 times, like 09:00, 13:00, 19:00: the first at least 90 minutes after the post, 30 minutes apart, the last by 23:00. Applies from the next day's queue; Reels already queued keep their times.", "schedule"),
  S("schedule.stats", "site", block("schedule"), "stats", "time", "20:00", "23:45", "Stats and learning",
    "When the day's numbers are collected and the learning loop runs. After the last Reel.", "schedule"),

  S("paused", "site", whole, "paused", "bool", null, null, "Daily posts paused",
    "On: no post is made until you turn it off. The same switch as Pause on Controls.", "posting"),
  S("auto_post_reels", "site", whole, "auto_post_reels", "bool", null, null, "Reels post by themselves",
    "On: each day's Reels post at their times unless you skip one. Off: every Reel waits for your Approve.", "posting"),

  S("pipeline.words_min", "site", block("pipeline"), "words_min", "int", 400, 2000, "Fewest words",
    "A post shorter than this after fact-checking is not published (the gate). Lower it when the checker trims hard.", "gate"),
  S("pipeline.words_max", "site", block("pipeline"), "words_max", "int", 500, 2500, "Most words",
    "A post longer than this is not published.", "gate"),
  S("pipeline.attempts", "site", block("pipeline"), "attempts", "int", 1, 4, "Tries per day",
    "How many times the writer may try before the day is skipped. Past Groq's free 200K tokens a day, the backup model (Gemini) takes over.", "gate",
    { warnAbove: 2, cost: { per: 86, of: 200, unit: "K Groq tokens a day" } }),
  S("pipeline.llm_check", "site", block("pipeline"), "llm_check", "bool", null, null, "Second fact-check",
    "The model re-reads the sources and drops sentences they don't support. Off means only the rule checks run.", "gate",
    { warnWhen: false }),
  S("pipeline.max_quotes", "site", block("pipeline"), "max_quotes", "int", 0, 3, "Quotes per post",
    "Most direct quotes a post may carry.", "gate"),

  S("pipeline.stories_per_post", "site", block("pipeline"), "stories_per_post", "int", 3, 6, "Stories per post",
    "How many stories the editor aims for.", "stories"),
  S("pipeline.min_stories", "site", block("pipeline"), "min_stories", "int", 1, 6, "Fewest stories",
    "With fewer good stories than this, the day is skipped.", "stories"),
  S("pipeline.max_per_category", "site", block("pipeline"), "max_per_category", "int", 1, 5, "Stories per topic",
    "At most this many stories from one topic (models, products, policy...) in a post.", "stories"),
  S("pipeline.max_per_source", "site", block("pipeline"), "max_per_source", "int", 1, 3, "Single-outlet stories",
    "At most this many stories that only one outlet reported.", "stories"),
  S("pipeline.lookback_hours", "site", block("pipeline"), "lookback_hours", "int", 12, 96, "News window (hours)",
    "Only items published in this many hours are considered.", "stories"),
  S("pipeline.dedupe_days", "site", block("pipeline"), "dedupe_days", "int", 1, 60, "Never repeat a link for (days)",
    "A source URL covered in this many days is not used again.", "stories"),
  S("pipeline.similar_title_days", "site", block("pipeline"), "similar_title_days", "int", 1, 14, "Skip near-repeats for (days)",
    "A story with an almost identical title in this many days is skipped.", "stories"),
  S("audience.editor_weight", "site", block("audience"), "editor_weight", "float", 0, 10, "Editor's say",
    "How much the editor's reader-interest score counts against plain importance. 0 = importance only.", "stories",
    { step: 0.5 }),
  S("player_boost.rivalry", "sources", whole, "rivalry", "float", 0, 3, "Boost: rivalry",
    "Extra score for a challenger taking on a giant (DeepSeek vs OpenAI).", "stories", { step: 0.1, line: /^player_boost:/m }),
  S("player_boost.giant", "sources", whole, "giant", "float", 0, 3, "Boost: AI giants",
    "Extra score for stories naming OpenAI, Anthropic, Google, Meta, Microsoft, Apple, Nvidia, xAI, Amazon.", "stories",
    { step: 0.1, line: /^player_boost:/m }),
  S("player_boost.challenger", "sources", whole, "challenger", "float", 0, 3, "Boost: challengers",
    "Extra score for DeepSeek, Mistral, Qwen, Perplexity and the other challengers.", "stories",
    { step: 0.1, line: /^player_boost:/m }),

  S("groq.min_interval_s", "site", provider("groq"), "min_interval_s", "int", 0, 120, "Groq: seconds between calls",
    "Spacing that keeps a post under Groq's 8K tokens a minute.", "models"),
  S("groq.max_completion_tokens", "site", provider("groq"), "max_completion_tokens", "int", 500, 8000, "Groq: longest answer (tokens)",
    "Cap on each model answer. Higher allows longer drafts but spends the daily budget faster.", "models"),
];

export const GROUPS = [
  { id: "schedule", title: "Schedule", note: "India time. The Clock starts each run at these times. The backup runs in daily.yml, post-scheduled.yml and collect-stats.yml keep their fixed times: a daily backup before the post's time skips itself, and the Reel and stats backups only act on what is already due." },
  { id: "posting", title: "Posting" },
  { id: "gate", title: "Quality gate" },
  { id: "stories", title: "Story picking" },
  { id: "models", title: "Model pacing" },
  { id: "sources", title: "News sources" },
];

/** The sources in sources.yaml, in file order, as [{id, name, category, weight, enabled}]. */
export function listSources(text) {
  const out = [];
  for (const m of text.matchAll(/^[ \t]*- \{id:[ \t]*([\w.-]+),[ \t]*name:[ \t]*([^,]+),.*$/gm)) {
    const line = m[0];
    out.push({ id: m[1], name: m[2].trim(), category: /\bcategory:\s*(\w+)/.exec(line)?.[1] || "",
               weight: Number(/\bweight:\s*(-?\d+(?:\.\d+)?)/.exec(line)?.[1]), enabled: !/\benabled:\s*false\b/.test(line) });
  }
  return out;
}

function sourceSettings(text) {
  return listSources(text).flatMap((s) => [
    S(`source.${s.id}.weight`, "sources", sourceLine(s.id), "weight", "float", 0, 3, `${s.name}: weight`,
      "How much one item from this source counts when ranking (1 = normal).", "sources", { step: 0.05, source: s.id }),
    { id: `source.${s.id}.enabled`, file: "sources", scope: sourceLine(s.id), type: "enabled", label: `${s.name}: on`,
      help: "Off: this source is not read.", group: "sources", source: s.id },
  ]);
}

const allSettings = (texts) => [...SETTINGS, ...sourceSettings(texts.sources || "")];

// ---------- read ----------

/** {start, end, raw} of a setting's value in its file, or a ConfigError if it is not found exactly once. */
function locate(text, s) {
  let [lo, hi] = (s.scope(text) || [-1, -1]);
  if (lo < 0) throw new ConfigError(`${FILES[s.file]}: can't find where ${s.id} lives`);
  if (s.line) {
    const m = s.line.exec(text.slice(lo, hi));
    if (!m) throw new ConfigError(`${FILES[s.file]}: can't find the line for ${s.id}`);
    lo += m.index;
    const end = text.indexOf("\n", lo);
    hi = end < 0 ? text.length : end;
  }
  const part = text.slice(lo, hi);
  if (s.type === "enabled") {
    const m = /,?[ \t]*enabled:[ \t]*(true|false)\b/.exec(part);
    return { start: lo, end: hi, raw: m ? m[1] : "true", line: part };
  }
  const re = new RegExp(`(?<=^|[\\s{,])${s.key}:[ \\t]*(${VALUE[s.type]})(?=[\\s,}#]|$)`, "gm");
  const hits = [...part.matchAll(re)];
  if (hits.length !== 1) throw new ConfigError(`${FILES[s.file]}: ${s.id} found ${hits.length} times, expected once`);
  const at = lo + hits[0].index + hits[0][0].length - hits[0][1].length;
  return { start: at, end: at + hits[0][1].length, raw: hits[0][1] };
}

const parse = (s, raw) => (s.type === "bool" || s.type === "enabled" ? raw === "true"
  : s.type === "time" ? raw.slice(1, -1) : s.type === "times" ? raw.match(/\d\d:\d\d/g) || [] : Number(raw));

/** Every setting's current value: {settings: [...public fields, value], sources: [...]}. */
export function readSettings(texts) {
  const settings = allSettings(texts).map((s) => {
    const { scope, line, file, ...pub } = s;                 // the page never sees locator internals
    return { ...pub, file: FILES[file], value: parse(s, locate(texts[file], s).raw) };
  });
  return { settings, sources: listSources(texts.sources || "") };
}

// ---------- write ----------

function check(s, v) {
  if (s.type === "time") {
    if (typeof v !== "string" || !HHMM.test(v)) throw new ConfigError(`${s.label} must be a time like 05:45`);
    if (mins(v) < mins(s.min) || mins(v) > mins(s.max)) throw new ConfigError(`${s.label} must be between ${s.min} and ${s.max}`);
    return;
  }
  if (s.type === "times") {
    if (!Array.isArray(v) || v.length < 1 || v.length > 3 || !v.every((t) => typeof t === "string" && HHMM.test(t))) {
      throw new ConfigError(`${s.label} must be 1 to 3 times like 09:00`);
    }
    if (v.some((t, i) => i && mins(t) - mins(v[i - 1]) < 30)) throw new ConfigError(`${s.label} must be in order, at least 30 minutes apart`);
    if (mins(v.at(-1)) > mins("23:00")) throw new ConfigError(`${s.label}: the last one must be by 23:00`);
    return;
  }
  if (s.type === "bool" || s.type === "enabled") {
    if (typeof v !== "boolean") throw new ConfigError(`${s.label} must be on or off`);
    return;
  }
  if (typeof v !== "number" || !Number.isFinite(v)) throw new ConfigError(`${s.label} must be a number`);
  if (s.type === "int" && !Number.isInteger(v)) throw new ConfigError(`${s.label} must be a whole number`);
  if (v < s.min || v > s.max) throw new ConfigError(`${s.label} must be between ${s.min} and ${s.max}`);
}

const format = (s, v) => (typeof v === "boolean" ? String(v) : s.type === "time" ? `"${v}"`
  : s.type === "times" ? `[${v.map((t) => `"${t}"`).join(", ")}]` : s.type === "int" ? String(v) : String(Number(v.toFixed(2))));

function edit(text, s, v) {
  const at = locate(text, s);
  if (s.type !== "enabled") return text.slice(0, at.start) + format(s, v) + text.slice(at.end);
  let line = at.line;
  if (/\benabled:/.test(line)) line = v ? line.replace(/,[ \t]*enabled:[ \t]*(true|false)\b/, "") : line.replace(/\benabled:[ \t]*(true|false)\b/, "enabled: false");
  else if (!v) line = line.replace(/\}([^}]*)$/, ", enabled: false}$1");
  return text.slice(0, at.start) + line + text.slice(at.end);
}

/** Rules that tie two settings together, checked on the values after the change. */
function crossCheck(values) {
  const v = (id) => values.get(id);
  if (v("pipeline.words_min") + 100 > v("pipeline.words_max")) throw new ConfigError("Most words must be at least 100 more than fewest words");
  if (v("pipeline.min_stories") > v("pipeline.stories_per_post")) throw new ConfigError("Fewest stories can't be more than stories per post");
  // the same rules fma/clock.py applies (it falls back to the defaults for anything that breaks them)
  if (mins(v("schedule.reels")[0]) < mins(v("schedule.daily")) + 90) throw new ConfigError("The first Reel must be at least 90 minutes after the daily post");
  if (mins(v("schedule.stats")) <= mins(v("schedule.reels").at(-1))) throw new ConfigError("Stats must run after the last Reel");
}

/**
 * Apply {settingId: newValue} to the two files. Returns {texts, changes: [{id, label, file, from, to, warn}], message}.
 * Throws ConfigError for an unknown id, a bad value, or an edit that would touch anything else.
 */
export function applyChanges(texts, wanted) {
  if (!wanted || typeof wanted !== "object" || Array.isArray(wanted)) throw new ConfigError("changes must be an object");
  const ids = Object.keys(wanted);
  if (!ids.length) throw new ConfigError("nothing to change");
  if (ids.length > 40) throw new ConfigError("too many changes at once");
  const list = allSettings(texts), byId = new Map(list.map((s) => [s.id, s]));
  const before = new Map(list.map((s) => [s.id, parse(s, locate(texts[s.file], s).raw)]));
  const out = { ...texts }, changes = [];
  for (const id of ids) {
    const s = byId.get(id);
    if (!s) throw new ConfigError(`unknown setting ${String(id).slice(0, 60)}`);
    const v = wanted[id];
    check(s, v);
    if (same(v, before.get(id))) continue;
    out[s.file] = edit(out[s.file], s, v);
    const warn = (s.warnAbove != null && v > s.warnAbove) || (s.warnWhen !== undefined && v === s.warnWhen);
    changes.push({ id, label: s.label, file: FILES[s.file], from: before.get(id), to: v, ...(warn ? { warn: true } : {}) });
  }
  // read everything back: exactly the requested values moved, nothing else did
  const after = new Map(allSettings(out).map((s) => [s.id, parse(s, locate(out[s.file], s).raw)]));
  for (const [id, was] of before) {
    const want = Object.hasOwn(wanted, id) ? wanted[id] : was;
    if (!same(after.get(id), want)) throw new ConfigError(`${id} would read ${after.get(id)} after the edit, not ${want}`);
  }
  if (after.size !== before.size) throw new ConfigError("the edit changed the list of sources");
  for (const f of Object.keys(FILES)) {
    const a = (texts[f] || "").split("\n"), b = (out[f] || "").split("\n");
    if (a.length !== b.length) throw new ConfigError(`${FILES[f]}: the edit changed the number of lines`);
  }
  crossCheck(after);
  const short = (c) => `${c.id.replace(/^(pipeline|source)\./, "")} ${c.from} -> ${c.to}`;
  const message = changes.length ? `Blog settings: ${changes.slice(0, 4).map(short).join(", ")}${changes.length > 4 ? `, +${changes.length - 4} more` : ""} (from the control dashboard)` : "";
  return { texts: out, changes, message };
}
