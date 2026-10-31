// The local HTTP server: the API handler plus the static page. Used by the dev server (browser) and by the desktop
// app. Listens on 127.0.0.1 only and refuses any other Host header, so a web page can't reach it through DNS
// rebinding. No dependencies.

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { handle } from "./api.js";

const PUBLIC = fileURLToPath(new URL("../public/", import.meta.url));
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".svg": "image/svg+xml", ".ttf": "font/ttf", ".json": "application/json", ".png": "image/png",
                ".ico": "image/x-icon", ".webmanifest": "application/manifest+json" };
export const CSP = "default-src 'self'; img-src 'self' https://fiveminuteai.net data:; media-src https://fiveminuteai.net; "
  + "style-src 'self'; style-src-attr 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; "
  + "manifest-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'";

/**
 * env: as for lib/api.js (LOCAL_DEV is forced on). local: committed-file fallback. desktop: the desktop module's
 * handler for /api/local/* (only the desktop app passes it). quiet: no request log.
 */
export function startServer({ port = 8788, env = {}, local = null, desktop = null, quiet = false } = {}) {
  const allowedHosts = new Set([`127.0.0.1:${port}`, `localhost:${port}`]);
  const fullEnv = { ...env, LOCAL_DEV: "1" };
  let lastSeen = Date.now();
  const server = createServer(async (req, res) => {
    try {
      if (!allowedHosts.has(String(req.headers.host || "").toLowerCase())) {
        res.writeHead(421, { "Content-Type": "text/plain" });
        res.end("wrong host");
        return;
      }
      lastSeen = Date.now();
      const url = new URL(req.url, `http://127.0.0.1:${port}`);
      if (url.pathname === "/api/ping") {        // the open window's heartbeat (desktop app); no data, no GitHub call
        res.writeHead(204, { "Cache-Control": "no-store" });
        res.end();
        return;
      }
      if (url.pathname.startsWith("/api/")) {
        const chunks = [];
        for await (const c of req) chunks.push(c);
        const request = new Request(url, { method: req.method, headers: req.headers,
          body: ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(chunks) });
        const out = await handle(request, fullEnv, { local, desktop });
        res.writeHead(out.status, Object.fromEntries(out.headers));
        res.end(Buffer.from(await out.arrayBuffer()));
        if (!quiet) console.log(`${req.method} ${url.pathname}${url.search} -> ${out.status}`);
        return;
      }
      const rel = url.pathname === "/" ? "index.html" : decodeURIComponent(url.pathname.slice(1));
      const file = normalize(join(PUBLIC, rel));
      if (!file.startsWith(PUBLIC.replace(/[\\/]$/, "") + sep) || rel.startsWith("_")) throw Object.assign(new Error(), { code: "ENOENT" });
      const data = await readFile(file);
      res.writeHead(200, { "Content-Type": TYPES[extname(file)] || "application/octet-stream", "Content-Security-Policy": CSP,
                           "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer" });
      res.end(data);
    } catch (err) {
      res.writeHead(err.code === "ENOENT" || err.code === "EISDIR" ? 404 : 500, { "Content-Type": "text/plain" });
      res.end(err.code === "ENOENT" ? "not found" : "error");
    }
  });
  server.idleMs = () => Date.now() - lastSeen;
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => resolve(server));
  });
}
