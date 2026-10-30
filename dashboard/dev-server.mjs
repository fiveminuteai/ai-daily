// Local dev server: the same API handler as the Cloudflare Pages Function, plus the static files.
// Listens on 127.0.0.1 only, so the Access check is skipped (LOCAL_DEV=1). No dependencies.
//
//   GITHUB_TOKEN=... node dev-server.mjs          (PowerShell: $env:GITHUB_TOKEN = "..."; node dev-server.mjs)
//   DRY_RUN=0 turns writes live. Leave it unset unless you mean it.

import { createServer } from "node:http";
import { readFile, readdir } from "node:fs/promises";
import { extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { handle } from "./lib/api.js";

const PORT = Number(process.env.PORT || 8788);
const PUBLIC = fileURLToPath(new URL("./public/", import.meta.url));
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".svg": "image/svg+xml", ".ttf": "font/ttf", ".json": "application/json", ".png": "image/png",
                ".webmanifest": "application/manifest+json" };
const CSP = "default-src 'self'; img-src 'self' https://fiveminuteai.net data:; style-src 'self'; style-src-attr 'unsafe-inline'; script-src 'self'; "
  + "connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'";
const env = {
  GITHUB_TOKEN: process.env.GITHUB_TOKEN || "", REPO: process.env.REPO || "fiveminuteai/ai-daily",
  DRY_RUN: process.env.DRY_RUN ?? "1", LOCAL_DEV: "1",
};

// LOCAL_FILES=.. reads committed files (posts, reports, data/) from a local checkout instead of GitHub's main branch,
// so an unpushed branch can be previewed. Runs and logs still come from GitHub.
const LOCAL_ROOT = process.env.LOCAL_FILES ? normalize(join(process.cwd(), process.env.LOCAL_FILES)) : "";
const local = LOCAL_ROOT ? {
  file: (p) => readFile(join(LOCAL_ROOT, normalize(p)), "utf-8").catch(() => null),
  list: (p) => readdir(join(LOCAL_ROOT, normalize(p))).then((names) => names.map((name) => ({ name }))).catch(() => []),
} : null;

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
    if (url.pathname.startsWith("/api/")) {
      const chunks = [];
      for await (const c of req) chunks.push(c);
      const request = new Request(url, { method: req.method, headers: req.headers,
        body: ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(chunks) });
      const out = await handle(request, env, { local });
      res.writeHead(out.status, Object.fromEntries(out.headers));
      res.end(Buffer.from(await out.arrayBuffer()));
      console.log(`${req.method} ${url.pathname}${url.search} -> ${out.status}`);
      return;
    }
    const rel = url.pathname === "/" ? "index.html" : decodeURIComponent(url.pathname.slice(1));
    const file = normalize(join(PUBLIC, rel));
    if (!file.startsWith(PUBLIC.replace(/[\\/]$/, "") + sep) || rel.startsWith("_")) throw Object.assign(new Error(), { code: "ENOENT" });
    const data = await readFile(file);
    res.writeHead(200, { "Content-Type": TYPES[extname(file)] || "application/octet-stream", "Content-Security-Policy": CSP,
                         "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
    res.end(data);
  } catch (err) {
    res.writeHead(err.code === "ENOENT" || err.code === "EISDIR" ? 404 : 500, { "Content-Type": "text/plain" });
    res.end(err.code === "ENOENT" ? "not found" : "error");
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`Five Minute AI dashboard: http://127.0.0.1:${PORT}/`);
  if (LOCAL_ROOT) console.log(`Committed files from ${LOCAL_ROOT} (runs and logs from GitHub)`);
  console.log(`GitHub token: ${env.GITHUB_TOKEN ? "set" : "NOT set (views will say so)"}; writes: ${["0", "false"].includes(env.DRY_RUN) ? "LIVE" : "dry run"}`);
});
