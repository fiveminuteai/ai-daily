// node --test test/   (no dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import { _resetCertCache, handle, setPaused, verifyJwt } from "../lib/api.js";
import { buildDay, buildHistory, dayRange, nextSchedule, parseLog } from "../lib/parse.js";

const LOCAL = { LOCAL_DEV: "1" };
const req = (path, init = {}) => new Request(`http://127.0.0.1:8788/api/${path}`, init);
const post = (path, body, headers = {}) => req(path, {
  method: "POST", body: JSON.stringify(body),
  headers: { "content-type": "application/json", "x-fma-dashboard": "1", ...headers },
});
const noFetch = () => { throw new Error("network must not be used"); };

// ---------- auth ----------

test("everything is refused until Cloudflare Access is configured", async () => {
  for (const env of [{}, { GITHUB_TOKEN: "t" }, { ACCESS_TEAM_DOMAIN: "x.cloudflareaccess.com", ACCESS_AUD: "a" }]) {
    const r = await handle(req("status"), env, { fetchImpl: noFetch });
    assert.equal(r.status, 403);
  }
});

async function signer() {
  const { publicKey, privateKey } = await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
  const jwk = { ...(await crypto.subtle.exportKey("jwk", publicKey)), kid: "k1" };
  const b64 = (o) => Buffer.from(typeof o === "string" ? o : JSON.stringify(o)).toString("base64url");
  const sign = async (claims, kid = "k1") => {
    const head = `${b64({ alg: "RS256", kid })}.${b64(claims)}`;
    const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", privateKey, new TextEncoder().encode(head));
    return `${head}.${Buffer.from(sig).toString("base64url")}`;
  };
  const fetchImpl = async (url) => {
    assert.equal(url, "https://team.cloudflareaccess.com/cdn-cgi/access/certs");
    return new Response(JSON.stringify({ keys: [jwk] }));
  };
  return { sign, fetchImpl };
}

test("a valid Access token for an allowed email gets in; anything else is refused", async () => {
  _resetCertCache();
  const { sign, fetchImpl } = await signer();
  const env = { ACCESS_TEAM_DOMAIN: "team.cloudflareaccess.com", ACCESS_AUD: "aud1", ALLOWED_EMAILS: "pavan@example.com" };
  const good = { aud: ["aud1"], iss: "https://team.cloudflareaccess.com", exp: Math.floor(Date.now() / 1000) + 600, email: "Pavan@example.com" };
  const call = async (token) => (await handle(req("status", { headers: { "cf-access-jwt-assertion": token } }), env, { fetchImpl })).status;
  assert.equal(await call(await sign(good)), 200);
  assert.equal(await call(await sign({ ...good, email: "someone@example.com" })), 403);
  assert.equal(await call(await sign({ ...good, aud: ["other"] })), 403);
  assert.equal(await call(await sign({ ...good, exp: 1 })), 403);
  assert.equal(await call(await sign({ ...good, iss: "https://evil.example" })), 403);
  const t = await sign(good);
  assert.equal(await call(t.slice(0, -4) + (t.endsWith("AAAA") ? "BBBB" : "AAAA")), 403);      // bad signature
  assert.equal(await verifyJwt("not.a.jwt", { team: "team.cloudflareaccess.com", aud: "aud1", fetchImpl }), null);
});

// ---------- no token ----------

test("without a token: status says so and data views explain how to fix it", async () => {
  const s = await (await handle(req("status"), LOCAL, { fetchImpl: noFetch })).json();
  assert.equal(s.configured, false);
  assert.equal(s.dryRun, true);
  for (const p of ["day?date=2026-10-30", "history", "social"]) {
    const r = await handle(req(p), LOCAL, { fetchImpl: noFetch });
    assert.equal(r.status, 503);
    assert.match((await r.json()).message, /GITHUB_TOKEN/);
  }
});

// ---------- writes ----------

test("dry run describes writes and never calls GitHub", async () => {
  const env = { ...LOCAL, GITHUB_TOKEN: "secret-token" };
  let r = await (await handle(post("control/rerun", {}), env, { fetchImpl: noFetch })).json();
  assert.equal(r.dryRun, true);
  assert.equal(r.request.path, "/repos/fiveminuteai/ai-daily/actions/workflows/daily.yml/dispatches");
  r = await (await handle(post("social/action", { item_id: "2026-10-30-x", action: "approve", text: "Hi" }), env, { fetchImpl: noFetch })).json();
  assert.deepEqual(r.request.body, { ref: "main", inputs: { item_id: "2026-10-30-x", action: "approve", text: "Hi" } });
  assert.ok(!JSON.stringify(r).includes("secret-token"));
});

test("live dispatch sends the token only to GitHub", async () => {
  const calls = [];
  const fetchImpl = async (url, init) => { calls.push({ url, init }); return new Response(null, { status: 204 }); };
  const r = await (await handle(post("control/redeploy", {}), { ...LOCAL, GITHUB_TOKEN: "tok", DRY_RUN: "0" }, { fetchImpl })).json();
  assert.equal(r.done, true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://api.github.com/repos/fiveminuteai/ai-daily/actions/workflows/deploy.yml/dispatches");
  assert.equal(calls[0].init.headers.Authorization, "Bearer tok");
  assert.ok(!JSON.stringify(r).includes("tok\""));
});

test("pause with a token reads site.yaml and shows the exact change", async () => {
  const yaml = "name: x\n# Set to true to stop\npaused: false\n";
  const fetchImpl = async (url, init) => {
    assert.equal(init.method, "GET");
    return new Response(JSON.stringify({ sha: "abc", content: Buffer.from(yaml).toString("base64") }));
  };
  const r = await (await handle(post("control/pause", { paused: true }), { ...LOCAL, GITHUB_TOKEN: "t" }, { fetchImpl })).json();
  assert.deepEqual(r.diff, { from: "paused: false", to: "paused: true" });
  assert.equal(r.done, false);
  assert.equal(setPaused(yaml, true), "name: x\n# Set to true to stop\npaused: true\n");
});

test("writes need the dashboard header, JSON, same origin and valid input", async () => {
  const env = { ...LOCAL };
  const status = async (r) => (await handle(r, env, { fetchImpl: noFetch })).status;
  assert.equal(await status(req("control/rerun", { method: "POST", body: "{}", headers: { "content-type": "application/json" } })), 400);
  assert.equal(await status(post("control/rerun", {}, { origin: "https://evil.example" })), 400);
  assert.equal(await status(post("social/action", { item_id: "../../etc", action: "approve" })), 400);
  assert.equal(await status(post("social/action", { item_id: "2026-10-30-x", action: "delete" })), 400);
  assert.equal(await status(post("control/pause", { paused: "yes" })), 400);
  assert.equal(await status(req("day?date=yesterday", {})), 503);         // no token is checked before input
});

// ---------- parsing ----------

const LOG = `2026-10-30T04:22:14.7380254Z ##[group]Run python -m fma daily || { sleep 120; python -m fma daily; } || {
2026-10-30T04:22:19.7879456Z 2026-10-30 04:22:19,787 INFO fma.pipeline: fetched 52 items: {'openai': 'ok:40', 'arxiv-ai': 'ok:0', 'msr': 'error:ReadTimeout', 'x': 'disabled', 'hf': 'ok:12'}
2026-10-30T04:22:21.6818154Z 2026-10-30 04:22:21,681 INFO fma.llm: groq used 2430 tokens
2026-10-30T04:22:51.4367847Z 2026-10-30 04:22:51,436 INFO fma.llm: groq used 2725 tokens
2026-10-30T04:25:00.0000000Z 2026-10-30 04:25:00,000 WARNING fma.pipeline: attempt 1 rejected: too few words; headline unverifiable
2026-10-30T04:30:42.7224226Z PUBLISHED 2026-10-30-mistral (960 words, model groq:openai/gpt-oss-120b)`;

test("old logs give fetch stats, model calls, rejections and the outcome", () => {
  const p = parseLog(LOG);
  assert.equal(p.fetched, 52);
  assert.deepEqual(p.sources.msr, { status: "error", items: 0, error: "ReadTimeout" });
  assert.deepEqual(p.sources.hf, { status: "ok", items: 12 });
  assert.equal(p.sources.x.status, "disabled");
  assert.equal(p.llmCalls, 2);
  assert.equal(p.tokens, 5155);
  assert.deepEqual(p.rejected, [{ n: 1, fails: ["too few words", "headline unverifiable"] }]);
  assert.equal(p.outcome.kind, "published");
  assert.equal(p.firstAt, "2026-10-30T04:22:14.7380254Z");
});

test("the FMA_RUN_SUMMARY line wins", () => {
  const p = parseLog(`${LOG}\n2026-10-30T04:30:43Z FMA_RUN_SUMMARY {"status":"published","stages":{"collect":{"status":"ok","items":3}}}`);
  assert.equal(p.summary.stages.collect.items, 3);
});

const run = (id, created, updated, conclusion = "success") => ({
  id, html_url: `https://github.com/r/${id}`, event: "schedule", status: "completed", conclusion,
  created_at: created, run_started_at: created, updated_at: updated,
});
const genJob = (commit) => ({ name: "generate", status: "completed", steps: [
  { name: "Write today's post", status: "completed", conclusion: "success", started_at: "2026-10-30T04:22:14Z", completed_at: "2026-10-30T04:30:42Z" },
  { name: "Commit the post", status: "completed", conclusion: commit, started_at: "2026-10-30T04:30:42Z", completed_at: "2026-10-30T04:30:50Z" }] });

test("a published day: every stage ok, the publishing run is the main one", () => {
  const d = buildDay({
    date: "2026-10-30",
    runs: [
      { run: run(2, "2026-10-30T05:42:29Z", "2026-10-30T05:42:43Z"), jobs: [genJob("skipped")], log: parseLog("2026-10-30T05:42:40Z SKIPPED 2026-10-30: post for 2026-10-30 already exists") },
      { run: run(1, "2026-10-30T04:22:02Z", "2026-10-30T04:31:23Z"), log: parseLog(LOG), jobs: [genJob("success"),
        { name: "deploy / build", status: "completed", conclusion: "success", started_at: "2026-10-30T04:31:00Z", completed_at: "2026-10-30T04:31:20Z" }] },
    ],
    post: { headline: "H", dek: "", slug: "s", model: "m", tags: [], word_count: 960, reading_minutes: 5, generated_at: "2026-10-30T04:30:21+00:00",
            sections: [{ title: "A", category: "models" }], sources: [1, 2],
            verification: { checked: 10, ok: 8, repaired: 1, dropped: 1, unused: 0, layer1_done: true, layer2_done: true } },
    queue: { items: [{ status: "pending" }, { status: "skipped" }] },
  });
  assert.equal(d.verdict, "ok");
  const st = Object.fromEntries(d.stages.map((s) => [s.key, s]));
  assert.equal(d.mainRunId, 1);
  assert.equal(d.runs.find((r) => r.id === 2).noop, true);
  assert.equal(st.collect.numbers.items, 52);
  assert.equal(st.collect.numbers.failing, 1);
  assert.equal(st.verify.numbers.confirmed, 8);
  assert.equal(st.publish.status, "ok");
  assert.equal(st.deploy.status, "ok");
  assert.equal(st.social.status, "pending");
  assert.equal(st.social.numbers.pending, 1);
});

test("a day with no run yet waits for the next schedule; code deploys don't count", () => {
  const d = buildDay({ date: "2026-10-31", now: new Date("2026-10-30T21:00:00Z"),
    deploys: [{ status: "completed", conclusion: "success", created_at: "2026-10-30T21:11:58Z", updated_at: "2026-10-30T21:12:30Z" }] });
  assert.equal(d.verdict, "waiting");
  assert.equal(d.nextRun, "2026-10-31T00:15:00.000Z");
  assert.ok(d.stages.every((s) => s.status === "pending"));
});

test("a skipped day is bad, and stages after the stop are skipped", () => {
  const log = parseLog("2026-10-30T04:30:00Z SKIPPED 2026-10-30: gate failed after retries: too few words");
  const d = buildDay({ date: "2026-10-30", runs: [{ run: run(1, "2026-10-30T00:20:00Z", "2026-10-30T00:40:00Z"), jobs: [genJob("skipped")], log }] });
  assert.equal(d.verdict, "bad");
  assert.equal(d.stages.find((s) => s.key === "gate").status, "failed");
  assert.equal(d.stages.find((s) => s.key === "publish").status, "skipped");
});

test("India-time day windows and schedules", () => {
  const [a, b] = dayRange("2026-10-31");
  assert.equal(a.toISOString(), "2026-10-30T18:30:00.000Z");
  assert.equal(b.toISOString(), "2026-10-31T18:30:00.000Z");
  assert.equal(nextSchedule("2026-10-31", new Date("2026-10-31T01:00:00Z")), "2026-10-31T01:45:00.000Z");
  assert.equal(nextSchedule("2026-10-31", new Date("2026-10-31T05:00:00Z")), null);
});

test("history marks the publishing run from the post's time, and earlier real runs as skipped", () => {
  const days = buildHistory({
    now: new Date("2026-10-30T20:00:00Z"), posts: ["2026-10-30"],
    meta: { "2026-10-30": { headline: "Mistral", generated_at: "2026-10-30T04:30:21+00:00" } },
    runs: [run(3, "2026-10-30T05:42:29Z", "2026-10-30T05:42:43Z"), run(2, "2026-10-30T04:22:02Z", "2026-10-30T04:31:23Z"),
           run(1, "2026-10-30T03:48:53Z", "2026-10-30T04:05:41Z")],
  });
  const d = days.find((x) => x.date === "2026-10-30");
  assert.equal(d.title, "Mistral");
  assert.deepEqual(d.runs.map((r) => [r.id, r.outcome, r.noop]), [[3, "unknown", true], [2, "published", false], [1, "skipped", false]]);
  assert.equal(days.find((x) => x.date === "2026-10-29").status, "before");
});
