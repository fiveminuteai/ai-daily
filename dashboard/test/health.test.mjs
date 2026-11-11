// 11 Nov 2026 audit: the dashboard showed a short edition, an overdue Reel and the wrong attempt as a clean "ok".
import assert from "node:assert/strict";
import { test } from "node:test";
import { buildDay } from "../lib/parse.js";

const post = (n, words, extra = {}) => ({ headline: "H", dek: "D", slug: "s", model: "m", tags: [], word_count: words,
  reading_minutes: 3, sources: [], generated_at: "2026-11-11T02:53:00+00:00",
  sections: Array.from({ length: n }, (_, k) => ({ title: `S${k}` })), ...extra });
const reel = (id, status, at, more = {}) => ({ id, platform: "instagram_reel", posting: "api", status, scheduled_at: at, ...more });
const stage = (d, key) => d.stages.find((s) => s.key === key);

test("a short edition is a warning, not ok", () => {
  const d = buildDay({ date: "2026-11-11", now: new Date("2026-11-11T04:00:00Z"), post: post(3, 564, { edition: "short" }) });
  assert.equal(stage(d, "gate").status, "warn");
  assert.match(stage(d, "gate").note, /3 stories, 564 words/);
  assert.equal(d.verdict, "warn");
});

test("the verify numbers are the published attempt's", () => {
  const summary = { published_attempt: 1, stages: {}, attempts: [
    { n: 1, fails: ["word count 860"], layer1: { checked: 104 }, layer2: { checked: 104, ok: 36, repaired: 36, dropped: 32 } },
    { n: 2, fails: ["word count 559"], layer1: { checked: 95 }, layer2: { checked: 95, ok: 38, repaired: 22, dropped: 35 } }] };
  const d = buildDay({ date: "2026-11-11", now: new Date("2026-11-11T04:00:00Z"), post: post(5, 860, { edition: "short" }), summary });
  assert.equal(stage(d, "verify").numbers.checked, 104);
});

test("an approved Reel long past its slot is a failure, and failures outrank pending", () => {
  const queue = { items: [reel("r1", "posted", "2026-11-11T03:30:00+00:00", { youtube_url: "y" }),
                          reel("r2", "approved", "2026-11-11T07:30:00+00:00"),
                          reel("r3", "pending", "2026-11-11T10:30:00+00:00")] };
  const d = buildDay({ date: "2026-11-11", now: new Date("2026-11-11T09:00:00Z"), post: post(5, 950), queue });
  assert.equal(stage(d, "social").status, "failed");
  assert.equal(stage(d, "social").numbers.overdue, 1);
  assert.equal(d.verdict, "warn");
  const early = buildDay({ date: "2026-11-11", now: new Date("2026-11-11T07:50:00Z"), post: post(5, 950), queue });
  assert.notEqual(stage(early, "social").status, "failed");      // 20 minutes late: GitHub's cron, not a failure
});

test("a past day where nothing posted is not ok", () => {
  const queue = { items: [reel("r1", "pending", "2026-11-10T03:30:00+00:00")] };
  const d = buildDay({ date: "2026-11-10", now: new Date("2026-11-11T09:00:00Z"), post: post(5, 950), queue });
  assert.equal(stage(d, "social").status, "failed");
});

test("a posted Reel with no YouTube Short is a warning", () => {
  const queue = { items: [reel("r1", "posted", "2026-11-11T03:30:00+00:00", { youtube_error: "upload outcome unknown" })] };
  const d = buildDay({ date: "2026-11-11", now: new Date("2026-11-11T09:00:00Z"), post: post(5, 950), queue });
  assert.equal(stage(d, "social").status, "warn");
});

test("a failing GitHub refresh is recorded so the screen can say its data is old", async () => {
  const { GitHub, freshness } = await import("../lib/github.js");
  let fail = false;
  const gh = new GitHub({ token: "t", repo: "o/r", fetchImpl: async () => (fail
    ? { ok: false, status: 503, json: async () => ({ message: "down" }) }
    : { ok: true, status: 200, json: async () => ({ ok: 1 }) }) });
  await gh.send("/x");
  assert.ok(freshness.okAt > 0);
  fail = true;
  await assert.rejects(gh.send("/y"));
  assert.ok(freshness.errorAt >= freshness.okAt && /503/.test(freshness.error));
});
