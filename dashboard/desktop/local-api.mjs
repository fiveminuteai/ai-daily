// /api/local/* for the desktop app only: mail, accounts, roadmap, credentials, the Instagram pages feed. lib/api.js hands these routes here
// (key like "GET mail"), and only when the server runs on 127.0.0.1 with this module passed in.

import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { fetchInbox, ImapError } from "./imap.mjs";
import { DEFAULT_FEED, readPagesFeed, validFeedPath } from "./pages.mjs";
import { CREDENTIALS, addCommand, forget, listCredentials, readCredential } from "./secrets.mjs";
import { Store, dataDir } from "./store.mjs";

const ACCOUNTS = fileURLToPath(new URL("./accounts.json", import.meta.url));
export const COLUMNS = ["ideas", "next", "doing", "done"];
const DEFAULT_SETTINGS = { imapHost: "imap.zoho.in", imapPort: 993, mailWeb: "https://mail.zoho.in/", vault: "https://vault.bitwarden.com/" };

const bad = (message) => Object.assign(new Error(message), { badInput: true });
const fail = (userMessage, status = 502, code = "failed") => Object.assign(new Error(userMessage), { userMessage, status, code });

// Operational to-dos as of 1 Nov 2026, used only to fill an empty board the first time.
export function seedRoadmap(now = new Date()) {
  const at = now.toISOString();
  const card = (column, title, note = "", tag = "") => ({ id: `c${Math.random().toString(36).slice(2, 10)}`, column, title, note, tag, created: at, updated: at });
  return { version: 1, cards: [
    card("ideas", "Mail inside the app (needs a paid Zoho plan)", "Zoho's free plan has no IMAP; hello@ is an alias of pavan@.", "mail"),
    card("next", "Review the 3-week Reel test (around 21 Nov)", "Keep, change or stop the three-a-day Reels, using Stats.", "instagram"),
    card("ideas", "Decide on X API spend", "About $0.20 per post with a link; stats reading also paid.", "x"),
    card("ideas", "Apply for LinkedIn Community Management API", "Needed for company-page posting and page stats.", "linkedin"),
    card("ideas", "Host the control app on Cloudflare (Pages + Access)", "Phone access. Steps in dashboard/README.md.", "app"),
    card("doing", "Story Reels: three a day, 3-week test", "Approve each day on the Posts screen.", "instagram"),
    card("done", "Instagram posting and stats through the Meta app", "31 Oct 2026", "instagram"),
    card("done", "Control app merged", "31 Oct 2026", "app"),
    card("done", "Website stats (GoatCounter token)", "1 Nov 2026", "stats"),
    card("done", "Site live at fiveminuteai.net", "29 Oct 2026", "site"),
  ] };
}

export function validateRoadmap(input) {
  if (!input || !Array.isArray(input.cards)) throw bad("cards must be a list");
  if (input.cards.length > 500) throw bad("too many cards");
  const ids = new Set();
  const cards = input.cards.map((c) => {
    if (!c || typeof c.id !== "string" || !/^c[a-z0-9]{4,20}$/.test(c.id) || ids.has(c.id)) throw bad("each card needs a unique id");
    ids.add(c.id);
    if (!COLUMNS.includes(c.column)) throw bad(`unknown column ${c.column}`);
    const title = String(c.title || "").trim();
    if (!title || title.length > 200) throw bad("a card needs a title under 200 characters");
    return { id: c.id, column: c.column, title, note: String(c.note || "").slice(0, 2000), tag: String(c.tag || "").slice(0, 30),
             created: c.created || new Date().toISOString(), updated: new Date().toISOString() };
  });
  return { version: 1, cards };
}

function where(name) {
  return new Promise((resolve) => execFile("where.exe", [name], { windowsHide: true, timeout: 5000 }, (err, out) => resolve(err ? "" : String(out).split(/\r?\n/)[0])));
}

async function bitwarden() {
  const path = await where("bw");
  if (!path) return { cli: false, status: "not installed" };
  const out = await new Promise((resolve) => execFile(path, ["status"], { windowsHide: true, timeout: 15000 }, (err, so) => resolve(err ? "" : String(so))));
  try { return { cli: true, status: JSON.parse(out).status || "unknown" }; } catch { return { cli: true, status: "unknown" }; }
}

/** deps are injectable for tests: store, readCredential, listCredentials, fetchInbox, bitwarden, readPagesFeed, env. */
export function createLocalApi(deps = {}) {
  const store = deps.store || new Store();
  const readCred = deps.readCredential || readCredential;
  const listCreds = deps.listCredentials || listCredentials;
  const inbox = deps.fetchInbox || fetchInbox;
  const bw = deps.bitwarden || bitwarden;
  const pagesFeed = deps.readPagesFeed || readPagesFeed;
  const env = deps.env || process.env;
  // the feed path: Settings first, then FMA_PAGES_FEED, then faceless-ig next to this repository
  const feedPath = (s) => s.pagesFeed || env.FMA_PAGES_FEED || DEFAULT_FEED;
  const settings = async () => ({ ...DEFAULT_SETTINGS, ...(await store.read("settings", {})) });
  let mailCache = null;

  return {
    async handle(key, body, query) {
      switch (key) {
        case "GET info": {
          const [creds, vault, s] = await Promise.all([listCreds(), bw(), settings()]);
          return { desktop: true, dataDir: store.dir || dataDir(), settings: s, bitwarden: vault,
                   credentials: Object.entries(CREDENTIALS).map(([k, c]) => ({ name: k, label: c.label, why: c.why, stored: Boolean(creds[k]),
                                                                              add: addCommand(k), remove: `cmdkey /delete:FiveMinuteAI/${k}` })) };
        }
        case "GET accounts": {
          const [base, notes, s] = await Promise.all([readFile(ACCOUNTS, "utf-8").then(JSON.parse), store.read("account-notes", {}), settings()]);
          return { vault: s.vault, accounts: base.accounts.map((a) => ({ ...a, notes: notes[a.id] || "" })) };
        }
        case "POST accounts/notes": {
          const { id, notes } = body || {};
          if (typeof id !== "string" || !/^[a-z-]+$/.test(id)) throw bad("unknown account");
          if (typeof notes !== "string" || notes.length > 4000) throw bad("notes must be text under 4,000 characters");
          if (/(password|passwd|pwd|secret|token|api[ _-]?key)\s*[:=]\s*\S{6,}/i.test(notes)) {
            throw bad("That looks like a password or key. Keep those in Bitwarden, not in notes.");
          }
          const all = await store.read("account-notes", {});
          all[id] = notes.trim();
          await store.write("account-notes", all);
          return { saved: true };
        }
        case "GET roadmap":
          return store.read("roadmap", null).then((r) => r || store.write("roadmap", seedRoadmap()));
        case "POST roadmap":
          return store.write("roadmap", validateRoadmap(body));
        case "POST settings": {
          const s = await settings();
          const next = { ...s };
          if (body?.imapHost != null) {
            if (!/^imap\.[a-z0-9.-]+$/i.test(body.imapHost)) throw bad("IMAP host must look like imap.zoho.in");
            next.imapHost = body.imapHost;
          }
          if (body?.mailWeb != null) {
            if (!/^https:\/\/[a-z0-9.-]+\//i.test(body.mailWeb)) throw bad("mail link must be an https address");
            next.mailWeb = body.mailWeb;
          }
          if (body?.pagesFeed != null) {
            if (body.pagesFeed === "") delete next.pagesFeed;          // back to the default
            else if (!validFeedPath(body.pagesFeed)) throw bad("the pages feed must be a full path to a .json file");
            else next.pagesFeed = body.pagesFeed;
          }
          return store.write("settings", next);
        }
        case "GET mail": {
          const s = await settings();
          if (mailCache && Date.now() - mailCache.at < 60e3 && query?.get("refresh") !== "1") return mailCache.data;
          const cred = await readCred("zoho");
          if (!cred) {
            return { connected: false, web: s.mailWeb, add: addCommand("zoho"),
                     message: "No Zoho app password in Windows Credential Manager yet." };
          }
          try {
            const r = await inbox({ host: s.imapHost, port: s.imapPort, user: cred.user, pass: cred.secret, limit: 30 });
            const data = { connected: true, account: cred.user, web: s.mailWeb, host: s.imapHost, fetched: new Date().toISOString(), ...r };
            mailCache = { at: Date.now(), data };
            return data;
          } catch (err) {
            if (err instanceof ImapError) {
              if (/login failed/.test(err.message)) forget("zoho");
              throw fail(`Mail: ${err.message}.`, 502, "mail");
            }
            throw err;
          }
        }
        case "GET pages": {
          const s = await settings();
          return { ...(await pagesFeed(feedPath(s))), defaultPath: DEFAULT_FEED, custom: Boolean(s.pagesFeed) };
        }
        case "GET bitwarden":
          return bw();
        default:
          throw Object.assign(new Error("not found"), { userMessage: "Not found.", status: 404, code: "not_found" });
      }
    },
  };
}
