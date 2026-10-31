// Desktop-only modules: IMAP client, Credential Manager wrapper, local store, local API, server host check.
import assert from "node:assert/strict";
import { mkdtemp, readdir, rm } from "node:fs/promises";
import { connect as netConnect, createServer as netServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { handle, parseShareMedia } from "../lib/api.js";
import { startServer } from "../lib/server.mjs";
import { decodeWords, fetchInbox, parseFetch, parseList } from "../desktop/imap.mjs";
import { createLocalApi, seedRoadmap, validateRoadmap } from "../desktop/local-api.mjs";
import { parseCmdkeyList, readCredential } from "../desktop/secrets.mjs";
import { Store } from "../desktop/store.mjs";

// ---------- IMAP ----------

/** A fake IMAP server: records commands, answers like Zoho would. */
function fakeImap({ password = "app-pass", messages }) {
  const commands = [];
  const server = netServer((sock) => {
    sock.write("* OK Zoho IMAP ready\r\n");
    let buf = "";
    sock.on("data", (d) => {
      buf += d;
      let nl;
      while ((nl = buf.indexOf("\r\n")) >= 0) {
        const line = buf.slice(0, nl);
        buf = buf.slice(nl + 2);
        const [tag, cmd, ...rest] = line.split(" ");
        commands.push(`${cmd} ${rest.join(" ")}`.trim());
        if (cmd === "LOGIN") {
          sock.write(rest.join(" ").endsWith(`"${password}"`) ? `${tag} OK logged in\r\n` : `${tag} NO [AUTHENTICATIONFAILED] Invalid credentials\r\n`);
        } else if (cmd === "EXAMINE" || cmd === "SELECT") {
          sock.write(`* ${messages.length} EXISTS\r\n* 0 RECENT\r\n${tag} OK [READ-ONLY] done\r\n`);
        } else if (cmd === "FETCH") {
          sock.write(messages.join("") + `${tag} OK FETCH completed\r\n`);
        } else if (cmd === "SEARCH") {
          sock.write(`* SEARCH 2\r\n${tag} OK done\r\n`);
        } else if (cmd === "LOGOUT") {
          sock.end(`* BYE\r\n${tag} OK bye\r\n`);
        } else {
          sock.write(`${tag} BAD unknown\r\n`);
        }
      }
    });
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve({ server, port: server.address().port, commands })));
}

const subjectLit = "Sponsorship \"inquiry\"\r\nfor Five Minute AI";
const MESSAGES = [
  `* 1 FETCH (UID 41 FLAGS (\\Seen) INTERNALDATE "30-Oct-2026 09:15:00 +0530" ENVELOPE ("Fri, 30 Oct 2026 09:15:00 +0530" "=?UTF-8?B?V2VsY29tZSB0byBab2hv?=" (("Zoho" NIL "noreply" "zoho.in")) NIL NIL NIL NIL NIL NIL "<a@z>"))\r\n`,
  `* 2 FETCH (UID 42 FLAGS (\\Flagged) INTERNALDATE "31-Oct-2026 08:00:00 +0530" ENVELOPE ("Sat, 31 Oct 2026 08:00:00 +0530" {${Buffer.byteLength(subjectLit)}}\r\n${subjectLit} (("=?UTF-8?Q?Ana_M=C3=BCller?=" NIL "ana" "example.com")) NIL NIL NIL NIL NIL NIL "<b@e>"))\r\n`,
];

test("IMAP: reads envelopes read-only, newest first, with literals and encoded words", async () => {
  const { server, port, commands } = await fakeImap({ messages: MESSAGES });
  try {
    const r = await fetchInbox({ host: "127.0.0.1", port, user: "hello@fiveminuteai.net", pass: "app-pass", limit: 25,
                                 connect: (o) => netConnect(o.port, o.host) });
    assert.equal(r.total, 2);
    assert.equal(r.unread, 1);
    assert.deepEqual(r.messages.map((m) => m.uid), [42, 41]);
    const [b, a] = r.messages;
    assert.equal(b.subject, 'Sponsorship "inquiry" for Five Minute AI');
    assert.deepEqual(b.from, { name: "Ana Müller", email: "ana@example.com" });
    assert.equal(b.unread, true);
    assert.equal(b.flagged, true);
    assert.equal(a.subject, "Welcome to Zoho");
    assert.equal(a.unread, false);
    assert.equal(a.date, "2026-10-30T03:45:00.000Z");
    // never SELECT (which can mark mail as read), never STORE, never fetch bodies
    assert.ok(commands.some((c) => c.startsWith("EXAMINE")));
    assert.ok(!commands.some((c) => /^(SELECT|STORE|EXPUNGE)/.test(c) || /BODY/.test(c)));
  } finally {
    server.close();
  }
});

test("IMAP: wrong app password is a clear error", async () => {
  const { server, port } = await fakeImap({ messages: [] });
  try {
    await assert.rejects(fetchInbox({ host: "127.0.0.1", port, user: "u", pass: "wrong", connect: (o) => netConnect(o.port, o.host) }),
      /login failed/);
  } finally {
    server.close();
  }
});

test("IMAP: parser pieces", () => {
  assert.deepEqual(parseList('(A "b c" NIL (d "e\\"f"))'), [["A", "b c", null, ["d", 'e"f']]]);
  assert.equal(decodeWords("=?utf-8?q?Hello_World?= =?UTF-8?B?IQ==?="), "Hello World!");
  assert.equal(parseFetch("* 3 EXISTS"), null);
  assert.equal(parseFetch('* 1 FETCH (FLAGS () ENVELOPE (NIL NIL NIL NIL NIL NIL NIL NIL NIL NIL))').subject, "(no subject)");
});

// ---------- secrets ----------

test("Credential Manager: parse cmdkey output, read via the helper, unknown names refused", async () => {
  assert.deepEqual(parseCmdkeyList("Currently stored credentials for FiveMinuteAI/*:\r\n\r\n    Target: FiveMinuteAI/zoho\r\n    Type: Generic\r\n"),
    { github: false, zoho: true });
  assert.deepEqual(parseCmdkeyList("* NONE *"), { github: false, zoho: false });
  const calls = [];
  const runner = async (file, args) => { calls.push(args.at(-1)); return args.at(-1) === "FiveMinuteAI/github" ? { code: 0, stdout: '{"user":"github","secret":"tok"}' } : { code: 2, stdout: "" }; };
  assert.deepEqual(await readCredential("github", { runner }), { user: "github", secret: "tok" });
  assert.equal(await readCredential("zoho", { runner }), null);
  await assert.rejects(readCredential("../evil", { runner }), /unknown credential/);
  assert.deepEqual(calls, ["FiveMinuteAI/github", "FiveMinuteAI/zoho"]);
});

// ---------- store + local API ----------

async function tempStore() {
  const dir = await mkdtemp(join(tmpdir(), "fma-test-"));
  return { store: new Store(dir), dir, done: () => rm(dir, { recursive: true, force: true }) };
}

test("store: atomic writes, no temp files left, bad names refused", async () => {
  const { store, dir, done } = await tempStore();
  try {
    assert.deepEqual(await store.read("roadmap", { x: 1 }), { x: 1 });
    await store.write("roadmap", { a: 1 });
    assert.deepEqual(await store.read("roadmap"), { a: 1 });
    assert.deepEqual(await readdir(dir), ["roadmap.json"]);
    await assert.rejects(store.write("../x", {}), /bad store name/);
  } finally { await done(); }
});

test("roadmap: seeded once, validated on save", async () => {
  const { store, done } = await tempStore();
  try {
    const api = createLocalApi({ store });
    const first = await api.handle("GET roadmap");
    assert.ok(first.cards.length >= 5 && first.cards.every((c) => ["ideas", "next", "doing", "done"].includes(c.column)));
    const saved = await api.handle("POST roadmap", { cards: [first.cards[0]] });
    assert.equal((await api.handle("GET roadmap")).cards.length, 1);
    assert.equal(saved.cards[0].title, first.cards[0].title);
    const card = first.cards[0];
    assert.throws(() => validateRoadmap({ cards: [card, card] }), /unique id/);
    assert.throws(() => validateRoadmap({ cards: [{ ...card, column: "someday" }] }), /unknown column/);
    assert.throws(() => validateRoadmap({ cards: [{ ...card, title: " " }] }), /title/);
    assert.equal(seedRoadmap().cards.some((c) => /password|token\s*[:=]/i.test(c.note) && !/cmdkey|secret/.test(c.note)), false);
  } finally { await done(); }
});

test("account notes refuse anything that looks like a password", async () => {
  const { store, done } = await tempStore();
  try {
    const api = createLocalApi({ store });
    await api.handle("POST accounts/notes", { id: "github", notes: "2FA via authenticator app" });
    for (const bad of ["password: hunter2xyz", "API key = sk-123456", "token:abcdef123"]) {
      await assert.rejects(api.handle("POST accounts/notes", { id: "x", notes: bad }), (e) => e.badInput && /Bitwarden/.test(e.message));
    }
    const { accounts } = await api.handle("GET accounts");
    assert.equal(accounts.find((a) => a.id === "github").notes, "2FA via authenticator app");
    assert.equal(accounts.find((a) => a.id === "x").notes, "");
    assert.ok(accounts.every((a) => !JSON.stringify(a).match(/@gmail\.com/)));   // no personal emails in the shipped list
  } finally { await done(); }
});

test("mail: not connected without a credential; connected path uses settings and the app password", async () => {
  const { store, done } = await tempStore();
  try {
    let seen = null;
    const none = createLocalApi({ store, readCredential: async () => null });
    const off = await none.handle("GET mail", null, new URLSearchParams());
    assert.equal(off.connected, false);
    assert.match(off.add, /^cmdkey \/generic:FiveMinuteAI\/zoho /);
    const on = createLocalApi({ store, readCredential: async () => ({ user: "hello@fiveminuteai.net", secret: "pw" }),
      fetchInbox: async (o) => { seen = o; return { folder: "INBOX", total: 1, unread: 1, messages: [{ subject: "Hi" }] }; } });
    await on.handle("POST settings", { imapHost: "imap.zoho.com" });
    const r = await on.handle("GET mail", null, new URLSearchParams());
    assert.equal(r.connected, true);
    assert.equal(seen.host, "imap.zoho.com");
    assert.equal(seen.pass, "pw");
    assert.ok(!JSON.stringify(r).includes("pw\""));                         // the password never goes back to the page
    await assert.rejects(on.handle("POST settings", { imapHost: "evil.com" }), /IMAP host/);
  } finally { await done(); }
});

// ---------- API gating, media, scheduling ----------

const LOCAL = { LOCAL_DEV: "1" };
const desk = { handle: async (key) => ({ key }) };
const req = (path, init) => new Request(`http://127.0.0.1:8788/api/${path}`, init);
const post = (path, body) => req(path, { method: "POST", body: JSON.stringify(body), headers: { "content-type": "application/json", "x-fma-dashboard": "1" } });

test("/api/local/* only exists in the desktop app", async () => {
  assert.equal((await handle(req("local/info"), LOCAL, {})).status, 404);                 // dev server: no desktop module
  assert.equal((await handle(req("local/info"), {}, { desktop: desk })).status, 403);      // Cloudflare: Access first
  const r = await handle(req("local/info"), LOCAL, { desktop: desk });
  assert.deepEqual(await r.json(), { key: "GET info" });
  assert.equal((await (await handle(req("status"), LOCAL, { desktop: desk })).json()).desktop, true);
  assert.equal((await (await handle(req("status"), LOCAL, {})).json()).desktop, false);
  // desktop writes still need the dashboard header
  assert.equal((await handle(req("local/roadmap", { method: "POST", body: "{}", headers: { "content-type": "application/json" } }), LOCAL, { desktop: desk })).status, 400);
});

test("a signed-in Cloudflare request still can't reach desktop routes, even if a desktop module were passed", async () => {
  const { _resetCertCache } = await import("../lib/api.js");
  _resetCertCache();
  const { publicKey, privateKey } = await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
  const jwk = { ...(await crypto.subtle.exportKey("jwk", publicKey)), kid: "k1" };
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
  const head = `${b64({ alg: "RS256", kid: "k1" })}.${b64({ aud: ["a1"], iss: "https://t.cloudflareaccess.com", exp: Math.floor(Date.now() / 1000) + 600, email: "p@example.com" })}`;
  const token = `${head}.${Buffer.from(await crypto.subtle.sign("RSASSA-PKCS1-v1_5", privateKey, new TextEncoder().encode(head))).toString("base64url")}`;
  const env = { ACCESS_TEAM_DOMAIN: "t.cloudflareaccess.com", ACCESS_AUD: "a1", ALLOWED_EMAILS: "p@example.com" };
  const fetchImpl = async () => new Response(JSON.stringify({ keys: [jwk] }));
  const signed = (path) => req(path, { headers: { "cf-access-jwt-assertion": token } });
  assert.equal((await handle(signed("status"), env, { fetchImpl, desktop: desk })).status, 200);       // signed in fine
  assert.equal((await handle(signed("local/mail"), env, { fetchImpl, desktop: desk })).status, 404);   // but no desktop routes
  assert.equal((await (await handle(signed("status"), env, { fetchImpl, desktop: desk })).json()).desktop, false);
});

test("media: slides and Reel read from the share page", async () => {
  const html = '<img src="/share/2026-10-30/carousel/02.jpg"><img src="/share/2026-10-30/carousel/01.jpg"><img src="/share/2026-10-30/carousel/01.jpg">'
    + '<video src="/share/2026-10-30/reel.mp4"></video><a href="/share/2026-10-30/carousel.zip">';
  const m = parseShareMedia(html, "2026-10-30");
  assert.deepEqual(m.slides, ["https://fiveminuteai.net/share/2026-10-30/carousel/01.jpg", "https://fiveminuteai.net/share/2026-10-30/carousel/02.jpg"]);
  assert.equal(m.reel, "https://fiveminuteai.net/share/2026-10-30/reel.mp4");
  assert.equal(m.zip, "https://fiveminuteai.net/share/2026-10-30/carousel.zip");
  const fetchImpl = async (url) => (url.endsWith("/2026-10-31/") ? new Response("nf", { status: 404 }) : new Response(html));
  const none = await (await handle(req("media?date=2026-10-31"), { ...LOCAL, GITHUB_TOKEN: "t" }, { fetchImpl })).json();
  assert.deepEqual(none.slides, []);
  assert.equal((await handle(req("media?date=../x"), { ...LOCAL, GITHUB_TOKEN: "t" }, { fetchImpl })).status, 400);
});

test("scheduling: next 14 days only, dry run by default, live writes the queue file", async () => {
  const env = { ...LOCAL, GITHUB_TOKEN: "t" };
  const soon = new Date(Date.now() + 3600e3).toISOString();
  const status = async (b) => (await handle(post("social/schedule", b), env, { fetchImpl: () => { throw new Error("no network"); } })).status;
  assert.equal(await status({ item_id: "2026-10-30-x", at: "2020-01-01T00:00:00Z" }), 400);
  assert.equal(await status({ item_id: "2026-10-30-x", at: new Date(Date.now() + 20 * 864e5).toISOString() }), 400);
  assert.equal(await status({ item_id: "bad", at: soon }), 400);
  const dry = await (await handle(post("social/schedule", { item_id: "2026-10-30-x", at: soon }), env, {})).json();
  assert.equal(dry.dryRun, true);
  assert.equal(dry.request.scheduled_at, soon);

  const queue = { items: [{ id: "2026-10-30-x", status: "pending" }, { id: "2026-10-30-linkedin", status: "pending" }] };
  let put = null;
  const fetchImpl = async (url, init) => {
    if (init.method === "PUT") { put = JSON.parse(init.body); return new Response("{}"); }
    return new Response(JSON.stringify({ sha: "q1", content: Buffer.from(JSON.stringify(queue)).toString("base64") }));
  };
  const live = await (await handle(post("social/schedule", { item_id: "2026-10-30-x", at: soon }), { ...env, DRY_RUN: "0" }, { fetchImpl })).json();
  assert.equal(live.done, true);
  const saved = JSON.parse(Buffer.from(put.content, "base64").toString());
  assert.equal(saved.items[0].scheduled_at, soon);
  assert.equal(saved.items[1].scheduled_at, undefined);
  assert.equal(put.sha, "q1");
});

test("server: only 127.0.0.1/localhost Host headers are answered (DNS-rebinding guard)", async () => {
  const port = 18000 + Math.floor(Math.random() * 1000);
  const server = await startServer({ port, quiet: true, env: {} });
  try {
    const ask = (host) => new Promise((resolve) => {
      const s = netConnect(port, "127.0.0.1", () => s.write(`GET /api/status HTTP/1.1\r\nHost: ${host}\r\nConnection: close\r\n\r\n`));
      let out = "";
      s.on("data", (d) => { out += d; });
      s.on("end", () => resolve(Number(out.split(" ")[1])));
    });
    assert.equal(await ask(`127.0.0.1:${port}`), 200);
    assert.equal(await ask(`localhost:${port}`), 200);
    assert.equal(await ask(`evil.example:${port}`), 421);
    // heartbeat: /api/ping answers 204 and resets the idle clock the desktop app uses to stop itself
    await new Promise((r) => setTimeout(r, 120));
    assert.ok(server.idleMs() >= 100);
    const ping = await fetch(`http://127.0.0.1:${port}/api/ping`);
    assert.equal(ping.status, 204);
    assert.ok(server.idleMs() < 100);
  } finally {
    server.close();
  }
});

// ---------- story Reels ----------

const REEL_QUEUE = { date: "2026-11-01", items: [
  { id: "2026-11-01-instagram", platform: "instagram", status: "pending" },
  { id: "2026-11-01-reel-1", platform: "instagram_reel", status: "pending", scheduled_at: "2026-11-01T03:30:00+00:00" },
  { id: "2026-11-01-reel-2", platform: "instagram_reel", status: "posted", posted_url: "https://www.instagram.com/reel/x/" },
  { id: "2026-11-01-reel-3", platform: "instagram_reel", status: "pending", scheduled_at: "2026-11-01T13:30:00+00:00" },
] };

function reelGithub(queue = REEL_QUEUE) {
  const dispatched = [];
  const fetchImpl = async (url, init = {}) => {
    if ((init.method || "GET") === "POST" && url.endsWith("/dispatches")) { dispatched.push(JSON.parse(init.body)); return new Response(null, { status: 204 }); }
    if (url.includes("contents/data/social/2026-11-01.json")) return new Response(JSON.stringify(queue));
    return new Response("{}", { status: 404 });
  };
  return { fetchImpl, dispatched };
}

test("Reel items can be approved, skipped and scheduled one by one", async () => {
  const env = { ...LOCAL, GITHUB_TOKEN: "t" };
  const soon = new Date(Date.now() + 3600e3).toISOString();
  for (const [path, b] of [["social/action", { item_id: "2026-11-01-reel-2", action: "approve" }],
                           ["social/action", { item_id: "2026-11-01-reel-3", action: "skip" }],
                           ["social/schedule", { item_id: "2026-11-01-reel-1", at: soon }]]) {
    const r = await handle(post(path, b), env, {});
    assert.equal(r.status, 200, `${path} ${JSON.stringify(b)}`);
    assert.equal((await r.json()).dryRun, true);
  }
  for (const bad of ["2026-11-01-reel-0", "2026-11-01-reel-x", "2026-11-01-reel-1/../x", "2026-11-01-reels"]) {
    assert.equal((await handle(post("social/action", { item_id: bad, action: "approve" }), env, {})).status, 400, bad);
  }
});

test("approve all Reels: dry run lists only the pending Reels; live sends one approval each", async () => {
  const { fetchImpl, dispatched } = reelGithub();
  const dry = await (await handle(post("social/approve-reels", { date: "2026-11-01" }), { ...LOCAL, GITHUB_TOKEN: "t" }, { fetchImpl })).json();
  assert.equal(dry.dryRun, true);
  assert.deepEqual(dry.items, ["2026-11-01-reel-1", "2026-11-01-reel-3"]);         // posted Reel and the carousel left out
  assert.deepEqual(dry.requests.map((r) => r.body.inputs), [{ item_id: "2026-11-01-reel-1", action: "approve" }, { item_id: "2026-11-01-reel-3", action: "approve" }]);
  assert.equal(dispatched.length, 0);
  const live = await (await handle(post("social/approve-reels", { date: "2026-11-01" }), { ...LOCAL, GITHUB_TOKEN: "t", DRY_RUN: "0" }, { fetchImpl })).json();
  assert.equal(live.done, true);
  assert.deepEqual(dispatched.map((d) => [d.ref, d.inputs.item_id, d.inputs.action]),
    [["main", "2026-11-01-reel-1", "approve"], ["main", "2026-11-01-reel-3", "approve"]]);
});

test("approve all Reels refuses when nothing is pending, a bad date, or no token", async () => {
  const none = reelGithub({ items: REEL_QUEUE.items.map((i) => ({ ...i, status: "posted" })) });
  const st = async (body, env, f) => (await handle(post("social/approve-reels", body), env, { fetchImpl: f })).status;
  assert.equal(await st({ date: "2026-11-01" }, { ...LOCAL, GITHUB_TOKEN: "t" }, none.fetchImpl), 400);
  assert.equal(await st({ date: "1 Nov" }, { ...LOCAL, GITHUB_TOKEN: "t" }, none.fetchImpl), 400);
  assert.equal(await st({ date: "2026-11-01" }, { ...LOCAL }, none.fetchImpl), 400);
  assert.equal(none.dispatched.length, 0);
});

test("share page: story Reels are listed in order, without duplicates", () => {
  const m = parseShareMedia('<video src="/share/2026-11-01/reels/03.mp4"></video><video src="/share/2026-11-01/reels/01.mp4"></video>'
    + '<a href="/share/2026-11-01/reels/01.mp4">dl</a><video src="/share/2026-11-01/reels/01.mp4"></video>', "2026-11-01");
  assert.deepEqual(m.reels, ["https://fiveminuteai.net/share/2026-11-01/reels/01.mp4", "https://fiveminuteai.net/share/2026-11-01/reels/03.mp4"]);
  assert.deepEqual(parseShareMedia("<p>no media</p>", "2026-11-01").reels, []);
});
