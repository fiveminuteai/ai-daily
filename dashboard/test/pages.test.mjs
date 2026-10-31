// The Pages screen's feed parser (desktop/pages.mjs) and its local API route.
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { createLocalApi } from "../desktop/local-api.mjs";
import { DEFAULT_FEED, parseFeed, readPagesFeed, validFeedPath } from "../desktop/pages.mjs";
import { Store } from "../desktop/store.mjs";

const fixture = (name) => readFile(new URL(`./fixtures/${name}`, import.meta.url), "utf-8");

test("parses the sample feed written by `python -m ig feed` (nothing posted yet)", async () => {
  const f = parseFeed(await fixture("pages-feed-sample.json"));
  assert.equal(f.version, 1);
  assert.deepEqual(f.warnings, []);
  assert.deepEqual(f.accounts.map((a) => [a.id, a.handle, a.status]), [["sql", "@onequeryaday", "building"], ["heart", "@pick-a-handle", "planned"]]);
  const sql = f.accounts[0];
  assert.equal(sql.secretsSet, false);
  assert.deepEqual(sql.queue, { waiting: 0, approved: 0, next: null });
  assert.deepEqual(sql.posted, { count: 0, last: null });
  assert.deepEqual(sql.qc, { built: 6, passed: 6 });
  assert.deepEqual(sql.week, { posts: 0, reach: 0, sendsPer100: null, savesPer100: null });
  assert.deepEqual(f.income, { total: 0, byMonth: [], byAccount: [], bySource: [] });
});

test("parses a full feed: queue, last permalink, week ratios, income breakdowns", async () => {
  const f = parseFeed(await fixture("pages-feed-full.json"));
  assert.deepEqual(f.warnings, []);
  const sql = f.accounts[0];
  assert.equal(sql.secretsSet, true);
  assert.deepEqual(sql.queue.next, { slug: "window-functions-running-total", kind: "carousel", at: "2026-11-01T19:00+05:30" });
  assert.equal(sql.posted.count, 12);
  assert.equal(sql.posted.last.permalink, "https://www.instagram.com/p/EXAMPLE123/");
  assert.equal(sql.posted.last.at, "2026-10-30T19:00:12+05:30");
  assert.deepEqual(sql.week, { posts: 7, reach: 4820, sendsPer100: 1.87, savesPer100: 3.42 });
  assert.equal(f.income.total, 4250);
  assert.deepEqual(f.income.byMonth, [["2026-09", 750], ["2026-10", 3500]]);
  assert.deepEqual(f.income.byAccount, [["sql", 4250]]);
  assert.deepEqual(f.income.bySource, [["affiliate", 1250], ["sponsor", 3000]]);
});

test("refuses what is not a v1 feed at all", () => {
  assert.throws(() => parseFeed("{not json"), (e) => e.feedError === "invalid");
  assert.throws(() => parseFeed("[1,2]"), (e) => e.feedError === "invalid");
  assert.throws(() => parseFeed("null"), (e) => e.feedError === "invalid");
  assert.throws(() => parseFeed('{"version": 2, "accounts": []}'), (e) => e.feedError === "version" && /version 2/.test(e.message));
  assert.throws(() => parseFeed('{"accounts": []}'), (e) => e.feedError === "version");
});

test("accepts a UTF-8 BOM (PowerShell's Out-File adds one)", () => {
  assert.equal(parseFeed('\uFEFF{"version": 1, "accounts": [], "income": {}}').accounts.length, 0);
});

test("bad fields become null with a warning instead of blanking the screen", () => {
  const f = parseFeed(JSON.stringify({
    version: 1, generated_at: "not a date",
    accounts: [
      { handle: "@x", status: "viral", secrets_set: "yes",
        queue: { waiting_approval: -1, approved: 1.5, next: { slug: 7, at: "soon" } },
        posted: { count: "12", last: { slug: "p", permalink: "javascript:alert(1)" } },
        qc: { built: 2, passed: 5 },
        week: { posts: 1, reach: 100, sends_per_100: "2", saves_per_100: -1 } },
      "junk",
    ],
    income: { total_inr: "lots", by_month: { "2026-11": 10, "2026-12": "x" }, by_account: [], by_source: null },
  }));
  const [a, junk] = f.accounts;
  assert.equal(f.generatedAt, null);
  assert.equal(a.id, "page-1");
  assert.equal(a.status, "viral");
  assert.equal(a.secretsSet, null);
  assert.deepEqual(a.queue, { waiting: null, approved: null, next: { slug: null, kind: null, at: null } });
  assert.equal(a.posted.count, null);
  assert.equal(a.posted.last.permalink, null, "only https links reach the page");
  assert.deepEqual(a.week, { posts: 1, reach: 100, sendsPer100: null, savesPer100: null });
  assert.equal(junk.id, "page-2");
  assert.deepEqual(junk.qc, { built: null, passed: null });
  assert.equal(f.income.total, 0);
  assert.deepEqual(f.income.byMonth, [["2026-11", 10]]);
  assert.deepEqual(f.income.byAccount, []);
  for (const w of [/accounts\[0\] has no id/, /unknown status "viral"/, /QC passed \(5\) is more than built \(2\)/,
                   /permalink is not an https link/, /income\.by_month\.2026-12/, /total_inr is not a number/]) {
    assert.ok(f.warnings.some((x) => w.test(x)), `missing warning ${w}`);
  }
});

test("warns when the months don't add up to the total", () => {
  const f = parseFeed(JSON.stringify({ version: 1, accounts: [], income: { total_inr: 100, by_month: { "2026-11": 60 } } }));
  assert.ok(f.warnings.some((w) => /adds to 60\.00, not the total 100\.00/.test(w)));
});

test("a feed with no accounts list still parses, with a warning", () => {
  const f = parseFeed('{"version": 1}');
  assert.deepEqual(f.accounts, []);
  assert.deepEqual(f.warnings, ["accounts is missing"]);
});

test("feed paths must be absolute .json paths", () => {
  assert.ok(validFeedPath("C:\\Users\\me\\faceless-ig\\data\\dashboard.json"));
  assert.ok(validFeedPath(DEFAULT_FEED));
  assert.ok(DEFAULT_FEED.endsWith(join("faceless-ig", "data", "dashboard.json")));
  for (const p of ["dashboard.json", "..\\data\\dashboard.json", "C:\\x\\dashboard.txt", "", 5, null, `C:\\${"a".repeat(400)}.json`]) {
    assert.equal(validFeedPath(p), false, String(p));
  }
});

test("readPagesFeed: found, missing, and not a feed", async () => {
  const dir = await mkdtemp(join(tmpdir(), "fma-pages-"));
  try {
    const good = join(dir, "dashboard.json");
    await writeFile(good, await fixture("pages-feed-full.json"));
    const ok = await readPagesFeed(good);
    assert.equal(ok.found, true);
    assert.equal(ok.path, good);
    assert.ok(Date.parse(ok.modified));
    assert.equal(ok.feed.accounts.length, 2);
    assert.equal(ok.how, `cd "${dirname(dir)}"; python -m ig feed`);

    const missing = await readPagesFeed(join(dir, "nope.json"));
    assert.equal(missing.found, false);
    assert.equal(missing.feed, undefined);
    assert.match(missing.message, /No pages feed/);

    const bad = join(dir, "bad.json");
    await writeFile(bad, '{"version": 9}');
    const wrong = await readPagesFeed(bad);
    assert.equal(wrong.found, true);
    assert.equal(wrong.feed, undefined);
    assert.match(wrong.message, /version 9/);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("local API: GET pages reads the configured path; POST settings sets and clears it", async () => {
  const dir = await mkdtemp(join(tmpdir(), "fma-pages-api-"));
  try {
    const store = new Store(dir);
    const seen = [];
    const api = createLocalApi({ store, env: { FMA_PAGES_FEED: "D:\\env\\dashboard.json" },
                                 readPagesFeed: async (p) => { seen.push(p); return { path: p, found: false }; } });
    let r = await api.handle("GET pages", null, new URLSearchParams());
    assert.equal(r.path, "D:\\env\\dashboard.json");
    assert.equal(r.custom, false);
    assert.equal(r.defaultPath, DEFAULT_FEED);

    await api.handle("POST settings", { pagesFeed: "E:\\pages\\dashboard.json" });
    r = await api.handle("GET pages", null, new URLSearchParams());
    assert.equal(r.path, "E:\\pages\\dashboard.json");
    assert.equal(r.custom, true);

    await assert.rejects(api.handle("POST settings", { pagesFeed: "relative.json" }), (e) => e.badInput);
    await assert.rejects(api.handle("POST settings", { pagesFeed: "C:\\x\\feed.yaml" }), (e) => e.badInput);

    await api.handle("POST settings", { pagesFeed: "" });
    assert.equal((await store.read("settings", {})).pagesFeed, undefined);
    r = await api.handle("GET pages", null, new URLSearchParams());
    assert.equal(r.path, "D:\\env\\dashboard.json");

    const plain = createLocalApi({ store, env: {}, readPagesFeed: async (p) => ({ path: p }) });
    assert.equal((await plain.handle("GET pages", null, new URLSearchParams())).path, DEFAULT_FEED);
    assert.equal(seen.length, 3);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("reads where the secrets are set; feeds written before that field still parse", async () => {
  const old = parseFeed(await fixture("pages-feed-sample.json"));
  assert.equal(old.accounts[0].secretsWhere, null);
  assert.deepEqual(old.accounts.map((a) => a.first), [true, false]);
  const f = parseFeed(JSON.stringify({ version: 1, accounts: [
    { id: "sql", secrets_set: true, secrets: { local: false, github: true } },
    { id: "gita", secrets_set: false, secrets: { local: false, github: null } },
    { id: "heart", secrets_set: false, secrets: { local: "yes", github: 1 } },
    { id: "x", secrets: [] },
  ] }));
  assert.deepEqual(f.accounts.map((a) => [a.secretsSet, a.secretsWhere]), [
    [true, { local: false, github: true }],
    [false, { local: false, github: null }],
    [false, { local: null, github: null }],
    [null, null],
  ]);
});
