// Five Minute AI desktop app: starts the local server (127.0.0.1 only) and opens it in its own Microsoft Edge app
// window (separate profile, own taskbar icon). Closing the window stops the server. Started by the Start-menu /
// desktop shortcut (install.ps1) or by hand:  node dashboard/desktop/app.mjs [--live] [--no-window]
//
// GitHub token, first found wins: Windows Credential Manager "FiveMinuteAI/github", $env:GITHUB_TOKEN, `gh auth token`.

import { execFile, spawn } from "node:child_process";
import { existsSync, openSync } from "node:fs";
import { appendFile, mkdir, readFile, readdir, rename, writeFile } from "node:fs/promises";
import { join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { exportCache, importCache } from "../lib/github.js";
import { startServer } from "../lib/server.mjs";
import { createLocalApi } from "./local-api.mjs";
import { readCredential } from "./secrets.mjs";
import { dataDir } from "./store.mjs";
import { checksFromGitHub, gitRunner, selfUpdate, version } from "./update.mjs";

const PORT = Number(process.env.FMA_PORT || 8788);
const URL_ = `http://127.0.0.1:${PORT}/`;
const LIVE = process.argv.includes("--live");
const NO_WINDOW = process.argv.includes("--no-window");
const REPO_ROOT = fileURLToPath(new URL("../../", import.meta.url));
const DATA = dataDir();

async function logLine(text) {
  try {
    await mkdir(DATA, { recursive: true });
    await appendFile(join(DATA, "app.log"), `${new Date().toISOString()} ${text}\n`, "utf-8");
  } catch { /* logging must never stop the app */ }
}

function ghToken() {
  return new Promise((resolve) => execFile("gh", ["auth", "token"], { windowsHide: true, timeout: 10000 },
    (err, out) => resolve(err ? "" : String(out).trim())));
}

async function githubToken() {
  const fromVault = await readCredential("github").catch(() => null);
  if (fromVault?.secret) return { token: fromVault.secret, source: "Windows Credential Manager" };
  if (process.env.GITHUB_TOKEN) return { token: process.env.GITHUB_TOKEN, source: "environment" };
  const gh = await ghToken();
  return gh ? { token: gh, source: "GitHub CLI login" } : { token: "", source: "none" };
}

function edgePath() {
  const pf86 = process.env["ProgramFiles(x86)"] || "C:\\Program Files (x86)";
  const pf = process.env.ProgramFiles || "C:\\Program Files";
  return [join(pf86, "Microsoft\\Edge\\Application\\msedge.exe"), join(pf, "Microsoft\\Edge\\Application\\msedge.exe")]
    .find((p) => existsSync(p)) || "";
}

function openWindow() {
  const edge = edgePath();
  if (!edge) {                                // no Edge: the default browser still works
    spawn("cmd.exe", ["/c", "start", "", URL_], { windowsHide: true, detached: true, stdio: "ignore" }).unref();
    return null;
  }
  // msImplicitSignin off + --disable-sync: Edge would otherwise sign this fresh profile into the Windows Microsoft
  // account and turn sync on (checked 11 Nov 2026: with both flags the profile holds no account)
  return spawn(edge, [`--app=${URL_}`, `--user-data-dir=${join(process.env.LOCALAPPDATA || DATA, "FiveMinuteAI", "window")}`,
    "--no-first-run", "--no-default-browser-check", "--window-size=1440,900", "--disable-sync",
    "--disable-features=Translate,msImplicitSignin"],
  { windowsHide: false, stdio: "ignore" });
}

async function alreadyRunning() {
  try {
    const r = await fetch(`${URL_}api/status`, { signal: AbortSignal.timeout(1500) });
    return r.ok;
  } catch { return false; }
}

if (await alreadyRunning()) {               // second launch: just another window on the running app
  console.log(`Five Minute AI is already running at ${URL_}; ${NO_WINDOW ? "nothing else to start" : "opening another window"}.`);
  if (!NO_WINDOW) openWindow();
  process.exit(0);
}

// Bring this checkout up to GitHub's main before serving (desktop/update.mjs), so the desktop shows the same screens
// as the web version. After a real update, start once more on the new code; FMA_NO_UPDATE=1 turns this off.
const git = gitRunner(REPO_ROOT);
let update;
if (process.env.FMA_NO_UPDATE === "1") {
  update = { updated: false, reason: process.env.FMA_UPDATE_NOTE || "self-update off",
             version: await version(git).catch(() => ({ commit: "", date: "" })) };
} else {
  const { token: t } = await githubToken();
  update = await selfUpdate(git, t ? { isGreen: checksFromGitHub(t, process.env.REPO || "fiveminuteai/ai-daily") } : {});
  await logLine(`self-update: ${update.reason}${update.updated ? ` (${update.from} -> ${update.to})` : ""}`);
  if (update.updated) {
    // the restarted app's own errors go to app.log (11 Nov 2026: with stdio ignored, a crash on the new code
    // opened no window and left no trace)
    let out = "ignore";
    try { out = openSync(join(DATA, "app.log"), "a"); } catch { /* no log folder: start anyway */ }
    spawn(process.execPath, [fileURLToPath(import.meta.url), ...process.argv.slice(2)], {
      env: { ...process.env, FMA_NO_UPDATE: "1", FMA_UPDATE_NOTE: update.reason },
      detached: true, stdio: ["ignore", out, out], windowsHide: true }).unref();
    process.exit(0);
  }
}

const { token, source } = await githubToken();
const root = normalize(REPO_ROOT);
const local = {                             // files main doesn't have yet (an unmerged branch) come from this checkout
  file: (p) => readFile(join(root, normalize(p)), "utf-8").catch(() => null),
  list: (p) => readdir(join(root, normalize(p))).then((names) => names.map((name) => ({ name }))).catch(() => []),
};
// last session's GitHub responses, so the first screen draws at once (see lib/github.js importCache)
const CACHE_FILE = join(process.env.LOCALAPPDATA || DATA, "FiveMinuteAI", "github-cache.json");
try { importCache(JSON.parse(await readFile(CACHE_FILE, "utf-8"))); } catch { /* no cache yet: a normal cold start */ }
async function saveCache() {
  try {
    await mkdir(join(CACHE_FILE, ".."), { recursive: true });
    await writeFile(`${CACHE_FILE}.tmp`, JSON.stringify(exportCache()), "utf-8");
    await rename(`${CACHE_FILE}.tmp`, CACHE_FILE);
  } catch { /* the cache is only a speed-up */ }
}
setInterval(saveCache, 5 * 60e3).unref();

const server = await startServer({
  port: PORT, quiet: true, local, desktop: createLocalApi(),
  env: { GITHUB_TOKEN: token, REPO: process.env.REPO || "fiveminuteai/ai-daily", DRY_RUN: LIVE ? "0" : "1",
         APP_VERSION: update.version.commit ? `${update.version.commit} · ${update.version.date}` : "", APP_UPDATE: update.reason },
});
await logLine(`started on ${URL_}; GitHub token from ${source}; writes ${LIVE ? "LIVE" : "dry run"}`);
console.log(`Five Minute AI is running at ${URL_} (GitHub token: ${source}; writes: ${LIVE ? "LIVE" : "dry run"})`);

if (!NO_WINDOW) {
  // Edge can keep its process alive after the window closes, so the window's own heartbeat (one ping a minute,
  // see public/app.js) decides: no request for IDLE_MIN minutes means the window is gone, and the server stops.
  const IDLE_MIN = Number(process.env.FMA_IDLE_MIN || 5);
  const stop = async (why) => { await saveCache(); await logLine(`stopped: ${why}`); server.close(); process.exit(0); };
  openWindow();
  setInterval(() => { if (server.idleMs() > IDLE_MIN * 60e3) stop(`no window for ${IDLE_MIN} minutes`); }, 30e3);
}
