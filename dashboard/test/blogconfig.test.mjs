// node --test test/   (no dependencies). The blog settings screen: config/site.yaml + config/sources.yaml.
import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { ConfigError, SETTINGS, applyChanges, listSources, readSettings } from "../lib/blogconfig.js";
import { handle } from "../lib/api.js";

const real = {
  site: readFileSync(new URL("../../config/site.yaml", import.meta.url), "utf8"),
  sources: readFileSync(new URL("../../config/sources.yaml", import.meta.url), "utf8"),
};
const changedLines = (a, b) => a.split("\n").map((l, i) => [l, b.split("\n")[i]]).filter(([x, y]) => x !== y);

test("every whitelisted setting is found exactly once in the real config, with the right type", () => {
  const { settings, sources } = readSettings(real);
  const by = Object.fromEntries(settings.map((s) => [s.id, s.value]));
  for (const s of SETTINGS) assert.ok(s.id in by, s.id);
  for (const s of settings) {
    const want = s.type === "bool" || s.type === "enabled" ? "boolean" : "number";
    assert.equal(typeof s.value, want, s.id);
    if (want === "number") assert.ok(Number.isFinite(s.value), s.id);
  }
  assert.ok(by["pipeline.words_min"] < by["pipeline.words_max"]);
  assert.ok(sources.length >= 20);
  assert.equal(new Set(sources.map((s) => s.id)).size, sources.length);
  // the page only ever gets the whitelisted values: no URLs, provider settings or key names
  const sent = JSON.stringify(readSettings(real));
  for (const leak of ["base_url", "key_env", "API_KEY", "instagram_id", "https://"]) assert.ok(!sent.includes(leak), leak);
});

test("a save changes exactly the requested values and nothing else in either file", () => {
  const wanted = { "pipeline.words_min": 800, "pipeline.attempts": 3, "player_boost.giant": 1.1, "groq.min_interval_s": 25,
                   "source.arxiv-ai.weight": 0.2, "source.hn.enabled": false, "audience.editor_weight": 2.5 };
  const r = applyChanges(real, wanted);
  assert.equal(r.changes.length, 7);
  const lines = [...changedLines(real.site, r.texts.site), ...changedLines(real.sources, r.texts.sources)];
  assert.equal(lines.length, 7);                               // one line per value
  assert.match(r.texts.site, /^ {2}words_min: 800$/m);
  assert.match(r.texts.site, /^ {2}attempts: 3 {17}# first try/m);         // the comment stays
  assert.match(r.texts.sources, /^player_boost: \{rivalry: 1\.2, giant: 1\.1, challenger: 0\.6\}$/m);
  assert.match(r.texts.sources, /- \{id: hn,.*ai_filter: true, enabled: false\}$/m);
  const after = Object.fromEntries(readSettings(r.texts).settings.map((s) => [s.id, s.value]));
  for (const [id, v] of Object.entries(wanted)) assert.equal(after[id], v, id);
  assert.match(r.message, /^Blog settings: words_min 880 -> 800, attempts 2 -> 3, /);
  assert.match(r.message, /\+3 more \(from the control dashboard\)$/);
});

test("turning a source off and on again gives back the same file", () => {
  const off = applyChanges(real, { "source.techcrunch.enabled": false }).texts;
  const on = applyChanges(off, { "source.techcrunch.enabled": true }).texts;
  assert.equal(on.sources, real.sources);
  // VentureBeat is off in the file today: turning it on removes the flag
  const vb = applyChanges(real, { "source.venturebeat.enabled": true }).texts.sources;
  assert.equal(listSources(vb).find((s) => s.id === "venturebeat").enabled, true);
  assert.ok(!/id: venturebeat,.*enabled/.test(vb));
});

test("bad requests are refused and change nothing", () => {
  const bad = [
    [{ "pipeline.words_min": 1100 }, /100 more/],             // 1100 + 100 > 1150
    [{ "pipeline.min_stories": 6, "pipeline.stories_per_post": 5 }, /Fewest stories/],
    [{ "pipeline.attempts": 9 }, /between 1 and 4/],
    [{ "pipeline.attempts": 2.5 }, /whole number/],
    [{ "pipeline.attempts": "3" }, /must be a number/],
    [{ "pipeline.llm_check": "false" }, /on or off/],
    [{ "source.hn.weight": -1 }, /between 0 and 3/],
    [{ "providers.groq.base_url": "https://evil" }, /unknown setting/],
    [{ "source.nope.weight": 1 }, /unknown setting/],
    [JSON.parse('{"__proto__": 1}'), /unknown setting/],
    [{ constructor: 1 }, /unknown setting/],
    [{}, /nothing to change/],
    [[], /must be an object/],
    [null, /must be an object/],
  ];
  for (const [wanted, msg] of bad) assert.throws(() => applyChanges(real, wanted), (e) => e instanceof ConfigError && msg.test(e.message), JSON.stringify(wanted));
});

test("a value the file can't hold exactly is refused, not rounded", () => {
  // weights are written with two decimals, so 0.155 would come back rounded: the read-back refuses it
  assert.throws(() => applyChanges(real, { "source.hn.weight": 0.155 }), (e) => e instanceof ConfigError && /would read 0\.1[56] after the edit, not 0\.155/.test(e.message));
  assert.equal(applyChanges(real, { "source.hn.weight": 0.15 }).changes[0].to, 0.15);
});

test("a value that is missing or appears twice is refused rather than guessed", () => {
  const twice = { ...real, site: real.site.replace("  words_min: 880\n", "  words_min: 880\n  words_min: 900\n") };
  assert.throws(() => readSettings(twice), /words_min found 2 times/);
  const gone = { ...real, site: real.site.replace(/^ {2}attempts:.*\n/m, "") };
  assert.throws(() => applyChanges(gone, { "pipeline.words_min": 800 }), /attempts found 0 times/);
  const noBlock = { ...real, site: real.site.replace(/^pipeline:/m, "pipe_line:") };
  assert.throws(() => readSettings(noBlock), /can't find where pipeline\./);
});

test("a key with the same name elsewhere in the file is not touched", () => {
  // `giant:` is also the players list key; only the player_boost line may change
  const r = applyChanges(real, { "player_boost.giant": 0.9 });
  assert.equal(changedLines(real.sources, r.texts.sources).length, 1);
  assert.match(r.texts.sources, /^ {2}giant: \[OpenAI/m);
});

// ---------- the API routes ----------

const LOCAL = { LOCAL_DEV: "1" };
const req = (path, init = {}) => new Request(`http://127.0.0.1:8788/api/${path}`, init);
const post = (path, body) => req(path, { method: "POST", body: JSON.stringify(body),
  headers: { "content-type": "application/json", "x-fma-dashboard": "1" } });

function fakeGitHub(files = { "config/site.yaml": real.site, "config/sources.yaml": real.sources }) {
  const puts = [];
  const fetchImpl = async (url, init = {}) => {
    const path = decodeURIComponent(new URL(url).pathname.replace(/^\/repos\/[^/]+\/[^/]+\/contents\//, ""));
    if ((init.method || "GET") === "PUT") {
      puts.push({ path, body: JSON.parse(init.body) });
      return new Response(JSON.stringify({ content: { sha: "new" } }), { status: 200 });
    }
    if (!(path in files)) return new Response("{}", { status: 404 });
    return new Response(JSON.stringify({ sha: `sha-${path}`, content: Buffer.from(files[path]).toString("base64") }));
  };
  return { fetchImpl, puts };
}

test("GET blog/settings returns the values and the file versions", async () => {
  const { fetchImpl } = fakeGitHub();
  const r = await (await handle(req("blog/settings"), { ...LOCAL, GITHUB_TOKEN: "t" }, { fetchImpl })).json();
  assert.equal(r.settings.find((s) => s.id === "pipeline.words_min").value, 880);
  assert.deepEqual(r.shas, { site: "sha-config/site.yaml", sources: "sha-config/sources.yaml" });
  assert.ok(r.groups.length >= 4);
});

test("POST blog/settings: dry run shows the commit and writes nothing", async () => {
  const { fetchImpl, puts } = fakeGitHub();
  const r = await (await handle(post("blog/settings", { changes: { "pipeline.words_min": 800 } }), { ...LOCAL, GITHUB_TOKEN: "t" }, { fetchImpl })).json();
  assert.equal(r.dryRun, true);
  assert.equal(r.done, false);
  assert.deepEqual(r.changes.map((c) => [c.id, c.from, c.to]), [["pipeline.words_min", 880, 800]]);
  assert.match(r.request.message, /words_min 880 -> 800/);
  assert.equal(puts.length, 0);
});

test("POST blog/settings live: one commit to the changed file only, against the version read", async () => {
  const { fetchImpl, puts } = fakeGitHub();
  const env = { ...LOCAL, GITHUB_TOKEN: "t", DRY_RUN: "0" };
  const r = await (await handle(post("blog/settings", { changes: { "pipeline.attempts": 3 }, shas: { site: "sha-config/site.yaml" } }), env, { fetchImpl })).json();
  assert.equal(r.done, true);
  assert.equal(puts.length, 1);
  assert.equal(puts[0].path, "config/site.yaml");
  assert.equal(puts[0].body.sha, "sha-config/site.yaml");
  assert.equal(puts[0].body.branch, "main");
  const written = Buffer.from(puts[0].body.content, "base64").toString();
  assert.deepEqual(changedLines(real.site, written).map(([, b]) => b.trim()), ["attempts: 3                 # first try + one retry, then skip the day"]);
});

test("POST blog/settings refuses a stale page and bad values without writing", async () => {
  const { fetchImpl, puts } = fakeGitHub();
  const env = { ...LOCAL, GITHUB_TOKEN: "t", DRY_RUN: "0" };
  const stale = await handle(post("blog/settings", { changes: { "pipeline.attempts": 3 }, shas: { site: "old" } }), env, { fetchImpl });
  assert.equal(stale.status, 400);
  assert.match((await stale.json()).message, /changed since this page loaded/);
  const bad = await handle(post("blog/settings", { changes: { "pipeline.attempts": 40 } }), env, { fetchImpl });
  assert.equal(bad.status, 400);
  assert.equal(puts.length, 0);
});

test("blog settings need sign-in and the dashboard header like every other write", async () => {
  const { fetchImpl, puts } = fakeGitHub();
  assert.equal((await handle(req("blog/settings"), { GITHUB_TOKEN: "t" }, { fetchImpl })).status, 403);
  const noHeader = req("blog/settings", { method: "POST", body: "{}", headers: { "content-type": "application/json" } });
  assert.equal((await handle(noHeader, { ...LOCAL, GITHUB_TOKEN: "t", DRY_RUN: "0" }, { fetchImpl })).status, 400);
  assert.equal(puts.length, 0);
});
