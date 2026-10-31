// Local dev server in a normal browser: the same API handler as the Cloudflare Pages Function, plus the static files.
// For the desktop app (mail, accounts, roadmap, Windows Credential Manager) run desktop/app.mjs instead.
//
//   GITHUB_TOKEN=... node dev-server.mjs          (PowerShell: $env:GITHUB_TOKEN = "..."; node dev-server.mjs)
//   DRY_RUN=0 turns writes live. Leave it unset unless you mean it.

import { readFile, readdir } from "node:fs/promises";
import { join, normalize } from "node:path";
import { startServer } from "./lib/server.mjs";

const PORT = Number(process.env.PORT || 8788);
const env = {
  GITHUB_TOKEN: process.env.GITHUB_TOKEN || "", REPO: process.env.REPO || "fiveminuteai/ai-daily",
  DRY_RUN: process.env.DRY_RUN ?? "1",
};

// LOCAL_FILES=.. fills in files GitHub's main branch doesn't have yet (posts, reports, data/) from a local checkout,
// so an unmerged branch can be previewed. Main always wins, so new daily posts still appear.
const LOCAL_ROOT = process.env.LOCAL_FILES ? normalize(join(process.cwd(), process.env.LOCAL_FILES)) : "";
const local = LOCAL_ROOT ? {
  file: (p) => readFile(join(LOCAL_ROOT, normalize(p)), "utf-8").catch(() => null),
  list: (p) => readdir(join(LOCAL_ROOT, normalize(p))).then((names) => names.map((name) => ({ name }))).catch(() => []),
} : null;

await startServer({ port: PORT, env, local });
console.log(`Five Minute AI dashboard: http://127.0.0.1:${PORT}/`);
if (LOCAL_ROOT) console.log(`Files missing on main are read from ${LOCAL_ROOT}`);
console.log(`GitHub token: ${env.GITHUB_TOKEN ? "set" : "NOT set (views will say so)"}; writes: ${["0", "false"].includes(env.DRY_RUN) ? "LIVE" : "dry run"}`);
